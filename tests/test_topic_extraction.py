import unittest

from research.topic_extraction import (
    build_topic_combinations,
    extract_accessibility_topics,
    extract_destinations,
    extract_travel_topics,
)
from research.topic_discovery_crawler import (
    SourceConfig,
    is_close_to_research_area,
    is_sitemap_research_candidate,
    looks_javascript_required,
)


class TopicExtractionTests(unittest.TestCase):
    def test_destination_accessibility_and_travel_topic_combination(self) -> None:
        destinations_vocab = {"countries": ["Spain"], "destinations": ["Tenerife"]}
        accessibility_vocab = {"mobility": ["wheelchair", "mobility scooter"]}

        text = "Wheelchair Accessible Beaches in Tenerife"

        destinations, countries = extract_destinations(text, destinations_vocab)
        accessibility_topics = extract_accessibility_topics(text, accessibility_vocab)
        travel_topics = extract_travel_topics(text)
        combinations = build_topic_combinations(
            destinations,
            countries,
            accessibility_topics,
            travel_topics,
        )

        self.assertEqual(destinations, ["Tenerife"])
        self.assertEqual(countries, [])
        self.assertEqual(accessibility_topics, ["wheelchair"])
        self.assertEqual(travel_topics, ["beaches"])
        self.assertEqual(
            combinations,
            [
                {
                    "destination": "Tenerife",
                    "accessibility_topic": "wheelchair",
                    "travel_topic": "beaches",
                    "topic": "Tenerife + wheelchair + beaches",
                }
            ],
        )

    def test_homepage_start_url_is_inside_research_area(self) -> None:
        self.assertTrue(
            is_close_to_research_area(
                "https://wheeltheworld.com/",
                "https://wheeltheworld.com/",
            )
        )

    def test_unquoted_app_shell_is_javascript_required(self) -> None:
        html = "<html><head><title></title></head><body><div id=app></div><script src=/js/app.js></script></body></html>"

        self.assertTrue(looks_javascript_required(html, ""))

    def test_sitemap_research_candidate_filter(self) -> None:
        start_url = "https://www.enableholidays.com/blog"

        self.assertTrue(
            is_sitemap_research_candidate(
                "https://www.enableholidays.com/flying-with-a-disability-or-reduced-mobility",
                start_url,
            )
        )
        self.assertTrue(
            is_sitemap_research_candidate(
                "https://www.enableholidays.com/accessible-city-breaks-brochure",
                start_url,
            )
        )
        self.assertFalse(
            is_sitemap_research_candidate(
                "https://www.enableholidays.com/privacy-policy",
                start_url,
            )
        )

    def test_source_config_supports_sitemap_first_strategy(self) -> None:
        source = SourceConfig(
            name="Enable Holidays",
            base_url="https://www.enableholidays.com/",
            start_url="https://www.enableholidays.com/blog",
            source_type="accessible_travel_operator",
            priority="high",
            discovery_strategy="sitemap_first",
        )

        self.assertEqual(source.discovery_strategy, "sitemap_first")


if __name__ == "__main__":
    unittest.main()
