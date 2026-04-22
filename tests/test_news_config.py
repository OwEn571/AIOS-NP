import json
import tempfile
import unittest
from pathlib import Path

from apps.news_app.config import load_news_app_config


class NewsConfigTest(unittest.TestCase):
    def test_hot_api_platforms_follow_explicit_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "pipeline": {
                            "intermediate_dir": "./intermediate",
                            "output_dir": "./output",
                            "max_news_per_category": 3,
                        },
                        "workflow": {"stages": ["hot_api", "sort"]},
                        "hot_api": {
                            "platform": "all",
                            "platforms": ["bd", "wb", "zh", "wb"],
                            "max_items_per_platform": 10,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            config = load_news_app_config(config_path)

            self.assertEqual(config.hot_api_platform, "all")
            self.assertEqual(config.hot_api_platforms, ("bd", "wb", "zh"))


if __name__ == "__main__":
    unittest.main()
