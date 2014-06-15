# -*- coding: utf-8 -*-

from datetime import datetime

import pytz
import anyjson
from celery import schedules
from werkzeug import MultiDict
from voluptuous import MultipleInvalid
from flask import Flask, request, jsonify, json

from asynx_core.taskqueue import (Task as _Task,
                                  TaskQueue as _TaskQueue,
                                  TaskAlreadyExists,
                                  TaskCNameRequired,
                                  TaskNotFound)

from . import forms, engines

app = Flask('asynxd')
app.config.from_pyfile('application.cfg')
redisconn = engines.make_redis(app)
celeryapp = engines.make_celery(app)


class AsynxJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, schedules.schedule):
            return _Task._schedule_to_string(obj)
        return super(AsynxJSONEncoder, self).default(obj)

app.json_encoder = AsynxJSONEncoder


class TaskQueue(_TaskQueue):

    def __init__(self, appname, queuename='default'):
        localzone = None
        # support optional extension Flask-Babel
        if 'BABEL_DEFAULT_TIMEZONE' in app.config:
            localzone = pytz.timezone(app.config['BABEL_DEFAULT_TIMEZONE'])
        super(TaskQueue, self).__init__(appname, queuename, localzone)
        self.bind_redis(redisconn)


class JSONParseError(ValueError):
    pass


class IdentifierNotFound(Exception):
    pass


error_mapping = {
    200100: (400, 'Parsing failure'),
    200101: (422, 'Validation failure'),
    207202: (404, 'Task not found'),
    207203: (409, 'Task already exists'),
    107250: (500, 'Internal server error'),
}


def _error_handler(error_code, error_detail):
    status, error_desc = error_mapping[error_code]
    return jsonify(
        request_uri=request.url,
        error_code=error_code,
        error_desc=error_desc,
        error_detail=error_detail), status


@app.errorhandler(500)
def internal_server_error_handler(e):
    return _error_handler(107250, str(e))


@app.errorhandler(JSONParseError)
def parse_error_handler(e):
    return _error_handler(200100, str(e))


@app.errorhandler(MultipleInvalid)
def validation_error_handler(e):
    return _error_handler(200101, str(e))


@app.errorhandler(IdentifierNotFound)
def identifier_not_found(e):
    return _error_handler(207202, str(e))


@app.errorhandler(TaskCNameRequired)
def task_cname_required_handler(e):
    return _error_handler(200101, str(e))


@app.errorhandler(TaskNotFound)
def task_not_found_handler(e):
    return _error_handler(207202, str(e))


@app.errorhandler(TaskAlreadyExists)
def task_already_exists_handler(e):
    return _error_handler(207203, str(e))


def validate(schema, data=None, datatype=None):
    if data is None:
        data = request.data
    if datatype == 'json':
        try:
            data = anyjson.loads(data)
        except ValueError as e:
            raise JSONParseError(str(e))
    elif isinstance(data, MultiDict):
        data = data.to_dict()
    return schema(data)


@app.route('/status', methods=['GET'])
def status():
    redisconn.ping()
    return 'true', 200, {'Content-Type': 'application/json'}


@app.route('/apps/<appname>/taskqueues/<taskqueue>/tasks', methods=['GET'])
def list_tasks(appname, taskqueue):
    """Lists all non deleted tasks in a taskqueue

    Request
    -------

    ```
    GET http://asynx.host/apps/:appname/taskqueues/:taskqueue/tasks
    ```

    Parameters:
        - appname:   url param, string, the application name
                     under which the queue lies
        - taskqueue: url param, string, the name of the taskqueue
                     to list tasks from
        - offset:    query param, integer, the offset position
                     where the list start
        - limit:     query param, integer, the count of tasks
                     to be listed. maximum 200

    Request body:
        Do not supply a request body with this method

    Response
    --------

    If successful, this method returns a response body in JSON with the
    following structure:

    ```json
    {
        "items": [
            :tasks
        ],
        "total": :total
    }
    ```

    - items: list, the tasks list currently active in the queue
    - total: integer, the count of all tasks in the queue

    """
    form = validate(forms.list_tasks_form, request.args)
    offset, limit = form['offset'], form['limit']
    tq = TaskQueue(appname, taskqueue)
    total = tq.count_tasks()
    items = tq.list_tasks(form['offset'], form['limit'])
    return jsonify(items=items, total=total)


@app.route('/apps/<appname>/taskqueues/<taskqueue>/tasks', methods=['POST'])
def insert_task(appname, taskqueue):
    """Inserts a task into a taskqueue

    Request
    -------

    ```
    POST http://asynx.host/apps/:appname/taskqueues/:taskqueue/tasks
    ```

    Parameters:
        - appname:   url param, string, the application name
                     under which the queue lies
        - taskqueue: url param, string, the name of the taskqueue
                     to insert the task into

    Request body:
        Supply a task in JSON with the following structure:

        ```json
        {
            "request": {
                "method": :method,
                "url": :url,
                "headers': {
                    :headers
                },
                "payload": :payload,
                "timeout": :timeout,
                "allow_redirects: :allow_redirects,
            },
            "cname": :cname,
            "countdown": :countdown,
            "eta": :eta,
            "schedule": :schedule,
            "on_success": on_success,
            "on_failure": on_failure,
            "on_complete": on_complete
        }
        ```

        - request:    request context, includes:
            - method:   HEAD, GET, POST, PUT, PATCH, DELETE, etc
            - url:      string, URL to be request, support http & https both
            - headers:  dict, request with these HTTP headers
            - payload:  string, request body
            - timeout:  float, the timeout of the request in seconds
            - allow_redirects: boolean, set to True if POST/PUT/DELETE
                               redirect following is allowed
        - cname:      string & optional, custom name for the task
                      min: 3 chars, max: 96 chars
        - countdown:  float, time interval to trigger the task, in seconds
        - eta:        datetime (isoformat), the local unix timestamp to
                      trigger the task, can not be used with countdown
        - schedule:   schedule string, provide this if the task is
                      a scheduled task
        - on_success: success callback. Can be a URL and it will be called
                      with a POST request;
                      or None to do nothing;
                      or an internal method:
                        __report__, report this task in application's log
                      Else, a subtask has the same structure of task
        - on_failure: Same as `on_success`, but for failure callback
                      default: __report__
        - on_complete: Same as `on_success`, but for all task callback
                       default: None

    Response
    --------

    ```json
        {
            id: :id,
            uuid: :uuid,
            cname: :cname,
            request: {
                :request
            },
            countdown: :countdown,
            eta: :eta,
            last_run_at: :last_run_at,
            status: :status,
            on_success: :on_success,
            on_failure: :on_failure,
            on_complete: :on_complete
        }
    ```

    Additional fields:

    - id:     integer, internal id of this task, uniqued in a queue
    - uuid:   string, internal uuid of this task, uniqued across the service
    - status: string, current status of this task, can be:
        "new", enqueued and will be executed immediately
        "delayed", enqueued but will not be triggered until eta
    - last_run_at: datetime (isoformat)

    """
    task_dict = validate(forms.add_task_form, datatype='json')
    tq = TaskQueue(appname, taskqueue)
    x = tq.add_task(**task_dict)
    return jsonify(x), 201


@app.route('/apps/<appname>/taskqueues/<taskqueue>/tasks/<identifier>',
           methods=['GET'])
def get_task(appname, taskqueue, identifier):
    """Gets identified task in a taskqueue

    Request
    -------

    ```
    GET http://asynx.host/apps/:appname/taskqueues/:taskqueue/tasks/:identifier
    ```

    Parameters:
        - appname:    url param, string, the application name
                      under which the queue lies
        - taskqueue:  url param, string, the name of the taskqueue
                      in which the task belongs
        - identifier: url param, string, the identifier to the task.
                      the identifier can be:
                        - id, form: {integer} or id:{integer};
                        - uuid, form: uuid:{string}
                        - cname, form: cname:{string}

    Request body:
        Do not supply a request body with this method

    Response
    --------

    Task resource same as `insert_task`.

    """
    try:
        kind, kind_id = validate(forms.identifier_form, identifier)
    except MultipleInvalid as e:
        raise IdentifierNotFound(str(e))
    tq = TaskQueue(appname, taskqueue)
    if kind == 'id':
        task = tq.get_task(kind_id)
    elif kind == 'uuid':
        task = tq.get_task_by_uuid(kind_id)
    elif kind == 'cname':
        task = tq.get_task_by_cname(kind_id)
    return jsonify(task)


@app.route('/apps/<appname>/taskqueues/<taskqueue>/tasks/<identifier>',
           methods=['DELETE'])
def delete_task(appname, taskqueue, identifier):
    """Deletes a task from a taskqueue

    Request
    -------

    ```
    DELETE \
        http://asynx.host/apps/:appname/taskqueues/:taskqueue/tasks/:identifier
    ```

    Parameters:
        - appname:    url param, string, the application name
                      under which the queue lies
        - taskqueue:  url param, string, the name of the taskqueue
                      to delete a task from
        - identifier: url param, string, the identifier to the task.
                      the identifier can be:
                        - id, form: {integer} or id:{integer};
                        - uuid, form: uuid:{string}
                        - cname, form: cname:{string}

    Request body:
        Do not supply a request body with this method

    Response
    --------

    If successful, this method returns null in JSON

    """
    kind, kind_id = validate(forms.identifier_form, identifier)
    tq = TaskQueue(appname, taskqueue)
    if kind == 'id':
        tq.delete_task(kind_id)
    elif kind == 'uuid':
        tq.delete_task_by_uuid(kind_id)
    elif kind == 'cname':
        tq.delete_task_by_cname(kind_id)
    return 'null', 200, {'Content-Type': 'application/json'}
