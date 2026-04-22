#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from cerebrum.config.config_manager import config
from cerebrum.llm.apis import llm_chat_with_json_output
from apps.news_app.editorial import build_story_dedupe_key, route_story_category
from apps.news_app.news_registry import (
    news_category_definitions,
    news_category_file_map,
    news_category_names,
)
from project_paths import INTERMEDIATE_DIR
from runtime_support.artifacts import get_artifact_store

aios_kernel_url = config.get_kernel_url()


def _strip_markdown_fences(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = cleaned.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


class SortAgent:
    CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
        "社会热点与公共事务": (
            "清明",
            "祭奠",
            "调查",
            "审查",
            "违纪",
            "违法",
            "高校",
            "政策",
            "政府",
            "央行",
            "通报",
            "地震",
            "营救",
            "公共",
            "社会",
            "先烈",
            "历史上的今天",
            "台湾",
            "普京",
        ),
        "娱乐与文化": (
            "周杰伦",
            "浪姐",
            "演唱会",
            "明星",
            "歌手",
            "影视",
            "音乐",
            "B站",
            "哔哩",
            "综艺",
            "青春",
            "世界杯",
            "王楚钦",
            "孙颖莎",
            "郭艾伦",
            "虎扑",
            "TES",
            "BLG",
            "JDG",
            "Uzi",
            "体育",
            "电竞",
        ),
        "商业与经济": (
            "财经",
            "股",
            "债",
            "订单",
            "消费",
            "市场",
            "公司",
            "企业",
            "经济",
            "金融",
            "茅台",
            "资生堂",
            "桃李面包",
            "片仔癀",
            "大飞机",
            "订单",
            "化债",
            "工业",
        ),
        "科技与创新": (
            "AI",
            "模型",
            "机器人",
            "华为",
            "小米",
            "大疆",
            "荣耀",
            "三星",
            "特斯拉",
            "NASA",
            "阿耳忒弥斯",
            "毫米波",
            "芯片",
            "手机",
            "部署",
            "Docker",
            "Python",
            "Agent",
            "鸿蒙",
            "互联网",
            "科技",
            "创新",
        ),
        "民生与健康": (
            "眼睛",
            "报警",
            "医生",
            "医院",
            "乳腺癌",
            "教育",
            "本科专业",
            "健康",
            "民生",
            "生活",
            "大学",
            "厦门大学",
            "停招",
        ),
        "争议事件": (
            "诈骗",
            "被骗",
            "遭",
            "卖贵了",
            "下头",
            "冷冻",
            "带毛",
            "闯祸",
            "排海",
            "变异",
            "低价低质",
            "废料",
            "拿唐山地震玩梗",
            "润人",
            "前倨后恭",
            "事故全责",
            "失去保修",
            "一个子儿都没有",
        ),
    }

    def __init__(self):
        self.agent_name = "sort_agent"
        self.categories = news_category_file_map()
        self.store = get_artifact_store()

    def run(self, hot_data_file_path: str) -> dict[str, Any]:
        try:
            print("🔥 开始分类整理任务...")
            print("=" * 50)

            hot_data_path = Path(hot_data_file_path)
            if not hot_data_path.exists():
                return {
                    "agent_name": self.agent_name,
                    "result": f"❌ 热榜数据文件不存在: {hot_data_file_path}",
                    "status": "failed",
                }

            hot_data = self.store.read_text(hot_data_path)
            topics = self._extract_topics(hot_data_path, hot_data)
            if not topics:
                return {
                    "agent_name": self.agent_name,
                    "result": "❌ 没有可分类的热点条目",
                    "status": "failed",
                }

            print(f"📊 提取到 {len(topics)} 个待分类热点")
            categorized_data = self._finalize_categories(self._categorize_topics(topics))
            saved_files = self._save_categorized_data(categorized_data)
            total_items = sum(len(items) for items in categorized_data.values())

            if not saved_files:
                return {
                    "agent_name": self.agent_name,
                    "result": "❌ 分类没有生成任何有效文件",
                    "status": "failed",
                    "summary": {"分类文件数": 0, "总热点数": 0},
                }

            return {
                "agent_name": self.agent_name,
                "result": "分类整理完成",
                "status": "success",
                "saved_files": saved_files,
                "summary": {
                    "分类文件数": len(saved_files),
                    "总热点数": total_items,
                },
            }
        except Exception as exc:
            return {
                "agent_name": self.agent_name,
                "result": f"分类整理失败: {exc}",
                "status": "failed",
            }

    def _extract_topics(self, hot_data_path: Path, hot_data: str) -> list[str]:
        json_path = hot_data_path.with_suffix(".json")
        if self.store.exists(json_path):
            try:
                payload = self.store.read_json(json_path)
                topics: list[str] = []
                for platform_payload in payload.get("platforms", []):
                    topics.extend(platform_payload.get("topics", []))
                return self._normalize_topics(topics)
            except Exception as exc:
                print(f"⚠️ 读取结构化热榜失败，回退文本解析: {exc}")

        topics: list[str] = []
        for line in hot_data.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("📊") or stripped.startswith("状态:") or stripped.startswith("【"):
                continue
            match = re.match(r"^\d+\.\s*(.+?)\s*$", stripped)
            if match:
                topics.append(match.group(1).strip())
        return self._normalize_topics(topics)

    def _normalize_topics(self, topics: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for topic in topics:
            candidate = topic.strip().lstrip("-").strip()
            candidate = re.sub(r"\s+", " ", candidate)
            if len(candidate) < 3:
                continue
            dedupe_key = re.sub(r"[\W_]+", "", candidate.lower())
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(candidate)
        return normalized

    def _categorize_topics(self, topics: list[str]) -> dict[str, list[str]]:
        llm_result = self._categorize_with_llm(topics)
        if any(llm_result.values()):
            print("✅ 使用 LLM 分类成功")
            return llm_result

        print("⚠️ LLM 分类未产出有效结果，回退到本地规则分类")
        return self._categorize_with_rules(topics)

    def _categorize_with_llm(self, topics: list[str]) -> dict[str, list[str]]:
        prompt = f"""请将以下热点标题分配到 6 个固定类别中，并返回 JSON。

热点标题：
{json.dumps(topics, ensure_ascii=False, indent=2)}

固定类别定义：
{news_category_definitions()}

要求：
1. 返回一个 JSON 对象，键必须严格是这 6 个类别名称。
2. 每个值必须是字符串数组，数组元素直接使用热点标题原文。
3. 每个热点只能出现一次。
4. 如果某个类别没有条目，返回空数组。
5. “争议事件” 只能收录真实世界中的冲突、事故、违法、调查、争议、风险事件。
6. 体育夺冠、明星去世、产品停运、温情故事、普通财经波动都不能放进“争议事件”。
5. 不要输出解释，不要输出 Markdown 代码块。
"""

        try:
            response = llm_chat_with_json_output(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            if response is None or "response" not in response:
                return {category: [] for category in self.categories}

            response_text = response["response"]["response_message"]
            cleaned = _strip_markdown_fences(str(response_text))
            parsed = json.loads(cleaned)
            return self._validate_llm_result(parsed, topics)
        except Exception as exc:
            print(f"⚠️ LLM 分类失败: {exc}")
            return {category: [] for category in self.categories}

    def _validate_llm_result(
        self,
        parsed: dict[str, Any],
        topics: list[str],
    ) -> dict[str, list[str]]:
        available = {topic: topic for topic in topics}
        categorized: dict[str, list[str]] = {category: [] for category in self.categories}
        assigned: set[str] = set()

        for category in categorized:
            raw_items = parsed.get(category, [])
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, str):
                    continue
                normalized = item.strip()
                if normalized not in available or normalized in assigned:
                    continue
                categorized[category].append(normalized)
                assigned.add(normalized)

        unassigned = [topic for topic in topics if topic not in assigned]
        if unassigned:
            fallback_result = self._categorize_with_rules(unassigned)
            for category, items in fallback_result.items():
                categorized[category].extend(items)

        return categorized

    def _categorize_with_rules(self, topics: list[str]) -> dict[str, list[str]]:
        categories = {category: [] for category in self.categories}
        for topic in topics:
            target_category = self._guess_category(topic)
            categories[target_category].append(topic)
        return categories

    def _finalize_categories(self, categorized_data: dict[str, list[str]]) -> dict[str, list[str]]:
        finalized = {category: [] for category in self.categories}
        best_by_key: dict[str, dict[str, Any]] = {}

        for original_category, items in categorized_data.items():
            for topic in items:
                routed_category = route_story_category(original_category, topic, topic)
                dedupe_key = build_story_dedupe_key(routed_category, topic, topic)
                candidate = {
                    "topic": topic,
                    "category": routed_category,
                    "score": self._topic_priority_score(topic, original_category, routed_category),
                }
                existing = best_by_key.get(dedupe_key)
                if existing is None or candidate["score"] > existing["score"]:
                    best_by_key[dedupe_key] = candidate

        for item in best_by_key.values():
            finalized[item["category"]].append(item["topic"])

        for category, items in finalized.items():
            finalized[category] = self._normalize_topics(items)

        return finalized

    def _topic_priority_score(self, topic: str, original_category: str, routed_category: str) -> int:
        lowered = topic.lower()
        score = len(topic)

        if original_category == routed_category:
            score += 2
        if original_category == "争议事件" and routed_category != "争议事件":
            score -= 2

        if routed_category == "争议事件":
            score += 6
        if routed_category == "娱乐与文化" and any(
            keyword in lowered for keyword in ("夺冠", "冠军", "锦标赛", "演员", "王楚钦", "赵心童")
        ):
            score += 5
        if any(keyword in lowered for keyword in ("创历史", "锦标赛", "量产", "停运", "去世", "病逝", "心梗")):
            score += 3
        if any(keyword in lowered for keyword in ("很开心", "一起", "回应", "热搜")):
            score -= 1

        return score

    def _guess_category(self, topic: str) -> str:
        lowered = topic.lower()
        best_category = "社会热点与公共事务"
        best_score = 0

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in lowered:
                    score += max(1, len(keyword) // 2)
            if score > best_score:
                best_category = category
                best_score = score

        return best_category

    def _save_categorized_data(self, categorized_data: dict[str, list[str]]) -> list[str]:
        saved_files: list[str] = []
        for category, items in categorized_data.items():
            valid_items = self._normalize_topics(items)
            if not valid_items:
                print(f"⚠️ {category} 分类为空，跳过保存")
                continue

            filename = INTERMEDIATE_DIR / self.categories[category]
            file_content = "".join(f"- {item}\n" for item in valid_items)
            self.store.write_text(filename, file_content)
            saved_files.append(str(filename))
            print(f"✅ 已保存: {filename} ({len(valid_items)} 条)")
        return saved_files


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="热点分类整理Agent")
    parser.add_argument("--hot_data_file", required=True, help="热榜数据文件路径")

    args = parser.parse_args()

    agent = SortAgent()
    result = agent.run(args.hot_data_file)

    print("\n=== 执行结果 ===")
    print(f"状态: {result['status']}")
    print(f"结果: {result['result']}")
    if result["status"] == "success":
        print(f"保存的文件: {result['saved_files']}")
        print(f"统计信息: {result['summary']}")
