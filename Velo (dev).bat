@echo off
title Velo
cd /d "%~dp0"
echo Iniciando Velo...
"venv-win\Scripts\python.exe" velo_app.py
echo.
echo (Velo foi fechado. Se houve erro acima, me avise.)
pause
