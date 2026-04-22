from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_paths import INTERMEDIATE_DIR, OUTPUT_DIR, project_path


VALID_WORKFLOW_STAGES = ("hot_api", "sort", "search", "generate", "review", "report")


@dataclass(frozen=True)
class NewsAppConfig:
    config_path: Path
    intermediate_dir: Path
    output_dir: Path
    workflow_stage_order: tuple[str, ...]
    parallel_domain_workers: int
    serial_domain_workers: int
    hot_api_platform: str
    hot_api_platforms: tuple[str, ...]
    hot_api_max_items: int
    max_news_per_category: int
    web_search_max_results: int
    sort_categories: tuple[str, ...]
    generation_retry_limit: int
    raw: dict[str, Any]


def _resolve_path(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate

    return project_path(*candidate.parts)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_stage_order(raw_stage_order: Any) -> tuple[str, ...]:
    if not isinstance(raw_stage_order, list):
        return VALID_WORKFLOW_STAGES

    normalized = []
    for stage in raw_stage_order:
        if stage in VALID_WORKFLOW_STAGES and stage not in normalized:
            normalized.append(stage)

    return tuple(normalized) if normalized else VALID_WORKFLOW_STAGES


def _normalize_platforms(raw_platforms: Any, fallback_platform: Any) -> tuple[str, ...]:
    if isinstance(raw_platforms, str):
        raw_platforms = [item.strip() for item in raw_platforms.split(",")]

    normalized: list[str] = []
    if isinstance(raw_platforms, list):
        for platform in raw_platforms:
            candidate = str(platform).strip()
            if not candidate:
                continue
            if candidate == "all":
                return ()
            if candidate not in normalized:
                normalized.append(candidate)
        if normalized:
            return tuple(normalized)

    platform = str(fallback_platform or "all").strip()
    if platform and platform != "all":
        return (platform,)
    return ()


def load_news_app_config(config_path: str | Path | None = None) -> NewsAppConfig:
    path = Path(config_path) if config_path else project_path("config.json")
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    pipeline = raw.get("pipeline", {})
    workflow = raw.get("workflow", {})
    hot_api = raw.get("hot_api", {})
    sort_agent = raw.get("sort_agent", {})
    news_generation = raw.get("news_generation", {})

    return NewsAppConfig(
        config_path=path.resolve(),
        intermediate_dir=_resolve_path(
            pipeline.get("intermediate_dir"),
            INTERMEDIATE_DIR,
        ),
        output_dir=_resolve_path(
            pipeline.get("output_dir"),
            OUTPUT_DIR,
        ),
        workflow_stage_order=_normalize_stage_order(workflow.get("stages")),
        parallel_domain_workers=_positive_int(
            workflow.get("parallel_domain_workers", pipeline.get("parallel_workers")),
            default=6,
        ),
        serial_domain_workers=_positive_int(
            workflow.get("serial_domain_workers"),
            default=1,
        ),
        hot_api_platform=str(hot_api.get("platform", "all")),
        hot_api_platforms=_normalize_platforms(
            hot_api.get("platforms"),
            hot_api.get("platform", "all"),
        ),
        hot_api_max_items=_positive_int(hot_api.get("max_items_per_platform"), default=10),
        max_news_per_category=_positive_int(pipeline.get("max_news_per_category"), default=3),
        web_search_max_results=_positive_int(
            raw.get("web_search", {}).get("max_results_per_query"),
            default=5,
        ),
        sort_categories=tuple(sort_agent.get("categories", [])),
        generation_retry_limit=_positive_int(news_generation.get("max_retries"), default=5),
        raw=raw,
    )
