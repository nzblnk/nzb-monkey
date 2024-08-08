@echo off
setlocal enabledelayedexpansion

echo Create NZB-Monkey source package...

for /f "tokens=2 delims='" %%i in ('type src\version.py ^| findstr "__version__"') do (
    set VERSION=%%i
)

set DESTINATION=nzbmonkey-v%VERSION%-linux
set DISTDIR=%CD%\dist

if not exist %DISTDIR% mkdir %DISTDIR%

echo %DESTINATION%

if exist %TEMP%\%DESTINATION% rmdir /s /q %TEMP%\%DESTINATION%
mkdir %TEMP%\%DESTINATION%

xcopy src\*.py %TEMP%\%DESTINATION%\ /Y
copy src\LICENSE %TEMP%\%DESTINATION%\ /Y

pushd %TEMP%

7z a -ttar %DESTINATION%.tar %DESTINATION%

7z a -tbzip2 %DISTDIR%\%DESTINATION%.tbz2 %DESTINATION%.tar

del %DESTINATION%.tar
rmdir /s /q %DESTINATION%

popd

echo Package created: %DISTDIR%\%DESTINATION%.tbz2

:eof