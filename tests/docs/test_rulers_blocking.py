"""Ruler-blocking regression gate (WP14 / FR-011, C-005, NFR-006, SC-005).

Mission B flips Mission A's report-only docs rulers to **blocking**. This module
is the per-class RED proof: for every violation class the gate must go RED
**independently**, exercised through the **same CLI invocation path the wired
``.github/workflows/docs-freshness.yml`` uses** — a script-level RED the CI
wiring never calls is the gate-silent-death failure mode (WP14 DoD).

The non-uniform flip:

* **R2 related-validator** flips via its wired ``--strict`` flag (the workflow
  passes it) and reds on its own seeded dangling-edge violation. (The R1
  anti-sprawl structure ratchet was retired — #2851 follow-up — so its
  per-class RED proofs are gone; the structure policy is now curated in bulk.)
* **R3 lockfile drift** is reported but no longer blocks: the
  ``INVENTORY-LOCKFILE-DRIFT`` finding runs default-on at ``warning`` severity,
  because the page inventory is regenerated on ``main`` after merge by the
  ``ci/regen-docs-index`` bot pull request, so a branch is expected to lag it
  (the content check is ``test_docs_index_regenerates_cleanly.py``). The
  ``severity == "warning"`` + ``rc == 0`` assertions pin that demotion.
* The **body-link gate** (WP18) is wired blocking too; it reds on its seeded
  violation. (The description gate retired with the legacy site build, #6943.)

Each clean-tree counterpart asserts the gate is **green** on a correct tree, so
the RED is attributable to the seeded violation and not a perpetually-red gate.

**Diff-scope proof (#3147, WP02 T012).** The bottom section preserves the
original diff-scoped ``--changed-from`` proof for R2 (related-validator) and
the body-link gate through the SAME CLI path ``docs-freshness.yml`` invokes on
``pull_request``, over real (throwaway) git repos. The sibling audience gate
added to that wiring by #3316 carries the same four-case proof in
``test_audience_resolves.py``.
Per B-WP02 in
``kitty-specs/ci-scoping-gate-reliability-01KZP80D/investigate-squad-findings.md``
this is a **four**-case proof, not three — the fourth (resolved-zero-docs) is
the load-bearing distinction the naive "empty changed-set -> ERROR" reading
would get wrong:

(a) a seeded violation IN the changed-set still reds (the check BITES);
(b) a pre-existing violation OUTSIDE the changed-set does NOT red (exit 0);
(c) an unresolvable/unfetched base ref errors (non-zero, distinct from both);
(d) a resolved diff touching zero in-scope docs files (the common shape for a
    non-docs-md PR, since ``docs-freshness.yml`` also triggers on
    ``src/specify_cli/**``, ``pyproject.toml``, etc.) exits 0 — NOT an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from scripts.docs import check_docs_freshness as orchestrator
from scripts.docs import related_validator
from scripts.docs import relative_link_fixer
from tests.docs.conftest import (
    commit_all_changes,
    init_git_repo_with_base,
)

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.architectural


def _write(path: Path, text: str = "# stub\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# R2 — related-validator: a dangling related: edge reds under --strict
# --------------------------------------------------------------------------- #


def test_r2_clean_tree_is_green_under_strict(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "docs" / "index.md")
    _write(root / "docs" / "target.md")
    _write(
        root / "docs" / "a.md",
        "---\nrelated:\n- target\n---\n# A\n",
    )
    assert related_validator.main(["--docs-root", str(root / "docs"), "--repo-root", str(root), "--strict"]) == 0


def test_r2_dangling_related_edge_reds(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "docs" / "index.md")
    _write(
        root / "docs" / "a.md",
        "---\nrelated:\n- does-not-exist\n---\n# A\n",
    )
    assert related_validator.main(["--docs-root", str(root / "docs"), "--repo-root", str(root), "--strict"]) == 1


# --------------------------------------------------------------------------- #
# R3 — lockfile drift: error severity reds the orchestrator (the wired path)
# --------------------------------------------------------------------------- #


def _stub_external_subchecks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub leakage + CLI-reference sub-checks to clean so R3 is the only signal."""

    def _clean_leakage(argv: list[str]) -> int:
        Path(argv[argv.index("--report") + 1]).write_text(
            json.dumps({"inventory_rows_count": 0, "findings": [], "exit_code": 0}),
            encoding="utf-8",
        )
        return 0

    def _clean_ref(argv: list[str]) -> int:
        Path(argv[argv.index("--report") + 1]).write_text(json.dumps({"findings": []}), encoding="utf-8")
        return 0

    monkeypatch.setattr(orchestrator, "_invoke_version_leakage", _clean_leakage)
    monkeypatch.setattr(orchestrator, "_invoke_cli_reference_freshness", _clean_ref)


def _stage_lockfile_workspace(root: Path, *, drift: bool) -> Path:
    """Stage docs/ + an inventory lockfile; when ``drift`` the two disagree."""
    from scripts.docs import inventory_lockfile as lockfile

    docs = root / "docs"
    _write(docs / "index.md", "---\nkind: How-To\n---\n# Home\n")
    _write(docs / "guides" / "g.md", "---\nkind: How-To\n---\n# Guide\n")
    inventory = root / "inventory.yaml"
    inventory.write_text(
        lockfile.render_lockfile(lockfile.generate_inventory(docs, repo_root=root)),
        encoding="utf-8",
    )
    if drift:
        # Tamper a page's frontmatter so the regeneration != committed lockfile.
        (docs / "guides" / "g.md").write_text("---\nkind: Reference\n---\n# Guide\n", encoding="utf-8")
    return root


def test_r3_clean_lockfile_is_green(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _stage_lockfile_workspace(tmp_path / "repo", drift=False)
    _stub_external_subchecks(monkeypatch)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    (root / "ref.md").write_text("# ref\n", encoding="utf-8")
    (root / "agent.md").write_text("# agent\n", encoding="utf-8")
    # Run from the repo root with relative paths, exactly as the CI workflow does
    # (the inventory rows are repo-relative, e.g. ``docs/index.md``).
    monkeypatch.chdir(root)
    rc = orchestrator.main(
        [
            "--inventory",
            "inventory.yaml",
            "--docs-root",
            "docs",
            "--reference",
            "ref.md",
            "--agent-reference",
            "agent.md",
            "--link-check",
            "none",
            "--ci",
        ]
    )
    assert rc == 0


def test_r3_lockfile_drift_is_reported_as_a_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _stage_lockfile_workspace(tmp_path / "repo", drift=True)
    findings = orchestrator._check_inventory_lockfile_drift(root / "inventory.yaml", root / "docs")
    # Drift is still reported (the check keeps running), at warning severity.
    assert findings, "expected lockfile drift findings"
    assert all(f.rule_id == "INVENTORY-LOCKFILE-DRIFT" for f in findings)
    assert all(f.severity == "warning" for f in findings)

    # And it no longer reds the orchestrator.
    _stub_external_subchecks(monkeypatch)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    (root / "ref.md").write_text("# ref\n", encoding="utf-8")
    (root / "agent.md").write_text("# agent\n", encoding="utf-8")
    monkeypatch.chdir(root)
    rc = orchestrator.main(
        [
            "--inventory",
            "inventory.yaml",
            "--docs-root",
            "docs",
            "--reference",
            "ref.md",
            "--agent-reference",
            "agent.md",
            "--link-check",
            "none",
            "--ci",
        ]
    )
    assert rc == 0


# --------------------------------------------------------------------------- #
# Body-link gate (WP18): blocking on its class. (The description gate retired
# with the legacy site build, #6943: doc-kitty's frontmatter validation enforces
# the description band in the docsite build.)
# --------------------------------------------------------------------------- #


def test_body_link_gate_reds_on_dead_link(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "docs" / "index.md", "# Home\n")
    _write(root / "docs" / "page.md", "See [gone](../missing/none.md).\n")
    assert relative_link_fixer.main(["--check", "--repo-root", str(root)]) == 1


def test_body_link_gate_green_when_links_resolve(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "docs" / "index.md", "# Home\n")
    _write(root / "docs" / "target.md", "# Target\n")
    _write(root / "docs" / "page.md", "See [target](target.md).\n")
    assert relative_link_fixer.main(["--check", "--repo-root", str(root)]) == 0


# --------------------------------------------------------------------------- #
# Diff-scope proof (#3147, WP02 T012) — the SAME CLI path docs-freshness.yml
# invokes on pull_request, with --changed-from wired. Four cases per B-WP02:
# in-scope BITE, out-of-scope PASS, base-unresolvable ERROR, resolved-zero-
# docs PASS (the fourth is the load-bearing distinction B-WP02 exists for).
# --------------------------------------------------------------------------- #

_UNRESOLVABLE_BASE_REF = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


class TestBodyLinkGateDiffScope:
    """``relative_link_fixer.py --check --changed-from`` — the WP18 body-link gate."""

    def test_in_scope_violation_reds(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md", "# Home\n")
        base_sha = init_git_repo_with_base(root)
        _write(root / "docs" / "page.md", "See [gone](../missing/none.md).\n")
        commit_all_changes(root, "add broken link")

        rc = relative_link_fixer.main(["--check", "--repo-root", str(root), "--changed-from", base_sha])
        assert rc == 1

    def test_out_of_scope_preexisting_violation_passes(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md", "# Home\n")
        # Pre-existing dead link, part of the base commit.
        _write(root / "docs" / "broken.md", "See [gone](../missing/none.md).\n")
        base_sha = init_git_repo_with_base(root)
        # The PR itself touches only an unrelated file.
        _write(root / "docs" / "other.md", "# Other\n")
        commit_all_changes(root, "add unrelated doc")

        rc = relative_link_fixer.main(["--check", "--repo-root", str(root), "--changed-from", base_sha])
        assert rc == 0

    def test_base_unresolvable_errors(self, tmp_path: Path) -> None:
        # B-WP02's load-bearing third case: distinct from both the in-scope
        # RED (1) and the out-of-scope/zero-docs PASS (0).
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md", "# Home\n")
        init_git_repo_with_base(root)

        rc = relative_link_fixer.main(
            [
                "--check",
                "--repo-root",
                str(root),
                "--changed-from",
                _UNRESOLVABLE_BASE_REF,
            ]
        )
        assert rc not in (0, 1)

    def test_resolved_zero_docs_passes(self, tmp_path: Path) -> None:
        # B-WP02's fourth case: a non-docs-md PR resolves fine and touches
        # zero in-scope docs files — must PASS, never error.
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md", "# Home\n")
        base_sha = init_git_repo_with_base(root)
        (root / "README.md").write_text("# readme change\n", encoding="utf-8")
        commit_all_changes(root, "non-docs change")

        rc = relative_link_fixer.main(["--check", "--repo-root", str(root), "--changed-from", base_sha])
        assert rc == 0


class TestRelatedValidatorDiffScope:
    """``related_validator.py --strict --changed-from`` — the R2 related-edge gate."""

    def test_in_scope_dangling_edge_reds(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md")
        base_sha = init_git_repo_with_base(root)
        _write(
            root / "docs" / "a.md",
            "---\nrelated:\n- does-not-exist\n---\n# A\n",
        )
        commit_all_changes(root, "add dangling related edge")

        rc = related_validator.main(
            [
                "--docs-root",
                str(root / "docs"),
                "--repo-root",
                str(root),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )
        assert rc == 1

    def test_out_of_scope_preexisting_dangling_edge_passes(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        # Pre-existing dangling edge, part of the base commit.
        _write(
            root / "docs" / "a.md",
            "---\nrelated:\n- does-not-exist\n---\n# A\n",
        )
        base_sha = init_git_repo_with_base(root)
        _write(root / "docs" / "other.md")
        commit_all_changes(root, "add unrelated doc")

        rc = related_validator.main(
            [
                "--docs-root",
                str(root / "docs"),
                "--repo-root",
                str(root),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )
        assert rc == 0

    def test_base_unresolvable_errors(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md")
        init_git_repo_with_base(root)

        rc = related_validator.main(
            [
                "--docs-root",
                str(root / "docs"),
                "--repo-root",
                str(root),
                "--strict",
                "--changed-from",
                _UNRESOLVABLE_BASE_REF,
            ]
        )
        assert rc not in (0, 1)

    def test_resolved_zero_docs_passes(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        _write(root / "docs" / "index.md")
        base_sha = init_git_repo_with_base(root)
        (root / "README.md").write_text("# readme change\n", encoding="utf-8")
        commit_all_changes(root, "non-docs change")

        rc = related_validator.main(
            [
                "--docs-root",
                str(root / "docs"),
                "--repo-root",
                str(root),
                "--strict",
                "--changed-from",
                base_sha,
            ]
        )
        assert rc == 0
