"""Simple local KB search utility for resolver agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class KBResult:
    """Represents a retrieved KB article."""

    source: str
    match_count: int
    content: str


class KBSearch:
    """Naive keyword-overlap retrieval over markdown files."""

    def __init__(self, kb_path: str) -> None:
        self._kb_path = Path(kb_path)

    def search(self, query: str, top_k: int = 2) -> list[KBResult]:
        """Return top matching KB results for a query."""

        terms = {t.lower() for t in query.split() if t.strip()}
        results: list[KBResult] = []
        for file_path in self._kb_path.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            haystack = content.lower()
            score = sum(1 for term in terms if term in haystack)
            if score > 0:
                results.append(KBResult(source=file_path.name, match_count=score, content=content))

        return sorted(results, key=lambda item: item.match_count, reverse=True)[:top_k]
