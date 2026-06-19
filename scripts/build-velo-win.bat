@echo off
REM ============================================================
REM  Velo - Windows build (pywebview app, anti-false-positive)
REM  Author: brenu
REM
REM  Packages the WebView2-based Velo app:
REM    * --onedir       : no temp self-extraction (low AV false positives)
REM    * --version-file : embeds publisher/product metadata
REM    * bundles only velo/web + assets/defaultConfig.json (no legacy art)
REM    * --collect-all webview : ships pywebview's JS + WebView2 binaries
REM ============================================================

set FOLDER_NAME=%cd%
for %%F in ("%cd%") do set FOLDER_NAME=%%~nxF
if /i "%FOLDER_NAME%"=="scripts" (
    cd ..
)

echo =^> Cleaning up previous builds...
if exist dist\Velo rmdir /s /q dist\Velo

echo =^> Creating virtual environment...
python -m venv venv-win

echo =^> Activating virtual environment...
call venv-win\Scripts\activate.bat

echo =^> Installing dependencies via pip...
python -m pip install --upgrade pip pyinstaller
pip install -r requirements.txt
pip install pywebview

echo =^> Running PyInstaller (onedir + version metadata)...
pyinstaller --onedir --noconsole --noconfirm ^
    --name="Velo" ^
    --icon=assets\icons\velo.ico ^
    --version-file=version.txt ^
    --add-data="velo\web;velo\web" ^
    --add-data="assets\defaultConfig.json;assets" ^
    --collect-all=webview ^
    --hidden-import=mido.backends.rtmidi ^
    --hidden-import=clr ^
    --paths="." ^
    velo_app.py

echo =^> Cleaning up temporary files...
del /F /Q *.spec
rmdir /s /q build __pycache__ venv-win

echo =^> Done! App folder available at 'dist\Velo\' (run 'dist\Velo\Velo.exe').
