from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .news_registry import NEWS_DOMAINS
from runtime_support.artifacts import ArtifactStore, get_artifact_store

from .config import NewsAppConfig, load_news_app_config
from .pipeline import STAGE_LABELS


ARTIFACT_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("hot_api_text", "热榜原始文本", "hot_api.txt"),
    ("hot_api_json", "热榜结构化数据", "hot_api.json"),
    ("category_topics", "领域分类结果", "*_api.txt"),
    ("search_results", "搜索结果", "*_search.txt"),
    ("image_notes", "配图线索", "*_image.txt"),
    ("generated_news", "生成稿件", "*_news.txt"),
    ("reviewed_news", "审阅稿件", "*_reviewed.txt"),
    ("source_notes", "信源结构化记录", "*_sources.json"),
)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

def _score_to_level(score: int) -> tuple[str, str]:
    if score >= 85:
        return ("excellent", "完成度很强")
    if score >= 70:
        return ("strong", "主线可演示")
    if score >= 50:
        return ("partial", "结构成型")
    return ("early", "还需补强")


class NewsWorkflowStateBuilder:
    def __init__(
        self,
        config: NewsAppConfig | None = None,
        store: ArtifactStore | None = None,
    ) -> None:
        self.config = config or load_news_app_config()
        self.store = store or get_artifact_store()

    def build(
        self,
        run_record: dict[str, Any],
        snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        snapshot = snapshot or {}
        stage_flow = self._build_stage_flow(run_record)
        artifacts = self._build_artifact_inventory(run_record)
        domains = self._build_domain_coverage(snapshot)
        report = self._build_report_summary(snapshot)
        coverage = self._build_coverage(snapshot, domains, report)
        evaluation = self._build_evaluation(run_record, stage_flow, coverage, report)
        recent_events = list((run_record.get("events") or [])[-20:])

        started_at = _parse_iso(run_record.get("started_at"))
        finished_at = _parse_iso(run_record.get("finished_at"))
        duration_seconds = None
        if started_at and finished_at:
            duration_seconds = round((finished_at - started_at).total_seconds(), 2)

        return {
            "version": "1.0",
            "run": {
                "id": run_record.get("id"),
                "status": run_record.get("status"),
                "mode": run_record.get("mode"),
                "source": run_record.get("source"),
                "created_at": run_record.get("created_at"),
                "started_at": run_record.get("started_at"),
                "finished_at": run_record.get("finished_at"),
                "duration_seconds": duration_seconds,
                "planned_stages": run_record.get("stages") or list(self.config.workflow_stage_order),
                "completed_stages": sum(
                    1 for item in stage_flow if item["status"] in {"success", "failed", "partial"}
                ),
            },
            "coverage": coverage,
            "evaluation": evaluation,
            "stage_flow": stage_flow,
            "domains": domains,
            "artifacts": artifacts,
            "report": report,
            "recent_events": recent_events,
        }

    def _build_stage_flow(self, run_record: dict[str, Any]) -> list[dict[str, Any]]:
        planned_stages = list(run_record.get("stages") or self.config.workflow_stage_order)
        stage_results = (run_record.get("result") or {}).get("stage_results") or {}
        stage_summaries = run_record.get("stage_summaries") or {}

        stage_flow: list[dict[str, Any]] = []
        for index, stage_name in enumerate(planned_stages, start=1):
            summary = stage_summaries.get(stage_name) or {}
            result = stage_results.get(stage_name) or {}
            status = summary.get("status") or result.get("status") or "pending"
            output_count = summary.get("output_count")
            if output_count is None:
                output_count = self._stage_output_count(stage_name, result)
            domain_breakdown = summary.get("domain_breakdown")
            if not domain_breakdown:
                domain_breakdown = self._stage_domain_breakdown(result)
            stage_flow.append(
                {
                    "order": index,
                    "stage": stage_name,
                    "label": summary.get("label") or STAGE_LABELS.get(stage_name, stage_name),
                    "status": status,
                    "duration": summary.get("duration"),
                    "summary": summary.get("summary") or result.get("message") or result.get("result"),
                    "output_count": output_count,
                    "domain_breakdown": domain_breakdown,
                }
            )
        return stage_flow

    def _stage_output_count(self, stage_name: str, result: dict[str, Any]) -> int:
        if not result:
            return 0
        if stage_name == "hot_api":
            payload = result.get("payload") or {}
            return int(payload.get("total_topics") or 0)
        if stage_name == "sort":
            return len(result.get("saved_files") or [])
        if stage_name == "search":
            return len(result.get("search_files") or result.get("news_files") or [])
        if stage_name == "generate":
            return len(result.get("news_files") or [])
        if stage_name == "review":
            return len(result.get("reviewed_files") or result.get("news_files") or [])
        if stage_name == "report":
            return int(bool(result.get("report_file")))
        return 0

    def _stage_domain_breakdown(self, result: dict[str, Any]) -> dict[str, int]:
        domain_results = result.get("domain_results") or {}
        success_count = 0
        failed_count = 0
        total_outputs = 0
        for domain_result in domain_results.values():
            if domain_result.get("status") == "success":
                success_count += 1
            else:
                failed_count += 1
            total_outputs += int(domain_result.get("count") or 0)
        return {
            "success_domains": success_count,
            "failed_domains": failed_count,
            "total_outputs": total_outputs,
        }

    def _build_domain_coverage(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        categories = snapshot.get("categories") or []
        if not categories:
            categories = [
                self._build_domain_snapshot(domain.name, domain.category_file)
                for domain in NEWS_DOMAINS
            ]
        category_lookup = {item.get("name"): item for item in categories}
        report_sections = self._report_section_lookup(snapshot)

        domains: list[dict[str, Any]] = []
        for domain in NEWS_DOMAINS:
            category = category_lookup.get(domain.name) or {}
            topics = category.get("topics") or []
            articles = category.get("articles") or []
            if not articles:
                articles = (report_sections.get(domain.name) or {}).get("articles") or []
            source_count = sum(len(article.get("sources") or []) for article in articles)
            article_titles = [article.get("title") for article in articles if article.get("title")]
            coverage_ratio = 0
            if topics:
                coverage_ratio = round(min(len(articles) / len(topics), 1.0) * 100)
            elif articles:
                coverage_ratio = 100

            if articles and topics:
                status = "ready"
            elif topics or articles:
                status = "partial"
            else:
                status = "empty"

            domains.append(
                {
                    "name": domain.name,
                    "description": domain.description,
                    "topic_count": len(topics),
                    "article_count": len(articles),
                    "source_count": source_count,
                    "coverage_ratio": coverage_ratio,
                    "status": status,
                    "titles": article_titles[:3],
                }
            )
        return domains

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

    def _build_artifact_inventory(self, run_record: dict[str, Any]) -> dict[str, Any]:
        groups = []
        for key, label, pattern in ARTIFACT_PATTERNS:
            files = self.store.glob_in(self.config.intermediate_dir, pattern)
            if key == "category_topics":
                files = [path for path in files if path.name != "hot_api.txt"]
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "pattern": pattern,
                    "count": len(files),
                    "sample_files": [str(path) for path in files[:4]],
                }
            )

        output_reports = sorted(
            self.config.output_dir.glob("新闻报_*.*"),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        report_result = ((run_record.get("result") or {}).get("stage_results") or {}).get("report") or {}

        return {
            "intermediate": groups,
            "outputs": [
                {
                    "key": "reports",
                    "label": "日报产物",
                    "count": len(output_reports),
                    "sample_files": [str(path) for path in output_reports[:6]],
                }
            ],
            "paths": {
                "intermediate_dir": str(self.config.intermediate_dir),
                "output_dir": str(self.config.output_dir),
                "report_file": report_result.get("report_file"),
                "report_json_file": report_result.get("report_json_file"),
                "report_html_file": report_result.get("report_html_file"),
            },
        }

    def _build_report_summary(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        report = snapshot.get("report") or {}
        document = report.get("document") or {}
        file_path = report.get("file_path")
        json_file_path = report.get("json_file_path")
        html_file_path = report.get("html_file_path")
        html_available = bool(report.get("html"))

        if not document and json_file_path and self.store.exists(json_file_path):
            document = self.store.read_json(json_file_path)

        if html_file_path and self.store.exists(html_file_path):
            html_available = True

        highlights = document.get("highlights") or []
        sections = document.get("sections") or []
        return {
            "title": document.get("report_title") or "今日新闻现场",
            "subtitle": document.get("report_subtitle") or "",
            "overview": document.get("overview") or report.get("excerpt") or "",
            "generated_at": document.get("generated_at") or snapshot.get("generated_at"),
            "date_label": document.get("date_label"),
            "metrics": document.get("metrics") or {},
            "highlight_titles": [
                item.get("title") for item in highlights[:6] if item.get("title")
            ],
            "section_names": [section.get("name") for section in sections if section.get("name")],
            "html_available": html_available,
            "file_path": file_path,
            "json_file_path": json_file_path,
            "html_file_path": html_file_path,
        }

    def _build_coverage(
        self,
        snapshot: dict[str, Any],
        domains: list[dict[str, Any]],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = snapshot.get("metrics") or {}
        report_metrics = report.get("metrics") or {}
        total_sources = 0
        total_articles = 0
        total_topics = int(metrics.get("total_topics") or 0)
        for domain in domains:
            total_sources += int(domain.get("source_count") or 0)
            total_articles += int(domain.get("article_count") or 0)
            total_topics += int(domain.get("topic_count") or 0)

        if metrics.get("total_topics"):
            total_topics = int(metrics.get("total_topics") or 0)

        total_articles = max(total_articles, int(report_metrics.get("total_articles") or 0))
        total_sources = max(total_sources, int(report_metrics.get("total_sources") or 0))
        active_categories = max(
            sum(1 for domain in domains if domain["status"] != "empty"),
            int(report_metrics.get("active_sections") or 0),
        )

        return {
            "total_topics": total_topics,
            "total_articles": total_articles,
            "total_sources": total_sources,
            "active_categories": active_categories,
            "ready_categories": sum(1 for domain in domains if domain["status"] == "ready"),
            "report_ready": report.get("html_available", False),
        }

    def _build_evaluation(
        self,
        run_record: dict[str, Any],
        stage_flow: list[dict[str, Any]],
        coverage: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        total_stages = max(len(stage_flow), 1)
        finished_stages = sum(
            1 for item in stage_flow if item["status"] in {"success", "failed", "partial"}
        )
        successful_stages = sum(1 for item in stage_flow if item["status"] == "success")
        stage_ratio = successful_stages / total_stages
        category_ratio = coverage["active_categories"] / max(len(NEWS_DOMAINS), 1)
        article_target = max(len(NEWS_DOMAINS) * self.config.max_news_per_category, 1)
        article_ratio = min(coverage["total_articles"] / article_target, 1.0)
        source_target = max(coverage["total_articles"] * 2, 1)
        source_ratio = min(coverage["total_sources"] / source_target, 1.0) if coverage["total_articles"] else 0.0
        report_ratio = 1.0 if report.get("html_available") else 0.0

        status = run_record.get("status")
        status_bonus = 10 if status == "success" else 4 if status == "running" else 0
        score = round(
            stage_ratio * 30
            + category_ratio * 20
            + article_ratio * 20
            + source_ratio * 10
            + report_ratio * 10
            + status_bonus
        )
        level, score_label = _score_to_level(score)

        strengths: list[str] = []
        if status == "success":
            strengths.append("工作流主线已经成功跑通。")
        if coverage["active_categories"] >= 4:
            strengths.append("覆盖领域较完整，已经具备日报汇总的基础。")
        if report.get("html_available"):
            strengths.append("已生成可直接给前端展示的 HTML 日报。")
        if coverage["total_sources"] >= max(coverage["total_articles"], 1):
            strengths.append("信源记录相对充足，便于做可追溯展示。")

        risks: list[str] = []
        if status != "success":
            risks.append("当前最新一次运行还没有完整成功结束。")
        if coverage["total_articles"] < max(4, len(NEWS_DOMAINS) // 2):
            risks.append("成稿数量还偏少，日报总览容易显得单薄。")
        if coverage["active_categories"] < max(3, len(NEWS_DOMAINS) // 2):
            risks.append("领域覆盖不足，容易退化成单主题新闻流。")
        if not report.get("html_available"):
            risks.append("虽然有结构化数据，但还缺少最终可展示的日报页面。")

        next_actions: list[str] = []
        if coverage["total_articles"] < article_target:
            next_actions.append("继续压全量 generate/review/report，优先把多领域成稿补齐。")
        if coverage["active_categories"] < len(NEWS_DOMAINS):
            next_actions.append("补强分类和搜索阶段的覆盖率，减少空领域。")
        if not report.get("html_available"):
            next_actions.append("确保 maker 阶段输出 HTML，并接入前端展示页。")
        if not next_actions:
            next_actions.append("继续做自动调度、人工复核和历史归档，往长期运行系统推进。")

        return {
            "score": score,
            "level": level,
            "score_label": score_label,
            "finished_stages": finished_stages,
            "total_stages": total_stages,
            "strengths": strengths[:4],
            "risks": risks[:4],
            "next_actions": next_actions[:4],
        }

    def _report_document(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        report = snapshot.get("report") or {}
        document = report.get("document") or {}
        if document.get("sections"):
            return document

        json_file_path = report.get("json_file_path")
        if json_file_path and self.store.exists(json_file_path):
            return self.store.read_json(json_file_path)
        return document

    def _report_section_lookup(self, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        document = self._report_document(snapshot)
        lookup: dict[str, dict[str, Any]] = {}
        for section in document.get("sections") or []:
            name = section.get("name")
            if name:
                lookup[name] = section
        return lookup
