#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys

from setuptools import setup, find_packages


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
    "django_mailman3>=1.2.0a2",
    "django-gravatar2>=1.0.6",
    "djangorestframework>=3.0.0",
    "robot-detection>=0.3",
    "pytz>=2012",
    "django-paintstore>=0.1.2",
    "django-compressor>=1.3",
    "mailmanclient>=3.1.1",
    "python-dateutil >= 2.0",
    "networkx>=1.9.1",
    # django-haystack>=2.5.0 suffices for Django-1.11
    "django-haystack>=2.8.0",
    "django-extensions>=1.3.7",
    "lockfile>=0.9.1",
    "django-q>=1.0.0",
    "Django>=1.11,<2.2",
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
    # packages=find_packages(exclude=["*.test", "test", "*.test.*"]),
    packages=find_packages(),
    include_package_data=True,
    install_requires=REQUIRES,
    tests_require=[
        "mock",
        "Whoosh>=2.5.7",
        "beautifulsoup4>=4.3.2",
        ],
    )
