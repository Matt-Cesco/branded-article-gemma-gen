"""External accessible-travel topic discovery crawler."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import parse, request, robotparser
from urllib.error import HTTPError, URLError

from research.config_loader import load_yaml
from research.topic_extraction import (
    build_topic_combinations,
    extract_accessibility_topics,
    extract_destinations,
    extract_travel_topics,
    guess_conversion_relevance,
    guess_search_intent,
    infer_content_type,
)

USER_AGENT = "LimitlessTravelContentResearchBot/0.1 (+research-only; respects robots.txt)"
DEFAULT_TIMEOUT = 15
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_PAGES_PER_DOMAIN = 40

CANDIDATE_PATH_TERMS = [
    "blog",
    "blogs",
    "news",
    "news-and-blog",
    "articles",
    "stories",
    "travel-stories",
    "guides",
    "inspiration",
    "resources",
    "travel-tips",
    "destinations",
    "accessible-travel",
    "wheelchair-friendly",
    "accessible-holidays",
]

RELEVANCE_TERMS = [
    "accessible",
    "accessibility",
    "disabled",
    "disability",
    "wheelchair",
    "mobility scooter",
    "reduced mobility",
    "accessible hotel",
    "adapted room",
    "wet room",
    "roll-in shower",
    "airport assistance",
    "accessible transport",
    "carer",
    "cruise",
    "holiday",
    "travel",
]

JS_REQUIRED_MARKERS = [
    "enable javascript",
    "requires javascript",
    "please turn javascript on",
    "__next_data__",
    "id=\"root\"",
    "id=\"app\"",
]


@dataclass
class SourceConfig:
    name: str
    base_url: str
    start_url: str
    source_type: str
    priority: str


@dataclass
class DiscoveredPage:
    source: str
    source_type: str
    url: str
    canonical_url: str | None
    title: str | None
    h1: str | None
    publication_date: str | None
    updated_date: str | None
    author: str | None
    headings: dict[str, list[str]]
    summary: str | None
    category: str | None
    tags: list[str]
    destination_mentions: list[str]
    country_mentions: list[str]
    accessibility_topics: list[str]
    travel_topics: list[str]
    topic_combinations: list[dict[str, str | None]]
    content_type: str | None
    search_intent_guess: str | None
    commercial_relevance: str
    conversion_relevance: str
    discovered_from: str | None
    crawl_depth: int
    crawled_at: str


@dataclass
class FetchResult:
    status: str
    url: str
    status_code: int | None = None
    html: str | None = None
    error: str | None = None


class ResearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.h1: str | None = None
        self.headings: dict[str, list[str]] = {"h2": [], "h3": []}
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self.canonical_url: str | None = None
        self._tag_stack: list[str] = []
        self._text_buffer: list[str] = []
        self._current_link: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        self._tag_stack.append(tag)
        if tag == "a" and attr.get("href"):
            self._current_link = attr["href"]
            self._link_text = []
        elif tag == "meta":
            key = attr.get("name") or attr.get("property")
            content = attr.get("content")
            if key and content:
                self.meta[key.lower()] = _clean_text(content)
        elif tag == "link" and attr.get("rel", "").lower() == "canonical":
            self.canonical_url = attr.get("href") or None

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link:
            self.links.append((self._current_link, _clean_text(" ".join(self._link_text))))
            self._current_link = None
            self._link_text = []
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if current_tag == "title" and not self.title:
            self.title = text
        elif current_tag == "h1" and not self.h1:
            self.h1 = text
        elif current_tag in {"h2", "h3"}:
            self.headings[current_tag].append(text)
        elif self._current_link:
            self._link_text.append(text)
        if current_tag not in {"script", "style", "noscript"}:
            self._text_buffer.append(text)

    @property
    def visible_text(self) -> str:
        return " ".join(self._text_buffer)


class TopicDiscoveryCrawler:
    def __init__(
        self,
        repo_root: Path,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_pages_per_domain: int = DEFAULT_MAX_PAGES_PER_DOMAIN,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
    ) -> None:
        self.repo_root = repo_root
        self.max_depth = max_depth
        self.max_pages_per_domain = max_pages_per_domain
        self.delay_seconds = delay_seconds
        self.destinations = load_yaml(repo_root / "config" / "destinations.yaml")
        self.accessibility_topics = load_yaml(repo_root / "config" / "accessibility-topics.yaml")
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_request_at: dict[str, float] = defaultdict(float)

    def run(self, sources: list[SourceConfig], crawl: bool = True) -> dict[str, Any]:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_dir = self.repo_root / "data" / "raw" / "research"
        processed_dir = self.repo_root / "data" / "processed" / "research"
        output_dir = self.repo_root / "data" / "output" / "opportunities"
        raw_run_dir = raw_dir / "runs" / run_id
        processed_run_dir = processed_dir / "runs" / run_id
        output_run_dir = output_dir / "runs" / run_id
        for directory in [raw_dir, processed_dir, output_dir, raw_run_dir, processed_run_dir, output_run_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        pages: list[DiscoveredPage] = []
        source_statuses: list[dict[str, Any]] = []

        if crawl:
            for source in sources:
                source_pages, status = self._crawl_source(source)
                pages.extend(source_pages)
                source_statuses.append(status)
        else:
            source_statuses = [
                {"source": source.name, "status": "configured_not_crawled", "start_url": source.start_url}
                for source in sources
            ]

        self._write_json(raw_run_dir / "source-statuses.json", source_statuses)
        self._write_json(raw_run_dir / "source-pages-raw.json", [asdict(page) for page in pages])
        self._write_json(processed_run_dir / "source-pages.json", [asdict(page) for page in pages])
        self._write_outputs(output_run_dir, pages)

        self._write_json(raw_dir / "source-statuses.json", source_statuses)
        self._write_json(raw_dir / "source-pages-raw.json", [asdict(page) for page in pages])
        self._write_json(processed_dir / "source-pages.json", [asdict(page) for page in pages])
        self._write_outputs(output_dir, pages)
        return {
            "pages": pages,
            "source_statuses": source_statuses,
            "run_id": run_id,
            "raw_run_dir": raw_run_dir,
            "processed_run_dir": processed_run_dir,
            "output_run_dir": output_run_dir,
        }

    def _crawl_source(self, source: SourceConfig) -> tuple[list[DiscoveredPage], dict[str, Any]]:
        queue: deque[tuple[str, int, str | None]] = deque([(source.start_url, 0, None)])
        seen: set[str] = set()
        pages: list[DiscoveredPage] = []
        failures: list[dict[str, Any]] = []
        source_js_required = False

        while queue and len(seen) < self.max_pages_per_domain:
            url, depth, discovered_from = queue.popleft()
            normalised_url = canonicalize_url(url, source.base_url)
            if not normalised_url or normalised_url in seen:
                continue
            if not is_same_domain(normalised_url, source.base_url):
                continue
            if depth > self.max_depth or not is_close_to_research_area(normalised_url, source.start_url):
                continue
            seen.add(normalised_url)

            if not self._allowed_by_robots(normalised_url):
                failures.append({"url": normalised_url, "status": "blocked_by_robots"})
                continue

            fetch_result = self._fetch(normalised_url)
            if fetch_result.status != "ok" or not fetch_result.html:
                failures.append(asdict(fetch_result))
                if fetch_result.status == "javascript_required":
                    source_js_required = True
                continue

            parser = ResearchHTMLParser()
            parser.feed(fetch_result.html)
            if looks_javascript_required(fetch_result.html, parser.visible_text):
                failures.append({"url": normalised_url, "status": "javascript_required"})
                source_js_required = True
                continue

            page = self._normalise_page(source, normalised_url, parser, discovered_from, depth)
            if is_relevant_page(page, parser.visible_text):
                pages.append(page)

            if depth < self.max_depth:
                for href, link_text in parser.links:
                    next_url = canonicalize_url(href, normalised_url)
                    if (
                        next_url
                        and next_url not in seen
                        and is_same_domain(next_url, source.base_url)
                        and is_discovery_link(next_url, link_text)
                    ):
                        queue.append((next_url, depth + 1, normalised_url))

        status = "ok"
        if not pages and source_js_required:
            status = "javascript_required"
        elif not pages and failures:
            status = "no_relevant_pages_found"
        return pages, {
            "source": source.name,
            "status": status,
            "start_url": source.start_url,
            "pages_crawled": len(seen),
            "relevant_pages": len(pages),
            "failures": failures[:20],
        }

    def _normalise_page(
        self,
        source: SourceConfig,
        url: str,
        parser: ResearchHTMLParser,
        discovered_from: str | None,
        depth: int,
    ) -> DiscoveredPage:
        title = parser.title or parser.meta.get("og:title")
        h1 = parser.h1
        headings = {
            "h2": _unique(parser.headings["h2"]),
            "h3": _unique(parser.headings["h3"]),
        }
        metadata_text = " ".join(
            [
                url,
                title or "",
                h1 or "",
                " ".join(headings["h2"]),
                parser.meta.get("description", ""),
                parser.meta.get("og:description", ""),
            ]
        )
        destinations, countries = extract_destinations(metadata_text, self.destinations)
        accessibility = extract_accessibility_topics(metadata_text, self.accessibility_topics)
        travel_topics = extract_travel_topics(metadata_text)
        combos = build_topic_combinations(destinations, countries, accessibility, travel_topics)
        conversion = guess_conversion_relevance(destinations + countries, accessibility, travel_topics)
        return DiscoveredPage(
            source=source.name,
            source_type=source.source_type,
            url=url,
            canonical_url=canonicalize_url(parser.canonical_url, url) if parser.canonical_url else url,
            title=title,
            h1=h1,
            publication_date=find_date(parser.meta, "published"),
            updated_date=find_date(parser.meta, "modified"),
            author=parser.meta.get("author") or parser.meta.get("article:author"),
            headings=headings,
            summary=parser.meta.get("description") or parser.meta.get("og:description"),
            category=parser.meta.get("article:section"),
            tags=_split_keywords(parser.meta.get("keywords")),
            destination_mentions=destinations,
            country_mentions=countries,
            accessibility_topics=accessibility,
            travel_topics=travel_topics,
            topic_combinations=combos,
            content_type=infer_content_type(url, title or "", headings["h2"] + headings["h3"]),
            search_intent_guess=guess_search_intent(title or "", headings["h2"] + headings["h3"]),
            commercial_relevance=conversion,
            conversion_relevance=conversion,
            discovered_from=discovered_from,
            crawl_depth=depth,
            crawled_at=datetime.now(timezone.utc).isoformat(),
        )

    def _fetch(self, url: str) -> FetchResult:
        domain = parse.urlparse(url).netloc
        elapsed = time.monotonic() - self._last_request_at[domain]
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        req = request.Request(url, headers=headers)
        for attempt in range(2):
            try:
                with request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
                    content_type = response.headers.get("content-type", "")
                    status_code = getattr(response, "status", None)
                    if "text/html" not in content_type:
                        return FetchResult("non_html", url, status_code=status_code)
                    charset = response.headers.get_content_charset() or "utf-8"
                    html = response.read().decode(charset, errors="replace")
                    self._last_request_at[domain] = time.monotonic()
                    return FetchResult("ok", url, status_code=status_code, html=html)
            except HTTPError as exc:
                if exc.code in {408, 429, 500, 502, 503, 504} and attempt == 0:
                    time.sleep(self.delay_seconds)
                    continue
                return FetchResult("http_error", url, status_code=exc.code, error=str(exc))
            except URLError as exc:
                if attempt == 0:
                    time.sleep(self.delay_seconds)
                    continue
                return FetchResult("request_error", url, error=str(exc))
        return FetchResult("request_error", url, error="temporary failure after retry")

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if parsed.netloc not in self._robots:
            rp = robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                return True
            self._robots[parsed.netloc] = rp
        return self._robots[parsed.netloc].can_fetch(USER_AGENT, url)

    def _write_outputs(self, output_dir: Path, pages: list[DiscoveredPage]) -> None:
        self._write_source_pages_csv(output_dir / "source-pages.csv", pages)
        self._write_frequency_csv(
            output_dir / "destinations.csv",
            pages,
            "destination",
            lambda p: p.destination_mentions + p.country_mentions,
        )
        self._write_frequency_csv(
            output_dir / "accessibility-topics.csv",
            pages,
            "accessibility_topic",
            lambda p: p.accessibility_topics,
        )
        self._write_topic_combinations_csv(output_dir / "topic-combinations.csv", pages)

    def _write_source_pages_csv(self, path: Path, pages: list[DiscoveredPage]) -> None:
        columns = [
            "source",
            "url",
            "title",
            "publication_date",
            "destination",
            "country",
            "accessibility_topics",
            "travel_topics",
            "source_type",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for page in pages:
                writer.writerow(
                    {
                        "source": page.source,
                        "url": page.url,
                        "title": page.title,
                        "publication_date": page.publication_date,
                        "destination": "; ".join(page.destination_mentions),
                        "country": "; ".join(page.country_mentions),
                        "accessibility_topics": "; ".join(page.accessibility_topics),
                        "travel_topics": "; ".join(page.travel_topics),
                        "source_type": page.source_type,
                    }
                )

    def _write_frequency_csv(
        self,
        path: Path,
        pages: list[DiscoveredPage],
        label: str,
        values_for_page: Any,
    ) -> None:
        counter: Counter[str] = Counter()
        sources: dict[str, set[str]] = defaultdict(set)
        for page in pages:
            for value in values_for_page(page):
                counter[value] += 1
                sources[value].add(page.source)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[label, "occurrences", "unique_sources", "editorial_frequency", "search_demand"],
            )
            writer.writeheader()
            for value, occurrences in counter.most_common():
                writer.writerow(
                    {
                        label: value,
                        "occurrences": occurrences,
                        "unique_sources": len(sources[value]),
                        "editorial_frequency": occurrences,
                        "search_demand": None,
                    }
                )

    def _write_topic_combinations_csv(self, path: Path, pages: list[DiscoveredPage]) -> None:
        rows: dict[tuple[str, str | None, str | None, str | None], dict[str, Any]] = {}
        for page in pages:
            for combo in page.topic_combinations:
                key = (
                    combo["topic"] or "",
                    combo["destination"],
                    combo["accessibility_topic"],
                    combo["travel_topic"],
                )
                row = rows.setdefault(
                    key,
                    {
                        "topic": key[0],
                        "destination": key[1],
                        "accessibility_topic": key[2],
                        "travel_topic": key[3],
                        "occurrences": 0,
                        "sources": set(),
                        "conversion_relevance": page.conversion_relevance,
                    },
                )
                row["occurrences"] += 1
                row["sources"].add(page.source)
        with path.open("w", newline="", encoding="utf-8") as handle:
            columns = [
                "topic",
                "destination",
                "accessibility_topic",
                "travel_topic",
                "occurrences",
                "unique_sources",
                "editorial_frequency",
                "search_demand",
                "conversion_relevance",
            ]
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in sorted(rows.values(), key=lambda item: item["occurrences"], reverse=True):
                writer.writerow(
                    {
                        "topic": row["topic"],
                        "destination": row["destination"],
                        "accessibility_topic": row["accessibility_topic"],
                        "travel_topic": row["travel_topic"],
                        "occurrences": row["occurrences"],
                        "unique_sources": len(row["sources"]),
                        "editorial_frequency": row["occurrences"],
                        "search_demand": None,
                        "conversion_relevance": row["conversion_relevance"],
                    }
                )

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_sources(repo_root: Path) -> list[SourceConfig]:
    config = load_yaml(repo_root / "config" / "sources.yaml")
    return [SourceConfig(**item) for item in config.get("sources", [])]


def canonicalize_url(url: str | None, base_url: str) -> str | None:
    if not url:
        return None
    absolute = parse.urljoin(base_url, url)
    parsed = parse.urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    query = parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered_query = [
        (key, value)
        for key, value in query
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid", "print"}
    ]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return parse.urlunparse(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, "", parse.urlencode(filtered_query), "")
    )


def is_same_domain(url: str, base_url: str) -> bool:
    return parse.urlparse(url).netloc == parse.urlparse(base_url).netloc.lower()


def is_close_to_research_area(url: str, start_url: str) -> bool:
    path = parse.urlparse(url).path.lower()
    start_path = parse.urlparse(start_url).path.lower().rstrip("/")
    if start_path and path.startswith(start_path):
        return True
    return any(term in path for term in CANDIDATE_PATH_TERMS)


def is_discovery_link(url: str, link_text: str) -> bool:
    haystack = f"{url} {link_text}".lower()
    if any(skip in haystack for skip in ["privacy", "terms", "login", "account", "basket", "checkout"]):
        return False
    return any(term in haystack for term in CANDIDATE_PATH_TERMS + RELEVANCE_TERMS)


def is_relevant_page(page: DiscoveredPage, visible_text: str) -> bool:
    haystack = " ".join(
        [
            page.url,
            page.title or "",
            page.h1 or "",
            " ".join(page.headings["h2"]),
            " ".join(page.accessibility_topics),
            " ".join(page.travel_topics),
            visible_text[:1000],
        ]
    ).lower()
    has_travel = any(term in haystack for term in ["travel", "holiday", "destination", "hotel", "flight", "cruise"])
    has_accessibility = any(term in haystack for term in RELEVANCE_TERMS[:10])
    return has_travel and has_accessibility


def looks_javascript_required(html: str, visible_text: str) -> bool:
    html_lower = html[:5000].lower()
    text_length = len(visible_text.strip())
    marker_found = any(marker in html_lower for marker in JS_REQUIRED_MARKERS)
    return marker_found and text_length < 300


def find_date(meta: dict[str, str], date_kind: str) -> str | None:
    candidates = [
        value
        for key, value in meta.items()
        if date_kind in key or ("article:published_time" == key and date_kind == "published")
    ]
    return candidates[0] if candidates else None


def _split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    return [_clean_text(item) for item in value.split(",") if _clean_text(item)]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            unique_values.append(value)
    return unique_values


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover external accessible-travel topic inspiration.")
    parser.add_argument("--no-crawl", action="store_true", help="Write config/status files without HTTP crawling.")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--max-pages-per-domain", type=int, default=DEFAULT_MAX_PAGES_PER_DOMAIN)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sources = load_sources(repo_root)
    crawler = TopicDiscoveryCrawler(
        repo_root=repo_root,
        max_depth=args.max_depth,
        max_pages_per_domain=args.max_pages_per_domain,
        delay_seconds=args.delay_seconds,
    )
    result = crawler.run(sources, crawl=not args.no_crawl)
    print(f"Configured sources: {len(sources)}")
    print(f"Discovered relevant pages: {len(result['pages'])}")
    print(f"Run ID: {result['run_id']}")
    print(f"Raw run files: {result['raw_run_dir']}")
    print(f"Processed run files: {result['processed_run_dir']}")
    print(f"Opportunity CSV run files: {result['output_run_dir']}")
    print("Latest snapshots also written under data/raw/research, data/processed/research and data/output/opportunities")


if __name__ == "__main__":
    main()
