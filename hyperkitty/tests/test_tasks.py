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

from email.message import EmailMessage

from hyperkitty import tasks
from hyperkitty.lib.incoming import add_to_list
from hyperkitty.models.email import Email
from hyperkitty.models.thread import Thread
from hyperkitty.tests.utils import TestCase
from mock import patch


class TaskTestCase(TestCase):

    def test_rebuild_thread_cache_new_email_no_thread(self):
        try:
            tasks.rebuild_thread_cache_new_email(42)
        except Thread.DoesNotExist:
            self.fail("No protection when the thread is deleted")

    def test_compute_thread_positions_no_thread(self):
        try:
            tasks.compute_thread_positions(42)
        except Thread.DoesNotExist:
            self.fail("No protection when the thread is deleted")

    def test_check_orphans_no_email(self):
        try:
            tasks.check_orphans(42)
        except Email.DoesNotExist:
            self.fail("No protection when the email is deleted")

    def test_check_orphans(self):
        # Create an orphan: the reply arrived first
        msg_reply = EmailMessage()
        msg_reply["From"] = "sender2@example.com"
        msg_reply["Message-ID"] = "<msgid2>"
        msg_reply["In-Reply-To"] = "<msgid1>"
        msg_reply.set_payload("reply")
        msg_orig = EmailMessage()
        msg_orig["From"] = "sender1@example.com"
        msg_orig["Message-ID"] = "<msgid1>"
        msg_orig.set_payload("original message")
        with patch("hyperkitty.tasks.check_orphans") as mock_co:
            add_to_list("example-list", msg_reply)
            add_to_list("example-list", msg_orig)
            self.assertEqual(mock_co.delay.call_count, 2)
        orig = Email.objects.get(message_id="msgid1")
        reply = Email.objects.get(message_id="msgid2")
        self.assertIsNone(reply.parent)
        # Now call the check_orphans function
        tasks.check_orphans(orig.id)
        reply.refresh_from_db()
        self.assertEqual(reply.parent_id, orig.pk)
