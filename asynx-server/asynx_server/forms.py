# -*- coding: utf-8 -*-

import voluptuous as v
from voluptuous import Schema, Required, All, Any, Coerce


def NestedSchema(schema_name, msg=None):

    def f(val):
        schema = globals()[schema_name]
        return v.Marker(schema.schema, msg)(val)
    return f


def Http(val):
    return v.Match('(?i)^https?://')(val)


list_tasks_form = Schema({
    Required('offset', default=0): Coerce(int),
    Required('limit', default=50): All(Coerce(int), v.Range(min=0, max=200))
})

add_task_form = Schema({
    Required('request'): {
        Required('method', default='GET'): v.Upper,
        Required('url'): Http,
        'headers': {str: Coerce(str)},
        'payload': str,
        'timeout': int,
        'allow_redirects': bool
    },
    'cname': str,
    'countdown': All(Coerce(float), v.Range(.0)),
    'eta': All(Coerce(float), v.Range(.0)),
    Any('on_success', 'on_failure', 'on_complete'):
    Any('__report__', Http, NestedSchema('add_task_form'))
})
