"""Prepare future keyword-pattern generation without querying search engines."""

from __future__ import annotations

ACCESSIBILITY_MODIFIERS = [
    "wheelchair accessible",
    "accessible",
    "disabled holidays",
    "reduced mobility",
    "mobility scooter",
    "wheelchair friendly",
    "accessible hotel",
    "accessible holiday",
    "disabled travel",
]

TRAVEL_INTENTS = [
    "holidays",
    "hotels",
    "resorts",
    "things to do",
    "transport",
    "beaches",
    "cruises",
    "flights",
    "airport",
    "excursions",
    "travel",
]


def generate_search_patterns(
    destination: str,
    modifiers: list[str] | None = None,
    intents: list[str] | None = None,
) -> list[str]:
    modifiers = modifiers or ACCESSIBILITY_MODIFIERS
    intents = intents or TRAVEL_INTENTS
    patterns: list[str] = []
    for modifier in modifiers:
        patterns.append(f"{modifier} {destination}")
        patterns.append(f"{destination} {modifier}")
        for intent in intents:
            patterns.append(f"{modifier} {intent} {destination}")
            patterns.append(f"{destination} {modifier} {intent}")
    return sorted(set(patterns))
