#! /bin/sh
set -e

pip install -r asynx-core/requirements.txt
pip install -r asynx-core/test-requirements.txt
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    pip install asynx-core/
    pip install -r asynx-server/requirements.txt
    pip install -r asynx-server/test-requirements.txt
fi
