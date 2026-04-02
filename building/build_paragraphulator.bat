@echo off
REM Build paragraphulator as a standalone Windows executable
REM
REM Usage: From the project root directory:
REM   conda activate CMT
REM   building\build_paragraphulator.bat

setlocal enabledelayedexpansion

echo ==========================================
echo Building paragraphulator.exe
echo ==========================================

REM Check if conda environment is active
if "%CONDA_PREFIX%"=="" (
    echo ERROR: Please activate your conda environment first:
    echo   conda activate CMT
    echo   build_paragraphulator.bat
    exit /b 1
)

set PYTHON=%CONDA_PREFIX%\python.exe
set PIP=%CONDA_PREFIX%\Scripts\pip.exe

echo Using conda environment: %CONDA_PREFIX%
echo Python: %PYTHON%

REM Clean previous builds (Windows-specific directories)
echo Cleaning previous builds...
if exist build-win rmdir /s /q build-win
if exist dist-win rmdir /s /q dist-win

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
REM Use --distpath and --workpath to avoid conflicts with macOS builds
echo Running PyInstaller...
"%PYTHON%" -m PyInstaller building\paragraphulator-win.spec --clean --noconfirm --distpath dist-win --workpath build-win

REM Check if build succeeded
if exist "dist-win\paragraphulator\paragraphulator.exe" (
    echo.
    echo ==========================================
    echo SUCCESS! Executable created at:
    echo   dist-win\paragraphulator\paragraphulator.exe
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
