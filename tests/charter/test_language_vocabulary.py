"""Tests for the doctrine-derived scoped-language vocabulary (WP03, FR-017, C-001)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


def _write_artifact(root: Path, subdir: str, name: str, languages: str, *, kind: str = "") -> None:
    directory = root / subdir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.{kind or subdir}.yaml").write_text(
        f"id: {name}\napplies_to_languages: {languages}\n",
        encoding="utf-8",
    )


def _vocabulary(repo_root: Path | None) -> frozenset[str]:
    from charter.activation.language_vocabulary import scoped_language_vocabulary

    return scoped_language_vocabulary(repo_root)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    try:
        from charter.activation.language_vocabulary import scoped_language_vocabulary
    except ImportError:
        return
    scoped_language_vocabulary.cache_clear()


def test_shipped_packs_contribute_python_and_no_reserved_or_sentinel_tokens() -> None:
    """RED (pins the fix): shipped scopes are read from packs; reserved/sentinel tokens never appear."""
    vocabulary = _vocabulary(None)

    assert "python" in vocabulary
    assert not vocabulary & {"any", "all", "unknown"}


def test_project_overlay_contributes_its_scope(tmp_path: Path) -> None:
    """RED (pins the fix): a project-overlay artifact scoped to ``elixir`` extends the vocabulary."""
    _write_artifact(tmp_path / ".kittify" / "charter-packs", "tactic", "elixir-thing", "[elixir]")

    assert "elixir" in _vocabulary(tmp_path)
    assert "elixir" not in _vocabulary(None)


def test_overlay_reserved_and_sentinel_scopes_contribute_nothing(tmp_path: Path) -> None:
    """RED (pins the fix): ``[unknown]`` / ``[any]`` scopes are not vocabulary."""
    doctrine = tmp_path / ".kittify" / "charter-packs"
    _write_artifact(doctrine, "tactic", "reserved-one", "[unknown]")
    _write_artifact(doctrine, "styleguide", "sentinel-one", "[any, ALL]")

    assert _vocabulary(tmp_path) == _vocabulary(None)


def test_org_pack_root_contributes_its_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED (pins the fix): configured org pack roots are scanned (tactics/<kind> layout)."""
    org_root = tmp_path / "org"
    _write_artifact(org_root, "tactics", "gleam-thing", "[gleam]", kind="tactic")
    from charter.activation import language_vocabulary

    monkeypatch.setattr(language_vocabulary, "resolve_pack_chain", lambda _repo_root, *, strict: [org_root])

    assert "gleam" in _vocabulary(tmp_path)


def test_repo_root_doctrine_dir_is_not_a_project_layer(tmp_path: Path) -> None:
    """The project layer follows ``resolve_project_root``; the retired repo-root ``doctrine/`` is no candidate (FR-011)."""
    _write_artifact(tmp_path / "doctrine", "tactic", "elixir-thing", "[elixir]")

    assert "elixir" not in _vocabulary(tmp_path)


def test_kittify_doctrine_wins_over_flat_doctrine_like_the_service(tmp_path: Path) -> None:
    """GREEN control: the project pack root is the project layer, as for the service."""
    _write_artifact(tmp_path / ".kittify" / "charter-packs", "tactic", "gleam-thing", "[gleam]")
    _write_artifact(tmp_path / "doctrine", "tactic", "elixir-thing", "[elixir]")

    vocabulary = _vocabulary(tmp_path)

    assert "gleam" in vocabulary
    assert "elixir" not in vocabulary


def test_non_string_and_non_word_scope_items_contribute_nothing(tmp_path: Path) -> None:
    """RED (pins F3b): ``[null, 3]`` and non-word strings are not language tokens."""
    _write_artifact(tmp_path / ".kittify" / "charter-packs", "tactic", "junk-scope", "[null, 3, 'a b', '']")

    assert _vocabulary(tmp_path) == _vocabulary(None)


def test_vocabulary_cache_is_bounded() -> None:
    """RED (pins F3c): the per-root memo is an LRU of bounded size, not an unbounded cache."""
    from charter.activation.language_vocabulary import scoped_language_vocabulary

    assert scoped_language_vocabulary.cache_info().maxsize == 8


def test_malformed_and_non_mapping_yaml_is_ignored(tmp_path: Path) -> None:
    """RED (pins the fix): unreadable scope fields degrade to no contribution, never raise."""
    doctrine = tmp_path / ".kittify" / "charter-packs" / "tactic"
    doctrine.mkdir(parents=True)
    (doctrine / "bad.tactic.yaml").write_text("applies_to_languages: [unterminated\n", encoding="utf-8")
    (doctrine / "list.tactic.yaml").write_text("- applies_to_languages\n", encoding="utf-8")
    (doctrine / "scalar.tactic.yaml").write_text("applies_to_languages: rust\n", encoding="utf-8")

    assert _vocabulary(tmp_path) == _vocabulary(None)


def test_vocabulary_is_memoized_and_cache_clear_resets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """RED (pins the fix): the scan runs once per root until ``cache_clear()``."""
    from charter.activation import language_vocabulary

    calls: list[Path] = []
    real = language_vocabulary._scoped_tokens_in_dir

    def counting(directory: Path, pattern: str) -> set[str]:
        calls.append(directory)
        return real(directory, pattern)

    monkeypatch.setattr(language_vocabulary, "_scoped_tokens_in_dir", counting)

    first = language_vocabulary.scoped_language_vocabulary(tmp_path)
    scans = len(calls)
    assert scans > 0
    assert language_vocabulary.scoped_language_vocabulary(tmp_path) == first
    assert len(calls) == scans

    language_vocabulary.scoped_language_vocabulary.cache_clear()
    language_vocabulary.scoped_language_vocabulary(tmp_path)
    assert len(calls) == 2 * scans


def test_importing_vocabulary_does_not_import_language_scope() -> None:
    """RED (pins the fix): no import cycle seam — the provider never reaches ``language_scope``."""
    import charter

    src_root = Path(charter.__file__).resolve().parents[1]
    code = "import sys; import charter.activation.language_vocabulary; sys.exit(1 if 'charter.activation.language_scope' in sys.modules else 0)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={"PYTHONPATH": str(src_root), "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
