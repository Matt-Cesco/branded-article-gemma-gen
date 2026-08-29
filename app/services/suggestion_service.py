"""Generate article-topic suggestions from local research data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib import parse

from app.schemas.suggestion import SuggestionRequest
from app.services.gemma_service import LLMError, OllamaGemmaService
from app.services.prompt_service import PromptService
from app.services.research_service import ResearchService


@dataclass
class TopicSuggestion:
    suggested_title: str
    topic: str
    destination: str
    accessibility_topic: str
    search_intent: str
    competitor_frequency: str
    conversion_relevance: str
    why: str
    article_url: str


class SuggestionService:
    def __init__(self, repo_root: Path) -> None:
        self.research = ResearchService(repo_root)
        self.prompts = PromptService()

    def available_research_summary(self) -> dict[str, int]:
        return self.research.available_research_summary()

    async def generate_suggestions(self, request: SuggestionRequest) -> list[TopicSuggestion]:
        rows = self._filter_rows(request)
        suggestions = [self._row_to_suggestion(row) for row in rows[:20]]
        if request.use_gemma and suggestions:
            await self._try_gemma_enrichment(rows[:20])
        return suggestions

    def _filter_rows(self, request: SuggestionRequest) -> list[dict[str, str]]:
        rows = self.research.load_topic_combinations()
        filtered: list[dict[str, str]] = []
        for row in rows:
            if int(row.get("unique_sources") or 0) < request.minimum_source_frequency:
                continue
            if request.destination and request.destination.lower() not in (row.get("destination") or "").lower():
                continue
            if request.accessibility_topic and request.accessibility_topic.lower() not in (row.get("accessibility_topic") or "").lower():
                continue
            if request.travel_topic and request.travel_topic.lower() not in (row.get("travel_topic") or "").lower():
                continue
            filtered.append(row)
        return sorted(filtered, key=lambda item: int(item.get("editorial_frequency") or 0), reverse=True)

    def _row_to_suggestion(self, row: dict[str, str]) -> TopicSuggestion:
        destination = row.get("destination") or ""
        accessibility = row.get("accessibility_topic") or ""
        travel_topic = row.get("travel_topic") or ""
        title_parts = [part for part in [accessibility.title(), travel_topic.title(), destination] if part]
        title = " ".join(title_parts) if title_parts else row.get("topic", "Accessible travel idea")
        if destination:
            title = f"{title}: What Travellers Need To Know"
        else:
            title = f"{title}: A Practical Guide"
        params = {
            "title": title,
            "primary_keyword": row.get("topic") or title,
            "destination": destination,
            "search_intent": row.get("search_intent") or "Informational",
        }
        return TopicSuggestion(
            suggested_title=title,
            topic=row.get("topic") or "",
            destination=destination,
            accessibility_topic=accessibility,
            search_intent=row.get("search_intent") or "Informational / Commercial Research",
            competitor_frequency=row.get("editorial_frequency") or row.get("occurrences") or "0",
            conversion_relevance=row.get("conversion_relevance") or "UNKNOWN",
            why="This topic appears in crawler research and may help answer a practical accessible-travel planning question.",
            article_url="/?" + parse.urlencode(params),
        )

    async def _try_gemma_enrichment(self, rows: list[dict[str, str]]) -> None:
        system_prompt, user_prompt = self.prompts.build_suggestion_prompt(rows)
        try:
            await OllamaGemmaService().generate(system_prompt, user_prompt)
        except LLMError:
            return
