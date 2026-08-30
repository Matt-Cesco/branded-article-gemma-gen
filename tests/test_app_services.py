import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.article import ArticleRequest
from app.schemas.suggestion import SuggestionRequest
from app.services.article_service import ArticleResult, ArticleService
from app.services.gemma_service import LLMError, LLMGeneration, LLMService
from app.services.guideline_service import GuidelineService
from app.services.prompt_service import PromptService
from app.services.research_service import ResearchService
from app.services.suggestion_service import SuggestionService


class FakeLLM(LLMService):
    def __init__(self, response: str = "# Article\n\nDraft", should_fail: bool = False) -> None:
        self.response = response
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneration:
        self.calls.append((system_prompt, user_prompt))
        if self.should_fail:
            raise LLMError("Ollama is not running")
        return LLMGeneration(
            content=self.response,
            provider="ollama",
            model="gemma-test",
            metrics={"prompt_eval_count": 12, "eval_count": 34},
        )


class FakeArticleService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    async def generate_brief(self, request: ArticleRequest) -> ArticleResult:
        return self._result("brief", "# Brief\n\nEDITORIAL READINESS: READY FOR DRAFT")

    async def generate_outline(self, request: ArticleRequest) -> ArticleResult:
        return self._result("outline", "# Outline")

    async def generate_draft(self, request: ArticleRequest) -> ArticleResult:
        return self._result("draft", "AI-ASSISTED DRAFT - HUMAN EDITING REQUIRED\n\nDraft")

    async def review_draft(self, draft_text: str) -> ArticleResult:
        return self._result("review", "# Editorial Review\n\n## Generic / formulaic writing")

    def _result(self, output_type: str, markdown: str) -> ArticleResult:
        return ArticleResult(
            markdown=markdown,
            draft_path=Path("articles") / f"{output_type}.md",
            model="fake-model",
            research_data_used=False,
            output_type=output_type,
        )


class AppServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_root = Path.cwd() / "tests" / ".tmp" / self._testMethodName
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)
        self.tmp_root.mkdir(parents=True)

    def tearDown(self) -> None:
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def test_guidelines_load_in_filename_order(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "02-second.md").write_text("second", encoding="utf-8")
        (guidelines / "01-first.md").write_text("first", encoding="utf-8")

        text = GuidelineService(root).load_all_guidelines()

        self.assertLess(text.index("01-first.md"), text.index("02-second.md"))

    def test_research_checkbox_disables_research_in_prompt(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife", use_research_data=False)
        _, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertIn("No crawler/research data was included", user_prompt)

    def test_debug_mode_defaults_to_false(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")

        self.assertFalse(request.show_debug_details)

    def test_debug_details_do_not_appear_when_disabled(self) -> None:
        client = TestClient(app)

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Generation debug details", response.text)

    def test_research_service_rejects_paths_outside_data(self) -> None:
        service = ResearchService(self.tmp_root)

        with self.assertRaises(ValueError):
            service.read_json_file("../outside.json")

    async def test_generated_drafts_get_unique_filenames(self) -> None:
        root = self.tmp_root
        (root / "articles" / "drafts").mkdir(parents=True)
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        service = ArticleService(root, llm_service=FakeLLM())

        first = service.save_draft(request, "# Article", "gemma-test")
        second = service.save_draft(request, "# Article", "gemma-test")

        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    async def test_generated_briefs_get_unique_filenames(self) -> None:
        root = self.tmp_root
        request = ArticleRequest(title="Planning an Accessible Holiday")
        service = ArticleService(root, llm_service=FakeLLM())
        generation = LLMGeneration("# Brief", "ollama", "gemma-test", {})

        first = service.save_brief(request, "# Brief", generation)
        second = service.save_brief(request, "# Brief", generation)

        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertIn("briefs", str(first))

    async def test_generated_reviews_get_unique_filenames(self) -> None:
        root = self.tmp_root
        service = ArticleService(root, llm_service=FakeLLM())
        generation = LLMGeneration("# Review", "ollama", "gemma-test", {})

        first = service.save_review("draft-review", "# Review", generation)
        second = service.save_review("draft-review", "# Review", generation)

        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertIn("reviews", str(first))

    async def test_article_generation_debug_payload_is_optional(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        service = ArticleService(root, llm_service=FakeLLM())

        plain_result = await service.generate_article(ArticleRequest(title="Wheelchair Accessible Holidays"))
        debug_result = await service.generate_article(
            ArticleRequest(title="Wheelchair Accessible Holidays", show_debug_details=True)
        )

        self.assertIsNone(plain_result.debug)
        self.assertIsNotNone(debug_result.debug)
        self.assertIn("prompt_preview", debug_result.debug)

    def test_human_input_fields_parse_from_form(self) -> None:
        request = ArticleRequest.from_form(
            {
                "working_topic": "Planning an accessible holiday",
                "title": "5 Tips for Planning an Accessible Holiday",
                "audience": "UK travellers aged 50+",
                "reader_goal": "Know what to check",
                "reader_next_understanding": "Accessible labels are not enough",
                "next_action": "Call Limitless Travel",
                "real_customer_questions": "Can I charge my scooter?",
                "travel_advisor_observations": "Bathroom layout often decides suitability.",
                "common_booking_problems": "Room labels are vague.",
                "real_examples_anecdotes": "A customer needed side-transfer space.",
                "relevant_limitless_services_process": "Advisors discuss requirements before options.",
                "verified_product_holiday_information": "Verified holiday detail.",
                "commercial_priority": "Encourage advisor calls.",
                "verified_accessibility_facts": "Verified ramp detail.",
                "facts_to_check": "Airline battery rules.",
            }
        )

        self.assertEqual(request.working_topic, "Planning an accessible holiday")
        self.assertEqual(request.audience, "UK travellers aged 50+")
        self.assertEqual(request.real_customer_questions, "Can I charge my scooter?")
        self.assertEqual(request.relevant_limitless_services_process, "Advisors discuss requirements before options.")

    def test_empty_human_input_warning_for_drafts(self) -> None:
        service = ArticleService(self.tmp_root, llm_service=FakeLLM())
        request = ArticleRequest(title="Planning an Accessible Holiday")

        warning = service.empty_human_input_warning(request)

        self.assertIn("little Limitless-specific human input", warning or "")

    def test_no_empty_human_input_warning_when_knowledge_supplied(self) -> None:
        service = ArticleService(self.tmp_root, llm_service=FakeLLM())
        request = ArticleRequest(
            title="Planning an Accessible Holiday",
            real_customer_questions="Can I charge my scooter?",
        )

        self.assertIsNone(service.empty_human_input_warning(request))

    async def test_research_disabled_means_no_research_context_reaches_llm(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        fake_llm = FakeLLM()
        service = ArticleService(root, llm_service=fake_llm)

        await service.generate_article(ArticleRequest(title="Wheelchair Accessible Holidays", use_research_data=False))

        self.assertIn("No crawler/research data was included", fake_llm.calls[0][1])

    async def test_brief_generation_workflow_uses_llm_and_saves_brief(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        fake_llm = FakeLLM("# Content Brief\n\nEDITORIAL READINESS: NEEDS MORE LIMITLESS INPUT")
        service = ArticleService(root, llm_service=fake_llm)

        result = await service.generate_brief(ArticleRequest(title="Planning an Accessible Holiday"))

        self.assertEqual(result.output_type, "brief")
        self.assertIn("briefs", str(result.draft_path))
        self.assertIn("CONTENT BRIEF TASK", fake_llm.calls[0][1])

    async def test_outline_generation_workflow_uses_approved_brief(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        fake_llm = FakeLLM("# Outline")
        service = ArticleService(root, llm_service=fake_llm)

        await service.generate_outline(
            ArticleRequest(title="Planning an Accessible Holiday", approved_content_brief="Approved brief text")
        )

        self.assertIn("OUTLINE TASK", fake_llm.calls[0][1])
        self.assertIn("Approved brief text", fake_llm.calls[0][1])

    async def test_draft_generation_labels_human_review_required(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        fake_llm = FakeLLM("AI-ASSISTED DRAFT - HUMAN EDITING REQUIRED\n\nDraft")
        service = ArticleService(root, llm_service=fake_llm)

        result = await service.generate_draft(ArticleRequest(title="Planning an Accessible Holiday"))

        self.assertEqual(result.output_type, "draft")
        self.assertIn("AI-ASSISTED DRAFT - HUMAN EDITING REQUIRED", fake_llm.calls[0][1])
        self.assertIn("little Limitless-specific human input", result.human_input_warning or "")

    def test_draft_prompt_includes_supplied_human_knowledge_without_fabricating_missing_knowledge(self) -> None:
        request = ArticleRequest(
            title="Planning an Accessible Holiday",
            real_customer_questions="Can I charge my scooter?",
            travel_advisor_observations="Bathroom layout often decides suitability.",
        )

        _, user_prompt = PromptService().build_draft_prompt(request, "guidelines", None)

        self.assertIn("Can I charge my scooter?", user_prompt)
        self.assertIn("Bathroom layout often decides suitability.", user_prompt)
        self.assertIn("Do not fabricate advisor observations", PromptService().build_draft_prompt(ArticleRequest(title="x topic"), "guidelines", None)[1])

    def test_brief_prompt_requires_central_argument_and_editorial_readiness(self) -> None:
        request = ArticleRequest(title="Planning an Accessible Holiday")
        _, user_prompt = PromptService().build_brief_prompt(request, "guidelines", None)

        self.assertIn("Central editorial argument", user_prompt)
        self.assertIn("EDITORIAL READINESS", user_prompt)
        self.assertIn("What makes this specifically Limitless?", user_prompt)

    def test_review_prompt_receives_draft_text_and_flags_generic_patterns(self) -> None:
        system_prompt, user_prompt = PromptService().build_review_prompt("Draft text here", "guidelines")

        self.assertIn("Do not act as an AI detector", system_prompt)
        self.assertIn("Draft text here", user_prompt)
        self.assertIn("Generic / formulaic writing", user_prompt)
        self.assertIn("Low-information paragraphs", user_prompt)
        self.assertIn("Missing Limitless specificity", user_prompt)

    def test_review_route_loads(self) -> None:
        client = TestClient(app)

        response = client.get("/review")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Review existing draft", response.text)

    def test_brief_outline_draft_and_review_post_routes_use_mocked_service(self) -> None:
        client = TestClient(app)
        with patch("app.routes.articles.ArticleService", FakeArticleService):
            brief = client.post("/brief/generate", data={"working_topic": "Planning an accessible holiday"})
            outline = client.post("/outline/generate", data={"working_topic": "Planning an accessible holiday"})
            draft = client.post("/draft/generate", data={"working_topic": "Planning an accessible holiday"})
            review = client.post("/review/analyse", data={"draft_text": "Generic draft text"})

        self.assertEqual(brief.status_code, 200)
        self.assertIn("Content brief", brief.text)
        self.assertEqual(outline.status_code, 200)
        self.assertIn("Content outline", outline.text)
        self.assertEqual(draft.status_code, 200)
        self.assertIn("human editing required", draft.text.lower())
        self.assertEqual(review.status_code, 200)
        self.assertIn("Generic / formulaic writing", review.text)

    async def test_draft_yaml_contains_generation_metadata(self) -> None:
        root = self.tmp_root
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife", use_research_data=True)
        service = ArticleService(root, llm_service=FakeLLM())
        generation = LLMGeneration("# Article", "ollama", "gemma-test", {})

        path = service.save_draft(request, "# Article", generation, generation_duration_seconds=1.25)
        text = path.read_text(encoding="utf-8")

        self.assertIn("provider: ollama", text)
        self.assertIn("research_data_requested: true", text)
        self.assertIn("generation_duration_seconds: 1.25", text)

    async def test_suggestion_aggregation_handles_duplicate_topics(self) -> None:
        root = self.tmp_root
        output = root / "data" / "output" / "opportunities"
        output.mkdir(parents=True)
        (output / "topic-combinations.csv").write_text(
            "topic,destination,accessibility_topic,travel_topic,occurrences,unique_sources,editorial_frequency,search_demand,conversion_relevance\n"
            "Tenerife + wheelchair + hotels,Tenerife,wheelchair,hotels,4,2,4,,VERY_HIGH\n"
            "Tenerife + wheelchair + beaches,Tenerife,wheelchair,beaches,1,1,1,,MEDIUM\n",
            encoding="utf-8",
        )
        service = SuggestionService(root)

        suggestions = await service.generate_suggestions(SuggestionRequest(destination="Tenerife", use_gemma=False))

        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0].competitor_frequency, "4")

    def test_research_enabled_selects_relevant_records_and_respects_limit(self) -> None:
        root = self.tmp_root
        output = root / "data" / "output" / "opportunities"
        output.mkdir(parents=True)
        (output / "source-pages.csv").write_text(
            "source,url,title,publication_date,destination,country,accessibility_topics,travel_topics,source_type\n"
            "A,https://example.com/1,Tenerife Wheelchair Guide,,Tenerife,Spain,wheelchair,hotels,blog\n"
            "A,https://example.com/2,Generic accessible travel,,,,,travel,blog\n",
            encoding="utf-8",
        )
        (output / "topic-combinations.csv").write_text(
            "topic,destination,accessibility_topic,travel_topic,occurrences,unique_sources,editorial_frequency,search_demand,conversion_relevance\n"
            "Tenerife + wheelchair + hotels,Tenerife,wheelchair,hotels,4,2,4,,VERY_HIGH\n",
            encoding="utf-8",
        )
        service = ResearchService(root)
        service.settings.max_research_records = 1

        selection = service.find_relevant_research(
            "Wheelchair Accessible Holidays in Tenerife",
            "wheelchair accessible holidays Tenerife",
            "Tenerife",
            ["wheelchair"],
        )

        self.assertEqual(selection.summary["records_selected"], 1)
        self.assertTrue(selection.truncated)
        self.assertIn("source-pages.csv", selection.files_consulted[0])

    def test_debug_prompt_preview_does_not_expose_environment_secrets(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife", show_debug_details=True)
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertNotIn("GEMINI_API_KEY", system_prompt + user_prompt)
        self.assertNotIn("OLLAMA_BASE_URL", system_prompt + user_prompt)

    def test_system_and_user_prompts_remain_separate(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertIn("guidelines", system_prompt)
        self.assertIn("ARTICLE BRIEF", user_prompt)
        self.assertNotIn("ARTICLE BRIEF", system_prompt)

    def test_factual_safety_rules_are_high_priority_in_system_prompt(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, _ = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertLess(system_prompt.index("FACTUAL & ACCESSIBILITY SAFETY"), system_prompt.index("You are writing"))
        self.assertIn("do not present it as confirmed fact", system_prompt)
        self.assertIn("Accessibility-related claims require a higher standard", system_prompt)
        self.assertIn("If uncertain: DO NOT GUESS", system_prompt)

    def test_prompt_blocks_unverified_limitless_and_competitor_claims(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)
        combined_prompt = system_prompt + "\n" + user_prompt

        self.assertIn("Do not invent or strengthen Limitless Travel capabilities", combined_prompt)
        self.assertIn("External competitor content is not a verified Limitless fact", combined_prompt)
        self.assertIn("must not be used as evidence that a Limitless holiday", combined_prompt)
        self.assertIn("VERIFIED LIMITLESS INFORMATION", user_prompt)
        self.assertIn("OPTIONAL RESEARCH CONTEXT", user_prompt)

    def test_prompt_requires_cautious_language_for_unknown_accessibility_details(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, _ = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertIn("check whether", system_prompt)
        self.assertIn("confirm whether", system_prompt)
        self.assertIn("availability should be confirmed", system_prompt)
        self.assertIn("rewrite it cautiously or remove it", system_prompt)
        self.assertIn("Avoid implied accessibility certainty", system_prompt)
        self.assertIn("well-equipped, easy, smooth, stress-free", system_prompt)
        self.assertIn("Destination-specific accessibility claims", system_prompt)
        self.assertIn("Safe general knowledge can support ordinary travel appeal", system_prompt)
        self.assertIn("It cannot support accessibility certainty", system_prompt)
        self.assertIn("Mandatory red-flag scan", system_prompt)
        self.assertIn("well-equipped for accessible holidays", system_prompt)
        self.assertIn("Do not claim that most airlines allow, carry or can accommodate mobility scooters or powerchairs", system_prompt)
        self.assertIn("Do not include an airline-policy FAQ unless verified airline context was supplied", system_prompt)
        self.assertIn("most airlines allow", system_prompt)
        self.assertIn("most airlines can accommodate", system_prompt)

    def test_prompt_requires_commercial_phone_enquiry_strategy(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)
        combined_prompt = system_prompt + "\n" + user_prompt

        self.assertIn("qualified Limitless Travel phone enquiry", combined_prompt)
        self.assertIn("branded commercial content with editorial value", combined_prompt)
        self.assertIn("commercial purpose should influence the article rather than dictate the structure of every paragraph", combined_prompt)
        self.assertIn("Do not count brand mentions", combined_prompt)
        self.assertIn("Brand mentions should appear only where they naturally add value", combined_prompt)
        self.assertIn("sell Limitless through the quality, usefulness and accessible-travel perspective", combined_prompt)
        self.assertIn("Sell the holiday experience", combined_prompt)
        self.assertIn("holiday feel possible and desirable", combined_prompt)
        self.assertIn("Do not invent services", combined_prompt)
        self.assertIn("Do not claim Limitless verifies every detail", combined_prompt)
        self.assertIn("use one main CTA", combined_prompt)
        self.assertIn("The primary CTA must identify Limitless by name", combined_prompt)
        self.assertIn("Call Limitless to discuss your holiday requirements", combined_prompt)
        self.assertIn("call us", combined_prompt)
        self.assertIn("without naming Limitless is incomplete", combined_prompt)
        self.assertIn("does not need extra brand mentions elsewhere unless they add value", combined_prompt)
        self.assertIn("Conversion should happen because the article exposes a real reason why personalised help is valuable", combined_prompt)

    def test_prompt_discourages_formulaic_ai_article_patterns(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)
        combined_prompt = system_prompt + "\n" + user_prompt

        self.assertIn("Avoid formulaic AI structure", combined_prompt)
        self.assertIn("Do not force every destination article into Introduction, Accommodation, Transport, Activities, Preparation, FAQ and CTA", combined_prompt)
        self.assertIn("Do not make \"5 tips\" behave like five identical mini-essays", combined_prompt)
        self.assertIn("produce exactly that many numbered tip sections", combined_prompt)
        self.assertIn("do not add a sixth tip or change the count", combined_prompt)
        self.assertIn("Do not let each section follow the same arc of friendly setup, generic problem, broad advice, reassurance and Limitless insertion", combined_prompt)
        self.assertIn("Every paragraph must earn its place", combined_prompt)
        self.assertIn("Concrete examples", combined_prompt)
        self.assertIn("Avoid generic introductions", combined_prompt)
        self.assertIn("Do not open with boilerplate", combined_prompt)
        self.assertIn("Ban fake warmth", combined_prompt)
        self.assertIn("When you think about your next getaway", combined_prompt)
        self.assertIn("Avoid generic AI transitions and cliches", combined_prompt)
        self.assertIn("Strongly reduce phrases such as however", combined_prompt)
        self.assertIn("If the company name could be replaced with another travel company", combined_prompt)

    def test_prompt_prioritises_information_density_over_target_length(self) -> None:
        request = ArticleRequest(title="5 Tips for Planning an Accessible Holiday That Works for You")
        _, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertIn("This is not a minimum; a shorter useful article is better than a padded one", user_prompt)
        self.assertIn("Do not insert placeholder labels such as [Mid-article CTA] inside the article", user_prompt)
        self.assertIn("The primary CTA section must contain the word Limitless", user_prompt)
        self.assertIn("If it does not, the response is invalid", user_prompt)
        self.assertIn("If the brief and research do not support a useful article at the target length", user_prompt)
        self.assertIn("write a shorter useful article", user_prompt)
        self.assertIn("identify missing research or information an editor should add", user_prompt)

    def test_research_enabled_prompt_requires_destination_specificity_without_claim_invention(self) -> None:
        root = self.tmp_root
        output = root / "data" / "output" / "opportunities"
        output.mkdir(parents=True)
        (output / "source-pages.csv").write_text(
            "source,url,title,publication_date,destination,country,accessibility_topics,travel_topics,source_type\n"
            "A,https://example.com/1,Tenerife Wheelchair Beaches,,Tenerife,Spain,wheelchair,beaches,blog\n",
            encoding="utf-8",
        )
        (output / "topic-combinations.csv").write_text(
            "topic,destination,accessibility_topic,travel_topic,occurrences,unique_sources,editorial_frequency,search_demand,conversion_relevance\n"
            "Tenerife + wheelchair + beaches,Tenerife,wheelchair,beaches,4,2,4,,VERY_HIGH\n",
            encoding="utf-8",
        )
        request = ArticleRequest(
            title="Wheelchair Accessible Holidays in Tenerife",
            destination="Tenerife",
            accessibility_requirements=["wheelchair"],
            use_research_data=True,
        )
        research = ResearchService(root).find_relevant_research(
            request.title,
            request.primary_keyword,
            request.destination,
            request.accessibility_requirements,
        )
        system_prompt, user_prompt = PromptService().build_article_prompts(request, "guidelines", research)
        combined_prompt = system_prompt + "\n" + user_prompt

        self.assertIn("Research data is ON", combined_prompt)
        self.assertIn("Inspect the selected rows before deciding the article structure", combined_prompt)
        self.assertIn("Research should influence structure, not be poured into a generic template", combined_prompt)
        self.assertIn("not evidence of Limitless product features or accessibility claims", combined_prompt)
        self.assertIn("Crawler rows, page titles, observed topics, source names, frequencies and conversion labels are not factual evidence by themselves", combined_prompt)
        self.assertIn("do not upgrade a theme into a destination claim", combined_prompt)
        self.assertIn("Tenerife Wheelchair Beaches", combined_prompt)

    def test_default_verified_limitless_section_prevents_service_scope_claims(self) -> None:
        request = ArticleRequest(title="Wheelchair Accessible Holidays in Tenerife")
        _, user_prompt = PromptService().build_article_prompts(request, "guidelines", None)

        self.assertIn("No specific verified Limitless product details provided", user_prompt)
        self.assertIn("Avoid factual claims about specific hotels", user_prompt)

    async def test_ollama_errors_are_reported_without_successful_draft(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        service = ArticleService(root, llm_service=FakeLLM(should_fail=True))

        with self.assertRaises(Exception) as error:
            await service.generate_article(ArticleRequest(title="Wheelchair Accessible Holidays"))

        self.assertIn("Ollama is not running", str(error.exception))


if __name__ == "__main__":
    unittest.main()
