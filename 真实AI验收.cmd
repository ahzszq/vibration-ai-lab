@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo 请先运行“安装并启动.cmd”，然后关闭仿真服务再运行本验收。
 pause
 exit /b 1
)
.venv\Scripts\python.exe tests\verify_real_ai.py
pause
