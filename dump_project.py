import os
import re
from datetime import datetime

# Какие папки игнорировать (расширенный список)
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", "staticfiles", "media", ".idea", ".vscode",
    "static/icons",  # иконки не нужны в дампе
    "logs", "cache", "temp",  # временные файлы и логи
}

# Какие расширения файлов пропускать (расширенный список)
IGNORED_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".sqlite3", ".sqlite", ".db",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".exe", ".dll", ".so", ".pkl", ".h5", ".model", ".pt",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".log", ".tmp", ".cache",
}

# Файлы, которые нужно полностью игнорировать
EXCLUDED_FILES = {
    "CODEX_LOG1.txt", "CODEX__LOGS.txt",  # ваши логи
    "package-lock.json", "yarn.lock",  # большие lock-файлы
}

# Максимальный размер файла для включения в дамп (в байтах)
MAX_FILE_SIZE = 500 * 1024  # 500KB

# Сжатие кода: удаление лишних пробелов и комментарий
COMPRESS_CODE = True


def is_binary_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in IGNORED_EXTENSIONS


def should_exclude_file(filename: str) -> bool:
    """Проверяет, нужно ли исключить файл"""
    return filename in EXCLUDED_FILES


def compress_content(content: str, filepath: str) -> str:
    """Сжимает содержимое файла (удаляет лишние пробелы и комментарии)"""
    if not COMPRESS_CODE:
        return content

    _, ext = os.path.splitext(filepath.lower())

    if ext in {'.py', '.js', '.css', '.html', '.ts'}:
        # Удаляем комментарии и лишние пробелы
        lines = []
        in_multiline_comment = False

        for line in content.split('\n'):
            # Обработка многострочных комментариев
            if in_multiline_comment:
                if '*/' in line:
                    line = line.split('*/', 1)[1]
                    in_multiline_comment = False
                else:
                    continue

            # Удаляем однострочные комментарии
            if '//' in line:
                line = line.split('//')[0]
            if '#' in line and not line.strip().startswith('#'):
                line = line.split('#')[0]

            # Обработка многострочных комментариев для CSS/JS
            if '/*' in line:
                if '*/' in line:
                    line = line.split('/*')[0] + line.split('*/')[1]
                else:
                    line = line.split('/*')[0]
                    in_multiline_comment = True

            # Удаляем начальные и конечные пробелы
            line = line.strip()
            if line:
                lines.append(line)

        return '\n'.join(lines)

    return content


def get_file_size_kb(filepath: str) -> float:
    """Возвращает размер файла в КБ"""
    return os.path.getsize(filepath) / 1024


def build_tree_and_collect_files(root: str):
    """
    Обходит проект, строит дерево директорий и собирает список файлов
    """
    tree_lines = []
    file_paths = []

    root = os.path.abspath(root)
    root_name = os.path.basename(root.rstrip(os.sep))

    tree_lines.append(f"{root_name}/")

    for current_root, dirs, files in os.walk(root):
        # Отбрасываем ненужные директории
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        ]

        rel_root = os.path.relpath(current_root, root)
        if rel_root == ".":
            depth = 0
        else:
            depth = rel_root.count(os.sep) + 1

        indent = "    " * depth

        if rel_root != ".":
            tree_lines.append(f"{indent}{os.path.basename(current_root)}/")

        # Файлы
        for name in sorted(files):
            if is_binary_file(name) or should_exclude_file(name):
                continue

            file_rel_path = os.path.join(rel_root, name) if rel_root != "." else name
            file_abs_path = os.path.join(current_root, name)

            # Пропускаем слишком большие файлы
            try:
                if get_file_size_kb(file_abs_path) > MAX_FILE_SIZE / 1024:
                    tree_lines.append(f"{indent}    {name} [SKIPPED - TOO LARGE]")
                    continue
            except OSError:
                continue

            tree_lines.append(f"{indent}    {name}")
            file_paths.append((file_rel_path, file_abs_path))

    return tree_lines, file_paths


def dump_project(root: str, output_filename: str = "project_dump.txt"):
    tree_lines, file_paths = build_tree_and_collect_files(root)

    root = os.path.abspath(root)
    header = [
        "#" * 80,
        "# COMPRESSED PROJECT DUMP",
        f"# Root: {root}",
        f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Files: {len(file_paths)}",
        f"# Max file size: {MAX_FILE_SIZE / 1024:.0f}KB",
        f"# Code compression: {COMPRESS_CODE}",
        "#" * 80,
        "",
    ]

    with open(output_filename, "w", encoding="utf-8", errors="replace") as f:
        # Шапка
        f.write("\n".join(header))

        # Дерево проекта
        f.write("PROJECT TREE:\n")
        f.write("-" * 80 + "\n")
        for line in tree_lines:
            f.write(line + "\n")

        # Разделитель
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("FILES CONTENT:\n")
        f.write("=" * 80 + "\n\n")

        # Содержимое файлов
        for i, (rel_path, abs_path) in enumerate(file_paths, 1):
            f.write(f"# File {i}/{len(file_paths)}: {rel_path}\n")
            f.write("#" * 80 + "\n\n")

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as src:
                    content = src.read()

                    # Сжимаем содержимое
                    compressed_content = compress_content(content, abs_path)
                    f.write(compressed_content)

            except Exception as e:
                f.write(f"<< ERROR READING FILE: {e} >>\n")

            f.write("\n\n")

            # Прогресс для больших проектов
            if i % 10 == 0:
                print(f"Processed {i}/{len(file_paths)} files...")

    file_size_kb = os.path.getsize(output_filename) / 1024
    print(f"Готово! Файл с дампом проекта: {output_filename}")
    print(f"Размер дампа: {file_size_kb:.0f}KB")
    print(f"Обработано файлов: {len(file_paths)}")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    dump_project(project_root)