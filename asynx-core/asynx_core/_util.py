# -*- coding: utf-8 -*-

from pytz import utc
from datetime import datetime, timedelta

import anyjson

_dumps = anyjson.dumps
_loads = anyjson.loads
_interrupt = (KeyboardInterrupt, SystemExit)

try:
    dict_items = dict.iteritems
except AttributeError:
    # python 3
    dict_items = dict.items

try:
    basestring = basestring
except NameError:
    basestring = str

try:
    get_total_seconds = timedelta.total_seconds
except AttributeError:
    # python 2.6
    get_total_seconds = lambda d: (d.microseconds +
                                   (d.seconds + d.days * 86400) *
                                   1e6) / 1e6


def not_bytes(s):
    # python3's json accept str instead of bytes
    if type(s).__name__ == 'bytes':
        s = s.decode('latin1')
    return s


def user_agent():
    return 'Asynx/4.0'


def utcnow():
    return utc.localize(datetime.utcnow())
