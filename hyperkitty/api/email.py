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

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from rest_framework import serializers, generics

from hyperkitty.models import Email, ArchivePolicy, MailingList
from hyperkitty.lib.view_helpers import is_mlist_authorized
from .attachment import AttachmentSerializer
from .sender import SenderSerializer
from .utils import (
    MLChildHyperlinkedRelatedField,
    IsMailingListPublicOrIsMember,
    )


class EmailShortSerializer(serializers.HyperlinkedModelSerializer):
    url = MLChildHyperlinkedRelatedField(
        view_name='hk_api_email_detail', read_only=True,
        lookup_field="message_id_hash", source="*")
    mailinglist = serializers.HyperlinkedRelatedField(
        view_name='hk_api_mailinglist_detail', read_only=True,
        lookup_field="name", lookup_url_kwarg="mlist_fqdn")
    thread = MLChildHyperlinkedRelatedField(
        view_name='hk_api_thread_detail', read_only=True,
        lookup_field="thread_id")
    parent = MLChildHyperlinkedRelatedField(
        view_name='hk_api_email_detail', read_only=True,
        lookup_field="message_id_hash")
    children = MLChildHyperlinkedRelatedField(
        view_name='hk_api_email_detail', read_only=True,
        lookup_field="message_id_hash", many=True)
    sender = SenderSerializer()

    class Meta:
        model = Email
        fields = ("url", "mailinglist", "message_id", "message_id_hash",
                  "thread", "sender", "sender_name", "subject", "date",
                  "parent", "children",
                  )


class EmailSerializer(EmailShortSerializer):
    votes = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Email
        fields = EmailShortSerializer.Meta.fields + (
            "votes", "content", "attachments")

    def get_votes(self, obj):
        return obj.get_votes()


class EmailList(generics.ListAPIView):
    """List emails"""

    serializer_class = EmailShortSerializer
    ordering_fields = ("archived_date", "thread_order", "date")

    def get_queryset(self):
        mlist = MailingList.objects.get(name=self.kwargs["mlist_fqdn"])
        if not is_mlist_authorized(self.request, mlist):
            raise PermissionDenied
        query = Email.objects.filter(
                mailinglist__name=self.kwargs["mlist_fqdn"])
        if "thread_id" in self.kwargs:
            query = query.filter(
                    thread__thread_id=self.kwargs["thread_id"]
                ).order_by("thread_order")
        else:
            query = query.order_by("-archived_date")
        return query


class EmailListBySender(generics.ListAPIView):
    """List emails by sender"""

    serializer_class = EmailShortSerializer

    def get_queryset(self):
        key = self.kwargs["mailman_id"]
        query = Email.objects.exclude(
            mailinglist__archive_policy=ArchivePolicy.private.value
        )
        if "@" in key:
            query = query.filter(sender__address=key)
        else:
            query = query.filter(sender__mailman_id=key)
        return query.order_by("-archived_date")


class EmailDetail(generics.RetrieveAPIView):
    """Show an email"""

    serializer_class = EmailSerializer
    permission_classes = [IsMailingListPublicOrIsMember]

    def get_object(self):
        email = get_object_or_404(
            Email,
            mailinglist__name=self.kwargs["mlist_fqdn"],
            message_id_hash=self.kwargs["message_id_hash"],
            )
        return email
