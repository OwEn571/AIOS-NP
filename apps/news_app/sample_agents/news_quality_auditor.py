from __future__ import annotations

from typing import Any


def _pick_context(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("context") or {}
    if "latest_state" in context or "latest_metrics" in context or "latest_report" in context:
        return context
    user_context = context.get("user_context")
    if isinstance(user_context, dict):
        return user_context
    return context


def run(payload: dict[str, Any]) -> dict[str, Any]:
    context = _pick_context(payload)
    latest_metrics = context.get("latest_metrics") or {}
    latest_state = context.get("latest_state") or {}
    latest_report = context.get("latest_report") or {}

    quality = latest_metrics.get("quality") or {}
    report_info = latest_state.get("report") or latest_report or {}
    coverage = latest_state.get("coverage") or {}
    run_meta = latest_state.get("run") or {}

    title_pass = float(quality.get("title_length_pass_rate") or 0.0)
    summary_pass = float(quality.get("summary_length_pass_rate") or 0.0)
    content_pass = float(quality.get("content_length_pass_rate") or 0.0)
    multi_source_rate = float(quality.get("multi_source_article_rate") or 0.0)

    weaknesses: list[str] = []
    if title_pass < 0.9:
        weaknesses.append("标题长度稳定性仍然偏弱，建议继续压 prompt 和标题规则。")
    if multi_source_rate < 1.0:
        weaknesses.append("多信源覆盖率未达 100%，需要收紧检索结果准入。")
    if not weaknesses:
        weaknesses.append("当前核心质量指标已达标，下一步更值得优化题材选择和新闻性。")

    return {
        "agent": "news-quality-auditor",
        "task": payload.get("input") or "质量审计",
        "run_id": run_meta.get("id") or run_meta.get("run_id"),
        "generated_at": run_meta.get("finished_at") or run_meta.get("ended_at") or run_meta.get("started_at"),
        "report_headline": report_info.get("title") or report_info.get("headline"),
        "article_count": report_info.get("article_count") or coverage.get("total_articles") or quality.get("article_count"),
        "active_domains": coverage.get("active_categories") or coverage.get("active_domains"),
        "quality_scorecard": {
            "title_length_pass_rate": title_pass,
            "summary_length_pass_rate": summary_pass,
            "content_length_pass_rate": content_pass,
            "multi_source_article_rate": multi_source_rate,
        },
        "primary_strength": "工作流已经具备可观测性、可恢复性和多阶段质量闸门。",
        "primary_weaknesses": weaknesses,
        "next_actions": [
            "继续优化标题约束和栏目新闻性 gate。",
            "把低质量题材拦截提前到 search/generate 之前。",
            "为动态 agent 增加更细的权限和工具目录管理。",
        ],
    }
