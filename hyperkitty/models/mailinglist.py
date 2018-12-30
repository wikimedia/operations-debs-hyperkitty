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

import datetime
from enum import Enum
from urllib.error import HTTPError

import dateutil.parser
from django.conf import settings
from django.db import models
from django.utils.timezone import now, utc
from django.core.cache import cache
from django_mailman3.lib.mailman import get_mailman_client
from mailmanclient import MailmanConnectionError

from hyperkitty.lib.utils import pgsql_disable_indexscan
from .common import ModelCachedValue
from .thread import Thread

import logging
logger = logging.getLogger(__name__)


class ArchivePolicy(Enum):
    """
    Copy from mailman.interfaces.archiver.ArchivePolicy since we can't import
    mailman (PY3-only).

    This should probably be moved to mailman.client.
    """
    never = 0
    private = 1
    public = 2


class MailingList(models.Model):
    """
    An archived mailing-list.
    """
    name = models.CharField(max_length=254, unique=True)
    list_id = models.CharField(max_length=254, null=True, unique=True)
    display_name = models.CharField(max_length=255)
    description = models.TextField()
    subject_prefix = models.CharField(max_length=255)
    archive_policy = models.IntegerField(
        choices=[(p.value, p.name) for p in ArchivePolicy],
        default=ArchivePolicy.public.value)
    created_at = models.DateTimeField(default=now)

    MAILMAN_ATTRIBUTES = (
        "display_name", "description", "subject_prefix",
        "archive_policy", "created_at", "list_id",
    )

    def __init__(self, *args, **kwargs):
        super(MailingList, self).__init__(*args, **kwargs)
        self.cached_values = {
            "recent_threads": RecentThreads(self),
            "participants_count_for_month": ParticipantsCountForMonth(self),
            "recent_participants_count": RecentParticipantsCount(self),
            "top_posters": TopPosters(self),
            "top_threads": TopThreads(self),
            "popular_threads": PopularThreads(self),
            "first_date": FirstDate(self),
        }
        self.recent_cached_values = [
            self.cached_values[key] for key in [
                "recent_threads",
                "recent_participants_count",
                "top_threads", "top_posters", "popular_threads",
                ]
            ]

    @property
    def is_private(self):
        return self.archive_policy == ArchivePolicy.private.value

    @property
    def is_new(self):
        return self.created_at and \
                now() - self.created_at <= datetime.timedelta(days=30)

    def get_recent_dates(self):
        today = now()
        # today -= datetime.timedelta(days=400) #debug
        # the upper boundary is excluded in the search, add one day
        end_date = today + datetime.timedelta(days=1)
        begin_date = end_date - datetime.timedelta(days=32)
        return begin_date, end_date

    def get_participants_count_between(self, begin_date, end_date):
        # We filter on emails dates instead of threads dates because that would
        # also include last month's participants when threads carry from one
        # month to the next
        # TODO: caching?
        return self.emails.filter(
                date__gte=begin_date, date__lt=end_date
            ).values("sender_id").distinct().count()

    def get_threads_between(self, begin_date, end_date):
        return self.threads.filter(
                starting_email__date__lt=end_date,
                date_active__gte=begin_date
            ).order_by("-date_active")

    @property
    def recent_participants_count(self):
        return self.cached_values["recent_participants_count"]()

    @property
    def recent_threads(self):
        return self.cached_values["recent_threads"]()

    @property
    def recent_threads_count(self):
        # Don't use a CachedValue for this one, because it does not need a
        # specific warm up or rebuild: this is done by the recent_threads
        # CachedValue.
        begin_date, end_date = self.get_recent_dates()
        cache_key = "MailingList:%s:recent_threads_count" % self.pk
        result = cache.get(cache_key)
        if result is None:
            result = self.get_threads_between(begin_date, end_date).count()
            # The cache will be refreshed daily by a periodic job.
            cache.set(cache_key, result, None)
        return result

    def get_participants_count_for_month(self, year, month):
        return self.cached_values["participants_count_for_month"](year, month)

    @property
    def top_posters(self):
        return self.cached_values["top_posters"]()

    @property
    def top_threads(self):
        """Threads with the most answers."""
        return self.cached_values["top_threads"]()

    @property
    def popular_threads(self):
        """Threads with the most votes."""
        return self.cached_values["popular_threads"]()

    def update_from_mailman(self):
        try:
            client = get_mailman_client()
            mm_list = client.get_list(self.name)
        except MailmanConnectionError:
            return
        except HTTPError:
            return  # can't update at this time
        if not mm_list:
            return

        def convert_date(value):
            value = dateutil.parser.parse(value)
            if value.tzinfo is None:
                value = value.replace(tzinfo=utc)
            return value
        converters = {
            "created_at": convert_date,
            "archive_policy": lambda p: ArchivePolicy[p].value,
        }
        for propname in self.MAILMAN_ATTRIBUTES:
            try:
                value = getattr(mm_list, propname)
            except AttributeError:
                value = mm_list.settings[propname]
            if propname in converters:
                value = converters[propname](value)
            setattr(self, propname, value)
        self.save()

    # Events (signal callbacks)

    def on_pre_save(self):
        # Set the default list_id
        if self.list_id is None:
            self.list_id = self.name.replace("@", ".")

    def on_thread_added(self, thread):
        pass

    def on_thread_deleted(self, thread):
        from hyperkitty.tasks import (
            rebuild_mailinglist_cache_recent,
            rebuild_mailinglist_cache_for_month,
            )
        begin_date, end_date = self.get_recent_dates()
        if thread.date_active >= begin_date and thread.date_active < end_date:
            # It's a recent thread
            rebuild_mailinglist_cache_recent.delay(self.name)
        rebuild_mailinglist_cache_for_month.delay(
            self.name, thread.date_active.year, thread.date_active.month)

    def on_email_added(self, email):
        if getattr(settings, "HYPERKITTY_BATCH_MODE", False):
            # Cache handling will be done at the end of the import
            # process.
            return
        # Rebuild the cached values.
        from hyperkitty.tasks import (
            rebuild_mailinglist_cache_recent,
            rebuild_mailinglist_cache_for_month,
            )
        rebuild_mailinglist_cache_recent.delay(self.name)
        rebuild_mailinglist_cache_for_month.delay(
            self.name, email.date.year, email.date.month)

    def on_email_deleted(self, email):
        # Don't use on_email_added, it will try appending to the
        # recent_threads and emails aren't associated to a thread
        # when they are deleted.
        # It's not semantically identical to on_thread_deleted() but it's the
        # same code, so DRY.
        try:
            email.thread
        except Thread.DoesNotExist:
            pass  # Already deleted
        else:
            self.on_thread_deleted(email.thread)

    def on_vote_added(self, vote):
        from hyperkitty.tasks import rebuild_cache_popular_threads
        rebuild_cache_popular_threads.delay(self.name)

    on_vote_deleted = on_vote_added


class RecentThreads(ModelCachedValue):

    cache_key = "recent_threads"

    def get_value(self):
        # Only cache the list of thread ids, or it may go over memcached's size
        # limit (1MB)
        begin_date, end_date = self.instance.get_recent_dates()
        thread_ids = self.instance.get_threads_between(
            begin_date, end_date).values_list("id", flat=True)
        return thread_ids

    def rebuild(self):
        value = super(RecentThreads, self).rebuild()
        cache.set("%s_count" % self._get_cache_key(), len(value), None)
        return value

    def get_or_set(self):
        thread_ids = super(RecentThreads, self).get_or_set()
        return [Thread.objects.get(pk=pk) for pk in thread_ids]

    def add_thread(self, thread):
        # Add the thread to the recent_threads.
        # Just append to the cache, a daily cron job will rebuild
        # the cache entirely to remove older threads.
        recent_thread_ids = self.get_value()
        if recent_thread_ids is None:
            recent_thread_ids = []
        if thread.id in recent_thread_ids:
            # If the thread is already recent, make it the most recent.
            recent_thread_ids.remove(thread.id)
        recent_thread_ids.insert(0, thread.id)
        cache.set(self._get_cache_key(), recent_thread_ids, None)
        cache.set("%s_count" % self._get_cache_key(),
                  len(recent_thread_ids), None)


class ParticipantsCountForMonth(ModelCachedValue):

    def _get_cache_key(self, year, month):
        return "MailingList:%s:p_count_for:%s:%s" % (
            self.instance.pk, year, month)

    def get_value(self, year, month):
        begin_date = datetime.datetime(year, month, 1, tzinfo=utc)
        end_date = begin_date + datetime.timedelta(days=32)
        end_date = end_date.replace(day=1)
        return self.instance.get_participants_count_between(
            begin_date, end_date)


class RecentParticipantsCount(ModelCachedValue):

    cache_key = "recent_participants_count"

    def get_value(self):
        begin_date, end_date = self.instance.get_recent_dates()
        return self.instance.get_participants_count_between(
            begin_date, end_date)


class TopPosters(ModelCachedValue):

    cache_key = "top_posters"

    def get_value(self):
        from .email import Email  # avoid circular imports
        begin_date, end_date = self.instance.get_recent_dates()
        query = Email.objects.filter(
                mailinglist=self.instance,
                date__gte=begin_date,
                date__lt=end_date,
            ).only("sender", "sender_name").select_related("sender")
        posters = {}
        for email in query:
            key = (email.sender.address, email.sender_name)
            if key not in posters:
                posters[key] = 1
            else:
                posters[key] += 1
        # It's not necessary to return instances since it's only used in
        # templates where access to instance attributes or dictionnary keys is
        # identical.
        posters = [
            {"address": p[0], "name": p[1], "count": c}
            for p, c in posters.items()
            ]
        sorted_posters = sorted(
            posters, key=lambda p: p["count"], reverse=True)
        return sorted_posters[:5]


class TopThreads(ModelCachedValue):
    """Threads with the most answers."""

    cache_key = "top_threads"

    def get_value(self):
        # Filter on the recent_threads ids instead of re-using the date
        # filter, otherwise the Sum will be computed for every thread
        # regardless of their date.
        begin_date, end_date = self.instance.get_recent_dates()
        recent_thread_ids = self.instance.get_threads_between(
            begin_date, end_date).values("id")
        threads = Thread.objects.filter(
            id__in=recent_thread_ids).annotate(
            models.Count("emails")).order_by("-emails__count")[:20]
        # (not sure about using .values_list() here because of the annotation)
        # Only cache the list of thread ids, or it may go over memcached's size
        # limit (1MB)
        return [t.id for t in threads]

    def get_or_set(self):
        thread_ids = super(TopThreads, self).get_or_set()
        return [Thread.objects.get(pk=pk) for pk in thread_ids]


class PopularThreads(ModelCachedValue):
    """Threads with the most votes."""

    cache_key = "popular_threads"

    def get_value(self):
        # Filter on the recent_threads ids instead of re-using the date
        # filter, otherwise the Sum will be computed for every thread
        # regardless of their date.
        begin_date, end_date = self.instance.get_recent_dates()
        recent_thread_ids = self.instance.get_threads_between(
            begin_date, end_date).values("id")
        threads = Thread.objects.filter(
            id__in=recent_thread_ids).annotate(
            models.Sum("emails__votes__value")).order_by(
            "-emails__votes__value__sum")[:20]
        # (not sure about using .values_list() here because of the annotation)
        for thread in threads:
            value = thread.emails__votes__value__sum
            if value is None:
                value = 0
            cache.set("Thread:%s:votes_total" % thread.id, value, None)
        # Only cache the list of thread ids, or it may go over memcached's size
        # limit (1MB)
        return [t.id for t in threads if t.votes_total > 0]

    def get_or_set(self):
        thread_ids = super(PopularThreads, self).get_or_set()
        return [Thread.objects.get(pk=pk) for pk in thread_ids]


class FirstDate(ModelCachedValue):

    cache_key = "first_date"

    def get_value(self):
        with pgsql_disable_indexscan():
            value = self.instance.emails.order_by(
                "date").values_list("date", flat=True).first()
        if value is not None:
            return value.date()
        else:
            return None
