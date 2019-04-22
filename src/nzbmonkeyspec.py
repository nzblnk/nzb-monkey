# -*- coding: utf-8 -*-

from configobj import ConfigObj


def getSpec():
    return ConfigObj("""
[GENERAL]
# Target for handling nzb files - EXECUTE, SABNZBD, NZBGET or SYNOLOGYDLS
target = string(default = 'EXECUTE')

# Let the monkey choose a category. Values are: off, auto, manual
categorize = 'option("off", "auto", "manual", default="off")'

# Debug outputs
debug = boolean(default = False)

[EXECUTE]
# Extend password to filename {{password}}
passtofile = boolean(default = True)
# Copy password to clipboard
passtoclipboard = boolean(default = False)
# Path to save nzb files
nzbsavepath = string(default = '')
# Don't execute default programm for .nzb
dontexecute = boolean(default = True)
# Delete old NZB files from nzbsavepath
clean_up_enable = boolean(default = False)
# NZB files older than x days will be deleted
clean_up_max_age = string(default = '2')
# Last clean up run. Only daily clean up. Set to 0 to force run on next start
clean_up_last_run = string(default = '0')

[SABNZBD]
# SABnzbd Hostname
host = string(default = 'localhost')
# SABnzbd Port
port = string(default = '8080')
# Use https
ssl = boolean(default = False)
# NZB Key
nzbkey = string(default = '')
# Basic Auth Username
basicauth_username = string(default = '')
# Basic Auth Password
basicauth_password = string(default = '')
# Basepath
basepath = string(default = 'sabnzbd')
# Category
category = string(default = '')
# Add the nzb paused to the queue
addpaused = boolean(default = False)

[NZBGET]
# NZBGet Host
host = string(default = 'localhost')
# NZBGet Port
port = string(default = '6789')
# Use https
ssl = boolean(default = False)
# NZBGet Username
user = string(default = '')
# NZBGet Password
pass = string(default = '')
# Basepath
basepath = string(default = 'xmlrpc')
# NZBGet Category
category = string(default = '')
# Add the nzb paused to the queue
addpaused = boolean(default = False)

[SYNOLOGYDLS]
# Downloadstation Host
host = string(default = 'localhost')
# Downloadstation Port
port = string(default = '5000')
# Use https
ssl = boolean(default = False)
# Downloadstation Username
user = string(default = '')
# Downloadstation Password
pass = string(default = '')
# Basepath
basepath = string(default = 'webapi')

[NZBCheck]
# Don't skip failed nzb
skip_failed = boolean(default = True)
# Max missing failed segments
max_missing_segments_percent = float(default = 2.)
# Max missing failed files
max_missing_files = integer(default = 2)
# Use always all Searchengines to find the best NZB
best_nzb = boolean(default = True)

[CATEGORIZER]
# Place your category and you regex here
# Please uncomment the following lines

# series = (s\d+e\d+|s\d+ complete)
# movies = (x264|xvid|bluray|720p|1080p|untouched)


[Searchengines]
# Set values between 0-9
# 0 = disabled; 1-9 = enabled; 1-9 are also the order in which the search engines are used
# More than 1 server with the same order number is allowed
# Enable Binsearch
binsearch =  integer(default = 1)
# Enable Binsearch - Alternative Server
binsearch_alternative = integer(default = 1)
# Enable NZBIndex
nzbindex =  integer(default = 1)
# Enable NZBKing
nzbking =  integer(default = 1)
# Enable Newzleech
newzleech =  integer(default = 1)
""".split('\n'))
