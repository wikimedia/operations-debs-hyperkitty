# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2021 by the Free Software Foundation, Inc.
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

import os
import tempfile
from datetime import datetime
from email.message import EmailMessage
from mimetypes import guess_all_extensions

from hyperkitty.lib.incoming import add_to_list
from hyperkitty.models import Email, MailingList, Sender, Thread
from hyperkitty.tests.utils import TestCase


def _create_tree(tree):
    emails = []
    for msgid in tree:
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["Message-ID"] = "<%s>" % msgid
        parent_id = msgid.rpartition(".")[0]
        if Email.objects.filter(message_id=parent_id).exists():
            msg["In-Reply-To"] = "<%s>" % parent_id
        msg.set_payload("dummy message")
        add_to_list("example-list", msg)
        emails.append(Email.objects.get(message_id=msgid))
    return emails


class EmailTestCase(TestCase):

    def test_as_message(self):
        msg_in = EmailMessage()
        msg_in["From"] = "dummy@example.com"
        msg_in["Message-ID"] = "<msg>"
        msg_in["Date"] = "Fri, 02 Nov 2012 16:07:54 +0000"
        msg_in.set_payload("Dummy message with email@address.com")
        add_to_list("list@example.com", msg_in)
        email = Email.objects.get(message_id="msg")
        msg = email.as_message()
        self.assertEqual(msg["From"], "dummy@example.com")
        self.assertEqual(msg["Message-ID"], "<msg>")
        self.assertEqual(msg["Date"], msg_in["Date"])
        self.assertTrue(msg.is_multipart())
        payload = msg.get_payload()
        self.assertEqual(len(payload), 1)
        self.assertEqual(
            payload[0].get_payload(),
            "Dummy message with email(a)address.com\n")

    def test_as_message_unicode(self):
        msg_in = EmailMessage()
        msg_in["From"] = "dummy@example.com"
        msg_in["Message-ID"] = "<msg>"
        msg_in.set_payload("Dummy message ünîcödé", charset="utf-8")
        add_to_list("list@example.com", msg_in)
        email = Email.objects.get(message_id="msg")
        msg = email.as_message()
        self.assertEqual(msg["From"], "dummy@example.com")
        self.assertEqual(msg["Message-ID"], "<msg>")
        self.assertTrue(msg.is_multipart())
        payload = msg.get_payload()
        self.assertEqual(len(payload), 1)
        payload = payload[0]
        self.assertEqual(
            payload.get_payload(),
            "Dummy message ünîcödé\n")

    def test_as_message_attachments(self):
        msg_in = EmailMessage()
        msg_in["From"] = "dummy@example.com"
        msg_in["Message-ID"] = "<msg>"
        msg_in.set_content("Hello World.")
        msg_in.add_attachment("Dummy message", subtype='plain')
        msg_in.add_attachment("<html><body>Dummy message</body></html>",
                              subtype='html')
        add_to_list("list@example.com", msg_in)
        email = Email.objects.get(message_id="msg")
        msg = email.as_message()
        self.assertEqual(msg["From"], "dummy@example.com")
        self.assertEqual(msg["Message-ID"], "<msg>")
        self.assertTrue(msg.is_multipart())
        payload = msg.get_payload()
        self.assertEqual(len(payload), 3)
        self.assertEqual(
            payload[0].get_content(), "Hello World.\n\n\n\n\n")
        self.assertEqual(
            payload[1].get_content(), "Dummy message\n")
        # The filename extension detection from content type is a bit random
        # (depends on the PYTHON_HASHSEED), make sure we get the right one
        # here for testing.
        expected_ext = guess_all_extensions("text/html", strict=False)[0]
        self.assertEqual(payload[2].get_content_type(), "text/html")
        self.assertEqual(
            payload[2]["Content-Disposition"],
            'attachment; filename="attachment%s"' % expected_ext)
        self.assertEqual(
            payload[2].get_content(),
            "<html><body>Dummy message</body></html>\n")

    def test_as_message_attachments_saved_to_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(HYPERKITTY_ATTACHMENT_FOLDER=tmpdir):
                self.test_as_message_attachments()
                # Test that attachments are indeed saved on the fs.  The
                # download path is deterministic and is based on the
                # email.message_id_hash which is going to be consistent because
                # we set the Message-ID in the test case above.  Name of the
                # attachment files are also deterministic since we know the
                # order in which they are added.
                download_path = os.path.join(
                    tmpdir, 'example.com/list/DH/ZU/5Y/1')
                files = sorted(os.listdir(download_path))
                self.assertEqual(len(files), 2)
                self.assertEqual(files, ['2', '3'])
                with open(os.path.join(download_path, '2')) as fd:
                    self.assertEqual(fd.read(), "Dummy message\n")
                with open(os.path.join(download_path, '3')) as fd:
                    self.assertEqual(
                        fd.read(),
                        "<html><body>Dummy message</body></html>\n")

    def test_as_message_timezone(self):
        msg_in = EmailMessage()
        msg_in["From"] = "dummy@example.com"
        msg_in["Message-ID"] = "<msg>"
        msg_in["Date"] = "Fri, 02 Nov 2012 16:07:54 +0400"
        msg_in.set_payload("Dummy message")
        add_to_list("list@example.com", msg_in)
        email = Email.objects.get(message_id="msg")
        msg = email.as_message()
        self.assertEqual(msg["Date"], msg_in["Date"])

    def test_as_message_folded_subject(self):
        sender = Sender(address="dummy@example.com")
        mlist = MailingList(name="list@example.com")
        email = Email(archived_date=datetime(2012, 11, 2, 12, 7, 54),
                      timezone=0,
                      message_id="msgid",
                      sender=sender,
                      date=datetime(2012, 11, 2, 12, 7, 54),
                      mailinglist=mlist,
                      subject="This is a folded\n subject",
                      in_reply_to="<msg1.example.com>\n <msg2.example.com>",
                      content="Dummy message")
        msg = email.as_message()
        self.assertEqual(msg["Subject"], "This is a folded subject")

    def test_as_message_specials_in_name(self):
        sender = Sender(address="dummy@example.com")
        mlist = MailingList(name="list@example.com")
        email = Email(archived_date=datetime(2012, 11, 2, 12, 7, 54),
                      timezone=0,
                      message_id="msgid",
                      sender=sender,
                      sender_name="Team: J.Q. Doe",
                      date=datetime(2012, 11, 2, 12, 7, 54),
                      mailinglist=mlist,
                      subject="Message subject",
                      content="Dummy message")
        msg = email.as_message()
        self.assertEqual(msg['from'], '"Team: J.Q. Doe" <dummy@example.com>')


class EmailSetParentTestCase(TestCase):

    def test_simple(self):
        email1, email2 = _create_tree(["msg1", "msg2"])
        email2.set_parent(email1)
        self.assertEqual(email2.parent_id, email1.id)
        self.assertEqual(email2.thread_id, email1.thread_id)
        self.assertEqual(Thread.objects.count(), 1)
        thread = Thread.objects.first()
        self.assertEqual(thread.id, email1.thread_id)
        self.assertEqual(thread.emails.count(), 2)
        self.assertEqual(
            list(thread.emails.order_by(
                "thread_order").values_list("message_id", flat=True)),
            ["msg1", "msg2"])
        self.assertEqual(thread.date_active, email2.date)

    def test_subthread(self):
        tree = ["msg1", "msg2", "msg2.1", "msg2.1.1", "msg2.1.1.1", "msg2.2"]
        emails = _create_tree(tree)
        email1 = emails[0]
        email2 = emails[1]
        self.assertEqual(email2.thread.emails.count(), len(tree) - 1)
        email2.set_parent(email1)
        self.assertEqual(email2.parent_id, email1.id)
        self.assertEqual(email2.thread_id, email1.thread_id)
        self.assertEqual(Thread.objects.count(), 1)
        thread = Thread.objects.first()
        self.assertEqual(thread.id, email1.thread_id)
        self.assertEqual(thread.emails.count(), len(tree))
        for msgid in tree:
            email = Email.objects.get(message_id=msgid)
            self.assertEqual(email.thread_id, email1.thread_id)
        self.assertEqual(
            tree, list(thread.emails.order_by(
                "thread_order").values_list("message_id", flat=True)))

    def test_switch(self):
        email1, email2 = _create_tree(["msg1", "msg1.1"])
        email1.set_parent(email2)
        self.assertEqual(email1.parent, email2)
        self.assertEqual(email2.parent, None)

    def test_attach_to_child(self):
        emails = _create_tree(["msg1", "msg1.1", "msg1.1.1", "msg1.1.2"])
        emails[1].set_parent(emails[2])
        self.assertEqual(emails[2].parent_id, emails[0].id)
        self.assertEqual(list(emails[0].thread.emails.order_by(
            "thread_order").values_list("message_id", flat=True)),
            ["msg1", "msg1.1.1", "msg1.1", "msg1.1.2"])

    def test_attach_to_grandchild(self):
        emails = _create_tree(
            ["msg1", "msg1.1", "msg1.1.1", "msg1.1.2", "msg1.1.1.1"])
        emails[1].set_parent(emails[-1])
        self.assertEqual(emails[-1].parent_id, emails[0].id)
        self.assertEqual(list(emails[0].thread.emails.order_by(
            "thread_order").values_list("message_id", flat=True)),
            ["msg1", "msg1.1.1.1", "msg1.1", "msg1.1.1", "msg1.1.2"])

    def test_attach_to_itself(self):
        email1 = _create_tree(["msg1"])[0]
        self.assertRaises(ValueError, email1.set_parent, email1)


class EmailDeleteTestCase(TestCase):

    def test_middle_tree(self):
        email1, email2, email3 = _create_tree(["msg1", "msg1.1", "msg1.1.1"])
        email2.delete()
        email3.refresh_from_db()
        self.assertEqual(email3.parent_id, email1.id)
