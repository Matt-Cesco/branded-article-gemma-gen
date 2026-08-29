"""Load research workflow configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML with PyYAML when available, falling back to a small subset parser."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded or {}
    except ModuleNotFoundError:
        return _load_simple_yaml(text)


def _load_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the limited YAML shape used by this project config."""
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    root: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(" ") or not line.endswith(":"):
            i += 1
            continue
        key = line[:-1]
        i += 1
        if i < len(lines) and lines[i].startswith("  - "):
            values: list[Any] = []
            while i < len(lines) and lines[i].startswith("  - "):
                item_text = lines[i][4:]
                if ": " in item_text:
                    item: dict[str, str] = {}
                    k, v = item_text.split(": ", 1)
                    item[k] = v
                    i += 1
                    while i < len(lines) and lines[i].startswith("    "):
                        child = lines[i].strip()
                        if ": " in child:
                            ck, cv = child.split(": ", 1)
                            item[ck] = cv
                        i += 1
                    values.append(item)
                else:
                    values.append(item_text)
                    i += 1
            root[key] = values
        else:
            children: dict[str, list[str]] = {}
            while i < len(lines) and lines[i].startswith("  "):
                child_key = lines[i].strip().rstrip(":")
                i += 1
                child_values: list[str] = []
                while i < len(lines) and lines[i].startswith("  - "):
                    child_values.append(lines[i][4:])
                    i += 1
                children[child_key] = child_values
            root[key] = children
    return root
