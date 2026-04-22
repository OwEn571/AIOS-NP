from __future__ import annotations

import json
import urllib.request
from pathlib import Path


SERVICE_BASE_URL = "http://127.0.0.1:8010"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url=f"{SERVICE_BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    prompt_agent = {
        "id": "kernel-briefing-agent",
        "name": "Kernel Briefing Agent",
        "description": "基于最新 workflow state 和 metrics 做系统简报",
        "agent_type": "prompt",
        "require_kernel": True,
        "system_prompt": (
            "你是部署在 AIOS kernel 上的运维简报 agent。"
            "你会结合提供的上下文，输出简洁的系统判断、瓶颈和下一步建议。"
        ),
        "tags": ["demo", "ops", "kernel"],
    }
    callable_agent = {
        "id": "news-quality-auditor",
        "name": "News Quality Auditor",
        "description": "读取最新日报和指标，输出结构化质量审计",
        "agent_type": "python_callable",
        "file_path": str(PROJECT_ROOT / "apps/news_app/sample_agents/news_quality_auditor.py"),
        "callable_name": "run",
        "tags": ["demo", "quality", "audit"],
    }

    for payload in (prompt_agent, callable_agent):
        result = post_json("/api/agents/register", payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
