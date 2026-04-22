from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from cerebrum.tool.base import BaseTool


class HotApiTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.api_url = "https://api.zhyunxi.com/api.php"
        self.supported_web = {
            "zh": "知乎",
            "bd": "百度",
            "wb": "微博",
            "blbl": "哔哩哔哩",
            "dy": "抖音",
            "bdtb": "百度贴吧",
            "dycj": "第一财经",
            "xlcj": "新浪财经",
            "itzj": "it之家",
            "ty": "虎扑体育",
            "lssdjt": "历史上的今天",
            "csdn": "CSDN",
            "52pj": "吾爱破解",
            "kysp": "开眼视频",
        }

    def _normalize_platforms(
        self,
        platforms: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        if not platforms:
            return tuple(self.supported_web.keys())

        normalized: list[str] = []
        for platform in platforms:
            candidate = str(platform).strip()
            if not candidate:
                continue
            if candidate == "all":
                return tuple(self.supported_web.keys())
            if candidate in self.supported_web and candidate not in normalized:
                normalized.append(candidate)

        return tuple(normalized) if normalized else tuple(self.supported_web.keys())

    def fetch_platform(self, web: str, api_key: str) -> dict[str, Any]:
        params = {
            "api": "29",
            "key": api_key,
            "web": web,
        }

        platform_name = self.supported_web.get(web, web)

        try:
            response = requests.get(self.api_url, params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                return {
                    "platform": web,
                    "platform_name": platform_name,
                    "status": "failed",
                    "board_title": None,
                    "topics": [],
                    "message": "返回格式异常",
                }

            if payload.get("code") != 0:
                return {
                    "platform": web,
                    "platform_name": platform_name,
                    "status": "failed",
                    "board_title": None,
                    "topics": [],
                    "message": payload.get("msg", "未知错误"),
                }

            all_data = payload.get("data", [])
            if not all_data:
                return {
                    "platform": web,
                    "platform_name": platform_name,
                    "status": "failed",
                    "board_title": None,
                    "topics": [],
                    "message": "无数据",
                }

            board = all_data[0]
            board_title = board.get("title") or platform_name
            hot_list = board.get("hot", [])
            topics: list[str] = []
            for item in hot_list:
                title = (
                    item.get("title")
                    or item.get("name")
                    or item.get("desc")
                    or item.get("keyword")
                    or item.get("hotword")
                    or ""
                ).strip()
                if title:
                    topics.append(title)

            if not topics:
                return {
                    "platform": web,
                    "platform_name": platform_name,
                    "status": "failed",
                    "board_title": board_title,
                    "topics": [],
                    "message": "标题为空",
                }

            return {
                "platform": web,
                "platform_name": platform_name,
                "status": "success",
                "board_title": board_title,
                "topics": topics,
                "message": f"获取成功，共 {len(topics)} 条",
            }
        except requests.exceptions.Timeout:
            message = "请求超时"
        except requests.exceptions.RequestException as exc:
            message = f"网络请求异常 - {exc}"
        except Exception as exc:
            message = str(exc)

        return {
            "platform": web,
            "platform_name": platform_name,
            "status": "failed",
            "board_title": None,
            "topics": [],
            "message": message,
        }

    def fetch_all(
        self,
        api_key: str,
        max_items: int = 10,
        platforms: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        target_platforms = self._normalize_platforms(platforms)
        platforms_by_code: dict[str, dict[str, Any]] = {}
        total_topics = 0
        success_count = 0

        max_workers = min(6, len(target_platforms))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.fetch_platform, web, api_key): web
                for web in target_platforms
            }
            for future in as_completed(futures):
                web = futures[future]
                platform_payload = future.result()
                limited_topics = platform_payload["topics"][:max_items]
                platform_payload["topics"] = limited_topics
                platform_payload["topic_count"] = len(limited_topics)
                platforms_by_code[web] = platform_payload

                if platform_payload["status"] == "success":
                    success_count += 1
                    total_topics += len(limited_topics)

        platforms = [platforms_by_code[web] for web in target_platforms if web in platforms_by_code]

        return {
            "status": "success" if success_count else "failed",
            "platform_count": success_count,
            "requested_platform_count": len(target_platforms),
            "requested_platforms": list(target_platforms),
            "total_topics": total_topics,
            "platforms": platforms,
        }

    def build_payload(
        self,
        *,
        api_key: str,
        platform: str = "all",
        platforms: list[str] | tuple[str, ...] | None = None,
        max_items: int = 10,
    ) -> dict[str, Any]:
        if platform == "all":
            return self.fetch_all(api_key=api_key, max_items=max_items, platforms=platforms)

        if platform not in self.supported_web:
            return {
                "status": "failed",
                "platform_count": 0,
                "requested_platform_count": 1,
                "requested_platforms": [platform],
                "total_topics": 0,
                "platforms": [
                    {
                        "platform": platform,
                        "platform_name": self.supported_web.get(platform, platform),
                        "status": "failed",
                        "board_title": None,
                        "topics": [],
                        "topic_count": 0,
                        "message": f"不支持的平台标识: {platform}",
                    }
                ],
            }

        platform_payload = self.fetch_platform(platform, api_key)
        platform_payload["topics"] = platform_payload["topics"][:max_items]
        platform_payload["topic_count"] = len(platform_payload["topics"])
        return {
            "status": platform_payload["status"],
            "platform_count": 1 if platform_payload["status"] == "success" else 0,
            "requested_platform_count": 1,
            "requested_platforms": [platform],
            "total_topics": platform_payload["topic_count"],
            "platforms": [platform_payload],
        }

    def _format_platform_block(self, platform_payload: dict[str, Any]) -> str:
        if platform_payload["status"] != "success":
            return (
                f"【{platform_payload['platform_name']}】\n"
                f"状态: {platform_payload['message']}"
            )

        lines = [f"【{platform_payload['board_title']}】"]
        for index, topic in enumerate(platform_payload["topics"], start=1):
            lines.append(f"{index}. {topic}")
        return "\n".join(lines)

    def run(self, params: dict[str, Any]) -> Any:
        try:
            platform = params.get("platform", "all")
            platforms = params.get("platforms")
            max_items = params.get("max_items", 10)
            debug = params.get("debug", False)
            return_payload = bool(params.get("return_payload", False))

            api_key = params.get("api_key") or os.getenv("ZH_API_KEY")
            if not api_key:
                return "错误：未提供API密钥，请通过参数传入或设置ZH_API_KEY环境变量"

            payload = self.build_payload(
                api_key=api_key,
                platform=platform,
                platforms=platforms,
                max_items=max_items,
            )
            if return_payload:
                return payload

            if platform != "all" and payload["status"] == "failed" and payload["platforms"]:
                platform_payload = payload["platforms"][0]
                if "不支持的平台标识" in str(platform_payload.get("message")):
                    return (
                        f"不支持的平台标识: {platform}\n"
                        f"支持的平台: {', '.join(self.supported_web.keys())}"
                    )

            lines = [
                f"📊 多平台热榜汇总 (成功{payload['platform_count']}个平台，共{payload['total_topics']}条)"
            ]
            for platform_payload in payload["platforms"]:
                if platform_payload["status"] == "success" or debug:
                    lines.append(self._format_platform_block(platform_payload))
            if platform != "all" and payload["platforms"]:
                return self._format_platform_block(payload["platforms"][0])
            return "\n\n".join(lines)
        except Exception as exc:
            return f"工具运行失败: {exc}"

    def get_tool_call_format(self):
        return {
            "type": "function",
            "function": {
                "name": "owen/hot_api",
                "description": "获取各大平台热榜信息的工具，支持百度、微博、知乎、B站、抖音等平台",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "api_key": {
                            "type": "string",
                            "description": "云析 API 密钥，也可通过 ZH_API_KEY 环境变量设置",
                        },
                        "platform": {
                            "type": "string",
                            "description": "平台标识，可选值：zh、bd、wb、blbl、dy、bdtb、dycj、xlcj、itzj、ty、lssdjt、csdn、52pj、kysp、all",
                            "default": "all",
                        },
                        "platforms": {
                            "type": "array",
                            "description": "当 platform=all 时可传入平台白名单，例如 [\"bd\", \"wb\", \"zh\"]",
                            "items": {"type": "string"},
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "每个平台最大返回条目数",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "是否输出失败平台的详细错误信息",
                            "default": False,
                        },
                    },
                    "required": ["api_key"],
                },
            },
        }
