"""Regression tests for ``spec-kitty migrate charter-encoding``.

Covers:
- T039: CLI surface (help flag, --help)
- T040: corpus scan — files discovered in kitty-specs/*/charter/ and .kittify/charter/
- T041: interactive default / --dry-run / --yes modes
- T042: idempotency — second run writes no new provenance records (NFR-006)
- T043: JSON-stable summary report + non-zero exit on ambiguous files

All filesystem I/O is in tmp_path fixtures. No network calls.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from tests._support.eacces import mode_bits_enforced


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_cp1252_file(path: Path, text: str | None = None) -> None:
    """Write a file in cp1252 encoding (bytes that are not valid UTF-8).

    The default text is chosen to be long enough that charset-normalizer
    detects it as cp1252 with >= 0.85 confidence (not ambiguous).
    """
    if text is None:
        # Use a multi-word text with several cp1252 high-byte characters so
        # charset-normalizer can detect it confidently.
        text = "R\xe9sum\xe9 na\xefve caf\xe9 H\xf4tel"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("cp1252"))


def _make_utf8_file(path: Path, text: str = "café naïve") -> None:
    """Write a file in UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _extract_json(output: str) -> dict[str, Any]:
    """Extract the JSON object from mixed CLI output (stdout+stderr in CliRunner).

    CliRunner merges stdout and stderr; diagnostic lines may precede the JSON.
    We locate the first '{' of the outermost JSON object and parse from there.
    """
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON object found in output: {output!r}")
    payload: dict[str, Any] = json.loads(output[idx:])
    return payload


def _count_provenance_records(provenance_path: Path) -> int:
    """Return the number of lines (records) in a provenance JSONL file."""
    if not provenance_path.exists():
        return 0
    return sum(1 for line in provenance_path.read_text(encoding="utf-8").splitlines() if line.strip())


# ---------------------------------------------------------------------------
# T039: CLI surface
# ---------------------------------------------------------------------------


def test_help_flag() -> None:
    """charter-encoding subcommand is registered and --help exits 0."""
    runner = CliRunner()
    result = runner.invoke(migrate_app, ["charter-encoding", "--help"])

    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "charter-encoding" in plain
    assert "--dry-run" in plain
    assert "--yes" in plain
    assert "--json" in plain
    assert "--project-root" in plain


# ---------------------------------------------------------------------------
# T040: Corpus scan
# ---------------------------------------------------------------------------


def test_corpus_scan_discovers_mission_charter_files(tmp_path: Path) -> None:
    """Files in kitty-specs/*/charter/*.yaml are discovered."""
    charter_dir = tmp_path / "kitty-specs" / "042-foo-feature" / "charter"
    _make_utf8_file(charter_dir / "charter.yaml")
    _make_utf8_file(charter_dir / "notes.md")
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--dry-run", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["files_inspected"] == 2


def test_corpus_scan_discovers_global_charter_files(tmp_path: Path) -> None:
    """Files in .kittify/charter/*.yaml are discovered."""
    global_charter = tmp_path / ".kittify" / "charter"
    _make_utf8_file(global_charter / "global.yaml")
    (tmp_path / "kitty-specs").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--dry-run", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["files_inspected"] == 1


def test_corpus_scan_empty_project_returns_zero(tmp_path: Path) -> None:
    """No charter directories → files_inspected == 0, exit 0."""
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["files_inspected"] == 0
    assert payload["result"] == "success"


def test_collect_charter_files_unstattable_mission_candidate_is_not_silently_skipped(
    tmp_path: Path,
) -> None:
    """`#3194`: the `mission_dir.is_dir()` filter in `_collect_charter_files` must
    not use the EACCES-divergent predicate.

    `Path.is_dir()` answers `False` for an unreadable candidate on Python 3.14
    only (RAISES on 3.11-3.13) — silently dropping the candidate (and any
    charter files under it) from the corpus scan with no signal, the same shape
    `#3177` fixed in `specify_cli.decisions.ownership`. `safe_is_dir` makes this
    raise on every interpreter instead.
    """
    from specify_cli.cli.commands.migrate.charter_encoding import _collect_charter_files

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    (specs / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

    canary = vault / "canary"
    canary.write_text("{}", encoding="utf-8")
    os.chmod(vault, 0o000)
    try:
        if not mode_bits_enforced(canary):
            pytest.skip(
                "SKIPPED HONESTLY, not passed: this process can stat through a "
                "0o000 directory (running as root, or a filesystem that ignores "
                "mode bits), so the branch cannot be constructed here."
            )
        with pytest.raises(OSError):
            _collect_charter_files(tmp_path)
    finally:
        os.chmod(vault, 0o700)


# ---------------------------------------------------------------------------
# T041: Mode tests
# ---------------------------------------------------------------------------


def test_dry_run_does_not_rewrite_files(tmp_path: Path) -> None:
    """--dry-run reports would-normalize but leaves files unchanged on disk."""
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    cp1252_file = charter_dir / "charter.yaml"
    _make_cp1252_file(cp1252_file)
    original_bytes = cp1252_file.read_bytes()
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--dry-run", "--json", "--project-root", str(tmp_path)],
    )
    # dry-run: exit 0 (no ambiguity)
    assert result.exit_code == 0, result.output
    # File content unchanged
    assert cp1252_file.read_bytes() == original_bytes


def test_yes_flag_normalizes_without_prompt(tmp_path: Path) -> None:
    """--yes applies normalizations without prompting; file becomes valid UTF-8."""
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    cp1252_file = charter_dir / "charter.yaml"
    # Use multi-word text with high-byte cp1252 chars for confident detection.
    _make_cp1252_file(cp1252_file)
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["result"] == "success"
    assert [Path(r["path"]).name for r in payload["normalized"]] == ["charter.yaml"]
    # File must now be valid UTF-8 (no UnicodeDecodeError).
    normalized_text = cp1252_file.read_text(encoding="utf-8")
    assert len(normalized_text) > 0


def test_yes_exits_nonzero_on_ambiguous_file(tmp_path: Path) -> None:
    """--yes exits non-zero when any file is ambiguous (CI contract).

    The mock patches ``charter.activation._io.load_charter_file`` — the canonical location
    used by the lazy local import in charter_encoding.py.
    """
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    ambiguous_file = charter_dir / "charter.yaml"
    ambiguous_file.parent.mkdir(parents=True, exist_ok=True)
    # Write non-UTF-8 bytes so the idempotency pre-check fails and the
    # chokepoint is invoked (then mocked to raise CharterEncodingError).
    ambiguous_file.write_bytes(bytes(range(0x80, 0xA0)))
    (tmp_path / ".kittify").mkdir()

    from charter.activation._diagnostics import CharterEncodingDiagnostic
    from charter.activation._io import CharterEncodingError

    with patch("charter.activation._io.load_charter_file") as mock_load:
        mock_load.side_effect = CharterEncodingError(
            CharterEncodingDiagnostic.AMBIGUOUS,
            "ERROR: CHARTER_ENCODING_AMBIGUOUS\n  File: charter.yaml\n  ...",
        )
        runner = CliRunner()
        result = runner.invoke(
            migrate_app,
            ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
        )

    # Must exit non-zero
    assert result.exit_code != 0
    payload = _extract_json(result.output)
    assert payload["result"] == "ambiguous_present"
    assert [Path(r["path"]).name for r in payload["ambiguous"]] == ["charter.yaml"]


# ---------------------------------------------------------------------------
# T042: Idempotency (NFR-006)
# ---------------------------------------------------------------------------


def test_idempotency_second_run_is_noop(tmp_path: Path) -> None:
    """Running the migration twice on a normalized corpus is idempotent.

    After the first run all files are UTF-8 — the idempotency pre-check
    (_is_pure_utf8) short-circuits them on the second run, so no new
    provenance records are written.
    """
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    cp1252_file = charter_dir / "charter.yaml"
    _make_cp1252_file(cp1252_file)  # multi-word text for confident detection
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()

    # First run: normalizes the cp1252 file.
    result1 = runner.invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )
    assert result1.exit_code == 0, result1.output
    payload1 = _extract_json(result1.output)
    assert [Path(r["path"]).name for r in payload1["normalized"]] == ["charter.yaml"]

    # Count provenance records written by the first run.
    provenance_path = tmp_path / "kitty-specs" / "042-foo" / ".encoding-provenance.jsonl"
    records_after_first_run = _count_provenance_records(provenance_path)
    assert records_after_first_run >= 1, "First run should have written at least one provenance record"

    # Second run: file is already UTF-8 → pre-check skips it → no new provenance.
    result2 = runner.invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )
    assert result2.exit_code == 0, result2.output
    payload2 = _extract_json(result2.output)
    # File is in already_utf8 bucket, not normalized
    assert len(payload2["normalized"]) == 0
    assert [Path(p).name for p in payload2["already_utf8"]] == ["charter.yaml"]

    # No new provenance records written on second run.
    records_after_second_run = _count_provenance_records(provenance_path)
    assert records_after_second_run == records_after_first_run, (
        f"Second run wrote {records_after_second_run - records_after_first_run} extra "
        "provenance record(s); idempotency contract violated (NFR-006)."
    )


def test_idempotency_precheck_skips_utf8_files_without_chokepoint(tmp_path: Path) -> None:
    """Already-UTF-8 files are skipped without invoking load_charter_file.

    This verifies the idempotency pre-check short-circuits the chokepoint,
    preventing new provenance records on re-runs.
    """
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    _make_utf8_file(charter_dir / "charter.yaml")
    (tmp_path / ".kittify").mkdir()

    with patch("charter.activation._io.load_charter_file") as mock_load:
        runner = CliRunner()
        result = runner.invoke(
            migrate_app,
            ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
        )
        # Chokepoint was never called — the pre-check short-circuited it.
        mock_load.assert_not_called()

    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert [Path(p).name for p in payload["already_utf8"]] == ["charter.yaml"]
    assert len(payload["normalized"]) == 0


# ---------------------------------------------------------------------------
# T043: JSON-stable summary report
# ---------------------------------------------------------------------------


def test_json_summary_schema_stability(tmp_path: Path) -> None:
    """JSON output has the expected top-level keys (schema stability)."""
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)

    required_keys = {"result", "files_inspected", "already_utf8", "normalized", "ambiguous", "dry_run"}
    assert required_keys <= set(payload.keys()), (
        f"Missing keys: {required_keys - set(payload.keys())}"
    )


def test_json_dry_run_flag_reflected_in_output(tmp_path: Path) -> None:
    """JSON summary sets ``dry_run: true`` when --dry-run is passed."""
    (tmp_path / ".kittify").mkdir()

    runner = CliRunner()
    result = runner.invoke(
        migrate_app,
        ["charter-encoding", "--dry-run", "--json", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["dry_run"] is True


def test_json_result_ambiguous_present_when_ambiguous(tmp_path: Path) -> None:
    """``result`` field is ``ambiguous_present`` and exit is non-zero when files are ambiguous.

    Patches ``charter.activation._io.load_charter_file`` (the canonical module location
    used by the lazy local import in charter_encoding.py).
    """
    charter_dir = tmp_path / "kitty-specs" / "042-foo" / "charter"
    bad_file = charter_dir / "charter.yaml"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    # Write non-UTF-8 bytes so idempotency pre-check fails.
    bad_file.write_bytes(bytes(range(0x80, 0xA0)))
    (tmp_path / ".kittify").mkdir()

    from charter.activation._diagnostics import CharterEncodingDiagnostic
    from charter.activation._io import CharterEncodingError

    with patch("charter.activation._io.load_charter_file") as mock_load:
        mock_load.side_effect = CharterEncodingError(
            CharterEncodingDiagnostic.AMBIGUOUS,
            "ERROR: CHARTER_ENCODING_AMBIGUOUS\n  File: charter.yaml",
        )
        runner = CliRunner()
        result = runner.invoke(
            migrate_app,
            ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
        )

    assert result.exit_code != 0
    payload = _extract_json(result.output)
    assert payload["result"] == "ambiguous_present"
    ambiguous_paths = [a["path"] for a in payload["ambiguous"]]
    assert any("charter.yaml" in p for p in ambiguous_paths)


# ---------------------------------------------------------------------------
# #4962 backup-collision contract (ported from the retired subprocess file
# tests/regressions/test_issue_4962_charter_encoding.py, case 3; #5621)
# ---------------------------------------------------------------------------

_COLLISION_TEXT = "# Team Charter\n\n" + "Tests must pass before merge.\n" * 10 + "We don’t ship on Fridays — the “freeze” rule. Owner: José Peña, São Paulo.\n"
_STALE_BACKUP = b"stale backup from an earlier run\n"


def test_preexisting_backup_blocks_normalization(tmp_path: Path) -> None:
    """#4962: a pre-existing ``.bak`` blocks normalization; nothing is overwritten.

    The defect is fixed; this is a permanent guard. Drives the migration
    command in-process (no subprocess) and pins the defined collision
    behaviour: the stale backup and the still-cp1252 source stay byte-identical,
    the collision is reported in the JSON payload, and the exit is non-zero.
    """
    charter_file = tmp_path / "kitty-specs" / "001-issue-4962" / "charter" / "charter.md"
    charter_file.parent.mkdir(parents=True)
    (tmp_path / ".kittify").mkdir()
    original_bytes = _COLLISION_TEXT.encode("cp1252")
    charter_file.write_bytes(original_bytes)
    backup_file = charter_file.with_name(charter_file.name + ".bak")
    backup_file.write_bytes(_STALE_BACKUP)

    result = CliRunner().invoke(
        migrate_app,
        ["charter-encoding", "--yes", "--json", "--project-root", str(tmp_path)],
    )

    assert result.exit_code != 0, result.output
    payload = _extract_json(result.output)
    assert payload["result"] == "backup_collision_present"
    assert [Path(r["path"]).name for r in payload["backup_collisions"]] == ["charter.md"]
    assert payload["normalized"] == []
    assert backup_file.read_bytes() == _STALE_BACKUP, "a pre-existing .bak must never be silently overwritten"
    assert charter_file.read_bytes() == original_bytes, "the source file must stay untouched when its backup collides"


def test_write_normalized_with_backup_refuses_existing_backup(tmp_path: Path) -> None:
    """#4962 seam: the writer itself refuses a colliding ``.bak`` (defence in depth).

    The command loop pre-checks for a collision; this pins the writer's own
    refusal so removing either layer is caught.
    """
    from specify_cli.cli.commands.migrate.charter_encoding import (
        _BackupCollisionError,
        _write_normalized_with_backup,
    )

    charter_file = tmp_path / "charter.md"
    original_bytes = _COLLISION_TEXT.encode("cp1252")
    charter_file.write_bytes(original_bytes)
    backup_file = tmp_path / "charter.md.bak"
    backup_file.write_bytes(_STALE_BACKUP)

    with pytest.raises(_BackupCollisionError):
        _write_normalized_with_backup(charter_file, _COLLISION_TEXT, original_bytes)

    assert backup_file.read_bytes() == _STALE_BACKUP
    assert charter_file.read_bytes() == original_bytes
    assert sorted(p.name for p in tmp_path.iterdir()) == ["charter.md", "charter.md.bak"], "no temp file left behind"


def test_write_normalized_with_backup_preserves_original_bytes(tmp_path: Path) -> None:
    """#4962 seam: the happy path writes a recoverable ``.bak`` and a byte-exact UTF-8 target.

    Operators rely on the ``.bak`` holding the exact original bytes; the target
    must be byte-exact UTF-8 and no temp file may be left behind.
    """
    from specify_cli.cli.commands.migrate.charter_encoding import _write_normalized_with_backup

    charter_file = tmp_path / "charter.md"
    original_bytes = _COLLISION_TEXT.encode("cp1252")
    charter_file.write_bytes(original_bytes)

    _write_normalized_with_backup(charter_file, _COLLISION_TEXT, original_bytes)

    assert (tmp_path / "charter.md.bak").read_bytes() == original_bytes
    assert charter_file.read_bytes() == _COLLISION_TEXT.encode("utf-8")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["charter.md", "charter.md.bak"], "no temp file left behind"
