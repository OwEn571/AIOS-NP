import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from runtime_support.memory import WorkflowMemoryRecorder


class WorkflowMemoryRecorderTest(unittest.TestCase):
    def test_record_editorial_decision_uses_cerebrum_memory_api(self) -> None:
        recorder = WorkflowMemoryRecorder(
            agent_name="news_workflow_memory",
            base_url="http://127.0.0.1:8001",
            enabled=True,
            timeout_seconds=8.0,
        )

        captured = {}

        def fake_create_memory(agent_name, content, metadata=None, base_url=None, timeout=None):
            captured["agent_name"] = agent_name
            captured["content"] = content
            captured["metadata"] = metadata
            captured["base_url"] = base_url
            captured["timeout"] = timeout
            return {"response": {"success": True, "memory_id": "mem-123"}}

        with patch("cerebrum.memory.apis.create_memory", side_effect=fake_create_memory):
            ok = recorder.record_editorial_decision(
                decision_kind="generation_gate",
                category="科技与创新",
                topic="国产模型进入应用爆发期",
                accepted=False,
                score=28,
                reasons=["搜索结果主要是低信号来源。"],
                metadata={"artifact_path": "/tmp/demo_gate.json"},
            )

        self.assertTrue(ok)
        self.assertEqual(recorder.write_count, 1)
        self.assertEqual(recorder.last_memory_id, "mem-123")
        self.assertEqual(captured["agent_name"], "news_workflow_memory")
        self.assertEqual(captured["base_url"], "http://127.0.0.1:8001")
        self.assertEqual(captured["timeout"], 8.0)
        self.assertIn('"decision_kind": "generation_gate"', captured["content"])
        self.assertIn("editorial_decision", captured["metadata"]["tags"])
        self.assertIn("generation_gate", captured["metadata"]["tags"])

    def test_search_editorial_decisions_filters_by_category_and_kind(self) -> None:
        recorder = WorkflowMemoryRecorder(
            agent_name="news_workflow_memory",
            base_url="http://127.0.0.1:8001",
            enabled=True,
            timeout_seconds=8.0,
        )

        fake_results = {
            "response": {
                "success": True,
                "search_results": [
                    {
                        "memory_id": "mem-a",
                        "content": '{"decision_kind":"generation_gate","accepted":false}',
                        "category": "科技与创新",
                        "tags": ["workflow", "editorial_decision", "generation_gate", "rejected"],
                        "score": 0.91,
                    },
                    {
                        "memory_id": "mem-b",
                        "content": '{"decision_kind":"publishability_gate","accepted":true}',
                        "category": "科技与创新",
                        "tags": ["workflow", "editorial_decision", "publishability_gate", "accepted"],
                        "score": 0.74,
                    },
                ],
            }
        }

        with patch("cerebrum.memory.apis.search_memories", return_value=fake_results):
            matches = recorder.search_editorial_decisions(
                "国产模型",
                category="科技与创新",
                decision_kind="generation_gate",
                k=3,
            )

        self.assertEqual(recorder.search_count, 1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["memory_id"], "mem-a")
        self.assertEqual(matches[0]["body"]["decision_kind"], "generation_gate")

    def test_search_editorial_decisions_filters_expired_memories_by_ttl(self) -> None:
        recorder = WorkflowMemoryRecorder(
            agent_name="news_workflow_memory",
            base_url="http://127.0.0.1:8001",
            enabled=True,
            timeout_seconds=8.0,
            ttl_seconds=3600,
        )

        now = datetime.now()
        old_timestamp = (now - timedelta(hours=3)).strftime("%Y%m%d%H%M")
        fresh_timestamp = (now - timedelta(minutes=20)).strftime("%Y%m%d%H%M")

        fake_results = {
            "response": {
                "success": True,
                "search_results": [
                    {
                        "memory_id": "mem-old",
                        "content": '{"decision_kind":"generation_gate","accepted":false}',
                        "category": "科技与创新",
                        "tags": ["workflow", "editorial_decision", "generation_gate", "rejected"],
                        "timestamp": old_timestamp,
                        "score": 0.92,
                    },
                    {
                        "memory_id": "mem-fresh",
                        "content": '{"decision_kind":"generation_gate","accepted":true}',
                        "category": "科技与创新",
                        "tags": ["workflow", "editorial_decision", "generation_gate", "accepted"],
                        "timestamp": fresh_timestamp,
                        "score": 0.88,
                    },
                ],
            }
        }

        deleted_ids: list[str] = []

        def fake_delete_memory(agent_name, memory_id, base_url=None, timeout=None):
            deleted_ids.append(memory_id)
            return {"response": {"success": True}}

        with patch("cerebrum.memory.apis.search_memories", return_value=fake_results):
            with patch("cerebrum.memory.apis.delete_memory", side_effect=fake_delete_memory):
                matches = recorder.search_editorial_decisions(
                    "国产模型",
                    category="科技与创新",
                    decision_kind="generation_gate",
                    k=3,
                )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["memory_id"], "mem-fresh")
        self.assertEqual(recorder.expired_filter_count, 1)
        self.assertEqual(recorder.expired_prune_count, 1)
        self.assertEqual(deleted_ids, ["mem-old"])


if __name__ == "__main__":
    unittest.main()
