# -*- coding: utf-8 -*-
#
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

import datetime
import gzip
import mailbox
import os
import tempfile
from io import StringIO

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from hyperkitty.lib.compat import get_list_by_name, month_name_to_num
from hyperkitty.models import Email, MailingList


def summary(request, list_name=None):
    if list_name is None:
        return redirect(reverse('hk_root'))
    mlist = get_list_by_name(list_name, request.get_host())
    return redirect(reverse('hk_list_overview',
                            kwargs={'mlist_fqdn': mlist.name}))


def arch_month(request, list_name, year, month_name, summary_type="thread"):
    mlist = get_list_by_name(list_name, request.get_host())
    return redirect(reverse('hk_archives_with_month', kwargs={
        'mlist_fqdn': mlist.name,
        'year': year,
        'month': str(month_name_to_num(month_name)).rjust(2, "0"),
        }))


def arch_month_mbox(request, list_name, year, month_name):
    """
    The messages must be rebuilt before being added to the mbox file, including
    headers and the textual content, making sure to escape email addresses.
    """
    return HttpResponse("Not implemented yet.",
                        content_type="text/plain", status=500)
    mlist = get_list_by_name(list_name, request.get_host())
    month = month_name_to_num(month_name)
    year = int(year)
    begin_date = datetime.datetime(year, month, 1)
    if month != 12:
        end_month = month + 1
    else:
        end_month = 1
    end_date = datetime.datetime(year, end_month, 1)
    messages = Email.objects.filter(
        mailinglist=mlist, date__gte=begin_date, date__lte=end_date
        ).order_by("date")
    mboxfile, mboxfilepath = tempfile.mkstemp(
        prefix="hyperkitty-", suffix=".mbox.gz")
    os.close(mboxfile)
    mbox = mailbox.mbox(mboxfilepath)
    for msg in messages:
        mbox.add(msg.full)
    mbox.close()
    content = StringIO()
    zipped_content = gzip.GzipFile(fileobj=content)
    with gzip.GzipFile(fileobj=content, mode="wb") as zipped_content:
        with open(mboxfilepath, "rb") as mboxfile:
            zipped_content.write(mboxfile.read())
    response = HttpResponse(content.getvalue())
    content.close()
    response['Content-Type'] = "application/mbox+gz"
    response['Content-Disposition'] = 'attachment; filename=%d-%s.txt.gz' \
        % (year, month_name)
    response['Content-Length'] = len(response.content)
    os.remove(mboxfilepath)
    return response


def message(request, list_name, year, month_name, msg_num):
    mlist = get_list_by_name(list_name, request.get_host())
    msg_num = int(msg_num) - 1  # pipermail starts at 1, not 0
    if msg_num < 0:
        raise Http404("No such message in this mailing-list.")
    try:
        msg = Email.objects.filter(
            mailinglist=mlist).order_by("archived_date")[msg_num]
    except IndexError:
        raise Http404("No such message in this mailing-list.")
    return redirect(reverse('hk_message_index', kwargs={
        'mlist_fqdn': mlist.name,
        'message_id_hash': msg.message_id_hash,
        }))


def redirect_list_id(request, list_id):
    mlist = get_object_or_404(MailingList, list_id=list_id)
    url = request.path.replace(list_id, mlist.name, 1)
    if request.GET:
        url = "%s?%s" % (url, request.GET.urlencode())
    return redirect(url)


def redirect_lists(request):
    url = request.path.replace("/lists/", "/list/", 1)
    if request.GET:
        url = "%s?%s" % (url, request.GET.urlencode())
    return redirect(url)
