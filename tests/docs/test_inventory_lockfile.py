"""Linchpin self-test for the frontmatter -> inventory lockfile generator.

The whole SSOT thesis (ADR ``2026-06-27-1`` decision D1) is only credible if
the generator genuinely *reads frontmatter*. The fakeable trap the reviewer
calls out: a no-op/echo generator that copies ``committed -> generated`` would
satisfy ``generated == committed`` forever while reading nothing. These tests
make that impossible:

* :func:`test_frontmatter_mutation_changes_generation_and_reds_drift` mutates a
  single *in-rollup* frontmatter field and asserts both that the regenerated
  output **changes** and that the returned drift object is non-empty
  (``has_drift is True``). "RED" here is the **returned drift object**, not an
  exit code — the tool stays exit-0 report-only.
* :func:`test_lockfile_only_handedit_is_rejected` hand-edits the committed
  lockfile alone (frontmatter untouched) and asserts the same drift signal
  flips to rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.docs import check_docs_freshness as orchestrator
from scripts.docs import inventory_lockfile as lockfile
from scripts.docs._inventory import (
    DivioType,
    PageInventoryEntry,
    VersionTag,
    load_inventory,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.architectural

PAGE_WITH_FRONTMATTER = (
    "---\ntitle: Getting Started\ndescription: A how-to page.\ntype: how-to\nversion_tag: current\nowning_workstream: E\n---\n\n# Getting Started\n"
)

PAGE_PLAIN = "# No frontmatter here\n\nJust prose.\n"


def _seed_docs_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Stage a small ``docs/`` tree; return (repo_root, docs_root)."""
    repo_root = tmp_path
    docs_root = repo_root / "docs"
    (docs_root / "guides").mkdir(parents=True)
    (docs_root / "guides" / "getting-started.md").write_text(PAGE_WITH_FRONTMATTER, encoding="utf-8")
    (docs_root / "index.md").write_text(PAGE_PLAIN, encoding="utf-8")
    return repo_root, docs_root


# ---------------------------------------------------------------------------
# (a) frontmatter mutation must change the generation AND red the drift
# ---------------------------------------------------------------------------


def test_frontmatter_mutation_changes_generation_and_reds_drift(
    tmp_path: Path,
) -> None:
    """Mutating one in-rollup frontmatter field changes the rollup and reds drift.

    This is the anti-fakeability linchpin: a no-op/echo generator that ignores
    frontmatter would leave ``before == after`` and ``has_drift is False``.
    """
    repo_root, docs_root = _seed_docs_tree(tmp_path)

    before_entries = lockfile.generate_inventory(docs_root, repo_root=repo_root)
    before_render = lockfile.render_lockfile(before_entries)

    # Commit the pre-mutation generation as the lockfile baseline.
    committed = list(before_entries)

    # Mutate exactly one in-rollup frontmatter field on one page.
    page = docs_root / "guides" / "getting-started.md"
    page.write_text(
        PAGE_WITH_FRONTMATTER.replace("type: how-to", "type: reference"),
        encoding="utf-8",
    )

    after_entries = lockfile.generate_inventory(docs_root, repo_root=repo_root)
    after_render = lockfile.render_lockfile(after_entries)

    # 1) The generated output actually changed — kills any echo/no-op generator.
    assert before_render != after_render

    # 2) The returned drift object is the RED signal (NOT an exit code).
    drift = lockfile.compare_inventories(after_entries, committed)
    assert drift.has_drift is True
    assert "docs/guides/getting-started.md" in drift.changed
    assert drift.added == ()
    assert drift.removed == ()


def test_report_only_stays_exit_zero_under_drift(tmp_path: Path) -> None:
    """Drift is reported but the process exit stays 0 in report-only mode."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    # Committed lockfile generated, then frontmatter diverges.
    committed_path = repo_root / "inventory.yaml"
    committed_path.write_text(
        lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root)),
        encoding="utf-8",
    )
    (docs_root / "guides" / "getting-started.md").write_text(
        PAGE_WITH_FRONTMATTER.replace("type: how-to", "type: explanation"),
        encoding="utf-8",
    )
    report = lockfile.run_generate_and_compare(
        docs_root=docs_root,
        inventory=committed_path,
        repo_root=repo_root,
        strict=False,
    )
    assert report.drift.has_drift is True
    assert report.exit_code == 0  # report-only


def test_strict_flag_flips_drift_to_nonzero_exit(tmp_path: Path) -> None:
    """The wired-but-off --strict flag makes drift a non-zero exit."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    committed_path = repo_root / "inventory.yaml"
    committed_path.write_text(
        lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root)),
        encoding="utf-8",
    )
    (docs_root / "guides" / "getting-started.md").write_text(
        PAGE_WITH_FRONTMATTER.replace("type: how-to", "type: explanation"),
        encoding="utf-8",
    )
    report = lockfile.run_generate_and_compare(
        docs_root=docs_root,
        inventory=committed_path,
        repo_root=repo_root,
        strict=True,
    )
    assert report.drift.has_drift is True
    assert report.exit_code == 1


# ---------------------------------------------------------------------------
# (b) a lockfile-only hand-edit (frontmatter untouched) is rejected
# ---------------------------------------------------------------------------


def test_lockfile_only_handedit_is_rejected(tmp_path: Path) -> None:
    """Hand-editing the committed lockfile alone reds the drift signal."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)

    # Fresh generation is the source of truth; frontmatter is left untouched.
    generated = lockfile.generate_inventory(docs_root, repo_root=repo_root)

    # Tamper with the committed rollup directly: flip one row's divio_type.
    committed = [
        PageInventoryEntry(
            path=entry.path,
            tag=entry.tag,
            divio_type=(DivioType.TUTORIAL if entry.path == "docs/guides/getting-started.md" else entry.divio_type),
            owning_workstream=entry.owning_workstream,
            current_target=entry.current_target,
            notes=entry.notes,
        )
        for entry in generated
    ]

    drift = lockfile.compare_inventories(generated, committed)
    assert drift.has_drift is True
    assert "docs/guides/getting-started.md" in drift.changed


# ---------------------------------------------------------------------------
# Determinism + schema invariants
# ---------------------------------------------------------------------------


def test_generation_is_byte_stable_on_rerun(tmp_path: Path) -> None:
    """Re-running the generator over an unchanged tree is byte-identical."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    first = lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root))
    second = lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root))
    assert first == second


def test_no_drift_when_committed_matches_generation(tmp_path: Path) -> None:
    """A committed lockfile equal to a fresh generation has no drift."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    generated = lockfile.generate_inventory(docs_root, repo_root=repo_root)
    drift = lockfile.compare_inventories(generated, list(generated))
    assert drift.has_drift is False


def test_rendered_lockfile_drops_citation_refs(tmp_path: Path) -> None:
    """The rollup omits the retired ``citation_refs`` field (decision D1)."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    rendered = lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root))
    # The retired field is never emitted as a row key (the header comment may
    # still reference it by name when explaining the retirement).
    assert "  citation_refs:" not in rendered


def test_rendered_lockfile_roundtrips_through_load_inventory(tmp_path: Path) -> None:
    """The generated lockfile is loadable by the canonical loader."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    rendered = lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root))
    out = repo_root / "generated.yaml"
    out.write_text(rendered, encoding="utf-8")
    reloaded = load_inventory(out)
    assert {entry.path for entry in reloaded} == {
        "docs/guides/getting-started.md",
        "docs/index.md",
    }


def test_frontmatter_maps_type_and_version_tag(tmp_path: Path) -> None:
    """Frontmatter ``type`` -> divio_type and ``version_tag`` -> tag."""
    entry = lockfile.entry_for_page(
        "docs/x.md",
        lockfile.parse_frontmatter(PAGE_WITH_FRONTMATTER),
    )
    assert entry.divio_type is DivioType.HOW_TO
    assert entry.tag is VersionTag.CURRENT
    assert entry.current_target is True
    assert entry.owning_workstream == "E"


def test_plain_page_defaults_to_current_none(tmp_path: Path) -> None:
    """A page without frontmatter falls back to current/none (report-only)."""
    entry = lockfile.entry_for_page("docs/x.md", lockfile.parse_frontmatter(PAGE_PLAIN))
    assert entry.tag is VersionTag.CURRENT
    assert entry.divio_type is DivioType.NONE
    assert entry.owning_workstream == "none"
    assert entry.notes is None


def test_parse_frontmatter_handles_missing_and_unclosed(tmp_path: Path) -> None:
    """Malformed / absent frontmatter yields an empty mapping, never raises."""
    assert lockfile.parse_frontmatter("no fence\n") == {}
    assert lockfile.parse_frontmatter("---\ntype: how-to\nunclosed") == {}
    assert lockfile.parse_frontmatter("---\n: : bad yaml : :\n---\n") == {}


def test_cli_report_only_exit_zero_and_writes_report(tmp_path: Path) -> None:
    """The CLI runs report-only (exit 0) and writes a JSON drift report."""
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    committed_path = repo_root / "inventory.yaml"
    committed_path.write_text(
        lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root)),
        encoding="utf-8",
    )
    (docs_root / "guides" / "getting-started.md").write_text(
        PAGE_WITH_FRONTMATTER.replace("type: how-to", "type: reference"),
        encoding="utf-8",
    )
    report_path = repo_root / "drift.json"
    rc = lockfile.main(
        [
            "--docs-root",
            str(docs_root),
            "--inventory",
            str(committed_path),
            "--repo-root",
            str(repo_root),
            "--report",
            str(report_path),
        ]
    )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["has_drift"] is True
    assert payload["exit_code"] == 0


# ---------------------------------------------------------------------------
# Orchestrator integration (blocking sub-check, default-on — Mission B / WP14)
# ---------------------------------------------------------------------------


def test_orchestrator_lockfile_subcheck_emits_blocking_errors(tmp_path: Path) -> None:
    """The inverted ruler emits INVENTORY-LOCKFILE-DRIFT *errors* (WP14 flip).

    Mission B makes the lockfile gate blocking: every drift finding is now
    ``error`` severity so the aggregate ``check_docs_freshness`` exit reds on
    drift (it keys off ``any(f.severity == "error")``).
    """
    repo_root, docs_root = _seed_docs_tree(tmp_path)
    committed_path = repo_root / "inventory.yaml"
    committed_path.write_text(
        lockfile.render_lockfile(lockfile.generate_inventory(docs_root, repo_root=repo_root)),
        encoding="utf-8",
    )
    # Diverge frontmatter so the regeneration drifts from the committed rollup.
    (docs_root / "guides" / "getting-started.md").write_text(
        PAGE_WITH_FRONTMATTER.replace("type: how-to", "type: reference"),
        encoding="utf-8",
    )
    findings = orchestrator._check_inventory_lockfile_drift(committed_path, docs_root)
    assert findings, "expected drift findings"
    assert all(f.rule_id == "INVENTORY-LOCKFILE-DRIFT" for f in findings)
    assert all(f.severity == "error" for f in findings)


def test_orchestrator_lockfile_subcheck_skips_missing_docs_root(
    tmp_path: Path,
) -> None:
    """The sub-check is a no-op when the docs root is absent."""
    findings = orchestrator._check_inventory_lockfile_drift(tmp_path / "inventory.yaml", tmp_path / "does-not-exist")
    assert findings == []
