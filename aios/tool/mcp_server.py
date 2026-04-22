from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.news_app.mcp_support import (
    build_latest_news_markdown,
    build_latest_news_payload,
    get_news_mcp_settings,
    read_latest_report_html,
    read_latest_report_json,
    read_latest_report_text,
    read_latest_snapshot,
)

settings = get_news_mcp_settings()

mcp = FastMCP(
    name=settings["name"],
    instructions=(
        "Expose the latest AIOS daily news report so any MCP-capable agent can read "
        "today's news as a concise summary, structured payload, raw JSON, HTML, or text."
    ),
    host=settings["host"],
    port=settings["port"],
    streamable_http_path=settings["path"],
    log_level="ERROR",
)


@mcp.resource(
    "news://latest/summary",
    name="latest-news-summary",
    title="Latest AIOS News Summary",
    description="Markdown summary of the latest AIOS daily news report.",
    mime_type="text/markdown",
)
def latest_news_summary_resource() -> str:
    return build_latest_news_markdown()


@mcp.resource(
    "news://latest/report-json",
    name="latest-news-report-json",
    title="Latest AIOS News JSON",
    description="Raw JSON payload for the latest AIOS daily news report.",
    mime_type="application/json",
)
def latest_news_report_json_resource() -> str:
    return json.dumps(read_latest_report_json(), ensure_ascii=False, indent=2)


@mcp.resource(
    "news://latest/report-html",
    name="latest-news-report-html",
    title="Latest AIOS News HTML",
    description="Raw HTML report for the latest AIOS daily news output.",
    mime_type="text/html",
)
def latest_news_report_html_resource() -> str:
    return read_latest_report_html()


@mcp.resource(
    "news://latest/report-text",
    name="latest-news-report-text",
    title="Latest AIOS News Text",
    description="Plain text report for the latest AIOS daily news output.",
    mime_type="text/plain",
)
def latest_news_report_text_resource() -> str:
    return read_latest_report_text()


@mcp.resource(
    "news://latest/snapshot",
    name="latest-news-snapshot",
    title="Latest AIOS News Snapshot",
    description="Latest ecosystem snapshot metadata for the current daily news run.",
    mime_type="application/json",
)
def latest_news_snapshot_resource() -> str:
    return json.dumps(read_latest_snapshot(), ensure_ascii=False, indent=2)


@mcp.tool(
    name="get_today_news_brief",
    title="Get Today News Brief",
    description=(
        "Return the latest AIOS daily news report as a concise markdown summary "
        "that any agent can directly read."
    ),
)
def get_today_news_brief(
    max_sections: int = 5,
    max_articles_per_section: int = 5,
) -> str:
    return build_latest_news_markdown(
        max_sections=max(1, min(max_sections, 12)),
        max_articles_per_section=max(1, min(max_articles_per_section, 12)),
    )


@mcp.tool(
    name="get_today_news_payload",
    title="Get Today News Payload",
    description=(
        "Return the latest AIOS daily news report as a structured object including "
        "overview, highlights, sections, article summaries, and optional raw content."
    ),
    structured_output=True,
)
def get_today_news_payload(
    max_sections: int = 5,
    max_articles_per_section: int = 5,
    include_content: bool = True,
    include_sources: bool = False,
) -> dict[str, Any]:
    return build_latest_news_payload(
        max_sections=max(1, min(max_sections, 12)),
        max_articles_per_section=max(1, min(max_articles_per_section, 12)),
        include_content=include_content,
        include_sources=include_sources,
    )


def main() -> None:
    mcp.run(settings["transport"])


if __name__ == "__main__":
    main()
