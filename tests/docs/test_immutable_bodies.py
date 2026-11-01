"""The doc-kitty frontmatter migration never changes an immutable body (#6929, FR-001).

ADRs, plans, reports, changelog entries and the archive are history: ADR
``2026-10-31-1`` D-7 allows a recorded, mechanical, frontmatter-only migration
of them and nothing else. This test runs the migration over every immutable file
in ``docs/`` and compares the SHA-256 of each file's body (everything after the
closing frontmatter fence) before and after.

Why in memory and not against a git base: a permanent comparison with a moving
base would fail every later, legitimate ADR amendment. The migration's own
``--verify-against <ref>`` mode proves a given diff is frontmatter-only; this test
proves the migration itself cannot touch a body, on the real corpus, on every run.

Non-vacuity: the corpus floor, a synthetic old-shape copy of a real ADR and a real
plan that the migration must rewrite, and a mutated body that must be caught.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

import pytest

from scripts.docs._dockitty_contract import body_of, is_immutable
from scripts.docs.dockitty_frontmatter_migration import Corpus, migrate_text

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_DOCS_ROOT: Final[Path] = _REPO_ROOT / "docs"
#: About 700 immutable files exist today (228 ADRs, plans, reports, changelog, archive).
_MIN_IMMUTABLE_FILES: Final[int] = 400


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _immutable_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(_DOCS_ROOT.rglob("*.md")):
        rel = path.relative_to(_DOCS_ROOT).as_posix()
        if is_immutable(rel):
            files.append((rel, path))
    return files


def assert_body_preserved(rel: str, before: str, after: str) -> None:
    """Raise ``AssertionError`` naming *rel* when the bodies of *before* and *after* differ."""
    if _sha(body_of(before)) != _sha(body_of(after)):
        raise AssertionError(f"{rel}: body changed by the migration")


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus.load(docs_root=_DOCS_ROOT, repo_root=_REPO_ROOT)


def test_migration_preserves_every_immutable_body(corpus: Corpus) -> None:
    files = _immutable_files()
    assert len(files) >= _MIN_IMMUTABLE_FILES, f"non-vacuity: only {len(files)} immutable files found under {_DOCS_ROOT}"
    offenders: list[str] = []
    for rel, path in files:
        before = path.read_text(encoding="utf-8")
        after = migrate_text(rel, before, corpus)
        try:
            assert_body_preserved(rel, before, after)
        except AssertionError as exc:
            offenders.append(str(exc))
    assert offenders == [], "\n".join(offenders)


def _real_body(rel: str) -> str:
    return body_of((_DOCS_ROOT / rel).read_text(encoding="utf-8"))


def _first_immutable(prefix: str) -> str:
    return next(rel for rel, _ in _immutable_files() if rel.startswith(prefix))


def test_migration_rewrites_old_shape_frontmatter_on_real_bodies(corpus: Corpus) -> None:
    """Positive control: the body check above runs over files the migration really rewrites."""
    adr = _first_immutable("adr/4.x/2026-")
    old_adr = "---\ntitle: 'ADR: x'\nstatus: Accepted\ndate: '2026-10-01'\n---\n" + _real_body(adr)
    migrated_adr = migrate_text(adr, old_adr, corpus)
    assert "doc_status: active" in migrated_adr
    assert "kind: ADR" in migrated_adr
    assert_body_preserved(adr, old_adr, migrated_adr)

    plan = _first_immutable("plans/")
    old_plan = (
        "---\ntitle: x\ndescription: y\ndoc_status: active\n"
        "audience: docs/context/audience/internal/maintainer.md\n"
        "related:\n- docs/context/charter.md\n- pyproject.toml\n---\n" + _real_body(plan)
    )
    migrated_plan = migrate_text(plan, old_plan, corpus)
    assert "profile: internal/maintainer" in migrated_plan
    assert "- context/charter" in migrated_plan
    assert "external_references:" in migrated_plan
    assert_body_preserved(plan, old_plan, migrated_plan)


def test_a_changed_body_is_caught() -> None:
    """Negative control: one appended character in a body fails the check and names the file."""
    before = "---\ntitle: x\n---\n# Body\n"
    with pytest.raises(AssertionError, match="adr/4.x/example.md"):
        assert_body_preserved("adr/4.x/example.md", before, before + "!")
