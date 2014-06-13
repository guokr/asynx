#! /usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
from collections import namedtuple

import sh
from flask.ext.script import Manager

from . import app

manager = Manager(app)

_shkw = {'_out': sys.stdout, '_err': sys.stderr,
         '_tty_in': True, '_tty_out': True}


def _celery():
    conf = app.config
    logdir = conf['CELERY_LOGDIR']
    logfile = os.path.join(logdir, 'celery.log')
    pidfile = os.path.join(logdir, 'celery.pid')
    g = namedtuple('celeryconf', 'APP ENABLE_BEAT LOGLEVEL '
                   'DEBUG_LOGLEVEL POOL LOGFILE PIDFILE')(
                       'asynxd:celeryapp',
                       conf['CELERY_ENABLE_BEAT'],
                       conf['CELERY_DAEMON_LOGLEVEL'],
                       conf['CELERY_DEBUG_LOGLEVEL'],
                       conf.get('CELERYD_POOL', False),
                       logfile, pidfile)
    try:
        os.makedirs(logdir)
    except OSError:
        pass
    return g


def _gunicorn():
    conf = app.config
    logdir = conf['LOGDIR']
    logfile = os.path.join(logdir, 'gunicorn.log')
    pidfile = os.path.join(logdir, 'gunicorn.pid')
    g = namedtuple('gunicornconf', 'APP BIND WORKERS LOGLEVEL '
                   'DEBUG_LOGLEVEL LOGFILE PIDFILE')(
                       'asynxd:app',
                       conf['BIND'],
                       conf['WORKERS'],
                       conf['DAEMON_LOGLEVEL'],
                       conf['DEBUG_LOGLEVEL'],
                       logfile, pidfile)
    try:
        os.makedirs(logdir)
    except OSError:
        pass
    return g


def safe_wait(p):
    try:
        p.wait()
    except (KeyboardInterrupt, SystemExit):
        p.terminate()
        p.wait()
        return 1


def say_ok():
    print('\x1b[1m\x1b[32mOK\x1b[0m')


def quoted_path():
    from pipes import quote
    return quote(os.environ['PATH'])


def _celery_opts(app, **kw):
    pass

celery_manager = Manager(_celery_opts)
celery_manager.__doc__ = ('Celery sub commands. Runs `{0} celery` '
                          'for more help.').format(sys.argv[0])
manager.add_command('celery', celery_manager)


def celery_debug():
    """Starting a celery worker in console mode"""
    g = _celery()
    p = sh.celery.worker(app=g.APP,
                         loglevel=g.DEBUG_LOGLEVEL,
                         pool=g.POOL,
                         _bg=True, **_shkw)
    safe_wait(p)
celery_debug.__name__ = 'debug'
celery_manager.command(celery_debug)


def celery_start():
    """Starting celery worker as a daemon"""
    g = _celery()
    sh.celery.multi.start('asynx-celery',
                          app=g.APP,
                          loglevel=g.LOGLEVEL,
                          pool=g.POOL,
                          logfile=g.LOGFILE,
                          pidfile=g.PIDFILE,
                          **_shkw)
celery_start.__name__ = 'start'
celery_manager.command(celery_start)


def celery_stop():
    """Stopping a daemonized celery worker"""
    g = _celery()
    sh.celery.multi.stop('asynx-celery',
                         pidfile=g.PIDFILE,
                         **_shkw)
celery_stop.__name__ = 'stop'
celery_manager.command(celery_stop)


def celery_kill():
    """Killing a daemonized celery worker"""
    g = _celery()
    sh.celery.multi.kill('asynx-celery',
                         pidfile=g.PIDFILE,
                         **_shkw)
    if g.ENABLE_BEAT:
        print('Warning: process celerybeat may not be killed properly, '
              'please do a recheck and kill it mannually if necessary',
              file=sys.stderr)
celery_kill.__name__ = 'kill'
celery_manager.command(celery_kill)


def celery_restart():
    """Restarting celery worker as a daemon"""
    g = _celery()
    sh.celery.multi.restart('asynx-celery',
                            app=g.APP,
                            pool=g.POOL,
                            loglevel=g.LOGLEVEL,
                            logfile=g.LOGFILE,
                            pidfile=g.PIDFILE,
                            **_shkw)
celery_restart.__name__ = 'restart'
celery_manager.command(celery_restart)


def celery_log():
    """Tailing print log for celery daemon"""
    g = _celery()
    p = sh.tail(g.LOGFILE, follow=True, _bg=True, **_shkw)
    safe_wait(p)
celery_log.__name__ = 'log'
celery_manager.command(celery_log)


@manager.command
def start():
    """Starting the restful server"""
    g = _gunicorn()
    print('Starting asynxd:', end=' ')
    sh.gunicorn(g.APP,
                '--log-level', g.LOGLEVEL,
                '--log-file', g.LOGFILE,
                daemon=True,
                bind=g.BIND,
                workers=g.WORKERS,
                pid=g.PIDFILE,
                **_shkw)
    say_ok()


@manager.command
def stop():
    """Stopping the restful server"""
    g = _gunicorn()
    if not os.path.isfile(g.PIDFILE):
        print('pidfile "{0}" is not found'.format(g.PIDFILE),
              file=sys.stderr)
        return 1
    print('Stopping asynxd:', end=' ')
    with open(g.PIDFILE) as fp:
        sh.kill(fp.read().strip(), **_shkw)
    say_ok()


@manager.command
def restart():
    """Restarting the restful server"""
    stop()
    start()


@manager.command
def reload():
    """Reloading the restful server"""
    g = _gunicorn()
    if not os.path.isfile(g.PIDFILE):
        print('pidfile "{0}" is not found'.format(g.PIDFILE),
              file=sys.stderr)
        return 1
    print('Reloading asynxd:', end=' ')
    with open(g.PIDFILE) as fp:
        sh.kill('-HUP', fp.read().strip(), **_shkw)
    say_ok()


def main():
    manager.run()

if __name__ == '__main__':
    main()
