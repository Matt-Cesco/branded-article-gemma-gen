"""Content assistant routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.schemas.article import ArticleRequest
from app.services.article_service import ArticleGenerationError, ArticleResult, ArticleService

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


@router.get("/brief", response_class=HTMLResponse)
async def brief_form(request: Request) -> HTMLResponse:
    return await article_form(request)


@router.get("/draft", response_class=HTMLResponse)
async def draft_form(request: Request) -> HTMLResponse:
    return await article_form(request)


@router.post("/article/generate", response_class=HTMLResponse)
async def generate_article(request: Request) -> HTMLResponse:
    return await generate_draft(request)


@router.post("/brief/generate", response_class=HTMLResponse)
async def generate_brief(request: Request) -> HTMLResponse:
    return await _generate_assistant_output(request, "brief")


@router.post("/outline/generate", response_class=HTMLResponse)
async def generate_outline(request: Request) -> HTMLResponse:
    return await _generate_assistant_output(request, "outline")


@router.post("/draft/generate", response_class=HTMLResponse)
async def generate_draft(request: Request) -> HTMLResponse:
    return await _generate_assistant_output(request, "draft")


async def _generate_assistant_output(request: Request, output_type: str) -> HTMLResponse:
    form = await request.form()
    article_request = ArticleRequest.from_form(form)
    service = ArticleService(settings.repo_root)
    try:
        if output_type == "brief":
            result = await service.generate_brief(article_request)
        elif output_type == "outline":
            result = await service.generate_outline(article_request)
        else:
            result = await service.generate_draft(article_request)
    except ArticleGenerationError as exc:
        return _form_response(request, article_request, str(exc), 400)
    return _result_response(request, result)


@router.get("/review", response_class=HTMLResponse)
async def review_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "review_form.html", {"prefill": {}})


@router.post("/review/analyse", response_class=HTMLResponse)
async def analyse_review(request: Request) -> HTMLResponse:
    form = await request.form()
    draft_text = str(form.get("draft_text") or "").strip()
    if not draft_text:
        return templates.TemplateResponse(
            request,
            "review_form.html",
            {"prefill": {"draft_text": draft_text}, "error": "Paste draft text to review."},
            status_code=400,
        )
    service = ArticleService(settings.repo_root)
    try:
        result = await service.review_draft(draft_text)
    except ArticleGenerationError as exc:
        return templates.TemplateResponse(
            request,
            "review_form.html",
            {"prefill": {"draft_text": draft_text}, "error": str(exc)},
            status_code=400,
        )
    return _result_response(request, result)


def _form_response(request: Request, article_request: ArticleRequest, error: str | None = None, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "article_form.html",
        {
            "prefill": article_request.to_form_data(),
            "error": error,
            "article_types": ArticleRequest.article_type_options(),
            "search_intents": ArticleRequest.search_intent_options(),
            "funnel_stages": ArticleRequest.funnel_stage_options(),
            "length_options": ArticleRequest.length_options(),
            "conversion_goals": ArticleRequest.conversion_goal_options(),
            "cta_strengths": ArticleRequest.cta_strength_options(),
        },
        status_code=status_code,
    )


def _result_response(request: Request, result: ArticleResult) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "article_result.html",
        {
            "generated_markdown": result.markdown,
            "draft_path": result.draft_path,
            "model": result.model,
            "research_data_used": result.research_data_used,
            "debug": result.debug,
            "human_input_used": result.human_input_used or [],
            "human_input_warning": result.human_input_warning,
            "output_type": result.output_type,
        },
    )


@router.get("/article/result")
async def article_result() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)
