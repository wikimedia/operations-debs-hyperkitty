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

import datetime
import json
import zlib


from django.urls import reverse
from django.http import (
    Http404, HttpResponse, StreamingHttpResponse, HttpResponseBadRequest)
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import formats, timezone
from django.utils.dateformat import format as date_format
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django_mailman3.lib.mailman import get_mailman_user_id
from django_mailman3.lib.paginator import paginate

from hyperkitty.models import Favorite, MailingList
from hyperkitty.lib.view_helpers import (
    get_category_widget, get_months, get_display_dates, daterange,
    check_mlist_private)


@check_mlist_private
def archives(request, mlist_fqdn, year=None, month=None, day=None):
    if year is None and month is None:
        today = datetime.date.today()
        return redirect(reverse(
                'hk_archives_with_month', kwargs={
                    "mlist_fqdn": mlist_fqdn,
                    'year': today.year,
                    'month': today.month}))

    try:
        begin_date, end_date = get_display_dates(year, month, day)
    except ValueError:
        # Wrong date format, for example 9999/0/0
        raise Http404("Wrong date format")
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    threads = mlist.get_threads_between(begin_date, end_date)
    if day is None:
        list_title = date_format(begin_date, "F Y")
        no_results_text = "for this month"
    else:
        list_title = formats.date_format(begin_date)  # works with i18n
        no_results_text = "for this day"
    # Export button
    export = {
        "url": "%s?start=%s&end=%s" % (
            reverse("hk_list_export_mbox", kwargs={
                    "mlist_fqdn": mlist.name,
                    "filename": "%s-%s" % (
                        mlist.name, begin_date.strftime("%Y-%m"))}),
            begin_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")),
        "message": _("Download"),
        "title": _("This month in gzipped mbox format"),
    }
    extra_context = {
        'month': begin_date,
        'month_num': begin_date.month,
        "list_title": list_title.capitalize(),
        "no_results_text": no_results_text,
        "export": export,
    }
    if day is None:
        extra_context["participants_count"] = \
            mlist.get_participants_count_for_month(int(year), int(month))
    return _thread_list(request, mlist, threads, extra_context=extra_context)


def _thread_list(request, mlist, threads,
                 template_name='hyperkitty/thread_list.html',
                 extra_context=None):
    threads = paginate(threads, request.GET.get('page'),
                       request.GET.get('count'))
    for thread in threads:
        # Favorites
        thread.favorite = False
        if request.user.is_authenticated:
            try:
                Favorite.objects.get(thread=thread, user=request.user)
            except Favorite.DoesNotExist:
                pass
            else:
                thread.favorite = True
        # Category
        thread.category_hk, thread.category_form = \
            get_category_widget(request, thread.category)

    context = {
        'mlist': mlist,
        'threads': threads,
        'months_list': get_months(mlist),
    }
    if extra_context is not None:
        context.update(extra_context)
    return render(request, template_name, context)


@check_mlist_private
def overview(request, mlist_fqdn=None):
    if not mlist_fqdn:
        return redirect('/')
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)

    # top authors are the ones that have the most kudos.  How do we determine
    # that?  Most likes for their post?
    authors = []

    # Threads by category
    threads_by_category = {}

    # Export button
    recent_dates = [
        d.strftime("%Y-%m-%d") for d in mlist.get_recent_dates()]
    recent_url = "%s?start=%s&end=%s" % (
        reverse("hk_list_export_mbox", kwargs={
                "mlist_fqdn": mlist.name,
                "filename": "%s-%s-%s" % (
                    mlist.name, recent_dates[0], recent_dates[1])}),
        recent_dates[0], recent_dates[1])
    today = datetime.date.today()
    month_dates = get_display_dates(today.year, today.month, None)
    month_url = "%s?start=%s&end=%s" % (
        reverse("hk_list_export_mbox", kwargs={
                "mlist_fqdn": mlist.name,
                "filename": "%s-%s" % (mlist.name, today.strftime("%Y-%m"))}),
        month_dates[0].strftime("%Y-%m-%d"),
        month_dates[1].strftime("%Y-%m-%d"))
    export = {"recent": recent_url, "month": month_url}

    context = {
        'view_name': 'overview',
        'mlist': mlist,
        'top_author': authors,
        'threads_by_category': threads_by_category,
        'months_list': get_months(mlist),
        'export': export,
    }
    return render(request, "hyperkitty/overview.html", context)


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_recent_threads(request, mlist_fqdn):
    """Return the most recently updated threads."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    return render(request, "hyperkitty/fragments/overview_threads.html", {
        'mlist': mlist,
        'threads': mlist.recent_threads[:20],
        'empty': _('No discussions this month (yet).'),
        })


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_pop_threads(request, mlist_fqdn):
    """Return the threads with the most votes."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    return render(request, "hyperkitty/fragments/overview_threads.html", {
        'mlist': mlist,
        'threads': mlist.popular_threads,
        "empty": _('No vote has been cast this month (yet).'),
        })


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_top_threads(request, mlist_fqdn):
    """Return the threads with the most answers."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    return render(request, "hyperkitty/fragments/overview_threads.html", {
        'mlist': mlist,
        'threads': mlist.top_threads,
        "empty": _('No discussions this month (yet).'),
        })


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_favorites(request, mlist_fqdn):
    """Return the threads that the logged-in user has set as favorite."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    if request.user.is_authenticated:
        favorites = [f.thread for f in Favorite.objects.filter(
            thread__mailinglist=mlist, user=request.user)]
    else:
        favorites = []
    return render(request, "hyperkitty/fragments/overview_threads.html", {
        'mlist': mlist,
        'threads': favorites,
        "empty": _('You have not flagged any discussions (yet).'),
        })


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_posted_to(request, mlist_fqdn):
    """Return the threads that the logged-in user has posted to."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    if request.user.is_authenticated:
        mm_user_id = get_mailman_user_id(request.user)
        threads_posted_to = []
        if mm_user_id is not None:
            for thread in mlist.recent_threads:
                senders = set(
                    [e.sender.mailman_id for e in thread.emails.all()])
                if mm_user_id in senders:
                    threads_posted_to.append(thread)
    else:
        threads_posted_to = []
    return render(request, "hyperkitty/fragments/overview_threads.html", {
        'mlist': mlist,
        'threads': threads_posted_to,
        "empty": _('You have not posted to this list (yet).'),
        })


@check_mlist_private
# @cache_page(3600 * 12)  # cache for 12 hours
def overview_top_posters(request, mlist_fqdn):
    """Return the authors that sent the most emails."""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    return render(request, "hyperkitty/fragments/overview_top_posters.html", {
        'mlist': mlist,
        })


@check_mlist_private
@cache_page(3600 * 12)  # cache for 12 hours
def recent_activity(request, mlist_fqdn):
    """Return the number of emails posted in the last 30 days"""
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    begin_date, end_date = mlist.get_recent_dates()
    days = daterange(begin_date, end_date)

    # Use get_messages and not get_threads to count the emails, because
    # recently active threads include messages from before the start date
    emails_in_month = mlist.emails.filter(
        date__gte=begin_date,
        date__lt=end_date)
    # graph
    emails_per_date = {}
    # populate with all days before adding data.
    for day in days:
        emails_per_date[day.strftime("%Y-%m-%d")] = 0
    # now count the emails
    for email in emails_in_month:
        date_str = email.date.strftime("%Y-%m-%d")
        if date_str not in emails_per_date:
            continue  # outside the range
        emails_per_date[date_str] += 1
    # return the proper format for the javascript chart function
    evolution = [{"date": d, "count": emails_per_date[d]}
                 for d in sorted(emails_per_date)]
    return HttpResponse(json.dumps({"evolution": evolution}),
                        content_type='application/javascript')


@check_mlist_private
def export_mbox(request, mlist_fqdn, filename):
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    query = mlist.emails
    try:
        if "start" in request.GET:
            start_date = datetime.datetime.strptime(
                request.GET["start"], "%Y-%m-%d")
            start_date = timezone.make_aware(start_date, timezone.utc)
            query = query.filter(date__gte=start_date)
        if "end" in request.GET:
            end_date = datetime.datetime.strptime(
                request.GET["end"], "%Y-%m-%d")
            end_date = timezone.make_aware(end_date, timezone.utc)
            query = query.filter(date__lt=end_date)
    except ValueError:
        return HttpResponseBadRequest("Invalid dates")
    if "thread" in request.GET:
        query = query.filter(thread__thread_id=request.GET["thread"])
    if "message" in request.GET:
        query = query.filter(message_id_hash=request.GET["message"])

    def stream_mbox(query):
        # Use the gzip format: http://www.zlib.net/manual.html#Advanced
        compressor = zlib.compressobj(6, zlib.DEFLATED, zlib.MAX_WBITS | 16)
        for email in query.order_by("archived_date").all():
            msg = email.as_message()
            yield compressor.compress(msg.as_bytes(unixfrom=True))
            yield compressor.compress(b"\n\n")
        yield compressor.flush()
    response = StreamingHttpResponse(
        stream_mbox(query), content_type="application/gzip")
    response['Content-Disposition'] = (
        'attachment; filename="%s.mbox.gz"' % filename)
    return response
