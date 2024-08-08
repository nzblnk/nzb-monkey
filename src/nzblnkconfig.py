#!/usr/bin/env python3
# coding: utf-8
"""
Script for windows/linux configuration
"""
import distutils.spawn
from importlib import import_module
import os
import os.path as op
import sys
from enum import Enum
from os.path import isfile
from subprocess import Popen
from subprocess import call
from time import sleep
from version import __requires__
from inspect import cleandoc

class ExeTypes(Enum):
    EXECUTE = 'EXECUTE',
    NZBGET = 'NZBGET',
    SABNZBD = 'SABNZBD'


wait_time = 1

if os.name == 'nt':  # Windows 10 has still problems :( / and float(platform.win32_ver()[0]) < 10:
    class Col:
        OK = ''
        WARN = ''
        FAIL = ''
        OFF = ''
else:
    class Col:
        OK = '\033[92m'
        WARN = '\033[93m'
        FAIL = '\033[91m'
        OFF = '\033[0m'


def config_file(cfg):
    if not isfile(cfg.filename):
        print(' Creating default config-file. ' + Col.OK + 'Please edit!' + Col.OFF)

        if sys.platform.startswith('darwin'):
            cfg['EXECUTE']['nzbsavepath'] = '/tmp/nzbmonkey'
        elif os.name == 'nt':
            cfg['EXECUTE']['nzbsavepath'] = os.environ['USERPROFILE'] + '\\Downloads\\nzbmonkey\\'
        elif os.name == 'posix':
            cfg['EXECUTE']['nzbsavepath'] = '/tmp/nzbmonkey'

        cfg.write()

        if sys.platform.startswith('darwin'):
            Popen(['open', cfg.filename])
        elif os.name == 'nt':
            Popen(['notepad', cfg.filename])
        elif os.name == 'posix':
            Popen(['xdg-open', cfg.filename])


def check_missing_modules():
    """Check for missing modules"""
    needed_modules = __requires__
    missing_modules = list()

    for moduleName in needed_modules:
        try:
            import_module(moduleName)
        except ImportError:
            missing_modules.append(moduleName)

    if missing_modules:
        print("""
{0}Missing module(s)!

{1}To use NZB-Monkey you have to install the missing module(s) use

pip3 install --user {2}
to install the missing module(s) in your home directory,

sudo -H pip3 install {3}
to install the missing module(s) globally to your client/server

or use your package manager to install the missing Python3 module(s): {4}.

To have a working pyperclip module you have to install xsel or xclip, see also pyperclip doku:
https://pyperclip.readthedocs.io/en/latest/introduction.html""".format(
            Col.FAIL, Col.OFF, ' '.join(missing_modules), ' '.join(missing_modules), ' '.join(missing_modules)))


def config_linux():

    desktop_command = None
    failed_terminal = False
    failed_mime = False
    home = op.expanduser('~')
    home_applications_path = op.normpath(op.join(home, '.local/share/applications/'))
    desktop_file_path = op.join(home_applications_path, 'nzblnk.desktop')

    working_dir = op.abspath(op.normpath(op.dirname(__file__)))
    script_path = op.join(working_dir, 'nzbmonkey.py')

    # The desktop file creates a entry in the menu, maybe we need a icon.
    desktop_file_content = cleandoc("""[Desktop Entry]
    Type=Application
    Name=NZBlnk
    Exec={0}
    Path={1}
    MimeType=x-scheme-handler/nzblnk;
    NoDisplay=true
    Terminal=false
    """)
    terminals = ({'term': 'gnome-terminal',
                  'command': '--hide-menubar --geometry=100x16 --working-directory="{1}" -e "{2} %u"'},
                 {'term': 'konsole',
                  'command': '--p tabtitle=NZB-Monkey"{0}" --hide-menubar --hide-tabbar --workdir="{1}" --nofork -e "{2} %u"'},
                 {'term': 'xfce4-terminal',
                  'command': '--title="{0}" --hide-menubar --geometry=100x16 --working-directory="{1}" -e "{2} %u"'},
                 {'term': 'mate-terminal',
                  'command': '--title="{0}" --hide-menubar --geometry=100x16 --working-directory="{1}" -e "{2} %u"'},
                 {'term': 'lxterminal',
                  'command': '--title="{0}" --geometry=100x16 --working-directory="{1}" -e "{2} %u"'},
                 {'term': 'lxterm',
                  'command': '-geometry 100x16+200+200 -e "{2} %u"'},
                 {'term': 'uxterm',
                  'command': '-geometry 100x16+200+200 -e "{2} %u"'},
                 {'term': 'xterm',
                  'command': '-geometry 100x16+200+200 -e "{2} %u"'},
                 {'term': 'alacritty',
                  'command': '--title {0} --working-directory={1} -e {2} %u'},)

    # Check terminals and create the desktop file with the first match

    print('Start Linux configuration for NZB-Monkey\n')
    print(' - Search for terminal emulators')

    for terminal in terminals:
        print('   Searching for {0} ...'.format(terminal['term']), end='', flush=True)
        path = distutils.spawn.find_executable(terminal['term'])
        if path:
            print(Col.OK + ' Found' + Col.OFF)
            desktop_command = '{0} {1}'.format(path, terminal['command'].format('NZB-Monkey', working_dir, script_path))
            sleep(wait_time)
            break
        else:
            print(Col.WARN + ' Not found' + Col.OFF)
            sleep(wait_time)

    if not desktop_command:
        failed_terminal = True
        print(Col.FAIL + '   No terminal emulator found.' + Col.OFF)
        print('   Please enter the path to your favorite terminal emulator in:')
        print('   ' + desktop_file_path)
        print('   and change parameters if necessary.')
        desktop_command = '{0} {1}'.format(
            '<Replace with path to terminal emulator>',
            "--title '{0}' --hide-menubar --geometry=100x40 --working-directory={1} --command='{2} %u'".format(
                'NZB-Monkey', working_dir, script_path
            )
        )
        sleep(wait_time * 4)

    # Write desktop file
    desktop_file_content = desktop_file_content.format(desktop_command, working_dir)
    print(" - Write desktop file to '{0}'".format(desktop_file_path))
    print('   ...', end='', flush=True)

    try:
        # Check home_applications_path
        if not op.exists(home_applications_path):
            os.makedirs(home_applications_path)
            if not op.exists(home_applications_path):
                print(Col.FAIL + ' FAILED' + Col.OFF)
                sys.exit(1)

        with open(desktop_file_path, 'w') as f:
            f.write(desktop_file_content)
            print(Col.OK + ' DONE' + Col.OFF)
    except OSError:
        print(Col.FAIL + ' FAILED' + Col.OFF)
        sys.exit(1)

    sleep(wait_time)

    # Add nzblnk to mimeapps.list
    print(' - Add nzblnk to mimeapps.list ...', end='', flush=True)
    path = distutils.spawn.find_executable('xdg-mime')
    if path:
        if call(('xdg-mime', 'default', 'nzblnk.desktop', 'x-scheme-handler/nzblnk')) == 0:
            print(Col.OK + ' DONE' + Col.OFF)
        else:
            print(Col.FAIL + ' FAILED' + Col.OFF)
            sys.exit(2)
    else:
        print(Col.FAIL + ' FAILED' + Col.OFF)
        failed_mime = True

    sleep(wait_time)

    if not failed_terminal:
        print(Col.OK + '\nConfiguration successfully finished.' + Col.OFF)
    else:
        print(Col.WARN + "\nConfiguration finished - Don't forget to change the nzblnk.desktop file" + Col.OFF)
        print(Col.WARN + "or NZB-Monkey will not work!!" + Col.OFF)

    if failed_mime:
        print(Col.WARN + "\nYou're running the NZB-Monkey configuration on a system that is not able to handle NZBLNK Links!!" + Col.OFF)

    check_missing_modules()


def config_win():

    try:
        import winreg as reg
        key = reg.CreateKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\\Classes\\nzblnk')
        reg.SetValue(key, '', reg.REG_SZ, 'URL:nzblnk')
        reg.SetValueEx(key, 'URL Protocol', 0, reg.REG_SZ, '')
        reg.CloseKey(key)

        key = reg.CreateKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\\Classes\\nzblnk\\shell\\open\\command')
        reg.SetValue(key, '', reg.REG_SZ, '"{0}" "%1"'.format(op.normpath(os.path.abspath(sys.executable))))
        reg.CloseKey(key)

    except (OSError, ImportError):
        print(Col.FAIL + ' FAILED to setup registry link for NZBLNK scheme!' + Col.OFF)
        sleep(wait_time)
        sys.exit(2)


def config_darwin():
    print('TBD')


def config_nzbmonkey():
    if os.name == 'posix':
        config_linux()
    elif os.name == 'nt':
        config_win()
    elif os.name == 'darwin':
        config_darwin()


def main():
    config_nzbmonkey()


if __name__ == '__main__':
    main()
