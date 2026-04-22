import unittest
from unittest.mock import patch

from agents.web_search_agent.topic_worker import process_topic


class WebSearchRuntimeToolTest(unittest.TestCase):
    def test_process_topic_prefers_runtime_tool_result(self) -> None:
        runtime_result = (
            "🔍 搜索查询: 测试\n\n"
            "📊 返回结果数量: 1\n\n"
            "📋 搜索结果:\n\n"
            "【结果 1】\n"
            "标题: 标题A\n"
            "链接: https://example.com/a\n"
            "📄 清理后的核心内容:\n"
            "这是一段足够长的中文内容，用来模拟搜索结果正文。"
        )

        with patch(
            "agents.web_search_agent.topic_worker.call_tool",
            return_value={"response": {"response_message": runtime_result, "finished": True}},
        ) as mocked_call_tool, patch(
            "agents.web_search_agent.topic_worker.WebSearch.run",
            side_effect=AssertionError("direct tool fallback should not be used"),
        ):
            result = process_topic(topic="测试", max_results=3, api_key="fake-key")

        self.assertEqual(result["status"], "success")
        self.assertIn("标题A", result["core_content"])
        mocked_call_tool.assert_called_once()

    def test_process_topic_falls_back_to_direct_tool_when_runtime_fails(self) -> None:
        direct_result = (
            "🔍 搜索查询: 测试\n\n"
            "📊 返回结果数量: 1\n\n"
            "📋 搜索结果:\n\n"
            "【结果 1】\n"
            "标题: 标题B\n"
            "链接: https://example.com/b\n"
            "📄 清理后的核心内容:\n"
            "这是一段备用的中文正文内容，用来验证 fallback 路径。"
        )

        with patch(
            "agents.web_search_agent.topic_worker.call_tool",
            side_effect=RuntimeError("kernel down"),
        ), patch(
            "agents.web_search_agent.topic_worker.WebSearch.run",
            return_value=direct_result,
        ) as mocked_direct_run:
            result = process_topic(topic="测试", max_results=3, api_key="fake-key")

        self.assertEqual(result["status"], "success")
        self.assertIn("标题B", result["core_content"])
        mocked_direct_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
