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
from typing import Optional

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
    env['DJANGO_SETTINGS_MODULE'] = env.get('DJANGO_SETTINGS_MODULE', 'backend.settings.local')
    env['DEBUG'] = env.get('DEBUG', '1')
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


def start_django(port: int):
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
        sys.executable, "backend/manage.py", "runserver", str(port)
    ])


def start_llm_service(host: str, port: int):
    """Запускает LLM микросервис"""
    print("\n" + "=" * 50)
    print("🧠 Запуск LLM сервиса...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "uvicorn",
        "services.llm_service.main:app",
        "--host", host,
        "--port", str(port),
        "--reload"
    ])


def start_ai_api(host: str, port: int):
    """Запускает AI API сервер"""
    print("\n" + "=" * 50)
    print("🤖 Запуск AI API сервера...")
    print("=" * 50)

    env = setup_environment()
    env['AI_API_HOST'] = host
    env['AI_API_PORT'] = str(port)
    return run_command([
        sys.executable, "-m", "uvicorn", "api_server:app", "--host", host, "--port", str(port)
    ], env=env)


def start_celery_worker(env: Optional[dict] = None):
    """Запускает Celery worker"""
    print("\n" + "=" * 50)
    print("🔧 Запуск Celery worker...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "celery",
        "-A", "backend.backend.config",
        "worker",
        "--loglevel=info",
        "--concurrency=2"
    ], env=env)


def start_celery_beat(env: Optional[dict] = None):
    """Запускает Celery beat"""
    print("\n" + "=" * 50)
    print("⏰ Запуск Celery beat...")
    print("=" * 50)

    return run_command([
        sys.executable, "-m", "celery",
        "-A", "backend.backend.config",
        "beat",
        "--loglevel=info"
    ], env=env)


def pick_port(preferred: int, env_name: str) -> int:
    """Возвращает доступный порт, если предпочтительный занят."""
    import socket

    try:
        override = int(os.environ.get(env_name, preferred))
    except (TypeError, ValueError):
        override = preferred

    def is_free(port_value: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            return sock.connect_ex(("127.0.0.1", port_value)) != 0

    if is_free(override):
        return override

    print(f"⚠️ Порт {override} занят. Подбираем свободный...")
    for candidate in range(override + 1, override + 20):
        if is_free(candidate):
            print(f"➡️  Используем альтернативный порт {candidate} для {env_name}")
            return candidate

    raise RuntimeError(f"Не удалось найти свободный порт рядом с {override}")


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

    django_port = pick_port(8000, "DJANGO_PORT")
    ai_api_port = pick_port(8001, "AI_API_PORT")
    llm_port = pick_port(8002, "LLM_SERVICE_PORT")

    env["DJANGO_PORT"] = str(django_port)
    env["AI_API_PORT"] = str(ai_api_port)
    env["LLM_SERVICE_PORT"] = str(llm_port)

    os.environ.update(env)

    processes = []

    try:
        # Запускаем сервисы
        services = [
            ("LLM Service", lambda: start_llm_service("0.0.0.0", llm_port), llm_port),
            ("AI API", lambda: start_ai_api("0.0.0.0", ai_api_port), ai_api_port),
            ("Celery Worker", lambda: start_celery_worker(env), None),
            ("Celery Beat", lambda: start_celery_beat(env), None),
            ("Django", lambda: start_django(django_port), django_port),
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
        print(f"   • Django: http://localhost:{django_port}")
        print(f"   • LLM Service: http://localhost:{llm_port}")
        print(f"   • AI API: http://localhost:{ai_api_port}")
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