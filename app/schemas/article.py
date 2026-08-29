"""Article generation form schema."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


def split_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = str(value).replace("\r", "\n").replace(",", "\n").split("\n")
    return [item.strip() for item in values if item and item.strip()]


class ArticleRequest(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    primary_keyword: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    article_type: str = "SEO guide"
    search_intent: str = "Informational"
    funnel_stage: str = "Awareness"
    reader_need: str | None = None
    reader_concerns: str | None = None
    accessibility_requirements: list[str] = Field(default_factory=list)
    destination: str | None = None
    country: str | None = None
    related_destinations: list[str] = Field(default_factory=list)
    target_country: str = "UK"
    language: str = "en-GB"
    target_length: int = 1500
    generate_seo_title: bool = True
    generate_meta_description: bool = True
    generate_slug: bool = True
    generate_faq: bool = True
    generate_internal_links: bool = True
    generate_image_suggestions: bool = True
    generate_editorial_score: bool = True
    generate_fact_check_notes: bool = True
    primary_conversion_goal: str = "Phone enquiry"
    cta_strength: str = "Automatic based on intent"
    cta_context: str | None = None
    include_mid_article_cta: bool = True
    include_final_cta: bool = True
    trust_points: str | None = None
    reassurance_points: str | None = None
    verified_limitless_information: str | None = None
    use_research_data: bool = False
    show_debug_details: bool = False

    @field_validator("target_length")
    @classmethod
    def validate_length(cls, value: int) -> int:
        if value < 500 or value > 5000:
            raise ValueError("Target article length must be between 500 and 5000 words.")
        return value

    @classmethod
    def from_form(cls, form: Any) -> "ArticleRequest":
        checked = set(form.keys())
        return cls(
            title=str(form.get("title", "")).strip(),
            primary_keyword=_optional(form.get("primary_keyword")),
            secondary_keywords=split_multi_value(form.get("secondary_keywords")),
            article_type=str(form.get("article_type") or "SEO guide"),
            search_intent=str(form.get("search_intent") or "Informational"),
            funnel_stage=str(form.get("funnel_stage") or "Awareness"),
            reader_need=_optional(form.get("reader_need")),
            reader_concerns=_optional(form.get("reader_concerns")),
            accessibility_requirements=split_multi_value(form.get("accessibility_requirements")),
            destination=_optional(form.get("destination")),
            country=_optional(form.get("country")),
            related_destinations=split_multi_value(form.get("related_destinations")),
            target_country=str(form.get("target_country") or "UK"),
            language=str(form.get("language") or "en-GB"),
            target_length=int(form.get("target_length") or 1500),
            generate_seo_title="generate_seo_title" in checked,
            generate_meta_description="generate_meta_description" in checked,
            generate_slug="generate_slug" in checked,
            generate_faq="generate_faq" in checked,
            generate_internal_links="generate_internal_links" in checked,
            generate_image_suggestions="generate_image_suggestions" in checked,
            generate_editorial_score="generate_editorial_score" in checked,
            generate_fact_check_notes="generate_fact_check_notes" in checked,
            primary_conversion_goal=str(form.get("primary_conversion_goal") or "Phone enquiry"),
            cta_strength=str(form.get("cta_strength") or "Automatic based on intent"),
            cta_context=_optional(form.get("cta_context")),
            include_mid_article_cta="include_mid_article_cta" in checked,
            include_final_cta="include_final_cta" in checked,
            trust_points=_optional(form.get("trust_points")),
            reassurance_points=_optional(form.get("reassurance_points")),
            verified_limitless_information=_optional(form.get("verified_limitless_information")),
            use_research_data="use_research_data" in checked,
            show_debug_details="show_debug_details" in checked,
        )

    def to_form_data(self) -> dict[str, Any]:
        data = self.model_dump()
        for key in ["secondary_keywords", "accessibility_requirements", "related_destinations"]:
            data[key] = "\n".join(data[key])
        return data

    @staticmethod
    def article_type_options() -> list[str]:
        return [
            "SEO guide",
            "Destination guide",
            "Accessibility guide",
            "Question / answer article",
            "Commercial research article",
            "Travel advice",
            "Holiday inspiration",
            "Other",
        ]

    @staticmethod
    def search_intent_options() -> list[str]:
        return ["Informational", "Problem / Question", "Destination Research", "Commercial Research", "High Commercial Intent"]

    @staticmethod
    def funnel_stage_options() -> list[str]:
        return ["Awareness", "Discovery", "Consideration", "High Intent"]

    @staticmethod
    def length_options() -> list[int]:
        return [800, 1200, 1500, 1800, 2000, 2500]

    @staticmethod
    def conversion_goal_options() -> list[str]:
        return ["Phone enquiry", "Explore holidays", "Destination page visit", "Request information", "Callback / form"]

    @staticmethod
    def cta_strength_options() -> list[str]:
        return ["Soft", "Moderate", "Strong", "Automatic based on intent"]


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
