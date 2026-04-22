from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .news_registry import NEWS_DOMAINS
from project_paths import (
    ECOSYSTEM_DIR,
    ECOSYSTEM_METRICS_DIR,
    ECOSYSTEM_RUNS_DIR,
    ECOSYSTEM_SNAPSHOTS_DIR,
    ECOSYSTEM_STATES_DIR,
    ensure_runtime_directories,
)
from runtime_support.artifacts import ArtifactStore, get_artifact_store
from runtime_support.env import load_project_env

from .config import VALID_WORKFLOW_STAGES, NewsAppConfig, load_news_app_config
from .metrics import NewsMetricsBuilder
from .pipeline import NewsWorkflowApp
from .state import NewsWorkflowStateBuilder


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_iso_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _parse_time(raw: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return (8, 0)

    if hour not in range(24) or minute not in range(60):
        return (8, 0)

    return (hour, minute)


import os


@dataclass(frozen=True)
class NewsEcosystemSettings:
    auto_run_enabled: bool
    auto_run_time: str
    auto_run_mode: str
    auto_run_on_start: bool
    scheduler_poll_seconds: int
    max_run_history: int

    @classmethod
    def load(cls) -> "NewsEcosystemSettings":
        load_project_env()
        auto_run_mode = os.getenv("NEWS_AUTO_RUN_MODE", "serial")
        if auto_run_mode not in {"serial", "parallel"}:
            auto_run_mode = "serial"

        return cls(
            auto_run_enabled=_bool_env("NEWS_AUTO_RUN_ENABLED", False),
            auto_run_time=os.getenv("NEWS_AUTO_RUN_TIME", "08:30"),
            auto_run_mode=auto_run_mode,
            auto_run_on_start=_bool_env("NEWS_AUTO_RUN_ON_START", False),
            scheduler_poll_seconds=_int_env("NEWS_SCHEDULER_POLL_SECONDS", 30),
            max_run_history=_int_env("NEWS_MAX_RUN_HISTORY", 30),
        )

    @property
    def scheduled_time(self) -> tuple[int, int]:
        return _parse_time(self.auto_run_time)


class NewsRunStore:
    def __init__(
        self,
        store: ArtifactStore | None = None,
        runs_dir: Path = ECOSYSTEM_RUNS_DIR,
        metrics_dir: Path = ECOSYSTEM_METRICS_DIR,
        states_dir: Path = ECOSYSTEM_STATES_DIR,
        snapshots_dir: Path = ECOSYSTEM_SNAPSHOTS_DIR,
        max_run_history: int = 30,
    ) -> None:
        ensure_runtime_directories()
        self.store = store or get_artifact_store()
        self.runs_dir = runs_dir
        self.metrics_dir = metrics_dir
        self.states_dir = states_dir
        self.snapshots_dir = snapshots_dir
        self.max_run_history = max_run_history
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.states_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, mode: str, source: str, stages: list[str]) -> dict[str, Any]:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        record = {
            "id": run_id,
            "mode": mode,
            "source": source,
            "stages": stages,
            "status": "queued",
            "created_at": now_iso(),
            "started_at": None,
            "finished_at": None,
            "message": None,
            "error": None,
            "events": [],
            "stage_summaries": {},
            "result": None,
            "snapshot_file": None,
            "metrics_file": None,
            "state_file": None,
            "report_file": None,
            "report_json_file": None,
            "report_html_file": None,
        }
        self.save_run(record)
        return record

    def save_run(self, record: dict[str, Any]) -> str:
        run_path = self.run_path(record["id"])
        self.store.write_json(run_path, record)
        self.store.write_json(ECOSYSTEM_DIR / "latest_run.json", record)
        self._trim_history()
        return str(run_path)

    def run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def snapshot_path(self, run_id: str) -> Path:
        return self.snapshots_dir / f"{run_id}.json"

    def state_path(self, run_id: str) -> Path:
        return self.states_dir / f"{run_id}.json"

    def metrics_path(self, run_id: str) -> Path:
        return self.metrics_dir / f"{run_id}.json"

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self.run_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        records = [self.store.read_json(file_path) for file_path in self.runs_dir.glob("*.json")]
        records.sort(
            key=lambda record: (
                _parse_iso_timestamp(record.get("created_at")),
                _parse_iso_timestamp(record.get("started_at")),
            ),
            reverse=True,
        )
        return records[:limit]

    def latest_run(self) -> dict[str, Any] | None:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def save_metrics(self, run_id: str, metrics: dict[str, Any]) -> str:
        path = self.metrics_path(run_id)
        self.store.write_json(path, metrics)
        self.store.write_json(self.metrics_dir / "latest.json", metrics)
        return str(path)

    def get_metrics(self, run_id: str) -> dict[str, Any] | None:
        path = self.metrics_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def latest_metrics(self) -> dict[str, Any] | None:
        path = self.metrics_dir / "latest.json"
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def save_state(self, run_id: str, state: dict[str, Any]) -> str:
        path = self.state_path(run_id)
        self.store.write_json(path, state)
        self.store.write_json(self.states_dir / "latest.json", state)
        return str(path)

    def get_state(self, run_id: str) -> dict[str, Any] | None:
        path = self.state_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def latest_state(self) -> dict[str, Any] | None:
        path = self.states_dir / "latest.json"
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def save_snapshot(self, run_id: str, snapshot: dict[str, Any]) -> str:
        path = self.snapshot_path(run_id)
        self.store.write_json(path, snapshot)
        self.store.write_json(self.snapshots_dir / "latest.json", snapshot)
        return str(path)

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        path = self.snapshot_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def latest_snapshot(self) -> dict[str, Any] | None:
        path = self.snapshots_dir / "latest.json"
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def _trim_history(self) -> None:
        files = list(self.runs_dir.glob("*.json"))
        files.sort(
            key=lambda file_path: _parse_iso_timestamp(
                self.store.read_json(file_path).get("created_at")
            ),
            reverse=True,
        )
        for stale_file in files[self.max_run_history :]:
            stale_file.unlink(missing_ok=True)


class NewsSnapshotBuilder:
    def __init__(
        self,
        config: NewsAppConfig | None = None,
        store: ArtifactStore | None = None,
    ) -> None:
        self.config = config or load_news_app_config()
        self.store = store or get_artifact_store()

    def build(self, run_record: dict[str, Any]) -> dict[str, Any]:
        report_file = self._resolve_report_file(run_record)
        report_json_file = self._resolve_report_json_file(run_record)
        report_html_file = self._resolve_report_html_file(run_record)
        report_content = self._read_optional_text(report_file)
        report_document = self._read_optional_json(report_json_file)
        report_html = self._read_optional_text(report_html_file)
        categories = [self._build_domain_snapshot(domain.name, domain.category_file) for domain in NEWS_DOMAINS]
        categories = self._merge_report_sections(categories, report_document)
        total_topics = sum(len(category["topics"]) for category in categories)
        total_articles = sum(len(category["articles"]) for category in categories)
        report_metrics = (report_document or {}).get("metrics") or {}
        total_articles = max(total_articles, int(report_metrics.get("total_articles") or 0))
        active_categories = sum(1 for category in categories if category["topics"] or category["articles"])
        active_categories = max(active_categories, int(report_metrics.get("active_sections") or 0))
        snapshot = {
            "run_id": run_record["id"],
            "generated_at": now_iso(),
            "status": run_record.get("status"),
            "message": run_record.get("message"),
            "metrics": {
                "total_topics": total_topics,
                "total_articles": total_articles,
                "active_categories": active_categories,
            },
            "report": {
                "file_path": report_file,
                "json_file_path": report_json_file,
                "html_file_path": report_html_file,
                "content": report_content,
                "excerpt": report_content[:600] if report_content else None,
                "document": report_document,
                "html": report_html,
            },
            "categories": categories,
            "timeline": run_record.get("events", []),
            "stage_summaries": run_record.get("stage_summaries", {}),
        }
        return snapshot

    def _resolve_report_file(self, run_record: dict[str, Any]) -> str | None:
        result = run_record.get("result") or {}
        report_result = (result.get("stage_results") or {}).get("report") or {}
        report_file = report_result.get("report_file")
        if report_file and self.store.exists(report_file):
            return str(report_file)

        candidates = sorted(
            self.config.output_dir.glob("新闻报_*.txt"),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
        return None

    def _resolve_report_json_file(self, run_record: dict[str, Any]) -> str | None:
        result = run_record.get("result") or {}
        report_result = (result.get("stage_results") or {}).get("report") or {}
        report_json_file = report_result.get("report_json_file")
        if report_json_file and self.store.exists(report_json_file):
            return str(report_json_file)

        candidates = sorted(
            self.config.output_dir.glob("新闻报_*.json"),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
        return None

    def _resolve_report_html_file(self, run_record: dict[str, Any]) -> str | None:
        result = run_record.get("result") or {}
        report_result = (result.get("stage_results") or {}).get("report") or {}
        report_html_file = report_result.get("report_html_file")
        if report_html_file and self.store.exists(report_html_file):
            return str(report_html_file)

        candidates = sorted(
            self.config.output_dir.glob("新闻报_*.html"),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
        return None

    def _build_domain_snapshot(self, category_name: str, category_file: str) -> dict[str, Any]:
        topics_path = self.config.intermediate_dir / category_file
        topics = self._read_topic_list(topics_path)
        articles = self._collect_articles(category_name)
        return {
            "name": category_name,
            "topic_count": len(topics),
            "article_count": len(articles),
            "topics": topics,
            "articles": articles,
        }

    def _merge_report_sections(
        self,
        categories: list[dict[str, Any]],
        report_document: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        section_lookup = self._report_section_lookup(report_document)
        merged: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for category in categories:
            name = category.get("name")
            report_section = section_lookup.get(name) if name else None
            merged_articles = category.get("articles") or []
            if not merged_articles and report_section:
                merged_articles = list(report_section.get("articles") or [])

            merged_category = {
                **category,
                "articles": merged_articles,
                "article_count": len(merged_articles),
            }
            merged.append(merged_category)
            if name:
                seen_names.add(name)

        for name, report_section in section_lookup.items():
            if name in seen_names:
                continue
            articles = list(report_section.get("articles") or [])
            merged.append(
                {
                    "name": name,
                    "topic_count": 0,
                    "article_count": len(articles),
                    "topics": [],
                    "articles": articles,
                }
            )

        return merged

    def _read_topic_list(self, path: Path) -> list[str]:
        if not self.store.exists(path):
            return []

        topics: list[str] = []
        for line in self.store.read_text(path).splitlines():
            normalized = line.strip()
            if normalized.startswith("- "):
                topics.append(normalized[2:].strip())
            elif normalized:
                topics.append(normalized)
        return topics

    def _collect_articles(self, category_name: str) -> list[dict[str, Any]]:
        intermediate_dir = self.config.intermediate_dir
        article_candidates: dict[int, Path] = {}

        for file_path in intermediate_dir.glob(f"{category_name}_*_news.txt"):
            match = re.search(rf"^{re.escape(category_name)}_(\d+)_news\.txt$", file_path.name)
            if match:
                article_candidates[int(match.group(1))] = file_path

        for file_path in intermediate_dir.glob(f"{category_name}_*_reviewed.txt"):
            match = re.search(rf"^{re.escape(category_name)}_(\d+)_reviewed\.txt$", file_path.name)
            if match:
                article_candidates[int(match.group(1))] = file_path

        articles = []
        for index, file_path in sorted(article_candidates.items()):
            raw_content = self.store.read_text(file_path)
            parsed = self._parse_article_content(raw_content)
            source_path = intermediate_dir / f"{category_name}_{index}_sources.json"
            sources_payload = self.store.read_json(source_path) if self.store.exists(source_path) else {}
            articles.append(
                {
                    "index": index,
                    "file_path": str(file_path),
                    "title": parsed["title"],
                    "summary": parsed["summary"],
                    "content": parsed["content"],
                    "raw_content": raw_content,
                    "sources": sources_payload.get("sources", []),
                }
            )
        return articles

    def _parse_article_content(self, raw_content: str) -> dict[str, str]:
        title_match = re.search(r"标题[：:]\s*(.*?)(?:\n\n|$)", raw_content, re.DOTALL)
        summary_match = re.search(r"摘要[：:]\s*(.*?)(?:\n\n|$)", raw_content, re.DOTALL)
        content_match = re.search(r"内容[：:]\s*(.*)$", raw_content, re.DOTALL)
        return {
            "title": title_match.group(1).strip() if title_match else "",
            "summary": summary_match.group(1).strip() if summary_match else "",
            "content": content_match.group(1).strip() if content_match else raw_content.strip(),
        }

    def _read_optional_text(self, path: str | None) -> str | None:
        if not path or not self.store.exists(path):
            return None
        return self.store.read_text(path)

    def _read_optional_json(self, path: str | None) -> dict[str, Any] | None:
        if not path or not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def _report_section_lookup(self, report_document: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for section in (report_document or {}).get("sections") or []:
            name = section.get("name")
            if name:
                lookup[name] = section
        return lookup


class NewsRunManager:
    def __init__(
        self,
        settings: NewsEcosystemSettings | None = None,
        store: NewsRunStore | None = None,
        snapshot_builder: NewsSnapshotBuilder | None = None,
        state_builder: NewsWorkflowStateBuilder | None = None,
        metrics_builder: NewsMetricsBuilder | None = None,
    ) -> None:
        self.settings = settings or NewsEcosystemSettings.load()
        self.store = store or NewsRunStore(max_run_history=self.settings.max_run_history)
        self.snapshot_builder = snapshot_builder or NewsSnapshotBuilder()
        self.state_builder = state_builder or NewsWorkflowStateBuilder()
        self.metrics_builder = metrics_builder or NewsMetricsBuilder()
        self._lock = threading.RLock()
        self._active_run_id: str | None = None
        self._worker: threading.Thread | None = None
        self._mark_orphaned_runs()

    def is_running(self) -> bool:
        return bool(self._worker and self._worker.is_alive())

    def trigger_run(
        self,
        mode: str = "serial",
        source: str = "manual",
        stages: list[str] | None = None,
        resume_from_existing: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"serial", "parallel"}:
            raise ValueError(f"Unsupported run mode: {mode}")

        normalized_stages = self._normalize_stage_override(stages)

        with self._lock:
            if self.is_running():
                return {
                    "accepted": False,
                    "reason": "run_in_progress",
                    "run_id": self._active_run_id,
                }

            run_record = self.store.create_run(
                mode=mode,
                source=source,
                stages=normalized_stages or list(load_news_app_config().workflow_stage_order),
            )
            run_record["resume_from_existing"] = bool(resume_from_existing)
            self._persist_state(run_record)
            self._active_run_id = run_record["id"]
            self._worker = threading.Thread(
                target=self._execute_run,
                args=(run_record["id"], mode, normalized_stages, bool(resume_from_existing)),
                daemon=True,
            )
            self._worker.start()
            return {
                "accepted": True,
                "run_id": run_record["id"],
                "mode": mode,
                "source": source,
                "stages": run_record["stages"],
                "resume": bool(resume_from_existing),
                "status": "queued",
            }

    def status(self) -> dict[str, Any]:
        latest_run = self.store.latest_run()
        latest_snapshot = self.store.latest_snapshot()
        active_run = self.store.get_run(self._active_run_id) if self._active_run_id else None

        return {
            "service": "news-ecosystem",
            "active_run_id": self._active_run_id,
            "running": self.is_running(),
            "active_run": self._summarize_run(active_run) if active_run else None,
            "latest_run": self._summarize_run(latest_run) if latest_run else None,
            "latest_snapshot": self._summarize_snapshot(latest_snapshot) if latest_snapshot else None,
            "settings": {
                "auto_run_enabled": self.settings.auto_run_enabled,
                "auto_run_time": self.settings.auto_run_time,
                "auto_run_mode": self.settings.auto_run_mode,
            },
        }

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self._summarize_run(record) for record in self.store.list_runs(limit=limit)]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_run(run_id)

    def latest_snapshot(self) -> dict[str, Any] | None:
        return self.store.latest_snapshot()

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_snapshot(run_id)

    def latest_state(self) -> dict[str, Any] | None:
        state = self.store.latest_state()
        latest_run = self.store.latest_run()
        if state and latest_run:
            state_run = (state.get("run") or {}).get("id")
            latest_report_exists = any(
                self.state_builder.config.output_dir.glob("新闻报_*.html")
            )
            if state_run == latest_run.get("id") and (
                (state.get("report") or {}).get("html_available") or not latest_report_exists
            ):
                return state
        elif state:
            return state

        if not latest_run:
            return None

        snapshot = self.store.get_snapshot(latest_run["id"]) or self.store.latest_snapshot()
        state = self.state_builder.build(latest_run, snapshot=snapshot)
        latest_run["state_file"] = self.store.save_state(latest_run["id"], state)
        self.store.save_run(latest_run)
        return state

    def get_state(self, run_id: str) -> dict[str, Any] | None:
        state = self.store.get_state(run_id)
        if state:
            return state

        run_record = self.store.get_run(run_id)
        if not run_record:
            return None

        snapshot = self.store.get_snapshot(run_id)
        state = self.state_builder.build(run_record, snapshot=snapshot)
        run_record["state_file"] = self.store.save_state(run_id, state)
        self.store.save_run(run_record)
        return state

    def latest_metrics(self) -> dict[str, Any] | None:
        metrics = self.store.latest_metrics()
        if metrics:
            return metrics

        latest_run = self.store.latest_run()
        if not latest_run:
            return None
        return self.get_metrics(latest_run["id"])

    def get_metrics(self, run_id: str) -> dict[str, Any] | None:
        metrics = self.store.get_metrics(run_id)
        if metrics:
            return metrics

        run_record = self.store.get_run(run_id)
        if not run_record:
            return None

        state = self.get_state(run_id)
        snapshot = self.store.get_snapshot(run_id)
        previous_metrics = self._previous_metrics_before(run_id)
        metrics = self.metrics_builder.build(
            run_record,
            state or {},
            snapshot=snapshot,
            previous_metrics=previous_metrics,
        )
        run_record["metrics_file"] = self.store.save_metrics(run_id, metrics)
        self.store.save_run(run_record)
        return metrics

    def dashboard(self, limit: int = 8) -> dict[str, Any]:
        latest_run = self.store.latest_run()
        latest_snapshot = self.store.latest_snapshot()
        latest_state = self.latest_state()
        latest_metrics = self.latest_metrics()
        recent_runs = self.store.list_runs(limit=limit)
        return {
            "generated_at": now_iso(),
            "status": self.status(),
            "latest_run": self._summarize_run(latest_run),
            "latest_snapshot": latest_snapshot,
            "latest_state": latest_state,
            "latest_metrics": latest_metrics,
            "recent_runs": [self._summarize_run(record) for record in recent_runs],
            "available_stages": list(VALID_WORKFLOW_STAGES),
            "links": {
                "latest_report_html": "/api/ecosystem/reports/latest/html",
                "latest_report_json": "/api/ecosystem/output/report/latest",
                "latest_snapshot": "/api/ecosystem/news/latest",
                "latest_metrics": "/api/ecosystem/metrics/latest",
            },
        }

    def _execute_run(
        self,
        run_id: str,
        mode: str,
        stages: list[str] | None,
        resume_from_existing: bool,
    ) -> None:
        record = self.store.get_run(run_id)
        if not record:
            return

        record["status"] = "running"
        record["started_at"] = now_iso()
        self.store.save_run(record)
        self._persist_state(record)

        def handle_event(event: dict[str, Any]) -> None:
            with self._lock:
                current = self.store.get_run(run_id) or record
                current.setdefault("events", []).append(event)
                if event["event"] == "stage_started":
                    current.setdefault("stage_summaries", {})[event["stage"]] = {
                        "label": event.get("label"),
                        "status": "running",
                        "duration": None,
                        "summary": None,
                        "output_count": 0,
                        "domain_breakdown": {
                            "success_domains": 0,
                            "failed_domains": 0,
                            "total_outputs": 0,
                        },
                    }
                if event["event"] == "stage_finished":
                    current.setdefault("stage_summaries", {})[event["stage"]] = {
                        "label": event.get("label"),
                        "status": event.get("status"),
                        "duration": event.get("duration"),
                        "summary": event.get("summary"),
                        "output_count": event.get("output_count", 0),
                        "domain_breakdown": event.get("domain_breakdown")
                        or {
                            "success_domains": 0,
                            "failed_domains": 0,
                            "total_outputs": 0,
                        },
                    }
                self.store.save_run(current)
                self._persist_state(current)

        try:
            app = NewsWorkflowApp(
                mode=mode,
                stage_order_override=stages,
                resume_from_existing=resume_from_existing,
                event_handler=handle_event,
            )
            result = app.run()
            current = self.store.get_run(run_id) or record
            current["status"] = result.get("status", "failed")
            current["message"] = result.get("message")
            current["finished_at"] = now_iso()
            current["result"] = result
            report_stage_result = (result.get("stage_results") or {}).get("report") or {}
            report_file = report_stage_result.get("report_file")
            current["report_file"] = report_file
            current["report_json_file"] = report_stage_result.get("report_json_file")
            current["report_html_file"] = report_stage_result.get("report_html_file")

            if result.get("status") == "success":
                snapshot = self.snapshot_builder.build(current)
                current["snapshot_file"] = self.store.save_snapshot(run_id, snapshot)
            else:
                current["error"] = result.get("message")

            self.store.save_run(current)
            self._persist_state(current)
        except Exception as exc:
            current = self.store.get_run(run_id) or record
            current["status"] = "failed"
            current["message"] = str(exc)
            current["error"] = str(exc)
            current["finished_at"] = now_iso()
            self.store.save_run(current)
            self._persist_state(current)
        finally:
            with self._lock:
                self._active_run_id = None

    def _normalize_stage_override(self, stages: list[str] | None) -> list[str] | None:
        if not stages:
            return None

        normalized = []
        for stage in stages:
            if stage not in VALID_WORKFLOW_STAGES:
                raise ValueError(f"Unsupported stage: {stage}")
            if stage not in normalized:
                normalized.append(stage)
        return normalized

    def _summarize_run(self, record: dict[str, Any] | None) -> dict[str, Any] | None:
        if not record:
            return None
        return {
            "id": record.get("id"),
            "status": record.get("status"),
            "mode": record.get("mode"),
            "source": record.get("source"),
            "created_at": record.get("created_at"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "message": record.get("message"),
            "snapshot_file": record.get("snapshot_file"),
            "metrics_file": record.get("metrics_file"),
            "state_file": record.get("state_file"),
            "report_file": record.get("report_file"),
            "report_json_file": record.get("report_json_file"),
            "report_html_file": record.get("report_html_file"),
        }

    def _summarize_snapshot(self, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
        if not snapshot:
            return None
        return {
            "run_id": snapshot.get("run_id"),
            "generated_at": snapshot.get("generated_at"),
            "status": snapshot.get("status"),
            "metrics": snapshot.get("metrics"),
            "report_excerpt": (snapshot.get("report") or {}).get("excerpt"),
        }

    def _persist_state(self, record: dict[str, Any]) -> None:
        snapshot = None
        snapshot_file = record.get("snapshot_file")
        if snapshot_file and self.store.store.exists(snapshot_file):
            snapshot = self.store.store.read_json(snapshot_file)
        else:
            snapshot = self.store.get_snapshot(record["id"])

        state = self.state_builder.build(record, snapshot=snapshot)
        record["state_file"] = self.store.save_state(record["id"], state)
        previous_metrics = self._previous_metrics_before(record["id"])
        metrics = self.metrics_builder.build(
            record,
            state,
            snapshot=snapshot,
            previous_metrics=previous_metrics,
        )
        record["metrics_file"] = self.store.save_metrics(record["id"], metrics)
        self.store.save_run(record)

    def _previous_metrics_before(self, run_id: str) -> dict[str, Any] | None:
        records = self.store.list_runs(limit=self.settings.max_run_history)
        for record in records:
            if record.get("id") == run_id:
                continue
            if record.get("status") != "success":
                continue
            metrics_file = record.get("metrics_file")
            if metrics_file and self.store.store.exists(metrics_file):
                return self.store.store.read_json(metrics_file)
            metrics = self.store.get_metrics(record.get("id"))
            if metrics:
                return metrics
        return None

    def _mark_orphaned_runs(self) -> None:
        updated = False
        for record in self.store.list_runs(limit=self.settings.max_run_history):
            if record.get("status") not in {"running", "queued"}:
                continue
            record["status"] = "failed"
            record["finished_at"] = record.get("finished_at") or now_iso()
            record["message"] = record.get("message") or "服务重启导致任务中断"
            record["error"] = record.get("error") or "interrupted_after_restart"
            self.store.save_run(record)
            self._persist_state(record)
            updated = True
        if updated:
            self._active_run_id = None


class NewsScheduler:
    def __init__(self, manager: NewsRunManager, settings: NewsEcosystemSettings) -> None:
        self.manager = manager
        self.settings = settings
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_auto_run_date: str | None = None

    def start(self) -> None:
        if self.settings.auto_run_on_start:
            self.manager.trigger_run(mode=self.settings.auto_run_mode, source="startup")

        if not self.settings.auto_run_enabled:
            return

        if self._thread and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.auto_run_enabled,
            "auto_run_time": self.settings.auto_run_time,
            "auto_run_mode": self.settings.auto_run_mode,
            "running": bool(self._thread and self._thread.is_alive()),
            "last_auto_run_date": self._last_auto_run_date,
        }

    def _loop(self) -> None:
        target_hour, target_minute = self.settings.scheduled_time
        while self._running:
            now = datetime.now().astimezone()
            today = now.date().isoformat()
            latest_run = self.manager.store.latest_run()
            already_ran_today = bool(
                latest_run
                and (latest_run.get("started_at") or latest_run.get("created_at") or "").startswith(today)
            )

            if (
                not self.manager.is_running()
                and not already_ran_today
                and (now.hour, now.minute) >= (target_hour, target_minute)
            ):
                result = self.manager.trigger_run(
                    mode=self.settings.auto_run_mode,
                    source="scheduler",
                )
                if result.get("accepted"):
                    self._last_auto_run_date = today

            time.sleep(self.settings.scheduler_poll_seconds)
