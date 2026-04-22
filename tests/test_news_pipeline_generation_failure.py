from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.news_app.pipeline import NewsWorkflowApp
from runtime_support.artifacts import LocalArtifactStore


class NewsPipelineGenerationFailureTest(unittest.TestCase):
    def test_persist_generation_failure_writes_debug_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            app = NewsWorkflowApp.__new__(NewsWorkflowApp)
            app.store = LocalArtifactStore(root=Path(tmp))

            search_path = Path(tmp) / "科技与创新_0_search.txt"
            search_path.write_text("demo", encoding="utf-8")

            app._persist_generation_failure(
                search_path=search_path,
                category="科技与创新",
                topic="测试主题",
                attempted_count=2,
                error_message="summary: 摘要长度不符合要求",
                generation_result={
                    "title": "测试标题",
                    "summary": "",
                    "content": "测试正文",
                    "judgments": {
                        "title": {"pass": True, "feedback": "", "retry_count": 0},
                        "summary": {"pass": False, "feedback": "摘要长度不符合要求", "retry_count": 2},
                        "content": {"pass": True, "feedback": "", "retry_count": 0},
                    },
                },
            )

            failure_path = Path(tmp) / "科技与创新_0_generation_failure.json"
            self.assertTrue(failure_path.exists())

            payload = app.store.read_json(failure_path)
            self.assertEqual(payload["topic"], "测试主题")
            self.assertEqual(payload["attempted_count"], 2)
            self.assertEqual(payload["judgments"]["summary"]["feedback"], "摘要长度不符合要求")
            self.assertEqual(payload["partial_outputs"]["title"], "测试标题")


if __name__ == "__main__":
    unittest.main()
