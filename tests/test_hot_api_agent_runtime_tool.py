import unittest
from unittest.mock import patch

from agents.hot_api_agent.agent import HotApiAgent


class _FallbackTool:
    def build_payload(self, **kwargs):
        return {
            "status": "success",
            "platform_count": 1,
            "requested_platform_count": 1,
            "requested_platforms": [kwargs.get("platform", "all")],
            "total_topics": 1,
            "platforms": [
                {
                    "platform": kwargs.get("platform", "wb"),
                    "platform_name": "微博",
                    "status": "success",
                    "board_title": "微博热搜",
                    "topics": ["fallback"],
                    "topic_count": 1,
                    "message": "ok",
                }
            ],
        }


class HotApiAgentRuntimeToolTest(unittest.TestCase):
    def test_prefers_runtime_tool_payload_when_available(self) -> None:
        agent = HotApiAgent(tool=_FallbackTool())  # type: ignore[arg-type]
        runtime_payload = {
            "status": "success",
            "platform_count": 2,
            "requested_platform_count": 2,
            "requested_platforms": ["wb", "zh"],
            "total_topics": 3,
            "platforms": [
                {
                    "platform": "wb",
                    "platform_name": "微博",
                    "status": "success",
                    "board_title": "微博热搜",
                    "topics": ["a", "b"],
                    "topic_count": 2,
                    "message": "ok",
                },
                {
                    "platform": "zh",
                    "platform_name": "知乎",
                    "status": "success",
                    "board_title": "知乎热榜",
                    "topics": ["c"],
                    "topic_count": 1,
                    "message": "ok",
                },
            ],
        }

        with patch(
            "agents.hot_api_agent.agent.call_tool",
            return_value={"response": {"response_message": runtime_payload, "finished": True}},
        ) as mocked_call_tool:
            payload = agent.get_all_platforms_hot("fake-key", max_items=5, platforms=("wb", "zh"))

        self.assertEqual(payload, runtime_payload)
        mocked_call_tool.assert_called_once()

    def test_falls_back_to_direct_tool_when_runtime_tool_fails(self) -> None:
        agent = HotApiAgent(tool=_FallbackTool())  # type: ignore[arg-type]

        with patch("agents.hot_api_agent.agent.call_tool", side_effect=RuntimeError("kernel down")):
            payload = agent.get_specific_platform_hot("fake-key", platform="wb", max_items=5)

        self.assertEqual(payload["platform_count"], 1)
        self.assertEqual(payload["platforms"][0]["topics"], ["fallback"])


if __name__ == "__main__":
    unittest.main()
