# -*- coding: utf-8 -*-

from unittest import TestCase
from datetime import datetime, timedelta

from pytz import utc
from asynx import TaskQueueClient


class TQClientTestCase(TestCase):

    def test_add_task(self):
        tqc = TaskQueueClient('http://localhost:17969', 'test')
        # a simple task
        task = tqc.add_task(url='http://httpbin.org/get')
        self.assertEqual(task['status'], 'new')
        self.assertEqual(task['eta'], None)
        self.assertEqual(task['request']['url'], 'http://httpbin.org/get')
        self.assertEqual(task['countdown'], None)

        # a delayed POST task
        task = tqc.add_task(url='http://httpbin.org/post',
                            method='POST',
                            countdown=200)
        self.assertEqual(task['status'], 'delayed')
        self.assertTrue(195 < task['countdown'] <= 200)
        utcnow = utc.localize(datetime.utcnow())
        delta = timedelta(seconds=205)
        self.assertTrue(utcnow < task['eta'] < utcnow + delta)

    def test_scheduled_task(self):
        tqc = TaskQueueClient('http://localhost:17969', 'test')
        kw = {'url': 'http://httpbin.org/get',
              'schedule': '*/10 * * * *'}
        self.assertRaises(tqc.ResponseError, tqc.add_task, **kw)
        kw['cname'] = 'test the crontab'
        task = tqc.add_task(**kw)
        self.assertEqual(task['schedule'], '*/10 * * * *')

    def test_list_tasks(self):
        tqc = TaskQueueClient('http://localhost:17969', 'test')
        for i in range(10):
            tqc.add_task(url='http://httpbin.org/get')
        result = tqc.list_tasks()
        self.assertTrue(len(result['items']) > 10)
        self.assertTrue(result['total'] > 10)

    def test_get_task(self):
        tqc = TaskQueueClient('http://localhost:17969', 'test')
        task = tqc.add_task(url='http://httpbin.org/get')
        task_get = tqc.get_task(task['id'])
        self.assertEqual(task, task_get)

    def test_delete_task(self):
        tqc = TaskQueueClient('http://localhost:17969', 'test')
        task = tqc.add_task(url='http://httpbin.org/get')
        self.assertEqual(tqc.delete_task(task['id']), None)
        self.assertRaises(tqc.ResponseError, tqc.get_task, task['id'])
