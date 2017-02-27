# -*- coding: utf-8 -*-
"""

History
v0.1.10
+ requests 2.13.0 (incl openssl)
+ Bugfixes
+ Newzleech search engine

v0.1.9
+ Added option addpaused
+ Lot of bugfixes

v0.1.8
+ Reorg code
+ Added verbose output
+ Added debug log writer to file

v0.1.7
+ Added Search for best NZB
+ Added NZB Folder clean up

v0.1.6
+ Added colorama
+ Added argparse to control NZB-Monkey by arguments
+ Searchengines can be disabled if down or faulted

v0.1.5
+ Separate missing module check
+ Exception Handling for external module import

v0.1.4
+ Switched to configobj

v0.1.3
+ Added dontexecute

v0.1.2
+ Added clipboard parsing

v0.1.1
+ Added NZB-validation

v0.1.0
+ Complete rewrite in python

"""

__version__ = '0.1.10'
__requires__ = ['pyperclip', 'requests', 'configobj', 'colorama', 'cryptography']
