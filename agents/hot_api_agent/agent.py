from __future__ import annotations

import argparse
import json
import os
from typing import Any

from cerebrum.config.config_manager import config
from cerebrum.tool.apis import call_tool
from cerebrum.tool.core.owen.hot_api_tool.entry import HotApiTool

from project_paths import INTERMEDIATE_DIR
from runtime_support.artifacts import ArtifactStore, get_artifact_store


class HotApiAgent:
    def __init__(
        self,
        agent_name: str = "hot_api_agent",
        tool: HotApiTool | None = None,
        store: ArtifactStore | None = None,
        base_url: str | None = None,
    ):
        self.agent_name = agent_name
        self.tool = tool or HotApiTool()
        self.store = store or get_artifact_store()
        self.base_url = base_url or config.get_kernel_url()

    def _unwrap_tool_response(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            payload = response.get("response")
            if isinstance(payload, dict):
                message = payload.get("response_message")
                if isinstance(message, dict):
                    return message
                if isinstance(message, str):
                    try:
                        parsed = json.loads(message)
                    except Exception:
                        pass
                    else:
                        if isinstance(parsed, dict):
                            return parsed
        raise RuntimeError(f"invalid tool response: {response!r}")

    def _invoke_hot_api_tool(
        self,
        *,
        api_key: str,
        platform: str = "all",
        platforms: list[str] | tuple[str, ...] | None = None,
        max_items: int = 10,
    ) -> dict[str, Any]:
        response = call_tool(
            self.agent_name,
            [
                {
                    "name": "hot_api",
                    "parameters": {
                        "api_key": api_key,
                        "platform": platform,
                        "platforms": list(platforms) if platforms else None,
                        "max_items": max_items,
                        "return_payload": True,
                    },
                }
            ],
            base_url=self.base_url,
        )
        return self._unwrap_tool_response(response)

    def get_all_platforms_hot(
        self,
        api_key: str,
        max_items: int = 10,
        platforms: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        try:
            return self._invoke_hot_api_tool(
                api_key=api_key,
                platform="all",
                platforms=platforms,
                max_items=max_items,
            )
        except Exception:
            return self.tool.build_payload(
                api_key=api_key,
                platform="all",
                platforms=platforms,
                max_items=max_items,
            )

    def get_specific_platform_hot(
        self,
        api_key: str,
        platform: str,
        max_items: int = 10,
    ) -> dict[str, Any]:
        try:
            return self._invoke_hot_api_tool(
                api_key=api_key,
                platform=platform,
                max_items=max_items,
            )
        except Exception:
            return self.tool.build_payload(
                api_key=api_key,
                platform=platform,
                max_items=max_items,
            )

    def process_hot_data(self, hot_payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        print("🔧 正在整理热榜数据...")
        lines = [
            f"📊 多平台热榜汇总 (成功{hot_payload['platform_count']}个平台，共{hot_payload['total_topics']}条)"
        ]
        for platform_payload in hot_payload["platforms"]:
            lines.append("")
            if platform_payload["status"] != "success":
                lines.append(f"【{platform_payload['platform_name']}】")
                lines.append(f"状态: {platform_payload['message']}")
                continue

            lines.append(f"【{platform_payload['board_title']}】")
            for index, topic in enumerate(platform_payload["topics"], start=1):
                lines.append(f"{index}. {topic}")

        processed_text = "\n".join(lines).strip()
        print(f"📊 结构化热榜平台数: {hot_payload['platform_count']}")
        print(f"📝 热榜文本长度: {len(processed_text)} 字符")
        return processed_text, hot_payload

    def save_to_file(self, content: str, payload: dict[str, Any]) -> tuple[str, str]:
        hot_api_path = INTERMEDIATE_DIR / "hot_api.txt"
        hot_api_json_path = INTERMEDIATE_DIR / "hot_api.json"
        self.store.write_text(hot_api_path, content)
        self.store.write_json(hot_api_json_path, payload)
        print(f"✅ 文件保存成功: {hot_api_path}")
        print(f"✅ 结构化数据保存成功: {hot_api_json_path}")
        return str(hot_api_path), str(hot_api_json_path)

    def run(
        self,
        task_input: str,
        api_key: str | None = None,
        platform: str = "all",
        platforms: list[str] | tuple[str, ...] | None = None,
        max_items: int = 10,
    ) -> dict[str, Any]:
        print("🔥 开始获取多平台热榜...")
        print("=" * 50)

        if not api_key:
            api_key = os.getenv("ZH_API_KEY")

        if not api_key:
            return {
                "agent_name": self.agent_name,
                "result": "❌ 错误：未提供API密钥，请通过参数传入或设置ZH_API_KEY环境变量",
                "status": "failed",
            }

        try:
            if platform == "all":
                target_platforms = list(platforms or [])
                if target_platforms:
                    joined = "、".join(target_platforms)
                    print(f"📊 获取指定热榜平台: {joined}，每个平台最多{max_items}条...")
                else:
                    print(f"📊 获取所有平台热榜，每个平台最多{max_items}条...")
                hot_payload = self.get_all_platforms_hot(api_key, max_items, platforms=platforms)
            else:
                print(f"📱 获取{platform}平台热榜，最多{max_items}条...")
                hot_payload = self.get_specific_platform_hot(api_key, platform, max_items)

            if hot_payload["platform_count"] == 0:
                failed_messages = [
                    f"{item['platform_name']}: {item['message']}"
                    for item in hot_payload["platforms"]
                    if item["status"] != "success"
                ]
                return {
                    "agent_name": self.agent_name,
                    "result": "❌ 热榜获取失败: " + "; ".join(failed_messages),
                    "status": "failed",
                }

            processed_text, structured_payload = self.process_hot_data(hot_payload)

            print("\n💾 正在保存到文件...")
            file_path, json_path = self.save_to_file(processed_text, structured_payload)
            return {
                "agent_name": self.agent_name,
                "result": "✅ 热榜获取和保存成功！",
                "status": "success",
                "data": processed_text,
                "payload": structured_payload,
                "file_path": file_path,
                "json_file_path": json_path,
            }
        except Exception as exc:
            return {
                "agent_name": self.agent_name,
                "result": f"❌ 运行失败: {exc}",
                "status": "failed",
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="热点获取 Agent")
    parser.add_argument("--task_input", type=str, default="获取热榜")
    parser.add_argument("--api_key", type=str, default=os.getenv("ZH_API_KEY"))
    parser.add_argument("--platform", type=str, default="all")
    parser.add_argument("--max_items", type=int, default=10)
    args = parser.parse_args()

    agent = HotApiAgent()
    result = agent.run(
        task_input=args.task_input,
        api_key=args.api_key,
        platform=args.platform,
        max_items=args.max_items,
    )
    print(result)
