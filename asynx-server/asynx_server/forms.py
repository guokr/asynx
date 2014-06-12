# -*- coding: utf-8 -*-

from uuid import UUID

import voluptuous as v
from dateutil import parser
from voluptuous import Schema, Required, All, Any, Coerce

from asynx_core.taskqueue import Task


def NestedSchema(schema_name, msg=None):

    def f(val):
        schema = globals()[schema_name]
        return v.Marker(schema.schema, msg)(val)
    return f


def Http(val):
    return v.Match('(?i)^https?://')(val)


def IdentifierKind(kind):

    def f(val):
        return (kind, val)
    return f


def DateTime(val):
    try:
        return parser.parse(val)
    except (TypeError, AttributeError, ValueError):
        raise v.Invalid("expected datetime")


def Schedule(val):
    try:
        return Task._schedule_from_string(val)
    except (TypeError, ValueError):
        raise v.Invalid("expected schedule/crontab string")

try:
    String = Any(unicode, str, msg='expected string')
except NameError:
    String = str

list_tasks_form = Schema({
    Required('offset', default=0): Coerce(int),
    Required('limit', default=50): All(Coerce(int), v.Range(min=0, max=200))
})

add_task_form = Schema({
    Required('request'): {
        Required('method', default='GET'): v.Upper,
        Required('url'): Http,
        'headers': {String: String},
        'payload': Any(String, None),
        'timeout': Any(Coerce(float), None),
        'allow_redirects': Any(bool, None)
    },
    'cname': Any(String, None),
    'countdown': Any(All(Coerce(float), v.Range(.0)), None),
    'eta': Any(Coerce(DateTime), None),
    'schedule': Any(Coerce(Schedule), None),
    Any('on_success', 'on_failure', 'on_complete'):
    Any('__report__', Http, NestedSchema('add_task_form'), None)
})

identifier_form = Schema(
    Any(
        All(v.Replace('^id:', ''), Coerce(int),
            v.Range(max=2 ** 63 - 1), Coerce(IdentifierKind('id'))),
        All(v.Match('^uuid:'), v.Replace('^uuid:', ''), Coerce(UUID),
            Coerce(str), Coerce(IdentifierKind('uuid'))),
        All(v.Match('^cname:'), v.Replace('^cname:', ''),
            v.Length(min=3, max=96), Coerce(IdentifierKind('cname')))
    )
)
