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
Definition of async tasks using Django-Q.

Author: Aurelien Bompard <abompard@fedoraproject.org>
"""

import importlib
import logging
from binascii import crc32
from functools import wraps

from django.conf import settings
from django.core.cache.utils import make_template_fragment_key
from django.core.cache import cache
from django_q.conf import Conf
from django_q.tasks import AsyncTask
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
    """This method is a wrapper that will actually be called by the workers.

    *args and **kwargs are attributes that will be passed to func function,
    when the task is actually run.

    :param str cache_key: Unique identifier for the function call and its args
    :param str func: __name__ of the callable function to run as a task.

    """
    # Drop the lock before run instead of after because the DB data may
    # have changed during the task's runtime.
    cache.delete(cache_key)
    if not callable(func):
        module, func_name = func.rsplit('.', 1)
        m = importlib.import_module(module)
        func = getattr(m, func_name)
    return func(*args, **kwargs)


def process_task_result(task):
    """Hook to process the result of async tasks.

    This checks if the task was executed successfully, if not, log the failure.

    :param django_q.task.Task task: The Task attribute to process result for.

    """
    if not task.success:
        log.info(
            'AsyncTask task "{0}" with args "{1}" and kwargs "{2}" finished with errors.'.format(  # noqa: E501
                task.func,
                task.args,
                task.kwargs)
        )
        log.debug(task.result)


class SingletonAsync(AsyncTask):
    """A singleton task implementation.

    A singleton task does not enqueue the function if there's already one in
    the queue.

    The cache is used for locking: the lock is acquired when the run() method
    is executed. If there's already an identical task in the queue, it will
    return this task's id.
    """

    #: This is the timeout after which the cache entry for a task will
    #: expire. The cache entry makes sure that same task aren't queued if
    #: there is one already in queue, unless they were scheduled LOCK_EXPIRE
    #: apart.
    LOCK_EXPIRE = getattr(settings, 'HYPERKITTY_TASK_LOCK_TIMEOUT', 60 * 10)
    # XXX(maxking): I am not sure what exactly does this achieve, since if the
    # task is still in the queue, it will process the results for the 2nd task
    # as well and 2nd one will basically be a repeated task, unless, there is a
    # new email to the list between the runs of the two tasks. So, on a
    # very-high volume mailing-list, this would mean that we are proactively
    # scheduling task runs.
    # However, this shouldn't cause any harm though and if there is someone
    # else looking at it in future, wondering what is the use of it, feel-free
    # to get-rid of it

    def __init__(self, func, *args, **kwargs):
        # We use the function's name along with hashed arguments to make sure
        # that we have only single function in queue with same arguments.
        # No space allowed in memcached keys. Use CRC32 on the arguments
        # to have a fast and sufficiently unique way to identify tasks.
        func_name = func.__name__ if callable(func) else func
        self._cache_key = "task:status:%s:%s".format(
            func_name,
            crc32((repr(args) + repr(kwargs)).encode('utf-8')) & 0xffffffff
        )
        # Call the Original AsyncTask class with required parameters.
        super().__init__(
            # This is the wrapper function that executes the actual function.
            # This function makes sure we drop the cache key before we call the
            # actual function.
            unlock_and_call,
            # Actual function to be run.
            func,
            # Identifier for the function with args, kwargs hashed.
            self._cache_key,
            # arguments to the function func
            *args,
            # Process the results of the async task.
            hook=process_task_result,
            # kwargs for func, written down here because **kwargs can come only
            # after all keyword arguments, in this case, hook
            **kwargs
        )

    def run(self):
        """
        Dispatch the task to one of the workers for execution.

        ..note:: Behavior of run is slightly different that the original
                AsyncTask.run() function that this method overrides. If there
                is a task that resembles to this task (i.e. same function call
                with same arguments) in the queue, we just don't run the task
                at all.  To find out if a task is there in a queue, we use
                Django's cache framework to store a unique key, which is a hash
                of function name all it's arguments.
        """
        # This overrides the AsyncTask.run() method.
        # First, check if there is a function with same args in queue already.
        pending_id = cache.get(self._cache_key, default=None)
        if pending_id is not None:
            # This means that there is a task in the queue already, so we call
            # ourselves "started" (yeah, air-quotes), and return the id of
            # original function.
            self.started = True
            # Log that we are not going to actually queue this function call.
            log.debug(
                'Skipping task "{0}" with args "{1}" and kwargs "{2}"'.format(
                    self.func,
                    self.args,
                    self.kwargs
                )
            )
            return pending_id
        # There is no task in the queue that matches the function, or the
        # previous version of this task was executed more than self.LOCK_EXPIRE
        # seconds ago.
        self.id = super().run()
        # Set the cache key to make sure that task is scheduled and added to
        # the queue. This expired in self.LOCK_EXPIRE seconds, so there can
        # effectively be multiple instances of same task.
        cache.set(self._cache_key, self.id, self.LOCK_EXPIRE)
        return self.id

    @classmethod
    def task(cls, func):
        """A decorator function that converts a function into an async task.

        Adds a ``delay()`` method to the decorated function which will run it
        asynchronously with the provided arguments.  The arguments accepted by
        the :py:class:`AsyncTask` class are accepted here too.
        """
        def delay(*args, **kwargs):
            if kwargs.get("sync", False) or Conf.SYNC:
                # Singleton locking does not work on sync calls because the
                # lock is placed after the run() call (to have the task id).
                return func(*args, **kwargs)
            # Use a more intuitive task name
            async_class = cls
            # In certain cases, we don't want to use singleton locking, when:
            # 1. we want to run synchronously
            # 2. global django-q settings is set to run as synchronous task
            # 3. the user especially wants to disable singleton locking
            if getattr(settings, "HYPERKITTY_DISABLE_SINGLETON_TASKS", False):
                # Singleton locking does not work on sync calls because the
                # lock is placed after the run() call (to have the task id).
                async_class = AsyncTask
            # Use a more intuitive task name, if one isn't already set.
            if "task_name" not in kwargs:
                kwargs["task_name"] = func.__name__ if callable(func) else func
            # Create the task.
            task = async_class(func, *args, **kwargs)
            return task.run()
        # Add a delay method to the function we are going is going to wrap.
        func.delay = delay
        return func


#
# Decorator to make functions asynchronous.
#

def async_task(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        task = AsyncTask(f, *args, **kwargs)
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
    try:
        thread = Thread.objects.get(id=thread_id)
    except Thread.DoesNotExist:
        # Maybe the thread was deleted? Not much we can do here.
        log.warning(
            "Cannot rebuild the thread cache: thread %s does not exist.",
            thread_id)
        return
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
    try:
        email = Email.objects.get(id=email_id)
    except Email.DoesNotExist:
        # Maybe the email was deleted? Not much we can do here.
        log.warning(
            "Cannot check for orphans: email %s does not exist.", email_id)
        return
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
