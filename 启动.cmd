@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
 .venv\Scripts\python.exe app.py
) else (
 call "安装并启动.cmd"
)
pause
