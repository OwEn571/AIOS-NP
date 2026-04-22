from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


class NewsMetricsBuilder:
    def build(
        self,
        run_record: dict[str, Any],
        state: dict[str, Any],
        snapshot: dict[str, Any] | None = None,
        previous_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        snapshot = snapshot or {}
        funnel = self._build_funnel(state)
        stage_benchmarks = self._build_stage_benchmarks(state)
        quality = self._build_quality(snapshot)
        domain_breakdown = self._build_domain_breakdown(snapshot)
        comparison = self._build_comparison(state, previous_metrics)

        return {
            "version": "1.0",
            "run_id": run_record.get("id"),
            "generated_at": now_iso(),
            "overview": {
                "status": run_record.get("status"),
                "mode": run_record.get("mode"),
                "source": run_record.get("source"),
                "duration_seconds": (state.get("run") or {}).get("duration_seconds"),
                "score": (state.get("evaluation") or {}).get("score"),
                "score_label": (state.get("evaluation") or {}).get("score_label"),
            },
            "funnel": funnel,
            "stage_benchmarks": stage_benchmarks,
            "quality": quality,
            "domain_breakdown": domain_breakdown,
            "comparison": comparison,
        }

    def _build_funnel(self, state: dict[str, Any]) -> dict[str, Any]:
        stage_lookup = {item.get("stage"): item for item in state.get("stage_flow") or []}
        topics = int((state.get("coverage") or {}).get("total_topics") or 0)
        search_outputs = int((stage_lookup.get("search") or {}).get("output_count") or 0)
        if search_outputs <= 0:
            search_outputs = self._artifact_count(state, "search_results")
        generated = self._artifact_count(state, "generated_news")
        reviewed = self._artifact_count(state, "reviewed_news")
        report_articles = int((state.get("coverage") or {}).get("total_articles") or 0)
        if report_articles <= 0:
            report_articles = int(((state.get("report") or {}).get("metrics") or {}).get("total_articles") or 0)

        def pct(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            return round((numerator / denominator) * 100, 2)

        return {
            "topics": topics,
            "search_outputs": search_outputs,
            "generated_articles": generated,
            "reviewed_articles": reviewed,
            "report_articles": report_articles,
            "topic_to_search_rate": pct(search_outputs, topics),
            "search_to_generate_rate": pct(generated, search_outputs),
            "generate_to_review_rate": pct(reviewed, generated),
            "topic_to_report_rate": pct(report_articles, topics),
        }

    def _build_stage_benchmarks(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        benchmarks: list[dict[str, Any]] = []
        for item in state.get("stage_flow") or []:
            duration = item.get("duration") or 0
            outputs = int(item.get("output_count") or 0)
            throughput_per_minute = 0.0
            if duration and duration > 0 and outputs > 0:
                throughput_per_minute = round(outputs / (duration / 60), 2)

            benchmarks.append(
                {
                    "stage": item.get("stage"),
                    "label": item.get("label"),
                    "status": item.get("status"),
                    "duration": duration,
                    "output_count": outputs,
                    "throughput_per_minute": throughput_per_minute,
                }
            )
        return benchmarks

    def _build_quality(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        articles = []
        for category in self._categories_with_articles(snapshot):
            articles.extend(category.get("articles") or [])

        reviewed_articles = [article for article in articles if str(article.get("file_path", "")).endswith("_reviewed.txt")]
        title_lengths = [len((article.get("title") or "").strip()) for article in articles]
        summary_lengths = [len((article.get("summary") or "").strip()) for article in articles]
        content_lengths = [len((article.get("content") or "").strip()) for article in articles]
        source_counts = [len(article.get("sources") or []) for article in articles]
        editorial_gates = [
            article.get("editorial_gate")
            for article in articles
            if isinstance(article.get("editorial_gate"), dict)
        ]
        memory_hint_counts = [int(gate.get("memory_hint_count") or 0) for gate in editorial_gates]
        memory_score_deltas = [int(gate.get("memory_score_delta") or 0) for gate in editorial_gates]

        def avg(values: list[int]) -> float:
            if not values:
                return 0.0
            return round(sum(values) / len(values), 2)

        def compliance(values: list[int], lower: int, upper: int) -> float:
            if not values:
                return 0.0
            passed = sum(1 for value in values if lower <= value <= upper)
            return round((passed / len(values)) * 100, 2)

        return {
            "article_count": len(articles),
            "reviewed_article_count": len(reviewed_articles),
            "review_completion_rate": round((len(reviewed_articles) / len(articles)) * 100, 2)
            if articles
            else 0.0,
            "avg_title_length": avg(title_lengths),
            "avg_summary_length": avg(summary_lengths),
            "avg_content_length": avg(content_lengths),
            "avg_sources_per_article": avg(source_counts),
            "title_length_pass_rate": compliance(title_lengths, 12, 24),
            "summary_length_pass_rate": compliance(summary_lengths, 70, 160),
            "content_length_pass_rate": compliance(content_lengths, 260, 650),
            "multi_source_article_rate": round(
                (sum(1 for value in source_counts if value >= 2) / len(source_counts)) * 100,
                2,
            ) if source_counts else 0.0,
            "memory_assisted_article_count": sum(1 for value in memory_hint_counts if value > 0),
            "memory_assisted_article_rate": round(
                (sum(1 for value in memory_hint_counts if value > 0) / len(articles)) * 100,
                2,
            ) if articles else 0.0,
            "avg_memory_hint_count": avg(memory_hint_counts),
            "memory_penalized_article_count": sum(1 for value in memory_score_deltas if value < 0),
            "memory_boosted_article_count": sum(1 for value in memory_score_deltas if value > 0),
        }

    def _build_domain_breakdown(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        breakdown: list[dict[str, Any]] = []
        for category in self._categories_with_articles(snapshot):
            articles = category.get("articles") or []
            source_counts = [len(article.get("sources") or []) for article in articles]
            content_lengths = [len((article.get("content") or "").strip()) for article in articles]
            reviewed_count = sum(
                1 for article in articles if str(article.get("file_path", "")).endswith("_reviewed.txt")
            )
            breakdown.append(
                {
                    "name": category.get("name"),
                    "topic_count": len(category.get("topics") or []),
                    "article_count": len(articles),
                    "reviewed_count": reviewed_count,
                    "source_count": sum(source_counts),
                    "avg_sources_per_article": round(sum(source_counts) / len(source_counts), 2)
                    if source_counts
                    else 0.0,
                    "avg_content_length": round(sum(content_lengths) / len(content_lengths), 2)
                    if content_lengths
                    else 0.0,
                }
            )
        return breakdown

    def _build_comparison(
        self,
        state: dict[str, Any],
        previous_metrics: dict[str, Any] | None,
    ) -> dict[str, Any]:
        current_score = int((state.get("evaluation") or {}).get("score") or 0)
        current_articles = int((state.get("coverage") or {}).get("total_articles") or 0)
        current_sources = int((state.get("coverage") or {}).get("total_sources") or 0)
        if current_articles <= 0:
            current_articles = int(((state.get("report") or {}).get("metrics") or {}).get("total_articles") or 0)
        if current_sources <= 0:
            current_sources = int(((state.get("report") or {}).get("metrics") or {}).get("total_sources") or 0)

        if not previous_metrics:
            return {
                "has_baseline": False,
                "score_delta": None,
                "article_delta": None,
                "source_delta": None,
            }

        previous_overview = previous_metrics.get("overview") or {}
        previous_quality = previous_metrics.get("quality") or {}
        return {
            "has_baseline": True,
            "baseline_run_id": previous_metrics.get("run_id"),
            "score_delta": current_score - int(previous_overview.get("score") or 0),
            "article_delta": current_articles - int(previous_quality.get("article_count") or 0),
            "source_delta": current_sources - int(
                sum(item.get("source_count", 0) for item in previous_metrics.get("domain_breakdown") or [])
            ),
        }

    def _artifact_count(self, state: dict[str, Any], key: str) -> int:
        for item in (state.get("artifacts") or {}).get("intermediate") or []:
            if item.get("key") == key:
                return int(item.get("count") or 0)
        return 0

    def _categories_with_articles(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        categories = snapshot.get("categories") or []
        report_lookup = self._report_category_lookup(snapshot)
        merged: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for category in categories:
            name = category.get("name")
            merged_articles = category.get("articles") or []
            if not merged_articles and name:
                merged_articles = (report_lookup.get(name) or {}).get("articles") or []
            merged.append({**category, "articles": merged_articles})
            if name:
                seen_names.add(name)

        for name, report_category in report_lookup.items():
            if name not in seen_names:
                merged.append(
                    {
                        "name": name,
                        "topics": [],
                        "articles": report_category.get("articles") or [],
                    }
                )

        return merged

    def _report_category_lookup(self, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        report = snapshot.get("report") or {}
        document = report.get("document") or {}
        if not document.get("sections"):
            json_file_path = report.get("json_file_path")
            if json_file_path:
                try:
                    with open(json_file_path, "r", encoding="utf-8") as file:
                        document = json.load(file)
                except OSError:
                    document = report.get("document") or {}

        lookup: dict[str, dict[str, Any]] = {}
        for section in document.get("sections") or []:
            name = section.get("name")
            if name:
                lookup[name] = section
        return lookup
