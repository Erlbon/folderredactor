@echo off
REM Builds a standalone Windows .exe using PyInstaller.
REM Run this from a Windows machine with Python 3.11+ installed.
REM
REM Checks the result of every step and stops with a clear message on
REM failure, instead of continuing to a false "Done" message.
REM
REM Does NOT bump the version number -- run bump_version.py yourself
REM first if this build should carry a new version.

cd /d "%~dp0"
echo Working directory: %cd%
echo.

echo Checking for Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: "python" was not found on your PATH.
    echo Install Python 3.11+ from python.org and make sure to check
    echo "Add python.exe to PATH" during installation, then try again.
    pause
    exit /b 1
)
echo.

echo Installing dependencies ^(this can take a minute the first time^)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. Common causes: no internet connection,
    echo or a proxy/firewall blocking pip. See the error above for details.
    pause
    exit /b 1
)
echo.

echo Building folderredactor.exe ...
REM "python -m PyInstaller": the pyinstaller console script is often not on PATH.
REM No UPX: the spec has upx=False (Defender flagged a UPX-packed sibling exe, a false positive).
python -m PyInstaller folderredactor.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See the error output above for details.
    pause
    exit /b 1
)
echo.

if not exist "dist\folderredactor.exe" (
    echo.
    echo ERROR: PyInstaller reported success but dist\folderredactor.exe
    echo was not found. Please copy the full output above and report it.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  SUCCESS. Your app is at: %cd%\dist\folderredactor.exe
echo  That one file can be copied anywhere and run.
echo ================================================================
