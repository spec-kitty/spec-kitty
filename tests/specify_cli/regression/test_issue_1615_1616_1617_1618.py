"""Regression tests for issues #1615, #1616, #1617, #1618.

Each test documents a specific bug and proves the fix:

  #1615 — implement.py dependency gate read status from repo_root/kitty-specs
           instead of the coord worktree → now uses resolve_mission_read_path.

  #1616 — orchestrator_api._resolve_mission_dir used bare kitty-specs path
           without checking coord worktree topology.

  #1617 — DecisionGitLog._decisions_file was rooted at repo_root when a
           coord worktree was in use, writing decision events to the wrong tree.

  #1618 — move_task emitted a second safe_commit to the protected target branch
           even when coord topology was active (coord branch already owns it).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]
# ---------------------------------------------------------------------------
# FR-017: source-scanning guards — stale strings must be absent, resolver
#         imports must be present (guards against re-introduction)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[3]  # tests/specify_cli/regression/ → repo root (worktree root)


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


_ORCHESTRATOR_API_DIR = "src/specify_cli/orchestrator_api"


def _orchestrator_api_sources() -> list[str]:
    """Every module of the orchestrator-api package (split by #5628)."""
    paths = sorted((REPO_ROOT / _ORCHESTRATOR_API_DIR).glob("*.py"))
    assert len(paths) >= 3, f"orchestrator_api package not found under {_ORCHESTRATOR_API_DIR}"
    return [path.read_text(encoding="utf-8") for path in paths]


# --- #1616: stale prompt strings must not reappear ---

def test_no_stale_status_in_main_repo_string() -> None:
    """workflow.py must not say status lives in main repo."""
    src = _read("src/specify_cli/cli/commands/agent/workflow.py")
    assert "Spec, plan, tasks, and status live in main repo" not in src, (
        "Stale prompt string from #1616 re-introduced in workflow.py"
    )


def test_no_stale_auto_commit_to_target_branch() -> None:
    """workflow.py must not say status auto-commits to target_branch."""
    src = _read("src/specify_cli/cli/commands/agent/workflow.py")
    assert "auto-commit to {target_branch} branch" not in src, (
        "Stale prompt string from #1616 re-introduced in workflow.py"
    )


def test_no_stale_for_review_to_in_progress() -> None:
    """workflow.py review docstring must not say for_review to in_progress."""
    src = _read("src/specify_cli/cli/commands/agent/workflow.py")
    assert "for_review to in_progress" not in src, (
        "Stale docstring from #1616 re-introduced in workflow.py"
    )


def test_no_stale_done_only_dependency() -> None:
    """Doctrine implement prompt must not require only 'done' status."""
    src = _read(
        "packs/built-in/missions/mission-steps/software-dev/implement/prompt.md"
    )
    assert "in `done` status before proceeding" not in src, (
        "Stale dependency condition from #1616 re-introduced in implement/prompt.md"
    )


# --- #1615: coord-aware resolver must be present ---

def test_resolve_mission_read_path_used_in_implement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#1615: implement's finalized/dependency gate reads the resolved coordination status surface.

    Behavioural oracle (it replaces a substring match that a comment satisfied). The primary
    checkout carries NO status events (every WP reads as genesis, "not finalized"); the WP is
    finalized only on the status surface the canonical resolver returns, the way a coord-topology
    mission is. implement must get past the finalization gate (and stop later, at the missing
    ``lanes.json``). If it read the primary surface instead, it would refuse with "not finalized".
    """
    import json
    import subprocess
    from unittest.mock import patch

    import typer

    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
    from specify_cli.cli.commands.implement import implement
    from specify_cli.coordination.surface_resolver import ResolvedStatusSurface
    from tests.specify_cli.cli.commands._implement_fixtures import create_meta_json, seed_planned

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_a, **_k: CharterPreflightResult(passed=True, checks=[]),
    )
    # A real (empty) repository: no implement collaborator is patched, so the oracle survives the
    # implement module being split.
    git_setup = (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
        ["commit", "-q", "--allow-empty", "-m", "init"],
    )
    for argv in git_setup:
        subprocess.run(["git", *argv], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".kittify").mkdir()
    primary = tmp_path / "kitty-specs" / "010-feature"
    meta_path = create_meta_json(primary)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = "01KVCPCHMCA5GSGF6NBAEE5E17"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    (primary / "tasks").mkdir(parents=True)
    (primary / "tasks" / "WP01-setup.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nexecution_mode: code_change\n"
        "owned_files:\n  - src/wp01/**\nauthoritative_surface: src/wp01/\n---\n# WP01",
        encoding="utf-8",
    )
    coord_surface = tmp_path / ".worktrees" / "010-feature-coord" / "kitty-specs" / "010-feature"
    coord_surface.mkdir(parents=True)
    seed_planned(coord_surface, "WP01")  # finalized on the coordination surface only

    monkeypatch.chdir(tmp_path)
    with (
        patch(
            "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
            return_value=ResolvedStatusSurface(surface_path=coord_surface / "status.events.jsonl", primary_anchor=primary),
        ),
        pytest.raises(typer.Exit),
    ):
        implement("WP01", mission="010-feature", json_output=True, recover=False)

    error = json.loads(capsys.readouterr().out.strip())["error"]
    assert "not finalized" not in error, f"implement read the primary surface, not the resolved status surface (#1615 regression): {error}"
    assert "lanes.json is required" in error, f"implement did not get past the finalization gate: {error}"


def test_resolve_mission_read_path_used_in_orchestrator_api() -> None:
    """The orchestrator_api package must use resolve_mission_read_path."""
    assert any("resolve_mission_read_path" in src for src in _orchestrator_api_sources()), (
        "coord-aware resolver not present in orchestrator_api (#1615 regression)"
    )


# ---------------------------------------------------------------------------
# #1615: implement.py reads status from coord worktree when present
# ---------------------------------------------------------------------------

class TestIssue1615ImplementCoordRead:
    """#1615: dependency gate must read from coord worktree, not primary checkout."""

    def test_resolve_mission_read_path_prefers_coord_worktree(self, tmp_path: Path) -> None:
        """resolve_mission_read_path returns coord path when coord dir exists on disk."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"
        # Create coord mission dir
        coord_dir = (
            tmp_path / ".worktrees" / f"{slug}-{mid8}-coord"
            / "kitty-specs" / f"{slug}-{mid8}"
        )
        coord_dir.mkdir(parents=True)
        # Also create primary (should NOT be selected)
        primary_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_dir.mkdir(parents=True)

        result = resolve_mission_read_path(tmp_path, slug, mid8)

        assert result == coord_dir, (
            f"Expected coord path {coord_dir}, got {result}. "
            "Regression: implement.py was reading from primary checkout instead of coord worktree."
        )

    def test_primary_checkout_returned_when_coord_absent(self, tmp_path: Path) -> None:
        """When no coord worktree, resolver correctly falls back to primary checkout."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"
        primary_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_dir.mkdir(parents=True)

        result = resolve_mission_read_path(tmp_path, slug, mid8)
        assert result == primary_dir

    def test_mid8_extracted_from_full_slug(self) -> None:
        """mid8 extraction from slug (used by implement.py before calling resolver)."""
        slug = "execution-context-unification-01KT3YBD"
        mid8 = ""
        if "-" in slug:
            tail = slug.rsplit("-", 1)[-1]
            if len(tail) == 8 and tail.isalnum() and tail.isupper():
                mid8 = tail
        assert mid8 == "01KT3YBD", (
            "Regression: implement.py failed to extract mid8 from mission slug."
        )


# ---------------------------------------------------------------------------
# #1616: orchestrator_api._resolve_mission_dir checks coord topology
# ---------------------------------------------------------------------------

class TestIssue1616OrchestratorApiCoordRead:
    """#1616 / #2016: _resolve_mission_dir must return coord path, not always primary."""

    # A *real* full 26-char Crockford ULID — realistic test data (NFR-005). The
    # mid8 is the first 8 chars; the canonical ``<slug>-<mid8>`` name embeds it.
    FULL_ULID = "01KVCPCHMCA5GSGF6NBAEE5E17"
    MID8 = FULL_ULID[:8]  # "01KVCPCH"

    def test_coord_path_returned_when_coord_exists(self, tmp_path: Path) -> None:
        """#2016: coord-ONLY-with-tail mission resolves via the shared mid8 cascade.

        Topology-true fixture: a mission present ONLY as a coordination worktree
        (``<slug>-<mid8>-coord``), with **no primary meta.json** (so
        ``mission_id`` is unproven). The defect: the orchestrator reimplemented
        mid8 resolution with only the strict ``resolve_mid8(slug, mission_id)``
        tier — keyed on primary meta — which DECLINES when ``mission_id`` is
        ``None`` → empty mid8 → empty read-path → ``None``. The fix adopts the
        shared 3-tier cascade whose tier-3 ``mid8_from_slug`` reads the real mid8
        from the canonical tail, so the coord path composes and returns.
        """
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        slug = "governed-coord-only-mission"
        handle = f"{slug}-{self.MID8}"
        coord_dir = (
            tmp_path / ".worktrees" / f"{handle}-coord"
            / "kitty-specs" / handle
        )
        coord_dir.mkdir(parents=True)
        # Intentionally NO primary meta.json — coord-only topology (C-001).

        result = _resolve_mission_dir(tmp_path, handle)
        assert result == coord_dir, (
            f"Expected coord path {coord_dir}, got {result}. "
            "Regression (#2016): orchestrator did not adopt the shared mid8 "
            "cascade, so the coord-only-with-tail topology resolved to an empty "
            "mid8 and missed the coord worktree."
        )

    def test_red_cause_is_empty_mid8_without_shared_cascade(self, tmp_path: Path) -> None:
        """Pin the RED *cause*: the strict primary-keyed tier alone yields ``""``.

        This locks WHY the pre-fix path returned ``None`` — not some unrelated
        change. With no declared ``mission_id`` (coord-only topology),
        ``resolve_mid8`` declines (``""``), whereas the shared cascade's tier-3
        ``mid8_from_slug`` recovers the real 8-char mid8 from the canonical tail.
        After the fix, the coord path test above proves tier-3 actually fired.
        """
        from specify_cli.lanes.branch_naming import mid8_from_slug, resolve_mid8

        handle = f"governed-coord-only-mission-{self.MID8}"
        # Pre-fix derivation (primary meta absent → mission_id None):
        assert resolve_mid8(handle, mission_id=None) == "", (
            "Pre-fix cause: resolve_mid8 keyed on absent primary meta must "
            "decline (empty mid8) for a coord-only mission."
        )
        # The shared cascade's tier-3 recovers the real mid8 from the tail:
        assert mid8_from_slug(handle) == self.MID8, (
            "tier-3 mid8_from_slug must recover the real mid8 from the "
            "canonical <slug>-<mid8> tail."
        )

    def test_none_returned_when_mission_not_found(self, tmp_path: Path) -> None:
        """_resolve_mission_dir returns None (not raises) when mission absent."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        result = _resolve_mission_dir(tmp_path, "nonexistent-01KT3YBD")
        assert result is None, (
            "Regression: _resolve_mission_dir should return None when mission not found."
        )

    def test_legacy_no_tail_no_id_returns_primary_not_raise(self, tmp_path: Path) -> None:
        """T012b: a legacy non-coord mission (no tail, no id) returns primary/None.

        Debbie's binding legacy-safety case: the shared helper returns ``""`` on
        exhaustion (does NOT raise), and the orchestrator's M5 raise is gated on
        ``declares_coordination``. A no-tail/no-id mission (e.g.
        ``099-test-mission``) has ``declares_coordination=False`` → the guard
        does NOT fire → it falls through to the primary read path, returning the
        primary dir (or ``None`` when absent), and MUST NOT raise.
        """
        import json

        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        slug = "099-test-mission"  # no Crockford tail, legacy NNN- form
        # Primary meta with NO mission_id and NO coordination_branch (legacy).
        primary_dir = tmp_path / "kitty-specs" / slug
        primary_dir.mkdir(parents=True)
        (primary_dir / "meta.json").write_text(
            json.dumps({"mission_slug": slug}), encoding="utf-8"
        )

        # Must NOT raise; must return the primary dir (it exists on disk).
        result = _resolve_mission_dir(tmp_path, slug)
        assert result == primary_dir, (
            "Legacy non-coord mission (no tail, no id) must keep the "
            f"primary-read path; expected {primary_dir}, got {result}."
        )

    def test_legacy_no_tail_no_id_absent_returns_none(self, tmp_path: Path) -> None:
        """T012b sibling: legacy no-tail/no-id, primary absent → None (not raise)."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        # No meta, no dir at all — pure absence on a legacy-style handle.
        result = _resolve_mission_dir(tmp_path, "099-absent-mission")
        assert result is None, (
            "Legacy non-coord absent mission must return None, not raise."
        )

    def test_exactly_one_mid8_cascade_in_orchestrator(self) -> None:
        """#2016 / NFR-005 / WP01 (binding, AST — not a skippable grep): the
        orchestrator derives the read path via exactly ONE seam — the shared
        ``resolve_handle_to_read_path`` (which owns the single
        ``resolve_declared_mid8`` cascade) — and retains NO local mid8 cascade of
        its own (neither a direct ``resolve_mid8`` keyed on primary meta NOR a
        re-derived ``resolve_declared_mid8``). After the WP01 extraction the
        cascade lives in the seam, not in ``commands.py``; re-introducing either
        derivation here is a regression.
        """
        called = {
            node.func.id
            for src in _orchestrator_api_sources()
            for node in ast.walk(ast.parse(src))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }
        assert "resolve_handle_to_read_path" in called, (
            "WP01: the orchestrator must consume the shared "
            "resolve_handle_to_read_path seam (the single guarded read-side path)."
        )
        assert "resolve_declared_mid8" not in called, (
            "WP01 / NFR-004: the mid8 cascade was lifted into the seam — the "
            "orchestrator must NOT re-derive resolve_declared_mid8 locally "
            "(no parallel cascade)."
        )
        assert "resolve_mid8" not in called, (
            "NFR-005: a second mid8-derivation path (direct resolve_mid8 keyed "
            "on primary meta) must not remain in orchestrator_api — "
            "consolidate onto the single seam cascade."
        )


# ---------------------------------------------------------------------------
# #1617: DecisionGitLog writes to coord worktree, not repo_root
# ---------------------------------------------------------------------------

class TestIssue1617DecisionLogCoordRouting:
    """#1617: decisions.events.jsonl must be written under coord worktree."""

    def test_decisions_file_uses_worktree_root_not_repo_root(self, tmp_path: Path) -> None:
        """When worktree_root is coord path, decisions_file is in coord path."""
        from specify_cli.events.decision_log import DecisionGitLog
        from runtime.next._internal_runtime.events import NullEmitter

        repo_root = tmp_path / "repo"
        coord_root = tmp_path / "coord-worktree"
        repo_root.mkdir()
        coord_root.mkdir()

        slug = "my-mission"
        log = DecisionGitLog(
            repo_root=repo_root,
            worktree_root=coord_root,
            destination_ref="kitty/mission-my-mission",
            mission_slug=slug,
            mission_dir=coord_root / "kitty-specs" / slug,
            inner=NullEmitter(),
        )

        # Regression: pre-fix this was repo_root / "kitty-specs" / ...
        expected = coord_root / "kitty-specs" / slug / "decisions.events.jsonl"
        assert log._decisions_file == expected, (
            f"Expected decisions_file under coord_root ({expected}), "
            f"but got {log._decisions_file}. "
            "Regression: DecisionGitLog was writing to repo_root instead of coord worktree."
        )

    def test_decisions_file_not_in_repo_root_when_coord_present(self, tmp_path: Path) -> None:
        """Explicitly assert that decisions_file is NOT in repo_root when coord is used."""
        from specify_cli.events.decision_log import DecisionGitLog
        from runtime.next._internal_runtime.events import NullEmitter

        repo_root = tmp_path / "repo"
        coord_root = tmp_path / "coord-worktree"
        repo_root.mkdir()
        coord_root.mkdir()

        slug = "my-mission"
        log = DecisionGitLog(
            repo_root=repo_root,
            worktree_root=coord_root,
            destination_ref="kitty/mission-my-mission",
            mission_slug=slug,
            mission_dir=coord_root / "kitty-specs" / slug,
            inner=NullEmitter(),
        )

        wrong_path = repo_root / "kitty-specs" / slug / "decisions.events.jsonl"
        assert log._decisions_file != wrong_path, (
            "Regression: DecisionGitLog._decisions_file must not point to repo_root "
            "when a coord worktree is in use."
        )


# ---------------------------------------------------------------------------
# #1618: move_task guard skips safe_commit when coord+protected
# ---------------------------------------------------------------------------

class TestIssue1618MoveTaskGuard:
    """#1618: second safe_commit skipped when coord topology active + protected branch."""

    def test_coord_topology_active_returns_true_when_coord_exists(self, tmp_path: Path) -> None:
        """_coord_topology_active returns True with coord worktree present on disk."""
        from specify_cli.cli.commands.agent.tasks import _coord_topology_active

        slug = "my-feature-01KT3YBD"
        mid8 = "01KT3YBD"
        base_slug = "my-feature"

        coord_path = tmp_path / ".worktrees" / f"{base_slug}-{mid8}-coord"
        coord_path.mkdir(parents=True)

        result = _coord_topology_active(tmp_path, slug)
        assert result is True, (
            "Regression: _coord_topology_active must return True when coord worktree exists. "
            "move_task guard was not detecting coord topology correctly."
        )

    def test_coord_topology_active_false_when_coord_absent(self, tmp_path: Path) -> None:
        """_coord_topology_active returns False when coord worktree absent."""
        from specify_cli.cli.commands.agent.tasks import _coord_topology_active

        result = _coord_topology_active(tmp_path, "my-feature-01KT3YBD")
        assert result is False

    def test_guard_condition_skips_commit_on_coord_plus_protected(self) -> None:
        """Guard: coord_active AND protected → skip second safe_commit."""
        coord_active = True
        target_branch = "main"
        protected = ["main"]

        skip = coord_active and target_branch in protected
        assert skip is True, (
            "Regression: move_task guard must set _skip_target_commit=True "
            "when coord topology active and target branch is protected."
        )

    def test_guard_condition_does_not_skip_on_legacy_missions(self) -> None:
        """Guard: legacy mission (coord_active=False) → safe_commit proceeds normally."""
        coord_active = False
        target_branch = "main"
        protected = ["main"]

        skip = coord_active and target_branch in protected
        assert skip is False, (
            "Regression: safe_commit must proceed for legacy missions (no coord topology)."
        )

    def test_guard_condition_does_not_skip_on_unprotected_branch(self) -> None:
        """Guard: coord active but target not protected → safe_commit still runs."""
        coord_active = True
        target_branch = "feature/my-work"
        protected = ["main"]

        skip = coord_active and target_branch in protected
        assert skip is False, (
            "Regression: safe_commit must run when target branch is not protected, "
            "even with coord topology active."
        )
