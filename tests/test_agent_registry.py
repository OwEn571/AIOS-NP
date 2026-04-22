import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.news_app.agent_registry import AgentRegistryManager, AgentRegistryStore
from runtime_support.artifacts import LocalArtifactStore


class _DummyNewsManager:
    def latest_state(self):
        return {
            "run": {"id": "run-1", "status": "success"},
            "coverage": {"total_articles": 3},
            "evaluation": {"score": 88},
            "report": {"title": "今日新闻现场", "metrics": {"total_articles": 3}},
        }

    def latest_metrics(self):
        return {"overview": {"status": "success"}, "quality": {"article_count": 3}}

    def latest_snapshot(self):
        return {
            "run_id": "run-1",
            "generated_at": "2026-04-06T18:00:00+08:00",
            "metrics": {"total_topics": 6},
            "report": {"excerpt": "最新日报摘要"},
        }


class AgentRegistryTest(unittest.TestCase):
    def _make_manager(self, root: Path) -> AgentRegistryManager:
        store = LocalArtifactStore(root=root)
        registry_store = AgentRegistryStore(
            store=store,
            agents_dir=root / "ecosystem" / "agents",
            agent_runs_dir=root / "ecosystem" / "agent_runs",
            max_run_history=20,
        )
        return AgentRegistryManager(news_manager=_DummyNewsManager(), store=registry_store)

    def test_register_and_list_prompt_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = self._make_manager(root)

            spec = manager.register_agent(
                {
                    "id": "briefing-agent",
                    "name": "Briefing Agent",
                    "description": "Summarize latest report",
                    "agent_type": "prompt",
                    "system_prompt": "You are a briefing agent.",
                    "tags": ["briefing", "demo"],
                }
            )

            self.assertEqual(spec["id"], "briefing-agent")
            self.assertEqual(manager.list_agents()[0]["id"], "briefing-agent")
            self.assertTrue((root / "ecosystem" / "agents" / "briefing-agent.json").exists())

    def test_run_prompt_agent_with_kernel_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = self._make_manager(root)
            manager.register_agent(
                {
                    "id": "ops-agent",
                    "name": "Ops Agent",
                    "agent_type": "prompt",
                    "system_prompt": "You are an operations agent.",
                    "require_kernel": True,
                }
            )

            with patch("apps.news_app.agent_registry.llm_chat") as mock_llm_chat:
                mock_llm_chat.return_value = {
                    "response": {
                        "response_class": "llm",
                        "response_message": "kernel-ok",
                        "finished": True,
                    }
                }
                result = manager.run_agent(
                    "ops-agent",
                    input_text="总结当前系统状态",
                    include_latest_state=True,
                    include_latest_metrics=True,
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["output_text"], "kernel-ok")
            self.assertEqual(mock_llm_chat.call_args.kwargs["require_kernel"], True)
            self.assertIn("latest_state", mock_llm_chat.call_args.kwargs["messages"][1]["content"])

    def test_run_python_callable_agent_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = self._make_manager(root)
            agent_file = root / "custom_agent.py"
            agent_file.write_text(
                "def run(payload):\n"
                "    return {'echo': payload['input'], 'has_context': 'latest_snapshot' in payload['context']}\n",
                encoding="utf-8",
            )

            manager.register_agent(
                {
                    "id": "callable-agent",
                    "name": "Callable Agent",
                    "agent_type": "python_callable",
                    "file_path": str(agent_file),
                    "callable_name": "run",
                }
            )

            result = manager.run_agent(
                "callable-agent",
                input_text="ping",
                include_latest_snapshot=True,
            )

            self.assertEqual(result["status"], "success")
            self.assertIn('"echo": "ping"', result["output_text"])
            self.assertIn('"has_context": true', result["output_text"])


if __name__ == "__main__":
    unittest.main()
