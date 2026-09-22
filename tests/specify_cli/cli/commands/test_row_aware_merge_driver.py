"""WP11 (FR-008 / #2482 / #2970) -- row-aware, base-aware matrix merge drivers.

Covers, per ``kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/
merge-driver-algorithm.md``:

- T039: a RED-FIRST #2970 (S2083 path-injection) repro driving the real,
  registered CLI entrypoint (``specify_cli._get_app()`` via
  ``typer.testing.CliRunner`` -- an in-process call through the actual argv
  parsing layer, not a synthetic mirror of the scanner's finding count).
- T042: driver-unit tests over synthetic ``%O``/``%A``/``%B`` proving the
  algorithm itself (disjoint-row union, stale-residue drop, same-field
  conflict, intra-side duplicate-key guard, byte-determinism) -- these pass
  regardless of WP01/durability.
- T045: the SC-003 durability-integration regression, seeded from a REAL git
  merge-base blob (not a synthetic base, not WP01's lane SHA) for both the
  coord-topology and flat-topology shapes -- proving zero clobber on two
  divergent sides writing disjoint rows.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli import _get_app
from specify_cli.cli.commands.merge_driver import (
    RowMatrixMergeError,
    _canonicalize_issue_ref,
    _resolve_merge_driver_paths,
    merge_driver_acceptance_matrix,
    merge_driver_issue_matrix,
    reconcile_acceptance_matrix_documents,
    reconcile_issue_matrix_documents,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------------
# T039 -- #2970 red-first path-injection regression (real main(argv) entry)
# ---------------------------------------------------------------------------
#
# Grounded in the empirically-verified git contract (see merge_driver.py's
# module docstring): every legitimate ``%O``/``%A``/``%B`` invocation -- real
# git AND every driver-unit test in this module -- keeps the three paths as
# siblings in ONE directory. These tests drive the driver's REAL registered
# CLI command (``specify_cli._get_app()``, the same Typer app
# ``spec-kitty merge-driver-*`` resolves to) through ``CliRunner.invoke`` --
# the actual argv-parsing entrypoint, not a hand-called Python function --
# with an untrusted argument that escapes that directory, and asserts refusal
# without any read/write leaking outside the intended location.


@pytest.mark.parametrize(
    "driver_command",
    [
        "merge-driver-event-log",
        "merge-driver-meta",
        "merge-driver-traces",
        "merge-driver-acceptance-matrix",
        "merge-driver-issue-matrix",
    ],
)
def test_merge_driver_refuses_relative_traversal_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, driver_command: str
) -> None:
    """#2970: a ``../`` traversal argument is refused before any I/O (all 5 drivers)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "O").write_text("", encoding="utf-8")
    (tmp_path / "A").write_text("SENTINEL-UNTOUCHED", encoding="utf-8")
    escape_dir = tmp_path.parent / f"escape-sibling-{tmp_path.name}"
    escape_dir.mkdir(exist_ok=True)
    escape_target = escape_dir / "theirs"
    escape_target.write_text("EVIL", encoding="utf-8")
    traversal_arg = f"../{escape_dir.name}/theirs"

    result = runner.invoke(_get_app(), [driver_command, "O", "A", traversal_arg])

    assert result.exit_code != 0, result.output
    assert (tmp_path / "A").read_text(encoding="utf-8") == "SENTINEL-UNTOUCHED"
    assert escape_target.read_text(encoding="utf-8") == "EVIL"


@pytest.mark.parametrize(
    "driver_command",
    [
        "merge-driver-event-log",
        "merge-driver-meta",
        "merge-driver-traces",
        "merge-driver-acceptance-matrix",
        "merge-driver-issue-matrix",
    ],
)
def test_merge_driver_refuses_absolute_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, driver_command: str
) -> None:
    """#2970: an absolute-path argument (e.g. ``/etc/...``-shaped) outside the
    working directory is refused before any read/write (all 5 drivers)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "O").write_text("", encoding="utf-8")
    (tmp_path / "A").write_text("SENTINEL-UNTOUCHED", encoding="utf-8")
    absolute_escape = tmp_path.parent / f"absolute-escape-{tmp_path.name}"
    absolute_escape.write_text("EVIL", encoding="utf-8")

    result = runner.invoke(_get_app(), [driver_command, "O", "A", str(absolute_escape)])

    assert result.exit_code != 0, result.output
    assert (tmp_path / "A").read_text(encoding="utf-8") == "SENTINEL-UNTOUCHED"
    assert absolute_escape.read_text(encoding="utf-8") == "EVIL"


def test_merge_driver_accepts_sibling_paths_regardless_of_shape(tmp_path: Path) -> None:
    """The path guard is a pure sibling-directory check: legitimate invocations
    (real git temp files, every driver-unit test's ``tmp_path`` siblings) are
    never refused."""
    base, ours, theirs = tmp_path / "O", tmp_path / "nested-name.json", tmp_path / "B"
    resolved = _resolve_merge_driver_paths(str(base), str(ours), str(theirs))
    assert resolved == (base.resolve(), ours.resolve(), theirs.resolve())


def test_merge_driver_path_guard_rejects_mismatched_parent(tmp_path: Path) -> None:
    sibling_dir = tmp_path / "elsewhere"
    sibling_dir.mkdir()
    with pytest.raises(Exception, match="path-injection"):
        _resolve_merge_driver_paths(
            str(tmp_path / "O"), str(tmp_path / "A"), str(sibling_dir / "B")
        )


# ---------------------------------------------------------------------------
# T042 -- issue-matrix.json driver-unit tests (synthetic %O)
# ---------------------------------------------------------------------------


def _issue_doc(rows: dict[str, dict[str, object]]) -> dict[str, object]:
    return {"schema_version": 1, "rows": rows}


def test_issue_matrix_disjoint_row_union_no_clobber() -> None:
    """Two lanes writing DIFFERENT keys union without clobbering either (#2482)."""
    base = _issue_doc({})
    ours = _issue_doc({"#100": {"verdict": "fixed", "evidence_ref": "a"}})
    theirs = _issue_doc({"#200": {"verdict": "wontfix", "evidence_ref": "b"}})

    merged = reconcile_issue_matrix_documents(base, ours, theirs)

    assert set(merged["rows"]) == {"#100", "#200"}
    assert merged["rows"]["#100"]["verdict"] == "fixed"
    assert merged["rows"]["#200"]["verdict"] == "wontfix"


def test_issue_matrix_stale_residue_dropped_when_unchanged_on_other_side() -> None:
    """A base row deleted on one side, untouched on the other, is DROPPED
    (delete-vs-stale disambiguation: "absent on one side, unchanged on the
    other -> intentional delete")."""
    row: dict[str, object] = {"verdict": "unknown", "evidence_ref": "<link or commit>"}
    base = _issue_doc({"#100": row})
    ours = _issue_doc({})  # ours deleted #100
    theirs = _issue_doc({"#100": dict(row)})  # theirs left it byte-identical

    merged = reconcile_issue_matrix_documents(base, ours, theirs)

    assert merged["rows"] == {}


def test_issue_matrix_stale_side_does_not_resurrect_a_real_change() -> None:
    """A base row deleted on one side, CHANGED on the other, keeps the change
    ("a stale non-edit does not resurrect-then-delete")."""
    base = _issue_doc({"#100": {"verdict": "unknown", "evidence_ref": "x"}})
    ours = _issue_doc({})  # ours deleted #100
    theirs = _issue_doc({"#100": {"verdict": "fixed", "evidence_ref": "commit abc"}})

    merged = reconcile_issue_matrix_documents(base, ours, theirs)

    assert merged["rows"]["#100"]["verdict"] == "fixed"


def test_issue_matrix_same_field_divergence_raises_fail_closed() -> None:
    """Both sides change the SAME field (``verdict``, unknown -> fixed/wontfix)
    to different values from base: neither side silently wins, and the merge
    fails closed by raising rather than embedding a conflict marker into the
    verdict-bearing document (fail-closed contract, #4880 / amended ADR
    2026-07-23-2)."""
    base = _issue_doc({"#100": {"verdict": "unknown", "evidence_ref": "x"}})
    ours = _issue_doc({"#100": {"verdict": "fixed", "evidence_ref": "x"}})
    theirs = _issue_doc({"#100": {"verdict": "wontfix", "evidence_ref": "x"}})

    with pytest.raises(RowMatrixMergeError, match="verdict"):
        reconcile_issue_matrix_documents(base, ours, theirs)


def test_issue_matrix_authored_verdict_beats_unknown_sentinel_no_raise() -> None:
    """An UNSET sentinel (``verdict == "unknown"``) is not an authored value: it
    yields to the authored side instead of failing closed. This is the common
    lane-merge case — one lane recorded a verdict, the other never did — and it
    must NOT abort the merge (#4880 sentinel-yield refinement)."""
    base = _issue_doc({})
    ours = _issue_doc({"#100": {"verdict": "verified-already-fixed", "evidence_ref": "x"}})
    theirs = _issue_doc({"#100": {"verdict": "unknown", "evidence_ref": "x"}})

    merged = reconcile_issue_matrix_documents(base, ours, theirs)
    assert merged["rows"]["#100"]["verdict"] == "verified-already-fixed"


def test_issue_matrix_intra_side_duplicate_key_raises_never_silent_drop() -> None:
    """Two DISTINCT raw rows on ONE side normalizing to the same canonical
    key (``GH-1726`` / ``#1726``) must not silently collapse."""
    base = _issue_doc({})
    ours = _issue_doc(
        {
            "GH-1726": {"verdict": "fixed", "evidence_ref": "a"},
            "#1726": {"verdict": "wontfix", "evidence_ref": "b"},
        }
    )
    theirs = _issue_doc({})

    with pytest.raises(RowMatrixMergeError, match="duplicate"):
        reconcile_issue_matrix_documents(base, ours, theirs)


def test_issue_matrix_intra_side_identical_duplicate_dedupes_without_error() -> None:
    """Two raw rows normalizing to the same key with IDENTICAL content is a
    harmless dedupe, not an error."""
    base = _issue_doc({})
    row: dict[str, object] = {"verdict": "fixed", "evidence_ref": "a"}
    ours = _issue_doc({"GH-1726": dict(row), "#1726": dict(row)})
    theirs = _issue_doc({})

    merged = reconcile_issue_matrix_documents(base, ours, theirs)

    assert merged["rows"] == {"#1726": row}


@pytest.mark.parametrize(
    ("raw_ref", "canonical"),
    [("#1726", "#1726"), ("GH-1726", "#1726"), ("1726", "#1726"), ("gh-1726", "#1726")],
)
def test_canonicalize_issue_ref_normalizes_all_shapes(raw_ref: str, canonical: str) -> None:
    assert _canonicalize_issue_ref(raw_ref) == canonical


def test_issue_matrix_merge_is_byte_deterministic_regardless_of_input_order() -> None:
    """Shuffled input row order -> identical output (contract: stable
    canonical order required for idempotence / FR-012)."""
    base = _issue_doc({})
    ours_a = _issue_doc({"#300": {"verdict": "a"}, "#100": {"verdict": "b"}})
    ours_b = _issue_doc({"#100": {"verdict": "b"}, "#300": {"verdict": "a"}})
    theirs = _issue_doc({"#200": {"verdict": "c"}})

    merged_a = json.dumps(reconcile_issue_matrix_documents(base, ours_a, theirs), sort_keys=True)
    merged_b = json.dumps(reconcile_issue_matrix_documents(base, ours_b, theirs), sort_keys=True)

    assert merged_a == merged_b
    assert list(reconcile_issue_matrix_documents(base, ours_a, theirs)["rows"]) == [
        "#100",
        "#200",
        "#300",
    ]


def test_merge_driver_issue_matrix_writes_canonical_sorted_json(tmp_path: Path) -> None:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    _write_json(base, _issue_doc({}))
    _write_json(ours, _issue_doc({"#300": {"verdict": "a"}, "#100": {"verdict": "b"}}))
    _write_json(theirs, _issue_doc({}))

    merge_driver_issue_matrix(str(base), str(ours), str(theirs))

    text = ours.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert list(json.loads(text)["rows"]) == ["#100", "#300"]  # sort_keys canonical order


def test_merge_driver_issue_matrix_rejects_corrupt_json_exit1(tmp_path: Path) -> None:
    """Corrupt JSON on either side is refused (exit 1), never silently treated
    as an empty document (would otherwise clobber the corrupt side's rows)."""
    import typer

    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text("{ not json", encoding="utf-8")
    theirs.write_text(json.dumps(_issue_doc({})), encoding="utf-8")

    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_issue_matrix(str(base), str(ours), str(theirs))
    assert excinfo.value.exit_code == 1


def test_merge_driver_acceptance_matrix_rejects_corrupt_json_exit1(tmp_path: Path) -> None:
    import typer

    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, not an object
    theirs.write_text(json.dumps(_acceptance_doc([])), encoding="utf-8")

    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_acceptance_matrix(str(base), str(ours), str(theirs))
    assert excinfo.value.exit_code == 1


def test_merge_driver_acceptance_matrix_rejects_both_sides_pass_fail_conflict_exit1(
    tmp_path: Path,
) -> None:
    """FR-002 CLI-exit contract: the real CLI entrypoint, not just the
    reconciler, refuses a both-sides ``pass_fail`` divergence -- exit 1, not
    a silently-written marker document (#4880)."""
    import typer

    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text(
        json.dumps(
            _acceptance_doc(
                [
                    {
                        "criterion_id": "FR-001",
                        "description": "d",
                        "proof_type": "automated_test",
                        "pass_fail": "pending",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    ours.write_text(
        json.dumps(
            _acceptance_doc(
                [
                    {
                        "criterion_id": "FR-001",
                        "description": "d",
                        "proof_type": "automated_test",
                        "pass_fail": "pass",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    theirs.write_text(
        json.dumps(
            _acceptance_doc(
                [
                    {
                        "criterion_id": "FR-001",
                        "description": "d",
                        "proof_type": "automated_test",
                        "pass_fail": "fail",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_acceptance_matrix(str(base), str(ours), str(theirs))
    assert excinfo.value.exit_code == 1


def test_merge_driver_issue_matrix_rejects_both_sides_verdict_conflict_exit1(
    tmp_path: Path,
) -> None:
    """FR-002 CLI-exit twin for the issue-matrix driver: a both-sides
    ``verdict`` divergence exits 1 through the real CLI entrypoint."""
    import typer

    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text(
        json.dumps(_issue_doc({"#100": {"verdict": "unknown", "evidence_ref": "x"}})),
        encoding="utf-8",
    )
    ours.write_text(
        json.dumps(_issue_doc({"#100": {"verdict": "fixed", "evidence_ref": "x"}})),
        encoding="utf-8",
    )
    theirs.write_text(
        json.dumps(_issue_doc({"#100": {"verdict": "wontfix", "evidence_ref": "x"}})),
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_issue_matrix(str(base), str(ours), str(theirs))
    assert excinfo.value.exit_code == 1


# ---------------------------------------------------------------------------
# T042 -- acceptance-matrix.json driver-unit tests (synthetic %O)
# ---------------------------------------------------------------------------


def _acceptance_doc(
    criteria: list[dict[str, Any]], negative_invariants: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "mission_slug": "m-01ABC",
        "criteria": criteria,
        "negative_invariants": negative_invariants or [],
    }


def test_acceptance_matrix_disjoint_criteria_union_no_clobber() -> None:
    base = _acceptance_doc([])
    ours = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d1", "proof_type": "automated_test", "pass_fail": "pass"}]
    )
    theirs = _acceptance_doc(
        [{"criterion_id": "AC-001", "description": "d2", "proof_type": "automated_test", "pass_fail": "pending"}]
    )

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    ids = {c["criterion_id"] for c in merged["criteria"]}
    assert ids == {"FR-001", "AC-001"}


def test_acceptance_matrix_overall_verdict_is_recomputed_never_stale() -> None:
    """The driver never re-authors ``overall_verdict`` as a stored field --
    it is always recomputed from the reconciled criteria (contract)."""
    base = _acceptance_doc([])
    ours = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pass"}],
    )
    ours["overall_verdict"] = "STALE-WRONG-VALUE"  # a corrupt/stale stored value
    theirs = _acceptance_doc([])

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    assert merged["overall_verdict"] == "pass"  # recomputed, not "STALE-WRONG-VALUE"


def test_acceptance_matrix_negative_invariants_keyed_by_invariant_id() -> None:
    base = _acceptance_doc([], [])
    ours = _acceptance_doc(
        [],
        [{"invariant_id": "NI-001", "description": "d", "verification_method": "grep_absence", "result": "confirmed_absent"}],
    )
    theirs = _acceptance_doc(
        [],
        [{"invariant_id": "NI-002", "description": "d2", "verification_method": "grep_absence", "result": "pending"}],
    )

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    ids = {ni["invariant_id"] for ni in merged["negative_invariants"]}
    assert ids == {"NI-001", "NI-002"}


def test_acceptance_matrix_stale_residue_dropped() -> None:
    criterion = {"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pending"}
    base = _acceptance_doc([criterion])
    ours = _acceptance_doc([])  # ours deleted FR-001
    theirs = _acceptance_doc([dict(criterion)])  # theirs left it unchanged

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    assert merged["criteria"] == []


def test_acceptance_matrix_same_field_conflict_raises_fail_closed() -> None:
    """A same-key both-sides ``pass_fail`` divergence (pending -> pass/fail,
    the direct #4880 repro) is refused, not silently embedded as an in-band
    conflict marker inside a verdict-bearing document (fail-closed contract,
    #4880 / amended ADR 2026-07-23-2)."""
    base = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pending"}]
    )
    ours = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pass"}]
    )
    theirs = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "fail"}]
    )

    with pytest.raises(RowMatrixMergeError, match="pass_fail"):
        reconcile_acceptance_matrix_documents(base, ours, theirs)


def test_acceptance_matrix_fail_closed_message_names_the_offending_row() -> None:
    """The fail-closed abort is resolved by a human, so the message must name
    the offending row's canonical key — otherwise an operator staring at a
    many-criterion matrix cannot locate the diverged verdict."""
    base = _acceptance_doc(
        [{"criterion_id": "FR-042", "description": "d", "proof_type": "automated_test", "pass_fail": "pending"}]
    )
    ours = _acceptance_doc(
        [{"criterion_id": "FR-042", "description": "d", "proof_type": "automated_test", "pass_fail": "pass"}]
    )
    theirs = _acceptance_doc(
        [{"criterion_id": "FR-042", "description": "d", "proof_type": "automated_test", "pass_fail": "fail"}]
    )

    with pytest.raises(RowMatrixMergeError, match=r"row 'FR-042'.*pass_fail"):
        reconcile_acceptance_matrix_documents(base, ours, theirs)


def test_acceptance_matrix_authored_pass_fail_beats_pending_sentinel_no_raise() -> None:
    """An UNSET sentinel (``pass_fail == "pending"``) yields to the authored
    side rather than failing closed — one lane graded the criterion, the other
    left it pending. Must NOT abort the merge (#4880 sentinel-yield refinement);
    contrast with the two-authored pass-vs-fail case above, which still raises."""
    base = _acceptance_doc([])
    ours = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pass"}]
    )
    theirs = _acceptance_doc(
        [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pending"}]
    )

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)
    (criterion,) = merged["criteria"]
    assert criterion["pass_fail"] == "pass"


def test_acceptance_matrix_intra_side_duplicate_criterion_id_raises() -> None:
    base = _acceptance_doc([])
    ours = _acceptance_doc(
        [
            {"criterion_id": "FR-001", "description": "d1", "proof_type": "automated_test", "pass_fail": "pass"},
            {"criterion_id": "FR-001", "description": "d2", "proof_type": "automated_test", "pass_fail": "fail"},
        ]
    )
    theirs = _acceptance_doc([])

    with pytest.raises(RowMatrixMergeError, match="duplicate"):
        reconcile_acceptance_matrix_documents(base, ours, theirs)


def test_acceptance_matrix_merge_is_byte_deterministic_regardless_of_input_order() -> None:
    base = _acceptance_doc([])
    crit_a = {"criterion_id": "FR-001", "description": "d1", "proof_type": "automated_test", "pass_fail": "pass"}
    crit_b = {"criterion_id": "AC-001", "description": "d2", "proof_type": "automated_test", "pass_fail": "pending"}
    ours_1 = _acceptance_doc([crit_a, crit_b])
    ours_2 = _acceptance_doc([crit_b, crit_a])
    theirs = _acceptance_doc([])

    merged_1 = reconcile_acceptance_matrix_documents(base, ours_1, theirs)
    merged_2 = reconcile_acceptance_matrix_documents(base, ours_2, theirs)

    assert [c["criterion_id"] for c in merged_1["criteria"]] == [c["criterion_id"] for c in merged_2["criteria"]]
    assert json.dumps(merged_1, sort_keys=True) == json.dumps(merged_2, sort_keys=True)


def test_merge_driver_acceptance_matrix_writes_result_to_ours(tmp_path: Path) -> None:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    _write_json(base, _acceptance_doc([]))
    _write_json(
        ours,
        _acceptance_doc(
            [{"criterion_id": "FR-001", "description": "d", "proof_type": "automated_test", "pass_fail": "pass"}]
        ),
    )
    _write_json(
        theirs,
        _acceptance_doc(
            [{"criterion_id": "AC-001", "description": "d2", "proof_type": "automated_test", "pass_fail": "pending"}]
        ),
    )

    merge_driver_acceptance_matrix(str(base), str(ours), str(theirs))

    merged = _read_json(ours)
    ids = {c["criterion_id"] for c in merged["criteria"]}
    assert ids == {"FR-001", "AC-001"}
    assert merged["overall_verdict"] == "pending"  # AC-001 is still pending


# ---------------------------------------------------------------------------
# T045 -- SC-003 durability-integration regression (real %O from git blobs)
# ---------------------------------------------------------------------------
#
# T042 above proves the ALGORITHM with a synthetic base and passes regardless
# of durability. This section seeds ``%O`` from a REAL git merge-base blob --
# a genuine common ancestor commit that both a coord-lineage/target-lineage
# pair and a target-lineage/lane pair diverge from -- and drives the actual
# registered driver FUNCTION (in-process; the underlying reconciliation logic
# is identical whether invoked via the CLI subprocess or in-process -- the
# subprocess boundary is exercised separately by the real ``git merge``
# integration coverage in ``tests/merge/test_event_log_merge_driver_
# integration.py`` and the #2804 regression). No dependency on WP01: %O is
# drawn from the matrix's own git lineage, never a lane base SHA.


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_issue_matrix(repo: Path, rows: dict[str, dict[str, object]], message: str) -> str:
    matrix_dir = repo / "kitty-specs" / "m-01ABC"
    matrix_dir.mkdir(parents=True, exist_ok=True)
    (matrix_dir / "issue-matrix.json").write_text(
        json.dumps(_issue_doc(rows), indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _blob_to_file(repo: Path, ref: str, rel_path: str, dest: Path) -> Path:
    """Extract a real git blob (``ref:rel_path``) to *dest* -- the same shape
    ``git`` feeds a merge driver's ``%O``/``%A``/``%B`` placeholders."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"], cwd=str(repo), capture_output=True, text=True
    )
    dest.write_text(result.stdout if result.returncode == 0 else "", encoding="utf-8")
    return dest


_MATRIX_REL_PATH = "kitty-specs/m-01ABC/issue-matrix.json"


def test_coord_topology_disjoint_rows_survive_real_git_merge_base(tmp_path: Path) -> None:
    """Coord topology: matrices serialize onto the single coord worktree
    (``commit_router.py:248-306``) -- so the disjoint-row case here is a
    coord-surface / coord<->target-integration merge (the coord branch's
    matrix state vs. the target's own accept-time update), NOT a
    lane->mission 3-way. ``%O`` is the git merge-base blob on this real
    coord<->target lineage -- topology-resolved, never WP01's lane SHA.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    base_sha = _commit_issue_matrix(repo, {"#100": {"verdict": "unknown"}}, "base: seed #100")

    _git(repo, "checkout", "-q", "-b", "coord")
    coord_sha = _commit_issue_matrix(
        repo, {"#100": {"verdict": "unknown"}, "#200": {"verdict": "fixed"}}, "coord: add #200"
    )

    _git(repo, "checkout", "-q", "main")
    target_sha = _commit_issue_matrix(
        repo, {"#100": {"verdict": "unknown"}, "#300": {"verdict": "wontfix"}}, "target: add #300"
    )

    merge_base = _git(repo, "merge-base", "main", "coord").stdout.strip()
    assert merge_base == base_sha  # sanity: real, non-synthetic common ancestor

    base_file = _blob_to_file(repo, merge_base, _MATRIX_REL_PATH, tmp_path / "O")
    ours_file = _blob_to_file(repo, target_sha, _MATRIX_REL_PATH, tmp_path / "A")
    theirs_file = _blob_to_file(repo, coord_sha, _MATRIX_REL_PATH, tmp_path / "B")

    merge_driver_issue_matrix(str(base_file), str(ours_file), str(theirs_file))

    merged_rows = _read_json(ours_file)["rows"]
    assert set(merged_rows) == {"#100", "#200", "#300"}, (
        f"zero-clobber (SC-003) violated -- expected #100/#200/#300 to all "
        f"survive the coord<->target integration merge, got {sorted(merged_rows)}"
    )


def test_flat_topology_disjoint_rows_survive_real_git_merge_base(tmp_path: Path) -> None:
    """Flat topology (SINGLE_BRANCH/LANES, no coord partition): the matrix
    lives directly on ``target_branch``, so lane-branch divergence is where
    the disjoint-row gap actually bites -- two lane branches forking from the
    SAME target_branch commit, each adding a different row, then both
    integrating back. ``%O`` is the real merge-base blob on the
    target_branch/lane lineage.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    base_sha = _commit_issue_matrix(repo, {"#100": {"verdict": "unknown"}}, "base: seed #100")

    _git(repo, "checkout", "-q", "-b", "lane-a")
    lane_a_sha = _commit_issue_matrix(
        repo, {"#100": {"verdict": "unknown"}, "#400": {"verdict": "fixed"}}, "lane-a: add #400"
    )

    _git(repo, "checkout", "-q", "main")
    lane_b_sha = _commit_issue_matrix(
        repo, {"#100": {"verdict": "unknown"}, "#500": {"verdict": "wontfix"}}, "main: add #500"
    )

    merge_base = _git(repo, "merge-base", "main", "lane-a").stdout.strip()
    assert merge_base == base_sha

    base_file = _blob_to_file(repo, merge_base, _MATRIX_REL_PATH, tmp_path / "O")
    ours_file = _blob_to_file(repo, lane_b_sha, _MATRIX_REL_PATH, tmp_path / "A")
    theirs_file = _blob_to_file(repo, lane_a_sha, _MATRIX_REL_PATH, tmp_path / "B")

    merge_driver_issue_matrix(str(base_file), str(ours_file), str(theirs_file))

    merged_rows = _read_json(ours_file)["rows"]
    assert set(merged_rows) == {"#100", "#400", "#500"}, (
        f"zero-clobber (SC-003) violated on flat topology -- expected "
        f"#100/#400/#500 to all survive, got {sorted(merged_rows)}"
    )


# ---------------------------------------------------------------------------
# T041 -- m_3_2_6_issue_matrix_driver_repoint registration migration (upgraded repos)
# ---------------------------------------------------------------------------
#
# The .gitattributes/init/registry parity itself is covered generically by
# ``tests/architectural/test_merge_reconciliation_class_guard.py``
# (``test_migration_seed_is_superset_of_registry_merge_drivers``, which
# auto-discovers every ``MergeDriverSeedingMigration`` subclass). These pin
# the migration's own detect/apply/idempotency behavior directly -- mirroring
# ``tests/upgrade/migrations/test_m_3_2_6_meta_traces_merge_drivers.py``.

from specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint import (  # noqa: E402
    IssueMatrixDriverRepointMigration,
)

_ISSUE_MATRIX_JSON_ENTRY = "kitty-specs/**/issue-matrix.json merge=spec-kitty-issue-matrix"


def test_m_3_2_6_issue_matrix_driver_repoint_is_a_new_file_not_a_mutation_of_gate_artifact() -> None:
    """Reviewer guidance: verify the migration is a NEW file, not an edit of
    the historical ``m_3_2_6_gate_artifact_merge_drivers``."""
    import specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers as m_3_2_6_gate
    import specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint as m_3_2_6_repoint

    assert m_3_2_6_gate.__file__ != m_3_2_6_repoint.__file__
    assert m_3_2_6_gate.GateArtifactMergeDriverMigration.migration_id == "3.2.6_gate_artifact_merge_drivers"
    assert m_3_2_6_repoint.IssueMatrixDriverRepointMigration.migration_id == "3.2.6_issue_matrix_driver_repoint"
    # The historical migration's issue-matrix.md driver entry is untouched
    # (inert on repos that already ran it -- WP05 means no .md is ever
    # written any more, but the historical record is not rewritten).
    assert any(
        d.pattern == "kitty-specs/**/issue-matrix.md" for d in m_3_2_6_gate._DRIVERS
    )
    assert any(
        d.pattern == "kitty-specs/**/issue-matrix.json" for d in m_3_2_6_repoint._DRIVERS
    )


def test_m_3_2_6_issue_matrix_driver_repoint_migration_detects_and_applies_json_attribute(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(tmp_path), check=True)
    migration = IssueMatrixDriverRepointMigration()

    assert migration.detect(tmp_path) is True

    result = migration.apply(tmp_path)

    assert result.success is True
    attributes = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
    assert _ISSUE_MATRIX_JSON_ENTRY in attributes
    assert migration.detect(tmp_path) is False  # idempotent: nothing left to apply


def test_m_3_2_6_issue_matrix_driver_repoint_migration_repoints_a_repo_still_on_the_stale_md_driver(
    tmp_path: Path,
) -> None:
    """A repo that already ran ``m_3_2_6`` (so it has the OLD ``.md`` driver
    config + attribute) still needs repointing -- ``detect`` must see the
    stale config/attribute mismatch, not just "config present"."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(tmp_path), check=True)
    from specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers import (
        GateArtifactMergeDriverMigration,
    )

    GateArtifactMergeDriverMigration().apply(tmp_path)  # seeds the stale .md driver

    migration = IssueMatrixDriverRepointMigration()
    assert migration.detect(tmp_path) is True  # stale .md config != new .json driver

    result = migration.apply(tmp_path)

    assert result.success is True
    attributes = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
    assert _ISSUE_MATRIX_JSON_ENTRY in attributes
    driver_check = subprocess.run(
        ["git", "config", "--local", "--get", "merge.spec-kitty-issue-matrix.driver"],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    assert driver_check.stdout.strip() == "spec-kitty merge-driver-issue-matrix %O %A %B"
