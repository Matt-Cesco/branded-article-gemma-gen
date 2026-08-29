import unittest

from research.topic_extraction import (
    build_topic_combinations,
    extract_accessibility_topics,
    extract_destinations,
    extract_travel_topics,
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


if __name__ == "__main__":
    unittest.main()
