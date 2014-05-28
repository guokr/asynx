#! /bin/sh
set -e

nosetests --with-doctest -s asynx-core
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    nosetests --with-doctest -s asynx-server
fi