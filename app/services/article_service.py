"""Article generation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from app.config import get_settings
from app.schemas.article import ArticleRequest
from app.services.gemma_service import LLMError, LLMGeneration, LLMService, OllamaGemmaService
from app.services.guideline_service import GuidelineService
from app.services.prompt_service import PromptService
from app.services.research_service import ResearchService


class ArticleGenerationError(RuntimeError):
    pass


@dataclass
class ArticleResult:
    markdown: str
    draft_path: Path
    model: str
    research_data_used: bool
    debug: dict[str, object] | None = None


class ArticleService:
    def __init__(self, repo_root: Path, llm_service: LLMService | None = None) -> None:
        self.repo_root = repo_root
        self.settings = get_settings()
        self.guidelines = GuidelineService(repo_root)
        self.research = ResearchService(repo_root)
        self.prompts = PromptService()
        self.llm = llm_service or OllamaGemmaService()

    async def generate_article(self, request: ArticleRequest) -> ArticleResult:
        guideline_bundle = self.guidelines.load_guideline_bundle()
        research_selection = None
        if request.use_research_data:
            research_selection = self.research.find_relevant_research(
                title=request.title,
                primary_keyword=request.primary_keyword,
                destination=request.destination,
                accessibility_topics=request.accessibility_requirements,
                secondary_keywords=request.secondary_keywords,
                reader_concerns=request.reader_concerns,
            )
        system_prompt, user_prompt = self.prompts.build_article_prompts(request, guideline_bundle.text, research_selection)
        started_at = datetime.now(timezone.utc)
        try:
            generation = await self.llm.generate(system_prompt, user_prompt)
        except LLMError as exc:
            raise ArticleGenerationError(str(exc)) from exc
        finished_at = datetime.now(timezone.utc)
        duration_seconds = round((finished_at - started_at).total_seconds(), 3)
        draft_path = self.save_draft(request, generation.content, generation, guideline_bundle, research_selection, duration_seconds)
        debug = None
        if request.show_debug_details:
            debug = {
                "model_configuration": {
                    "provider": generation.provider,
                    "model": generation.model,
                    "base_url": self.settings.ollama_base_url,
                },
                "guidelines": {
                    "file_count": len(guideline_bundle.filenames),
                    "filenames": guideline_bundle.filenames,
                    "character_count": guideline_bundle.character_count,
                    "approximate_tokens": guideline_bundle.approximate_tokens,
                },
                "article_brief": request.model_dump(),
                "research": self._research_debug(request.use_research_data, research_selection),
                "prompt_preview": {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                "generation": {
                    "generation_started_at": started_at.isoformat(),
                    "generation_finished_at": finished_at.isoformat(),
                    "generation_duration_seconds": duration_seconds,
                    "ollama_metrics": generation.metrics,
                },
            }
        return ArticleResult(
            markdown=generation.content,
            draft_path=draft_path,
            model=generation.model,
            research_data_used=request.use_research_data,
            debug=debug,
        )

    def save_draft(
        self,
        request: ArticleRequest,
        markdown: str,
        generation: LLMGeneration | str,
        guideline_bundle: object | None = None,
        research_selection: object | None = None,
        generation_duration_seconds: float | None = None,
    ) -> Path:
        drafts_dir = self.repo_root / "articles" / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).date().isoformat()
        base_slug = slugify(request.title)
        path = drafts_dir / f"{date}-{base_slug}.md"
        suffix = 2
        while path.exists():
            path = drafts_dir / f"{date}-{base_slug}-{suffix}.md"
            suffix += 1
        model = generation.model if isinstance(generation, LLMGeneration) else str(generation)
        provider = generation.provider if isinstance(generation, LLMGeneration) else "unknown"
        guideline_file_count = len(getattr(guideline_bundle, "filenames", [])) if guideline_bundle else 0
        research_count = 0
        if research_selection:
            research_count = int(getattr(research_selection, "summary", {}).get("records_selected", 0))
        front_matter = "\n".join(
            [
                "---",
                f"title: {request.title}",
                f"primary_keyword: {request.primary_keyword or ''}",
                f"search_intent: {request.search_intent}",
                f"destination: {request.destination or ''}",
                f"generated_at: {datetime.now(timezone.utc).isoformat()}",
                f"model: {model}",
                f"provider: {provider}",
                f"research_data_requested: {str(request.use_research_data).lower()}",
                f"research_data_used: {str(bool(research_count)).lower()}",
                f"research_record_count: {research_count}",
                f"guideline_file_count: {guideline_file_count}",
                f"generation_duration_seconds: {generation_duration_seconds if generation_duration_seconds is not None else ''}",
                "status: draft",
                "---",
                "",
            ]
        )
        path.write_text(front_matter + markdown, encoding="utf-8")
        return path

    def _research_debug(self, requested: bool, research_selection: object | None) -> dict[str, object]:
        if not requested or research_selection is None:
            return {
                "requested": False,
                "included_records": 0,
                "files_consulted": [],
                "truncated": False,
                "context_character_count": 0,
                "selected_source_pages": [],
                "selected_topic_combinations": [],
            }
        return {
            "requested": True,
            "included_records": getattr(research_selection, "summary", {}).get("records_selected", 0),
            "files_consulted": getattr(research_selection, "files_consulted", []),
            "truncated": getattr(research_selection, "truncated", False),
            "context_character_count": getattr(research_selection, "context_character_count", 0),
            "selected_source_pages": getattr(research_selection, "source_pages", []),
            "selected_topic_combinations": getattr(research_selection, "topic_combinations", []),
        }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "article"
