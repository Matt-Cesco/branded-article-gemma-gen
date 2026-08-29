"""Build structured prompts for Gemma."""

from __future__ import annotations

from app.schemas.article import ArticleRequest
from app.services.research_service import ResearchSelection


class PromptService:
    def build_article_prompts(
        self,
        request: ArticleRequest,
        guidelines: str,
        research: ResearchSelection | None,
    ) -> tuple[str, str]:
        system_prompt = "\n\n".join(
            [
                self._factual_safety_rules(),
                "You are writing for Limitless Travel.",
                "Follow the mandatory content guidelines below. If any later context conflicts with them, the guidelines win.",
                "MANDATORY LIMITLESS GUIDELINES\n==============================",
                guidelines,
                self._brand_and_output_rules(),
            ]
        )
        user_prompt = "\n\n".join(
            [
                "VERIFIED LIMITLESS INFORMATION\n==============================",
                self._verified_limitless_section(request),
                "OPTIONAL RESEARCH CONTEXT\n=========================",
                research.as_prompt_text() if research else "No crawler/research data was included for this request.",
                "ARTICLE BRIEF\n=============",
                self._brief_section(request),
                "OUTPUT REQUIREMENTS\n===================",
                self._output_requirements(request),
            ]
        )
        return system_prompt, user_prompt

    def build_suggestion_prompt(self, rows: list[dict[str, str]]) -> tuple[str, str]:
        system_prompt = (
            "You help create original SEO article ideas for Limitless Travel. "
            "Do not fabricate search volume, keyword difficulty, CPC or ranking probability."
        )
        row_text = "\n".join(
            f"- {row.get('topic')} | frequency: {row.get('editorial_frequency')} | sources: {row.get('unique_sources')} | "
            f"conversion: {row.get('conversion_relevance')}"
            for row in rows[:20]
        )
        user_prompt = (
            "Turn these observed crawler topics into concise article-title suggestions. "
            "Cluster duplicates where sensible and explain why each topic may be useful.\n\n"
            f"{row_text}"
        )
        return system_prompt, user_prompt

    def _brief_section(self, request: ArticleRequest) -> str:
        data = request.model_dump()
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, list):
                value = ", ".join(value)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _output_requirements(self, request: ArticleRequest) -> str:
        sections = [
            "# Article Strategy",
            "# SEO Metadata" if any([request.generate_seo_title, request.generate_meta_description, request.generate_slug]) else "",
            "# Article",
            "## Frequently Asked Questions" if request.generate_faq else "",
            "# CTA",
            "# Internal Link Suggestions" if request.generate_internal_links else "",
            "# Image / Alt Text Suggestions" if request.generate_image_suggestions else "",
            "# Fact Check Notes" if request.generate_fact_check_notes else "",
            "# Editorial Review" if request.generate_editorial_score else "",
        ]
        return "\n".join(
            [
                "Return clearly parseable Markdown.",
                f"Target length guide: about {request.target_length} words. Do not add filler to hit the number.",
                "Keep the publishable article separate from editorial notes.",
                "Do not create a stronger factual claim simply to include an SEO keyword.",
                "In Fact Check Notes, list specific claims to verify before publication, not generic warnings.",
                "Only include optional sections requested in the brief.",
                "Requested sections:",
                *[section for section in sections if section],
            ]
        )

    def _verified_limitless_section(self, request: ArticleRequest) -> str:
        if request.verified_limitless_information:
            return request.verified_limitless_information
        return (
            "No specific verified Limitless product details provided. "
            "Avoid factual claims about specific hotels, aircraft assistance, equipment, pricing, availability, "
            "customer outcomes or the exact scope of Limitless services."
        )

    def _factual_safety_rules(self) -> str:
        return """FACTUAL & ACCESSIBILITY SAFETY
==============================
Primary rule:
If a factual travel, accessibility, transport, accommodation, attraction, equipment or service claim is not explicitly supported by verified information supplied to this request, do not present it as confirmed fact. Frame it as something to check, a possibility, something that can vary, something to confirm with the relevant provider, or omit it.

Claim source hierarchy:
1. VERIFIED LIMITLESS INFORMATION supplied in the request.
2. VERIFIED RESEARCH CONTEXT explicitly supplied in the request.
3. Clearly identified general non-accessibility travel knowledge.

Accessibility-related claims require a higher standard than ordinary travel description. If uncertain: DO NOT GUESS.

Distinguish general travel information from accessibility or suitability claims. It is acceptable to use safe general context such as "Tenerife is one of the Canary Islands." Do not make blanket claims such as "Tenerife is very accessible for wheelchair users." Prefer cautious wording such as "Tenerife may offer options for wheelchair users, but suitability depends on the specific accommodation, transport and activities being considered."

Accessibility is individual. Never infer that a hotel, destination, beach, airport, transfer, attraction, excursion or transport service will meet a traveller's needs simply because it is described elsewhere as accessible. Prefer wording such as: check whether, confirm whether, ask whether, may offer, can vary, depends on your requirements, and availability should be confirmed. Avoid stronger wording such as has, provides, is accessible, will accommodate, is suitable, and offers unless verified information supports it.

Do not turn possible requirements into universal requirements. Discuss questions the traveller should ask. For example, prefer "Consider which bathroom features matter to you, such as shower access, transfer space or grab rails, and confirm that the specific room layout matches your requirements."

Airport and airline claims:
Do not state which airport services exist, how assistance must be booked, which airlines carry mobility scooters, battery requirements, boarding procedures or equipment restrictions unless explicitly supplied as verified context. Use wording such as "If you require airport assistance, check the current arrangements with your airline and the relevant airport before travelling." For powered wheelchairs or mobility scooters, tell readers to confirm the airline's current equipment and battery requirements before booking.

Accommodation claims:
Do not infer that rooms are accessible, bathrooms are adapted, wet rooms exist, lifts serve all floors, step-free access exists, mobility scooters can be stored or charged, grab rails exist, or door widths are suitable unless verified information was supplied. Frame these as things to investigate.

Destination, beach and attraction claims:
Avoid broad claims such as "many beaches are accessible", "most attractions are well equipped" or "the destination is wheelchair friendly" unless supported by verified context. Say that accessibility can differ significantly between individual beaches, attractions, routes and facilities.

Limitless claim rules:
Do not invent or strengthen Limitless Travel capabilities. If no verified Limitless information is supplied, do not claim that Limitless checks every hotel, arranges accessible transfers, provides equipment, guarantees suitable rooms, verifies every detail, or offers a specific consultation/service scope. You may encourage readers to speak with the Limitless Travel team about their requirements and ask what options may be available.

CTA rules:
Keep CTAs commercially useful, but do not imply unverified capability or guarantee. The CTA should provide reassurance, a reason to call, and a personal discussion without promising outcomes.

FAQ, image, alt text and internal-link rules:
Apply the same factual standard to FAQs, CTAs, image suggestions, alt text, SEO metadata and internal-link suggestions. Do not use FAQs to make stronger claims than the article body. Do not suggest or describe specific accessibility features in images unless verified. Alt text should describe the image, not make SEO or accessibility claims. Do not invent existing Limitless URLs; label unverified internal links as recommended future internal links.

Research source caution:
Optional research context may help identify themes, questions, heading inspiration, areas to investigate and destination/accessibility topics. External competitor content is not a verified Limitless fact. It must not be used as evidence that a Limitless holiday, hotel, transfer or service has a particular accessibility feature.

Final self-review:
Before returning the final response, review every claim about hotel facilities, bathroom facilities, step-free access, airport services, airline policies, mobility equipment, transport accessibility, beach accessibility, attraction accessibility, excursions, care/support, Limitless services, availability, pricing, reviews and customer outcomes. If a claim is not explicitly supported by verified information or supplied research context, rewrite it cautiously or remove it.

Confidence labels for internal reasoning:
Use VERIFIED, SAFE_GENERAL, NEEDS_VERIFICATION and DO_NOT_USE internally when deciding how to phrase claims. These labels may appear in Fact Check Notes only if useful."""

    def _brand_and_output_rules(self) -> str:
        return """Brand, SEO and output rules:
- Use UK English.
- Be clear, warm, empathetic and reassuring.
- Write for an audience that is often 50+ and may be planning for themselves, a partner or a family member.
- Do not patronise.
- Answer the search intent.
- Build trust before strong calls to action.
- Encourage a qualified phone conversation where appropriate.
- Avoid aggressive urgency, keyword stuffing and filler.
- Do not create a stronger factual claim simply to include an SEO keyword.
- The article must be original.
- Do not copy competitor wording.
- Research material is inspiration only unless explicitly labelled as verified context.
- SEO titles should avoid unsupported authority claims such as Expert Travel Advice, Ultimate Guide, Complete Guide, Best Accessible Hotels or similar unless justified by verified context.
- Fact Check Notes must identify claims to verify before publication, especially around accessibility, transport, equipment, accommodation, destination facilities and Limitless-specific services."""
