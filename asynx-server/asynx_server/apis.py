# -*- coding: utf-8 -*-

import anyjson
from werkzeug import MultiDict
from voluptuous import MultipleInvalid
from flask import Flask, request, jsonify
from flask.ext.redis import Redis

from asynx_core.taskqueue import (TaskQueue as _TaskQueue,
                                  TaskAlreadyExists,
                                  TaskNotFound)

from . import forms

app = Flask('asynx_server')
app.config.from_pyfile('application.cfg')
redisconn = Redis(app)


class TaskQueue(_TaskQueue):

    def __init__(self, appname, queuename='default'):
        super(TaskQueue, self).__init__(appname, queuename)
        self.bind_redis(redisconn)


class JSONParseError(Exception):
    pass


error_mapping = {
    200100: (400, 'Parsing failure'),
    200101: (400, 'Validation failure'),
    207202: (404, 'Task not found'),
    207203: (409, 'Task already exists'),
}


def _error_handler(error_code, error_detail):
    status, error_desc = error_mapping[error_code]
    return jsonify(
        request_uri=request.url,
        error_code=error_code,
        error_desc=error_desc,
        error_detail=error_detail), status


@app.errorhandler(JSONParseError)
def parse_error_handler(e):
    return _error_handler(200100, str(e))


@app.errorhandler(MultipleInvalid)
def validation_error_handler(e):
    return _error_handler(200101, str(e))


@app.errorhandler(TaskNotFound)
def task_not_found_handler(e):
    return _error_handler(207202, str(e))


@app.errorhandler(TaskAlreadyExists)
def task_already_exists_handler(e):
    return _error_handler(207203, str(e))


def validate(schema, data=None):
    if data is None:
        data = request.data
    if isinstance(data, basestring):
        try:
            data = anyjson.loads(data)
        except ValueError as e:
            raise JSONParseError(str(e))
    elif isinstance(data, MultiDict):
        data = data.to_dict()
    return schema(data)


@app.route('/app/<appname>/taskqueues/<taskqueue>/tasks', methods=['GET'])
def list_tasks(appname, taskqueue):
    """Lists all non deleted tasks in a taskqueue

    Request
    -------

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


@app.route('/app/<appname>/taskqueues/<taskqueue>/tasks', methods=['POST'])
def insert_tasks(appname, taskqueue):
    """Insert a task into an taskqueue

    Request
    -------

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
        - countdown:  float, time interval to trigger the task, in seconds
        - eta:        float, the UTC unix timestamp to trigger the task,
                      can not be used with countdown
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
        "new"
        "enqueued", enqueued and will be executed immediately
        "delayed", enqueued but will not be triggered until eta

    """
    task_dict = validate(forms.add_task_form)
    tq = TaskQueue(appname, taskqueue)
    return jsonify(tq.add_task(**task_dict)), 201
