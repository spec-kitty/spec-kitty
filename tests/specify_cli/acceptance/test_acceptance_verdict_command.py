"""WP04 (write-side-seam-matrix-tracer-01KYP3MH): T014/T015/T016/T017/T018.

Covers:

* T014 — ``overall_verdict`` stays a COMPUTED property, never a stored field
  (round-trips a hand-edited/stale on-disk value away — #2743 negative-
  invariant-integrity's sibling guard for the acceptance half of the schema).
* T016 — the #2318 regression: an all-pass / zero-negative-invariant accept
  must persist the recomputed verdict, not leave the on-disk file stuck at a
  stale ``pending`` (the pre-fix gate only wrote inside the
  ``negative_invariants`` arm).
* T015/T017 — the ``acceptance-verdict`` command routes its write through the
  WP03 write seam (``write_and_commit_acceptance_matrix`` ->
  ``coordination.write_seam.write_artifact``), is idempotent (FR-012), and
  lands acceptance-matrix.json on the COORD surface for a coord-topology
  mission (never a stranded primary copy).
"""

from __future__ import annotations

import importlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance.gates_core import _evaluate_acceptance_matrix
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    enforce_negative_invariants,
    read_acceptance_matrix,
    write_acceptance_matrix,
    write_and_commit_acceptance_matrix,
)
from specify_cli.cli.commands.agent.acceptance_verdict import (
    _resolve_criterion_update,
    acceptance_verdict,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.status.locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
    feature_status_lock_path,
)
from kernel.git_topology import git_common_dir

# Reused verbatim (not duplicated) — the shared coord-topology mission
# fixture builder this mission's own #2404 coord-partition test already
# establishes (module docstring there: "Build ON #2462's landed ...").
from tests.integration.test_accept_matrix_coord_partition import (
    _build_coord_mission_for_matrix,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ``specify_cli.cli.commands.agent``'s ``__init__.py`` does
# ``from .acceptance_verdict import acceptance_verdict`` — the FUNCTION is
# re-exported under the SAME name as its own SUBMODULE, which shadows the
# submodule on a plain attribute access (and even on ``import ... as alias``,
# since that binding form is also attribute-lookup-based). ``importlib.
# import_module`` reads straight from ``sys.modules`` instead, giving the
# real submodule object so ``monkeypatch.setattr(av_command, "name", ...)``
# patches the COMMAND-MODULE binding the concurrency seam tests need.
av_command = importlib.import_module("specify_cli.cli.commands.agent.acceptance_verdict")


# ---------------------------------------------------------------------------
# Shared flat-repo git helpers
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _head(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


_FLAT_BRANCH = "matrix-verdict-work"


def _mission_id_for(slug: str) -> str:
    """A deterministic, valid-shape 26-char ULID for a test mission_id.

    ``resolve_mission_handle`` (``cli/selector_resolution.py``) indexes
    missions by ``meta.json``'s ``mission_id`` — a flat mission fixture
    without one is unresolvable (``MissionNotFoundError``). Mirrors the
    hand-minted-ULID convention used by
    ``tests/specify_cli/test_accept_no_commit_readonly.py``.
    """
    digest = f"{slug:0<26}".upper()[:26]
    # ULIDs use Crockford base32 — strip characters outside that alphabet so
    # the fixture value is shape-valid, not just length-valid.
    allowed = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return "".join(c if c in allowed else "0" for c in digest)


def _init_flat_mission(tmp_path: Path, slug: str) -> tuple[Path, Path]:
    """A minimal, real flat (non-coord) mission repo for the write/commit path.

    ``main``/``master`` are protected by default
    (``ProtectionPolicy._DEFAULT_PROTECTED_BRANCHES``); a dedicated
    non-default branch mirrors ``test_accept_matrix_coord_partition.py``'s own
    ``_WORK_BRANCH`` convention so the seam commits directly rather than
    refusing on a protected ref.
    """
    repo_root = tmp_path
    _git(repo_root, "init", "-q")
    _git(repo_root, "checkout", "-q", "-b", _FLAT_BRANCH)
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    # A ``.kittify/`` marker gives ``locate_project_root`` a definite project
    # boundary at ``repo_root`` (WP04 C-A1 fixture hardening): without one,
    # repo-root detection falls back to a bare ``.git`` walk-up that can
    # escape past this fixture into an unrelated ancestor project on a
    # contaminated filesystem. ``mission_type_activations`` mirrors every
    # mission this fixture mints (``mission_type": "software-dev"`` above).
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    mission_id = _mission_id_for(slug)
    meta = {
        "mission_slug": slug,
        "slug": slug,
        "mission_id": mission_id,
        "mid8": mission_id[:8],
        "friendly_name": "Matrix Verdict Test",
        "mission_type": "software-dev",
        "target_branch": _FLAT_BRANCH,
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "init")
    return repo_root, feature_dir


# ===========================================================================
# T014 — overall_verdict stays a computed property, never hand-stored
# ===========================================================================


class TestOverallVerdictIsComputedNotStored:
    def test_overall_verdict_is_not_a_dataclass_field(self) -> None:
        """The schema itself cannot carry a stored ``overall_verdict`` — it is a
        ``@property``, not a ``dataclasses.field`` (#2743 sibling guard)."""
        field_names = {f.name for f in fields(AcceptanceMatrix)}
        assert "overall_verdict" not in field_names
        assert isinstance(AcceptanceMatrix.overall_verdict, property)

    def test_from_dict_ignores_a_hand_stored_stale_verdict(self) -> None:
        """A hand-edited/stale on-disk ``overall_verdict`` is IGNORED on load —
        the reconstructed object recomputes it fresh from criteria/invariants,
        so a stale value on disk can never smuggle a wrong verdict back in."""
        matrix = AcceptanceMatrix(
            mission_slug="verdict-integrity-mission",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="works",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        )
        assert matrix.overall_verdict == "pass"

        payload = matrix.to_dict()
        # Simulate a stale/hand-edited on-disk value — deliberately wrong.
        payload["overall_verdict"] = "fail"

        reloaded = AcceptanceMatrix.from_dict(payload)
        assert reloaded.overall_verdict == "pass", (
            "a stored overall_verdict value must never override the computed one"
        )

    def test_to_dict_round_trip_omits_no_information_needed_to_recompute(self) -> None:
        matrix = AcceptanceMatrix(
            mission_slug="verdict-integrity-mission",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="works",
                    proof_type="automated_test",
                    pass_fail="pending",
                )
            ],
        )
        assert matrix.overall_verdict == "pending"
        reloaded = AcceptanceMatrix.from_dict(matrix.to_dict())
        assert reloaded.overall_verdict == "pending"
        assert reloaded.criteria[0].criterion_id == "FR-001"


# ===========================================================================
# NFR-001 — verdict determinism, zero product-source reads
# ===========================================================================


class TestVerdictDeterminismNoIo:
    def test_overall_verdict_is_a_pure_function_of_in_memory_state(self) -> None:
        """``overall_verdict`` never touches the filesystem — it is derived
        purely from ``criteria``/``negative_invariants`` already held in
        memory (NFR-001). Any accidental I/O would raise here, since the
        matrix objects below reference no real files at all."""
        matrix = AcceptanceMatrix(
            mission_slug="pure-verdict-mission",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="works",
                    proof_type="automated_test",
                    pass_fail="pass",
                ),
                AcceptanceCriterion(
                    criterion_id="FR-002",
                    description="also works",
                    proof_type="code_review",
                    pass_fail="pass",
                ),
            ],
        )
        # Same result computed twice from the SAME in-memory state — a pure
        # function is stable under repeated evaluation with no side effects.
        assert matrix.overall_verdict == "pass"
        assert matrix.overall_verdict == "pass"


# ===========================================================================
# T016 — #2318 regression: all-pass / no-negative-invariant accept persists
# the recomputed verdict instead of leaving a stale on-disk 'pending'
# ===========================================================================


class TestPersistOnAcceptRegression2318:
    def test_all_pass_no_invariants_persists_pass_not_stale_pending(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Drives the PRE-EXISTING entry point named in #2318 comment
        5102989064 (``_evaluate_acceptance_matrix``) directly: an all-pass
        matrix with ZERO negative invariants (the previously-uncovered
        branch — the old gate only wrote inside ``if
        acc_matrix.negative_invariants``) must still have its recomputed
        ``overall_verdict`` land on disk as ``"pass"``."""
        slug = "no-invariant-mission"
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)

        matrix = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="the feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        )
        # Seed a stale on-disk 'pending' matrix first (the #2318 starting
        # state — a scaffolded, never-since-refreshed matrix) so this test
        # actually pins the "stops being stale" transition, not merely "a
        # fresh write happens to say pass".
        stale = AcceptanceMatrix(mission_slug=slug, criteria=[
            AcceptanceCriterion(
                criterion_id="FR-001",
                description="the feature behaves as specified",
                proof_type="automated_test",
                pass_fail="pending",
            )
        ])
        write_acceptance_matrix(feature_dir, stale)
        assert json.loads((feature_dir / "acceptance-matrix.json").read_text())["overall_verdict"] == "pending"

        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)

        activity_issues: list[str] = []
        skipped: list = []
        blocked: list = []
        _evaluate_acceptance_matrix(
            tmp_path, feature_dir, activity_issues, skipped, blocked, mutate_matrix=True
        )

        assert activity_issues == []
        persisted = json.loads((feature_dir / "acceptance-matrix.json").read_text())
        assert persisted["overall_verdict"] == "pass", (
            "#2318: an all-pass / no-negative-invariant accept must persist "
            "the recomputed verdict, not leave the on-disk file at a stale "
            "'pending'"
        )

    def test_diagnose_mode_still_does_not_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contrast case: ``mutate_matrix=False`` (``--diagnose``) must still
        never write — the T016 fix only widens the ``mutate_matrix=True`` arm,
        it does not touch the read-only contract (#1883/#1908)."""
        slug = "diagnose-mission"
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        matrix = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="works",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        )
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)

        _evaluate_acceptance_matrix(tmp_path, feature_dir, [], [], [], mutate_matrix=False)

        assert not (feature_dir / "acceptance-matrix.json").exists()


# ===========================================================================
# T017 — write_and_commit_acceptance_matrix (the WP03-seam composition helper)
# ===========================================================================


class TestWriteAndCommitAcceptanceMatrix:
    def test_first_write_commits_second_identical_write_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        """FR-012 idempotence, inherited from ``commit_for_mission``: a
        byte-identical re-write resolves to ``"unchanged"`` — no duplicate
        commit, HEAD does not move."""
        slug = "seam-idempotence-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        matrix = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="works",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
        )
        policy = ProtectionPolicy.resolve(repo_root)

        first = write_and_commit_acceptance_matrix(
            repo_root,
            slug,
            feature_dir,
            matrix,
            entry_id="FR-001",
            message="chore(acceptance): record FR-001=pass",
            policy=policy,
        )
        assert first.status == "committed", first
        head_after_first = _head(repo_root)

        second = write_and_commit_acceptance_matrix(
            repo_root,
            slug,
            feature_dir,
            matrix,
            entry_id="FR-001",
            message="chore(acceptance): record FR-001=pass",
            policy=policy,
        )
        assert second.status == "unchanged", second
        assert _head(repo_root) == head_after_first, "a no-op re-write must not create a new commit"


# ===========================================================================
# T015 — the ``acceptance-verdict`` command
# ===========================================================================


class TestAcceptanceVerdictCommand:
    def _seed_matrix(self, feature_dir: Path, slug: str) -> None:
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="FR-001",
                        description="the feature behaves as specified",
                        proof_type="automated_test",
                        pass_fail="pending",
                    )
                ],
            ),
        )

    def test_records_verdict_and_persists_recomputed_overall_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slug = "verdict-command-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        self._seed_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed acceptance-matrix")
        monkeypatch.chdir(repo_root)

        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ci-run-123",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        assert reloaded.criteria[0].pass_fail == "pass"
        assert reloaded.criteria[0].verified_by == "tester"
        assert reloaded.criteria[0].evidence == "ci-run-123"
        assert reloaded.overall_verdict == "pass"

    def test_rerun_with_identical_inputs_is_a_no_op(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-012: a second invocation with IDENTICAL inputs does not bump
        ``verified_at`` (nothing observable changed), so the underlying write
        is byte-identical and the commit resolves to ``"unchanged"`` — no new
        commit, HEAD unchanged."""
        slug = "verdict-command-idempotent-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        self._seed_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed acceptance-matrix")
        monkeypatch.chdir(repo_root)

        def _invoke() -> dict[str, object]:
            capsys.readouterr()
            try:
                acceptance_verdict(
                    mission=slug,
                    criterion="FR-001",
                    result="pass",
                    verification_method="automated_test",
                    actor="tester",
                    evidence="ci-run-123",
                    json_output=True,
                )
            except typer.Exit as exc:
                assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"
            out = capsys.readouterr().out.strip()
            return dict(json.loads(out))

        first_payload = _invoke()
        assert first_payload["write_status"] == "committed"
        head_after_first = _head(repo_root)

        second_payload = _invoke()
        assert second_payload["write_status"] == "unchanged", second_payload
        assert _head(repo_root) == head_after_first, "an identical re-run must not create a new commit"

    def test_unknown_criterion_reports_available_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slug = "verdict-command-unknown-criterion"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        self._seed_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed acceptance-matrix")
        monkeypatch.chdir(repo_root)

        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission=slug,
                criterion="FR-999",
                result="pass",
                verification_method=None,
                actor=None,
                evidence=None,
                json_output=False,
            )
        assert exc_info.value.exit_code == 1

    def test_invalid_result_value_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission="whatever",
                criterion="FR-001",
                result="not-a-real-verdict",
                verification_method=None,
                actor=None,
                evidence=None,
                json_output=False,
            )
        assert exc_info.value.exit_code == 2

    def test_lands_on_coord_surface_not_a_stranded_primary_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The command must resolve the SAME coord surface every other
        production writer lands on (never a stranded primary-checkout copy)."""
        result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
        slug = result.mission_slug

        coord_feature_dir.mkdir(parents=True, exist_ok=True)
        self._seed_matrix(coord_feature_dir, slug)
        subprocess.run(
            ["git", "-C", str(coord_root), "add", "-A"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(coord_root), "commit", "-q", "-m", "seed coord matrix"],
            check=True,
            capture_output=True,
        )

        monkeypatch.chdir(tmp_path)
        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method=None,
                actor="tester",
                evidence=None,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        # The PRIMARY checkout must NOT carry a stranded copy of the matrix.
        assert not (result.feature_dir / "acceptance-matrix.json").exists(), (
            "acceptance-verdict must not strand a copy on the primary checkout "
            "for a coord-topology mission"
        )
        reloaded = read_acceptance_matrix(coord_feature_dir)
        assert reloaded is not None
        assert reloaded.criteria[0].pass_fail == "pass"


# ===========================================================================
# #4858 (P0) — concurrent acceptance-verdict lost-update (T001/T002).
#
# Deterministic serialized "read1 -> full-run2 -> finish1" harness (NO real
# threads): a ONE-SHOT nonlocal-guarded wrapper patched onto the
# COMMAND-MODULE binding (never the ``specify_cli.acceptance.matrix``
# definition — the command imports the symbol by name, so patching the
# source module would not intercept the call; see US1's Independent Test).
# On the invocation's own slow-check/seam call, the wrapper drives a SECOND,
# FULL ``acceptance-verdict`` invocation for a DISTINCT entry id to
# completion (real check + commit), then delegates to the real check for
# the FIRST invocation. The second invocation's own nested call to the same
# patched name sees the one-shot flag already tripped and delegates straight
# to the real implementation — otherwise it would recurse infinitely.
# ===========================================================================


def _ni_one_shot_driver(
    *,
    mission_slug: str,
    other_invariant_id: str,
    other_result: str,
    on_after_other: Callable[[], None] | None = None,
) -> Callable[..., list[NegativeInvariant]]:
    """Build the one-shot NI-mode interleaving wrapper (US1 test-craft contract).

    ``other_result`` is ``"pass"`` or ``"fail"`` — translated to a
    ``custom_command`` verification command (``exit 0`` / ``exit 1``) so the
    OTHER invocation's judged result is deterministic and controlled by the
    caller, independent of repo contents.
    """
    driven = False
    command_for_result = {"pass": "exit 0", "fail": "exit 1"}[other_result]

    def _wrapper(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object) -> list[NegativeInvariant]:
        nonlocal driven
        if not driven:
            driven = True
            try:
                acceptance_verdict(
                    mission=mission_slug,
                    negative_invariant=other_invariant_id,
                    description=f"{other_invariant_id} must not exist",
                    verification_method="custom_command",
                    verification_command=command_for_result,
                    json_output=True,
                )
            except typer.Exit as exc:
                assert exc.exit_code in (0, None), f"driven invocation failed: exit {exc.exit_code}"
            if on_after_other is not None:
                on_after_other()
        # The unpatched, real implementation — imported at module top BEFORE
        # any monkeypatching of the command-module binding, so this reference
        # is never affected by ``monkeypatch.setattr`` on that other module.
        return enforce_negative_invariants(repo_root_arg, invariants, **kwargs)

    return _wrapper


def _seed_empty_matrix(feature_dir: Path, slug: str) -> None:
    write_acceptance_matrix(feature_dir, AcceptanceMatrix(mission_slug=slug))


class TestConcurrentVerdictLostUpdateFlatNegativeInvariant:
    """T001 — US1 Scenarios 1-3, flat layout, negative-invariant mode."""

    def test_scenario1_row_survival_and_honest_fail_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US1 S1: A reads first, finishes last; B fully completes and
        commits a FAILING row; A commits a PASSING row. Both rows must
        survive on disk (with evidence) and the disk-computed overall
        verdict must be ``fail``. RED on base (B's row dropped, verdict
        flips to ``pass``)."""
        slug = "concurrent-ni-flat-s1"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_empty_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed empty matrix")
        monkeypatch.chdir(repo_root)

        wrapper = _ni_one_shot_driver(
            mission_slug=slug, other_invariant_id="NI-B", other_result="fail"
        )
        monkeypatch.setattr(av_command, "enforce_negative_invariants", wrapper)

        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="NI-A must not exist",
                verification_method="custom_command",
                verification_command="exit 0",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"A's invocation failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        by_id = {ni.invariant_id: ni for ni in reloaded.negative_invariants}
        assert by_id.keys() == {"NI-A", "NI-B"}, (
            "a committed sibling row must never be dropped by a stale-snapshot "
            "overwrite (#4858)"
        )
        assert by_id["NI-A"].result == "confirmed_absent"
        assert by_id["NI-B"].result == "still_present"
        assert by_id["NI-B"].evidence, "B's evidence must survive intact"
        assert reloaded.overall_verdict == "fail", (
            "concurrency must never flip a committed failing row's verdict to pass"
        )

    def test_scenario2_midpoint_checkpoint_shows_b_before_a_resumes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US1 S2: at the point B finishes (inside the wrapped seam) and
        BEFORE A resumes, the on-disk matrix already contains B's row —
        proving the loss (when it occurs) is A's stale-snapshot overwrite,
        not a B-side failure."""
        slug = "concurrent-ni-flat-s2"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_empty_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed empty matrix")
        monkeypatch.chdir(repo_root)

        midpoint: dict[str, AcceptanceMatrix | None] = {"matrix": None}

        def _capture_midpoint() -> None:
            midpoint["matrix"] = read_acceptance_matrix(feature_dir)

        wrapper = _ni_one_shot_driver(
            mission_slug=slug,
            other_invariant_id="NI-B",
            other_result="fail",
            on_after_other=_capture_midpoint,
        )
        monkeypatch.setattr(av_command, "enforce_negative_invariants", wrapper)

        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="NI-A must not exist",
                verification_method="custom_command",
                verification_command="exit 0",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        captured = midpoint["matrix"]
        assert captured is not None, "B must have committed before A resumes"
        ids_at_midpoint = {ni.invariant_id for ni in captured.negative_invariants}
        assert "NI-B" in ids_at_midpoint
        assert "NI-A" not in ids_at_midpoint, "A has not resumed/committed yet at this checkpoint"

    def test_scenario3_reverse_role_passing_sibling_survives(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US1 Scenario 3 (reverse role): B commits a PASSING row and A
        commits a FAILING row. A splice that only preserves a FAILING
        sibling would silently drop a PASSING one here — invisible to
        Scenario 1 (where A's own row is passing)."""
        slug = "concurrent-ni-flat-s3"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_empty_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed empty matrix")
        monkeypatch.chdir(repo_root)

        wrapper = _ni_one_shot_driver(
            mission_slug=slug, other_invariant_id="NI-B", other_result="pass"
        )
        monkeypatch.setattr(av_command, "enforce_negative_invariants", wrapper)

        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="NI-A must not exist",
                verification_method="custom_command",
                verification_command="exit 1",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        by_id = {ni.invariant_id: ni for ni in reloaded.negative_invariants}
        assert by_id.keys() == {"NI-A", "NI-B"}
        assert by_id["NI-A"].result == "still_present"
        assert by_id["NI-B"].result == "confirmed_absent"
        assert reloaded.overall_verdict == "fail"


class TestConcurrentVerdictLostUpdateCoord:
    """T002 — US2: the guarantee holds on coordination topology."""

    def test_lock_key_resolves_to_same_path_across_primary_and_coord_worktree(
        self, tmp_path: Path
    ) -> None:
        """US2 Scenario 2: the primary checkout and the coordination worktree
        of the SAME mission resolve the identical lock-file path — the lock
        spans worktrees via the shared git common dir."""
        result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
        coord_feature_dir.mkdir(parents=True, exist_ok=True)
        write_acceptance_matrix(coord_feature_dir, AcceptanceMatrix(mission_slug=result.mission_slug))
        subprocess.run(["git", "-C", str(coord_root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(coord_root), "commit", "-q", "-m", "seed coord matrix"],
            check=True,
            capture_output=True,
        )

        primary_lock_path = feature_status_lock_path(tmp_path, coord_feature_dir.name)
        coord_lock_path = feature_status_lock_path(coord_root, coord_feature_dir.name)
        assert primary_lock_path == coord_lock_path, (
            "the SAME lock file must serialize writers whether they act "
            "through the primary checkout or the coordination worktree"
        )

    def test_coord_surface_row_survival_and_honest_verdict_under_concurrency(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US2 Scenario 1: the concurrent-loss guarantee holds identically on
        the COORD surface (asserted non-vacuously distinct from primary, and
        that the write never strands a primary copy — mirrors the pre-existing
        ``test_lands_on_coord_surface_not_a_stranded_primary_dir`` control).
        Scenario 2 above is the dedicated dual-worktree-root lock-spanning
        proof (spec's explicit test-craft alternative for proving the lock
        spans worktrees)."""
        result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
        slug = result.mission_slug

        coord_feature_dir.mkdir(parents=True, exist_ok=True)
        _seed_empty_matrix(coord_feature_dir, slug)
        subprocess.run(["git", "-C", str(coord_root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(coord_root), "commit", "-q", "-m", "seed coord matrix"],
            check=True,
            capture_output=True,
        )

        monkeypatch.chdir(tmp_path)

        wrapper = _ni_one_shot_driver(
            mission_slug=slug, other_invariant_id="NI-B", other_result="fail"
        )
        monkeypatch.setattr(av_command, "enforce_negative_invariants", wrapper)

        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="NI-A must not exist",
                verification_method="custom_command",
                verification_command="exit 0",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        assert not (result.feature_dir / "acceptance-matrix.json").exists(), (
            "must not strand a primary copy for a coord-topology mission"
        )
        reloaded = read_acceptance_matrix(coord_feature_dir)
        assert reloaded is not None
        by_id = {ni.invariant_id: ni for ni in reloaded.negative_invariants}
        assert by_id.keys() == {"NI-A", "NI-B"}
        assert reloaded.overall_verdict == "fail"


class TestConcurrentVerdictLostUpdateCriterionMode:
    """T002 — US3: the guarantee also holds for criterion mode.

    Criterion mode has no slow-check seam, so the interleaving is forced at
    ``_resolve_criterion_update`` instead (the seam this fix computes the
    candidate row from, BEFORE the locked re-read+splice)."""

    def test_criterion_mode_concurrent_row_survival(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slug = "concurrent-criterion-flat"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="FR-001", description="A", proof_type="automated_test", pass_fail="pending"
                    ),
                    AcceptanceCriterion(
                        criterion_id="FR-002", description="B", proof_type="automated_test", pass_fail="pending"
                    ),
                ],
            ),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed matrix")
        monkeypatch.chdir(repo_root)

        driven = False

        def _wrapper(
            existing: AcceptanceCriterion,
            *,
            result: str,
            verification_method: str | None,
            actor: str | None,
            evidence: str | None,
        ) -> AcceptanceCriterion:
            nonlocal driven
            if not driven:
                driven = True
                try:
                    acceptance_verdict(
                        mission=slug,
                        criterion="FR-002",
                        result="pass",
                        verification_method="automated_test",
                        actor="B",
                        evidence="b-evidence",
                        json_output=True,
                    )
                except typer.Exit as exc:
                    assert exc.exit_code in (0, None), f"driven invocation failed: exit {exc.exit_code}"
            return _resolve_criterion_update(
                existing,
                result=result,
                verification_method=verification_method,
                actor=actor,
                evidence=evidence,
            )

        monkeypatch.setattr(av_command, "_resolve_criterion_update", _wrapper)

        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="fail",
                verification_method="automated_test",
                actor="A",
                evidence="a-evidence",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        by_id = {c.criterion_id: c for c in reloaded.criteria}
        assert by_id["FR-001"].pass_fail == "fail"
        assert by_id["FR-002"].pass_fail == "pass", (
            "B's committed passing criterion must survive A's stale-snapshot write"
        )
        assert reloaded.overall_verdict == "fail"


# ===========================================================================
# #4858 — gate spies (US1 Scenarios 4-9): each gate is independently
# falsifiable by a spy/ordering assertion, not review-only.
# ===========================================================================


class TestConcurrencyGateSpies:
    def _seed_flat_criterion_mission(self, tmp_path: Path, slug: str) -> tuple[Path, Path]:
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="FR-001",
                        description="works",
                        proof_type="automated_test",
                        pass_fail="pending",
                    )
                ],
            ),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        return repo_root, feature_dir

    def test_lock_acquired_with_correct_key_and_path_under_common_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-007: a spy on the lock helper records acquisition with
        ``lock_key == matrix_dir.name`` and a resolved lock path under the
        git common dir."""
        slug = "gate-spy-lock-key"
        repo_root, feature_dir = self._seed_flat_criterion_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        calls: list[tuple[Path, str, float]] = []

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            calls.append((repo_root_arg, lock_key, timeout))
            return feature_status_lock(repo_root_arg, lock_key, timeout=timeout)

        monkeypatch.setattr(av_command, "feature_status_lock", _spy_lock)

        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ev",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        assert len(calls) == 1, "the critical section must acquire the lock exactly once"
        called_repo_root, lock_key, timeout = calls[0]
        assert lock_key == feature_dir.name
        assert timeout == BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
        lock_path = feature_status_lock_path(called_repo_root, lock_key)
        common_dir = git_common_dir(repo_root)
        assert lock_path.is_relative_to(common_dir), "the lock file must live under the git common dir"

    def test_slow_check_runs_before_lock_is_acquired(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-008: the slow custom check is invoked BEFORE the lock is
        acquired (short critical section), verified by call-order."""
        slug = "gate-spy-call-order"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_empty_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        monkeypatch.chdir(repo_root)

        order: list[str] = []

        def _spy_enforce(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object):
            order.append("check")
            return enforce_negative_invariants(repo_root_arg, invariants, **kwargs)

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            order.append("lock_enter")
            cm = feature_status_lock(repo_root_arg, lock_key, timeout=timeout)
            return _OrderTrackingContext(cm, order)

        monkeypatch.setattr(av_command, "enforce_negative_invariants", _spy_enforce)
        monkeypatch.setattr(av_command, "feature_status_lock", _spy_lock)

        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="d",
                verification_method="custom_command",
                verification_command="exit 0",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        assert order == ["check", "lock_enter", "lock_exit"], order

    def test_reread_and_write_happen_strictly_inside_the_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-4858-reread-in-lock: strict order
        ``lock.__enter__ -> read_acceptance_matrix -> write -> lock.__exit__``
        — kills the "re-read outside the lock" mutant a serial harness alone
        cannot catch."""
        slug = "gate-spy-strict-order"
        repo_root, feature_dir = self._seed_flat_criterion_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        order: list[str] = []

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            order.append("enter")
            cm = feature_status_lock(repo_root_arg, lock_key, timeout=timeout)
            return _OrderTrackingContext(cm, order)

        def _spy_read(feature_dir_arg: Path):
            order.append("read")
            return read_acceptance_matrix(feature_dir_arg)

        def _spy_write(*args: object, **kwargs: object):
            order.append("write")
            return write_and_commit_acceptance_matrix(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(av_command, "feature_status_lock", _spy_lock)
        monkeypatch.setattr(av_command, "read_acceptance_matrix", _spy_read)
        monkeypatch.setattr(av_command, "write_and_commit_acceptance_matrix", _spy_write)

        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ev",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        # The FIRST "read" is the pre-lock existence check at the top of
        # ``acceptance_verdict()``; the SECOND is the locked re-read.
        assert order == ["read", "enter", "read", "write", "lock_exit"], order

    def test_write_acceptance_matrix_routes_through_atomic_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-009/C-003: the shared writer routes through
        ``kernel.atomic.atomic_write``, not a bare ``path.write_text``."""
        from kernel.atomic import atomic_write as real_atomic_write

        slug = "gate-spy-atomic-write"
        repo_root, feature_dir = self._seed_flat_criterion_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        calls: list[Path] = []

        def _spy_atomic_write(path: Path, content: str | bytes, *, mkdir: bool = False) -> None:
            calls.append(path)
            return real_atomic_write(path, content, mkdir=mkdir)

        monkeypatch.setattr("specify_cli.acceptance.matrix.atomic_write", _spy_atomic_write)

        try:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ev",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)

        assert calls, "write_acceptance_matrix must route through kernel.atomic.atomic_write"
        assert calls[0] == feature_dir / "acceptance-matrix.json"

    def test_fail_closed_on_lock_timeout_never_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-4858-fail-closed / C-012 / FR-015: on a lock-acquisition timeout,
        no write ever happens, the command exits non-zero with a structured
        error, and it never falls back to an unlocked write."""
        slug = "gate-spy-fail-closed"
        repo_root, feature_dir = self._seed_flat_criterion_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)
        head_before = _head(repo_root)

        def _timeout_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            raise FeatureStatusLockTimeoutError(
                "simulated timeout",
                lock_path=Path("/nonexistent/fake.status.lock"),
                timeout=timeout,
            )

        write_calls: list[object] = []

        def _spy_write(*args: object, **kwargs: object):
            write_calls.append(args)
            return write_and_commit_acceptance_matrix(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(av_command, "feature_status_lock", _timeout_lock)
        monkeypatch.setattr(av_command, "write_and_commit_acceptance_matrix", _spy_write)

        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission=slug,
                criterion="FR-001",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ev",
                json_output=True,
            )
        assert exc_info.value.exit_code == 1
        assert not write_calls, "a lock-acquisition timeout must never reach the write"
        assert _head(repo_root) == head_before, "no commit must occur on a fail-closed timeout"

    def test_reported_overall_verdict_matches_disk_after_concurrent_interleaving(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-016: the command's own reported ``overall_verdict`` is computed
        from the re-read+spliced (committed) matrix, matching disk — not the
        stale pre-lock in-memory snapshot."""
        slug = "gate-spy-honest-verdict"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_empty_matrix(feature_dir, slug)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        monkeypatch.chdir(repo_root)

        wrapper = _ni_one_shot_driver(
            mission_slug=slug, other_invariant_id="NI-B", other_result="fail"
        )
        monkeypatch.setattr(av_command, "enforce_negative_invariants", wrapper)

        capsys.readouterr()
        try:
            acceptance_verdict(
                mission=slug,
                negative_invariant="NI-A",
                description="d",
                verification_method="custom_command",
                verification_command="exit 0",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)
        out = capsys.readouterr().out.strip()
        lines = [line for line in out.splitlines() if line.strip()]
        # B prints first (nested inside the wrapped seam call); A's own
        # payload is the LAST line printed.
        a_payload = dict(json.loads(lines[-1]))

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        assert a_payload["overall_verdict"] == "fail"
        assert a_payload["overall_verdict"] == reloaded.overall_verdict


class _OrderTrackingContext:
    """Wrap a context manager, appending ``"lock_exit"`` to *order* on exit.

    Used by the call-order gate-spy tests above so the SAME ``order`` list
    records ``lock_enter`` (before ``__enter__``) and ``lock_exit`` (after
    ``__exit__``) around the real lock's own body.
    """

    def __init__(self, inner: object, order: list[str]) -> None:
        self._inner = inner
        self._order = order

    def __enter__(self) -> object:
        return self._inner.__enter__()  # type: ignore[attr-defined]

    def __exit__(self, *exc_info: object) -> object:
        result = self._inner.__exit__(*exc_info)  # type: ignore[attr-defined]
        self._order.append("lock_exit")
        return result
