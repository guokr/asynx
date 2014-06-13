#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import setuptools

try:
    # work-around to avoid "setup.py test" error
    # see: http://bugs.python.org/issue15881#msg170215
    import multiprocessing
    assert multiprocessing
except ImportError:
    pass

py_version = sys.version_info

with open(os.path.join(os.getcwd(),
                       'asynxd/version.txt')) as fp:
    VERSION = fp.read().strip()


def strip_comments(l):
    return l.split('#', 1)[0].strip()


def reqs(*filename):
    requires = set([])
    for fname in filename:
        with open(os.path.join(os.getcwd(),
                               fname)) as fp:
            requires |= set(filter(None, [strip_comments(l)
                                          for l in fp.readlines()]))
    return list(requires)

if py_version[0:2] == (2, 6):
    install_requires = reqs('requirements.txt',
                            'py26-requirements.txt')
else:
    install_requires = reqs('requirements.txt')

setup_params = dict(
    name="asynxd",
    version=VERSION,
    url="https://github.com/guokr/asynx",
    author='Guokr',
    author_email="bug@guokr.com",
    description=('RESTful server side of an open source, distributed, '
                 'and web / HTTP oriented taskqueue & scheduler service '
                 'inspired by Google App Engine'),
    packages=['asynxd'],
    install_requires=install_requires,
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
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'],
    entry_points={
        'console_scripts': 'asynxd = asynxd.manage:main'
    },
    test_suite="nose.collector",
    zip_safe=True)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
