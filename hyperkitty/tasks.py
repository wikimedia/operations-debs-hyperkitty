# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2017 by the Free Software Foundation, Inc.
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

"""
Definition of async tasks using Celery.

Author: Aurelien Bompard <abompard@fedoraproject.org>
"""

from __future__ import absolute_import, unicode_literals

import importlib
import logging
from binascii import crc32
from functools import wraps

from django.core.cache.utils import make_template_fragment_key
from django_mailman3.lib.cache import cache
from django_q.conf import Conf
from django_q.tasks import Async
from mailmanclient import MailmanConnectionError

from hyperkitty.lib.analysis import compute_thread_order_and_depth
from hyperkitty.lib.utils import run_with_lock
from hyperkitty.models.email import Email
from hyperkitty.models.mailinglist import MailingList
from hyperkitty.models.sender import Sender
from hyperkitty.models.thread import Thread
from hyperkitty.search_indexes import update_index

log = logging.getLogger(__name__)


def unlock_and_call(func, cache_key, *args, **kwargs):
    """
    This method is a wrapper that will actually be called by the workers.
    """
    # Drop the lock before run instead of after because the DB data may
    # have changed during the task's runtime.
    cache.delete(cache_key)
    if not callable(func):
        module, func_name = func.rsplit('.', 1)
        m = importlib.import_module(module)
        func = getattr(m, func_name)
    return func(*args, **kwargs)


class SingletonAsync(Async):
    """A singleton task implementation.

    A singleton task does not enqueue the function if there's already one in
    the queue.

    The cache is used for locking: the lock is acquired when the run() method
    is executed. If there's already an identical task in the queue, it will
    return this task's id.
    """

    LOCK_EXPIRE = 60 * 10  # Lock expires in 10 minutes

    def __init__(self, func, *args, **kwargs):
        func_name = func.__name__ if callable(func) else func
        # No space allowed in memcached keys. Use CRC32 on the arguments
        # to have a fast and sufficiently unique way to identify tasks.
        self._cache_key = "task:status:%s:%s" % (
            func_name, crc32(repr(args) + repr(kwargs)) & 0xffffffff)
        super(SingletonAsync, self).__init__(
            unlock_and_call, func, self._cache_key, *args, **kwargs)

    # def _report_start(self, func):
    #     @wraps(func)
    #     def wrapper(*args, **kwargs):
    #         # Drop the lock before run instead of after because the DB data
    #         # may have changed during the task's runtime.
    #         cache.delete(self._lock_cache_key)
    #         return func(*args, **kwargs)
    #     return wrapper

    def run(self):
        pending_id = cache.get(self._cache_key)
        if pending_id is not None:
            self.id = pending_id
            self.started = True
            return pending_id
        # cache.set(self._lock_cache_key, "enqueuing...", self.LOCK_EXPIRE)
        super(SingletonAsync, self).run()
        cache.set(self._cache_key, self.id, self.LOCK_EXPIRE)
        return self.id

    @classmethod
    def task(cls, func):
        """Turn a function into an async task.

        Adds a ``delay()`` method to the decorated function which will run it
        asynchronously with the provided arguments.  The arguments accepted by
        the :py:class:`Async` class are accepted here too.
        """
        def delay(*args, **kwargs):
            async_class = cls
            if kwargs.get("sync", False) or Conf.SYNC:
                # Singleton locking does not work on sync calls because the
                # lock is placed after the run() call (to have the task id).
                async_class = Async
            # Use a more intuitive task name
            if "task_name" not in kwargs:
                kwargs["task_name"] = func.__name__ if callable(func) else func
            task = async_class(func, *args, **kwargs)
            return task.run()
        func.delay = delay
        return func
        # @wraps(func)
        # def wrapper(*args, **kwargs):
        #     task = cls(func, *args, **kwargs)
        #     return task.run()
        # return wrapper


#
# Decorator to make functions asynchronous.
#

def async_task(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        task = Async(f, *args, **kwargs)
        return task.run()
    return wrapper


#
# Tasks
#

@SingletonAsync.task
def update_search_index():
    """Update the full-text index"""
    run_with_lock(update_index, remove=False)

# @SingletonAsync.task
# def update_and_clean_search_index():
#     """Update the full-text index and clean old entries"""
#     run_with_lock(update_index, remove=True)


@SingletonAsync.task
def rebuild_mailinglist_cache_recent(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    for cached_value in mlist.recent_cached_values:
        cached_value.rebuild()


@SingletonAsync.task
def rebuild_mailinglist_cache_for_month(mlist_name, year, month):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.cached_values["participants_count_for_month"].rebuild(year, month)


@SingletonAsync.task
def rebuild_thread_cache_new_email(thread_id):
    try:
        thread = Thread.objects.get(id=thread_id)
    except Thread.DoesNotExist:
        log.warning(
            "Cannot rebuild the thread cache: thread %s does not exist.",
            thread_id)
        return
    for cached_key in ["participants_count", "emails_count"]:
        thread.cached_values[cached_key].rebuild()
    # Don't forget the cached template fragment.
    cache.delete(make_template_fragment_key(
        "thread_participants", [thread.id]))


@SingletonAsync.task
def rebuild_cache_popular_threads(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.cached_values["popular_threads"].rebuild()


@SingletonAsync.task
def compute_thread_positions(thread_id):
    thread = Thread.objects.get(id=thread_id)
    compute_thread_order_and_depth(thread)


@SingletonAsync.task
def update_from_mailman(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.update_from_mailman()


@SingletonAsync.task
def sender_mailman_id(sender_id):
    sender = Sender.objects.get(pk=sender_id)
    try:
        sender.set_mailman_id()
    except MailmanConnectionError:
        pass


@SingletonAsync.task
def check_orphans(email_id):
    """
    When a reply is received before its original message, it must be
    re-attached when the original message arrives.
    """
    email = Email.objects.get(id=email_id)
    orphans = Email.objects.filter(
            mailinglist=email.mailinglist,
            in_reply_to=email.message_id,
            parent_id__isnull=True,
        ).exclude(
            # guard against emails with the in-reply-to header pointing to
            # themselves
            id=email.id
        )
    for orphan in orphans:
        orphan.set_parent(email)


@SingletonAsync.task
def rebuild_thread_cache_votes(thread_id):
    thread = Thread.objects.get(id=thread_id)
    for cached_key in ["votes", "votes_total"]:
        thread.cached_values[cached_key].rebuild()


@SingletonAsync.task
def rebuild_email_cache_votes(email_id):
    email = Email.objects.get(id=email_id)
    email.cached_values["votes"].rebuild()
