"""Focused unit coverage for ``specify_cli.merge.drivers``.

Complements (never duplicates) ``tests/merge/test_merge_driver_goldens.py``'s
byte-characterisation net: this module targets the branches internal to the
driver bodies themselves -- the completeness guard tying ``MERGE_DRIVER_BODIES`` to
the two other driver-name authorities, each body's error-wrapping-vs-
re-raise-as-is decision (contract invariant 3: a foreign exception is wrapped
`MergeDriverError(str(exc)) from exc`; an exception that is ALREADY a
``MergeDriverError`` subclass is re-raised as-is, never re-wrapped), the
review-cycle body's ``MergeDriverOutcome.notice`` contract, the traces body's
deliberately-NOT-broadened ``UnicodeDecodeError`` propagation, and the CLI
shell's translation of a body's outcome to ``typer``'s exit protocol.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import _COMMAND_REGISTRARS
from specify_cli.cli.commands import merge_driver as merge_driver_shell
from specify_cli.lanes.merge import _MERGE_DRIVERS
from specify_cli.merge import drivers
from specify_cli.merge.drivers import (
    MERGE_DRIVER_BODIES,
    MergeDriverError,
    MergeDriverOutcome,
    MergeDriverPathError,
    RowMatrixMergeError,
    run_acceptance_matrix_driver,
    run_event_log_driver,
    run_issue_matrix_driver,
    run_meta_driver,
    run_review_cycle_driver,
    run_traces_driver,
)
from specify_cli.merge.git_probes import _DRIVER_COMMAND_PATTERN
from specify_cli.status import EventLogMergeError

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SRC = Path(__file__).resolve().parents[2] / "src"


# ---------------------------------------------------------------------------
# Completeness (structural guard against a 7th driver drifting)
# ---------------------------------------------------------------------------


def test_merge_driver_bodies_matches_the_two_other_driver_name_authorities() -> None:
    """``MERGE_DRIVER_BODIES`` keys == the registry-derived command names ==
    the ``merge-driver-*`` keys of ``_COMMAND_REGISTRARS`` (6 each)."""
    registry_derived = {match.group(1) for spec in _MERGE_DRIVERS if (match := _DRIVER_COMMAND_PATTERN.match(spec.command))}
    registrar_derived = {key for key in _COMMAND_REGISTRARS if key.startswith("merge-driver-")}
    assert set(MERGE_DRIVER_BODIES) == registry_derived == registrar_derived
    assert len(MERGE_DRIVER_BODIES) == 6


def test_drivers_module_imports_no_typer_or_cli() -> None:
    """``drivers.py`` must not import ``typer`` or any ``specify_cli.cli``
    module (contract invariant 1). Complements, without duplicating,
    ``TestMergeCliBoundary`` in ``tests/architectural/test_layer_rules.py``
    (that class scans every module under ``specify_cli/merge/**``; this is a
    narrow, single-file AST assertion scoped to this test's own subject)."""
    tree = ast.parse((_SRC / "specify_cli" / "merge" / "drivers.py").read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(alias.name for alias in node.names if alias.name == "typer" or alias.name.startswith("specify_cli.cli"))
        elif isinstance(node, ast.ImportFrom) and node.module and (node.module == "typer" or node.module.startswith("specify_cli.cli")):
            offenders.append(node.module)
    assert not offenders, f"merge/drivers.py must not import typer/specify_cli.cli; found: {offenders!r}"


# ---------------------------------------------------------------------------
# Path hardening (shared choke point -- MergeDriverPathError IS a MergeDriverError)
# ---------------------------------------------------------------------------


def test_resolve_merge_driver_paths_refuses_escape(tmp_path: Path) -> None:
    sibling_dir = tmp_path / "elsewhere"
    sibling_dir.mkdir()
    with pytest.raises(MergeDriverPathError) as excinfo:
        drivers._resolve_merge_driver_paths(str(tmp_path / "O"), str(tmp_path / "A"), str(sibling_dir / "B"))
    assert isinstance(excinfo.value, MergeDriverError)


# ---------------------------------------------------------------------------
# run_event_log_driver
# ---------------------------------------------------------------------------


def test_event_log_driver_unions_ours_and_theirs(tmp_path: Path) -> None:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text('{"event_id": "e1", "at": "2026-01-01T00:00:00Z"}\n', encoding="utf-8")
    theirs.write_text('{"event_id": "e2", "at": "2026-01-02T00:00:00Z"}\n', encoding="utf-8")

    outcome = run_event_log_driver(str(base), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged_ids = {line.split('"event_id": "')[1].split('"')[0] for line in ours.read_text().splitlines()}
    assert merged_ids == {"e1", "e2"}


def test_event_log_driver_wraps_foreign_error(tmp_path: Path) -> None:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text("not json\n", encoding="utf-8")
    theirs.write_text("", encoding="utf-8")

    with pytest.raises(MergeDriverError) as excinfo:
        run_event_log_driver(str(base), str(ours), str(theirs))
    assert type(excinfo.value) is MergeDriverError  # foreign error wrapped, not re-raised as its own type
    assert isinstance(excinfo.value.__cause__, EventLogMergeError)
    assert str(excinfo.value) == str(excinfo.value.__cause__)


# ---------------------------------------------------------------------------
# run_meta_driver
# ---------------------------------------------------------------------------


def test_meta_driver_field_merges_and_writes_canonical_json(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text('{"mission_number": 7, "status": "accepted"}', encoding="utf-8")
    theirs.write_text('{"mission_slug": "m", "mission_number": null}', encoding="utf-8")

    outcome = run_meta_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    assert ours.read_text().endswith("\n")
    merged = ours.read_text()
    assert '"mission_number": 7' in merged
    assert '"mission_slug": "m"' in merged


def test_meta_driver_wraps_malformed_json(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("{ not json", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")

    with pytest.raises(MergeDriverError) as excinfo:
        run_meta_driver(str(tmp_path / "O"), str(ours), str(theirs))
    assert type(excinfo.value) is MergeDriverError
    assert isinstance(excinfo.value.__cause__, EventLogMergeError)


# ---------------------------------------------------------------------------
# run_traces_driver -- the deliberately-NOT-broadened UnicodeDecodeError
# ---------------------------------------------------------------------------


def test_traces_driver_unions_both_sides(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("<!-- section:target -->\ntarget line\n", encoding="utf-8")
    theirs.write_text("<!-- section:coord -->\ncoord line\n", encoding="utf-8")

    outcome = run_traces_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = ours.read_text()
    assert "target line" in merged
    assert "coord line" in merged


def test_traces_driver_propagates_unicode_decode_error_unwrapped(tmp_path: Path) -> None:
    """Pin (research R2): this driver never caught ``UnicodeDecodeError``
    before the move and must not start now -- it must propagate UNWRAPPED,
    never translated to :class:`MergeDriverError`."""
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_bytes(b"\xff\xfe not valid utf-8")
    theirs.write_text("", encoding="utf-8")

    with pytest.raises(UnicodeDecodeError):
        run_traces_driver(str(tmp_path / "O"), str(ours), str(theirs))


# ---------------------------------------------------------------------------
# run_issue_matrix_driver -- RowMatrixMergeError re-raised as-is (never
# re-wrapped: it is ALREADY a MergeDriverError subclass, contract invariant 3)
# ---------------------------------------------------------------------------


def test_issue_matrix_driver_row_union(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text('{"rows": {"#1": {"issue_ref": "#1", "verdict": "closed"}}}', encoding="utf-8")
    theirs.write_text('{"rows": {"#2": {"issue_ref": "#2", "verdict": "open"}}}', encoding="utf-8")

    outcome = run_issue_matrix_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = ours.read_text()
    assert '"#1"' in merged and '"#2"' in merged
    assert merged.endswith("\n")


def test_issue_matrix_driver_reraises_row_matrix_error_as_is(tmp_path: Path) -> None:
    """A malformed document raises :class:`RowMatrixMergeError` directly --
    NOT re-wrapped into a bare :class:`MergeDriverError` (it already IS one)."""
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("not json", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")

    with pytest.raises(RowMatrixMergeError) as excinfo:
        run_issue_matrix_driver(str(tmp_path / "O"), str(ours), str(theirs))
    assert type(excinfo.value) is RowMatrixMergeError  # never re-wrapped
    assert isinstance(excinfo.value, MergeDriverError)


# ---------------------------------------------------------------------------
# run_acceptance_matrix_driver -- both error branches (re-raise vs wrap)
# ---------------------------------------------------------------------------


def test_acceptance_matrix_driver_row_union(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text(
        '{"mission_slug": "m", "criteria": [{"criterion_id": "AC-1", "description": "d", '
        '"proof_type": "automated_test", "pass_fail": "pass"}], "negative_invariants": []}',
        encoding="utf-8",
    )
    theirs.write_text('{"mission_slug": "m", "criteria": [], "negative_invariants": []}', encoding="utf-8")

    outcome = run_acceptance_matrix_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome()
    merged = ours.read_text()
    # Exact serialized form: json.dumps(..., indent=2) with NO sort_keys, so
    # field order follows AcceptanceMatrix/Criterion's declared field order,
    # not alphabetical. A weaker substring/no-blank-line check would miss a
    # regression to sort_keys=True or a reordered/renamed field.
    assert merged == (
        "{\n"
        '  "mission_slug": "m",\n'
        '  "mission_number": "",\n'
        '  "mission_type": "",\n'
        '  "overall_verdict": "pass",\n'
        '  "criteria": [\n'
        "    {\n"
        '      "criterion_id": "AC-1",\n'
        '      "description": "d",\n'
        '      "proof_type": "automated_test",\n'
        '      "evidence": null,\n'
        '      "pass_fail": "pass",\n'
        '      "verified_by": null,\n'
        '      "verified_at": null,\n'
        '      "notes": null\n'
        "    }\n"
        "  ],\n"
        '  "negative_invariants": []\n'
        "}\n"
    )


def test_acceptance_matrix_driver_reraises_row_matrix_error_as_is(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("not json", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")

    with pytest.raises(RowMatrixMergeError) as excinfo:
        run_acceptance_matrix_driver(str(tmp_path / "O"), str(ours), str(theirs))
    assert type(excinfo.value) is RowMatrixMergeError  # never re-wrapped


def test_acceptance_matrix_driver_wraps_parse_error(tmp_path: Path) -> None:
    """A reconciled row carrying a raw conflict-marker string fails
    :meth:`AcceptanceMatrix.from_dict`'s read-side guard with
    :class:`AcceptanceMatrixParseError` -- a FOREIGN error (not a
    MergeDriverError subclass), so it must be wrapped."""
    doc = (
        '{"mission_slug": "m", "criteria": ['
        '{"criterion_id": "AC-1", "description": "d", "proof_type": "automated_test", '
        '"pass_fail": "pass", "notes": "<<<<<<< stray"}], "negative_invariants": []}'
    )
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text(doc, encoding="utf-8")
    theirs.write_text(doc, encoding="utf-8")  # identical on both sides -> row survives untouched into from_dict

    with pytest.raises(MergeDriverError) as excinfo:
        run_acceptance_matrix_driver(str(tmp_path / "O"), str(ours), str(theirs))
    assert type(excinfo.value) is MergeDriverError
    assert "conflict marker" in str(excinfo.value)


# ---------------------------------------------------------------------------
# run_review_cycle_driver -- MergeDriverOutcome.notice contract
# ---------------------------------------------------------------------------


def test_review_cycle_driver_identical_sides_returns_no_notice(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("verdict: approved\n", encoding="utf-8")
    theirs.write_text("verdict: approved\n", encoding="utf-8")

    outcome = run_review_cycle_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome == MergeDriverOutcome(notice=None)
    assert ours.read_text() == "verdict: approved\n"


def test_review_cycle_driver_collision_returns_notice_and_embeds_both(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("verdict: approved\n", encoding="utf-8")
    theirs.write_text("verdict: rejected\n", encoding="utf-8")

    outcome = run_review_cycle_driver(str(tmp_path / "O"), str(ours), str(theirs))

    assert outcome.notice is not None
    assert "collision" in outcome.notice
    merged = ours.read_text()
    assert "verdict: approved" in merged
    assert "verdict: rejected" in merged
    assert "<<<<<<< ours" in merged
    assert ">>>>>>> theirs" in merged


# ---------------------------------------------------------------------------
# CLI shell: MergeDriverError -> exit 1 + stderr; outcome.notice -> stdout
# ---------------------------------------------------------------------------


def test_shell_run_translates_merge_driver_error_to_exit1(capsys: pytest.CaptureFixture[str]) -> None:
    def _body(base: str, ours: str, theirs: str) -> MergeDriverOutcome:
        del base, ours, theirs
        raise MergeDriverError("boom")

    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_shell._run(_body, "O", "A", "B")
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "boom"
    assert captured.out == ""


def test_shell_run_echoes_outcome_notice_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    def _body(base: str, ours: str, theirs: str) -> MergeDriverOutcome:
        del base, ours, theirs
        return MergeDriverOutcome(notice="a notice")

    merge_driver_shell._run(_body, "O", "A", "B")

    captured = capsys.readouterr()
    assert captured.out.strip() == "a notice"
    assert captured.err == ""


def test_shell_run_no_notice_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    def _body(base: str, ours: str, theirs: str) -> MergeDriverOutcome:
        del base, ours, theirs
        return MergeDriverOutcome()

    merge_driver_shell._run(_body, "O", "A", "B")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
