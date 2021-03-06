# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2019 by the Free Software Foundation, Inc.
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

import json

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django_mailman3.lib.paginator import paginate
from django_mailman3.lib.mailman import get_subscriptions

from hyperkitty.models import MailingList, ArchivePolicy


def index(request):
    mlists = MailingList.objects.all()
    sort_mode = request.GET.get("sort", "popular")

    # Domain filtering
    if settings.FILTER_VHOST:
        domain = request.get_host().split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        domain = "@%s" % domain
        mlists = mlists.filter(name__iendswith=domain)

    # Name filtering
    name_filter = request.GET.get('name')
    if name_filter:
        sort_mode = "name"
        mlists = mlists.filter(
            Q(name__icontains=name_filter) |
            Q(display_name__icontains=name_filter)
            )
        if mlists.count() == 1:
            return redirect(
                'hk_list_overview', mlist_fqdn=mlists.first().name)

    # Access Filtering
    if request.user.is_superuser:
        # Superusers see everything
        pass
    elif request.user.is_authenticated:
        # For authenticated users show only their subscriptions
        # and public lists
        mlists = mlists.filter(
            Q(list_id__in=get_subscriptions(request.user)) |
            Q(archive_policy=ArchivePolicy.public.value)
        )
    else:
        # Unauthenticated users only see public lists
        mlists = mlists.filter(
            archive_policy=ArchivePolicy.public.value)

    # Sorting
    if sort_mode == "name":
        mlists = mlists.order_by("name")
    elif sort_mode == "active":
        mlists = list(mlists)
        mlists.sort(key=lambda l: l.recent_threads_count, reverse=True)
    elif sort_mode == "popular":
        mlists = list(mlists)
        mlists.sort(key=lambda l: l.recent_participants_count, reverse=True)
    elif sort_mode == "creation":
        mlists = mlists.order_by("-created_at")
    else:
        return HttpResponse("Wrong search parameter",
                            content_type="text/plain", status=500)

    mlists = paginate(mlists, request.GET.get('page'),
                      request.GET.get('count'))

    context = {
        'view_name': 'all_lists',
        'all_lists': mlists,
        'sort_mode': sort_mode,
        }
    return render(request, "hyperkitty/index.html", context)


def find_list(request):
    term = request.GET.get('term')
    result = []
    if term:
        query = MailingList.objects.filter(
            Q(name__icontains=term) | Q(display_name__icontains=term)
            ).order_by("name").values("name", "display_name")
        for line in query[:20]:
            result.append({
                "value": line["name"],
                "label": line["display_name"] or line["name"],
            })
    return HttpResponse(
        json.dumps(result), content_type='application/javascript')
