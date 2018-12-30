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
from hyperkitty.models import Tag
from .utils import MLChildHyperlinkedRelatedField


class TagSerializer(serializers.HyperlinkedModelSerializer):

    threads = MLChildHyperlinkedRelatedField(
        view_name='hk_api_thread_detail', many=True, read_only=True,
        lookup_field="thread_id")
    users = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field='username')

    class Meta:
        model = Tag
        fields = ("name", "threads", "users")
        lookup_field = "name"


class TagList(generics.ListAPIView):
    """List tags"""

    queryset = Tag.objects.all()
    lookup_field = "name"
    serializer_class = TagSerializer
