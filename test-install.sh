#! /bin/sh

pip uninstall asynx-core asynx-server -y

set -e
pip install asynx-core/
pip install -r asynx-core/test-requirements.txt
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    pip install asynx-server/
    pip install -r asynx-server/test-requirements.txt
fi
