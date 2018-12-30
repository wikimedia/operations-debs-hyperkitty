# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 by the Free Software Foundation, Inc.
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
from django.db import models


class Vote(models.Model):
    """
    A User's vote on a message
    """
    email = models.ForeignKey(
        "Email", related_name="votes", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             related_name="votes", on_delete=models.CASCADE)
    value = models.SmallIntegerField(db_index=True)

    class Meta:
        unique_together = ("email", "user")

    def on_post_save(self):
        self.email.on_vote_added(self)
        self.email.thread.on_vote_added(self)
        self.email.mailinglist.on_vote_added(self)

    def on_post_delete(self):
        self.email.on_vote_deleted(self)
        self.email.thread.on_vote_deleted(self)
        self.email.mailinglist.on_vote_deleted(self)
