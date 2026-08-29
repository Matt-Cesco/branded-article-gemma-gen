"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.routes import articles, suggestions

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.repo_root / "app" / "templates"))

app = FastAPI(title="Limitless Travel Content Engine")
app.mount("/static", StaticFiles(directory=str(settings.repo_root / "app" / "static")), name="static")
app.include_router(articles.router)
app.include_router(suggestions.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    if request.url.path.startswith("/health"):
        return JSONResponse({"status": "error", "detail": "unexpected error"}, status_code=500)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"error": "Something went wrong. Please check the app logs and try again."},
        status_code=500,
    )
