import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import bootstrap


def test_ensure_required_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bootstrap.ensure_required_files()

    for directory in bootstrap.REQUIRED_DIRS:
        assert (tmp_path / directory).is_dir()

    for file_path in bootstrap.REQUIRED_FILES:
        assert (tmp_path / file_path).is_file()
