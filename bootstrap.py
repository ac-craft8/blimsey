from pathlib import Path

REQUIRED_DIRS = [
    'logs',
    'history',
]

REQUIRED_FILES = {
    'messages/__init__.py': (
        "processing_lock_message = 'Por favor espera mientras se procesa tu mensaje anterior...\n'"
    ),
    'history/__init__.py': '',
}


def ensure_required_files(base_path: str = '.') -> None:
    """Create required directories and files if they don't exist."""
    base = Path(base_path)

    for directory in REQUIRED_DIRS:
        dir_path = base / directory
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f'[bootstrap] Created directory: {dir_path}')

    for file_path, content in REQUIRED_FILES.items():
        path = base / file_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            print(f'[bootstrap] Created file: {path}')

