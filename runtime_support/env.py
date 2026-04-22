from __future__ import annotations

import os
from pathlib import Path

from project_paths import PROJECT_ROOT


def load_project_env(env_file: str | Path = ".env.local") -> Path | None:
    path = Path(env_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    return path
