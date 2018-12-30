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

from django.core.cache import cache


class CachedValue(object):

    cache_key = None
    timeout = None

    def _get_cache_key(self, *args, **kwargs):
        if self.cache_key is not None:
            return self.cache_key
        raise NotImplementedError

    def get_value(self, *args, **kwargs):
        """Get the value that must be cached."""
        raise NotImplementedError

    def warm_up(self, *args, **kwargs):
        """Stores the value in the cache if it is not there already."""
        if cache.get(self._get_cache_key(*args, **kwargs)) is None:
            self.rebuild(*args, **kwargs)

    def rebuild(self, *args, **kwargs):
        """Overwrite the value in the cache."""
        value = self.get_value(*args, **kwargs)
        cache.set(self._get_cache_key(*args, **kwargs), value, self.timeout)
        return value

    def get_or_set(self, *args, **kwargs):
        """Return the cached value, rebuilding the cache if necessary."""
        value = cache.get(self._get_cache_key(*args, **kwargs))
        if value is None:
            value = self.rebuild(*args, **kwargs)
        return value

    def __call__(self, *args, **kwargs):
        return self.get_or_set(*args, **kwargs)


class ModelCachedValue(CachedValue):

    def __init__(self, instance):
        self.instance = instance

    def _get_cache_key(self, *args, **kwargs):
        if self.cache_key is not None:
            return "%s:%s:%s" % (
                self.instance.__class__.__name__,
                self.instance.pk,
                self.cache_key)
        raise NotImplementedError


class VotesCachedValue(ModelCachedValue):

    cache_key = "votes"

    def get_value(self):
        from .thread import Thread
        from .email import Email
        from .vote import Vote
        if isinstance(self.instance, Thread):
            filters = {"email__thread_id": self.instance.id}
        elif isinstance(self.instance, Email):
            filters = {"email_id": self.instance.id}
        else:
            ValueError("The 'votes' cached value only accepts 'Email' "
                       "and 'Thread' instance")
        votes = list(Vote.objects.filter(**filters).values_list(
            "value", flat=True))
        return (
                len([v for v in votes if v == 1]),
                len([v for v in votes if v == -1]),
            )

    def get_or_set(self):
        votes = super(VotesCachedValue, self).get_or_set()
        likes, dislikes = votes
        # XXX: use an Enum?
        if likes - dislikes >= 10:
            status = "likealot"
        elif likes - dislikes > 0:
            status = "like"
        else:
            status = "neutral"
        return {"likes": likes, "dislikes": dislikes, "status": status}
