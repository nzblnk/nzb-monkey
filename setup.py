#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import datetime
from distutils.core import setup

try:
    import py2exe
except ImportError:
    if len(sys.argv) >= 2 and sys.argv[1] == 'py2exe':
        print("Cannot import py2exe, please install!", file=sys.stderr)
        exit(1)

# Load version
exec(compile(open('src/version.py').read(), 'src/version.py', 'exec'))

params = {
    'console': [{
        "script": "./src/nzbmonkey.py",
        "dest_base": "nzbmonkey",
        "icon_resources": [(0, "./resource/nzb-monkey-icons.ico")],
        "product_name": "NZB-Monkey™",
        "version": __version__,
        "company_name": "NZBLNK, Inc.",
        "copyright": "© %d, NZBLNK, Inc." % datetime.datetime.now().year
    }],
    'options': {
        "py2exe": {
            "bundle_files": 1,
            "compressed": 1,
            "optimize": 2,
            'includes': 'nzblnkconfig',
            'excludes': ['doctest','pdb','unittest','difflib','inspect'],
            "dist_dir": 'dist'
        }
    },
    'zipfile': None
}

setup(
    name='nzb-monkey-py',
    version=__version__,
    packages=[''],
    url='',
    license='',
    author='',
    author_email='',
    description='',
    requires=__requires__,
    **params
)
