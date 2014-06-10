# -*- coding: utf-8 -*-

from datetime import datetime
try:
    from urlparse import urlparse, urlunparse
except ImportError:
    from urllib.parse import urlparse, urlunparse

import anyjson
import requests
from dateutil import parser


class TaskQueueResponseError(Exception):

    def __init__(self, code, desc, detail, request_uri):
        self.code = code
        self.desc = desc
        self.detail = detail
        self.request_uri = request_uri
        Exception.__init__(self, '{0} ({1}): {2}'.format(desc, code, detail))


class TaskQueueServerError(Exception):
    pass


def _task_convert(task):
    if task['eta'] is not None:
        task['eta'] = parser.parse(task['eta'])
    return task


class TaskQueueClient(object):

    ResponseError = TaskQueueResponseError
    ServerError = TaskQueueServerError

    def __init__(self, base_url, appname,
                 timeout=5.0, task_timeout=120.0):
        """taskqueue client for asynx-server

        Parameters:
            - base_url: string, base URL of asynx-server's RESTful API
            - appname:  string, application's name
            - timeout:  float, timeout for requestions to asynx-server
            - task_timeout: float, timeout for task running

        """
        self._base_url = urlparse(base_url)
        self.appname = appname
        self.timeout = timeout
        self.task_timeout = task_timeout

    @classmethod
    def _handle_errors(cls, resp):
        is_ok = resp.status_code in (200, 201)
        is_json = resp.headers['content-type'] == 'application/json'
        if is_json:
            if is_ok:
                return
            err = resp.json()
            raise cls.ResponseError(
                err['error_code'], err['error_desc'],
                err['error_detail'], err['request_uri'])
        else:
            raise cls.ServerError(
                'Response content is not in JSON format')

    def _rest_url(self, taskqueue, suffix=''):
        path = 'app/{0}/taskqueues/{1}/tasks'.format(self.appname, taskqueue)
        path += suffix
        return urlunparse(self._base_url[:2] + (path, '', '', ''))

    def list_tasks(self, taskqueue='default', offset=0, limit=50):
        """Listing all non deleted tasks in a taskqueue

        GET http://asynx.host/app/:appname/taskqueues/:taskqueue/tasks

        Parameters:
            - taskqueue: string, taskqueue's name
            - offset:    integer, the offset position where
                         the list start, default 0
            - limit:     integer, the count of tasks to be listed,
                         default 50, maximum 200

        Returns:
            same as RESTful API
            dictionary:
                items: [:task]
                total: :task_count

        """
        url = self._rest_url(taskqueue)
        resp = requests.get(url, params={'offset': offset,
                                         'limit': limit},
                            timeout=self.timeout)
        self._handle_errors(resp)
        result = resp.json()
        for task in result['items']:
            _task_convert(task)
        return result

    def task(self,
             url,
             method='GET',
             params=None,
             data=None,
             headers=None,
             cookies=None,
             files=None,
             auth=None,
             timeout=None,
             allow_redirects=None,
             cname=None,
             countdown=None,
             eta=None,
             on_success=None,
             on_failure='__report__',
             on_complete=None):
        """Create a dictionary with task structure

        With this method, you can create sub-task for `on_sccess`,
        `on_failure` or `on_complete` using.

        Parameter:
            - url:     string, URL to be request asynchronously, http or https
            - method:  HEAD, GET (default), POST, PUT, PATCH, DELETE
            - params:  (optional) dictionary or bytes to be sent in the query
                       string of the request
            - data:    (optional) dictionary, bytes or file like object to send
                       in the body of request
            - headers: (optional) dictionary of HTTP headers to send with req
            - cookies: (optional) dict or CookieJar object to send with req
            - files:   (optional) dictionary of 'name': file-like-objects for
                       multipart encoding upload
            - auth:    (optional) auth tuple to enable Basic/Digest/Custom
                       HTTP auth
            - timeout: (optional) float describing the timeout of the request
                       in seconds
            - allow_redirects: (optional) boolean. True if POST/PUT/DELETE
                       redirect following is allowed
            - cname:   (optional) string, custom name for task
            - countdown: (optional) float, time interval to trigger the task,
                       in seconds, can not be passed with eta
            - eta:     (optional) datetime, when to trigger the task, can not
                       be passed with countdown
            - on_success: (optional) success callback.
                       string of URL (will be called using a POST request);
                       or `None` to do nothing;
                       or and internal method `__report__` to report task;
                       else, a sub-task shared the same structure
                       like this task
            - on_failure: (optional) same as `on_success`,
                       but be called when failed, default `__report__`
            - on_complete: (optional) same as `on_success`,
                       but be called always. default `None`

        Returns:
            dictionary with task structure

        """
        # borrow from python-requests to prepare request dict
        request = requests.models.Request(method=method,
                                          url=url,
                                          headers=headers,
                                          files=files,
                                          data=data,
                                          params=params,
                                          auth=auth,
                                          cookies=cookies)
        p = request.prepare()
        task = {
            'request': {
                'url': p.url,
                'method': p.method,
                'headers': dict(p.headers),
                'payload': p.body
            },
            'on_success': on_success,
            'on_failure': on_failure,
            'on_complete': on_complete
        }
        if cname:
            task['cname'] = cname
        task['request']['timeout'] = timeout if timeout else self.task_timeout
        if allow_redirects is not None:
            task['request']['allow_redirects'] = allow_redirects
        if countdown is not None:
            task['countdown'] = countdown
        elif eta is not None:
            if isinstance(eta, datetime):
                eta = eta.isoformat()
            task['eta'] = eta
        return task

    def add_task(self, task=None, taskqueue='default', **kwargs):
        """Inserts a task into a taskqueue

        POST http://asynx.host/app/:appname/taskqueues/:taskqueue/tasks

        Parameters:
            - task:      (optional) dictionary created by self.task()
            - taskqueue: string, taskqueue's name, default 'default'
            - kwargs:    (optional) parameters passed to self.task(),
                         if `task` is None

        Returns:
            dictionary of task, same as RESTful API

        """
        if task:
            if 'on_success' in kwargs:
                task['on_success'] = kwargs['on_success']
            if 'on_failure' in kwargs:
                task['on_failure'] = kwargs['on_failure']
            if 'on_complete' in kwargs:
                task['on_complete'] = kwargs['on_complete']
        else:
            task = self.task(**kwargs)
        task = anyjson.dumps(task)
        url = self._rest_url(taskqueue)
        resp = requests.post(url, data=task,
                             headers={'Content-Type': 'application/json'},
                             timeout=self.timeout)
        self._handle_errors(resp)
        return _task_convert(resp.json())

    def get_task(self, id=None, cname=None,
                 uuid=None, taskqueue='default'):
        """Gets identified task in a taskqueue

        GET http://asynx.host/app/:appname/ \
            taskqueues/:taskqueue/tasks/:identifier

        Parameters:
            - id: (optional) integer, task id
            - cname: (optional) string, task custom name
            - uuid: (optional) string, task uuid
            - taskqueue: string, taskqueue's name, default 'default'

        Returns:
            dictionary of task, same as RESTful API

        """
        if id is None and cname is None and uuid is None:
            raise TypeError('Provide `task_id`, `cname` '
                            'or `uuid` to retrieve a task')
        if id:
            idf = '/id:{0}'.format(id)
        elif cname:
            idf = '/cname:{0}'.format(cname)
        else:
            idf = '/uuid:{0}'.format(uuid)
        url = self._rest_url(taskqueue, idf)
        resp = requests.get(url)
        self._handle_errors(resp)
        return _task_convert(resp.json())

    def delete_task(self, task_id=None, cname=None,
                    uuid=None, taskqueue='default'):
        """Deletes identified task in a taskqueue

        DELETE http://asynx.host/app/:appname/ \
               taskqueues/:taskqueue/tasks/:identifier

        Parameters:
            - task_id: (optional) integer, task id
            - cname: (optional) string, task custom name
            - uuid: (optional) string, task uuid
            - taskqueue: string, taskqueue's name, default 'default'

        Returns: None

        """
        if task_id is None and cname is None and uuid is None:
            raise TypeError('Provide `task_id`, `cname` '
                            'or `uuid` to retrieve a task')
        if task_id:
            idf = '/id:{0}'.format(task_id)
        elif cname:
            idf = '/cname:{0}'.format(cname)
        else:
            idf = '/uuid:{0}'.format(uuid)
        url = self._rest_url(taskqueue, idf)
        resp = requests.delete(url)
        self._handle_errors(resp)
