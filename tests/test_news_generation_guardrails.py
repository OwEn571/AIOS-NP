import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


NEWS_GENERATION_DIR = Path(__file__).resolve().parents[1] / "agents" / "news_generation_agent"
if str(NEWS_GENERATION_DIR) not in sys.path:
    sys.path.insert(0, str(NEWS_GENERATION_DIR))

import content_agent  # type: ignore
import judge_agent  # type: ignore
import summary_agent  # type: ignore
import test_parallel_agents  # type: ignore
import title_agent  # type: ignore


class NewsGenerationGuardrailsTest(unittest.TestCase):
    def test_title_agent_returns_empty_when_llm_has_no_text(self) -> None:
        with patch.object(
            title_agent,
            "llm_chat",
            return_value={
                "response": {
                    "response_message": None,
                    "error": "provider failure",
                }
            },
        ):
            agent = title_agent.TitleAgent()
            self.assertEqual(agent.generate_title("搜索结果", "测试主题"), "")

    def test_summary_and_content_agents_do_not_emit_placeholder_templates(self) -> None:
        failed_response = {
            "response": {
                "response_message": None,
                "error": "provider failure",
            }
        }

        with patch.object(summary_agent, "llm_chat", return_value=failed_response):
            agent = summary_agent.SummaryAgent()
            self.assertEqual(agent.generate_summary("搜索结果", "测试主题"), "")

        with patch.object(content_agent, "llm_chat", return_value=failed_response):
            agent = content_agent.ContentAgent()
            self.assertEqual(agent.generate_content("搜索结果", "测试主题"), "")

    def test_parallel_generator_fails_closed_instead_of_returning_placeholder_news(self) -> None:
        generator = test_parallel_agents.ParallelNewsTest()
        generator.max_retries = 1
        generator.title_agent = Mock()
        generator.summary_agent = Mock()
        generator.content_agent = Mock()
        generator.judge_agent = Mock()

        generator.title_agent.generate_title.return_value = ""
        generator.summary_agent.generate_summary.return_value = ""
        generator.content_agent.generate_content.return_value = ""
        generator.judge_agent.judge_single_part.side_effect = [
            (False, "标题为空"),
            (False, "摘要为空"),
            (False, "正文为空"),
        ]

        result = generator.generate_news("搜索结果", "测试主题", "科技与创新")

        self.assertEqual(result["title"], "")
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["content"], "")
        self.assertIn("title:", result["error"])
        self.assertIn("summary:", result["error"])
        self.assertIn("content:", result["error"])
        self.assertEqual(result["judgments"]["title"]["feedback"], "标题为空")
        self.assertEqual(result["judgments"]["summary"]["feedback"], "摘要为空")
        self.assertEqual(result["judgments"]["content"]["feedback"], "正文为空")
        self.assertNotIn("基于搜索结果", result["summary"])
        self.assertNotIn("根据最新信息", result["content"])
        generator.judge_agent.save_news_to_file.assert_not_called()

    def test_default_judge_ranges_are_relaxed_but_not_open_ended(self) -> None:
        agent = judge_agent.JudgeAgent()

        title_ok, _ = agent._default_single_judgment("title", "这是一条十一个字标题")
        summary_text = "这是一段更宽松窗口下仍然合格的摘要，用来验证摘要长度要求已经从过去的严格区间放宽到更适合新闻生成的范围，同时保持基本质量门槛。"
        summary_ok, _ = agent._default_single_judgment("summary", summary_text)
        content_too_short, feedback = agent._default_single_judgment("content", "太短了")

        self.assertTrue(title_ok)
        self.assertTrue(summary_ok)
        self.assertFalse(content_too_short)
        self.assertIn("260-650字", feedback)


if __name__ == "__main__":
    unittest.main()
