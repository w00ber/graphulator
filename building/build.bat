@echo off
REM Build a graphulator app as a standalone Windows .exe folder.
REM
REM Usage (from repo root):
REM     conda activate ^<your-env^>
REM     building\build.bat graphulator
REM     building\build.bat paragraphulator
REM
REM Output: dist\<app>\<app>.exe

setlocal enabledelayedexpansion

set APP=%~1
if "%APP%"=="" goto usage
if not "%APP%"=="graphulator" if not "%APP%"=="paragraphulator" goto usage

echo ==========================================
echo Building %APP%.exe
echo ==========================================

if "%CONDA_PREFIX%"=="" (
    echo ERROR: activate a conda environment first ^(e.g. "conda activate CMT"^).
    exit /b 1
)

set PYTHON=%CONDA_PREFIX%\python.exe
set PIP=%CONDA_PREFIX%\Scripts\pip.exe

echo Using conda environment: %CONDA_PREFIX%

"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    "%PIP%" install pyinstaller
)

echo Ensuring graphulator package is installed (editable)...
"%PIP%" install -e . --quiet

echo Running PyInstaller on building\%APP%.spec...
"%PYTHON%" -m PyInstaller "building\%APP%.spec" --clean --noconfirm

if not exist "dist\%APP%\%APP%.exe" (
    echo.
    echo ERROR: build failed; %APP%.exe not found.
    exit /b 1
)

echo.
echo ==========================================
echo SUCCESS: dist\%APP%\%APP%.exe
echo ==========================================
endlocal
exit /b 0

:usage
echo Usage: %~nx0 {graphulator^|paragraphulator}
exit /b 2
