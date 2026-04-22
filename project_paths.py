from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("AIOS_NP_DATA_DIR", PROJECT_ROOT))
INTERMEDIATE_DIR = Path(
    os.getenv("AIOS_NP_INTERMEDIATE_DIR", str(DATA_ROOT / "intermediate"))
)
OUTPUT_DIR = Path(os.getenv("AIOS_NP_OUTPUT_DIR", str(DATA_ROOT / "output")))
LOG_DIR = Path(os.getenv("AIOS_NP_LOG_DIR", str(DATA_ROOT / "logs")))
ROOT_DIR = Path(os.getenv("AIOS_NP_ROOT_DIR", str(DATA_ROOT / "root")))
PROC_DIR = Path(os.getenv("AIOS_NP_PROC_DIR", str(DATA_ROOT / "proc")))
ECOSYSTEM_DIR = Path(os.getenv("AIOS_NP_ECOSYSTEM_DIR", str(DATA_ROOT / "ecosystem")))
ECOSYSTEM_RUNS_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_RUNS_DIR", str(ECOSYSTEM_DIR / "runs"))
)
ECOSYSTEM_METRICS_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_METRICS_DIR", str(ECOSYSTEM_DIR / "metrics"))
)
ECOSYSTEM_STATES_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_STATES_DIR", str(ECOSYSTEM_DIR / "states"))
)
ECOSYSTEM_SNAPSHOTS_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_SNAPSHOTS_DIR", str(ECOSYSTEM_DIR / "snapshots"))
)
ECOSYSTEM_AGENTS_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_AGENTS_DIR", str(ECOSYSTEM_DIR / "agents"))
)
ECOSYSTEM_AGENT_RUNS_DIR = Path(
    os.getenv("AIOS_NP_ECOSYSTEM_AGENT_RUNS_DIR", str(ECOSYSTEM_DIR / "agent_runs"))
)


def ensure_runtime_directories() -> None:
    for path in (
        INTERMEDIATE_DIR,
        OUTPUT_DIR,
        LOG_DIR,
        ROOT_DIR,
        PROC_DIR,
        ECOSYSTEM_DIR,
        ECOSYSTEM_RUNS_DIR,
        ECOSYSTEM_METRICS_DIR,
        ECOSYSTEM_STATES_DIR,
        ECOSYSTEM_SNAPSHOTS_DIR,
        ECOSYSTEM_AGENTS_DIR,
        ECOSYSTEM_AGENT_RUNS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)
