# -*- coding: utf-8 -*-

import mailbox
import os.path
import sys
from datetime import datetime
from email import message_from_file
from email.message import EmailMessage
from io import StringIO
from traceback import format_exc
from unittest import SkipTest, expectedFailure

from django.conf import settings
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS
from django.utils.timezone import utc

from mock import Mock, patch

from hyperkitty.lib.incoming import add_to_list
from hyperkitty.management.commands.hyperkitty_import import Command
from hyperkitty.models import Email, MailingList
from hyperkitty.tests.utils import TestCase, get_test_file


class CommandTestCase(TestCase):

    def setUp(self):
        self.command = Command()
        self.common_cmd_args = dict(
            verbosity=2, list_address="list@example.com",
            since=None, no_sync_mailman=True, ignore_mtime=False,
        )

    def tearDown(self):
        settings.HYPERKITTY_BATCH_MODE = False

    def test_impacted_threads(self):
        # existing message
        msg1 = EmailMessage()
        msg1["From"] = "dummy@example.com"
        msg1["Message-ID"] = "<msg1>"
        msg1["Date"] = "01 Jan 2015 12:00:00"
        msg1.set_payload("msg1")
        add_to_list("list@example.com", msg1)
        # new message in the imported mbox
        msg2 = EmailMessage()
        msg2["From"] = "dummy@example.com"
        msg2["Message-ID"] = "<msg2>"
        msg2["Date"] = "01 Feb 2015 12:00:00"
        msg2.set_payload("msg2")
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg2)
        mbox.close()
        # do the import
        output = StringIO()
        with patch("hyperkitty.management.commands.hyperkitty_import"
                   ".compute_thread_order_and_depth") as mock_compute:
            kw = self.common_cmd_args.copy()
            kw["stdout"] = kw["stderr"] = output
            call_command('hyperkitty_import',
                         os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(mock_compute.call_count, 1)
        thread = mock_compute.call_args[0][0]
        self.assertEqual(thread.emails.count(), 1)
        self.assertEqual(thread.starting_email.message_id, "msg2")

    def test_since_auto(self):
        # When there's mail already and the "since" option is not used, it
        # defaults to the last email's date
        msg1 = EmailMessage()
        msg1["From"] = "dummy@example.com"
        msg1["Message-ID"] = "<msg1>"
        msg1["Date"] = "01 Jan 2015 12:00:00"
        msg1.set_payload("msg1")
        add_to_list("list@example.com", msg1)
        mailbox.mbox(os.path.join(self.tmpdir, "test.mbox")).close()
        # do the import
        output = StringIO()
        with patch("hyperkitty.management.commands.hyperkitty_import"
                   ".DbImporter") as DbImporterMock:
            instance = Mock()
            instance.impacted_thread_ids = []
            DbImporterMock.side_effect = lambda *a, **kw: instance
            kw = self.common_cmd_args.copy()
            kw["stdout"] = kw["stderr"] = output
            call_command('hyperkitty_import',
                         os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(DbImporterMock.call_args[0][1]["since"],
                         datetime(2015, 1, 1, 12, 0, tzinfo=utc))

    def test_since_override(self):
        # The "since" option is used
        msg1 = EmailMessage()
        msg1["From"] = "dummy@example.com"
        msg1["Message-ID"] = "<msg1>"
        msg1["Date"] = "01 Jan 2015 12:00:00"
        msg1.set_payload("msg1")
        add_to_list("list@example.com", msg1)
        mailbox.mbox(os.path.join(self.tmpdir, "test.mbox")).close()
        # do the import
        output = StringIO()
        with patch("hyperkitty.management.commands.hyperkitty_import"
                   ".DbImporter") as DbImporterMock:
            instance = Mock()
            instance.impacted_thread_ids = []
            DbImporterMock.side_effect = lambda *a, **kw: instance
            kw = self.common_cmd_args.copy()
            kw["stdout"] = kw["stderr"] = output
            kw["since"] = "2010-01-01 00:00:00 UTC"
            call_command('hyperkitty_import',
                         os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(DbImporterMock.call_args[0][1]["since"],
                         datetime(2010, 1, 1, tzinfo=utc))

    def test_lowercase_list_name(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg1>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg1")
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        kw["list_address"] = "LIST@example.com"
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(MailingList.objects.count(), 1)
        ml = MailingList.objects.first()
        self.assertEqual(ml.name, "list@example.com")

    def test_missing_message_id(self):
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg1")
        msg2 = EmailMessage()
        msg2["From"] = "dummy@example.com"
        msg2["Date"] = "01 Feb 2015 12:00:00"
        msg2.set_payload("msg2")
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.add(msg2)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Both messages should be archived.
        self.assertEqual(Email.objects.count(), 2)

    def test_wrong_encoding(self):
        """badly encoded message, only fails on PostgreSQL"""
        db_engine = settings.DATABASES[DEFAULT_DB_ALIAS]["ENGINE"]
        if db_engine == "django.db.backends.sqlite3":
            raise SkipTest  # SQLite will accept anything
        with open(get_test_file("payload-utf8-wrong.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # Second message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg1>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg1")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Message wrong.encoding failed to import, skipping",
                      output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_ungettable_date(self):
        # Certain bad Date: headers will throw TypeError on msg.get('date').
        # Test that we handle that.
        # For this test we use the testdata mbox directly to avoid a parse
        # error in message_from_file().
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        kw["verbosity"] = 2
        call_command('hyperkitty_import',
                     get_test_file("non-ascii-date-header.txt"), **kw)
        # The message should be archived.
        self.assertEqual(Email.objects.count(), 1)
        # But there should be an error message.
        self.assertIn("Can't get date header in message", output.getvalue())

    def test_no_date_but_resent_date(self):
        # If there's no Dete: header, fall back to Resent-Date:.
        with open(get_test_file("resent-date.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # The message should be archived.
        self.assertEqual(Email.objects.count(), 1)
        # The archived_date should be 8 Nov 1999 20:53:05 -0600 which is
        # 9 Nov 1999 02:53:05 UTC.
        self.assertEqual(Email.objects.all()[0].date,
                         datetime(1999, 11, 9, 2, 53, 5, tzinfo=utc))

    def test_no_date_and_no_resent_date(self):
        # If there's no Dete: header and no Resent-Date: header, fall back
        # to the unixfrom date.
        with open(get_test_file("unixfrom-date.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # The message should be archived.
        self.assertEqual(Email.objects.count(), 1)
        # The archived_date should be Nov  9 21:54:11 1999
        self.assertEqual(Email.objects.all()[0].date,
                         datetime(1999, 11, 9, 21, 54, 11, tzinfo=utc))

    def test_bad_date_tz_and_no_resent_date(self):
        # If the Dete: header is bad and no Resent-Date: header, fall back
        # to the unixfrom date.
        with open(get_test_file("bad_date_tz.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # The message should be archived.
        self.assertEqual(Email.objects.count(), 1)
        # The archived_date should be Dec  1 00:56:19 1999 1999
        self.assertEqual(Email.objects.all()[0].date,
                         datetime(1999, 12, 1, 0, 56, 19, tzinfo=utc))

    def test_folding_with_cr(self):
        # See https://gitlab.com/mailman/hyperkitty/-/issues/280 for the
        # issue.
        with open(get_test_file("bad_folding.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # The message should be archived.
        self.assertEqual(Email.objects.count(), 1)
        # The subject should be ???
        self.assertEqual(Email.objects.all()[0].subject,
                         '[<redacted>]  Sicherheit 2005: Stichworte und '
                         'Vorschlag PC-Mitglieder; Ergänzung!')

    def test_bad_subject_header(self):
        # This message has a Subject: header with an encoded word that
        # contains \x85 which becomes a unicode next line.
        with open(get_test_file("bad-subject-header.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)
        self.assertEqual(Email.objects.first().subject,
                         '(et en plus, en local\x85)')

    def test_cant_write_error(self):
        # This message throws an exception which is caught by the catchall
        # except clause. Ensure we can then write the error message.
        with open(get_test_file("cant_write_error_message.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # Add a scond message because we need to archive something.
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg2")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("failed to import, skipping",
                      output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_unconvertable_message(self):
        # This message can't be converted to an email.message.EmailMessage.
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        # We have to do it this way to see the exception.
        with open(get_test_file("unconvertable_message.txt"), "rb") as em_file:
            with open(os.path.join(self.tmpdir, "test.mbox"), "wb") as mb_file:
                mb_file.write(em_file.read())
        # Add a scond message because we need to archive something.
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg2")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed to convert", output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_another_unconvertable_message(self):
        # This message can't be converted to an email.message.EmailMessage.
        # This fails with Python>=3.7.5 because
        # https://bugs.python.org/issue37491 is fixed.
        if sys.hexversion >= 0x30705f0:
            raise SkipTest
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        # We have to do it this way to see the exception.
        with open(get_test_file("unconvertable_msg-2.txt"), "rb") as em_file:
            with open(os.path.join(self.tmpdir, "test.mbox"), "wb") as mb_file:
                mb_file.write(em_file.read())
        # Add a scond message because we need to archive something.
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg2")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed to convert n/a to email", output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_ungetable_message(self):
        # This mbox message can't be converted to bytes.
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        # We have to do it this way to see the exception.
        with open(get_test_file("unicode_issue.txt"), "rb") as em_file:
            with open(os.path.join(self.tmpdir, "test.mbox"), "wb") as mb_file:
                mb_file.write(em_file.read())
        # Add a scond message because we need to archive something.
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg2")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed to convert n/a to bytes", output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_unknown_encoding(self):
        # Spam messages have been seen with bogus charset= encodings which
        # throw LookupError.
        with open(get_test_file("unknown-charset.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # Second message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg2>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg2")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed adding message <msg@id>:",
                      output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    @expectedFailure
    # This fails because the fix for #294 'fixes' this too.
    def test_another_wrong_encoding(self):
        # This is gb2312 with a bad character. It seems to fail before
        # getting to the back end.
        with open(get_test_file("another-wrong-encoding.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # Second message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg1>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg1")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed adding message <msg@id>:",
                      output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_another_wrong_encoding_part_two(self):
        # This is gb2312 with a bad character. Since above failure was fixed,
        # test current behavior.
        with open(get_test_file("another-wrong-encoding.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    @expectedFailure
    # This fails because the fix at django-mailman3!88 'fixes' this too.
    def test_bad_content_type(self):
        # Content-Type: binary/octet-stream throws KeyError.
        with open(get_test_file("bad_content_type.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # Second message
        msg = EmailMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg1>"
        msg["Date"] = "01 Feb 2015 12:00:00"
        msg.set_payload("msg1")
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message 1 must have been rejected, but no crash
        self.assertIn("Failed adding message <msg@id>:",
                      output.getvalue())
        # Message 2 must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_bad_content_type_part_two(self):
        # Content-Type: binary/octet-stream.  Since above failure was fixed,
        # test current behavior.
        with open(get_test_file("bad_content_type.txt")) as email_file:
            msg = message_from_file(email_file)
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)

    def test_weird_timezone(self):
        # An email has a timezone with a strange offset (seen in the wild).
        # Make sure it does not break our _is_old_enough() method.
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        # First message is already imported
        msg1 = EmailMessage()
        msg1["From"] = "dummy@example.com"
        msg1["Message-ID"] = "<msg1>"
        msg1["Date"] = "01 Jan 2008 12:00:00"
        msg1.set_payload("msg1")
        add_to_list("list@example.com", msg1)
        # Second message is in the mbox to import
        msg2 = EmailMessage()
        msg2["From"] = "dummy@example.com"
        msg2["Message-ID"] = "<msg2>"
        msg2["Date"] = "Sat, 30 Aug 2008 16:40:31 +05-30"
        msg2.set_payload("msg2")
        mbox.add(msg2)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        try:
            call_command('hyperkitty_import',
                         os.path.join(self.tmpdir, "test.mbox"), **kw)
        except ValueError as e:
            self.fail(format_exc(e))
        # Message must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 2)

    def test_unixfrom(self):
        # Make sure the UNIX From line is forwarded to the incoming function.
        msg = mailbox.mboxMessage()
        msg["From"] = "dummy@example.com"
        msg["Message-ID"] = "<msg1>"
        msg["Date"] = "01 Jan 2008 12:00:00"
        msg.set_payload("msg1")
        msg.set_from("dummy@example.com Mon Jul 21 11:44:51 2008")
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        kw = self.common_cmd_args.copy()
        kw["stdout"] = kw["stderr"] = output
        call_command('hyperkitty_import',
                     os.path.join(self.tmpdir, "test.mbox"), **kw)
        # Message must have been accepted
        self.assertEqual(MailingList.objects.count(), 1)
        self.assertEqual(Email.objects.count(), 1)
        email = Email.objects.first()
        self.assertEqual(
            email.archived_date,
            datetime(2008, 7, 21, 11, 44, 51, tzinfo=utc))

    def test_impacted_threads_batch(self):
        # Fix GL issue #86
        mbox = mailbox.mbox(os.path.join(self.tmpdir, "test.mbox"))
        for i in range(250):
            msg = EmailMessage()
            msg["From"] = "dummy@example.com"
            msg["Message-ID"] = "<msg%d>" % i
            msg["Date"] = "01 Jan 2015 12:00:00"
            msg.set_payload("msg%d" % i)
            mbox.add(msg)
        mbox.close()
        # do the import
        output = StringIO()
        with patch("hyperkitty.management.commands.hyperkitty_import"
                   ".compute_thread_order_and_depth") as mock_compute:
            kw = self.common_cmd_args.copy()
            kw["stdout"] = kw["stderr"] = output
            call_command('hyperkitty_import',
                         os.path.join(self.tmpdir, "test.mbox"), **kw)
        called_thread_ids = set([
            call[0][0].starting_email.message_id
            for call in mock_compute.call_args_list
            ])
        self.assertEqual(
            called_thread_ids,
            set([("msg%d" % i) for i in range(250)]))
