@echo off

py -3 -c "import sys;exit(2 if sys.maxsize > 2**32 else 1)"
if errorlevel 2 goto SIXTYFOUR

set DIR=%CD%
cd %~dp0
set PYTHONPATH=./src
py -3 setup.py py2exe
cd %DIR%
goto EOF

:SIXTYFOUR
echo.
echo  Please run with a 32-bit python.
:EOF
timeout 5
