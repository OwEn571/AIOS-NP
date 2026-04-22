import json
import tempfile
import unittest
from pathlib import Path

from agents.maker_agent.agent import MakerAgent
from runtime_support.artifacts import LocalArtifactStore


class MakerAgentTest(unittest.TestCase):
    def test_maker_agent_outputs_text_json_and_html_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            intermediate_dir = root / "intermediate"
            output_dir = root / "output"
            intermediate_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            store = LocalArtifactStore(root=root)
            store.write_text(
                intermediate_dir / "娱乐与文化_0_news.txt",
                "标题: 一场演唱会争议\n\n摘要: 一段摘要\n\n内容: 一段正文",
            )
            store.write_json(
                intermediate_dir / "娱乐与文化_0_sources.json",
                {
                    "news_title": "一场演唱会争议",
                    "sources": [
                        {
                            "title": "来源A",
                            "link": "https://example.com/a",
                            "relevance_score": 91,
                            "relevance_reason": "相关",
                            "key_info": "要点",
                        }
                    ],
                },
            )
            store.write_text(
                intermediate_dir / "娱乐与文化_0_search.txt",
                "【结果 1】\n标题: 来源A\n链接: https://example.com/a\n📄 清理后的核心内容:\n一段正文",
            )
            store.write_text(
                intermediate_dir / "娱乐与文化_0_image.txt",
                "【结果 1】\n1. https://images.example.com/story.jpg",
            )

            agent = MakerAgent()
            agent.store = store
            agent.generate_title_and_overview = lambda sections: {
                "report_title": "今日新闻现场",
                "report_subtitle": "一页看完今天的重点",
                "overview": "这里是一段日报总览。",
            }

            result = agent.run(str(intermediate_dir), str(output_dir))

            self.assertEqual(result["status"], "success")
            self.assertTrue(Path(result["report_file"]).exists())
            self.assertTrue(Path(result["report_json_file"]).exists())
            self.assertTrue(Path(result["report_html_file"]).exists())

            report_json = json.loads(Path(result["report_json_file"]).read_text(encoding="utf-8"))
            report_html = Path(result["report_html_file"]).read_text(encoding="utf-8")

            self.assertEqual(report_json["report_title"], "今日新闻现场")
            self.assertEqual(report_json["metrics"]["total_articles"], 1)
            article = report_json["sections"][0]["articles"][0]
            self.assertEqual(article["image"]["url"], "https://images.example.com/story.jpg")
            self.assertIn("一场演唱会争议", report_html)
            self.assertIn('href="https://example.com/a"', report_html)
            self.assertIn('src="https://images.example.com/story.jpg"', report_html)
            self.assertIn("AIOS-NP Daily Brief", report_html)

    def test_maker_agent_dedupes_story_and_filters_low_score_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            intermediate_dir = root / "intermediate"
            output_dir = root / "output"
            intermediate_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            store = LocalArtifactStore(root=root)

            store.write_text(intermediate_dir / "娱乐与文化_api.txt", "- 赵心童：很开心和王楚钦一起拿冠军\n")
            store.write_text(intermediate_dir / "争议事件_api.txt", "- 赵心童夺得斯诺克巡回锦标赛冠军\n")
            store.write_text(intermediate_dir / "科技与创新_api.txt", "- 微信宣布这项功能将全面停运\n")

            store.write_text(
                intermediate_dir / "赵心童：很开心和王楚钦一起拿冠军_0_reviewed.txt",
                "标题: 赵心童10-3大胜！与王楚钦同庆夺冠\n\n摘要: 一段摘要\n\n内容: 一段正文" * 20,
            )
            store.write_json(
                intermediate_dir / "赵心童：很开心和王楚钦一起拿冠军_0_sources.json",
                {
                    "topic": "赵心童：很开心和王楚钦一起拿冠军",
                    "sources": [
                        {
                            "title": "来源A",
                            "link": "https://news.qq.com/a",
                            "relevance_score": 100,
                            "relevance_reason": "相关",
                        },
                        {
                            "title": "来源B",
                            "link": "https://zhibo8.com/a",
                            "relevance_score": 98,
                            "relevance_reason": "相关",
                        },
                    ],
                },
            )

            store.write_text(
                intermediate_dir / "赵心童夺得斯诺克巡回锦标赛冠军_0_reviewed.txt",
                "标题: 赵心童加冕巡回锦标赛 单赛季三冠创历史\n\n摘要: 一段摘要\n\n内容: 一段正文" * 20,
            )
            store.write_json(
                intermediate_dir / "赵心童夺得斯诺克巡回锦标赛冠军_0_sources.json",
                {
                    "topic": "赵心童夺得斯诺克巡回锦标赛冠军",
                    "sources": [
                        {
                            "title": "来源C",
                            "link": "https://xinhuanet.com/a",
                            "relevance_score": 100,
                            "relevance_reason": "相关",
                        },
                        {
                            "title": "来源D",
                            "link": "https://news.cn/a",
                            "relevance_score": 95,
                            "relevance_reason": "相关",
                        },
                    ],
                },
            )

            store.write_text(
                intermediate_dir / "微信宣布这项功能将全面停运_0_reviewed.txt",
                "标题: 微信“微信支付有优惠”小程序停运整合计划确认\n\n摘要: 一段摘要\n\n内容: 一段正文" * 20,
            )
            store.write_json(
                intermediate_dir / "微信宣布这项功能将全面停运_0_sources.json",
                {
                    "topic": "微信宣布这项功能将全面停运",
                    "sources": [
                        {
                            "title": "高分1",
                            "link": "https://news.qq.com/wechat",
                            "relevance_score": 100,
                            "relevance_reason": "相关",
                        },
                        {
                            "title": "高分2",
                            "link": "https://news.cn/wechat",
                            "relevance_score": 85,
                            "relevance_reason": "相关",
                        },
                        {
                            "title": "低分1",
                            "link": "https://example.com/low1",
                            "relevance_score": 10,
                            "relevance_reason": "无关",
                        },
                        {
                            "title": "低分2",
                            "link": "https://example.com/low2",
                            "relevance_score": 5,
                            "relevance_reason": "无关",
                        },
                    ],
                },
            )

            agent = MakerAgent()
            agent.store = store
            agent.generate_title_and_overview = lambda sections: {
                "report_title": "今日新闻现场",
                "report_subtitle": "一页看完今天的重点",
                "overview": "这里是一段日报总览。",
            }

            result = agent.run(str(intermediate_dir), str(output_dir))
            report_json = json.loads(Path(result["report_json_file"]).read_text(encoding="utf-8"))

            all_titles = [article["title"] for section in report_json["sections"] for article in section["articles"]]
            self.assertEqual(sum("赵心童" in title for title in all_titles), 1)
            self.assertFalse(any(section["name"] == "争议事件" for section in report_json["sections"]))

            tech_section = next(section for section in report_json["sections"] if section["name"] == "科技与创新")
            tech_sources = tech_section["articles"][0]["sources"]
            self.assertEqual(len(tech_sources), 2)
            self.assertTrue(all(source["relevance_score"] >= 35 for source in tech_sources))

    def test_maker_agent_prefers_top_source_image_and_filters_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            intermediate_dir = root / "intermediate"
            output_dir = root / "output"
            intermediate_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            store = LocalArtifactStore(root=root)
            store.write_text(intermediate_dir / "娱乐与文化_api.txt", "- 一场演唱会争议\n")
            store.write_text(
                intermediate_dir / "一场演唱会争议_0_reviewed.txt",
                "标题: 一场演唱会争议\n\n摘要: 一段摘要\n\n内容: 一段正文" * 20,
            )
            store.write_json(
                intermediate_dir / "一场演唱会争议_0_sources.json",
                {
                    "topic": "一场演唱会争议",
                    "sources": [
                        {
                            "title": "来源B",
                            "link": "https://example.com/b",
                            "relevance_score": 98,
                            "relevance_reason": "相关",
                        },
                        {
                            "title": "来源A",
                            "link": "https://example.com/a",
                            "relevance_score": 80,
                            "relevance_reason": "相关",
                        },
                    ],
                },
            )
            store.write_text(
                intermediate_dir / "娱乐与文化_0_search.txt",
                (
                    "【结果 1】\n标题: 来源A\n链接: https://example.com/a\n📄 清理后的核心内容:\nA\n\n"
                    "【结果 2】\n标题: 来源B\n链接: https://example.com/b\n📄 清理后的核心内容:\nB"
                ),
            )
            store.write_text(
                intermediate_dir / "娱乐与文化_0_image.txt",
                (
                    "【结果 1】\n"
                    "1. https://cdn.example.com/logo.png\n"
                    "2. https://cdn.example.com/a-story.jpg\n\n"
                    "【结果 2】\n"
                    "1. https://cdn.example.com/app-screenshot.png\n"
                    "2. https://cdn.example.com/b-story.webp"
                ),
            )

            agent = MakerAgent()
            agent.store = store
            agent.generate_title_and_overview = lambda sections: {
                "report_title": "今日新闻现场",
                "report_subtitle": "一页看完今天的重点",
                "overview": "这里是一段日报总览。",
            }

            result = agent.run(str(intermediate_dir), str(output_dir))
            report_json = json.loads(Path(result["report_json_file"]).read_text(encoding="utf-8"))
            article = report_json["sections"][0]["articles"][0]

            self.assertEqual(article["image"]["url"], "https://cdn.example.com/b-story.webp")
            self.assertEqual(article["image"]["source_link"], "https://example.com/b")
            self.assertEqual(article["image"]["search_result_index"], 2)


if __name__ == "__main__":
    unittest.main()
