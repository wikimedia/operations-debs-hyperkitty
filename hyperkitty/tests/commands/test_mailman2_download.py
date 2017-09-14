# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 by the Free Software Foundation, Inc.
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

from __future__ import absolute_import, print_function, unicode_literals

import datetime

from mock import Mock, patch
from django.core.management import call_command

from hyperkitty.management.commands.mailman2_download import (
    _archive_downloader, MONTHS)
from hyperkitty.tests.utils import TestCase


class CommandTestCase(TestCase):

    def setUp(self):
        self.common_cmd_args = dict(
            verbosity=2, list_address="list@example.com",
            url="http://example.com", destination=self.tmpdir,
        )

    @patch("hyperkitty.management.commands.mailman2_download.Pool")
    def test_simple(self, pool_class):
        this_year = datetime.date.today().year
        kwargs = self.common_cmd_args.copy()
        pool = Mock()
        pool_class.return_value = pool
        call_command('mailman2_download', **kwargs)
        self.assertEqual(pool.map.call_count, 1)
        map_args = pool.map.call_args_list[0][0]
        self.assertEqual(map_args[0], _archive_downloader)
        self.assertEqual(len(list(map_args[1])), 12)
        expected_options = kwargs.copy()
        expected_options["start"] = [this_year]
        for index, dl_args in enumerate(map_args[1]):
            self.assertEqual(dl_args[0], expected_options)
            self.assertEqual(dl_args[1], this_year)
            self.assertEqual(dl_args[2], MONTHS[index])
