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

from collections import namedtuple
from django.conf import settings
from django.db import models
from django.utils.timezone import now, utc

from hyperkitty.lib.analysis import compute_thread_order_and_depth
from .common import ModelCachedValue, VotesCachedValue


import logging
logger = logging.getLogger(__name__)


class Thread(models.Model):
    """
    A thread of archived email, from a mailing-list. It is identified by both
    the list name and the thread id.
    """
    mailinglist = models.ForeignKey(
        # Delete the model if the MailingList is deleted.
        "MailingList", related_name="threads", on_delete=models.CASCADE)
    thread_id = models.CharField(max_length=255, db_index=True)
    date_active = models.DateTimeField(db_index=True, default=now)
    category = models.ForeignKey(
        "ThreadCategory", related_name="threads", null=True,
        on_delete=models.SET_NULL)
    starting_email = models.OneToOneField(
        "Email", related_name="started_thread", null=True,
        on_delete=models.SET_NULL)

    def __init__(self, *args, **kwargs):
        super(Thread, self).__init__(*args, **kwargs)
        self.cached_values = {
            "participants_count": ParticipantsCount(self),
            "emails_count": EmailsCount(self),
            "subject": Subject(self),
            "votes": VotesCachedValue(self),
            "votes_total": VotesTotal(self),
        }

    class Meta:
        unique_together = ("mailinglist", "thread_id")

    @property
    def participants(self):
        """Set of email senders in this thread"""
        from .email import Email
        Participant = namedtuple("Participant", ["name", "address"])
        return [
            Participant(name=e["sender_name"], address=e["sender__address"])
            for e in Email.objects.filter(thread_id=self.id).values(
                "sender__address", "sender_name").distinct()
            ]

    @property
    def participants_count(self):
        return self.cached_values["participants_count"]()

    def replies_after(self, date):
        return self.emails.filter(date__gt=date)

    # def _get_category(self):
    #     if not self.category_id:
    #         return None
    #     return self.category_obj.name
    # def _set_category(self, name):
    #     if not name:
    #         self.category_id = None
    #         return
    #     session = object_session(self)
    #     try:
    #         category = session.query(Category).filter_by(name=name).one()
    #     except NoResultFound:
    #         category = Category(name=name)
    #         session.add(category)
    #     self.category_id = category.id
    # category = property(_get_category, _set_category)

    @property
    def emails_count(self):
        return self.cached_values["emails_count"]()

    @property
    def subject(self):
        return self.cached_values["subject"]()

    def get_votes(self):
        return self.cached_values["votes"]()

    @property
    def votes_total(self):
        return self.cached_values["votes_total"]()

    @property
    def prev_thread(self):  # TODO: Make it a relationship
        return Thread.objects.filter(
                mailinglist=self.mailinglist,
                date_active__lt=self.date_active
            ).order_by("-date_active").first()

    @property
    def next_thread(self):  # TODO: Make it a relationship
        return Thread.objects.filter(
                mailinglist=self.mailinglist,
                date_active__gt=self.date_active
            ).order_by("date_active").first()

    def is_unread_by(self, user):
        if not user.is_authenticated:
            return False
        try:
            last_view = LastView.objects.get(thread=self, user=user)
        except LastView.DoesNotExist:
            return True
        except LastView.MultipleObjectsReturned:
            last_view_duplicate, last_view = LastView.objects.filter(
                thread=self, user=user).order_by("view_date").all()
            last_view_duplicate.delete()
        return self.date_active.replace(tzinfo=utc) > last_view.view_date

    def find_starting_email(self):
        # Find and set the staring email if it was not specified
        from .email import Email  # circular import
        if self.starting_email is not None:
            return
        try:
            self.starting_email = self.emails.get(parent_id__isnull=True)
        except Email.DoesNotExist:
            self.starting_email = self.emails.order_by("date").first()

    def on_pre_save(self):
        self.find_starting_email()

    def on_post_created(self):
        self.mailinglist.on_thread_added(self)

    def on_post_save(self):
        pass

    def on_post_delete(self):
        self.mailinglist.on_thread_deleted(self)

    def on_email_added(self, email):
        self.find_starting_email()
        self.date_active = email.date
        if self.starting_email is None:
            self.starting_email = email
        self.save()
        if not getattr(settings, "HYPERKITTY_BATCH_MODE", False):
            # Cache handling and thread positions will be handled at the end of
            # the import process.
            from hyperkitty.tasks import (
                rebuild_thread_cache_new_email,
                compute_thread_positions,
                )
            rebuild_thread_cache_new_email.delay(self.id)
            compute_thread_positions.delay(self.id)

    def on_email_deleted(self, email):
        from hyperkitty.tasks import rebuild_thread_cache_new_email
        # update or cleanup thread
        if self.emails.count() == 0:
            self.delete()
        else:
            if self.starting_email is None:
                self.find_starting_email()
                self.save(update_fields=["starting_email"])
            compute_thread_order_and_depth(self)
            self.date_active = self.emails.order_by("-date").first().date
            rebuild_thread_cache_new_email.delay(self.id)

    def on_vote_added(self, vote):
        from hyperkitty.tasks import rebuild_thread_cache_votes
        rebuild_thread_cache_votes.delay(self.id)

    on_vote_deleted = on_vote_added


class ParticipantsCount(ModelCachedValue):

    cache_key = "participants_count"

    def get_value(self):
        return len(self.instance.participants)


class EmailsCount(ModelCachedValue):

    cache_key = "emails_count"

    def get_value(self):
        return self.instance.emails.count()


class Subject(ModelCachedValue):

    cache_key = "subject"

    def get_value(self):
        return self.instance.starting_email.subject


class VotesTotal(ModelCachedValue):

    cache_key = "votes_total"

    def get_value(self):
        votes = self.instance.get_votes()
        return votes["likes"] - votes["dislikes"]


class LastView(models.Model):
    thread = models.ForeignKey(
        "Thread", related_name="lastviews", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="lastviews", on_delete=models.CASCADE)
    view_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Unicode representation"""
        return "Last view of %s by %s was %s" % (
            str(self.thread), str(self.user),
            self.view_date.isoformat())

    def num_unread(self):
        if self.thread.date_active.replace(tzinfo=utc) <= self.view_date:
            return 0  # avoid the expensive query below
        else:
            return self.thread.emails.filter(date__gt=self.view_date).count()
