#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name='leankit',
    version='0.0.1',
    description='LeanKit API in Python',
    long_description=readme + '\n\n' + history,
    author='Rick Harding',
    author_email='rick.harding@canonical.com',
    url='https://github.com/mitechie/leankit',
    packages=[
        'leankit',
    ],
    package_dir={'leankit': 'leankit'},
    include_package_data=True,
    install_requires=[
        'requests'
    ],
    license="BSD",
    zip_safe=False,
    keywords='leankit',
    entry_points={
        'console_scripts':
        ['leankit2poker=leankit.scripts.leankit2poker:main']
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
    ],
    test_suite='tests',
)
