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

import os
import re
from email.message import EmailMessage

from django.conf import settings
from django.db import models, IntegrityError
from django.utils.timezone import now, get_fixed_timezone

from hyperkitty.lib.analysis import compute_thread_order_and_depth
from .common import VotesCachedValue
from .mailinglist import MailingList
from .thread import Thread
from .vote import Vote

import logging
logger = logging.getLogger(__name__)


class Email(models.Model):
    """
    An archived email, from a mailing-list. It is identified by both the list
    name and the message id.
    """
    mailinglist = models.ForeignKey(
        "MailingList", related_name="emails", on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255, db_index=True)
    message_id_hash = models.CharField(max_length=255, db_index=True)
    sender = models.ForeignKey(
        "Sender", related_name="emails", on_delete=models.CASCADE)
    sender_name = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=512, db_index=True)
    content = models.TextField()
    date = models.DateTimeField(db_index=True)
    timezone = models.SmallIntegerField()
    in_reply_to = models.CharField(
        max_length=255, null=True, blank=True, db_index=True)
    # Delete behavior is handled by on_pre_delete()
    parent = models.ForeignKey(
        "self", blank=True, null=True, on_delete=models.DO_NOTHING,
        related_name="children")
    thread = models.ForeignKey(
        "Thread", related_name="emails", on_delete=models.CASCADE)
    archived_date = models.DateTimeField(default=now, db_index=True)
    thread_depth = models.IntegerField(default=0)
    thread_order = models.IntegerField(null=True, blank=True, db_index=True)

    ADDRESS_REPLACE_RE = re.compile(r"([\w.+-]+)@([\w.+-]+)")

    def __init__(self, *args, **kwargs):
        super(Email, self).__init__(*args, **kwargs)
        self.cached_values = {
            "votes": VotesCachedValue(self),
        }

    def __lt__(self, other):
        return self.date < other.date

    class Meta:
        unique_together = ("mailinglist", "message_id")

    def get_votes(self):
        return self.cached_values["votes"]()

    def vote(self, value, user):
        # Checks if the user has already voted for this message.
        existing = self.votes.filter(user=user).first()
        if existing is not None and existing.value == value:
            return  # Vote already recorded (should I raise an exception?)
        if value not in (0, 1, -1):
            raise ValueError("A vote can only be +1 or -1 (or 0 to cancel)")
        if existing is not None:
            # vote changed or cancelled
            if value == 0:
                existing.delete()
            else:
                existing.value = value
                existing.save()
        else:
            # new vote
            vote = Vote(email=self, user=user, value=value)
            vote.save()

    def set_parent(self, parent):
        if self.id == parent.id:
            raise ValueError("An email can't be its own parent")
        # Compute the subthread
        subthread = [self]

        def _collect_children(current_email):
            children = list(current_email.children.all())
            if not children:
                return
            subthread.extend(children)
            for child in children:
                _collect_children(child)
        _collect_children(self)
        # now set my new parent value
        old_parent_id = self.parent_id
        self.parent = parent
        self.save(update_fields=["parent_id"])
        # If my future parent is in my current subthread, I need to set its
        # parent to my current parent
        if parent in subthread:
            parent.parent_id = old_parent_id
            parent.save(update_fields=["parent_id"])
            # do it after setting the new parent_id to avoid having two
            # parent_ids set to None at the same time (IntegrityError)
        if self.thread_id != parent.thread_id:
            # we changed the thread, reattach the subthread
            former_thread = self.thread
            for child in subthread:
                child.thread = parent.thread
                child.save(update_fields=["thread_id"])
                if child.date > parent.thread.date_active:
                    parent.thread.date_active = child.date
            parent.thread.save()
            # if we were the starting email, or former thread may be empty
            if former_thread.emails.count() == 0:
                former_thread.delete()
        compute_thread_order_and_depth(parent.thread)

    def as_message(self, escape_addresses=True):
        # http://wordeology.com/computer/how-to-send-good-unicode-email-with-python.html
        # http://stackoverflow.com/questions/31714221/how-to-send-an-email-with-quoted
        # http://stackoverflow.com/questions/9403265/how-do-i-use-python/9509718#9509718
        msg = EmailMessage()

        # Headers
        unixfrom = "From %s %s" % (
            self.sender.address, self.archived_date.strftime("%c"))
        assert isinstance(self.sender.address, str)
        header_from = self.sender.address
        if self.sender_name and self.sender_name != self.sender.address:
            header_from = "%s <%s>" % (self.sender_name, header_from)
        header_to = self.mailinglist.name
        msg.set_unixfrom(unixfrom)
        headers = (
            ("From", header_from),
            ("To", header_to),
            ("Subject", self.subject),
            )
        for header_name, header_value in headers:
            msg[header_name] = header_value
        tz = get_fixed_timezone(self.timezone)
        header_date = self.date.astimezone(tz).replace(microsecond=0)
        # Date format: http://tools.ietf.org/html/rfc5322#section-3.3
        msg["Date"] = header_date.strftime("%a, %d %b %Y %H:%M:%S %z")
        msg["Message-ID"] = "<%s>" % self.message_id
        if self.in_reply_to:
            msg["In-Reply-To"] = self.in_reply_to

        # Body
        content = self.ADDRESS_REPLACE_RE.sub(r"\1(a)\2", self.content)

        # Enforce `multipart/mixed` even when there are no attachments
        # Q: Why are all emails supposed to be multipart?
        if self.attachments.count() == 0:
            msg.set_content(content, subtype='plain')
            msg.make_mixed()

        # Attachments
        for attachment in self.attachments.order_by("counter"):
            mimetype = attachment.content_type.split('/', 1)
            msg.add_attachment(attachment.content, maintype=mimetype[0],
                               subtype=mimetype[1], filename=attachment.name)

        return msg

    @property
    def display_fixed(self):
        return "@@" in self.content

    def _set_message_id_hash(self):
        from hyperkitty.lib.utils import get_message_id_hash  # circular import
        if not self.message_id_hash:
            self.message_id_hash = get_message_id_hash(self.message_id)

    def on_post_init(self):
        self._set_message_id_hash()

    def on_post_created(self):
        self.thread.on_email_added(self)
        self.mailinglist.on_email_added(self)
        if not getattr(settings, "HYPERKITTY_BATCH_MODE", False):
            # For batch imports, let the cron job do the work
            from hyperkitty.tasks import check_orphans
            check_orphans.delay(self.id)

    def on_pre_save(self):
        self._set_message_id_hash()
        # Link to the thread
        if self.thread_id is None:
            # Create the thread if not found
            thread, _thread_created = Thread.objects.get_or_create(
                mailinglist=self.mailinglist,
                thread_id=self.message_id_hash)
            self.thread = thread
        # Make sure there is only one email with parent_id == None in a thread
        if self.parent_id is not None:
            return
        starters = Email.objects.filter(
                thread=self.thread, parent_id__isnull=True
            ).values_list("id", flat=True)
        if len(starters) > 0 and list(starters) != [self.id]:
            raise IntegrityError("There can be only one email with "
                                 "parent_id==None in the same thread")

    def on_post_save(self):
        pass

    def on_pre_delete(self):
        # Reset parent_id
        children = self.children.order_by("date")
        if not children:
            return
        if self.parent is None:
            #  Temporarily set the email's parent_id to not None, to allow the
            #  next email to be the starting email (there's a check on_save for
            #  duplicate thread starters)
            self.parent = self
            self.save(update_fields=["parent"])
            starter = children[0]
            starter.parent = None
            starter.save(update_fields=["parent"])
            children.all().update(parent=starter)
        else:
            children.update(parent=self.parent)

    def on_post_delete(self):
        try:
            thread = Thread.objects.get(id=self.thread_id)
        except Thread.DoesNotExist:
            pass
        else:
            thread.on_email_deleted(self)
        try:
            mlist = MailingList.objects.get(pk=self.mailinglist_id)
        except MailingList.DoesNotExist:
            pass
        else:
            mlist.on_email_deleted(self)

    def on_vote_added(self, vote):
        from hyperkitty.tasks import rebuild_email_cache_votes
        rebuild_email_cache_votes.delay(self.id)

    on_vote_deleted = on_vote_added


class Attachment(models.Model):
    email = models.ForeignKey(
        "Email", related_name="attachments", on_delete=models.CASCADE)
    counter = models.SmallIntegerField()
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255)
    encoding = models.CharField(max_length=255, null=True)
    size = models.IntegerField(null=True)
    content = models.BinaryField(null=True)

    class Meta:
        unique_together = ("email", "counter")

    def on_pre_save(self):
        # set the size
        if not self.size and self.content is not None:
            self.size = len(self.content)

    def _get_folder(self):
        global_folder = getattr(
            settings, "HYPERKITTY_ATTACHMENT_FOLDER", None)
        if global_folder is None:
            return None
        mlist = self.email.mailinglist.name
        try:
            listname, domain = mlist.rsplit("@", 1)
        except ValueError:
            listname = "none"
            domain = mlist
        return os.path.join(
            global_folder, domain, listname,
            self.email.message_id_hash[0:2],
            self.email.message_id_hash[2:4],
            self.email.message_id_hash[4:6],
            str(self.email.id),
        )

    def get_content(self):
        folder = self._get_folder()
        if folder is None:
            return self.content
        filepath = os.path.join(folder, str(self.counter))
        if not os.path.exists(filepath):
            logger.error("Could not find local attachment %s for email %s",
                         self.counter, self.email.id)
            return ""
        with open(filepath, "rb") as f:
            content = f.read()
        return content

    def set_content(self, content):
        if isinstance(content, str):
            if self.encoding is not None:
                content = content.encode(self.encoding)
            else:
                content = content.encode('utf-8')
        self.size = len(content)
        folder = self._get_folder()
        if folder is None:
            self.content = content
            return
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(os.path.join(folder, str(self.counter)), "wb") as f:
            f.write(content)
        self.content = None
