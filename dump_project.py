import os
from datetime import datetime

# Какие папки игнорировать (расширенный список)
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", "staticfiles", "media", ".idea", ".vscode",
    "static/icons",      # иконки не нужны в дампе
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
    "CODEX_LOG1.txt", "CODEX__LOGS.txt",
    "package-lock.json", "yarn.lock",
}

# Никакого лимита на размер файла и дампа
MAX_FILE_SIZE = None  # не используется
MAX_TOTAL_DUMP_SIZE = None  # не используется

# Сжатие кода выключено, содержимое пишется как есть
COMPRESS_CODE = False


def is_binary_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in IGNORED_EXTENSIONS


def should_exclude_file(filename: str) -> bool:
    return filename in EXCLUDED_FILES


def compress_content(content: str, filepath: str) -> str:
    # Оставлено для совместимости, по факту возвращает исходный контент
    if not COMPRESS_CODE:
        return content
    return content


def detect_language(filepath: str) -> str:
    """
    Определение "языка" для ИИ по расширению файла,
    чтобы он лучше понимал, что за содержимое перед ним.
    """
    _, ext = os.path.splitext(filepath.lower())
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "markdown",
        ".sh": "bash",
        ".bat": "batch",
        ".ps1": "powershell",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".txt": "text",
        ".sql": "sql",
        ".csv": "csv",
        ".xml": "xml",
    }
    return mapping.get(ext, "text")


def build_tree_and_collect_files(root: str):
    """
    Обходит проект, строит дерево директорий и собирает список файлов.
    Фильтр только по директориям/расширениям/именам.
    """
    tree_lines = []
    file_paths = []

    root = os.path.abspath(root)
    root_name = os.path.basename(root.rstrip(os.sep))

    tree_lines.append(f"{root_name}/")

    for current_root, dirs, files in os.walk(root):
        # Фильтр директорий
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

        for name in sorted(files):
            if is_binary_file(name) or should_exclude_file(name):
                continue

            file_rel_path = os.path.join(rel_root, name) if rel_root != "." else name
            file_abs_path = os.path.join(current_root, name)

            tree_lines.append(f"{indent}    {name}")
            file_paths.append((file_rel_path, file_abs_path))

    return tree_lines, file_paths


def dump_project(root: str, output_filename: str = "project_dump.txt"):
    tree_lines, file_paths = build_tree_and_collect_files(root)

    root = os.path.abspath(root)

    # Индекс файлов для ИИ, чтобы он мог быстро увидеть структуру и прыгать по пути
    files_index_lines = []
    for idx, (rel_path, abs_path) in enumerate(file_paths, 1):
        lang = detect_language(abs_path)
        files_index_lines.append(
            f"{idx}. PATH={rel_path} | LANG={lang}"
        )

    header = [
        "#" * 80,
        "# FULL PROJECT DUMP (NO TRUNCATION)",
        "# FORMAT FOR LLM:",
        "#   1) PROJECT TREE — общая структура проекта.",
        "#   2) FILES INDEX — плоский список файлов с путём и языком.",
        "#   3) FILES CONTENT — для каждого файла:",
        "#        ===== FILE START =====",
        "#        FILE_INDEX: <N>",
        "#        PATH: <relative/path>",
        "#        LANG: <language>",
        "#        ===== CONTENT START =====",
        "#        <raw file content>",
        "#        ===== CONTENT END =====",
        "#        ===== FILE END =====",
        "#   Файлы идут в том же порядке, что и в индексе.",
        "#" * 80,
        f"# Root: {root}",
        f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Files listed: {len(file_paths)}",
        f"# Max single file size: NONE",
        f"# Max total dump size: NONE",
        f"# Code compression enabled: {COMPRESS_CODE}",
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

        # Индекс файлов
        f.write("\n\n")
        f.write("FILES INDEX:\n")
        f.write("-" * 80 + "\n")
        for line in files_index_lines:
            f.write(line + "\n")

        # Разделитель
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("FILES CONTENT:\n")
        f.write("=" * 80 + "\n\n")

        total_files = len(file_paths)

        for i, (rel_path, abs_path) in enumerate(file_paths, 1):
            lang = detect_language(abs_path)

            # Явные маркеры для ИИ
            f.write("===== FILE START =====\n")
            f.write(f"FILE_INDEX: {i}\n")
            f.write(f"PATH: {rel_path}\n")
            f.write(f"LANG: {lang}\n")
            f.write("===== CONTENT START =====\n")

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as src:
                    content = src.read()

                content = compress_content(content, abs_path)
                f.write(content)

            except Exception as e:
                f.write(f"<< ERROR READING FILE: {e} >>\n")

            f.write("\n===== CONTENT END =====\n")
            f.write("===== FILE END =====\n\n")

            if i % 10 == 0:
                print(f"Processed {i}/{total_files} files...")

    file_size_bytes = os.path.getsize(output_filename)
    file_size_kb = file_size_bytes / 1024
    file_size_mb = file_size_bytes / (1024 * 1024)

    print(f"Готово! Файл с дампом проекта: {output_filename}")
    print(f"Размер дампа: {file_size_kb:.0f}KB (~{file_size_mb:.2f}MB)")
    print(f"Файлов в обходе (включено в дамп): {len(file_paths)}")


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    dump_project(project_root)
