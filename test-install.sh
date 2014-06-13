#! /bin/sh

pip uninstall asynx-core asynxd -y

set -e
pip install asynx-core/
pip install -r asynx-core/test-requirements.txt
if python --version 2>&1 | grep 'Python 2' >/dev/null ; then
    pip install asynxd/
    pip install -r asynxd/test-requirements.txt
fi
