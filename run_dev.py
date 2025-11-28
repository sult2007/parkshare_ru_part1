#!/usr/bin/env python3
"""
Единый скрипт для запуска всей системы ParkShare Development
Запускает: Django, LLM сервис, AI API сервер, Celery worker
"""
import os
import sys
import time
import subprocess
import signal
import threading
from pathlib import Path

# Добавляем корень проекта в Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_command(command, cwd=None, shell=False, env=None):
    """Запускает команду и возвращает процесс"""
    if env is None:
        env = os.environ.copy()

    print(f"🚀 Запуск: {command}")
    process = subprocess.Popen(
        command,
        cwd=cwd or project_root,
        shell=shell,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    return process


def log_output(process, name):
    """Логирует вывод процесса"""

    def log_thread():
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"[{name}] {output.strip()}")
        process.poll()

    thread = threading.Thread(target=log_thread)
    thread.daemon = True
    thread.start()
    return thread


def setup_environment():
    """Настраивает окружение для разработки"""
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    env['DJANGO_SETTINGS_MODULE'] = 'backend.settings.local'
    env['DEBUG'] = '1'
    return env


def wait_for_service(port, timeout=30):
    """Ожидает пока сервис на порту станет доступен"""
    import socket
    import time

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                if result == 0:
                    print(f"✅ Сервис на порту {port} готов")
                    return True
        except:
            pass
        time.sleep(1)

    print(f"❌ Таймаут ожидания порта {port}")
    return False


def start_django():
    """Запускает Django development server"""
    print("\n" + "=" * 50)
    print("🔄 Запуск Django сервера...")
    print("=" * 50)

    # Применяем миграции
    print("📦 Применяем миграции...")
    migrate_process = run_command([
        sys.executable, "backend/manage.py", "migrate"
    ])
    migrate_process.wait()

    # Собираем статику
    print("📦 Собираем статику...")
    collectstatic_process = run_command([
        sys.executable, "backend/manage.py", "collectstatic", "--noinput"
    ])
    collectstatic_process.wait()

    # Запускаем сервер
    return run_command([
        sys.executable, "backend/manage.py", "runserver", "8000"
    ])


def start_llm_service():
    """Запускает LLM микросервис"""
    print("\n" + "=" * 50)
    print("🧠 Запуск LLM сервиса...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "uvicorn",
        "ai_services.llm_service.main:app",
        "--host", "0.0.0.0",
        "--port", "8002",
        "--reload"
    ])


def start_ai_api():
    """Запускает AI API сервер"""
    print("\n" + "=" * 50)
    print("🤖 Запуск AI API сервера...")
    print("=" * 50)

    return run_command([
        sys.executable, "api_server.py"
    ])


def start_celery_worker():
    """Запускает Celery worker"""
    print("\n" + "=" * 50)
    print("🔧 Запуск Celery worker...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "celery",
        "-A", "backend.config",
        "worker",
        "--loglevel=info",
        "--concurrency=2"
    ])


def start_celery_beat():
    """Запускает Celery beat"""
    print("\n" + "=" * 50)
    print("⏰ Запуск Celery beat...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "celery",
        "-A", "backend.config",
        "beat",
        "--loglevel=info"
    ])


def check_dependencies():
    """Проверяет наличие всех зависимостей"""
    print("🔍 Проверка зависимостей...")

    try:
        import django
        import fastapi
        import uvicorn
        import celery
        import redis
        print("✅ Все зависимости установлены")
        return True
    except ImportError as e:
        print(f"❌ Отсутствует зависимость: {e}")
        print("Установите зависимости: pip install -r requirements.txt")
        return False


def main():
    """Основная функция запуска"""
    print("🎯 ParkShare Development Launcher")
    print("Запуск всех компонентов системы...")

    # Проверяем зависимости
    if not check_dependencies():
        sys.exit(1)

    # Настраиваем окружение
    env = setup_environment()

    processes = []

    try:
        # Запускаем сервисы
        services = [
            ("LLM Service", start_llm_service, 8002),
            ("AI API", start_ai_api, 8001),
            ("Celery Worker", start_celery_worker, None),
            ("Celery Beat", start_celery_beat, None),
            ("Django", start_django, 8000),
        ]

        for name, starter, port in services:
            process = starter()
            processes.append((name, process))

            if port:
                # Даем время сервису начать запуск
                time.sleep(2)
                if not wait_for_service(port, timeout=10):
                    print(f"⚠️  Сервис {name} медленно запускается...")

        # Запускаем логирование для всех процессов
        threads = []
        for name, process in processes:
            thread = log_output(process, name)
            threads.append(thread)

        print("\n" + "🎉 Все сервисы запущены!")
        print("📊 Статус сервисов:")
        print("   • Django: http://localhost:8000")
        print("   • LLM Service: http://localhost:8002")
        print("   • AI API: http://localhost:8001")
        print("   • Celery Worker: ✅")
        print("   • Celery Beat: ✅")
        print("\n🛑 Для остановки нажмите Ctrl+C")

        # Ожидаем завершения
        while True:
            time.sleep(1)
            # Проверяем, что все процессы еще работают
            for name, process in processes:
                if process.poll() is not None:
                    print(f"❌ Процесс {name} завершился с кодом {process.returncode}")
                    # Можно перезапустить или завершить все

    except KeyboardInterrupt:
        print("\n🛑 Остановка сервисов...")

        # Останавливаем процессы
        for name, process in processes:
            if process.poll() is None:
                print(f"⏹️  Останавливаем {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"❌ Принудительная остановка {name}...")
                    process.kill()

        print("👋 Все сервисы остановлены")


if __name__ == "__main__":
    main()