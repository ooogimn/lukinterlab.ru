#!/usr/bin/env python3
"""
Обход бага Windows: django dumpdata -o открывает файл в текстовом режиме без encoding=,
из-за чего cp1251/cp1252 ломают emoji в JSON (ensure_ascii=False).

Запуск (из корня проекта):
  python scripts/dumpdata_utf8.py --exclude auth.permission --exclude contenttypes -o final_reborn_dump.json

Дочерний процесс стартует с PYTHONUTF8=1 (PEP 540), open(..., "wt") пишет в UTF-8.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    rc = subprocess.call(
        [sys.executable, str(root / "manage.py"), "dumpdata", *sys.argv[1:]],
        cwd=str(root),
        env=env,
    )
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
