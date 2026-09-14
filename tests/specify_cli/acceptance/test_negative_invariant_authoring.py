"""WP05 (post-merge-write-authoring-finish-01KYRRM5): T019-T025 (#2318 authoring finish).

Covers:

* T019/T020 — ``acceptance-verdict --negative-invariant`` registers AND
  executes a :class:`~specify_cli.acceptance.matrix.NegativeInvariant`
  through the deterministic CLI (zero hand-edited JSON), reusing the
  existing :func:`~specify_cli.acceptance.matrix.enforce_negative_invariants`
  engine verbatim (never reimplemented).
* T021 — ``AcceptanceMatrix.from_dict`` raises the typed
  :class:`~specify_cli.acceptance.matrix.AcceptanceMatrixParseError` on a
  malformed item instead of an unhandled ``TypeError`` (the actual mgifford
  ``accept --diagnose`` crash-before-diagnosis defect), and the
  ``accept --diagnose`` CLI layer catches it, reports which item + why, and
  exits non-zero — with gate behaviour for well-formed input unchanged.
  RED-FIRST: ``TestDiagnoseHardening`` pins the pre-existing entry point
  (``AcceptanceMatrix.from_dict``) directly, and drives the real ``accept()``
  CLI function end to end.
* T022 — SC-007 pin: an all-pass / no-negative-invariant matrix persists a
  fresh ``overall_verdict: pass``, not a stale ``pending`` (samuelgoff).
  ALREADY fixed upstream — commit ``b04da00e1`` (mission
  ``write-side-seam-matrix-tracer-01KYP3MH`` T016) is an ANCESTOR of this
  mission's own base commit (verified via ``git merge-base --is-ancestor``),
  so the fix predates this WP's work. This class PINS the behaviour for
  SC-007; it is not a red-first fix (there was no red left to produce).
* T023 — the accept mission-step prompt SOURCE drives ``acceptance-verdict``
  via an executable invocation in its Steps section (structural check, not a
  prose-mention check).
* T024 — ``acceptance/matrix.py``'s write path uses the WP04 ``stage=``
  thunk (no pre-staging before the routability probe); a refused write
  leaves zero untracked residue (paula M2).
* T025 — SC-006/SC-007 end-to-end integration coverage.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    AcceptanceMatrixParseError,
    NegativeInvariant,
    read_acceptance_matrix,
    write_acceptance_matrix,
    write_and_commit_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.cli.commands.agent.acceptance_verdict import acceptance_verdict
from specify_cli.git.protection_policy import ProtectionPolicy

# Reused verbatim (not duplicated) — the shared flat-mission fixture builder
# WP04's own acceptance-verdict test module already establishes.
from tests.specify_cli.acceptance.test_acceptance_verdict_command import (
    _git,
    _init_flat_mission,
)

# Reused verbatim — the real-git "unroutable mission" fixture WP04's write-seam
# thunk regression suite already establishes (a coord topology declaring a
# coordination_branch that was never materialized -- the FR-011 zero-write
# scenario), so this suite does not hand-roll a second one.
from tests.specify_cli.coordination.test_write_seam_thunk import (
    _build_coord_branch_deleted_fixture,
)

# Reused verbatim — the accept-ready, mission_id-bearing lane fixture the
# accept --no-commit CLI contract suite already establishes (tasks dir +
# status event log + lanes.json + a real mission_id resolve_mission_handle
# can find); it is what actually reaches ``_check_lane_gates`` ->
# ``_evaluate_acceptance_matrix`` through the real CLI entry point.
from tests.specify_cli.test_accept_no_commit_readonly import (
    _CLI_SLUG as _ACCEPT_READY_SLUG,
)
from tests.specify_cli.test_accept_no_commit_readonly import (
    _create_acceptready_lane_feature,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _seed_matrix(feature_dir: Path, slug: str) -> None:
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


def _seed_commit(repo_root: Path) -> None:
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed acceptance-matrix")


# ===========================================================================
# T019/T020 — acceptance-verdict --negative-invariant registers and executes
# ===========================================================================


class TestNegativeInvariantRegisterAndExecute:
    def test_register_and_execute_confirmed_absent_zero_hand_edited_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-007/FR-008/SC-006: registering a negative invariant through the
        CLI persists a well-shaped ``NegativeInvariant`` (no hand-edited
        JSON), and T020 executes it via the real
        ``enforce_negative_invariants`` engine — a pattern genuinely absent
        from this isolated fixture repo confirms ``confirmed_absent``."""
        slug = "ni-register-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="FR-001",
                        description="the feature behaves as specified",
                        proof_type="automated_test",
                        pass_fail="pass",
                    )
                ],
            ),
        )
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        try:
            acceptance_verdict(
                mission=slug,
                criterion=None,
                result=None,
                verification_method="grep_absence",
                actor="tester",
                evidence=None,
                negative_invariant="NI-001",
                description="Legacy shim must not reappear",
                verification_command="a-pattern-that-genuinely-does-not-exist-anywhere-xyz123",
                scope=None,
                execute=True,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        assert len(reloaded.negative_invariants) == 1
        ni = reloaded.negative_invariants[0]
        assert ni.invariant_id == "NI-001"
        assert ni.description == "Legacy shim must not reappear"
        assert ni.verification_method == "grep_absence"
        assert ni.result == "confirmed_absent", "T020: executed via the real engine, not just registered"
        assert reloaded.overall_verdict == "pass"

    def test_execute_records_still_present_when_pattern_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A well-formed-but-FAILING invariant is judged ``still_present``
        (distinct from the malformed case T021 covers) -- proves T020
        genuinely runs the check, it does not just stamp a happy default."""
        slug = "ni-still-present-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, slug)
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        try:
            acceptance_verdict(
                mission=slug,
                criterion=None,
                result=None,
                verification_method="grep_absence",
                actor="tester",
                evidence=None,
                negative_invariant="NI-002",
                description=f"{slug} must not appear in its own meta.json",
                verification_command=slug,
                scope=None,
                execute=True,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        ni = next(n for n in reloaded.negative_invariants if n.invariant_id == "NI-002")
        assert ni.result == "still_present"
        assert reloaded.overall_verdict == "fail"

    def test_register_without_execute_leaves_result_pending(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-execute`` registers the row without judging it (FR-007
        without FR-008) -- the row is well-shaped but stays ``pending``."""
        slug = "ni-register-only-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, slug)
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        try:
            acceptance_verdict(
                mission=slug,
                criterion=None,
                result=None,
                verification_method="grep_absence",
                actor=None,
                evidence=None,
                negative_invariant="NI-003",
                description="Judged later",
                verification_command="whatever-pattern",
                scope=None,
                execute=False,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        ni = next(n for n in reloaded.negative_invariants if n.invariant_id == "NI-003")
        assert ni.result == "pending"

    def test_re_register_same_id_replaces_row_not_duplicates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slug = "ni-reregister-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, slug)
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        for description in ("first description", "corrected description"):
            try:
                acceptance_verdict(
                    mission=slug,
                    criterion=None,
                    result=None,
                    verification_method="grep_absence",
                    actor=None,
                    evidence=None,
                    negative_invariant="NI-004",
                    description=description,
                    verification_command="a-pattern-that-genuinely-does-not-exist-xyz789",
                    scope=None,
                    execute=True,
                    json_output=True,
                )
            except typer.Exit as exc:
                assert exc.exit_code in (0, None), f"command failed: exit {exc.exit_code}"

        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        matching = [ni for ni in reloaded.negative_invariants if ni.invariant_id == "NI-004"]
        assert len(matching) == 1, "re-registering the same id must REPLACE the row, not duplicate it"
        assert matching[0].description == "corrected description"


class TestNegativeInvariantFlagValidation:
    def test_criterion_and_negative_invariant_are_mutually_exclusive(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission="whatever",
                criterion="FR-001",
                result="pass",
                verification_method=None,
                actor=None,
                evidence=None,
                negative_invariant="NI-001",
                description="x",
                verification_command=None,
                scope=None,
                execute=True,
                json_output=False,
            )
        assert exc_info.value.exit_code == 2

    def test_missing_mode_selector_is_rejected(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission="whatever",
                criterion=None,
                result=None,
                verification_method=None,
                actor=None,
                evidence=None,
                negative_invariant=None,
                description=None,
                verification_command=None,
                scope=None,
                execute=True,
                json_output=False,
            )
        assert exc_info.value.exit_code == 2

    def test_negative_invariant_requires_description(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission="whatever",
                criterion=None,
                result=None,
                verification_method="grep_absence",
                actor=None,
                evidence=None,
                negative_invariant="NI-001",
                description=None,
                verification_command=None,
                scope=None,
                execute=True,
                json_output=False,
            )
        assert exc_info.value.exit_code == 2

    def test_negative_invariant_requires_verification_method(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            acceptance_verdict(
                mission="whatever",
                criterion=None,
                result=None,
                verification_method=None,
                actor=None,
                evidence=None,
                negative_invariant="NI-001",
                description="x",
                verification_command=None,
                scope=None,
                execute=True,
                json_output=False,
            )
        assert exc_info.value.exit_code == 2


# ===========================================================================
# T021 — accept --diagnose hardening (mgifford: crash before diagnosis)
# ===========================================================================


class TestDiagnoseHardening:
    def test_from_dict_raises_typed_error_for_malformed_negative_invariant(self) -> None:
        """RED-FIRST (before the fix): pins the ACTUAL pre-existing entry
        point, ``AcceptanceMatrix.from_dict``, directly. Before T021 this
        raised an unhandled ``TypeError`` (the mgifford crash-before-
        diagnosis defect); it must now raise the TYPED
        ``AcceptanceMatrixParseError`` naming the item and section."""
        data = {
            "mission_slug": "malformed-ni-mission",
            "criteria": [],
            "negative_invariants": [
                {"description": "missing invariant_id and verification_method"}
            ],
        }
        with pytest.raises(AcceptanceMatrixParseError) as exc_info:
            AcceptanceMatrix.from_dict(data)
        err = exc_info.value
        assert err.section == "negative_invariants"
        assert err.item_index == 0

    def test_from_dict_raises_typed_error_for_malformed_criterion(self) -> None:
        """The SAME hardening applies to a malformed ``criteria`` entry
        (renata M2: both sections, not only negative_invariants)."""
        data = {
            "mission_slug": "malformed-criterion-mission",
            "criteria": [{"description": "missing criterion_id and proof_type"}],
            "negative_invariants": [],
        }
        with pytest.raises(AcceptanceMatrixParseError) as exc_info:
            AcceptanceMatrix.from_dict(data)
        err = exc_info.value
        assert err.section == "criteria"
        assert err.item_index == 0

    def test_from_dict_still_loads_well_formed_matrix_unchanged(self) -> None:
        """renata M2: gate behaviour for WELL-FORMED input is unchanged —
        the shared load path (``gates_core.py`` / ``post_consolidation.py``)
        is not weakened by this hardening."""
        matrix = AcceptanceMatrix(
            mission_slug="well-formed-mission",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001", description="x", proof_type="automated_test", pass_fail="pass"
                )
            ],
            negative_invariants=[
                NegativeInvariant(
                    invariant_id="NI-001", description="y", verification_method="grep_absence"
                )
            ],
        )
        reloaded = AcceptanceMatrix.from_dict(matrix.to_dict())
        assert reloaded.criteria[0].criterion_id == "FR-001"
        assert reloaded.negative_invariants[0].invariant_id == "NI-001"
        assert reloaded.overall_verdict == matrix.overall_verdict

    def test_diagnose_cli_reports_malformed_invariant_instead_of_crashing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-009/SC-006: ``spec-kitty accept --diagnose`` on a malformed
        negative invariant is REPORTED (which item, why) and exits non-zero
        with ZERO unhandled exceptions -- the actual mgifford defect, driven
        through the real CLI entry point. Before the fix this test fails
        with an uncaught ``TypeError`` (not a clean ``typer.Exit``), proving
        the crash for the right reason."""
        repo_root = (tmp_path / "repo").resolve()
        repo_root.mkdir()
        feature_dir = _create_acceptready_lane_feature(repo_root)
        slug = _ACCEPT_READY_SLUG
        # A malformed on-disk matrix -- the exact shape a corrupted write or
        # a hand-edit could produce; never a hand-edit performed BY this test
        # of a matrix the CLI produced, just the fixture for the crash path.
        (feature_dir / "acceptance-matrix.json").write_text(
            json.dumps(
                {
                    "mission_slug": slug,
                    "criteria": [],
                    "negative_invariants": [{"description": "malformed: no invariant_id"}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        capsys.readouterr()
        with pytest.raises(typer.Exit) as exc_info:
            accept(
                mission=slug,
                mode="auto",
                actor=None,
                test=[],
                json_output=True,
                lenient=False,
                no_commit=False,
                diagnose=True,
                allow_fail=False,
                normalize_encoding=False,
            )
        assert exc_info.value.exit_code == 1
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert "error" in payload
        assert "negative_invariants[0]" in payload["error"], payload["error"]

    def test_diagnose_cli_still_reports_readiness_for_well_formed_matrix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Contrast case (renata M2): a well-formed matrix's ``--diagnose``
        pass is completely unaffected by the hardening."""
        repo_root = (tmp_path / "repo").resolve()
        repo_root.mkdir()
        _create_acceptready_lane_feature(repo_root)
        slug = _ACCEPT_READY_SLUG
        monkeypatch.chdir(repo_root)

        capsys.readouterr()
        with pytest.raises(typer.Exit) as exc_info:
            accept(
                mission=slug,
                mode="auto",
                actor=None,
                test=[],
                json_output=True,
                lenient=False,
                no_commit=False,
                diagnose=True,
                allow_fail=False,
                normalize_encoding=False,
            )
        assert exc_info.value.exit_code == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload.get("diagnose") is True


# ===========================================================================
# T022 — SC-007 pin: fresh overall_verdict persisted on the all-pass /
# no-negative-invariant branch. ALREADY FIXED upstream (see module docstring)
# ===========================================================================


class TestFreshVerdictPersistPin:
    def test_all_pass_no_invariants_persists_fresh_pass_not_stale_pending(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC-007 (samuelgoff): an all-pass / no-negative-invariant accept
        persists ``overall_verdict: pass``, never a stale ``pending``. This
        PINS a fix already landed upstream of this mission's base commit
        (see module docstring); it is not this WP's own red-first repair."""
        from specify_cli.acceptance.gates_core import _evaluate_acceptance_matrix

        slug = "sc007-pin-mission"
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)

        stale = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001", description="x", proof_type="automated_test", pass_fail="pending"
                )
            ],
        )
        write_acceptance_matrix(feature_dir, stale)
        assert json.loads((feature_dir / "acceptance-matrix.json").read_text())["overall_verdict"] == "pending"

        fresh = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001", description="x", proof_type="automated_test", pass_fail="pass"
                )
            ],
            negative_invariants=[],
        )
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: fresh)

        activity_issues: list[str] = []
        _evaluate_acceptance_matrix(tmp_path, feature_dir, activity_issues, [], [], mutate_matrix=True)

        assert activity_issues == []
        persisted = json.loads((feature_dir / "acceptance-matrix.json").read_text())
        assert persisted["overall_verdict"] == "pass"


# ===========================================================================
# T023 — accept prompt SOURCE drives acceptance-verdict (structural check)
# ===========================================================================


class TestAcceptPromptDrivesAcceptanceVerdict:
    _PROMPT_PATH = (
        _REPO_ROOT
        / "packs"
        / "built-in"
        / "missions"
        / "mission-steps"
        / "software-dev"
        / "accept"
        / "prompt.md"
    )

    def test_prompt_source_exists_at_the_canonical_path(self) -> None:
        assert self._PROMPT_PATH.is_file(), (
            f"expected the accept mission-step prompt SOURCE at {self._PROMPT_PATH} "
            "(never a generated agent copy)"
        )

    def test_prompt_source_contains_executable_acceptance_verdict_invocation(self) -> None:
        """priti M2: the prompt must DRIVE the CLI -- an executable
        invocation inside a fenced code block in the Steps section -- not
        merely mention it in prose."""
        text = self._PROMPT_PATH.read_text(encoding="utf-8")
        assert "## Steps" in text
        steps_section = text.split("## Steps", 1)[1]
        code_blocks = re.findall(r"```bash\n(.*?)```", steps_section, re.DOTALL)
        assert code_blocks, "expected at least one fenced bash block in the Steps section"
        assert any(
            "spec-kitty agent mission acceptance-verdict" in block for block in code_blocks
        ), "accept prompt SOURCE must DRIVE acceptance-verdict via an executable invocation"
        # Both modes (criterion + negative-invariant) must be driven, not just
        # mentioned -- the "zero hand-edited JSON" guarantee covers both.
        assert any("--criterion" in block for block in code_blocks)
        assert any("--negative-invariant" in block for block in code_blocks)

    def test_prompt_source_forbids_hand_editing_the_matrix(self) -> None:
        text = self._PROMPT_PATH.read_text(encoding="utf-8")
        assert "hand-edit" in text.lower()


# ===========================================================================
# T024 — acceptance/matrix.py write path uses the WP04 stage= thunk
# ===========================================================================


class TestWriteAndCommitUsesStagingThunk:
    def test_write_and_commit_passes_stage_not_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T024: the write must go through ``write_artifact``'s ``stage=``
        thunk (WP04's no-residue contract) -- never the historical
        pre-staged ``files=`` contract, and the file must not exist on disk
        until the thunk is actually invoked."""
        captured: dict[str, object] = {}

        def _fake_write_artifact(**kwargs: object):
            captured.update(kwargs)
            from specify_cli.coordination.write_seam import WriteSeamResult

            return WriteSeamResult(
                status="committed",
                entry_id=str(kwargs["entry_id"]),
                destination_surface="main",
                commit_hash="deadbee",
            )

        monkeypatch.setattr(
            "specify_cli.coordination.write_seam.write_artifact", _fake_write_artifact
        )

        matrix_dir = tmp_path / "kitty-specs" / "thunk-mission"
        matrix_dir.mkdir(parents=True)
        matrix = AcceptanceMatrix(
            mission_slug="thunk-mission",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001", description="x", proof_type="automated_test", pass_fail="pass"
                )
            ],
        )
        policy = ProtectionPolicy.resolve(tmp_path)

        result = write_and_commit_acceptance_matrix(
            tmp_path,
            "thunk-mission",
            matrix_dir,
            matrix,
            entry_id="FR-001",
            message="chore: record",
            policy=policy,
        )

        assert result.status == "committed"
        assert "files" not in captured, "matrix.py must pass stage=, not the historical files= contract"
        assert not (matrix_dir / "acceptance-matrix.json").exists(), (
            "must not pre-stage before write_artifact's routability probe"
        )

        stage = captured["stage"]
        assert callable(stage)
        files = stage()
        assert isinstance(files, tuple) and len(files) == 1
        staged_path = files[0]
        assert staged_path == matrix_dir / "acceptance-matrix.json"
        assert staged_path.exists(), "invoking the thunk must materialize the file on disk"
        assert captured["primary_paths_created_this_invocation"] == frozenset({staged_path})


class TestRefusedWriteLeavesNoResidue:
    def test_refused_write_via_matrix_py_leaves_zero_untracked(self, tmp_path: Path) -> None:
        """paula M2 -- "refused write via matrix.py -> 0 untracked files"
        regression. Real git, real unroutable mission (a coord topology
        declaring a ``coordination_branch`` that was never materialized --
        the same FR-011 fixture ``test_write_seam_thunk.py`` uses for the
        tracer writer)."""
        repo = tmp_path / "repo"
        mission_slug = _build_coord_branch_deleted_fixture(repo)
        policy = ProtectionPolicy.resolve(repo)
        matrix_dir = repo / "kitty-specs" / mission_slug

        matrix = AcceptanceMatrix(
            mission_slug=mission_slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001", description="x", proof_type="automated_test", pass_fail="pass"
                )
            ],
        )

        result = write_and_commit_acceptance_matrix(
            repo,
            mission_slug,
            matrix_dir,
            matrix,
            entry_id="FR-001",
            message="chore: should be refused",
            policy=policy,
        )

        assert result.status == "refused", result
        assert not (matrix_dir / "acceptance-matrix.json").exists(), (
            "a refused write must leave zero untracked residue"
        )
        status = _git(repo, "status", "--porcelain", "--untracked-files=all")
        assert status.stdout.strip() == "", f"expected a clean tree, got: {status.stdout!r}"


# ===========================================================================
# T025 — SC-006 end-to-end: full accept pass incl. a negative invariant
# ===========================================================================


class TestFullAcceptPassWithNegativeInvariantSC006:
    def test_full_accept_pass_registers_ni_via_cli_and_persists_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC-006: an agent completes a full accept pass including a
        negative invariant with ZERO hand-edited JSON -- the invariant is
        registered/executed purely through ``acceptance-verdict`` (never
        constructed as a dataclass literal by this test), then the whole
        matrix converges to ``overall_verdict: pass`` after ``accept
        --no-commit`` re-resolves it."""
        slug = "sc006-full-accept-mission"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC1",
                        description="feature behaves as specified",
                        proof_type="automated_test",
                        pass_fail="pending",
                    )
                ],
            ),
        )
        _seed_commit(repo_root)
        monkeypatch.chdir(repo_root)

        # Step 1: record the criterion, exactly as the accept prompt's Step 1
        # instructs -- through acceptance-verdict, zero hand-edited JSON.
        try:
            acceptance_verdict(
                mission=slug,
                criterion="AC1",
                result="pass",
                verification_method="automated_test",
                actor="tester",
                evidence="ci-run-1",
                negative_invariant=None,
                description=None,
                verification_command=None,
                scope=None,
                execute=True,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"criterion recording failed: exit {exc.exit_code}"

        # Step 1 (cont.): register + execute a negative invariant that is
        # genuinely absent from this isolated fixture repo.
        try:
            acceptance_verdict(
                mission=slug,
                criterion=None,
                result=None,
                verification_method="grep_absence",
                actor=None,
                evidence=None,
                negative_invariant="NI-SC006",
                description="Legacy pattern must not reappear",
                verification_command="a-pattern-genuinely-absent-sc006-xyz",
                scope=None,
                execute=True,
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"negative-invariant recording failed: exit {exc.exit_code}"

        reloaded_before_accept = read_acceptance_matrix(feature_dir)
        assert reloaded_before_accept is not None
        assert reloaded_before_accept.negative_invariants[0].result == "confirmed_absent"
        assert reloaded_before_accept.overall_verdict == "pass"

        # Step 2: run the accept gate itself (--no-commit -- this repo is not
        # a full lane-based mission; the acceptance-matrix re-resolution path
        # is exercised the same way regardless).
        exit_code: int | None = 0
        try:
            accept(
                mission=slug,
                mode="checklist",
                actor="tester",
                test=[],
                json_output=True,
                lenient=True,
                no_commit=True,
                diagnose=False,
                allow_fail=True,
                normalize_encoding=False,
            )
        except typer.Exit as exc:
            exit_code = exc.exit_code
        assert exit_code in (0, 1), f"accept checklist crashed unexpectedly: exit {exit_code}"

        reloaded_after_accept = read_acceptance_matrix(feature_dir)
        assert reloaded_after_accept is not None
        assert reloaded_after_accept.overall_verdict == "pass", (
            "SC-006/SC-007: the full pass (incl. the CLI-registered negative "
            "invariant) must converge to a fresh 'pass', not a stale value"
        )
        assert reloaded_after_accept.negative_invariants[0].invariant_id == "NI-SC006"
        assert reloaded_after_accept.negative_invariants[0].result == "confirmed_absent"
