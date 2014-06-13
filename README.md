asynx
=====

An open source, distributed, and web / HTTP oriented taskqueue &amp; scheduler service inspired by Google App Engine

[![Build Status](https://travis-ci.org/guokr/asynx.svg?branch=master)](https://travis-ci.org/guokr/asynx)


Asynxd
------

Asynxd is a RESTful server to the asynx-core. With the HTTP API asynxd provided, applications can create, retrieve, list, even delete their asynchronous tasks in one or more taskqueues.

### Installation

#### Dependencies

`Asynxd` depends on `Celery`, and specifically use `Redis` (>=2.2) as the message broker. We recommend you to install `redis>=2.6`.

In a Debian/Ubuntu server, use `apt-get` to install `build-essential`, `python.h` and Redis server:

```bash
$ sudo apt-get install build-essential python2.7-dev redis-server
# To see the version of redis
$ redis-server -v
```

#### Recommendation

You are recommended to install `gevent>=1.0` to increase Celery's performance, `simplejson>=3.5` to solve [issue 11489](http://bugs.python.org/issue11489).

```bash
$ sudo apt-get install libev
# in your python environment (for example: virtualenv)
$ pip install gevent simplejson
```

#### From PyPI

You can install `asynxd` from PyPI repository with PIP:

```bash
$ pip install asynxd
```

Or with Setuptools:

```bash
$ easy_install asynxd
```

#### From Github

Else, you can just clone this repository to install the development version:

```bash
$ git clone https://github.com/guokr/asynx.git
$ cd asynx/asynxd
$ python setup.py install
```

### Usage examples

To start the RESTful server:

```bash
$ asynxd start
```

To start Celery workers:

```bash
$ asynxd celery start
```

Full list of commands see `asynxd --help` and `asynxd celery --help`.

Use these environment variables to custom your application:

```bash
# redis settings
$ export ASYNX_REDIS_HOST=localhost
$ export ASYNX_REDIS_PORT=6379
$ export ASYNX_REDIS_DB=0
# gunicorn settings
$ export ASNYX_BIND="0.0.0.0:17969"
$ export ASYNX_WORKERS=4
$ export ASYNX_LOGDIR=/tmp/asynx-log
$ export ASYNX_DAEMON_LOGLEVEL=INFO
$ export ASYNX_DEBUG_LOGLEVEL=DEBUG
# celery settings
$ export ASYNX_CELERY_BROKER_URL="redis://localhost:6379/0"
$ export ASYNX_CELERY_RESULT_BACKEND="redis://localhost:6379/0"
$ export ASYNX_CELERY_LOGDIR=/tmp/asynx-log/celery
$ export ASNYX_CELERY_DAEMON_LEVEL=INFO
$ export ASNYX_CELERY_DEBUG_LEVEL=DEBUG
```

Asynx
-----

Asynx (Client) is a Python SDK for the RESTful server asynxd.

### Installation

#### Dependencies

In a Debian/Ubuntu server, use `apt-get` to install `build-essential`, `python.h`:

```bash
$ sudo apt-get install build-essential python2.7-dev
```

#### Recommendation

You are recommended to install `simplejson>=3.5` to solve [issue 11489](http://bugs.python.org/issue11489).

```bash
# in your python environment (for example: virtualenv)
$ pip install simplejson
```

#### From PyPI

You can install `asynxd` from PyPI repository with PIP:

```bash
$ pip install asynx
```

Or with Setuptools:

```bash
$ easy_install asynx
```

#### From Github

Else, you can just clone this repository to install the development version:

```bash
$ git clone https://github.com/guokr/asynx.git
$ cd asynx/asynx
$ python setup.py install
```

### Usage examples

To create a simple task with success callback:

```python
from asynx import TaskQueueClient

tqc = TaskQueueClient('http://localhost:17969', appname='test')
task = tqc.add_task(url='http://httpbin.org/get',
                    on_success='http://httpbin.org/post')
```

To create a scheduled task:

```python
task = tqc.add_task(method='DELETE',
                    url='http://httpbin.org/delete',
                    cname='scheduled task 1',  # scheduled task must have cname
                    schedule='every 30 seconds')
# or create a crontab-style scheduled task
task = tqc.add_task(method='POST',
                    url='http://httpbin.org/post',
                    data={'asynx': 'awesome!'},
                    cname='scheduled task 2',
                    schedule='*/10 1-5,8 * * *')  # m h dom mon dow
```

`TaskQueueClient.add_task` borrowed [python-requests](http://docs.python-requests.org/en/latest/)'s Request model. You can upload file-like objects as well as `requests`:

```python
fp = open('/tmp/example1.txt', 'rb')
task = tqc.add_task(method='POST',
                    url='http://httpbin.org/post',
                    files={'file': fp})
```

To retreive a task by task id, uuid or cname:

```python
task = tqc.add_task(url='http://httpbin.org/get', cname='example')
task_by_id = tqc.get_task(task['id'])
task_by_uuid = tqc.get_task(uuid=task['uuid'])  # celery uuid
task_by_cname = tqc.get_task(cname='example')
assert task == task_by_id == task_by_uuid == task_by_cname
```

To delete task:

```python
task = tqc.add_task(url='http://httpbin.org/get')
task_by_id = tqc.delete_task(task['id'])
tqc.delete_task(uuid=task['uuid'])
# raises TaskQueueResponseError
```

To list tasks in a taskqueue:

```python
tasks = tqc.list_task(offset=100, limit=50)
```
