"""Read and filter optional crawler/research data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings


@dataclass
class ResearchSelection:
    source_pages: list[dict[str, str]]
    topic_combinations: list[dict[str, str]]
    summary: dict[str, int]
    files_consulted: list[str]
    truncated: bool
    context_character_count: int

    def as_prompt_text(self) -> str:
        if not self.source_pages and not self.topic_combinations:
            return "No relevant crawler/research rows found for this brief."
        lines = [
            "Crawler/research context. Use as topic inspiration only. Do not copy wording or treat competitor claims as verified Limitless facts.",
            "",
            "Relevant source pages:",
        ]
        for row in self.source_pages:
            lines.append(
                f"- {row.get('title') or row.get('url')} | source: {row.get('source')} | "
                f"destination: {row.get('destination') or row.get('country') or 'n/a'} | "
                f"accessibility: {row.get('accessibility_topics') or 'n/a'} | "
                f"travel topics: {row.get('travel_topics') or 'n/a'}"
            )
        lines.append("")
        lines.append("Observed topic combinations:")
        for row in self.topic_combinations:
            lines.append(
                f"- {row.get('topic')} | observed frequency: {row.get('editorial_frequency') or row.get('occurrences')} | "
                f"sources: {row.get('unique_sources')} | conversion relevance: {row.get('conversion_relevance') or 'unknown'}"
            )
        return "\n".join(lines)


class ResearchService:
    def __init__(self, repo_root: Path) -> None:
        self.data_dir = repo_root / "data"
        self.settings = get_settings()

    def available_research_summary(self) -> dict[str, int]:
        return {
            "source_pages": len(self._read_csv(self._safe_data_path("output/opportunities/source-pages.csv"))),
            "topic_combinations": len(self._read_csv(self._safe_data_path("output/opportunities/topic-combinations.csv"))),
            "destinations": len(self._read_csv(self._safe_data_path("output/opportunities/destinations.csv"))),
            "accessibility_topics": len(self._read_csv(self._safe_data_path("output/opportunities/accessibility-topics.csv"))),
        }

    def find_relevant_research(
        self,
        title: str,
        primary_keyword: str | None,
        destination: str | None,
        accessibility_topics: list[str],
        secondary_keywords: list[str] | None = None,
        reader_concerns: str | None = None,
    ) -> ResearchSelection:
        strong_terms, weak_terms = _normalise_terms(
            [title, primary_keyword, destination, *(secondary_keywords or []), *accessibility_topics, reader_concerns]
        )
        source_pages_path = self._safe_data_path("output/opportunities/source-pages.csv")
        topic_combinations_path = self._safe_data_path("output/opportunities/topic-combinations.csv")
        pages = self._read_csv(source_pages_path)
        combos = self._read_csv(topic_combinations_path)
        files_consulted = [
            str(source_pages_path.relative_to(self.data_dir)),
            str(topic_combinations_path.relative_to(self.data_dir)),
        ]

        scored_pages = sorted(
            ((self._score_row(row, strong_terms, weak_terms), row) for row in pages),
            key=lambda item: item[0],
            reverse=True,
        )
        scored_combos = sorted(
            ((self._score_row(row, strong_terms, weak_terms), row) for row in combos),
            key=lambda item: item[0],
            reverse=True,
        )
        selected_pages = [row for score, row in scored_pages if score >= 2]
        selected_combos = [row for score, row in scored_combos if score >= 2]
        selected_pages, selected_combos, truncated, context_chars = self._limit_selection(selected_pages, selected_combos)
        return ResearchSelection(
            source_pages=selected_pages,
            topic_combinations=selected_combos,
            summary={
                "source_pages_considered": len(pages),
                "topic_combinations_considered": len(combos),
                "source_pages_selected": len(selected_pages),
                "topic_combinations_selected": len(selected_combos),
                "records_selected": len(selected_pages) + len(selected_combos),
            },
            files_consulted=files_consulted,
            truncated=truncated,
            context_character_count=context_chars,
        )

    def load_topic_combinations(self) -> list[dict[str, str]]:
        return self._read_csv(self._safe_data_path("output/opportunities/topic-combinations.csv"))

    def _safe_data_path(self, relative_path: str) -> Path:
        path = (self.data_dir / relative_path).resolve()
        data_root = self.data_dir.resolve()
        if path != data_root and data_root not in path.parents:
            raise ValueError("Research path is outside the data directory.")
        return path

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def read_json_file(self, relative_path: str) -> Any:
        path = self._safe_data_path(relative_path)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _score_row(self, row: dict[str, str], strong_terms: set[str], weak_terms: set[str]) -> int:
        text = " ".join(str(value).lower() for value in row.values())
        score = sum(2 for term in strong_terms if term in text)
        score += sum(1 for term in weak_terms if term in text)
        return score

    def _limit_selection(
        self,
        pages: list[dict[str, str]],
        combos: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], bool, int]:
        max_records = self.settings.max_research_records
        max_chars = self.settings.max_research_context_chars
        selected_pages: list[dict[str, str]] = []
        selected_combos: list[dict[str, str]] = []
        context_chars = 0
        truncated = False
        combined: list[tuple[str, dict[str, str]]] = [("page", row) for row in pages] + [("combo", row) for row in combos]
        for kind, row in combined:
            row_chars = len(" ".join(str(value) for value in row.values()))
            if len(selected_pages) + len(selected_combos) >= max_records or context_chars + row_chars > max_chars:
                truncated = True
                break
            context_chars += row_chars
            if kind == "page":
                selected_pages.append(row)
            else:
                selected_combos.append(row)
        return selected_pages, selected_combos, truncated, context_chars


GENERIC_RESEARCH_TERMS = {
    "accessible",
    "accessibility",
    "travel",
    "holiday",
    "holidays",
    "disabled",
    "guide",
    "hotel",
    "hotels",
}


def _normalise_terms(values: list[str | None]) -> tuple[set[str], set[str]]:
    strong_terms: set[str] = set()
    weak_terms: set[str] = set()
    for value in values:
        if not value:
            continue
        for part in str(value).replace(",", "\n").replace(";", "\n").split("\n"):
            part = part.strip().lower()
            if not part:
                continue
            words = [word for word in part.split() if word not in GENERIC_RESEARCH_TERMS]
            if part not in GENERIC_RESEARCH_TERMS and (len(words) >= 2 or part in words):
                strong_terms.add(part)
            for word in words:
                if len(word) >= 4:
                    weak_terms.add(word)
    return strong_terms, weak_terms
