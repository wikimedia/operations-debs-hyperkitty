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

import logging
import os
import shutil
import tempfile
from unittest import SkipTest

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.migrations import RunPython, RunSQL
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase as DjangoTestCase
from django.test import TransactionTestCase

import mailmanclient
from mock import Mock, patch


def setup_logging(tmpdir):
    formatter = logging.Formatter(fmt="%(message)s")
    levels = ["debug", "info", "warning", "error"]
    handlers = []
    for level_name in levels:
        log_path = os.path.join(tmpdir, "%s.log" % level_name)
        handler = logging.FileHandler(log_path)
        handler.setLevel(getattr(logging, level_name.upper()))
        handler.setFormatter(formatter)
        handlers.append(handler)
    for logger_name in ["django", "hyperkitty"]:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)
        for handler in handlers:
            logger.addHandler(handler)


class TestCase(DjangoTestCase):

    # Testcase classes can use this variable to add more overrides:
    override_settings = {}

    def _pre_setup(self):
        super(TestCase, self)._pre_setup()
        self.tmpdir = tempfile.mkdtemp(prefix="hyperkitty-testing-")
        # Logging
        setup_logging(self.tmpdir)
        # Override settings
        self._old_settings = {}
        self._override_setting(
            "STATIC_ROOT", os.path.join(self.tmpdir, "static"))
        override_settings = self.override_settings.copy()
        for key, value in override_settings.items():
            self._override_setting(key, value)
        self.mailman_client = Mock()
        self.mailman_client.get_user.side_effect = \
            mailmanclient.MailmanConnectionError()
        self.mailman_client.get_list.side_effect = \
            mailmanclient.MailmanConnectionError()
        self._mm_client_patcher = patch(
            "django_mailman3.lib.mailman.MailmanClient",
            lambda *a: self.mailman_client)
        self._mm_client_patcher.start()

    def _override_setting(self, key, value):
        self._old_settings[key] = getattr(settings, key, None)
        setattr(settings, key, value)

    def _post_teardown(self):
        self._mm_client_patcher.stop()
        cache.clear()
        for key, value in self._old_settings.items():
            if value is None:
                delattr(settings, key)
            else:
                setattr(settings, key, value)
        shutil.rmtree(self.tmpdir)
        super(TestCase, self)._post_teardown()


class SearchEnabledTestCase(TestCase):

    def _pre_setup(self):
        try:
            import whoosh  # noqa: F401
        except ImportError:
            raise SkipTest("The Whoosh library is not available")
        super(SearchEnabledTestCase, self)._pre_setup()
        call_command('clear_index', verbosity=0, interactive=False)
        call_command('update_index', verbosity=0)

    def _post_teardown(self):
        super(SearchEnabledTestCase, self)._post_teardown()


class MigrationTestCase(TransactionTestCase):
    """ Inpired by
https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations
    """

    migrate_from = None
    migrate_to = None

    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    def _pre_setup(self):
        super(MigrationTestCase, self)._pre_setup()
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties"\
            .format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        self.executor = MigrationExecutor(connection)
        self.old_apps = \
            self.executor.loader.project_state(self.migrate_from).apps
        # Make non-reversible operations reversible.
        for migration, _backwards in \
                self.executor.migration_plan(self.migrate_from):
            for operation in migration.operations:
                if not operation.reversible:
                    if isinstance(operation, RunPython):
                        operation.reverse_code = lambda *a: None
                    if isinstance(operation, RunSQL):
                        operation.reverse_sql = []
        # Reverse to the original migration.
        self.executor.migrate(self.migrate_from)

    def migrate(self):
        """Run the migration to test and return the new apps."""
        # Either reset the migration graph, or use a new instance of
        # MigrationExecutor.
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        return self.executor.loader.project_state(self.migrate_to).apps


def get_test_file(*fileparts):
    return os.path.join(os.path.dirname(__file__), "testdata", *fileparts)


get_test_file.__test__ = False
