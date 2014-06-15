# -*- coding: utf-8 -*-

from datetime import datetime
from unittest import TestCase

import redis
import anyjson
from pytz import utc
from tzlocal import get_localzone
from celery import Celery

from asynxd import apis


class ApisTestCase(TestCase):

    def setUp(self):
        apis.redisconn.flushdb()
        self.conn1 = redis.StrictRedis(db=1)
        self.conn1.delete('celery')
        self.celery = Celery(broker='redis://localhost/1')
        self.app = apis.app
        self.client = self.app.test_client()
        self.app.config.update({
            'DEBUG': True,
            'TESTING': True
        })

    def tearDown(self):
        self.conn1.delete('celery')
        apis.redisconn.flushdb()

    def test_list_tasks(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            [tq.add_task({'method': 'GET',
                          'url': 'http://httpbin.org/get'})
             for i in range(72)]
        rv = self.client.get('/apps/test/taskqueues/default/tasks?limit=a')
        self.assertEqual(rv.status_code, 422)
        err = anyjson.loads(rv.data)
        self.assertEqual(err['error_code'], 200101)
        self.assertEqual(err['error_desc'], 'Validation failure')
        self.assertEqual(err['request_uri'], 'http://localhost/apps/test/'
                         'taskqueues/default/tasks?limit=a')
        self.assertTrue('error_detail' in err)
        rv = self.client.get('/apps/test/taskqueues/default/tasks')
        self.assertEqual(rv.status_code, 200)
        result = anyjson.loads(rv.data)
        self.assertTrue('items' in result)
        self.assertEqual(result['total'], 72)
        self.assertEqual(len(result['items']), 50)
        self.assertEqual(result['items'][0]['id'], 1)
        self.assertEqual(result['items'][49]['id'], 50)
        self.assertEqual(result['items'][49]['status'], 'new')
        rv = self.client.get('/apps/test/taskqueues/default/tasks?offset=50')
        self.assertEqual(rv.status_code, 200)
        result = anyjson.loads(rv.data)
        self.assertTrue('items' in result)
        self.assertEqual(result['total'], 72)
        self.assertEqual(len(result['items']), 22)
        self.assertEqual(result['items'][0]['id'], 51)
        self.assertEqual(result['items'][21]['id'], 72)

    def test_scheduled_task(self):
        task_dict = {
            'request': {'url': 'http://httpbin.org/get'},
            'schedule': '1234567',
            'cname': 'haha'
        }
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 422)
        task_dict['schedule'] = 'every 30 second'
        task_dict.pop('cname')
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 422)
        task_dict['cname'] = 'test schedule'
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 201)
        task = anyjson.loads(rv.data)
        self.assertEqual(task['id'], 1)
        self.assertEqual(task['schedule'], 'every 30.0 seconds')
        task_dict['schedule'] = '*/1 1-5,8 * * *'
        task_dict['cname'] = 'test crontab'
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 201)
        task = anyjson.loads(rv.data)
        self.assertEqual(task['id'], 2)
        self.assertEqual(task['schedule'], '*/1 1-5,8 * * *')

    def test_insert_task(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            tq.add_task({'method': 'GET',
                         'url': 'http://httpbin.org/get'},
                        cname='testtask')
        task_dict = {
            'request': {'url': 'http://httpbin.org/get'},
            'cname': 'testtask',
            'eta': '10:42'
        }
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 409)
        self.assertEqual(anyjson.loads(rv.data)['error_code'], 207203)
        task_dict['cname'] = 'testtask1'
        rv = self.client.post(
            '/apps/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 201)
        task = anyjson.loads(rv.data)
        self.assertEqual(task['id'], 2)
        self.assertEqual(task['request']['method'], 'GET')
        self.assertEqual(task['cname'], 'testtask1')
        now = datetime.now()
        eta_expect = utc.normalize(
            get_localzone().localize(
                datetime(now.year, now.month, now.day, 10, 42)
            )
        ).isoformat()
        self.assertEqual(task['eta'], eta_expect)
        self.assertTrue(isinstance(task['countdown'], float))

    def test_get_task(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            task = tq.add_task({'method': 'GET',
                                'url': 'http://httpbin.org/get'},
                               cname='testtask')
        rv = self.client.get('/apps/test/taskqueues/default/tasks/1')
        self.assertEqual(rv.status_code, 200)
        task_by_id_implicit = anyjson.loads(rv.data)
        rv = self.client.get('/apps/test/taskqueues/default/tasks/id:1')
        self.assertEqual(rv.status_code, 200)
        task_by_id = anyjson.loads(rv.data)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/uuid:{0}'
            .format(task['uuid']))
        self.assertEqual(rv.status_code, 200)
        task_by_uuid = anyjson.loads(rv.data)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/cname:testtask')
        self.assertEqual(rv.status_code, 200)
        task_by_cname = anyjson.loads(rv.data)
        self.assertTrue(task == task_by_id_implicit == task_by_id ==
                        task_by_uuid == task_by_cname)
        rv = self.client.get('/apps/test/taskqueues/default/tasks/uuid:1')
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/{0}'.format(task['uuid']))
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get('/apps/test/taskqueues/default/tasks/testtask')
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/{0}'.format(2 ** 63 - 1))
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/{0}'.format(2 ** 63))
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get('/apps/test/taskqueues/default/tasks/cname:aaa')
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get('/apps/test/taskqueues/default/tasks/cname:aa')
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/cname:' + ('a' * 96))
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get(
            '/apps/test/taskqueues/default/tasks/cname:' + ('a' * 97))
        self.assertEqual(rv.status_code, 404)

    def test_delete_task(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            task = tq.add_task({'method': 'GET',
                                'url': 'http://httpbin.org/get'},
                               cname='testtask')
        rv = self.client.delete(
            '/apps/test/taskqueues/default/tasks/uuid:{0}'
            .format(task['uuid']))
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(tq.count_tasks(), 0)
