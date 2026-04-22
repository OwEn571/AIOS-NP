from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from project_paths import ECOSYSTEM_SNAPSHOTS_DIR, OUTPUT_DIR
from runtime_support.env import load_project_env

DEFAULT_NEWS_MCP_HOST = "0.0.0.0"
DEFAULT_NEWS_MCP_PORT = 8011
DEFAULT_NEWS_MCP_TRANSPORT = "streamable-http"
DEFAULT_NEWS_MCP_PATH = "/"

NEWS_MCP_TOOL_NAMES = [
    "get_today_news_brief",
    "get_today_news_payload",
]

NEWS_MCP_RESOURCE_URIS = [
    "news://latest/summary",
    "news://latest/report-json",
    "news://latest/report-html",
    "news://latest/report-text",
    "news://latest/snapshot",
]


def _normalize_http_path(raw: str | None) -> str:
    path = (raw or DEFAULT_NEWS_MCP_PATH).strip() or DEFAULT_NEWS_MCP_PATH
    if not path.startswith("/"):
        path = f"/{path}"
    trimmed = path.rstrip("/")
    return trimmed or "/"


def _safe_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _latest_file(directory: Path, pattern: str) -> Path | None:
    candidates = sorted(
        directory.glob(pattern),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _today_date() -> datetime.date:
    return datetime.now().astimezone().date()


def _parse_generated_at(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _connectable_local_url(host: str, port: int, path: str) -> str:
    base_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    suffix = "" if path == "/" else path
    return f"http://{base_host}:{port}{suffix or '/'}"


def get_news_mcp_settings() -> dict[str, Any]:
    load_project_env()

    host = os.getenv("NEWS_MCP_HOST", DEFAULT_NEWS_MCP_HOST)
    port = _safe_int(os.getenv("NEWS_MCP_PORT"), DEFAULT_NEWS_MCP_PORT)
    transport = os.getenv("NEWS_MCP_TRANSPORT", DEFAULT_NEWS_MCP_TRANSPORT).strip() or DEFAULT_NEWS_MCP_TRANSPORT
    path = _normalize_http_path(os.getenv("NEWS_MCP_PATH", DEFAULT_NEWS_MCP_PATH))
    public_url = (os.getenv("NEWS_MCP_PUBLIC_URL") or "").strip()

    return {
        "name": "AIOS Daily News MCP",
        "host": host,
        "port": port,
        "transport": transport,
        "path": path,
        "local_url": _connectable_local_url(host, port, path),
        "public_url": public_url or None,
        "tool_names": NEWS_MCP_TOOL_NAMES,
        "resource_uris": NEWS_MCP_RESOURCE_URIS,
    }


def get_news_mcp_metadata() -> dict[str, Any]:
    settings = get_news_mcp_settings()
    return {
        **settings,
        "description": "Expose the latest AIOS daily news report as MCP tools and resources.",
    }


def read_latest_report_json() -> dict[str, Any]:
    report_path = _latest_file(OUTPUT_DIR, "新闻报_*.json")
    if not report_path:
        raise FileNotFoundError("No latest report JSON available.")
    return json.loads(report_path.read_text(encoding="utf-8"))


def read_latest_report_html() -> str:
    report_path = _latest_file(OUTPUT_DIR, "新闻报_*.html")
    if not report_path:
        raise FileNotFoundError("No latest report HTML available.")
    return report_path.read_text(encoding="utf-8")


def read_latest_report_text() -> str:
    report_path = _latest_file(OUTPUT_DIR, "新闻报_*.txt")
    if not report_path:
        raise FileNotFoundError("No latest report text available.")
    return report_path.read_text(encoding="utf-8")


def read_latest_snapshot() -> dict[str, Any]:
    snapshot_path = ECOSYSTEM_SNAPSHOTS_DIR / "latest.json"
    if snapshot_path.exists():
        return json.loads(snapshot_path.read_text(encoding="utf-8"))

    snapshot_path = _latest_file(ECOSYSTEM_SNAPSHOTS_DIR, "*.json")
    if not snapshot_path:
        raise FileNotFoundError("No latest ecosystem snapshot available.")
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def _trim_article(
    article: dict[str, Any],
    *,
    include_content: bool,
    include_sources: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "index": article.get("index"),
        "title": article.get("title"),
        "topic": article.get("topic"),
        "summary": article.get("summary"),
        "display_category": article.get("display_category"),
        "source_count": article.get("source_count", len(article.get("sources") or [])),
        "trusted_source_count": article.get("trusted_source_count"),
        "top_source_score": article.get("top_source_score"),
    }
    if include_content:
        payload["content"] = article.get("content")
    if include_sources:
        payload["sources"] = article.get("sources") or []
    if article.get("image"):
        payload["image"] = article.get("image")
    return payload


def _trim_sections(
    sections: list[dict[str, Any]],
    *,
    max_sections: int,
    max_articles_per_section: int,
    include_content: bool,
    include_sources: bool,
) -> list[dict[str, Any]]:
    trimmed_sections: list[dict[str, Any]] = []
    for section in sections[:max_sections]:
        articles = section.get("articles") or []
        trimmed_sections.append(
            {
                "name": section.get("name"),
                "accent": section.get("accent"),
                "article_count": section.get("article_count", len(articles)),
                "articles": [
                    _trim_article(
                        article,
                        include_content=include_content,
                        include_sources=include_sources,
                    )
                    for article in articles[:max_articles_per_section]
                ],
            }
        )
    return trimmed_sections


def build_latest_news_markdown(
    *,
    max_sections: int = 5,
    max_articles_per_section: int = 5,
) -> str:
    report = read_latest_report_json()
    generated_at = _parse_generated_at(report.get("generated_at"))
    metrics = report.get("metrics") or {}
    lines = [
        f"# {report.get('report_title') or 'AIOS 当日新闻'}",
        "",
        report.get("report_subtitle") or "",
        "",
        f"- 生成时间: {report.get('generated_at') or 'N/A'}",
        f"- 日期标签: {report.get('date_label') or 'N/A'}",
        f"- 是否为当日: {'是' if generated_at and generated_at.date() == _today_date() else '否'}",
        f"- 成稿数: {metrics.get('total_articles', 0)}",
        f"- 栏目数: {metrics.get('active_sections', 0)}",
        f"- 信源数: {metrics.get('total_sources', 0)}",
        "",
        "## 今日概览",
        "",
        report.get("overview") or "暂无概览。",
        "",
    ]

    highlights = report.get("highlights") or []
    if highlights:
        lines.extend(["## 重点摘要", ""])
        for index, item in enumerate(highlights, start=1):
            category = item.get("category") or "未分类"
            title = item.get("title") or "未命名条目"
            summary = item.get("summary") or "暂无摘要。"
            lines.append(f"{index}. [{category}] {title}")
            lines.append(f"   {summary}")
        lines.append("")

    sections = report.get("sections") or []
    if sections:
        lines.append("## 栏目详情")
        lines.append("")
        for section in sections[:max_sections]:
            lines.append(f"### {section.get('name') or '未命名栏目'}")
            lines.append("")
            articles = section.get("articles") or []
            for index, article in enumerate(articles[:max_articles_per_section], start=1):
                title = article.get("title") or "未命名新闻"
                summary = article.get("summary") or "暂无摘要。"
                source_count = article.get("source_count", len(article.get("sources") or []))
                lines.append(f"{index}. {title}")
                lines.append(f"   - 摘要: {summary}")
                lines.append(f"   - 信源数: {source_count}")
            lines.append("")

    return "\n".join(lines).strip()


def build_latest_news_payload(
    *,
    max_sections: int = 5,
    max_articles_per_section: int = 5,
    include_content: bool = True,
    include_sources: bool = False,
) -> dict[str, Any]:
    report = read_latest_report_json()
    snapshot = read_latest_snapshot()
    generated_at = _parse_generated_at(report.get("generated_at"))

    return {
        "status": "ok",
        "report_title": report.get("report_title"),
        "report_subtitle": report.get("report_subtitle"),
        "overview": report.get("overview"),
        "generated_at": report.get("generated_at"),
        "date_label": report.get("date_label"),
        "time_label": report.get("time_label"),
        "is_today": bool(generated_at and generated_at.date() == _today_date()),
        "metrics": report.get("metrics") or {},
        "highlights": report.get("highlights") or [],
        "sections": _trim_sections(
            report.get("sections") or [],
            max_sections=max_sections,
            max_articles_per_section=max_articles_per_section,
            include_content=include_content,
            include_sources=include_sources,
        ),
        "snapshot": {
            "run_id": snapshot.get("run_id"),
            "status": snapshot.get("status"),
            "generated_at": snapshot.get("generated_at"),
        },
        "markdown_summary": build_latest_news_markdown(
            max_sections=max_sections,
            max_articles_per_section=max_articles_per_section,
        ),
    }
