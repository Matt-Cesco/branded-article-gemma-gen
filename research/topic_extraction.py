"""Rule-based topic extraction for external accessible-travel research."""

from __future__ import annotations

import re
from itertools import product
from typing import Any


TRAVEL_TOPICS = {
    "beaches": ["beach", "beaches"],
    "flights": ["flight", "flights", "flying", "airport"],
    "hotels": ["hotel", "hotels", "accommodation", "resort", "resorts"],
    "cruises": ["cruise", "cruises"],
    "transport": ["transport", "taxi", "coach", "transfer", "transfers"],
    "excursions": ["excursion", "excursions", "things to do", "attraction", "attractions"],
    "travel tips": ["tips", "guide", "guides", "advice", "checklist", "preparation"],
    "holidays": ["holiday", "holidays", "break", "breaks", "vacation", "tour", "tours"],
}


def extract_destinations(text: str, vocabulary: dict[str, Any]) -> tuple[list[str], list[str]]:
    destinations = _find_terms(text, vocabulary.get("destinations", []))
    countries = _find_terms(text, vocabulary.get("countries", []))
    return destinations, countries


def extract_accessibility_topics(text: str, vocabulary: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for values in vocabulary.values():
        terms.extend(values)
    return _find_terms(text, terms)


def extract_travel_topics(text: str) -> list[str]:
    found: list[str] = []
    text_lower = text.lower()
    for label, variants in TRAVEL_TOPICS.items():
        if any(_contains_term(text_lower, variant) for variant in variants):
            found.append(label)
    return found


def build_topic_combinations(
    destinations: list[str],
    countries: list[str],
    accessibility_topics: list[str],
    travel_topics: list[str],
) -> list[dict[str, str | None]]:
    destination_values = destinations + countries
    combos: list[dict[str, str | None]] = []

    if destination_values and accessibility_topics and travel_topics:
        for destination, accessibility_topic, travel_topic in product(
            destination_values, accessibility_topics, travel_topics
        ):
            combos.append(
                {
                    "destination": destination,
                    "accessibility_topic": accessibility_topic,
                    "travel_topic": travel_topic,
                    "topic": f"{destination} + {accessibility_topic} + {travel_topic}",
                }
            )
    elif destination_values and accessibility_topics:
        for destination, accessibility_topic in product(destination_values, accessibility_topics):
            combos.append(
                {
                    "destination": destination,
                    "accessibility_topic": accessibility_topic,
                    "travel_topic": None,
                    "topic": f"{destination} + {accessibility_topic}",
                }
            )
    elif accessibility_topics and travel_topics:
        for accessibility_topic, travel_topic in product(accessibility_topics, travel_topics):
            combos.append(
                {
                    "destination": None,
                    "accessibility_topic": accessibility_topic,
                    "travel_topic": travel_topic,
                    "topic": f"{accessibility_topic} + {travel_topic}",
                }
            )
    elif accessibility_topics:
        for accessibility_topic in accessibility_topics:
            combos.append(
                {
                    "destination": None,
                    "accessibility_topic": accessibility_topic,
                    "travel_topic": None,
                    "topic": accessibility_topic,
                }
            )
    return combos


def infer_content_type(url: str, title: str, headings: list[str]) -> str | None:
    haystack = " ".join([url, title, *headings]).lower()
    if any(word in haystack for word in ["faq", "question", "can i", "how to"]):
        return "traveller_question"
    if any(word in haystack for word in ["guide", "tips", "advice", "checklist"]):
        return "guide"
    if any(word in haystack for word in ["review", "experience", "story"]):
        return "experience_or_review"
    if any(word in haystack for word in ["destination", "things to do"]):
        return "destination_content"
    return None


def guess_search_intent(title: str, headings: list[str]) -> str | None:
    haystack = " ".join([title, *headings]).lower()
    if any(word in haystack for word in ["holiday", "hotel", "resort", "book"]):
        return "commercial_investigation"
    if any(word in haystack for word in ["how", "can i", "tips", "guide", "advice"]):
        return "informational"
    return None


def guess_conversion_relevance(
    destinations: list[str],
    accessibility_topics: list[str],
    travel_topics: list[str],
) -> str:
    if destinations and accessibility_topics and any(t in travel_topics for t in ["holidays", "hotels"]):
        return "VERY_HIGH"
    if accessibility_topics and any(t in travel_topics for t in ["flights", "transport", "holidays"]):
        return "HIGH"
    if destinations and accessibility_topics:
        return "MEDIUM"
    if accessibility_topics:
        return "LOW"
    return "UNKNOWN"


def _find_terms(text: str, terms: list[str]) -> list[str]:
    text_lower = text.lower()
    found = [term for term in terms if _contains_term(text_lower, term.lower())]
    return sorted(set(found), key=str.lower)


def _contains_term(text_lower: str, term_lower: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(term_lower).replace(r"\ ", r"[\s\-]+") + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None
