# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2021 by the Free Software Foundation, Inc.
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


import json
from email.message import EmailMessage

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import override_settings

from django_mailman3.models import MailDomain
from django_mailman3.tests.utils import FakeMMList, FakeMMMember
from mock import Mock

from hyperkitty.lib.incoming import add_to_list
from hyperkitty.models import ArchivePolicy, MailingList
from hyperkitty.tests.utils import TestCase
from hyperkitty.utils import reverse


class PrivateListTestCase(TestCase):

    def setUp(self):
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
        self.mailman_client.get_list.side_effect = \
            lambda name: FakeMMList(name)

        User.objects.create_user(
            'superuser', 'super@example.com', 'testPass', is_superuser=True)

        self.mm_subbed_user = self._create_user(
            'subbeduser', 'subbed@example.com')
        self.mm_subbed_user.subscriptions = [
            FakeMMMember("list.example.com", 'subbed@example.com'),
        ]
        self.mm_unsubbed_user = self._create_user(
            'unsubbeduser', 'unsubbed@example.com')
        self.mm_unsubbed_user.subscriptions = []

        def mm_get_user(email):
            if email == 'subbed@example.com':
                return self.mm_subbed_user
            else:
                return self.mm_unsubbed_user
        self.mailman_client.get_user.side_effect = mm_get_user

    def tearDown(self):
        self.client.logout()

    def _create_user(self, username, email):
        User.objects.create_user(username, email, 'testPass')
        mm_user = Mock()
        mm_user.user_id = "dummy"
        mm_user.addresses = [email]
        return mm_user

    def _do_test(self, sort_mode):
        response = self.client.get(reverse("hk_root"), {"sort": sort_mode})
        self.assertNotContains(response, "list@example.com", status_code=200)

    def _do_test_contains(self, sort_mode):
        response = self.client.get(reverse("hk_root"), {"sort": sort_mode})
        self.assertContains(response, "list@example.com", status_code=200)

    def test_sort_active(self):
        self._do_test("active")

    def test_sort_popular(self):
        self._do_test("popular")

    def test_sort_name(self):
        self._do_test("name")

    def test_sort_creation(self):
        self._do_test("creation")

    def test_sort_active_subbed(self):
        self.client.login(username='subbeduser', password='testPass')
        self._do_test_contains("active")

    def test_sort_popular_subbed(self):
        self.client.login(username='subbeduser', password='testPass')
        self._do_test_contains("popular")

    def test_sort_name_subbed(self):
        self.client.login(username='subbeduser', password='testPass')
        self._do_test_contains("name")

    def test_sort_creation_subbed(self):
        self.client.login(username='subbeduser', password='testPass')
        self._do_test_contains("creation")

    def test_sort_active_unsubbed(self):
        self.client.login(username='unsubbeduser', password='testPass')
        self._do_test("active")

    def test_sort_popular_unsubbed(self):
        self.client.login(username='unsubbeduser', password='testPass')
        self._do_test("popular")

    def test_sort_name_unsubbed(self):
        self.client.login(username='unsubbeduser', password='testPass')
        self._do_test("name")

    def test_sort_creation_unsubbed(self):
        self.client.login(username='unsubbeduser', password='testPass')
        self._do_test("creation")

    def test_sort_active_super(self):
        self.client.login(username='superuser', password='testPass')
        self._do_test_contains("active")

    def test_sort_popular_super(self):
        self.client.login(username='superuser', password='testPass')
        self._do_test_contains("popular")

    def test_sort_name_super(self):
        self.client.login(username='superuser', password='testPass')
        self._do_test_contains("name")

    def test_sort_creation_super(self):
        self.client.login(username='superuser', password='testPass')
        self._do_test_contains("creation")


class FindTestCase(TestCase):

    def setUp(self):
        MailingList.objects.create(name="list-one@example.com")
        MailingList.objects.create(name="list-two@example.com",
                                   display_name="List Two")

    def test_find(self):
        response = self.client.get("%s?term=one" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content.decode(response.charset)),
            [{'label': 'list-one@example.com',
              'value': 'list-one@example.com'}]
            )

    def test_redirect(self):
        response = self.client.get(reverse("hk_root"), {"name": "one"})
        self.assertRedirects(response, reverse("hk_list_overview", kwargs={
            "mlist_fqdn": "list-one@example.com"}))

    def test_find_name(self):
        response = self.client.get("%s?term=example" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content.decode(response.charset)),
            [{'label': 'list-one@example.com',
              'value': 'list-one@example.com'},
             {'label': 'List Two',
              'value': 'list-two@example.com'}]
            )

    def test_find_name_index(self):
        response = self.client.get(reverse("hk_root"), {"name": "example"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["all_lists"].paginator.count, 2)

    def test_display_name(self):
        ml = MailingList.objects.get(name="list-one@example.com")
        ml.display_name = "Test Value"
        ml.save()
        response = self.client.get("%s?term=value" % reverse("hk_find_list"))
        self.assertEqual(
            json.loads(response.content.decode(response.charset)),
            [{'label': 'Test Value', 'value': 'list-one@example.com'}]
            )

    def test_find_display_name_index(self):
        response = self.client.get(reverse("hk_root"), {"name": "List Two"})
        self.assertRedirects(response, reverse("hk_list_overview", kwargs={
            "mlist_fqdn": "list-two@example.com"}))

    def test_show_inactive_list_default(self):
        response = self.client.get(reverse("hk_root"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            '<label><input type="checkbox" value="inactive" />Hide inactive'
            '</label>' in
            str(response.content))

    @override_settings(SHOW_INACTIVE_LISTS_DEFAULT=True)
    def test_show_inactive_list_true(self):
        response = self.client.get(reverse("hk_root"))
        self.assertTrue(settings.SHOW_INACTIVE_LISTS_DEFAULT)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            '<label><input type="checkbox" value="inactive" checked="checked"'
            '/>Hide inactive</label>' in
            str(response.content))


@override_settings(FILTER_VHOST=True, ALLOWED_HOSTS=["*"])
class DomainFilteringTestCase(TestCase):

    def setUp(self):
        self._site = Site.objects.create(domain='www.example.com',
                                         name='www')
        self.mail_domain2 = MailDomain.objects.create(
            site=self._site, mail_domain="example.com")

    def _do_test(self, listdomain, vhost, expected):
        MailingList.objects.get_or_create(
            name="test@{}".format(listdomain))[0]
        response = self.client.get(reverse("hk_root"), HTTP_HOST=vhost)
        self.assertEqual(
            response.context["all_lists"].paginator.count, expected)

    def test_same_domain(self):
        self._do_test("example.com", "example.com", 1)
        self._do_test("lists.example.com", "lists.example.com", 1)

    def test_web_subdomain(self):
        self._do_test("example.com", "www.example.com", 1)

    def test_top_domain(self):
        self._do_test("lists.example.com", "example.com", 0)

    def test_different_subdomains(self):
        self._do_test("lists.example.com", "something-else.example.com", 0)

    def test_different_domains(self):
        self._do_test("example.com", "another-example.com", 0)
        self._do_test("lists.example.com", "archives.another-example.com", 0)

    def test_single_component_domain(self):
        self._do_test("intranet", "intranet", 1)

    def test_different_single_component_domain(self):
        self._do_test("intranet", "extranet", 0)
