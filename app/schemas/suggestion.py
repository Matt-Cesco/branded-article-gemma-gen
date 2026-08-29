"""Topic suggestion request schema."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SuggestionRequest(BaseModel):
    destination: str | None = None
    accessibility_topic: str | None = None
    travel_topic: str | None = None
    search_intent: str | None = None
    minimum_source_frequency: int = Field(default=1, ge=1, le=50)
    use_gemma: bool = True

    @classmethod
    def from_form(cls, form: Any) -> "SuggestionRequest":
        return cls(
            destination=_optional(form.get("destination")),
            accessibility_topic=_optional(form.get("accessibility_topic")),
            travel_topic=_optional(form.get("travel_topic")),
            search_intent=_optional(form.get("search_intent")),
            minimum_source_frequency=int(form.get("minimum_source_frequency") or 1),
            use_gemma="use_gemma" in set(form.keys()),
        )

    def to_form_data(self) -> dict[str, Any]:
        return self.model_dump()


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
