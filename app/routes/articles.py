"""Article generation routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.schemas.article import ArticleRequest
from app.services.article_service import ArticleGenerationError, ArticleService

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.repo_root / "app" / "templates"))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def article_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "article_form.html",
        {
            "prefill": dict(request.query_params),
            "article_types": ArticleRequest.article_type_options(),
            "search_intents": ArticleRequest.search_intent_options(),
            "funnel_stages": ArticleRequest.funnel_stage_options(),
            "length_options": ArticleRequest.length_options(),
            "conversion_goals": ArticleRequest.conversion_goal_options(),
            "cta_strengths": ArticleRequest.cta_strength_options(),
        },
    )


@router.post("/article/generate", response_class=HTMLResponse)
async def generate_article(request: Request) -> HTMLResponse:
    form = await request.form()
    article_request = ArticleRequest.from_form(form)
    service = ArticleService(settings.repo_root)
    try:
        result = await service.generate_article(article_request)
    except ArticleGenerationError as exc:
        return templates.TemplateResponse(
            request,
            "article_form.html",
            {
                "prefill": article_request.to_form_data(),
                "error": str(exc),
                "article_types": ArticleRequest.article_type_options(),
                "search_intents": ArticleRequest.search_intent_options(),
                "funnel_stages": ArticleRequest.funnel_stage_options(),
                "length_options": ArticleRequest.length_options(),
                "conversion_goals": ArticleRequest.conversion_goal_options(),
                "cta_strengths": ArticleRequest.cta_strength_options(),
            },
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "article_result.html",
        {
            "generated_markdown": result.markdown,
            "draft_path": result.draft_path,
            "model": result.model,
            "research_data_used": result.research_data_used,
            "debug": result.debug,
        },
    )


@router.get("/article/result")
async def article_result() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)
