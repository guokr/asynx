# -*- coding: utf-8 -*-
from os import path

from apis import app, celeryapp

__all__ = ['app', 'celeryapp']

with open(path.join(path.dirname(__file__), 'version.txt')) as fp:
    __version__ = fp.read().strip()
