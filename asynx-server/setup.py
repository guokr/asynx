#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import setuptools

try:
    # work-around to avoid "setup.py test" error
    # see: http://bugs.python.org/issue15881#msg170215
    import multiprocessing
    assert multiprocessing
except ImportError:
    pass

with open(os.path.join(os.getcwd(),
                       'asynx_server/version.txt')) as fp:
    VERSION = fp.read().strip()


def strip_comments(l):
    return l.split('#', 1)[0].strip()


def reqs(filename):
    with open(os.path.join(os.getcwd(),
                           filename)) as fp:
        return filter(None, [strip_comments(l)
                             for l in fp.readlines()])

setup_params = dict(
    name="asynx-server",
    version=VERSION,
    url="https://github.com/guokr/asynx",
    author='Guokr',
    author_email="bug@guokr.com",
    description=('An open source, distributed taskqueue / scheduler '
                 'service inspired by Google App Engine'),
    packages=['asynx_server'],
    install_requires=reqs('requirements.txt'),
    tests_require=reqs('test-requirements.txt'),
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'],
    entry_points={
        'console_scripts': 'asynx = asynx_server.manage:main'
    },
    test_suite="nose.collector",
    zip_safe=True)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
