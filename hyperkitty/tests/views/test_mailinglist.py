# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2021 by the Free Software Foundation, Inc.
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

import re
from email.message import EmailMessage
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import override_settings

from bs4 import BeautifulSoup

from hyperkitty.lib.incoming import add_to_list
from hyperkitty.models import Email, Thread
from hyperkitty.tests.utils import TestCase
from hyperkitty.utils import reverse


class DeleteMailingListTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'testuser', 'test@example.com', 'testPass')
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='testuser', password='testPass')

    def test_delete_mailinglist(self):
        # Let's add a few messages.
        for num in range(10):
            msg = EmailMessage()
            msg["From"] = "Dummy Sender <dummy@example.com>"
            msg["Subject"] = "First Subject {}".format(num)
            msg["Date"] = "Mon, 02 Feb 2015 13:00:00 +0300"
            msg["Message-ID"] = "<msg{}>".format(num)
            msg.set_payload("Dummy message {}".format(num))
            add_to_list("list@example.com", msg)
        self.assertEqual(len(Thread.objects.all()), 10)
        self.assertEqual(len(Email.objects.all()), 10)
        url = reverse('hk_list_delete', args=("list@example.com",))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'hyperkitty/list_delete.html')
        self.assertContains(resp, 'Do you want to continue?')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/')
        self.assertEqual(len(Thread.objects.all()), 0)
        self.assertEqual(len(Email.objects.all()), 0)

    def test_delete_mailinglist_logged_out(self):
        self.client.logout()
        msg = EmailMessage()
        msg["From"] = "Dummy Sender <dummy@example.com>"
        msg["Subject"] = "First Subject"
        msg["Date"] = "Mon, 02 Feb 2015 13:00:00 +0300"
        msg["Message-ID"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        url = reverse('hk_list_delete', args=("list@example.com",))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.url,
            '/accounts/login/?next=/list/list%40example.com/delete/')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.url,
            '/accounts/login/?next=/list/list%40example.com/delete/')

    def test_delete_mailinglist_raised_error(self):
        msg = EmailMessage()
        msg["From"] = "Dummy Sender <dummy@example.com>"
        msg["Subject"] = "First Subject"
        msg["Date"] = "Mon, 02 Feb 2015 13:00:00 +0300"
        msg["Message-ID"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        url = reverse('hk_list_delete', args=("list@example.com",))
        with patch('hyperkitty.views.mlist.get_object_or_404') as mock_obj:
            mock_mlist = Mock()
            mock_mlist.delete.side_effect = IntegrityError('Error Deleting')
            mock_mlist.name = "list@example.com"
            mock_obj.return_value = mock_mlist

            resp = self.client.post(url)
            self.assertTrue(mock_mlist.delete.called)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(
                resp.url,
                reverse('hk_list_overview', args=("list@example.com",)))

    def test_overview_new_thread_button(self):
        msg = EmailMessage()
        msg["From"] = "Dummy Sender <dummy@example.com>"
        msg["Subject"] = "First Subject"
        msg["Date"] = "Mon, 02 Feb 2015 13:00:00 +0300"
        msg["Message-ID"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        url = reverse('hk_list_overview', args=('list@example.com', ))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(len(soup.find_all("span",
                                           string=re.compile("Start a n"))), 1)
        # Check that the button does not exist when the setting is disabled.
        with override_settings(HYPERKITTY_ALLOW_WEB_POSTING=False):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            soup = BeautifulSoup(response.content, "html.parser")
            self.assertEqual(len(soup.find_all(
                "span", string=re.compile("Start a n"))), 0)
