import unittest

from apps.news_app.editorial import (
    evaluate_generation_input,
    evaluate_publishability,
    filter_display_sources,
    route_story_category,
)


class EditorialGateTest(unittest.TestCase):
    def test_generation_gate_rejects_idiom_dictionary_material(self) -> None:
        search_data = """
【结果 1】
标题: 前倨后恭的意思_前倨后恭是什么意思_前倨后恭成语 - 开心工具箱
链接: https://kxyfr.com/chengyu/17644.html
📄 清理后的核心内容:
“前倨后恭”是一个成语，出自《战国策》。

【结果 2】
标题: 前倨后恭造句 - 造句网
链接: https://zaojv.com/7013859.html
📄 清理后的核心内容:
知道我当了主任，他前倨后恭的态度令人憎恶。
"""
        decision = evaluate_generation_input("争议事件", "嘲讽同胞秒打脸,润人前倨后恭", search_data)
        self.assertFalse(decision.accepted)
        self.assertGreaterEqual(len(decision.reasons), 1)

    def test_generation_gate_rejects_empty_search(self) -> None:
        decision = evaluate_generation_input("商业与经济", "市场震荡加剧资金流向成谜", "")
        self.assertFalse(decision.accepted)
        self.assertIn("搜索结果为空", decision.reasons[0])

    def test_publishability_rejects_low_confidence_sources(self) -> None:
        decision = evaluate_publishability(
            category="民生与健康",
            topic="伊朗：美以空袭伊朗谢里夫理工大学",
            title="战火撕裂校园",
            sources=[
                {"title": "来源A", "link": "https://www.xinhuanet.com/example", "relevance_score": 5},
                {"title": "来源B", "link": "https://www.dw.com/example", "relevance_score": 4},
                {"title": "来源C", "link": "https://www.stcn.com/example", "relevance_score": 3},
            ],
        )
        self.assertFalse(decision.accepted)
        self.assertTrue(any("匹配度过低" in reason for reason in decision.reasons))

    def test_generation_gate_uses_memory_feedback_for_similar_rejected_topics(self) -> None:
        search_data = """
【结果 1】
标题: 国产模型进入应用爆发期 - 新华网
链接: https://www.xinhuanet.com/tech/example
📄 清理后的核心内容:
国产模型进入应用落地期，行业开始关注真实使用质量与商业化节奏。
"""
        decision = evaluate_generation_input(
            "科技与创新",
            "国产模型进入应用爆发期",
            search_data,
            memory_hints=[
                {
                    "body": {
                        "decision_kind": "generation_gate",
                        "topic": "国产模型进入应用爆发期",
                        "accepted": False,
                        "score": 28,
                    }
                }
            ],
        )

        self.assertEqual(decision.memory_hint_count, 1)
        self.assertLess(decision.memory_score_delta, 0)
        self.assertTrue(any("AIOS memory" in reason for reason in decision.reasons))

    def test_publishability_uses_memory_feedback_for_similar_topics(self) -> None:
        decision = evaluate_publishability(
            category="科技与创新",
            topic="微信小程序停运引发开发者迁移",
            title="微信小程序停运冲击开发者生态",
            sources=[
                {"title": "来源A", "link": "https://news.qq.com/example", "relevance_score": 95},
                {"title": "来源B", "link": "https://www.thepaper.cn/example", "relevance_score": 88},
            ],
            memory_hints=[
                {
                    "body": {
                        "decision_kind": "publishability_gate",
                        "topic": "微信小程序停运引发开发者迁移",
                        "accepted": False,
                        "score": 35,
                    }
                }
            ],
        )

        self.assertEqual(decision.memory_hint_count, 1)
        self.assertLess(decision.memory_score_delta, 0)

    def test_filter_display_sources_removes_low_score_and_placeholder_reason(self) -> None:
        filtered = filter_display_sources(
            [
                {
                    "title": "高相关来源",
                    "link": "https://news.qq.com/example",
                    "relevance_score": 92,
                    "relevance_reason": "由搜索结果文本自动提取，供日报展示使用。",
                },
                {
                    "title": "低相关来源",
                    "link": "https://example.com/low",
                    "relevance_score": 10,
                    "relevance_reason": "与主题无关",
                },
            ]
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "高相关来源")
        self.assertNotIn("由搜索结果文本自动提取", filtered[0]["relevance_reason"])

    def test_route_story_category_moves_sports_story_out_of_controversy(self) -> None:
        category = route_story_category(
            "争议事件",
            "赵心童夺得斯诺克巡回锦标赛冠军",
            "赵心童加冕巡回锦标赛 单赛季三冠创历史",
        )
        self.assertEqual(category, "娱乐与文化")


if __name__ == "__main__":
    unittest.main()
