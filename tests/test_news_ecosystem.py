import tempfile
import unittest
from pathlib import Path

from apps.news_app.config import NewsAppConfig
from apps.news_app.ecosystem import NewsRunStore, NewsSnapshotBuilder
from runtime_support.artifacts import LocalArtifactStore


class NewsEcosystemTest(unittest.TestCase):
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
            max_news_per_category=3,
            web_search_max_results=5,
            sort_categories=(),
            generation_retry_limit=3,
            raw={},
        )

    def test_run_store_persists_runs_and_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalArtifactStore(root=root)
            run_store = NewsRunStore(
                store=store,
                runs_dir=root / "ecosystem" / "runs",
                snapshots_dir=root / "ecosystem" / "snapshots",
                max_run_history=5,
            )
            record = run_store.create_run("serial", "manual", ["hot_api"])
            snapshot_path = run_store.save_snapshot(record["id"], {"run_id": record["id"], "status": "success"})

            self.assertTrue(run_store.get_run(record["id"]))
            self.assertEqual(run_store.latest_snapshot()["run_id"], record["id"])
            self.assertTrue(Path(snapshot_path).exists())

    def test_snapshot_builder_collects_topics_articles_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalArtifactStore(root=root)
            config = self._make_config(root)
            config.intermediate_dir.mkdir(parents=True, exist_ok=True)
            config.output_dir.mkdir(parents=True, exist_ok=True)

            store.write_text(
                config.intermediate_dir / "科技与创新_api.txt",
                "- AI 代理系统\n- 今日科技热点\n",
            )
            store.write_text(
                config.intermediate_dir / "科技与创新_0_reviewed.txt",
                "标题: AI 代理系统\n\n摘要: 一条摘要\n\n内容: 一段内容",
            )
            store.write_json(
                config.intermediate_dir / "科技与创新_0_sources.json",
                {"sources": [{"title": "来源A", "relevance_score": 92}]},
            )
            store.write_text(
                config.output_dir / "新闻报_20260406_120000.txt",
                "今日新闻报正文",
            )

            builder = NewsSnapshotBuilder(config=config, store=store)
            snapshot = builder.build(
                {
                    "id": "run-1",
                    "status": "success",
                    "message": "ok",
                    "events": [],
                    "stage_summaries": {},
                    "result": {
                        "stage_results": {
                            "report": {
                                "report_file": str(config.output_dir / "新闻报_20260406_120000.txt")
                            }
                        }
                    },
                }
            )

            self.assertEqual(snapshot["run_id"], "run-1")
            self.assertEqual(snapshot["metrics"]["total_topics"], 2)
            self.assertEqual(snapshot["metrics"]["total_articles"], 1)
            self.assertEqual(snapshot["categories"][3]["name"], "科技与创新")
            self.assertEqual(snapshot["categories"][3]["articles"][0]["title"], "AI 代理系统")
            self.assertEqual(snapshot["report"]["content"], "今日新闻报正文")

    def test_snapshot_builder_falls_back_to_report_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalArtifactStore(root=root)
            config = self._make_config(root)
            config.intermediate_dir.mkdir(parents=True, exist_ok=True)
            config.output_dir.mkdir(parents=True, exist_ok=True)

            report_json_path = config.output_dir / "新闻报_20260406_121000.json"
            store.write_json(
                report_json_path,
                {
                    "report_title": "今日新闻现场",
                    "metrics": {"total_articles": 1, "active_sections": 1},
                    "sections": [
                        {
                            "name": "科技与创新",
                            "articles": [
                                {
                                    "title": "国产模型进入应用爆发期",
                                    "summary": "一段摘要",
                                    "content": "一段正文",
                                    "sources": [{"title": "来源A", "relevance_score": 92}],
                                }
                            ],
                        }
                    ],
                },
            )

            builder = NewsSnapshotBuilder(config=config, store=store)
            snapshot = builder.build(
                {
                    "id": "run-2",
                    "status": "success",
                    "message": "ok",
                    "events": [],
                    "stage_summaries": {},
                    "result": {
                        "stage_results": {
                            "report": {
                                "report_json_file": str(report_json_path),
                            }
                        }
                    },
                }
            )

            self.assertEqual(snapshot["metrics"]["total_articles"], 1)
            self.assertEqual(snapshot["metrics"]["active_categories"], 1)
            self.assertEqual(snapshot["categories"][3]["name"], "科技与创新")
            self.assertEqual(snapshot["categories"][3]["article_count"], 1)
            self.assertEqual(snapshot["categories"][3]["articles"][0]["title"], "国产模型进入应用爆发期")


if __name__ == "__main__":
    unittest.main()
