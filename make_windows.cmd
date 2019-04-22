@echo off

set DIR=%CD%
cd %~dp0
set PYTHONPATH=./src
pyinstaller -F --distpath ./dist --workpath ./build --icon ./resource/nzb-monkey-icons.ico --noupx --clean ./src/nzbmonkey.py
cd %DIR%
goto EOF

:EOF
timeout 5
