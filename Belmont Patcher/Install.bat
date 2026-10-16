@echo off
setlocal
rem Belmont Patcher launcher: finds Python 3 (installs it when it is missing), then opens the settings window.
cd /d "%~dp0"
set "PYVER=3.13.13"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "PYEXE="
call :find_python
if /i "%~1"=="/detect" (
  echo Python found: [%PYEXE%]
  exit /b 0
)
if defined PYEXE goto run

echo.
echo  Belmont Patcher needs Python 3 (version 3.10 or newer, with its "tcl/tk" part).
echo  It was not found on this PC.
echo.
echo  This will download the official Python %PYVER% installer from python.org (about 27 MB)
echo  and install it for your user account only (no administrator rights needed), then open
echo  the patcher window. When you click Apply there, the patcher also downloads the
echo  Python package it needs (UnityPy), once.
echo.
echo  Internet is needed for this. Close this window to cancel, or
pause
call :install_python
call :find_python
if not defined PYEXE (
  echo.
  echo  Python could not be installed automatically.
  echo  Install it yourself from https://www.python.org/downloads/ - on the first screen of
  echo  the installer tick "Add python.exe to PATH" - then double-click Install.bat again.
  echo.
  pause
  exit /b 1
)
echo.
echo  Python installed. Opening the patcher window...

:run
%PYEXE% -c "import sys; print(sys.version)" > launcher_log.txt 2>&1
%PYEXE% belmont_patcher.py --gui >> launcher_log.txt 2>&1
if errorlevel 1 (
  echo.
  echo The settings window could not start. Details:
  echo.
  type launcher_log.txt
  echo.
  pause
)
exit /b 0

:find_python
rem Accepts the first Python 3.10+ that has tkinter: the py launcher, python on PATH, or a per-user install.
set "PYEXE="
call :try "py -3"
if defined PYEXE exit /b 0
call :try "python"
if defined PYEXE exit /b 0
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
  if not defined PYEXE call :try "\"%%~D\python.exe\""
)
for /d %%D in ("%ProgramFiles%\Python3*") do (
  if not defined PYEXE call :try "\"%%~D\python.exe\""
)
exit /b 0

:try
set "CAND=%~1"
%CAND% -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >NUL 2>&1
if not errorlevel 1 set "PYEXE=%CAND%"
exit /b 0

:install_python
set "PYSETUP=%TEMP%\python-%PYVER%-amd64.exe"
echo.
echo  Downloading %PYURL%
curl.exe -L -# -o "%PYSETUP%" "%PYURL%"
if errorlevel 1 (
  echo  curl failed, trying PowerShell...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYSETUP%'"
)
if not exist "%PYSETUP%" (
  echo  Download failed.
  exit /b 1
)
echo.
echo  Installing Python %PYVER% (a progress window opens and closes by itself)...
"%PYSETUP%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_tcltk=1 Include_pip=1 Include_test=0 Include_doc=0 Shortcuts=0
echo  Installer finished with code %ERRORLEVEL% (0 = ok).
del "%PYSETUP%" >NUL 2>&1
exit /b 0
