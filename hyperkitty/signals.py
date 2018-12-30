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

from django.conf import settings
from django.db.models.signals import (
    post_init, pre_save, post_save, pre_delete, post_delete)
from django.dispatch import receiver
from django_mailman3.signals import mailinglist_created, mailinglist_modified

from hyperkitty.lib.mailman import import_list_from_mailman
from hyperkitty.models.email import Email, Attachment
from hyperkitty.models.mailinglist import MailingList
from hyperkitty.models.profile import Profile
from hyperkitty.models.thread import Thread
from hyperkitty.models.vote import Vote


# Email

@receiver(post_init, sender=Email)
def Email_on_post_init(sender, **kwargs):
    kwargs["instance"].on_post_init()


@receiver(pre_save, sender=Email)
def Email_on_pre_save(sender, **kwargs):
    kwargs["instance"].on_pre_save()


@receiver(post_save, sender=Email)
def Email_on_post_save(sender, **kwargs):
    if kwargs["created"]:
        kwargs["instance"].on_post_created()
    else:
        kwargs["instance"].on_post_save()


@receiver(pre_delete, sender=Email)
def Email_on_pre_delete(sender, **kwargs):
    kwargs["instance"].on_pre_delete()


@receiver(post_delete, sender=Email)
def Email_on_post_delete(sender, **kwargs):
    kwargs["instance"].on_post_delete()


# Attachment

@receiver(pre_save, sender=Attachment)
def Attachment_on_pre_save(sender, **kwargs):
    kwargs["instance"].on_pre_save()


# MailingList

@receiver(pre_save, sender=MailingList)
def MailingList_set_list_id(sender, **kwargs):
    kwargs["instance"].on_pre_save()


# Profile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def Profile_on_post_save(sender, **kwargs):
    user = kwargs["instance"]
    if not Profile.objects.filter(user=user).exists():
        Profile.objects.create(user=user)


# Thread

@receiver(pre_save, sender=Thread)
def Thread_on_pre_save(sender, **kwargs):
    kwargs["instance"].on_pre_save()


@receiver(post_save, sender=Thread)
def Thread_on_post_save(sender, **kwargs):
    if kwargs["created"]:
        kwargs["instance"].on_post_created()
    else:
        kwargs["instance"].on_post_save()


@receiver(post_delete, sender=Thread)
def Thread_on_post_delete(sender, **kwargs):
    kwargs["instance"].on_post_delete()


# Vote

@receiver(post_save, sender=Vote)
def Vote_on_post_save(sender, **kwargs):
    kwargs["instance"].on_post_save()


@receiver(post_delete, sender=Vote)
def Vote_on_post_delete(sender, **kwargs):
    kwargs["instance"].on_post_delete()


# Mailman signals

@receiver(mailinglist_created)
def on_mailinglist_created(sender, **kwargs):
    import_list_from_mailman(kwargs["list_id"])


@receiver(mailinglist_modified)
def on_mailinglist_modified(sender, **kwargs):
    import_list_from_mailman(kwargs["list_id"])
