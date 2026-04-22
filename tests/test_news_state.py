import tempfile
import unittest
from pathlib import Path

from apps.news_app.config import NewsAppConfig
from apps.news_app.dashboard import build_dashboard_html
from apps.news_app.metrics import NewsMetricsBuilder
from apps.news_app.state import NewsWorkflowStateBuilder
from runtime_support.artifacts import LocalArtifactStore


class NewsWorkflowStateTest(unittest.TestCase):
    def _make_config(self, root: Path) -> NewsAppConfig:
        return NewsAppConfig(
            config_path=root / "config.json",
            intermediate_dir=root / "intermediate",
            output_dir=root / "output",
            workflow_stage_order=("hot_api", "sort", "search", "generate", "review", "report"),
            parallel_domain_workers=3,
            serial_domain_workers=1,
            hot_api_platform="all",
            hot_api_platforms=(),
            hot_api_max_items=10,
            max_news_per_category=2,
            web_search_max_results=5,
            sort_categories=(),
            generation_retry_limit=3,
            raw={},
        )

    def test_state_builder_builds_evaluation_and_report_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalArtifactStore(root=root)
            config = self._make_config(root)
            config.intermediate_dir.mkdir(parents=True, exist_ok=True)
            config.output_dir.mkdir(parents=True, exist_ok=True)

            store.write_text(config.intermediate_dir / "科技与创新_api.txt", "- AI OS\n- Agent Runtime\n")
            store.write_text(
                config.intermediate_dir / "科技与创新_0_reviewed.txt",
                "标题：AIOS 进入演示阶段\n\n摘要：一条摘要\n\n内容：一段正文",
            )
            store.write_json(
                config.intermediate_dir / "科技与创新_0_sources.json",
                {"sources": [{"title": "来源A", "relevance_score": 88}]},
            )
            store.write_text(config.output_dir / "新闻报_20260406_120000.html", "<html>demo</html>")

            run_record = {
                "id": "run-123",
                "status": "success",
                "mode": "serial",
                "source": "manual",
                "created_at": "2026-04-06T12:00:00+08:00",
                "started_at": "2026-04-06T12:00:01+08:00",
                "finished_at": "2026-04-06T12:05:01+08:00",
                "stages": ["hot_api", "sort", "search", "generate", "review", "report"],
                "events": [],
                "stage_summaries": {
                    "hot_api": {"label": "热榜获取", "status": "success", "duration": 1.2, "summary": "ok"},
                    "sort": {"label": "分类整理", "status": "success", "duration": 2.1, "summary": "ok"},
                    "search": {"label": "Web搜索", "status": "success", "duration": 3.5, "summary": "ok"},
                    "generate": {"label": "新闻生成", "status": "success", "duration": 6.2, "summary": "ok"},
                    "review": {"label": "新闻审阅", "status": "success", "duration": 4.4, "summary": "ok"},
                    "report": {"label": "新闻报制作", "status": "success", "duration": 0.8, "summary": "ok"},
                },
                "result": {
                    "stage_results": {
                        "report": {
                            "report_file": str(config.output_dir / "新闻报_20260406_120000.txt"),
                            "report_json_file": str(config.output_dir / "新闻报_20260406_120000.json"),
                            "report_html_file": str(config.output_dir / "新闻报_20260406_120000.html"),
                        }
                    }
                },
            }
            snapshot = {
                "run_id": "run-123",
                "generated_at": "2026-04-06T12:05:01+08:00",
                "status": "success",
                "metrics": {"total_topics": 2, "total_articles": 1},
                "report": {
                    "file_path": str(config.output_dir / "新闻报_20260406_120000.txt"),
                    "json_file_path": str(config.output_dir / "新闻报_20260406_120000.json"),
                    "html_file_path": str(config.output_dir / "新闻报_20260406_120000.html"),
                    "html": "<html>demo</html>",
                    "excerpt": "这是日报摘要。",
                    "document": {
                        "report_title": "今日新闻现场",
                        "report_subtitle": "一页看清今天的重要变化",
                        "overview": "这里是一段总览。",
                        "metrics": {"total_articles": 1, "active_sections": 1, "highlight_count": 1},
                        "highlights": [{"title": "AIOS 进入演示阶段"}],
                        "sections": [{"name": "科技与创新"}],
                    },
                },
                "categories": [
                    {"name": "社会热点与公共事务", "topics": [], "articles": []},
                    {"name": "娱乐与文化", "topics": [], "articles": []},
                    {"name": "商业与经济", "topics": [], "articles": []},
                    {
                        "name": "科技与创新",
                        "topics": ["AI OS", "Agent Runtime"],
                        "articles": [
                            {
                                "title": "AIOS 进入演示阶段",
                                "file_path": str(config.intermediate_dir / "科技与创新_0_reviewed.txt"),
                                "sources": [{"title": "来源A"}],
                            }
                        ],
                    },
                    {"name": "民生与健康", "topics": [], "articles": []},
                    {"name": "争议事件", "topics": [], "articles": []},
                ],
            }

            builder = NewsWorkflowStateBuilder(config=config, store=store)
            state = builder.build(run_record, snapshot=snapshot)
            metrics = NewsMetricsBuilder().build(run_record, state, snapshot=snapshot)

            self.assertEqual(state["run"]["id"], "run-123")
            self.assertEqual(state["coverage"]["total_articles"], 1)
            self.assertTrue(state["report"]["html_available"])
            self.assertEqual(state["domains"][3]["name"], "科技与创新")
            self.assertEqual(state["domains"][3]["titles"][0], "AIOS 进入演示阶段")
            self.assertGreater(state["evaluation"]["score"], 0)
            self.assertEqual(len(state["stage_flow"]), 6)
            self.assertEqual(metrics["funnel"]["report_articles"], 1)
            self.assertEqual(metrics["quality"]["reviewed_article_count"], 1)
            self.assertEqual(metrics["domain_breakdown"][3]["reviewed_count"], 1)

    def test_dashboard_html_renders_latest_state(self) -> None:
        html = build_dashboard_html(
            {
                "latest_state": {
                    "evaluation": {"score": 84, "score_label": "主线可演示", "strengths": ["主线跑通。"], "risks": [], "next_actions": []},
                    "coverage": {"active_categories": 4, "ready_categories": 2, "total_articles": 5, "total_sources": 11},
                    "run": {"status": "success", "source": "manual"},
                    "stage_flow": [],
                    "domains": [],
                    "report": {"title": "今日新闻现场", "subtitle": "副标题", "overview": "overview", "metrics": {}, "highlight_titles": []},
                    "artifacts": {"intermediate": [], "outputs": []},
                },
                "latest_run": {"id": "run-123", "status": "success"},
                "recent_runs": [],
            }
        )

        self.assertIn("AIOS News Ecosystem", html)
        self.assertIn("今日新闻现场", html)
        self.assertIn("/api/ecosystem/dashboard", html)

    def test_state_and_metrics_fall_back_to_report_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalArtifactStore(root=root)
            config = self._make_config(root)
            config.intermediate_dir.mkdir(parents=True, exist_ok=True)
            config.output_dir.mkdir(parents=True, exist_ok=True)

            run_record = {
                "id": "run-report-fallback",
                "status": "success",
                "mode": "serial",
                "source": "manual",
                "created_at": "2026-04-06T12:00:00+08:00",
                "started_at": "2026-04-06T12:00:01+08:00",
                "finished_at": "2026-04-06T12:10:01+08:00",
                "stages": ["hot_api", "sort", "search", "generate", "review", "report"],
                "events": [],
                "stage_summaries": {},
                "result": {
                    "stage_results": {
                        "report": {
                            "report_file": str(config.output_dir / "新闻报_20260406_121000.txt"),
                            "report_json_file": str(config.output_dir / "新闻报_20260406_121000.json"),
                            "report_html_file": str(config.output_dir / "新闻报_20260406_121000.html"),
                        }
                    }
                },
            }
            snapshot = {
                "run_id": "run-report-fallback",
                "generated_at": "2026-04-06T12:10:01+08:00",
                "status": "success",
                "metrics": {"total_topics": 4, "total_articles": 0, "active_categories": 2},
                "report": {
                    "file_path": str(config.output_dir / "新闻报_20260406_121000.txt"),
                    "json_file_path": str(config.output_dir / "新闻报_20260406_121000.json"),
                    "html_file_path": str(config.output_dir / "新闻报_20260406_121000.html"),
                    "html": "<html>demo</html>",
                    "document": {
                        "report_title": "今日新闻现场",
                        "metrics": {"total_articles": 1, "active_sections": 1, "total_sources": 2},
                        "sections": [
                            {
                                "name": "科技与创新",
                                "articles": [
                                    {
                                        "title": "国产模型进入应用爆发期",
                                        "file_path": str(config.intermediate_dir / "国产模型进入应用爆发期_0_reviewed.txt"),
                                        "content": "一段正文",
                                        "summary": "一段摘要",
                                        "sources": [
                                            {"title": "来源A", "relevance_score": 92},
                                            {"title": "来源B", "relevance_score": 85},
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                },
                "categories": [
                    {"name": "社会热点与公共事务", "topics": ["topic-a"], "articles": []},
                    {"name": "娱乐与文化", "topics": [], "articles": []},
                    {"name": "商业与经济", "topics": [], "articles": []},
                    {"name": "科技与创新", "topics": ["topic-b"], "articles": []},
                    {"name": "民生与健康", "topics": [], "articles": []},
                    {"name": "争议事件", "topics": [], "articles": []},
                ],
            }

            builder = NewsWorkflowStateBuilder(config=config, store=store)
            state = builder.build(run_record, snapshot=snapshot)
            metrics = NewsMetricsBuilder().build(run_record, state, snapshot=snapshot)

            self.assertEqual(state["coverage"]["total_articles"], 1)
            self.assertEqual(state["coverage"]["total_sources"], 2)
            self.assertEqual(state["domains"][3]["article_count"], 1)
            self.assertEqual(state["domains"][3]["titles"][0], "国产模型进入应用爆发期")
            self.assertEqual(metrics["funnel"]["report_articles"], 1)
            self.assertEqual(metrics["quality"]["article_count"], 1)
            self.assertEqual(metrics["domain_breakdown"][3]["article_count"], 1)


if __name__ == "__main__":
    unittest.main()
