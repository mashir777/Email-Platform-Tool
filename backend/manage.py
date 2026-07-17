#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    if os.environ.get("VERCEL"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Windows often resolves `python` to WindowsApps/store stub even when
        # a project .venv exists. Re-run with the local venv interpreter.
        venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
        current = Path(sys.executable).resolve()
        if venv_python.is_file() and current != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
