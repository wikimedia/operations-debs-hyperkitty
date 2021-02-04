# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2021 by the Free Software Foundation, Inc.
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

import logging

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key

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

#
# Tasks
#


def update_search_index():
    """Update the full-text index"""
    AsyncTask(run_with_lock, update_index, remove=False,
              q_options={'task_name': 'update_search_index'}).run()


# def update_and_clean_search_index():
#     """Update the full-text index and clean old entries"""
#     run_with_lock(update_index, remove=True)

def rebuild_mailinglist_cache_recent(mlist_name):
    AsyncTask(
        _rebuild_mailinglist_cache_recent, mlist_name,
        q_options={'task_name': 'rebuild_mailinglist_cache_recent'}).run()


def _rebuild_mailinglist_cache_recent(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    for cached_value in mlist.recent_cached_values:
        cached_value.rebuild()


def rebuild_mailinglist_cache_for_month(mlist_name, year, month):
    AsyncTask(
        _rebuild_mailinglist_cache_for_month, mlist_name, year, month,
        q_options={'task_name': 'rebuild_mailinglist_cache_for_month'}).run()


def _rebuild_mailinglist_cache_for_month(mlist_name, year, month):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.cached_values["participants_count_for_month"].rebuild(year, month)


def rebuild_thread_cache_new_email(thread_id):
    AsyncTask(_rebuild_thread_cache_new_email, thread_id,
              q_options={'task_name': 'rebuild_thread_cache_new_email'}).run()


def _rebuild_thread_cache_new_email(thread_id):
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


def rebuild_cache_popular_threads(mlist_name):
    AsyncTask(_rebuild_cache_popular_threads, mlist_name,
              q_options={'task_name': 'rebuild_cache_popular_threads'}).run()


def _rebuild_cache_popular_threads(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.cached_values["popular_threads"].rebuild()


def compute_thread_positions(thread_id):
    AsyncTask(_compute_thread_positions, thread_id,
              q_options={'task_name': 'compute_thread_positions'}).run()


def _compute_thread_positions(thread_id):
    try:
        thread = Thread.objects.get(id=thread_id)
    except Thread.DoesNotExist:
        # Maybe the thread was deleted? Not much we can do here.
        log.warning(
            "Cannot rebuild the thread cache: thread %s does not exist.",
            thread_id)
        return
    compute_thread_order_and_depth(thread)


def update_from_mailman(mlist_name):
    AsyncTask(_update_from_mailman, mlist_name,
              q_options={'task_name': 'update_from_mailman'}).run()


def _update_from_mailman(mlist_name):
    mlist = MailingList.objects.get(name=mlist_name)
    mlist.update_from_mailman()


def sender_mailman_id(sender_id):
    AsyncTask(_sender_mailman_id, sender_id,
              q_options={'task_name': 'sender_mailman_id'}).run()


def _sender_mailman_id(sender_id):
    sender = Sender.objects.get(pk=sender_id)
    try:
        sender.set_mailman_id()
    except MailmanConnectionError:
        pass


def check_orphans(email_id):
    AsyncTask(_check_orphans, email_id,
              q_options={'task_name': 'check_orphans'}).run()


def _check_orphans(email_id):
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


def rebuild_thread_cache_votes(thread_id):
    AsyncTask(_rebuild_thread_cache_votes, thread_id,
              q_options={'task_name': 'rebuild_thread_cache_votes'}).run()


def _rebuild_thread_cache_votes(thread_id):
    try:
        thread = Thread.objects.get(id=thread_id)
    except Thread.DoesNotExist:
        log.warning('Thread with id {thread_id} does not exist'.format(
            thread_id=thread_id))
        return

    for cached_key in ["votes", "votes_total"]:
        thread.cached_values[cached_key].rebuild()


def rebuild_email_cache_votes(email_id):
    AsyncTask(_rebuild_email_cache_votes, email_id,
              q_options={'task_name': 'rebuild_email_cache_votes'}).run()


def _rebuild_email_cache_votes(email_id):
    email = Email.objects.get(id=email_id)
    email.cached_values["votes"].rebuild()
