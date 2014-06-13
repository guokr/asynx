#! /bin/sh

pip uninstall gevent simplejson -y
set -e
nosetests --with-doctest -s asynx-core
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    nosetests --with-doctest -s asynxd
    asynxd restart
    nosetests --with-doctest -s asynx
    asynxd stop
fi
pip install gevent simplejson
nosetests --with-doctest -s asynx-core
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    nosetests --with-doctest -s asynxd
    asynxd restart
    nosetests --with-doctest -s asynx
    asynxd stop
fi
