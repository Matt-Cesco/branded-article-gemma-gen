"""Topic suggestion routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.schemas.suggestion import SuggestionRequest
from app.services.suggestion_service import SuggestionService

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.repo_root / "app" / "templates"))
router = APIRouter()


@router.get("/suggestions", response_class=HTMLResponse)
async def suggestions_form(request: Request) -> HTMLResponse:
    service = SuggestionService(settings.repo_root)
    return templates.TemplateResponse(
        request,
        "suggestions.html",
        {
            "summary": service.available_research_summary(),
            "prefill": {},
        },
    )


@router.post("/suggestions/generate", response_class=HTMLResponse)
async def generate_suggestions(request: Request) -> HTMLResponse:
    form = await request.form()
    suggestion_request = SuggestionRequest.from_form(form)
    service = SuggestionService(settings.repo_root)
    suggestions = await service.generate_suggestions(suggestion_request)
    return templates.TemplateResponse(
        request,
        "suggestion_result.html",
        {
            "suggestions": suggestions,
            "prefill": suggestion_request.to_form_data(),
        },
    )
