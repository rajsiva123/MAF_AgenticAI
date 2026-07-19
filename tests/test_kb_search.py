"""Tests for KB keyword matching behavior."""

from pathlib import Path

from tools.kb_search import KBSearch


def test_kb_search_returns_ranked_results(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "a.md").write_text("vpn login reset password", encoding="utf-8")
    (kb_dir / "b.md").write_text("vpn troubleshooting", encoding="utf-8")

    results = KBSearch(str(kb_dir)).search("vpn password")

    assert results[0].source == "a.md"
    assert results[0].match_count >= results[1].match_count


def test_kb_search_handles_empty_query(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "a.md").write_text("content", encoding="utf-8")

    assert KBSearch(str(kb_dir)).search("") == []
