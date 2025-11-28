@echo off
echo 🎯 ParkShare Development Launcher (Windows)

REM Активируем виртуальное окружение если есть
if exist venv (
    echo 🔧 Активация виртуального окружения...
    call venv\Scripts\activate
)

REM Запускаем основной скрипт
python run_dev.py
pause