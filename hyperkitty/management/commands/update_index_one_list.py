# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2018 by the Free Software Foundation, Inc.
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
Update the search index for a single list.
"""

from django.core.management.base import BaseCommand
from hyperkitty.management.utils import setup_logging
from hyperkitty.search_indexes import update_index


class Command(BaseCommand):
    help = "Update the search index with all posts from a single list."

    def add_arguments(self, parser):
        parser.add_argument(
            'listname', nargs=1, default=False,
            help="The name of the list whose messages to index.")

    def handle(self, *args, **options):
        options["verbosity"] = int(options.get("verbosity", "1"))
        setup_logging(self, options["verbosity"])
        update_index(listname=options.get("listname")[0],
                     verbosity=options["verbosity"])
