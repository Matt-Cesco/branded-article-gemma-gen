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
    human_input_used: list[str] | None = None
    human_input_warning: str | None = None
    output_type: str = "draft"


class ArticleService:
    def __init__(self, repo_root: Path, llm_service: LLMService | None = None) -> None:
        self.repo_root = repo_root
        self.settings = get_settings()
        self.guidelines = GuidelineService(repo_root)
        self.research = ResearchService(repo_root)
        self.prompts = PromptService()
        self.llm = llm_service or OllamaGemmaService()

    async def generate_article(self, request: ArticleRequest) -> ArticleResult:
        return await self.generate_draft(request)

    async def generate_brief(self, request: ArticleRequest) -> ArticleResult:
        return await self._generate_content_artifact(request, "brief")

    async def generate_outline(self, request: ArticleRequest) -> ArticleResult:
        return await self._generate_content_artifact(request, "outline")

    async def generate_draft(self, request: ArticleRequest) -> ArticleResult:
        return await self._generate_content_artifact(request, "draft")

    async def review_draft(self, draft_text: str) -> ArticleResult:
        guideline_bundle = self.guidelines.load_guideline_bundle()
        system_prompt, user_prompt = self.prompts.build_review_prompt(draft_text, guideline_bundle.text)
        generation, duration_seconds, started_at, finished_at = await self._run_generation(system_prompt, user_prompt)
        path = self.save_review("draft-review", generation.content, generation, guideline_bundle, duration_seconds)
        return ArticleResult(
            markdown=generation.content,
            draft_path=path,
            model=generation.model,
            research_data_used=False,
            output_type="review",
        )

    async def _generate_content_artifact(self, request: ArticleRequest, output_type: str) -> ArticleResult:
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
        if output_type == "brief":
            system_prompt, user_prompt = self.prompts.build_brief_prompt(request, guideline_bundle.text, research_selection)
        elif output_type == "outline":
            system_prompt, user_prompt = self.prompts.build_outline_prompt(request, guideline_bundle.text, research_selection)
        elif output_type == "draft":
            system_prompt, user_prompt = self.prompts.build_draft_prompt(request, guideline_bundle.text, research_selection)
        else:
            system_prompt, user_prompt = self.prompts.build_article_prompts(request, guideline_bundle.text, research_selection)
        generation, duration_seconds, started_at, finished_at = await self._run_generation(system_prompt, user_prompt)
        if output_type == "brief":
            draft_path = self.save_brief(request, generation.content, generation, guideline_bundle, research_selection, duration_seconds)
        else:
            draft_path = self.save_draft(request, generation.content, generation, guideline_bundle, research_selection, duration_seconds)
        human_input_used = self.human_input_used(request)
        human_input_warning = self.empty_human_input_warning(request) if output_type == "draft" else None
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
                "human_input_used": human_input_used,
                "human_input_warning": human_input_warning,
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
            human_input_used=human_input_used,
            human_input_warning=human_input_warning,
            output_type=output_type,
        )

    async def _run_generation(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[LLMGeneration, float, datetime, datetime]:
        started_at = datetime.now(timezone.utc)
        try:
            generation = await self.llm.generate(system_prompt, user_prompt)
        except LLMError as exc:
            raise ArticleGenerationError(str(exc)) from exc
        finished_at = datetime.now(timezone.utc)
        duration_seconds = round((finished_at - started_at).total_seconds(), 3)
        return generation, duration_seconds, started_at, finished_at

    def save_brief(
        self,
        request: ArticleRequest,
        markdown: str,
        generation: LLMGeneration | str,
        guideline_bundle: object | None = None,
        research_selection: object | None = None,
        generation_duration_seconds: float | None = None,
    ) -> Path:
        return self._save_markdown_artifact(
            "briefs",
            request.title,
            request,
            markdown,
            generation,
            guideline_bundle,
            research_selection,
            generation_duration_seconds,
        )

    def save_review(
        self,
        title: str,
        markdown: str,
        generation: LLMGeneration | str,
        guideline_bundle: object | None = None,
        generation_duration_seconds: float | None = None,
    ) -> Path:
        request = ArticleRequest(title=title)
        return self._save_markdown_artifact(
            "reviews",
            title,
            request,
            markdown,
            generation,
            guideline_bundle,
            None,
            generation_duration_seconds,
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
        return self._save_markdown_artifact(
            "drafts",
            request.title,
            request,
            markdown,
            generation,
            guideline_bundle,
            research_selection,
            generation_duration_seconds,
        )

    def _save_markdown_artifact(
        self,
        folder_name: str,
        title: str,
        request: ArticleRequest,
        markdown: str,
        generation: LLMGeneration | str,
        guideline_bundle: object | None = None,
        research_selection: object | None = None,
        generation_duration_seconds: float | None = None,
    ) -> Path:
        output_dir = self.repo_root / "articles" / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).date().isoformat()
        base_slug = slugify(title)
        path = output_dir / f"{date}-{base_slug}.md"
        suffix = 2
        while path.exists():
            path = output_dir / f"{date}-{base_slug}-{suffix}.md"
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
                f"artifact_type: {folder_name.rstrip('s')}",
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

    def human_input_used(self, request: ArticleRequest) -> list[str]:
        fields = [
            ("Real customer questions", request.real_customer_questions),
            ("Travel advisor observations", request.travel_advisor_observations),
            ("Common booking problems", request.common_booking_problems),
            ("Real examples / anecdotes", request.real_examples_anecdotes),
            ("Relevant Limitless services / process", request.relevant_limitless_services_process),
            ("Verified product / holiday information", request.verified_product_holiday_information),
            ("Commercial priority", request.commercial_priority),
        ]
        return [label for label, value in fields if value]

    def empty_human_input_warning(self, request: ArticleRequest) -> str | None:
        critical_fields = [
            request.real_customer_questions,
            request.travel_advisor_observations,
            request.real_examples_anecdotes,
            request.relevant_limitless_services_process,
            request.verified_product_holiday_information,
        ]
        if any(critical_fields):
            return None
        return (
            "This draft has little Limitless-specific human input. It may sound generic. "
            "For a stronger article, add advisor observations, real customer questions or verified business knowledge."
        )

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
