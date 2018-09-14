# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 by the Free Software Foundation, Inc.
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

from django.contrib import admin
from hyperkitty import models


admin.site.register(models.profile.Profile)
admin.site.register(models.tag.Tag)
admin.site.register(models.vote.Vote)
admin.site.register(models.thread.LastView)
admin.site.register(models.favorite.Favorite)
admin.site.register(models.mailinglist.MailingList)


@admin.register(models.category.ThreadCategory)
class ThreadCategoryAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.name = obj.name.lower()
        return super(ThreadCategoryAdmin, self).save_model(
                     request, obj, form, change)
