# -*- coding: utf-8 -*-

import pytz
from datetime import datetime

from unittest import TestCase
from voluptuous import MultipleInvalid

from asynxd import forms


class FormsTestCase(TestCase):

    def test_add_task_form(self):
        _form = forms.add_task_form

        data = {'request': {'url': 'ftp://example.com'}}
        self.assertRaises(MultipleInvalid, _form, data)

        data['request']['url'] = 'http://httpbin.org'
        expect = {'request': {'method': 'GET',
                              'url': 'http://httpbin.org'}}
        self.assertEqual(_form(data), expect)

        data['request'].update({
            'method': 'post',
            'url': 'http://httpbin.org/post'})
        expect['request'].update({
            'method': 'POST',
            'url': 'http://httpbin.org/post'})
        self.assertEqual(_form(data), expect)

        data.update({
            'on_success': {
                'request': {'url': 'http://httpbin.org/get'}
            },
            'on_failure': '__report__',
            'on_complete': 'http://httpbin.org/post'})
        expect.update({
            'on_success': {
                'request': {'method': 'GET',
                            'url': 'http://httpbin.org/get'}
            },
            'on_failure': '__report__',
            'on_complete': 'http://httpbin.org/post'})
        self.assertEqual(_form(data), expect)

        data['countdown'] = None
        expect['countdown'] = None
        self.assertEqual(_form(data), expect)

        data['countdown'] = 42
        expect['countdown'] = 42.0
        self.assertEqual(_form(data), expect)

        data['request']['headers'] = {123: '321'}
        self.assertRaises(MultipleInvalid, _form, data)

        data['request']['headers'] = {'X-Test': '321'}
        expect['request']['headers'] = {'X-Test': '321'}
        self.assertEqual(_form(data), expect)

        data['eta'] = 0xffffffff
        self.assertRaises(MultipleInvalid, _form, data)

        data['eta'] = None
        expect['eta'] = None
        self.assertEqual(_form(data), expect)

        data['eta'] = '2014-03-14 15:09:26.535898Z'
        expect['eta'] = pytz.utc.localize(
            datetime(2014, 3, 14, 15, 9, 26, 535898))
        self.assertEqual(_form(data), expect)

        data['eta'] = '2014-03-14 15:09:26.535898+0800'
        expect['eta'] = pytz.timezone('Asia/Shanghai').localize(
            datetime(2014, 3, 14, 15, 9, 26, 535898))
        self.assertEqual(_form(data), expect)
