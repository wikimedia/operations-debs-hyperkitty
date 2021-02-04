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

import re

from django.core.validators import RegexValidator
from django.db import models
from django.forms import TextInput


# Max length of a color's hex code is 7, which includes a preceding '#'.
MAX_COLOR_LENGTH = 7
# Regex to validate colors which are HEX of length 6, preceded by a '#' sign.
color_re = re.compile('^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')
# Custom validator for HEX color.
validate_color = RegexValidator(
    regex=color_re,
    # Error message used if the validation fails.
    message='Enter a valid hex color.',
    # Error code used if validation fails.
    code='invalid')


class ColorInput(TextInput):
    """Form widget to use for a color input."""
    input_type = 'color'


class ColorField(models.CharField):

    default_validators = [validate_color]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = MAX_COLOR_LENGTH
        super(ColorField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs['widget'] = ColorInput
        return super(ColorField, self).formfield(**kwargs)


class ThreadCategory(models.Model):
    name = models.CharField(max_length=255, db_index=True, unique=True)
    color = ColorField()

    class Meta:
        verbose_name_plural = "Thread categories"

    def __str__(self):
        return 'Thread category "%s"' % self.name
