# -*- coding: utf-8 -*-

from unittest import TestCase
from datetime import datetime, timedelta

import redis
import anyjson
from celery import Celery, schedules

from asynx_core.taskqueue import (TaskQueue, Task,
                                  TaskNotFound,
                                  TaskStatusNotMatched,
                                  TaskAlreadyExists,
                                  TaskCNameRequired)
from asynx_core._util import user_agent, not_bytes, utcnow


class TaskQueueTestCase(TestCase):

    def setUp(self):
        self.conn0 = redis.StrictRedis()
        self.conn1 = redis.StrictRedis(db=1)
        self.conn0.delete('celery')
        self.conn1.flushdb()
        self.app = Celery(broker='redis://')

    def tearDown(self):
        self.conn0.delete('celery')
        self.conn1.flushdb()

    def test_dispatch_task(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        task = Task({'method': 'GET',
                     'url': 'http://httpbin.org'},
                    1)
        idx, task_dict = task._to_redis()
        metakey = tq._TaskQueue__metakey(idx)
        self.assertTrue(self.conn1.hmset(metakey, task_dict))
        task.bind_taskqueue(tq)
        tq._dispatch_task(task)
        r = self.conn1.hmget(metakey, 'status', 'request',
                             'cname', 'on_complete', 'on_failure',
                             'on_success', 'uuid')
        self.assertEqual(r[0:1] + r[2:-1], [b'"new"', b'null', b'null',
                                            b'"__report__"', b'null'])
        self.assertEqual(anyjson.loads(not_bytes(r[1])),
                         {"url": "http://httpbin.org", "method": "GET"})
        clobj = anyjson.loads(not_bytes(self.conn0.lindex('celery', 0)))
        self.assertEqual(clobj['properties']['correlation_id'],
                         anyjson.loads(not_bytes(r[-1])))
        task = Task({'method': 'GET',
                     'url': 'http://httpbin.org'},
                    2, countdown=10)
        idx, task_dict = task._to_redis()
        metakey = tq._TaskQueue__metakey(idx)
        self.assertTrue(self.conn1.hmset(metakey, task_dict))
        task.bind_taskqueue(tq)
        tq._dispatch_task(task)
        self.assertEqual(self.conn1.hget(metakey, 'status'), b'"delayed"')

    def test_add_task(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        now = datetime.now()
        delta = timedelta(seconds=2.718287)
        task = tq.add_task(
            {'method': 'GET',
             'url': 'http://httpbin.org'},
            cname='task001',
            eta=now + delta)
        self.assertEqual(task['status'], 'delayed')
        self.assertEqual(task['cname'], 'task001')
        self.assertTrue(2.5 < task['countdown'] < 2.71287)
        self.assertEqual(task['eta'].utcoffset(), timedelta(0))
        self.assertRaises(TaskAlreadyExists,
                          tq.add_task, {}, cname='task001')

    def test_scheduled_task(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        kw = {
            'request': {'method': 'GET',
                        'url': 'http://httpbin.org'},
            'schedule': schedules.crontab('*/10', '1,2-10')
        }
        self.assertRaises(TaskCNameRequired, tq.add_task, **kw)
        kw['cname'] = 'crontest'
        task00 = tq.add_task(**kw)
        metakey = tq._TaskQueue__metakey(task00['id'])
        self.assertEqual(not_bytes(self.conn1.hget(metakey, 'schedule')),
                         '"*/10 1,2-10 * * *"')
        kw['schedule'] = schedules.schedule(30)
        kw['cname'] = 'schedtest'
        task01 = tq.add_task(**kw)
        metakey = tq._TaskQueue__metakey(task01['id'])
        self.assertEqual(not_bytes(self.conn1.hget(metakey, 'schedule')),
                         '"every 30.0 seconds"')
        task10 = tq.get_task_by_cname('crontest')
        self.assertEqual(task00, task10)
        task11 = tq.get_task_by_cname('schedtest')
        self.assertEqual(task01, task11)
        task = tq._get_task_by_cname('schedtest')
        task.dispatch()
        task21 = tq.get_task_by_cname('schedtest')
        self.assertNotEqual(task11, task21)
        now = utcnow()
        self.assertTrue(now - timedelta(5) < task21['last_run_at'] < now)
        task11.pop('last_run_at')
        task11.pop('uuid')
        task21.pop('last_run_at')
        task21.pop('uuid')
        self.assertEqual(task11, task21)

    def test_iter_tasks(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        for i in range(51):
            tq.add_task(
                {'method': 'GET',
                 'url': 'http://httpbin.org/get'},
                cname='task{0}'.format(2 * i))
            tq.add_task(
                {'method': 'POST',
                 'url': 'http://httpbin.org/post',
                 'payload': 'test'},
                cname='task{0}'.format(2 * i + 1),
                countdown=1)
        self.assertEqual(tq.count_tasks(), 102)
        offset93 = tq.iter_tasks(93)
        task93 = next(offset93)
        self.assertEqual(task93['cname'], 'task93')
        j = 0
        now = utcnow()
        delta = timedelta(seconds=5)
        for task in tq.iter_tasks(per_pipeline=17):
            self.assertEqual(task['cname'], 'task{0}'.format(j))
            if j % 2:
                self.assertEqual(task['request']['method'], 'POST')
                self.assertTrue(
                    now - delta < task['eta'] < now + delta)
            else:
                self.assertEqual(task['request']['method'], 'GET')
            j += 1
        return tq

    def test_list_tasks(self):
        tq = self.test_iter_tasks()
        tasks = tq.list_tasks(17, 83)
        self.assertEqual(len(tasks), 83)
        for i, task in zip(range(17, 100), tasks):
            self.assertEqual(task['cname'], 'task{0}'.format(i))

    def test_get_task(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        for i in range(5):
            tq.add_task({'method': 'GET',
                         'url': 'http://httpbin.org'})
        task = tq.get_task(5)
        self.assertEqual(task['status'], 'new')
        self.assertEqual(task['id'], 5)
        self.assertEqual(task['cname'], None)
        self.assertRaises(TaskNotFound, tq.get_task, 6)

    def test_get_task_by_uuid(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        for i in range(5):
            task = tq.add_task({'method': 'GET',
                                'url': 'http://httpbin.org'})
        task = tq.get_task_by_uuid(task['uuid'])
        self.assertEqual(task['status'], 'new')
        self.assertEqual(task['id'], 5)
        self.assertEqual(task['cname'], None)
        self.assertRaises(TaskNotFound, tq.get_task_by_uuid, 'notuuid')

    def test_get_task_by_cname(self):
        tq = TaskQueue('test')
        tq.bind_redis(self.conn1)
        task = tq.add_task({'method': 'GET',
                            'url': 'http://httpbin.org'},
                           cname='tasktest')
        task = tq.get_task_by_cname('tasktest')
        self.assertEqual(task['status'], 'new')
        self.assertEqual(task['id'], 1)
        self.assertEqual(task['cname'], 'tasktest')
        self.assertRaises(TaskNotFound, tq.get_task_by_cname, 'notexist')

    def test_delete_task(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        tq.add_task({'method': 'GET',
                     'url': 'http://httpbin.org'},
                    cname='deletetask')
        tq.delete_task(1)
        self.assertRaises(TaskNotFound, tq.delete_task, 2)
        self.assertFalse(conn1.exists(tq._TaskQueue__metakey(1)))
        self.assertFalse(conn1.exists(tq._TaskQueue__cnamekey('deletetask')))
        self.assertFalse(conn1.exists(tq._TaskQueue__uuidkey()))
        self.assertEqual(conn1.hget(*tq._TaskQueue__hincrkey()), b'1')

    def test_delete_task_by_uuid(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        task = tq.add_task({'method': 'GET',
                            'url': 'http://httpbin.org'})
        tq.delete_task_by_uuid(task['uuid'])
        self.assertRaises(TaskNotFound, tq.delete_task_by_uuid, 'notuuid')
        self.assertFalse(conn1.exists(tq._TaskQueue__metakey(1)))
        self.assertFalse(conn1.exists(tq._TaskQueue__uuidkey()))

    def test_delete_task_by_cname(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        tq.add_task({'method': 'GET',
                     'url': 'http://httpbin.org'},
                    cname='deletetask')
        tq.delete_task_by_cname('deletetask')
        self.assertFalse(conn1.exists(tq._TaskQueue__metakey(1)))
        self.assertFalse(conn1.exists(tq._TaskQueue__cnamekey('deletetask')))
        self.assertFalse(conn1.exists(tq._TaskQueue__uuidkey()))
        self.assertRaises(TaskNotFound, tq.delete_task_by_uuid, 'notexist')

    def test_update_status(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        tq.add_task({'method': 'GET',
                     'url': 'http://httpbin.org'},
                    cname='deletetask')
        tq._update_status(1, 'running', 'new', 'delayed')
        self.assertRaises(
            TaskStatusNotMatched,
            tq._update_status,
            1, 'running', 'new', 'delayed')

    def test_task_dispatch(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        tq.add_task({'method': 'POST',
                     'url': 'http://httpbin.org/post',
                     'payload': '{"a":"b"}',
                     'timeout': 30},
                    cname='thistask', countdown=42)
        task = tq._get_task(1)
        resp = task._dispatch(**task.request)
        r = resp.json()
        self.assertEqual(r['headers']['X-Asynx-Taskuuid'], task.uuid)
        self.assertEqual(r['headers']['X-Asynx-Taskcname'], 'thistask')
        self.assertEqual(r['headers']['User-Agent'], user_agent())
        self.assertEqual(r['data'], '{"a":"b"}')
        self.assertTrue('X-Asynx-Tasketa' in r['headers'])
        task.dispatch()
        self.assertFalse(conn1.exists(tq._TaskQueue__metakey(1)))
        self.assertFalse(conn1.exists(tq._TaskQueue__cnamekey('deletetask')))
        self.assertFalse(conn1.exists(tq._TaskQueue__uuidkey()))

    def test_task_callback(self):
        conn1 = self.conn1
        tq = TaskQueue('test')
        tq.bind_redis(conn1)
        tq.add_task({'method': 'POST',
                     'url': 'http://httpbin.org/post',
                     'payload': '{"a":"b"}',
                     'timeout': 30},
                    cname='thistask', countdown=42,
                    on_success='http://httpbin.org/post')
        task = tq._get_task(1)
        resp = task._dispatch(**task.request)
        subtask = task._dispatch_callback(task.on_success, resp)
        self.assertEqual(subtask['id'], 2)
        subtask = tq._get_task(2)
        resp = subtask._dispatch(**subtask.request)
        r = resp.json()
        self.assertEqual(r['headers']['X-Asynx-Chained'],
                         'http://httpbin.org/post')
        self.assertEqual(r['headers']['X-Asynx-Chained-Taskcname'],
                         'thistask')
        self.assertTrue('X-Asynx-Chained-Tasketa' in r['headers'])
        payload = r['json']
        pr = anyjson.loads(not_bytes(payload['content']))
        self.assertEqual(pr['headers']['X-Asynx-Taskuuid'], task.uuid)
        self.assertEqual(pr['headers']['X-Asynx-Taskcname'], 'thistask')
        self.assertEqual(pr['headers']['User-Agent'], user_agent())
        self.assertEqual(pr['data'], '{"a":"b"}')
        self.assertTrue('X-Asynx-Tasketa' in pr['headers'])
