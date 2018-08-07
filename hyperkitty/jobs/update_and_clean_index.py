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

"""
Update the full-text index
"""

from django_extensions.management.jobs import BaseJob

from hyperkitty.lib.utils import run_with_lock
from hyperkitty.search_indexes import update_index


class Job(BaseJob):
    help = "Update the full-text index and clean old entries"
    when = "monthly"

    def execute(self):
        run_with_lock(update_index, remove=True)
