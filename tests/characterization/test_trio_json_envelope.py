"""CLI-envelope characterization of the coord-authority trio's 4 surfaces.

WP01 (coord-authority-trio-degod-01KX7094) -- T003.

======================================================================
WP01 REVIEWER CHECKLIST -- what is pinned, per surface (read before
approving; this enumerates the behaviours WP02/03/04 must not silently
change without an explicit, reviewed update to this suite)
======================================================================

* ``spec-kitty accept --mission <slug> --json --diagnose`` (flat + coord):
  - Full ``AcceptanceSummary.to_dict()`` JSON envelope shape (all top-level
    keys), plus ``acceptance_lane_derivations`` merge and the
    ``"diagnose": true`` marker.
  - ``ok`` / ``all_done`` booleans for a fully-approved single-WP mission.
  - Coord-topology fixture: the mission declares ``coordination_branch`` in
    ``meta.json`` but the coordination worktree is NEVER materialized on
    disk -- this exercises the LENIENT not-exists DEGRADE path of
    ``acceptance._status_read_feature_dir`` (see also
    ``test_trio_transitions.py``) end-to-end through the real CLI, not just
    at the unit boundary. The command still succeeds and reads STATUS off
    the primary checkout (``all_done`` / approved lane). RE-PIN 2026-07-25
    (PR #2906): the acceptance-MATRIX gate now REFUSES the un-materialized
    coord surface (GEC-5 / C2, #2885) rather than judging a primary
    substitute, so ``ok`` is now ``False`` for this fixture -- see the
    per-test docstring on ``test_coord_mission_diagnose_envelope_degrades_leniently``.

* ``spec-kitty implement WP01 --mission <slug> --recover --json`` (flat +
  coord): the crash-recovery "nothing to recover" JSON contract --
  ``{"status": "ok", "message": "No crashed implementation sessions
  found.", "recovered_wps": [], "worktrees_recreated": 0,
  "transitions_emitted": 0, "errors": []}`` -- for a mission with no
  in-flight worktree/context state. This is the ONLY read-only,
  side-effect-free path through ``implement.py``'s ``--json`` surface; the
  non-recover path materializes a real git worktree and is out of scope
  for this WP (tracked as a gap below). The coord case runs on a fixture
  whose coordination worktree IS materialized (``coord_repo_materialized``,
  the shape ``mission create`` leaves): since ``2fd7eabf0`` a coordination
  read on an unmaterialized coordination worktree fails closed by design,
  so ``--recover`` on the unmaterialized ``coord_repo`` refuses instead.

* ``spec-kitty agent action implement WP01 --mission <slug>`` (flat + coord
  MATERIALIZED, TEXT output -- see gap note below): a FIRST call on a
  freshly-``planned`` WP claims it and materializes the lane worktree. The
  big ``IMPLEMENT: WP01`` prompt banner (isolation rules, charter context,
  WP-prompt BEGIN/END wrapper) is written to an OS-temp-dir
  ``spec-kitty-prompts/<hash>/...`` FILE, not printed to stdout --
  confirmed by reading captured output, not assumed. Pinned: the stdout
  claim-confirmation text ("Creating workspace for WP01", "Lane worktree
  ready", the "CRITICAL: change to the lane worktree" banner, the
  lane-test-env export line, the "NEXT STEP: read the prompt file" pointer,
  and the ``move-task ... --to for_review`` next-step hint).

* ``spec-kitty agent action review WP01 --mission <slug>`` (flat + coord
  MATERIALIZED for the flat + happy-path coord fixture; see the DEFECT note
  below for the coord case that actually crashes): mirrors ``implement`` --
  a FIRST call on a ``for_review`` WP claims it for review and writes its
  own big prompt banner to an OS-temp-dir ``spec-kitty-review-prompts/...``
  path. Pinned:
  "Claimed WP01 for review", "Created workspace:", the prompt-file pointer,
  both ``move-task --to approved`` / ``move-task --to planned
  --review-feedback-file`` next-step hints, and the commit-recorded summary.

GAP NOTE 1 (DIRECTIVE_044 -- canonical sources, no silent workaround): the WP
prompt that generated this suite asked for all 4 surfaces to be
characterized "in --json via CliRunner". ``agent action implement`` and
``agent action review`` (``src/specify_cli/cli/commands/agent/workflow.py``)
do NOT expose a ``--json`` typer option today -- confirmed by reading the
module (no ``typer.Option("--json", ...)`` anywhere in ``implement()`` /
``review()``'s signatures). Only ``spec-kitty implement --json`` and
``spec-kitty accept --json`` genuinely support JSON output. Rather than
fabricate a flag that does not exist, this suite characterizes the CURRENT
behaviour of ``agent action implement``/``review`` as normalized TEXT
output (their real envelope), and files the discrepancy here instead of
silently reinterpreting the WP. If a future WP adds ``--json`` to these two
commands, this file's ``TestAgentActionImplementTextEnvelope`` /
``TestAgentActionReviewTextEnvelope`` classes are the ones to extend.

GAP NOTE 2 (a genuine current-behaviour finding, filed not worked around):
``agent action review`` on a coord-topology, ``for_review`` WP whose
coordination worktree IS materialized but which has NO prior ``implement``
claim in the lane crashes with a raw, unwrapped ``FileNotFoundError`` on the
not-yet-created lane worktree path -- BEFORE
``_prepare_review_workspace``'s own "Creating workspace"/"Created workspace"
lines ever print. The identical materialized-coord fixture pattern succeeds
end-to-end for ``implement`` (``TestAgentActionImplementTextEnvelope``'s
coord case). ``TestAgentActionReviewTextEnvelope.
test_coord_mission_prompt_skeleton`` pins this exact crash as CURRENT
behaviour (exit code 1, the raw ``[Errno 2]`` message, the "commits
recorded ... [refused]" trailer) rather than forcing the fixture into an
unrepresentative shape to dodge it. Root-causing and fixing this crash is
explicitly OUT OF SCOPE for WP01 (a characterization-only WP) -- it should
be filed as its own tracked defect by whoever picks this note up.

Also see two upstream ordering/naming pitfalls this suite's fixture builder
had to discover and correct (documented inline in ``_build_mission_repo``):
(1) the canonical VERBATIM coord-branch grammar is
``kitty/mission-<slug>-<mid8>`` (``lanes.branch_naming.
coord_reconstruct_branch``), not the bare ``kitty/mission-<slug>`` the
canonical NNN-stripping mission-create composer uses; (2) a MATERIALIZED
coordination worktree's surface resolver expects the on-disk mission
directory itself to carry the ``-<mid8>`` suffix
(``kitty-specs/<slug>-<mid8>/``) -- a bare-slug mission directory is only
tolerated for PRIMARY reads, not once the coord worktree is checked out.

Marker: integration + git_repo (CliRunner over a real git repository).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.analysis_report import write_analysis_report
from tests.characterization._normalize import normalize_envelope, normalize_json_value
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest
from tests.specify_cli.charter_preflight._fixtures import (
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
    write_metadata,
)
from tests.utils import write_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixture builders -- flat (no coordination_branch) and coord-topology
# (coordination_branch declared, coord worktree deliberately NOT
# materialized so the lenient degrade path is what the CLI actually walks).
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _build_mission_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    coord: bool,
    mission_slug: str,
    wp_lane: str,
    materialize_coord: bool = False,
) -> tuple[Path, str]:
    """Return ``(repo_root, mission_handle)`` -- the ``--mission`` CLI value.

    For a materialized-coord fixture, the on-disk mission directory (and the
    ``--mission`` handle) MUST carry the ``-<mid8>`` suffix
    (``kitty-specs/<slug>-<mid8>/``): the coordination-worktree surface
    resolver navigates the checked-out coord tree looking for exactly that
    dirname (confirmed by reading its warning: "carries no mission dir").
    Non-materialized fixtures keep the bare human slug -- both forms are
    genuinely tolerated by the read-side canonicalizer for a PRIMARY read.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "trio-characterization@example.invalid")
    _git(repo_root, "config", "user.name", "Trio Characterization")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")

    # ``agent action implement``/``review`` gate on a synced charter bundle
    # (charter_runtime preflight) before rendering the prompt. Reuse the
    # canonical charter_preflight test fixtures to materialise a minimal
    # fresh bundle rather than hand-rolling the synthesis-manifest shape.
    charter_path, metadata_path = seed_charter(repo_root)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo_root)
    # consolidate-charter-bundle WP06 re-pointed charter_runtime freshness at
    # ``charter.yaml`` (the sole resolving source); seed it BEFORE the manifest
    # so ``seed_manifest``'s auto-compute stamps a matching bundle_content_hash
    # and all three freshness sub-states read ``fresh``.
    seed_charter_yaml(repo_root)
    seed_manifest(repo_root, built_in_only=False)
    seed_graph(repo_root)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed")

    # ``main`` is a protected branch (ProtectionPolicy default) -- status
    # writes refuse to commit there. Real missions run on a dedicated target
    # branch; mirror that instead of fighting the protection gate.
    target_branch = "trio-integration"
    _git(repo_root, "checkout", "-q", "-b", target_branch)

    # Software Dev Kitty's path-convention gate (validate_mission_paths)
    # requires these to exist for a non-research mission. ``src``/``tests``/
    # ``docs`` are repo-root "build" paths; ``contracts`` (deliverables) is
    # mission-scoped and resolves against ``feature_dir`` instead (see
    # ``accept.py``'s ``planning_read_dir`` comment on this exact split).
    for path_dir in ("src", "tests", "docs"):
        (repo_root / path_dir).mkdir(exist_ok=True)

    mission_id = derive_mission_id(mission_slug)
    mid8 = mission_id[:8]
    mission_dirname = f"{mission_slug}-{mid8}" if materialize_coord else mission_slug

    feature_dir = repo_root / "kitty-specs" / mission_dirname
    feature_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001: Demo spec for trio characterization.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    (feature_dir / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    (feature_dir / "data-model.md").write_text("# Data model\n", encoding="utf-8")
    (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    # Canonical VERBATIM coord-branch grammar is "<slug>-<mid8>" (mid8
    # appended), reconstructed via lanes.branch_naming.coord_reconstruct_branch
    # -- NOT the bare "kitty/mission-<slug>" the canonical (NNN-stripped)
    # mission-create composer uses. Get this wrong and every coord-aware
    # STATUS read (read_current_wp_state_transactional) silently finds no
    # events on the (wrongly-named) branch and reports Lane.GENESIS.
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_slug": mission_slug,
        "slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "friendly_name": "Trio characterization mission",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    if coord:
        # Declared AND the branch ref exists (status commits route there),
        # but the coordination WORKTREE is deliberately NEVER materialized
        # on disk -- no `.worktrees/*-coord` checkout is created. Every
        # coord-aware READ in the trio must therefore degrade leniently to
        # the primary checkout for this fixture to produce a usable result
        # (the behaviour under test).
        meta["coordination_branch"] = coord_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_single_lane_manifest(
        feature_dir,
        wp_ids=("WP01",),
        target_branch=target_branch,
        mission_id=mission_id,
    )
    write_wp(repo_root, mission_dirname, wp_lane, "WP01")

    from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=mission_slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-01",
                    description="Trio characterization fixture is self-consistent",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        ),
    )

    # `agent action implement` refuses to proceed without a fresh
    # /spec-kitty.analyze report (#1989 gate) -- seed one so the implement
    # surface reaches the actual prompt-rendering code under test.
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed mission scaffold")

    if coord:
        # Branch the coord ref from the FULLY populated mission commit --
        # mirrors real mission setup (coord branches off the seeded
        # scaffold).
        _git(repo_root, "branch", coord_branch)
        if materialize_coord:
            # ``read_current_wp_state_transactional`` (status/work_package_
            # lifecycle.py, the START-implementation/START-review status
            # read) has NO lenient not-exists fallback -- unlike
            # ``acceptance._status_read_feature_dir`` -- so a coord-declared
            # mission whose coord worktree is unmaterialized reads back
            # Lane.GENESIS regardless of what the primary checkout's event
            # log says. Materializing it here proves the "coord path
            # actually works" branch; the leniency asymmetry itself is
            # pinned directly in test_trio_transitions.py.
            from specify_cli.coordination.workspace import CoordinationWorkspace

            CoordinationWorkspace.resolve(repo_root, mission_dirname, mid8)

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root, mission_dirname


@pytest.fixture()
def flat_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Flat (no coordination_branch) mission, WP01 in ``approved`` -- accept surface."""
    return _build_mission_repo(tmp_path, monkeypatch, coord=False, mission_slug="trio-flat-mission", wp_lane="approved")


@pytest.fixture()
def coord_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Coord-topology mission (coord worktree unmaterialized), WP01 ``approved``."""
    return _build_mission_repo(tmp_path, monkeypatch, coord=True, mission_slug="trio-coord-mission", wp_lane="approved")


@pytest.fixture()
def coord_repo_materialized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Coord-topology mission, WP01 ``approved``, coord worktree MATERIALIZED
    -- the shape ``mission create`` leaves. A coordination read on an
    unmaterialized coordination worktree fails closed (``2fd7eabf0``), so the
    recover surface is characterized here rather than on ``coord_repo``."""
    return _build_mission_repo(
        tmp_path, monkeypatch, coord=True, mission_slug="trio-coord-recover", wp_lane="approved", materialize_coord=True
    )


@pytest.fixture()
def flat_repo_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Flat mission, WP01 ``planned`` -- implement surface (claimable)."""
    return _build_mission_repo(tmp_path, monkeypatch, coord=False, mission_slug="trio-flat-implement", wp_lane="planned")


@pytest.fixture()
def coord_repo_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Coord-topology mission, WP01 ``planned``, coord worktree MATERIALIZED
    -- implement's status-claim read has no lenient not-exists fallback
    (see ``test_trio_transitions.py``), so this fixture proves the
    coord-materialized path instead of the degrade path."""
    return _build_mission_repo(
        tmp_path, monkeypatch, coord=True, mission_slug="trio-coord-implement", wp_lane="planned", materialize_coord=True
    )


@pytest.fixture()
def flat_repo_for_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Flat mission, WP01 ``for_review`` -- review surface."""
    return _build_mission_repo(tmp_path, monkeypatch, coord=False, mission_slug="trio-flat-review", wp_lane="for_review")


@pytest.fixture()
def coord_repo_for_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Coord-topology mission, WP01 ``for_review``, coord worktree MATERIALIZED
    (see ``coord_repo_planned`` docstring for why)."""
    return _build_mission_repo(
        tmp_path, monkeypatch, coord=True, mission_slug="trio-coord-review", wp_lane="for_review", materialize_coord=True
    )


# ---------------------------------------------------------------------------
# Surface 1: ``spec-kitty accept --json --diagnose``
# ---------------------------------------------------------------------------


class TestAcceptJsonDiagnose:
    """Read-only diagnostic JSON envelope -- no commit, no matrix mutation."""

    def _run(self, repo_root: Path, mission_slug: str) -> dict[str, Any]:
        result = runner.invoke(
            root_app,
            ["accept", "--mission", mission_slug, "--json", "--diagnose"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        normalized: dict[str, Any] = normalize_json_value(payload, repo_root)
        return normalized

    def test_flat_mission_diagnose_envelope(self, flat_repo: tuple[Path, str]) -> None:
        repo_root, mission_slug = flat_repo
        payload = self._run(repo_root, mission_slug)

        assert payload["diagnose"] is True
        assert payload["all_done"] is True
        assert payload["ok"] is True
        assert payload["lanes"]["approved"] == ["WP01"]
        assert payload["work_packages"][0]["id"] == "WP01"
        assert payload["work_packages"][0]["lane"] == "approved"
        assert payload["accepted_wps"] == ["WP01"]
        assert payload["approved_wps"] == ["WP01"]
        assert payload["done_wps"] == []
        assert payload["blocked_checks"] == []
        assert payload["metadata_issues"] == []

    def test_coord_mission_diagnose_envelope_degrades_leniently(self, coord_repo: tuple[Path, str]) -> None:
        """The coordination worktree was never materialized.

        The STATUS read still degrades leniently to the primary checkout --
        ``all_done`` and the approved lane are read there (``_status_read_feature_dir``'s
        not-exists fallback is unchanged). The ACCEPTANCE-MATRIX gate, however, no
        longer judges the coord-homed matrix against a PRIMARY substitute: it
        refuses (``acceptance_matrix_cannot_evaluate`` / ``SURFACE_CANNOT_HOLD_FACT``),
        so the diagnostic envelope reports ``ok=False`` and names why.

        RE-PIN 2026-07-25 (PR #2906, operator-reviewed). This overrides the prior
        ``ok=True`` pin from mission ``coord-authority-trio-degod`` (WP01). The
        lifecycle-gate-execution-context mission's GEC-5 / C2 (#2885)
        ``_matrix_surface_cannot_hold`` makes a coord-declared mission whose
        coordination surface is not materialized REFUSE rather than judge an empty
        or substituted PRIMARY surface -- the "refuse rather than guess" thesis this
        mission exists to enforce. The old lenient ``ok=True`` was exactly the
        confident-wrong-verdict (judging a coord fact off a primary substitute) the
        mission eliminates. The command still succeeds (exit 0) and the envelope is
        still emitted; it now discloses the cannot-evaluate honestly.
        """
        repo_root, mission_slug = coord_repo
        payload = self._run(repo_root, mission_slug)

        assert payload["diagnose"] is True
        # Status still degrades leniently to the primary checkout.
        assert payload["all_done"] is True
        assert payload["lanes"]["approved"] == ["WP01"]
        assert payload["mission_slug"] == mission_slug
        # The matrix gate refuses the un-materialized coord surface (GEC-5 / C2).
        assert payload["ok"] is False
        assert any(
            c["check"] == "acceptance_matrix_cannot_evaluate" for c in payload["blocked_checks"]
        ), payload["blocked_checks"]
        assert any(
            "SURFACE_CANNOT_HOLD_FACT" in c["detail"] for c in payload["blocked_checks"]
        ), payload["blocked_checks"]


# ---------------------------------------------------------------------------
# Surface 2: ``spec-kitty implement --recover --json``
# ---------------------------------------------------------------------------


class TestImplementRecoverJson:
    """The sole side-effect-free ``--json`` path through ``implement.py``."""

    def _run(self, repo_root: Path, mission_slug: str) -> dict[str, Any]:
        result = runner.invoke(
            root_app,
            ["implement", "WP01", "--mission", mission_slug, "--recover", "--json"],
        )
        assert result.exit_code == 0, result.output
        payload: dict[str, Any] = json.loads(result.output)
        return payload

    def test_flat_mission_no_crashed_sessions(self, flat_repo: tuple[Path, str]) -> None:
        repo_root, mission_slug = flat_repo
        payload = self._run(repo_root, mission_slug)

        assert payload == {
            "status": "ok",
            "message": "No crashed implementation sessions found.",
            "recovered_wps": [],
            "worktrees_recreated": 0,
            "transitions_emitted": 0,
            "errors": [],
        }

    def test_coord_mission_no_crashed_sessions(self, coord_repo_materialized: tuple[Path, str]) -> None:
        repo_root, mission_slug = coord_repo_materialized
        payload = self._run(repo_root, mission_slug)

        assert payload == {
            "status": "ok",
            "message": "No crashed implementation sessions found.",
            "recovered_wps": [],
            "worktrees_recreated": 0,
            "transitions_emitted": 0,
            "errors": [],
        }


# ---------------------------------------------------------------------------
# Surface 3 & 4: ``agent action implement`` / ``agent action review``
# (TEXT envelope -- no --json flag exists on these two commands; see the
# GAP NOTE in the module docstring).
# ---------------------------------------------------------------------------


def _run_action(repo_root: Path, verb: str, mission_slug: str, *extra_args: str) -> str:
    result = runner.invoke(
        root_app,
        ["agent", "action", verb, "WP01", "--mission", mission_slug, *extra_args],
    )
    assert result.exit_code == 0, result.output
    return normalize_envelope(result.output, repo_root)


class TestAgentActionImplementTextEnvelope:
    """A FIRST ``implement`` call on a freshly-``planned`` WP claims it and
    materializes the lane worktree; the big ``IMPLEMENT: WP01`` prompt banner
    (isolation rules, charter context, WP-prompt wrapper) is written to an
    OS-temp-dir ``spec-kitty-prompts/...`` FILE rather than printed to
    stdout -- this is genuine current behaviour (confirmed by reading the
    captured output), not an assumption. This class pins the stdout
    claim-confirmation text."""

    def _assert_skeleton(self, text: str) -> None:
        assert "Creating workspace for WP01" in text
        assert "Lane worktree ready" in text
        assert "CRITICAL: Change to the lane worktree before editing files" in text
        assert "Lane-specific test environment" in text
        assert "NEXT STEP: Read the full prompt file now" in text
        assert "spec-kitty agent tasks move-task WP01 --to for_review" in text

    def test_flat_mission_prompt_skeleton(self, flat_repo_planned: tuple[Path, str]) -> None:
        repo_root, mission_slug = flat_repo_planned
        text = _run_action(repo_root, "implement", mission_slug)
        self._assert_skeleton(text)

    def test_coord_mission_prompt_skeleton(self, coord_repo_planned: tuple[Path, str]) -> None:
        repo_root, mission_slug = coord_repo_planned
        text = _run_action(repo_root, "implement", mission_slug)
        self._assert_skeleton(text)


class TestAgentActionReviewTextEnvelope:
    """Mirror of ``TestAgentActionImplementTextEnvelope`` for the review verb:
    a FIRST ``review`` call on a ``for_review`` WP claims it for review and
    writes the big prompt banner to an OS-temp-dir
    ``spec-kitty-review-prompts/...`` file; this class pins the stdout
    claim-confirmation text."""

    def _assert_skeleton(self, text: str) -> None:
        assert "Claimed WP01 for review" in text
        assert "Created workspace:" in text
        assert "NEXT STEP: Read the full prompt file now" in text
        assert "spec-kitty agent tasks move-task WP01 --to approved" in text
        assert "spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file" in text
        assert "[review] Commits recorded:" in text

    def test_flat_mission_prompt_skeleton(self, flat_repo_for_review: tuple[Path, str]) -> None:
        repo_root, mission_slug = flat_repo_for_review
        text = _run_action(repo_root, "review", mission_slug, "--agent", "reviewer-renata")
        self._assert_skeleton(text)

    def test_coord_mission_prompt_skeleton(self, coord_repo_for_review: tuple[Path, str]) -> None:
        """A coord review without lane commits fails with an actionable gate.

        The former raw ``FileNotFoundError`` is gone; the command now reaches
        the review commit guard and reports the refused coordination branch.
        """
        repo_root, mission_slug = coord_repo_for_review
        result = runner.invoke(
            root_app,
            ["agent", "action", "review", "WP01", "--mission", mission_slug, "--agent", "reviewer-renata"],
        )

        assert result.exit_code == 1
        text = normalize_envelope(result.output, repo_root)
        assert "Error: [Errno 2]" not in text
        assert "[review] Commits recorded:" in text
        assert "[refused]" in text
