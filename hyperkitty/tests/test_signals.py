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

from django_mailman3.signals import mailinglist_created, mailinglist_modified
from mock import patch

from hyperkitty.tests.utils import TestCase


class SignalsTestCase(TestCase):

    @patch('hyperkitty.signals.import_list_from_mailman')
    def test_user_subscribed(self, mock_ilfm):
        mailinglist_created.send(
            sender="Postorius", list_id="list.example.com")
        self.assertEqual(mock_ilfm.call_count, 1)
        self.assertEqual(
            mock_ilfm.call_args_list[0][0],
            ("list.example.com", )
            )
        mailinglist_modified.send(
            sender="Postorius", list_id="list.example.com")
        self.assertEqual(mock_ilfm.call_count, 2)
        self.assertEqual(
            mock_ilfm.call_args_list[1][0],
            ("list.example.com", )
            )
