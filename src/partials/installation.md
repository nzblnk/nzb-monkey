## Installation

The NZB Monkey is at the moment only available for [Windows](#windows-platform)
and [Linux](#linux-platform) platform. For macOS user we are working hard on a
solution to bring you the same experience like the other OSs.

### Windows Platform

Please **create a folder** where you finally want to locate the NZB Monkey. Copy
the contents of the downloaded ZIP archive (the `nzbmonkey.exe`) into this folder
and start the `nzbmonkey.exe` (by double clicking it).

If a error appears the system asking for `MSVCR100.DLL` please download the
[Microsoft Visual C++ 2010 Redistributable Package (x86)](https://www.microsoft.com/en-US/download/details.aspx?id=5555)
and install it.

After the first start is a configuration in the registry saved, which enables the
monkey to catch all clicks on a [NZBLNK™](https://nzblnk.github.io) link.  

> **Important**: Please do not move the EXE file after the first start. If you want
to move the exe somewhere else on your computer please remove your CFG file
(rename it or move it somewhere else) and start the monkey on its new location.
The configuration in the registry is now updated. Copy your config back afterwards.

If everything went right there should be a `nzbmonkey.cfg` nearby the EXE file
and it opened automatically with Notepad. Please continue reading with the
[configuration](#configuration).

### Linux platform

Please **create a folder** where you finally want to locate the NZB Monkey.
Move the downloaded tbz2 file into this folder and extract it with
`bzip2 -dc <tar filename> | tar xvf -` e.g. `bzip2 -dc nzbmonkey-v0.2.6-linux.tbz2 | tar xvf -`.  
Execute the config script `./nzblnkconfig.py`, which enables the monkey to catch
all clicks on a [NZBLNK™](https://nzblnk.github.io) link and checks all dependencies.  

If you got the following error you should install pip3:
```
Traceback (most recent call last):
  File "./nzblnkconfig.py", line 6, in <module>
    import distutils.spawn
ModuleNotFoundError: No module named 'distutils.spawn'
```

Dependencies output example:

    Missing module(s)!
    To use NZB-Monkey you have to install the missing module(s) use
    
    pip3 install --user pyperclip requests configobj colorama
    to install the missing module(s) in your home directory,
    
    sudo -H pip3 install pyperclip requests configobj colorama
    to install the missing module(s) globally to your client/server
    
    or use your package manager to install the missing Python3 module(s): pyperclip requests configobj colorama.
    
    To have a working pyperclip module you have to install xsel or xclip, see also pyperclip doku:
    https://pyperclip.readthedocs.io/en/latest/introduction.html
Resolve all dependencies before you continue.
> **Important**: Please do not move the NZB Monkey files after this
[NZBLNK™](https://nzblnk.github.io) registration.  
If you want to move them somewhere else on your computer, please execute the config script `./nzblnkconfig.py`
on the new location to update the [NZBLNK™](https://nzblnk.github.io) registration.

Now start NZB-Monkey `./nzbmonkey.py`. This creates a default configuration file `nzbmonkey.cfg`
and opened it with the default editor.

Please continue reading with the [configuration](#configuration).
