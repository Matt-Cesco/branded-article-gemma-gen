"""Read mandatory Limitless Travel content guidelines."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass


@dataclass
class GuidelineBundle:
    text: str
    filenames: list[str]
    character_count: int
    approximate_tokens: int


class GuidelineService:
    def __init__(self, repo_root: Path) -> None:
        self.guidelines_dir = repo_root / "content-guidelines"

    def load_all_guidelines(self) -> str:
        return self.load_guideline_bundle().text

    def load_guideline_bundle(self) -> GuidelineBundle:
        parts: list[str] = []
        filenames: list[str] = []
        for path in sorted(self.guidelines_dir.glob("*.md"), key=lambda item: item.name):
            filenames.append(path.name)
            parts.append(f"# {path.name}\n\n{path.read_text(encoding='utf-8')}")
        text = "\n\n---\n\n".join(parts)
        return GuidelineBundle(
            text=text,
            filenames=filenames,
            character_count=len(text),
            approximate_tokens=max(1, len(text) // 4) if text else 0,
        )

    def load_guideline(self, filename: str) -> str:
        if Path(filename).name != filename:
            raise ValueError("Guideline filenames must not include paths.")
        path = self.guidelines_dir / filename
        resolved = path.resolve()
        if self.guidelines_dir.resolve() not in resolved.parents:
            raise ValueError("Guideline path is outside content-guidelines.")
        return path.read_text(encoding="utf-8")
