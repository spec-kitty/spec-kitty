"""The corpus gate: the published tree satisfies the frontmatter contract (#6931).

``python -m scripts.docs.frontmatter_contract --strict`` over the real ``docs/`` tree
is the check ADR 2026-10-31-1 D-7 asks for and that this repository can run today:
doc-kitty's own ``dockitty-validate-frontmatter`` needs ``site/`` (#6930), which does
not exist on ``main``. This suite proves three things about that gate:

1. **It is green on the migrated corpus** — 0 errors, 0 warnings, every published
   page carrying a canonical ``kind``.
2. **It can fail.** A gate that cannot fail is decoration: a mutated fixture page
   missing ``kind`` must red, and an unclassifiable page must be a migration failure
   rather than a guessed kind.
3. **It fails closed on a collapsed page set** — a docs tree below the non-vacuity
   floor exits ``2`` rather than reporting a clean pass over nothing.

Point 2 is why the fixture lives in ``tmp_path``: it mutates a copy, never ``docs/``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.docs._published_pages import MINIMUM_EXPECTED_PAGES
from scripts.docs.frontmatter_contract import (
    EXIT_COVERAGE_FAILURE,
    KINDS,
    CoverageError,
    main,
    validate_tree,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the gate as the CLI a maintainer (and CI) would run."""
    return subprocess.run(
        [sys.executable, "-m", "scripts.docs.frontmatter_contract", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_published_corpus_satisfies_the_contract() -> None:
    """0 errors and 0 warnings over the whole published tree (SC-001)."""
    report = validate_tree(docs_root=_DOCS_ROOT, repo_root=_REPO_ROOT)
    assert report.errors == (), [v.as_dict() for v in report.errors[:10]]
    assert report.warnings == (), [v.as_dict() for v in report.warnings[:10]]


def test_the_gate_is_not_vacuous() -> None:
    """It checks the whole published tree, not a handful of pages."""
    report = validate_tree(docs_root=_DOCS_ROOT, repo_root=_REPO_ROOT)
    assert report.checked_count >= MINIMUM_EXPECTED_PAGES, (
        f"the gate checked only {report.checked_count} pages, below the "
        f"{MINIMUM_EXPECTED_PAGES} floor"
    )


def test_every_published_page_carries_a_canonical_kind() -> None:
    """ADR D-7: "any page left unclassified is a migration failure"."""
    from scripts.docs._inventory import parse_frontmatter
    from scripts.docs._published_pages import resolve_published_pages

    page_set = resolve_published_pages(docs_root=_DOCS_ROOT)
    missing: list[str] = []
    off_set: list[str] = []
    for page in sorted(page_set.pages):
        frontmatter = parse_frontmatter((_DOCS_ROOT.parent / page).read_text(encoding="utf-8"))
        kind = frontmatter.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            missing.append(page.as_posix())
        elif kind not in KINDS:
            off_set.append(f"{page.as_posix()}: {kind}")
    assert missing == [], f"pages without a kind: {missing[:10]}"
    assert off_set == [], f"pages whose kind is outside the canonical set: {off_set[:10]}"


def test_the_cli_exits_zero_on_the_real_tree() -> None:
    """``--strict`` is the CI shape, and it is green today."""
    result = _run_cli("--strict", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error_count"] == 0
    assert payload["warning_count"] == 0
    assert payload["checked_count"] >= MINIMUM_EXPECTED_PAGES


def _copy_published_tree(tmp_path: Path) -> Path:
    """Copy ``docs/`` and the one config the publication authority reads."""
    docs_copy = tmp_path / "docs"
    shutil.copytree(_DOCS_ROOT, docs_copy)
    return docs_copy


def test_a_page_missing_kind_turns_the_gate_red(tmp_path: Path) -> None:
    """The gate can fail: a required field removed from a real page reds it (SC-004)."""
    docs_copy = _copy_published_tree(tmp_path)
    victim = docs_copy / "guides" / "tutorials" / "your-first-mission.md"
    text = victim.read_text(encoding="utf-8")
    stripped = "\n".join(line for line in text.splitlines() if not line.startswith("kind:")) + "\n"
    victim.write_text(stripped, encoding="utf-8")

    report = validate_tree(docs_root=docs_copy, repo_root=tmp_path)
    planted = [
        (v.path, v.field, v.reason)
        for v in report.errors
        if v.path == "docs/guides/tutorials/your-first-mission.md"
    ]
    assert ("docs/guides/tutorials/your-first-mission.md", "kind", "required") in [
        (path, field, reason) for path, field, reason in planted
    ]
    # The rest of the corpus stays clean: one planted defect, one report.
    assert len(report.errors) == 1, [v.as_dict() for v in report.errors]

    exit_code = main(["--docs-root", str(docs_copy), "--repo-root", str(tmp_path), "--strict"])
    assert exit_code == 1


def test_a_collapsed_page_set_fails_closed(tmp_path: Path) -> None:
    """A docs tree under the non-vacuity floor exits 2, never a clean pass (NFR-001)."""
    docs_copy = tmp_path / "docs"
    (docs_copy / "guides").mkdir(parents=True)
    (docs_copy / "guides" / "only.md").write_text("---\ntitle: t\n---\nbody\n", encoding="utf-8")
    (docs_copy / "docfx.json").write_text(
        json.dumps({"build": {"content": [{"files": ["guides/**.md"]}]}}), encoding="utf-8"
    )

    result = _run_cli("--docs-root", str(docs_copy), "--repo-root", str(tmp_path), "--strict")
    assert result.returncode == EXIT_COVERAGE_FAILURE
    assert "COVERAGE FAILURE" in result.stderr

    with pytest.raises(CoverageError):
        validate_tree(docs_root=docs_copy, repo_root=tmp_path)


def test_an_unreadable_publication_declaration_fails_closed(tmp_path: Path) -> None:
    """No ``docfx.json`` means no authority: exit 2, not "assume everything"."""
    docs_copy = tmp_path / "docs"
    docs_copy.mkdir()
    (docs_copy / "page.md").write_text("---\ntitle: t\n---\nbody\n", encoding="utf-8")

    result = _run_cli("--docs-root", str(docs_copy), "--repo-root", str(tmp_path), "--strict")
    assert result.returncode == EXIT_COVERAGE_FAILURE
    assert "COVERAGE FAILURE" in result.stderr
