# -*- coding: utf-8 -*-
# Copyright (C) 2015-2017 by the Free Software Foundation, Inc.
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
from django.conf import settings
from django.core.checks import Error, register


@register()
def config_check(app_configs, **kwargs):
    if app_configs is not None and 'hyperkitty' not in [
            c.name for c in app_configs]:
        return []
    attachment_folder = getattr(
        settings, "HYPERKITTY_ATTACHMENT_FOLDER", None)
    errors = []
    if attachment_folder is not None:
        if not os.path.exists(attachment_folder):
            errors.append(
                Error(
                    'HyperKitty\'s attachment folder does not exist',
                    hint=('The folder set in the config variable '
                          'HYPERKITTY_ATTACHMENT_FOLDER does not exist yet '
                          '({!r}). You must create it and make sure the '
                          'webserver has the permissions to write there.'
                          ).format(attachment_folder),
                    id='hyperkitty.E001',
                )
            )
        else:
            try:
                filepath = os.path.join(attachment_folder, "_check")
                with open(filepath, "w") as f:
                    f.write("check")
                os.remove(filepath)
            except OSError as e:
                errors.append(
                    Error(
                        'Could not write to HyperKitty\'s attachment folder',
                        hint='The folder set in the config variable '
                             'HYPERKITTY_ATTACHMENT_FOLDER cannot be '
                             'written to. Make sure the webserver has '
                             'the permissions to write there.',
                        id='hyperkitty.E002',
                    )
                )
    return errors
