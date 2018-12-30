# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 by the Free Software Foundation, Inc.
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
# Author: Aamir Khan <syst3m.w0rm@gmail.com>
# Author: Aurelien Bompard <abompard@fedoraproject.org>
#

import os
import datetime
import gzip
import mailbox
import shutil
from email import message_from_bytes, policy
from email.message import EmailMessage

from mock import Mock
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from hyperkitty.utils import reverse
from django.core.cache import cache
from django_mailman3.tests.utils import FakeMMList, FakeMMMember

from hyperkitty.models import (
    MailingList, ArchivePolicy, Sender, Thread, Favorite, Email)
from hyperkitty.lib.incoming import add_to_list
from hyperkitty.tests.utils import TestCase


class ListArchivesTestCase(TestCase):

    def setUp(self):
        # Create the list by adding a dummy message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)

    def test_no_date(self):
        today = datetime.date.today()
        response = self.client.get(reverse(
                'hk_archives_latest', args=['list@example.com']))
        final_url = reverse(
            'hk_archives_with_month',
            kwargs={
                'mlist_fqdn': 'list@example.com',
                'year': today.year,
                'month': today.month,
            })
        self.assertRedirects(response, final_url)

    def test_wrong_date(self):
        response = self.client.get(reverse(
                'hk_archives_with_month', kwargs={
                    'mlist_fqdn': 'list@example.com',
                    'year': '9999',
                    'month': '0',
                }))
        self.assertEqual(response.status_code, 404)

    def test_overview(self):
        response = self.client.get(reverse(
            'hk_list_overview', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_name"], "overview")

    def test_overview_top_threads(self):
        response = self.client.get(reverse(
            'hk_list_overview_top_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)

    def test_overview_recent_threads(self):
        response = self.client.get(reverse(
            'hk_list_overview_recent_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)

    def test_overview_pop_threads(self):
        response = self.client.get(reverse(
            'hk_list_overview_pop_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 0)

    def test_overview_with_user(self):
        user = User.objects.create_user(
            'testuser', 'dummy@example.com', 'testPass')
        sender = Sender.objects.get(address='dummy@example.com')
        sender.mailman_id = "dummy"
        sender.save()
        mm_user = Mock()
        mm_user.user_id = "dummy"
        self.mailman_client.get_user.side_effect = lambda name: mm_user
        self.client.login(username='testuser', password='testPass')
        thread = Thread.objects.first()
        Favorite.objects.create(thread=thread, user=user)
        response = self.client.get(
            reverse('hk_list_overview', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_name"], "overview")
        response = self.client.get(
            reverse('hk_list_overview_posted_to', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)
        response = self.client.get(
            reverse('hk_list_overview_favorites', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)

    def test_overview_cleaned_cache(self):
        # Test the overview page with a clean cache (different code path for
        # MailingList.recent_threads)
        mlist = MailingList.objects.get(name="list@example.com")
        cache.delete("MailingList:%s:recent_threads" % mlist.pk)
        response = self.client.get(
            reverse('hk_list_overview', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse(
            'hk_list_overview_top_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)
        response = self.client.get(reverse(
            'hk_list_overview_recent_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 1)
        response = self.client.get(reverse(
            'hk_list_overview_pop_threads', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["threads"]), 0)

    def test_email_escaped_sender(self):
        response = self.client.get(reverse(
            'hk_list_overview_top_posters', args=["list@example.com"]))
        self.assertContains(response, "dummy", status_code=200)
        self.assertNotContains(response, "dummy@example.com", status_code=200)


class ExportMboxTestCase(TestCase):

    def setUp(self):
        # Create the list by adding a dummy message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        # We need a temp dir for the mailbox, Python's mailbox module needs a
        # filesystem path, it does not accept a file-like object.

    def _get_mbox(self, qs=None):
        url = reverse(
            "hk_list_export_mbox", args=["list@example.com", "dummy"])
        if qs:
            url += "?" + qs
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/gzip")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="dummy.mbox.gz"')
        mboxfilepath = os.path.join(self.tmpdir, "dummy.mbox")
        # Store the gzipped mailbox
        with open(mboxfilepath + ".gz", "wb") as mboxfile:
            for line in response.streaming_content:
                mboxfile.write(line)
        # Decompress the mailbox
        with gzip.open(mboxfilepath + ".gz", 'rb') as f_in, \
                open(mboxfilepath, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        mbox = mailbox.mbox(mboxfilepath)
        return mbox

    def test_basic(self):
        mbox = self._get_mbox()
        content = open(mbox._path).read()
        self.assertTrue(content.startswith("From dummy@example.com "))
        self.assertEqual(len(mbox), 1)
        msg = mbox.values()[0]
        msg_raw = msg.as_bytes(unixfrom=False)
        email = message_from_bytes(msg_raw, policy=policy.default)
        self.assertEqual(email["From"], "dummy@example.com")
        self.assertEqual(email["Message-ID"], "<msg>")
        self.assertTrue(email.is_multipart())
        content = email.get_payload()[0]
        self.assertEqual(content.get_payload(), "Dummy message\n")

    def test_with_sender_name(self):
        email = Email.objects.get(message_id="msg")
        email.sender_name = "Dummy Sender"
        email.save()
        mbox = self._get_mbox()
        email = mbox.values()[0]
        self.assertEqual(email["From"], "Dummy Sender <dummy@example.com>")

    def test_between_dates(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Date"] = "01 Sep 2015 00:00:00"
        msg["Message-ID"] = "<msg2>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        mbox = self._get_mbox(qs="start=2015-09-01&end=2015-10-01")
        self.assertEqual(len(mbox), 1)
        mbox_msg = mbox.values()[0]
        self.assertEqual(mbox_msg["Message-ID"], "<msg2>")

    def test_thread(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["In-Reply-To"] = "<msg>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        # Add a message in a different thread:
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg3>"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)
        thread_id = Email.objects.get(message_id="msg").thread.thread_id
        mbox = self._get_mbox(qs="thread=%s" % thread_id)
        self.assertEqual(len(mbox), 2)
        self.assertEqual(
            [m["Message-ID"] for m in mbox], ["<msg>", "<msg2>"])

    def test_message(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["In-Reply-To"] = "<msg>"
        msg.set_payload("Dummy message")
        msg_id = add_to_list("list@example.com", msg)
        mbox = self._get_mbox(qs="message=%s" % msg_id)
        self.assertEqual(len(mbox), 1)
        self.assertEqual([m["Message-ID"] for m in mbox], ["<msg2>"])

    def test_bogus_dates(self):
        base_url = reverse(
            "hk_list_export_mbox", args=["list@example.com", "dummy"])
        url = "{}?start=invalid".format(base_url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        url = "{}?end=2017-01-01/".format(base_url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)


class PrivateArchivesTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'testuser', 'test@example.com', 'testPass')
        MailingList.objects.create(
            name="list@example.com", subject_prefix="[example] ",
            archive_policy=ArchivePolicy.private.value)
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msgid>"
        msg["Subject"] = "Dummy message"
        msg.set_payload("Dummy message")
        msg["Message-ID-Hash"] = self.msgid = add_to_list(
            "list@example.com", msg)
        # Set the mailman_client after the message has been added to the list,
        # otherwise MailingList.update_from_mailman() will overwrite the list
        # properties.
        self.mailman_client.get_list.side_effect = \
            lambda name: FakeMMList(name)
        self.mm_user = Mock()
        self.mm_user.user_id = "dummy"
        self.mailman_client.get_user.side_effect = lambda name: self.mm_user
        self.mm_user.subscriptions = [
            FakeMMMember("list.example.com", self.user.email),
        ]
        self.mm_user.addresses = ['test@example.com']

    def tearDown(self):
        self.client.logout()

    def _do_test(self, url, query=None):
        if query is None:
            query = {}
        response = self.client.get(url, query)
        self.assertEqual(response.status_code, 403)
        self.client.login(username='testuser', password='testPass')
        # # use a temp variable below because self.client.session is actually a
        # # property which returns a new instance en each call :-/
        # http://blog.joshcrompton.com/2012/09/how-to-use-sessions-in-django-unit-tests.html
        # session = self.client.session
        # session["subscribed"] = ["list@example.com"]
        # session.save()
        response = self.client.get(url, query)
        self.assertEqual(response.status_code, 200)
        try:
            self.assertContains(response, "Dummy message")
        except AssertionError:
            print(response.content)
            raise

    def test_month_view(self):
        now = datetime.datetime.now()
        self._do_test(reverse(
            'hk_archives_with_month',
            args=["list@example.com", now.year, now.month]))

    def test_overview_top_threads(self):
        self._do_test(reverse(
            'hk_list_overview_top_threads', args=["list@example.com"]))

    def test_overview_recent_threads(self):
        self._do_test(reverse(
            'hk_list_overview_recent_threads', args=["list@example.com"]))

    def test_thread_view(self):
        self._do_test(reverse(
            'hk_thread', args=["list@example.com", self.msgid]))

    def test_message_view(self):
        self._do_test(reverse(
            'hk_message_index', args=["list@example.com", self.msgid]))


class MonthsListTestCase(TestCase):

    def setUp(self):
        # Create the list by adding a dummy message
        # The message must be old to create multiple year accordion panels in
        # the months list.
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg>"
        msg["Date"] = "01 Feb 2010 00:00:00 UTC"
        msg.set_payload("Dummy message")
        add_to_list("list@example.com", msg)

    def _assertCollapsed(self, panel):
        self.assertTrue(
            "in" not in panel["class"],
            "Panel %s has the 'in' class" % panel["id"])
        self.assertTrue(
            "collapse" in panel["class"],
            "Panel %s has no 'collapse' class" % panel["id"])

    def _assertNotCollapsed(self, panel):
        self.assertTrue(
            "in" in panel["class"],
            "Panel %s has no 'in' class" % panel["id"])

    def _assertActivePanel(self, html, panel_num):
        """ Checks that the <panel_num> year is active.
        The panel_num arg is the id in the years list. Example: panel_num=0
        means the current year is active, panel_num=-1 means the year of the
        first archived email is active.
        """
        soup = BeautifulSoup(html, "html.parser")
        months_list = soup.find(id="months-list")
        panels = months_list.find_all(class_="panel-collapse")
        for panel in panels:
            if panel == panels[panel_num]:
                self._assertNotCollapsed(panel)
            else:
                self._assertCollapsed(panel)

    def test_overview(self):
        response = self.client.get(reverse(
            'hk_list_overview', args=["list@example.com"]))
        self.assertEqual(response.status_code, 200)
        self._assertActivePanel(response.content, 0)

    def test_month_list(self):
        response = self.client.get(reverse(
                'hk_archives_with_month', kwargs={
                    'mlist_fqdn': 'list@example.com',
                    'year': '2011',
                    'month': '1',
                }))
        self.assertEqual(response.status_code, 200)
        self._assertActivePanel(response.content, -2)
