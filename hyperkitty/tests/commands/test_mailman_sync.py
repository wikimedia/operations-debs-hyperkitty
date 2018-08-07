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

from mock import patch
from django.core.management import call_command

from hyperkitty.tests.utils import TestCase


class CommandTestCase(TestCase):

    @patch("hyperkitty.management.commands.mailman_sync.sync_with_mailman")
    def test_simple(self, sync_fn):
        call_command('mailman_sync')
        self.assertTrue(sync_fn.called)
        self.assertEqual(sync_fn.call_args[1], {"overwrite": False})
        call_command('mailman_sync', overwrite=True)
        self.assertEqual(sync_fn.call_args[1], {"overwrite": True})
