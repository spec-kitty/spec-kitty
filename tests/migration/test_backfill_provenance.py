"""Migration oracle for ``spec-kitty migrate backfill-provenance`` (FR-014).

Covers WP05:
- T027: on-disk migration walk — non-``pending`` results lacking provenance
  are stamped ``provenance_origin: legacy_unrecorded``; ``verified_ref`` /
  ``verified_surface_kind`` stay null.
- T028: whole-corpus write is commit-or-revert — a failure partway through
  restores every file already written in that run, leaving no partial
  migration state.
- T029 (AM-4): the migration never auto-archives; its failure path never
  reaches an archive operation.
- T030: oracle — over a fixture matrix corpus (shaped from the REAL,
  measured on-disk corpus: 155 files, 40 negative invariants, all 40
  non-pending, 0 with provenance, split 39 confirmed_absent / 1
  still_present — measured 2026-07-24 via
  ``find kitty-specs -name acceptance-matrix.json`` + a parse pass, NOT the
  153/40 figures quoted in the tasks prompt, which were unverified), every
  non-``pending`` result ends with a valid ``provenance_origin`` and
  ``validate_matrix_evidence`` passes on the migrated corpus.

Post-review follow-up (FR-014 operator-invokability): the migration is also
wired into the CLI as ``spec-kitty migrate backfill-provenance``
(``migrate_cmd.py``, mirroring the ``charter-encoding`` twin). The CLI
registration tests below (``Test*Cli`` section) cover that surface directly
via ``typer.testing.CliRunner``, matching
``tests/migration/test_backfill_topology_cli.py``.

All filesystem I/O is under ``tmp_path``. No network calls, no git shell-out
(pure JSON file I/O) — plain ``unit``/``fast`` markers, matching
``tests/migrate/test_charter_encoding_migration.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.acceptance.matrix import (
    PROVENANCE_LEGACY_UNRECORDED,
    PROVENANCE_RECORDED,
    AcceptanceMatrix,
    validate_matrix_evidence,
)
from specify_cli.cli.commands.migrate.backfill_provenance import (
    _CorpusWriteTransaction,
    _collect_matrix_paths,
    run_backfill_provenance_migration,
)
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from tests._support.eacces import deny_path_method

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixture builders — realistic, production-shaped matrix content
# ---------------------------------------------------------------------------


def _write_matrix(specs_root: Path, slug: str, data: dict[str, Any]) -> Path:
    feature_dir = specs_root / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    path = feature_dir / "acceptance-matrix.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _base_matrix(slug: str, negative_invariants: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_slug": slug,
        "mission_number": "",
        "mission_type": "software-dev",
        "overall_verdict": "pending",
        "criteria": [
            {
                "criterion_id": "FR-001",
                "description": "Verify FR-001 is satisfied",
                "proof_type": "automated_test",
                "evidence": None,
                "pass_fail": "pending",
                "verified_by": None,
                "verified_at": None,
                "notes": None,
            }
        ],
        "negative_invariants": negative_invariants,
    }


def _pre_schema_confirmed_absent(invariant_id: str) -> dict[str, Any]:
    """Shape of a real pre-WP04 recorded invariant: no provenance keys at all."""
    return {
        "invariant_id": invariant_id,
        "description": "No import of any deleted shim namespace remains (NFR-002).",
        "verification_method": "grep_absence",
        "verification_command": "grep -rn deleted_shim src/ tests/",
        "result": "confirmed_absent",
        "evidence": "grep found zero matches",
    }


def _pre_schema_still_present(invariant_id: str) -> dict[str, Any]:
    return {
        "invariant_id": invariant_id,
        "description": "Legacy shim namespace must be fully removed.",
        "verification_method": "custom_command",
        "verification_command": ".venv/bin/python -c \"import sys; sys.exit(1)\"",
        "result": "still_present",
        "evidence": "Command exited 1: ",
    }


def _pending_invariant(invariant_id: str) -> dict[str, Any]:
    return {
        "invariant_id": invariant_id,
        "description": "Not yet judged.",
        "verification_method": "grep_absence",
        "verification_command": "grep -rn some_pattern src/",
        "result": "pending",
    }


def _already_recorded_invariant(invariant_id: str) -> dict[str, Any]:
    """A WP04-gate-judged row — already carries full provenance."""
    return {
        "invariant_id": invariant_id,
        "description": "Judged by the gate after WP04 landed.",
        "verification_method": "grep_absence",
        "verification_command": "grep -rn other_pattern src/",
        "result": "confirmed_absent",
        "evidence": "grep found zero matches",
        "provenance_origin": PROVENANCE_RECORDED,
        "verified_ref": "abc123def456",
        "verified_surface_kind": "primary",
    }


def _already_legacy_unrecorded_invariant(invariant_id: str) -> dict[str, Any]:
    """A row from a PRIOR run of this same migration (idempotency case)."""
    return {
        "invariant_id": invariant_id,
        "description": "Already migrated in an earlier run.",
        "verification_method": "grep_absence",
        "verification_command": "grep -rn yet_another src/",
        "result": "still_present",
        "evidence": "grep found matches: some/file.py:12",
        "provenance_origin": PROVENANCE_LEGACY_UNRECORDED,
    }


# ---------------------------------------------------------------------------
# T027 — migration walk stamps the sentinel
# ---------------------------------------------------------------------------


def test_stamps_legacy_unrecorded_on_non_pending_missing_provenance(tmp_path: Path) -> None:
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "017-runtime-observability-baseline",
        _base_matrix(
            "017-runtime-observability-baseline",
            [
                _pre_schema_confirmed_absent("NI-001"),
                _pre_schema_still_present("NI-002"),
            ],
        ),
    )

    summary = run_backfill_provenance_migration(tmp_path)

    assert summary.result == "success"
    assert summary.errors == []
    assert [record.path for record in summary.migrated] == [path]
    assert summary.migrated[0].invariants_stamped == 2

    migrated = json.loads(path.read_text(encoding="utf-8"))
    invariants = {ni["invariant_id"]: ni for ni in migrated["negative_invariants"]}
    for invariant_id in ("NI-001", "NI-002"):
        ni = invariants[invariant_id]
        assert ni["provenance_origin"] == PROVENANCE_LEGACY_UNRECORDED
        assert ni.get("verified_ref") is None
        assert ni.get("verified_surface_kind") is None
    # Unrelated fields must survive untouched (T027: "leaving verified_ref /
    # verified_surface_kind null", nothing else rewritten).
    assert invariants["NI-001"]["evidence"] == "grep found zero matches"


def test_pending_invariant_left_untouched(tmp_path: Path) -> None:
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "034-feature-status-state-model-remediation",
        _base_matrix(
            "034-feature-status-state-model-remediation",
            [_pending_invariant("NI-010")],
        ),
    )
    before = path.read_text(encoding="utf-8")

    summary = run_backfill_provenance_migration(tmp_path)

    assert summary.migrated == []
    assert summary.unchanged == [path]
    assert path.read_text(encoding="utf-8") == before


def test_already_recorded_invariant_never_overwritten(tmp_path: Path) -> None:
    """NI-2 / C3: a terminal result with real provenance is never re-stamped."""
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "coord-commit-integrity-01KY5JS8",
        _base_matrix(
            "coord-commit-integrity-01KY5JS8",
            [_already_recorded_invariant("NI-020")],
        ),
    )
    before = path.read_text(encoding="utf-8")

    summary = run_backfill_provenance_migration(tmp_path)

    assert summary.migrated == []
    assert path.read_text(encoding="utf-8") == before


def test_rerun_is_idempotent_second_pass_touches_nothing(tmp_path: Path) -> None:
    """Running the migration twice must not re-stamp an already-migrated row."""
    specs_root = tmp_path / "kitty-specs"
    _write_matrix(
        specs_root,
        "unshim-wave2-01KWMCAX",
        _base_matrix(
            "unshim-wave2-01KWMCAX",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )

    first = run_backfill_provenance_migration(tmp_path)
    assert first.migrated[0].invariants_stamped == 1

    second = run_backfill_provenance_migration(tmp_path)
    assert second.migrated == []
    assert len(second.unchanged) == 1


def test_matrix_with_no_negative_invariants_is_unchanged(tmp_path: Path) -> None:
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "docs-only-mission-01KY00AA",
        {
            "mission_slug": "docs-only-mission-01KY00AA",
            "mission_number": "",
            "mission_type": "documentation",
            "overall_verdict": "pending",
            "criteria": [],
            "negative_invariants": [],
        },
    )
    before = path.read_text(encoding="utf-8")

    summary = run_backfill_provenance_migration(tmp_path)

    assert summary.migrated == []
    assert path.read_text(encoding="utf-8") == before


def test_dry_run_reports_but_writes_nothing(tmp_path: Path) -> None:
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "017-runtime-observability-baseline",
        _base_matrix(
            "017-runtime-observability-baseline",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )
    before = path.read_text(encoding="utf-8")

    summary = run_backfill_provenance_migration(tmp_path, dry_run=True)

    assert summary.dry_run is True
    assert summary.migrated[0].invariants_stamped == 1
    # Nothing written to disk.
    assert path.read_text(encoding="utf-8") == before


def test_collect_matrix_paths_unstattable_mission_candidate_is_not_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`#3194`: the `p.is_dir()` filter in `_collect_matrix_paths` must not use
    the EACCES-divergent predicate.

    `Path.is_dir()` answers `False` for an unreadable candidate on Python 3.14
    only (RAISES on 3.11-3.13) — silently dropping the candidate (and any
    acceptance-matrix.json under it) from corpus discovery with no signal, the
    same shape `#3177` fixed in `specify_cli.decisions.ownership`. `safe_is_dir`
    makes this raise on every interpreter instead.
    """
    specs_root = tmp_path / "kitty-specs"
    specs_root.mkdir()
    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs_root / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

    # Deny the stat at the seam: root stats through a 0o000 directory (#5691).
    deny_path_method(monkeypatch, "stat", specs_root / "m-link")
    with pytest.raises(OSError):
        _collect_matrix_paths(tmp_path)


# ---------------------------------------------------------------------------
# T028 — commit-or-revert transaction
# ---------------------------------------------------------------------------


def test_corpus_write_transaction_rollback_restores_original_bytes(tmp_path: Path) -> None:
    """Unit-level: the transaction primitive itself restores on rollback."""
    target = tmp_path / "acceptance-matrix.json"
    original = '{"negative_invariants": []}\n'
    target.write_text(original, encoding="utf-8")

    txn = _CorpusWriteTransaction()
    txn.write(target, '{"negative_invariants": ["mutated"]}\n')
    assert target.read_text(encoding="utf-8") != original

    txn.rollback()

    assert target.read_text(encoding="utf-8") == original


def test_migration_failure_partway_reverts_every_already_written_file(tmp_path: Path) -> None:
    """T028: a failure on the SECOND file's write must revert the FIRST file too.

    No partial migration state may be observable on disk after a failed run.
    """
    specs_root = tmp_path / "kitty-specs"
    path_a = _write_matrix(
        specs_root,
        "aaa-first-mission-01KY0001",
        _base_matrix(
            "aaa-first-mission-01KY0001",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )
    path_b = _write_matrix(
        specs_root,
        "bbb-second-mission-01KY0002",
        _base_matrix(
            "bbb-second-mission-01KY0002",
            [_pre_schema_still_present("NI-002")],
        ),
    )
    before_a = path_a.read_text(encoding="utf-8")
    before_b = path_b.read_text(encoding="utf-8")

    real_write = _CorpusWriteTransaction.write
    calls = {"count": 0}

    def _flaky_write(self: _CorpusWriteTransaction, path: Path, content: str) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated disk failure on second write")
        real_write(self, path, content)

    with (
        patch.object(_CorpusWriteTransaction, "write", _flaky_write),
        pytest.raises(OSError, match="simulated disk failure"),
    ):
        run_backfill_provenance_migration(tmp_path)

    # Both files — including the one written successfully before the
    # failure — are back to their pre-migration bytes. No partial state.
    assert path_a.read_text(encoding="utf-8") == before_a
    assert path_b.read_text(encoding="utf-8") == before_b


# ---------------------------------------------------------------------------
# T029 — AM-4: never auto-archive
# ---------------------------------------------------------------------------


def test_unparseable_matrix_is_reported_not_raised_and_never_archived(tmp_path: Path) -> None:
    """A matrix the migration cannot bring onto the schema is an error entry,
    never an exception that could route into a wider auto-archive handler,
    and never an archive call — this module has none reachable (AM-4)."""
    specs_root = tmp_path / "kitty-specs"
    feature_dir = specs_root / "broken-mission-01KY0003"
    feature_dir.mkdir(parents=True)
    bad_path = feature_dir / "acceptance-matrix.json"
    bad_path.write_text("{ not valid json", encoding="utf-8")

    good_path = _write_matrix(
        specs_root,
        "good-mission-01KY0004",
        _base_matrix(
            "good-mission-01KY0004",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )

    summary = run_backfill_provenance_migration(tmp_path)

    assert len(summary.errors) == 1
    assert summary.errors[0].path == bad_path
    # The unparseable file is untouched; the rest of the corpus still migrates.
    assert bad_path.read_text(encoding="utf-8") == "{ not valid json"
    assert good_path in [record.path for record in summary.migrated]


def test_module_never_references_archive_symbols() -> None:
    """Structural guard for AM-4: no archive-operation symbol is IMPORTED by
    this migration's source. Negative, registry-backed (one module's import
    list), not a positive literal count — permitted under NFR-008's
    structural exception because "no archive call exists" is inherently a
    structural (absence) property, not something observable via a fixture
    run. Doctrine comments in the module are free to say "archive" (and do,
    to document the guarantee) — only actual imports are checked."""
    import ast

    import specify_cli.cli.commands.migrate.backfill_provenance as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)

    assert not any("archive" in name.lower() for name in imported_names)
    assert not hasattr(module, "archive_mission")
    assert not hasattr(module, "ArchivedMission")


# ---------------------------------------------------------------------------
# T030 — migration oracle over a measured-shape fixture corpus
# ---------------------------------------------------------------------------


def _build_measured_shape_corpus(specs_root: Path) -> list[Path]:
    """Build a small fixture corpus proportioned like the REAL measured one.

    Real corpus (measured 2026-07-24): 155 files, 40 negative invariants (all
    39 confirmed_absent : 1 still_present split), 0 pending, 0 with
    provenance. This fixture keeps that same qualitative shape at a workable
    test scale: multiple files, a confirmed_absent-heavy split with one
    still_present, plus the edge rows a real corpus also contains (already
    ``recorded``, already ``legacy_unrecorded``, ``pending``, and a
    criteria-only file with no negative invariants at all).
    """
    paths = []
    paths.append(
        _write_matrix(
            specs_root,
            "unshim-wave2-01KWMCAX",
            _base_matrix(
                "unshim-wave2-01KWMCAX",
                [
                    _pre_schema_confirmed_absent("NI-001"),
                    _pre_schema_confirmed_absent("NI-002"),
                    _pre_schema_still_present("NI-003"),
                ],
            ),
        )
    )
    paths.append(
        _write_matrix(
            specs_root,
            "017-runtime-observability-baseline",
            _base_matrix(
                "017-runtime-observability-baseline",
                [_pre_schema_confirmed_absent(f"NI-{i:03d}") for i in range(10, 14)],
            ),
        )
    )
    paths.append(
        _write_matrix(
            specs_root,
            "coord-commit-integrity-01KY5JS8",
            _base_matrix(
                "coord-commit-integrity-01KY5JS8",
                [_already_recorded_invariant("NI-020")],
            ),
        )
    )
    paths.append(
        _write_matrix(
            specs_root,
            "prior-run-mission-01KY0005",
            _base_matrix(
                "prior-run-mission-01KY0005",
                [_already_legacy_unrecorded_invariant("NI-030")],
            ),
        )
    )
    paths.append(
        _write_matrix(
            specs_root,
            "034-feature-status-state-model-remediation",
            _base_matrix(
                "034-feature-status-state-model-remediation",
                [_pending_invariant("NI-040")],
            ),
        )
    )
    paths.append(
        _write_matrix(
            specs_root,
            "docs-only-mission-01KY00AA",
            {
                "mission_slug": "docs-only-mission-01KY00AA",
                "mission_number": "",
                "mission_type": "documentation",
                "overall_verdict": "pending",
                "criteria": [],
                "negative_invariants": [],
            },
        )
    )
    return paths


def test_oracle_every_non_pending_result_has_valid_provenance_after_migration(
    tmp_path: Path,
) -> None:
    specs_root = tmp_path / "kitty-specs"
    paths = _build_measured_shape_corpus(specs_root)

    summary = run_backfill_provenance_migration(tmp_path)

    assert summary.errors == []
    # Two files needed no change (already-recorded, already-legacy_unrecorded,
    # pending-only, and criteria-only all count as "no non-pending row lacking
    # provenance"); the rest gained stamps.
    stamped_paths = {record.path for record in summary.migrated}
    assert stamped_paths == {
        p
        for p in paths
        if p.parent.name
        in {
            "unshim-wave2-01KWMCAX",
            "017-runtime-observability-baseline",
        }
    }

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        matrix = AcceptanceMatrix.from_dict(data)
        errors = validate_matrix_evidence(matrix)
        assert errors == [], f"{path}: {errors}"
        for invariant in matrix.negative_invariants:
            if invariant.result == "pending":
                continue
            assert invariant.provenance_origin in {
                PROVENANCE_RECORDED,
                PROVENANCE_LEGACY_UNRECORDED,
            }


# ---------------------------------------------------------------------------
# CLI registration — ``spec-kitty migrate backfill-provenance`` (FR-014
# operator-invokability). Mirrors
# ``tests/migration/test_backfill_topology_cli.py`` / the ``charter-encoding``
# twin's ``--help`` + end-to-end pattern in
# ``tests/migrate/test_charter_encoding_migration.py``.
# ---------------------------------------------------------------------------


def _extract_json(output: str) -> dict[str, Any]:
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON object found in output: {output!r}")
    payload: dict[str, Any] = json.loads(output[idx:])
    return payload


def test_cli_help_flag_registers_subcommand_and_options() -> None:
    """``spec-kitty migrate backfill-provenance --help`` is registered."""
    result = CliRunner().invoke(migrate_app, ["backfill-provenance", "--help"])

    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "backfill-provenance" in plain
    assert "--dry-run" in plain
    assert "--json" in plain
    assert "--project-root" in plain


def test_cli_dry_run_json_reports_without_writing(tmp_path: Path) -> None:
    """End-to-end CLI invocation: dry-run + JSON reports the plan; no writes."""
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "017-runtime-observability-baseline",
        _base_matrix(
            "017-runtime-observability-baseline",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )
    before = path.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        migrate_app,
        [
            "backfill-provenance",
            "--dry-run",
            "--json",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["dry_run"] is True
    assert payload["result"] == "success"
    assert payload["summary"]["files_inspected"] == 1
    assert payload["summary"]["migrated"] == 1
    assert payload["summary"]["invariants_stamped"] == 1
    assert path.read_text(encoding="utf-8") == before


def test_cli_live_run_writes_and_exits_zero(tmp_path: Path) -> None:
    """A real (non-dry-run) CLI invocation stamps the sentinel to disk."""
    specs_root = tmp_path / "kitty-specs"
    path = _write_matrix(
        specs_root,
        "017-runtime-observability-baseline",
        _base_matrix(
            "017-runtime-observability-baseline",
            [_pre_schema_confirmed_absent("NI-001")],
        ),
    )

    result = CliRunner().invoke(
        migrate_app,
        ["backfill-provenance", "--json", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["dry_run"] is False
    assert payload["summary"]["migrated"] == 1

    migrated = json.loads(path.read_text(encoding="utf-8"))
    stamped = migrated["negative_invariants"][0]
    assert stamped["provenance_origin"] == PROVENANCE_LEGACY_UNRECORDED


def test_cli_exits_nonzero_on_unparseable_matrix(tmp_path: Path) -> None:
    """A matrix the migration cannot parse surfaces as a non-zero exit (AM-4:
    reported, never auto-archived — see the module-level error tests above)."""
    feature_dir = tmp_path / "kitty-specs" / "broken-mission-01KY0006"
    feature_dir.mkdir(parents=True)
    (feature_dir / "acceptance-matrix.json").write_text(
        "{ not valid json", encoding="utf-8"
    )

    result = CliRunner().invoke(
        migrate_app,
        ["backfill-provenance", "--json", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _extract_json(result.output)
    assert payload["result"] == "errors_present"
    assert payload["summary"]["errors"] == 1
