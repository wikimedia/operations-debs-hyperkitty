# -*- coding: utf-8 -*-
# Copyright (C) 2014-2018 by the Free Software Foundation, Inc.
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
# Modified by Mark Sapiro <mark@msapiro.net>
#

from django.core.management.base import CommandError
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from haystack import indexes
from haystack.query import SearchQuerySet
from haystack.management.commands.update_index import \
    Command as UpdateIndexCommand
from hyperkitty.models import Email, MailingList

# Create a global for the listname.
LISTNAME = None


class EmailIndex(indexes.SearchIndex, indexes.Indexable):

    text = indexes.CharField(document=True, use_template=True)
    mailinglist = indexes.CharField(model_attr='mailinglist__name')
    subject = indexes.CharField(model_attr='subject', boost=1.25,
                                use_template=True)
    date = indexes.DateTimeField(model_attr='date')
    sender = indexes.CharField(
        model_attr='sender_name', null=True, boost=1.125)
    tags = indexes.MultiValueField(
        model_attr='thread__tags__name', null=True, boost=1.25)
    archived_date = indexes.DateTimeField(model_attr='archived_date')

    def get_model(self):
        return Email

    def get_updated_field(self):
        return 'archived_date'

    def index_queryset(self, using=None):
        if LISTNAME is None:
            return self.get_model().objects.all()
        else:
            return self.get_model().objects.filter(
                mailinglist__name=LISTNAME)

    def load_all_queryset(self):
        # Pull other objects related to the Email in search results.
        return self.get_model().objects.all().select_related(
            "sender", "thread")


def update_index(remove=False, listname=None, verbosity=0):
    """
    Update the search index with the new emails since the last index update
    or if listname is provided, with all emails from that list.

    Setting remove to True is extremely slow, it needs to scan the entire
    index and database. It takes about 15 minutes on Fedora's lists, so it is
    not fit for a frequent operation.

    The listname option is intended to update a single list after importing
    that list's archives.  Doing the entire archive takes way too long and
    doing a 'since' doesn't get the old imported posts.
    """
    global LISTNAME
    LISTNAME = listname
    update_cmd = UpdateIndexCommand()
    if LISTNAME is None:
        # Find the last email in the index:
        try:
            last_email = SearchQuerySet().latest('archived_date')
        except Exception:
            # Different backends can raise different exceptions unfortunately
            update_cmd.start_date = None
        else:
            update_cmd.start_date = last_email.archived_date
    else:
        # Is this a valid list?
        try:
            get_object_or_404(MailingList, name=listname)
        except Http404 as e:
            raise CommandError('{}: {}'.format(listname, e))
        # set the start date to None to do the whole list.
        update_cmd.start_date = None
    # set defaults
    update_cmd.verbosity = verbosity
    update_cmd.batchsize = None
    update_cmd.end_date = None
    update_cmd.workers = 0
    update_cmd.commit = True
    update_cmd.remove = remove
    try:
        from haystack.management.commands.update_index import \
            DEFAULT_MAX_RETRIES
    except ImportError:
        pass
    else:
        update_cmd.max_retries = DEFAULT_MAX_RETRIES
    update_cmd.update_backend("hyperkitty", "default")
