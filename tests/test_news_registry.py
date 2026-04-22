import unittest

from apps.news_app.news_registry import (
    NEWS_DOMAINS,
    news_category_definitions,
    news_category_file_map,
    news_category_names,
)


class NewsRegistryTest(unittest.TestCase):
    def test_domain_registry_has_expected_shape(self) -> None:
        self.assertEqual(len(NEWS_DOMAINS), 6)
        self.assertEqual(len(news_category_names()), 6)
        self.assertEqual(len(news_category_file_map()), 6)

    def test_category_files_match_domain_names(self) -> None:
        file_map = news_category_file_map()
        for domain in NEWS_DOMAINS:
            self.assertIn(domain.name, file_map)
            self.assertTrue(file_map[domain.name].endswith("_api.txt"))

    def test_category_definitions_include_all_domains(self) -> None:
        definitions = news_category_definitions()
        for domain in NEWS_DOMAINS:
            self.assertIn(domain.name, definitions)
            self.assertIn(domain.description, definitions)


if __name__ == "__main__":
    unittest.main()
