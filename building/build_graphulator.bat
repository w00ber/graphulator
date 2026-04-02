@echo off
REM Build graphulator as a standalone Windows executable
REM
REM Usage: From the project root directory:
REM   conda activate CMT
REM   building\build_graphulator.bat

setlocal enabledelayedexpansion

echo ==========================================
echo Building graphulator.exe
echo ==========================================

REM Check if conda environment is active
if "%CONDA_PREFIX%"=="" (
    echo ERROR: Please activate your conda environment first:
    echo   conda activate CMT
    echo   build_graphulator.bat
    exit /b 1
)

set PYTHON=%CONDA_PREFIX%\python.exe
set PIP=%CONDA_PREFIX%\Scripts\pip.exe

echo Using conda environment: %CONDA_PREFIX%
echo Python: %PYTHON%

REM Clean previous builds (use separate directories from paragraphulator)
echo Cleaning previous builds...
if exist build-graphulator-win rmdir /s /q build-graphulator-win
if exist dist-graphulator-win rmdir /s /q dist-graphulator-win

REM Ensure pyinstaller is installed in the conda environment
echo Checking pyinstaller...
"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found in conda env. Installing...
    "%PIP%" install pyinstaller
)

echo Using PyInstaller from conda env

REM Install the package in development mode (if not already)
echo Ensuring graphulator is installed...
"%PIP%" install -e . --quiet

REM Run PyInstaller using python -m to ensure correct environment
echo Running PyInstaller...
"%PYTHON%" -m PyInstaller building\graphulator-win.spec --clean --noconfirm --distpath dist-graphulator-win --workpath build-graphulator-win

REM Check if build succeeded
if exist "dist-graphulator-win\graphulator\graphulator.exe" (
    echo.
    echo ==========================================
    echo SUCCESS! Executable created at:
    echo   dist-graphulator-win\graphulator\graphulator.exe
    echo.
    echo To create installer, use Inno Setup or similar.
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo ERROR: Build failed. Check output above.
    echo ==========================================
    exit /b 1
)

endlocal
