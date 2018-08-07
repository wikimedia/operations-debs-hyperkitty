# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 by the Free Software Foundation, Inc.
#
# This file is part of HyperKitty.
#
# HyperKitty is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# HyperKitty is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# HyperKitty.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Aurelien Bompard <abompard@fedoraproject.org>
#

import re
from email.message import EmailMessage

from django.conf import settings
from django.db import DataError
from django.utils import timezone
from django_mailman3.lib.scrub import Scrubber

from hyperkitty.lib.utils import (
    get_ref, parseaddr, parsedate, header_to_unicode, get_message_id)
from hyperkitty.models import (
    MailingList, Sender, Email, Attachment, ArchivePolicy)
from hyperkitty.tasks import update_from_mailman, sender_mailman_id

import logging
logger = logging.getLogger(__name__)


UNIXFROM_DATE_RE = re.compile(r'^\s*[^\s]+@[^\s]+ (.*)$')


class DuplicateMessage(Exception):
    """
    The database already contains an email with the same Message-ID header.
    """


def add_to_list(list_name, message):
    assert isinstance(message, EmailMessage)
    # timeit("1 start")
    mlist = MailingList.objects.get_or_create(name=list_name)[0]
    if not getattr(settings, "HYPERKITTY_BATCH_MODE", False):
        update_from_mailman.delay(mlist.name)
    mlist.save()
    if mlist.archive_policy == ArchivePolicy.never.value:
        logger.info("Archiving disabled by list policy for %s", list_name)
        return
    if "Message-Id" not in message:
        raise ValueError("No 'Message-Id' header in email", message)
    # timeit("2 after ml, before checking email & sender")
    msg_id = get_message_id(message)
    if Email.objects.filter(mailinglist=mlist, message_id=msg_id).exists():
        raise DuplicateMessage(msg_id)
    email = Email(mailinglist=mlist, message_id=msg_id)
    email.in_reply_to = get_ref(message)  # Find thread id
    if message.get_unixfrom() is not None:
        mo = UNIXFROM_DATE_RE.match(message.get_unixfrom())
        if mo:
            archived_date = parsedate(mo.group(1))
            if archived_date is not None:
                email.archived_date = archived_date

    # Sender
    try:
        from_str = header_to_unicode(message['From'])
        from_name, from_email = parseaddr(from_str)
        from_name = from_name.strip()
        sender_address = from_email.encode('ascii').decode("ascii").strip()
    except (UnicodeDecodeError, UnicodeEncodeError):
        raise ValueError("Non-ascii sender address", message)
    if not sender_address:
        if from_name:
            sender_address = re.sub("[^a-z0-9]", "", from_name.lower())
            if not sender_address:
                sender_address = "unknown"
            sender_address = "{}@example.com".format(sender_address)
        else:
            sender_address = "unknown@example.com"
    email.sender_name = from_name
    sender = Sender.objects.get_or_create(address=sender_address)[0]
    email.sender = sender
    if not getattr(settings, "HYPERKITTY_BATCH_MODE", False):
        sender_mailman_id.delay(sender.pk)
    # timeit("3 after sender, before email content")

    # Headers
    email.subject = header_to_unicode(message.get('Subject'))
    if email.subject is not None:
        # limit subject size to 512, it's a varchar field
        email.subject = email.subject[:512]
    msg_date = parsedate(message.get("Date"))
    if msg_date is None:
        # Absent or unparseable date
        msg_date = timezone.now()
    utcoffset = msg_date.utcoffset()
    if msg_date.tzinfo is not None:
        msg_date = msg_date.astimezone(timezone.utc)  # store in UTC
    email.date = msg_date
    if utcoffset is None:
        email.timezone = 0
    else:
        # in minutes
        email.timezone = int(
            ((utcoffset.days * 24 * 60 * 60) + utcoffset.seconds) / 60)

    # Content
    scrubber = Scrubber(message)
    # warning: scrubbing modifies the msg in-place
    email.content, attachments = scrubber.scrub()
    # timeit("4 after email content, before signals")

    # TODO: detect category?

    # Find the parent email.
    # This can't be moved to Email.on_pre_save() because Email.set_parent()
    # needs to be free to change the parent independently from the in_reply_to
    # property, and will save() the instance.
    # This, along with some of the work done in Email.on_pre_save(), could be
    # moved to an async task, but the rest of the app must be able to cope with
    # emails lacking this data, and email being process randomly (child before
    # parent). The work in Email.on_post_created() also depends on it, so be
    # careful with task dependencies if you ever do this.
    # Plus, it has "premature optimization" written all over it.
    if email.in_reply_to is not None:
        try:
            ref_msg = Email.objects.get(
                mailinglist=email.mailinglist,
                message_id=email.in_reply_to)
        except Email.DoesNotExist:
            # the parent may not be archived (on partial imports), create a new
            # thread for now.
            pass
        else:
            # re-use parent's thread-id
            email.parent = ref_msg
            email.thread_id = ref_msg.thread_id

    try:
        email.save()
    except DataError as e:
        raise ValueError(str(e))

    # Attachments (email must have been saved before)
    for attachment in attachments:
        counter, name, content_type, encoding, content = attachment
        if Attachment.objects.filter(email=email, counter=counter).exists():
            continue
        att = Attachment.objects.create(
            email=email, counter=counter, name=name, content_type=content_type,
            encoding=encoding)
        att.set_content(content)
        att.save()

    return email.message_id_hash
