#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021 by the Free Software Foundation, Inc.
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
import sys

from setuptools import find_packages, setup


# extract the version number without importing the package
with open('hyperkitty/__init__.py') as fp:
    for line in fp:
        mo = re.match("""VERSION\s*=\s*['"](?P<version>[^'"]+?)['"]""", line)
        if mo:
            __version__ = mo.group('version')
            break
    else:
        print('No version number found')
        sys.exit(1)


# Requirements
REQUIRES = [
    "Django>=2.2,<3.2",
    "django_mailman3>=1.3.3",
    "django-gravatar2>=1.0.6",
    "djangorestframework>=3.0.0",
    "robot-detection>=0.3",
    "pytz>=2012",
    "django-compressor>=1.3",
    "mailmanclient>=3.3.1",
    "python-dateutil >= 2.0",
    "networkx>=2.0",
    "django-haystack>=2.8.0",
    "django-extensions>=1.3.7",
    "flufl.lock>=4.0",
    "django-q>=1.0.0",
]


setup(
    name="HyperKitty",
    version=__version__,
    description="A web interface to access GNU Mailman v3 archives",
    long_description=open('README.rst').read(),
    author='HyperKitty Developers',
    author_email='hyperkitty-devel@lists.fedorahosted.org',
    url="https://gitlab.com/mailman/hyperkitty",
    license="GPLv3",
    classifiers=[
        "Framework :: Django",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: Communications :: Email :: Mailing List Servers",
        "Programming Language :: Python :: 3",
        "Programming Language :: JavaScript",
        ],
    keywords='email',
    packages=find_packages(
        exclude=["example_project"]
    ),
    include_package_data=True,
    install_requires=REQUIRES,
    setup_requires=[
        "isort",
    ],
    tests_require=[
        "mock",
        "Whoosh>=2.5.7",
        "beautifulsoup4>=4.3.2",
        "django-debug-toolbar",
        ],
    extras_require={
        'dev': [
            "Whoosh>=2.5.7",
            "django-debug-toolbar"
        ]
    })
