# -*- coding: utf-8 -*-

from unittest import TestCase

import redis
import anyjson
from celery import Celery

from asynx_server import apis


class ApisTestCase(TestCase):

    def setUp(self):
        apis.redisconn.flushdb()
        self.conn1 = redis.StrictRedis(db=1)
        self.conn1.delete('celery')
        self.celery = Celery(broker='redis://localhost/1')
        self.app = apis.app
        self.client = self.app.test_client()

    def tearDown(self):
        self.conn1.delete('celery')
        apis.redisconn.flushdb()

    def test_list_tasks(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            [tq.add_task({'method': 'GET',
                          'url': 'http://httpbin.org/get'})
             for i in range(72)]
        rv = self.client.get('/app/test/taskqueues/default/tasks?limit=a')
        self.assertEqual(rv.status_code, 400)
        err = anyjson.loads(rv.data)
        self.assertEqual(err['error_code'], 200101)
        self.assertEqual(err['error_desc'], 'Validation failure')
        self.assertEqual(err['request_uri'], 'http://localhost/app/test/'
                         'taskqueues/default/tasks?limit=a')
        self.assertTrue('error_detail' in err)
        rv = self.client.get('/app/test/taskqueues/default/tasks')
        self.assertEqual(rv.status_code, 200)
        result = anyjson.loads(rv.data)
        self.assertTrue('items' in result)
        self.assertEqual(result['total'], 72)
        self.assertEqual(len(result['items']), 50)
        self.assertEqual(result['items'][0]['id'], 1)
        self.assertEqual(result['items'][49]['id'], 50)
        self.assertEqual(result['items'][49]['status'], 'enqueued')
        rv = self.client.get('/app/test/taskqueues/default/tasks?offset=50')
        self.assertEqual(rv.status_code, 200)
        result = anyjson.loads(rv.data)
        self.assertTrue('items' in result)
        self.assertEqual(result['total'], 72)
        self.assertEqual(len(result['items']), 22)
        self.assertEqual(result['items'][0]['id'], 51)
        self.assertEqual(result['items'][21]['id'], 72)

    def test_insert_task(self):
        with self.app.app_context():
            tq = apis.TaskQueue('test')
            tq.add_task({'method': 'GET',
                         'url': 'http://httpbin.org/get'},
                        cname='testtask')
        task_dict = {
            'request': {'url': 'http://httpbin.org/get'},
            'cname': 'testtask'
        }
        rv = self.client.post(
            '/app/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 409)
        self.assertEqual(anyjson.loads(rv.data)['error_code'], 207203)
        task_dict['cname'] = 'testtask1'
        rv = self.client.post(
            '/app/test/taskqueues/default/tasks',
            data=anyjson.dumps(task_dict))
        self.assertEqual(rv.status_code, 201)
        task = anyjson.loads(rv.data)
        self.assertEqual(task['id'], 3)
        self.assertEqual(task['request']['method'], 'GET')
        self.assertEqual(task['cname'], 'testtask1')
        self.assertEqual(task['eta'], None)
        self.assertEqual(task['countdown'], None)
