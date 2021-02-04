# -*- coding: utf-8 -*-
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

from rest_framework import permissions, serializers

from hyperkitty.lib.view_helpers import is_mlist_authorized
from hyperkitty.models import MailingList


class MLChildHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):

    def get_url(self, obj, view_name, request, format):
        lookup_value = getattr(obj, self.lookup_field)
        kwargs = {self.lookup_url_kwarg: lookup_value,
                  "mlist_fqdn": obj.mailinglist.name}
        return self.reverse(view_name, kwargs=kwargs, request=request,
                            format=format)

    def get_object(self, view_name, view_args, view_kwargs):
        lookup_value = view_kwargs[self.lookup_url_kwarg]
        lookup_kwargs = {self.lookup_field: lookup_value,
                         "mailinglist__name": view_kwargs["mlist_fqdn"]}
        return self.get_queryset().get(**lookup_kwargs)


class EnumField(serializers.IntegerField):

    def __init__(self, **kwargs):
        self.enum = kwargs.pop("enum", None)
        super(EnumField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, int):
            try:
                data = self.enum(data)
            except ValueError:
                self.fail("invalid")
        else:
            try:
                data = getattr(self.enum, data)
            except AttributeError:
                self.fail("invalid")
        return data.value

    def to_representation(self, value):
        return self.enum(value).name


class IsMailingListPublicOrIsMember(permissions.BasePermission):
    """
    Custom permission to only allow access to public lists or to lists the
    authenticated user is a member of.
    """

    def _get_mlist(self, obj):
        if isinstance(obj, MailingList):
            return obj
        if hasattr(obj, "mailinglist"):
            return obj.mailinglist

    def has_object_permission(self, request, view, obj):
        mlist = self._get_mlist(obj)
        if mlist is None:
            # This is not a object linked to a mailing-list.
            return True
        return is_mlist_authorized(request, mlist)
