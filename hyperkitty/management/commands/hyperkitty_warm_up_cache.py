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
Warm up the cache.

Author: Aurelien Bompard <abompard@fedoraproject.org>
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils.timezone import now
from hyperkitty.management.utils import setup_logging
from hyperkitty.models import MailingList


class Command(BaseCommand):
    help = "Warm up the cache"

    def add_arguments(self, parser):
        parser.add_argument('mlists', nargs='*')
        parser.add_argument(
            '-m', '--months', type=int, default=1,
            help="number of months to cache")

    def handle(self, *args, **options):
        setup_logging(self, options["verbosity"])
        mlists = [
            MailingList.objects.get(name=name)
            for name in options["mlists"]
            ]
        if not mlists:
            mlists = MailingList.objects.order_by("name").all()
        for mlist in mlists:
            self.warm_up_mlist(mlist, options)

    def warm_up_mlist(self, mlist, options):
        if options["verbosity"] > 1:
            self.stdout.write("Warming up cache for %s" % mlist.name)
        # Recent data
        for cached_value in mlist.recent_cached_values:
            cached_value.warm_up()
        for thread in mlist.recent_threads:
            self.warm_up_thread(thread)
        # Other months
        month_start = now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        for month_num in range(options["months"]):
            month_start = month_start - datetime.timedelta(days=1)
            month_start = month_start.replace(day=1)
            mlist.cached_values["participants_count_for_month"].warm_up(
                month_start.year, month_start.month)
            month_end = month_start + datetime.timedelta(days=32)
            month_end = month_end.replace(day=1)
            for thread in mlist.get_threads_between(month_start, month_end):
                self.warm_up_thread(thread)

    def warm_up_thread(self, thread):
        for cached_value in thread.cached_values.values():
            cached_value.warm_up()
        for email in thread.emails.all():
            for cached_value in email.cached_values.values():
                cached_value.warm_up()
