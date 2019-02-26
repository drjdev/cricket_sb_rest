#!/usr/bin/env python3

from setuptools import setup

config = {
    'name': 'scoreboardrest',
    'version': '1.0.0',
    'packages': ['scoreboardrest'],
    'install_requires': [
        'flask',
        'flask-cors',
        'jsonschema',
        'PyCmdMessenger',
    ],
    'tests_require': ['pytest'],  
}

setup(**config)
