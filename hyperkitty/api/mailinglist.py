# -*- coding: utf-8 -*-
# Copyright (C) 2012-2017 by the Free Software Foundation, Inc.
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

from rest_framework import serializers, generics

from hyperkitty.models import MailingList, ArchivePolicy
from .utils import EnumField, IsMailingListPublicOrIsMember


class MailingListSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='hk_api_mailinglist_detail', lookup_field="name",
        lookup_url_kwarg="mlist_fqdn")
    threads = serializers.HyperlinkedIdentityField(
        view_name='hk_api_thread_list', lookup_field="name",
        lookup_url_kwarg="mlist_fqdn")
    emails = serializers.HyperlinkedIdentityField(
        view_name='hk_api_email_list', lookup_field="name",
        lookup_url_kwarg="mlist_fqdn")
    archive_policy = EnumField(enum=ArchivePolicy)

    class Meta:
        model = MailingList
        fields = (
            "url", "name", "display_name", "description", "subject_prefix",
            "archive_policy", "created_at", "threads", "emails")
        lookup_field = "name"


class MailingListList(generics.ListAPIView):
    """List mailing-lists"""

    queryset = MailingList.objects.exclude(
        archive_policy=ArchivePolicy.private.value)
    ordering = ("name", )
    ordering_fields = ("name", "created_at")
    lookup_field = "name"
    serializer_class = MailingListSerializer


class MailingListDetail(generics.RetrieveAPIView):
    """Show a mailing-list"""

    queryset = MailingList.objects.all()
    lookup_field = "name"
    lookup_url_kwarg = "mlist_fqdn"
    serializer_class = MailingListSerializer
    permission_classes = [IsMailingListPublicOrIsMember]
