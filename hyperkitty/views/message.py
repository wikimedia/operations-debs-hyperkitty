#-*- coding: utf-8 -*-
# Copyright (C) 2014-2015 by the Free Software Foundation, Inc.
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

from __future__ import absolute_import, unicode_literals

import urllib
import datetime
import json

from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.exceptions import SuspiciousOperation
from django.template import RequestContext, loader
from django.contrib.auth.decorators import login_required

from hyperkitty.lib.mailman import ModeratedListException
from hyperkitty.lib.posting import post_to_list, PostingFailed, reply_subject
from hyperkitty.lib.view_helpers import (
    get_months, check_mlist_private, get_posting_form)
from hyperkitty.models import MailingList, Email, Attachment
from .forms import PostForm, ReplyForm


@check_mlist_private
def index(request, mlist_fqdn, message_id_hash):
    '''
    Displays a single message identified by its message_id_hash (derived from
    message_id)
    '''
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    message = get_object_or_404(Email,
        mailinglist=mlist, message_id_hash=message_id_hash)
    if request.user.is_authenticated():
        message.myvote = message.votes.filter(user=request.user).first()
    else:
        message.myvote = None

    context = {
        'mlist' : mlist,
        'message': message,
        'message_id_hash' : message_id_hash,
        'months_list': get_months(mlist),
        'month': message.date,
        'reply_form': get_posting_form(ReplyForm, request, mlist),
    }
    return render(request, "hyperkitty/message.html", context)


@check_mlist_private
def attachment(request, mlist_fqdn, message_id_hash, counter, filename):
    """
    Sends the numbered attachment for download. The filename is not used for
    lookup, but validated nonetheless for security reasons.
    """
    # pylint: disable=unused-argument
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    message = get_object_or_404(Email,
        mailinglist=mlist, message_id_hash=message_id_hash)
    att = get_object_or_404(Attachment,
        email=message, counter=int(counter))
    if att.name != filename:
        raise Http404
    # http://djangosnippets.org/snippets/1710/
    response = HttpResponse(att.content)
    response['Content-Type'] = att.content_type
    response['Content-Length'] = att.size
    if att.encoding is not None:
        response['Content-Encoding'] = att.encoding
    # Follow RFC2231, browser support is sufficient nowadays (2012-09)
    response['Content-Disposition'] = 'attachment; filename*=UTF-8\'\'%s' \
            % urllib.quote(att.name.encode('utf-8'))
    return response


@check_mlist_private
def vote(request, mlist_fqdn, message_id_hash):
    """ Vote for or against a given message identified by messageid. """
    if request.method != 'POST':
        raise SuspiciousOperation
    if not request.user.is_authenticated():
        return HttpResponse('You must be logged in to vote',
                            content_type="text/plain", status=403)
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    message = get_object_or_404(Email,
        mailinglist=mlist, message_id_hash=message_id_hash)

    value = int(request.POST['vote'])
    message.vote(value, request.user)

    # Extract all the votes for this message to refresh it
    message.myvote = message.votes.filter(user=request.user).first()
    t = loader.get_template('hyperkitty/fragments/like_form.html')
    html = t.render(RequestContext(request, {
            "object": message,
            "message_id_hash": message_id_hash,
            }))

    votes = message.get_votes()
    result = { "like": votes["likes"], "dislike": votes["dislikes"],
               "html": html, }
    return HttpResponse(json.dumps(result),
                        content_type='application/javascript')


@login_required
@check_mlist_private
def reply(request, mlist_fqdn, message_id_hash):
    """Sends a reply to the list."""
    if request.method != 'POST':
        raise SuspiciousOperation
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    form = get_posting_form(ReplyForm, request, mlist, request.POST)
    if not form.is_valid():
        return HttpResponse(form.errors.as_text(),
                            content_type="text/plain", status=400)
    if form.cleaned_data["newthread"]:
        subject = form.cleaned_data["subject"]
        headers = {}
    else:
        message = get_object_or_404(Email,
            mailinglist=mlist, message_id_hash=message_id_hash)
        subject = reply_subject(message.subject)
        headers = {"In-Reply-To": "<%s>" % message.message_id,
                   "References": "<%s>" % message.message_id, }
    if form.cleaned_data["sender"]:
        headers["From"] = form.cleaned_data["sender"]
    try:
        subscribed_now = post_to_list(
            request, mlist, subject, form.cleaned_data["message"], headers)
    except PostingFailed, e:
        return HttpResponse(str(e), content_type="text/plain", status=500)
    except ModeratedListException, e:
        return HttpResponse(str(e), content_type="text/plain", status=403)

    # TODO: if newthread, don't insert the temp mail in the thread, redirect to
    # the new thread. Should we insert the mail in the DB and flag it as
    # "temporary", to be confirmed by a later reception from mailman? This
    # looks complex, because the temp mail should only be visible by its
    # sender.

    if form.cleaned_data["newthread"]:
        html = None
    else:
        email_reply = {
            "sender_name": "%s %s" % (request.user.first_name,
                                      request.user.last_name),
            "sender_email": form.cleaned_data["sender"] or request.user.email,
            "content": form.cleaned_data["message"],
            "level": message.thread_depth, # no need to increment, level = thread_depth - 1
        }
        t = loader.get_template('hyperkitty/ajax/temp_message.html')
        html = t.render(RequestContext(request, { 'email': email_reply }))
    # TODO: make the message below translatable.
    result = {"result": "Your reply has been sent and is being processed.",
              "message_html": html}
    if subscribed_now:
        result['result'] += "\n  You have been subscribed to {} list.".format(mlist_fqdn)
    return HttpResponse(json.dumps(result),
                        content_type="application/javascript")


@login_required
@check_mlist_private
def new_message(request, mlist_fqdn):
    """ Sends a new thread-starting message to the list. """
    mlist = get_object_or_404(MailingList, name=mlist_fqdn)
    if request.method == 'POST':
        form = get_posting_form(PostForm, request, mlist, request.POST)
        if form.is_valid():
            today = datetime.date.today()
            headers = {}
            if form.cleaned_data["sender"]:
                headers["From"] = form.cleaned_data["sender"]
            try:
                post_to_list(request, mlist, form.cleaned_data['subject'],
                             form.cleaned_data["message"], headers)
            except PostingFailed, e:
                messages.error(request, str(e))
            else:
                messages.success(request, "The message has been sent successfully.")
                redirect_url = reverse('hk_archives_with_month', kwargs={
                    "mlist_fqdn": mlist_fqdn,
                    'year': today.year, 'month': today.month})
                return redirect(redirect_url)
    else:
        form = get_posting_form(PostForm, request, mlist)
    context = {
        "mlist": mlist,
        "post_form": form,
        'months_list': get_months(mlist),
    }
    return render(request, "hyperkitty/message_new.html", context)
