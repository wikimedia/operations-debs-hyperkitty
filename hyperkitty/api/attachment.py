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

try:
    from django.core.urlresolvers import reverse
except ImportError:
    # For Django 2.0+
    from django.urls import reverse
from rest_framework import serializers

from hyperkitty.models import Attachment
from .utils import MLChildHyperlinkedRelatedField


class AttachmentSerializer(serializers.HyperlinkedModelSerializer):
    email = MLChildHyperlinkedRelatedField(
        view_name='hk_api_email_detail', read_only=True,
        lookup_field="message_id_hash")
    download = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "email", "counter", "name", "content_type", "encoding",
            "size", "download",
        )

    def get_download(self, obj):
        relative_url = reverse(
            "hk_message_attachment", kwargs=dict(
                mlist_fqdn=obj.email.mailinglist.name,
                message_id_hash=obj.email.message_id_hash,
                counter=obj.counter,
                filename=obj.name,
            )
        )
        if "request" in self.context:
            return self.context["request"].build_absolute_uri(relative_url)
        else:
            return relative_url
