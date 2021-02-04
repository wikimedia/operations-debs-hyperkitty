# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2021 by the Free Software Foundation, Inc.
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

import datetime
import os
from email import message_from_file, message_from_string
from email.message import EmailMessage
from tempfile import gettempdir
from traceback import format_exc

from django.utils import timezone
from django.utils.timezone import get_fixed_timezone

from hyperkitty.lib import utils
from hyperkitty.tests.utils import TestCase, get_test_file


SLOP = datetime.timedelta(seconds=2)


def test_rwl(*args, **kwargs):
    """This function is called in some tests by

    run_with_lock(test_rwl, *args, **kwargs)

    kwargs are:
    remove: boolean if true use a longer lifetime
    lockfile: the path to the lockfile
    lifetime: the expected lock lifetime.

    If the path exists and its mtime is now + the expected lifetime +- slop, it
    just returns. Otherwise it raises various exceptions.
"""

    try:
        expire_time = datetime.datetime.fromtimestamp(
            os.stat(kwargs['lockfile']).st_mtime)
    except FileNotFoundError:
        raise
    if isinstance(kwargs['lifetime'], int):
        life = datetime.timedelta(seconds=kwargs['lifetime'])
    elif isinstance(kwargs['lifetime'], datetime.timedelta):
        life = kwargs['lifetime']
    else:
        raise ValueError
    expect_expire = datetime.datetime.now() + life
    if abs(expire_time - expect_expire) > SLOP:
        raise ValueError


class TestUtils(TestCase):

    def test_ref_parsing(self):
        with open(
                get_test_file("strange-in-reply-to-header.txt")
                ) as email_file:
            msg = message_from_file(email_file)
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "200704070053.46646.other.person@example.com")

    def test_wrong_reply_to_format(self):
        with open(get_test_file("wrong-in-reply-to-header.txt")) as email_file:
            msg = message_from_file(email_file)
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, None)

    def test_in_reply_to(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["In-Reply-To"] = " <ref-1> "
        msg.set_content("Dummy message")
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "ref-1")

    def test_in_reply_to_and_reference(self):
        """The In-Reply-To header should win over References"""
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["In-Reply-To"] = " <ref-1> "
        msg["References"] = " <ref-2> "
        msg.set_content("Dummy message")
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "ref-1")

    def test_single_reference(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["References"] = " <ref-1> "
        msg.set_content("Dummy message")
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "ref-1")

    def test_reference_no_brackets(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["References"] = "ref-1"
        msg.set_content("Dummy message")
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "ref-1")

    def test_multiple_reference(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["References"] = " <ref-1> <ref-2> "
        msg.set_content("Dummy message")
        ref_id = utils.get_ref(msg)
        self.assertEqual(ref_id, "ref-2")

    def test_empty_reference(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["References"] = " "
        msg.set_content("Dummy message")
        try:
            utils.get_ref(msg)
        except IndexError:
            self.fail("Empty 'References' tag should be handled")

    def test_non_ascii_headers(self):
        """utils.header_to_unicode must handle non-ascii headers"""
        testdata = [
                ("=?ISO-8859-2?Q?V=EDt_Ondruch?=", 'V\xedt Ondruch'),
                ("=?UTF-8?B?VsOtdCBPbmRydWNo?=", 'V\xedt Ondruch'),
                ("=?iso-8859-1?q?Bj=F6rn_Persson?=", 'Bj\xf6rn Persson'),
                ("=?UTF-8?B?TWFyY2VsYSBNYcWhbMOhxYhvdsOh?=",
                 'Marcela Ma\u0161l\xe1\u0148ov\xe1'),
                ("Dan =?ISO-8859-1?Q?Hor=E1k?=", 'Dan Hor\xe1k'),
                ("=?ISO-8859-1?Q?Bj=F6rn?= Persson", 'Bj\xf6rn Persson'),
                ("=?UTF-8?Q?Re=3A_=5BFedora=2Dfr=2Dlist=5D_Compte=2D"
                 "rendu_de_la_r=C3=A9union_du_?= =?UTF-8?Q?1_novembre_2009?=",
                 "Re: [Fedora-fr-list] Compte-rendu de la r\xe9union du "
                 "1 novembre 2009"),
                ("=?iso-8859-1?q?Compte-rendu_de_la_r=E9union_du_?= "
                 "=?iso-8859-1?q?1_novembre_2009?=",
                 "Compte-rendu de la r\xe9union du 1 novembre 2009"),
                ]
        for h_in, h_expected in testdata:
            h_out = utils.header_to_unicode(h_in)
            self.assertEqual(h_out, h_expected)
            self.assertTrue(isinstance(h_out, str))

    def test_bad_header(self):
        """
        utils.header_to_unicode must handle badly encoded non-ascii headers
        """
        testdata = [
            (b"Guillermo G\xf3mez", "Guillermo G\ufffdmez"),
            ("=?gb2312?B?UmU6IFJlOl9bQW1iYXNzYWRvcnNdX01hdGVyaWFfc29icmVfb1"
             "9DRVNvTF8oRGnhcmlvX2RlX2JvcmRvKQ==?=",
             "Re: Re:_[Ambassadors]_Materia_sobre_o_CESoL_"
             "(Di\ufffdrio_de_bordo)"),
        ]
        for h_in, h_expected in testdata:
            try:
                h_out = utils.header_to_unicode(h_in)
            except UnicodeDecodeError as e:
                self.fail(e)
            self.assertEqual(h_out, h_expected)
            self.assertTrue(isinstance(h_out, str))

    def test_wrong_datestring(self):
        datestring = "Fri, 5 Dec 2003 11:41 +0000 (GMT Standard Time)"
        parsed = utils.parsedate(datestring)
        self.assertEqual(parsed, None)

    def test_very_large_timezone(self):
        """
        Timezone displacements must not be greater than 14 hours
        Or PostgreSQL won't accept them.
        """
        datestrings = [
            ("Wed, 1 Nov 2006 23:50:26 +1800",
             datetime.datetime(2006, 11, 1, 23, 50, 26,
                               tzinfo=get_fixed_timezone(18*60))),
            ("Wed, 1 Nov 2006 23:50:26 -1800",
             datetime.datetime(2006, 11, 1, 23, 50, 26,
                               tzinfo=get_fixed_timezone(-18*60))),
            ]
        for datestring, expected in datestrings:
            parsed = utils.parsedate(datestring)
            self.assertEqual(parsed, expected)
            self.assertTrue(parsed.utcoffset() <= datetime.timedelta(hours=13),
                            "UTC offset %s for datetime %s is too large"
                            % (parsed.utcoffset(), parsed))

    def test_datestring_no_timezone(self):
        datestring = "Sun, 12 Dec 2004 19:11:28"
        parsed = utils.parsedate(datestring)
        expected = datetime.datetime(2004, 12, 12, 19, 11, 28,
                                     tzinfo=timezone.utc)
        self.assertEqual(parsed, expected)

    def test_datestring_wrong_offset(self):
        datestring = "Sat, 30 Aug 2008 16:40:31 +05-30"
        try:
            parsed = utils.parsedate(datestring)
        except ValueError as e:
            self.fail(format_exc(e))
        expected = datetime.datetime(2008, 8, 30, 16, 40, 31,
                                     tzinfo=timezone.utc)
        self.assertEqual(parsed, expected)

    def test_unknown_encoding(self):
        """Unknown encodings should just replace unknown characters"""
        header = "=?x-gbk?Q?Frank_B=A8=B9ttner?="
        decoded = utils.header_to_unicode(header)
        self.assertEqual(decoded, 'Frank B\ufffd\ufffdttner')

    def test_no_from(self):
        msg = EmailMessage()
        msg.set_content("Dummy message")
        try:
            name, email = utils.parseaddr(msg["From"])
        except AttributeError as e:
            self.fail(e)
        self.assertEqual(name, '')
        self.assertEqual(email, '')

    def test_odd_from(self):
        msg = EmailMessage()
        msg['From'] = 'First Last at somedomain <user@example.com>'
        msg.set_content("Dummy message")
        try:
            name, email = utils.parseaddr(msg["From"])
        except AttributeError as e:
            self.fail(e)
        self.assertEqual(name, 'First Last at somedomain')
        self.assertEqual(email, 'user@example.com')

    def test_from_with_at(self):
        msg = EmailMessage()
        msg['From'] = 'user at example.com'
        msg.set_content("Dummy message")
        try:
            name, email = utils.parseaddr(msg["From"])
        except AttributeError as e:
            self.fail(e)
        self.assertEqual(name, 'user@example.com')
        self.assertEqual(email, 'user@example.com')

    def test_from_with_bracketed_at(self):
        msg = EmailMessage()
        msg['From'] = 'Display Name <user at example.com>'
        msg.set_content("Dummy message")
        try:
            name, email = utils.parseaddr(msg["From"])
        except AttributeError as e:
            self.fail(e)
        self.assertEqual(name, 'Display Name')
        if email != '"user@example.com"':
            # This is bogus. utils.parseaddr only seems to return the address
            # quoted in this test, not when called in other contexts.
            self.assertEqual(email, 'user@example.com')

    def test_normal_from(self):
        msg = EmailMessage()
        msg['From'] = 'Display Name <user@example.com>'
        msg.set_content("Dummy message")
        try:
            name, email = utils.parseaddr(msg["From"])
        except AttributeError as e:
            self.fail(e)
        self.assertEqual(name, 'Display Name')
        self.assertEqual(email, 'user@example.com')

    def test_get_message_id_hash(self):
        msg_id = '<87myycy5eh.fsf@uwakimon.sk.tsukuba.ac.jp>'
        expected = 'JJIGKPKB6CVDX6B2CUG4IHAJRIQIOUTP'
        self.assertEqual(utils.get_message_id_hash(msg_id), expected)

    def test_get_message_id(self):
        msg = EmailMessage()
        msg["Message-Id"] = '<%s>' % ('x' * 300)
        self.assertEqual(utils.get_message_id(msg), 'x' * 254)

    def test_get_folded_message_id(self):
        msg = message_from_string("""\
From: dummy@example.com
To: list@example.com
Subject: Test message
Message-ID:
 <a.folded.message.id>

Dummy Message
""")
        self.assertEqual(utils.get_message_id(msg), 'a.folded.message.id')

    def test_non_ascii_ref(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<dummy>"
        msg["In-Reply-To"] = "<ref-\xed>"
        msg.set_content("Dummy message")
        try:
            ref_id = utils.get_ref(msg)
        except UnicodeEncodeError as e:
            self.fail(e)
        # utf-8 characters are perfectly legitimate here (RFC 6532) and
        # stripping it here makes no sense at all
        self.assertEqual(ref_id, "ref-\xed")

    def test_run_with_lock_defaults(self):
        utils.run_with_lock(
            test_rwl, remove=False, lifetime=15,
            lockfile=os.path.join(gettempdir(),
                                  'hyperkitty-jobs-update-index.lock'))
        self.assertEqual('',
                         open(os.path.join(self.tmpdir, 'error.log')).read())

    def test_run_with_lock_extended(self):
        utils.run_with_lock(
            test_rwl, remove=True, lifetime=900,
            lockfile=os.path.join(gettempdir(),
                                  'hyperkitty-jobs-update-index.lock'))
        self.assertEqual('',
                         open(os.path.join(self.tmpdir, 'error.log')).read())

    def test_run_with_lock_extended_setting(self):
        self._override_setting('HYPERKITTY_JOBS_UPDATE_INDEX_LOCK_LIFE', 300)
        utils.run_with_lock(
            test_rwl, remove=True, lifetime=300,
            lockfile=os.path.join(gettempdir(),
                                  'hyperkitty-jobs-update-index.lock'))
        self.assertEqual('',
                         open(os.path.join(self.tmpdir, 'error.log')).read())

    def test_run_with_lock_alternate_file(self):
        self._override_setting(
            'HYPERKITTY_JOBS_UPDATE_INDEX_LOCKFILE',
            os.path.join(gettempdir(), 'alt.lock'))
        utils.run_with_lock(
            test_rwl, remove=False, lifetime=15,
            lockfile=os.path.join(gettempdir(), 'alt.lock'))
        self.assertEqual('',
                         open(os.path.join(self.tmpdir, 'error.log')).read())

    def test_run_with_lock_bad_file(self):
        utils.run_with_lock(test_rwl, remove=False,
                            lifetime=15, lockfile='/bogus/file/name')
        self.assertIn('/bogus/file/name',
                      open(os.path.join(self.tmpdir, 'error.log')).read())

    def test_run_with_lock_wrong_time(self):
        utils.run_with_lock(
            test_rwl, remove=False, lifetime=20,
            lockfile=os.path.join(gettempdir(),
                                  'hyperkitty-jobs-update-index.lock'))
        self.assertIn('ValueError',
                      open(os.path.join(self.tmpdir, 'error.log')).read())
