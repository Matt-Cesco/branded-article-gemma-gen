import shutil
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.article import ArticleRequest
from app.schemas.suggestion import SuggestionRequest
from app.services.article_service import ArticleService
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

    async def test_research_disabled_means_no_research_context_reaches_llm(self) -> None:
        root = self.tmp_root
        guidelines = root / "content-guidelines"
        guidelines.mkdir()
        (guidelines / "00.md").write_text("guidelines", encoding="utf-8")
        fake_llm = FakeLLM()
        service = ArticleService(root, llm_service=fake_llm)

        await service.generate_article(ArticleRequest(title="Wheelchair Accessible Holidays", use_research_data=False))

        self.assertIn("No crawler/research data was included", fake_llm.calls[0][1])

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
