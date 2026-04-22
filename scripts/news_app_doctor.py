#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.news_app.config import load_news_app_config
from apps.news_app.pipeline import NewsWorkflowApp
from apps.news_app.news_registry import NEWS_DOMAINS
from runtime_support.artifacts import describe_artifact_store, get_artifact_store
from runtime_support.env import load_project_env
from runtime_support.memory import get_workflow_memory_recorder


def check_kernel_status() -> dict[str, object]:
    kernel_url = os.getenv("AIOS_SERVER_URL") or "http://127.0.0.1:8001"
    status_url = kernel_url.rstrip("/") + "/status"
    try:
        with urlopen(status_url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "url": status_url, "payload": payload}
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "url": status_url, "error": str(exc)}


def check_env_var(name: str) -> dict[str, object]:
    value = os.getenv(name)
    return {"present": bool(value), "masked": mask_secret(value)}


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def main() -> int:
    loaded_env = load_project_env()
    config = load_news_app_config()
    store = get_artifact_store()
    memory_recorder = get_workflow_memory_recorder()
    app = NewsWorkflowApp(mode="serial")

    report = {
        "app": {
            "mode": app.mode,
            "config_path": str(config.config_path),
            "stages": list(config.workflow_stage_order),
            "parallel_domain_workers": config.parallel_domain_workers,
            "serial_domain_workers": config.serial_domain_workers,
        },
        "env_file": str(loaded_env) if loaded_env else None,
        "domains": [
            {
                "name": domain.name,
                "category_file": domain.category_file,
                "expert_agent": domain.expert_agent_name,
            }
            for domain in NEWS_DOMAINS
        ],
        "paths": {
            "intermediate_dir_exists": store.exists(config.intermediate_dir),
            "output_dir_exists": store.exists(config.output_dir),
            "intermediate_dir": str(config.intermediate_dir),
            "output_dir": str(config.output_dir),
        },
        "artifact_store": describe_artifact_store(store),
        "workflow_memory": memory_recorder.describe(),
        "environment": {
            "OPENAI_API_KEY": check_env_var("OPENAI_API_KEY"),
            "AIOS_LLM_MODEL": check_env_var("AIOS_LLM_MODEL"),
            "AIOS_LLM_BASE_URL": check_env_var("AIOS_LLM_BASE_URL"),
            "ZH_API_KEY": check_env_var("ZH_API_KEY"),
            "TAVILY_API_KEY": check_env_var("TAVILY_API_KEY"),
            "AIOS_ARTIFACT_STORE_BACKEND": check_env_var("AIOS_ARTIFACT_STORE_BACKEND"),
            "AIOS_ARTIFACT_AGENT_NAME": check_env_var("AIOS_ARTIFACT_AGENT_NAME"),
            "AIOS_WORKFLOW_MEMORY_ENABLED": check_env_var("AIOS_WORKFLOW_MEMORY_ENABLED"),
            "AIOS_WORKFLOW_MEMORY_AGENT_NAME": check_env_var("AIOS_WORKFLOW_MEMORY_AGENT_NAME"),
        },
        "kernel": check_kernel_status(),
        "agent_bootstrap": {
            "hot_api_agent": type(app._hot_api_agent()).__name__,
            "sort_agent": type(app._sort_agent()).__name__,
            "web_search_agent": type(app._web_search_agent()).__name__,
            "maker_agent": type(app._maker_agent()).__name__,
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
