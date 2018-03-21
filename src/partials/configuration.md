## Configuration

The configuration file (ending `.cfg`) is in the same folder like the main application.
Open it with your favorite editor.

It contains so called "sections" witch are marked by square brackets.

### GENERAL section

The `GENERAL` section has only two options:

```
[GENERAL]
target = EXECUTE
categorize = off
```

The first key here is `target`. It can have four values:

- `EXECUTE` - The NZB is handled by a software registered to the filetype `.NZB` on
  same machine. Comparable by downloading the NZB file to the hard disk and
  executing (double clicking) it.  
  
- `SABNZBD` - The NZB is pushed to a [SABnzbd](https://sabnzbd.org) on the same
  network or computer. Described [here](#sabnzbd-section) 
  
- `NZBGET` - The NZB is pushed to a [NZBGet](http://nzbget.net/) on the same
  network or computer.  Described [here](#nzbget-section) 
  
- `SYNOLOGYDLS` - The NZB is pushed to a [Synology Download
  Station](https://www.synology.com/en-us/knowledgebase/DSM/help/DownloadStation/DownloadStation_desc)
  on the same
  network or computer.  Described [here](#synologydls-section)
  
  `EXECUTE` is the default.
  
The second one is `categorize` which switches the categorisation modes. Options are here:

- `off` - The default. Does nothing.
 
- `auto` - The monkey tries to guess the category by the tagname. More information about
 it [here](#categorizer-section).

- `manual` - Before sending the NZB file to your download target, the monkey "asks" it for
 your categories. These will be shown and you have to choose one by pressing the
 corresponding number on you keyboard. This only works with _NZBGet_  and _SabNZBd_.

### EXECUTE section

```
[EXECUTE]
passtofile = True
passtoclipboard = True
nzbsavepath = c:\path\to\your\nzb\files\
dontexecute = False
clean_up_enable = False
clean_up_max_age = 1
```

Here is everything specified which belongs to the local handling of NZB files.
This brings some handy options making the lives easier even without a downloading
solution like NZBGet or SABnzbd.


- `passtofile` enables the filename extension by an optional password in curly brackets `{{password}}`. 
  It's a boolean value, which means it holds the word "True" or "False". Default is `True`. 

- `passtoclipboard` enables the monkey to copy the optional password into
  your clipboard. Default is `False`. 


- `nzbsavepath` holds the path to the folder where your NZB files are stored to.

- `dontexecute` if set to True, the monkey does not "start" the NZB file after
  downloading. This is great for just downloading the NZBs.  Default is `True`. 

- `clean_up_enable` makes sure that old NZBs are deleted from your download folder.
  Default is `False`. 

- `clean_up_max_age` sets the time in days how long the NZBs kept. Default is `2` days. 

### SABNZBD section

For SABnzbd users is the section
```
[SABNZBD]
host = localhost
port = 8080
ssl = False
nzbkey =
basicauth_username =
basicauth_password =
basepath = sabnzbd
category =
addpaused = False
```
interesting. Here are all the parameters specific to SABnzbd set up:

- `host` sets the hostname or IP of your SABnzbd
- `port` sets the port. `8080` is default for HTTP and `9090` is default for HTTPS.
- `ssl` enables SSL/TLS when set to `True`. Default is `False`.
- `nzbkey` is the "**API** Key" (was the NZB Key in the past!) from your SABnzbd
 configuration (General/ API Key)
- `basicauth_username` and `basicauth_password` are used to do a basic authentication
 (fill out only if you need it)
- `basepath` is the API endpoint. Change this only if needed.
- `category` is one of the configured categories (Categories). Empty is default category. If
 category choosing is enabled, this will be overwritten.
- `addpaused` can be set to `True` if every NZB should be added in pause state

### NZBGET section

For NZBGet users is the section
```
[NZBGET]
host = localhost
port = 6789
ssl = False
user = nzbget
pass = tegbzn
category =
basepath = xmlrpc
addpaused = False
```
interesting. Here are all the parameters specific to NZBGet set up:

- `host` sets the hostname or IP of your NZBGet
- `port` sets the port.  Default is `6789`.
- `ssl` enables SSL/TLS when set to `True`. Default is `False`.
- `user` is the "AddUsername" set in your NZBGet Security settings.
- `pass` is the "AddPassword" set in your NZBGet Security settings.
- `basepath` is the API endpoint. Change this only if needed.
- `category` is one of the configured categories in your NZBGet Categories settings.
  Empty is no category. If category choosing is enabled, this will be overwritten.
- `addpaused` can be set to `True` if every NZB should be added in pause state

### SYNOLOGYDLS section

Owner of a Synology DiskStation Manager can use the [Download
Station](https://www.synology.com/en-us/knowledgebase/DSM/help/DownloadStation/DownloadStation_desc). To configure
it this section is used.

```
[SYNOLOGYDLS]
host = localhost
port = 5000
ssl = False
user = 
pass = 
basepath = webapi
```
- `host` sets the hostname or IP of your Synology
- `port` sets the port.  Default is `5000`. For SSL its normally `5001`
- `ssl` enables SSL/TLS when set to `True`. Default is `False`.
- `user` is the user on your DiskStation who has access to the Download Station software
- `pass` is the corresponding password.
- `basepath` is the API endpoint. Change this only if needed.

### NZBCheck section

The `NZBCheck` section lets you configure the NZB verification mechanism.

```
[NZBCheck]
skip_failed = True
max_missing_segments_percent = 2.0
max_missing_files = 2
best_nzb = True
```
- `skip_failed` on `True` stops the processing on broken NZBs. This is great
  for new uploads. Some search engines hand out "broken" NZBs.
  Default is `True`.
- `max_missing_segments_percent` defines the threshold in percent where the monkey
  should stop accepting the NZB. Default is `2.0`.
- `max_missing_files` defines the threshold in total number of missing files where the
  monkey should stop accepting the NZB. Default is `1`.
- `best_nzb` set on `True` checks all search engines and chooses the best one.
  `False` stops after the first successful NZB.
  Default is `True`.

### Searchengines section

In the `Searchengines` section are the order and the use of search engines
configurable.

```
[Searchengines]
binsearch = 1
binsearch_alternative = 2
nzbking = 3
nzbindex = 4
```
All keys are the corresponding search engines. A value of `0` means disabled.
A value bigger than `0` means enabled. Bigger numbers mean a lower priority.
A search engine with a `3` is checked after one with a `2`.
Default for all search engines is `1`.

### CATEGORIZER section

The `CATEGORIZER` section defines the "searchterms" for a category guessing. It looks like this:

```
[CATEGORIZER]
series = (s\d+e\d+|s\d+ complete)
movies = (x264|xvid|bluray|720p|1080p|untouched)
```
There weird characters are [Regular Expressions](https://en.wikipedia.org/wiki/Regular_expression). Each value of this
entries is tested against the current tagline. A positive finding stops the testing and the keyword (ex. "series") is
used as category.

## Finally

After successful installation you can click a link 
[@@nzblnk like this](nzblnk:?t=UbuntuStudio-14.04.5-DVD-AMD64&h=ubuntustudio-14.04.5-dvd-amd64.iso.nzb)
and the NZB Monkey should open.