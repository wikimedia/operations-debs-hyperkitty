# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301,
# USA.
#
# Author: Aurelien Bompard <abompard@fedoraproject.org>


import email.utils
import errno
import logging
import os
import os.path
import re
from base64 import b32encode
from contextlib import contextmanager
from datetime import timedelta
from email.parser import BytesHeaderParser, HeaderParser
from email.policy import default
from hashlib import sha1
from tempfile import gettempdir

import dateutil.parser
import dateutil.tz
from django.conf import settings
from django.db import connection
from django.utils import timezone
from lockfile import AlreadyLocked, LockFailed
from lockfile.pidlockfile import PIDLockFile


log = logging.getLogger(__name__)


def get_message_id_hash(msg_id):
    """
    Returns the X-Message-ID-Hash header for the provided Message-ID header.

    See <http://wiki.list.org/display/DEV/Stable+URLs#StableURLs-Headers> for
    details. Example:
    """
    msg_id = email.utils.unquote(msg_id).encode('utf-8')
    return b32encode(sha1(msg_id).digest()).decode('utf-8')


def get_message_id(message):
    msg_id = email.utils.unquote(message['Message-Id'])
    # Protect against extremely long Message-Ids (there is no limit in the
    # email spec), it's set to VARCHAR(255) in the database
    if len(msg_id) >= 255:
        msg_id = msg_id[:254]
    return msg_id


IN_BRACKETS_RE = re.compile("[^<]*<([^>]+)>.*")


def get_ref(message):
    """
    Returns the message-id of the reference email for a given message.
    """
    if ("References" not in message and
            "In-Reply-To" not in message):
        return None
    ref_id = message.get("In-Reply-To")

    # EmailMessage will always return instances of str
    assert ref_id is None or isinstance(ref_id, str)

    if ref_id is None or not ref_id.strip():
        ref_id = message.get("References")
        if ref_id is not None and ref_id.strip():
            # There can be multiple references, use the last one
            ref_id = ref_id.split()[-1].strip()
    if ref_id is not None:
        if "<" in ref_id or ">" in ref_id:
            ref_id = IN_BRACKETS_RE.match(ref_id)
            if ref_id:
                ref_id = ref_id.group(1)
    if ref_id is not None:
        ref_id = ref_id[:254]
    return ref_id


def parseaddr(address):
    """
    Wrapper around email.utils.parseaddr to also handle Mailman's generated
    mbox archives.
    """
    if address is None:
        return "", ""
    address = address.replace(" at ", "@")
    from_name, from_email = email.utils.parseaddr(address)
    if not from_name:
        from_name = from_email
    return from_name, from_email


def parsedate(datestring):
    if datestring is None:
        return None
    try:
        parsed = dateutil.parser.parse(datestring)
    except ValueError:
        return None
    try:
        offset = parsed.utcoffset()
    except ValueError:
        # Wrong offset, reset to UTC
        offset = None
        parsed = parsed.replace(tzinfo=timezone.utc)
    if offset is not None and \
            abs(offset) > timedelta(hours=13):
        parsed = parsed.astimezone(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)  # make it aware
    return parsed


def header_to_unicode(header):
    if header is None:
        header = str(header)
    if isinstance(header, str):
        msg = HeaderParser(policy=default).parsestr('dummy: ' + header)
    elif isinstance(header, bytes):
        msg = BytesHeaderParser(policy=default).parsebytes(b'dummy: ' + header)
    else:
        raise ValueError('header must be str or bytes, but is ' + type(header))

    return msg['dummy']


def stripped_subject(mlist, subject):
    if mlist is None:
        return subject
    if not subject:
        return "(no subject)"
    if not mlist.subject_prefix:
        return subject
    if subject.lower().startswith(mlist.subject_prefix.lower()):
        subject = subject[len(mlist.subject_prefix):]
    return subject


# File-based locking

def run_with_lock(fn, *args, **kwargs):
    lock = PIDLockFile(getattr(
        settings, "HYPERKITTY_JOBS_UPDATE_INDEX_LOCKFILE",
        os.path.join(gettempdir(), "hyperkitty-jobs-update-index.lock")))
    try:
        lock.acquire(timeout=-1)
    except AlreadyLocked:
        if check_pid(lock.read_pid()):
            log.warning("The job 'update_index' is already running")
            return
        else:
            lock.break_lock()
            lock.acquire(timeout=-1)
    except LockFailed as e:
        log.warning("Could not obtain a lock for the 'update_index' "
                    "job (%s)", e)
        return
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log.exception("Failed to update the fulltext index: %s", e)
    finally:
        lock.release()


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        if e.errno == errno.ESRCH:
            # if errno !=3, we may just not be allowed to send the signal
            return False
    return True


@contextmanager
def pgsql_disable_indexscan():
    # Sometimes PostgreSQL chooses a very inefficient query plan:
    # https://pagure.io/fedora-infrastructure/issue/6164
    if connection.vendor != "postgresql":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("SET enable_indexscan = OFF")
        try:
            yield
        finally:
            cursor.execute("SET enable_indexscan = ON")


# import time
# from collections import defaultdict
# LASTTIME = None
# TIMES = defaultdict(list)
#
# def timeit(name):
#     global LASTTIME
#     now = time.time()
#     if LASTTIME is not None:
#         spent = now - LASTTIME
#         TIMES[name].append(spent)
#         print("{}: {}".format(name, spent))
#     LASTTIME = now
