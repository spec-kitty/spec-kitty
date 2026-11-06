"""Tests for the ``spec-kitty charter preflight`` typer command (WP03 / T020).

Covers:

* ``--json`` emits the binding shape (parseable, sorted keys).
* Exit-code matrix from ``contracts/charter-preflight-json.md``:
  passed → 0; non-passed without ``--strict`` → 0; non-passed with
  ``--strict`` → 1; hard error → 2.
* FR-005 (charter-preflight-remediation WP05): F1 ("no charter at all") is
  distinguishable from F4 (``charter.yaml`` present, unparseable) and from
  F2 (legacy bundle present, no ``charter.yaml``) on this surface's rendered
  ``detail`` text — the fix lives in ``computer.py`` (WP02's file); this
  module only proves it actually reaches the ``charter preflight`` operator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app

from tests._support.git_ceiling import GIT_CEILING_ENV

from ._fixtures import (
    build_f1_no_charter,
    build_f2_legacy_bundle_no_charter_yaml,
    build_f4_invalid_charter_yaml,
    init_git_repo,
    make_fresh_repo,
    seed_bundle_files,
    seed_charter,
    write_metadata,
)


pytestmark = [pytest.mark.integration]

_runner = CliRunner()


def test_command_is_registered() -> None:
    """``preflight`` must be discoverable via ``spec-kitty charter --help``."""
    result = _runner.invoke(charter_app, ["--help"])
    assert "preflight" in result.stdout


def test_passed_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh repo → JSON has ``passed=true`` → exit 0."""
    make_fresh_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["passed"] is True
    assert payload["blocked_reason"] is None


def test_non_strict_blocked_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Blocked without ``--strict`` → exit 0 (contract row 1)."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    # No manifest -> drg missing.

    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["passed"] is False
    assert payload["blocked_reason"] is not None


def test_strict_blocked_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--strict`` + non-passing → exit 1."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json", "--strict"])
    assert result.exit_code == 1, result.stdout


def test_hard_error_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No repo root found → exit 2 (no JSON payload).

    ``find_repo_root()`` walks to git's discovery ceiling. Bound that ceiling to this
    test's own tmp tree (issue #128): nothing above ``tmp_path`` is under test control,
    and under a full parallel run a sibling test's shared ancestor can transiently gain a
    ``.git``/``.kittify``, which would flip this "nothing found" verdict
    non-deterministically (same class of bug as #130/#139's ``_find_project_root``).
    ``GIT_CEILING_DIRECTORIES`` is the boundary now that the walk carries no ``stop=``
    of its own (#7076).
    """
    # tmp_path is not a git repo and has no .kittify ancestor -> find_repo_root raises.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(GIT_CEILING_ENV, str(tmp_path))
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    assert result.exit_code == 2, result.stdout


def test_json_is_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--json`` output uses sorted keys so it is byte-stable."""
    make_fresh_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    assert result.exit_code == 0
    payload_str = result.stdout.strip().splitlines()[-1]
    # If keys are sorted, re-dumping the parsed dict yields the same string.
    parsed = json.loads(payload_str)
    assert json.dumps(parsed, sort_keys=True, ensure_ascii=False) == payload_str


# ---------------------------------------------------------------------------
# FR-005 (WP05) — F1 vs F4 vs F2 distinguishability
# ---------------------------------------------------------------------------


def _charter_source_check(payload: dict[str, object]) -> dict[str, object]:
    checks = payload["checks"]
    assert isinstance(checks, list)
    (check,) = [c for c in checks if c["name"] == "charter_source"]
    return check


def test_f1_no_charter_reads_as_no_charter_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 — a project that never had a charter — must say so plainly."""
    build_f1_no_charter(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    check = _charter_source_check(payload)
    assert check["state"] == "missing"
    assert "no charter at all" in check["detail"]


def test_f4_invalid_charter_yaml_distinguishable_from_f1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F4 (``charter.yaml`` present, unparseable) must never read like F1
    ("no charter at all") — different state, different detail text."""
    build_f4_invalid_charter_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    check = _charter_source_check(payload)
    assert check["state"] == "invalid"
    assert "no charter at all" not in check["detail"]
    assert "cannot be parsed" in check["detail"]


def test_f2_legacy_bundle_does_not_read_as_no_charter_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F2 (legacy bundle present, no ``charter.yaml``) is the mission's
    trigger state: an operator who has a charter, just not in the required
    form, must not be told they have no charter at all. Before WP05, F1 and
    F2 rendered byte-identical output on this surface (both fell back to
    the generic "charter source is missing" text); this pins the fix."""
    build_f2_legacy_bundle_no_charter_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    check = _charter_source_check(payload)
    assert check["state"] == "missing"
    assert "no charter at all" not in check["detail"]
    assert "legacy charter bundle" in check["detail"]


def test_f1_and_f2_share_state_but_not_detail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real FR-005 gap: F1 and F2 both report ``state="missing"`` —
    identical on that axis — so an operator can only tell them apart via
    ``detail``. Regression-pin that the two texts differ."""
    monkeypatch.chdir(tmp_path)

    build_f1_no_charter(tmp_path)
    result_f1 = _runner.invoke(charter_app, ["preflight", "--json"])
    detail_f1 = _charter_source_check(json.loads(result_f1.stdout.strip().splitlines()[-1]))["detail"]

    f2_repo = tmp_path / "f2-sibling"
    f2_repo.mkdir()
    build_f2_legacy_bundle_no_charter_yaml(f2_repo)
    monkeypatch.chdir(f2_repo)
    result_f2 = _runner.invoke(charter_app, ["preflight", "--json"])
    detail_f2 = _charter_source_check(json.loads(result_f2.stdout.strip().splitlines()[-1]))["detail"]

    assert detail_f1 != detail_f2


def test_f1_still_non_blocking_without_strict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006 regression guard: making F1 distinguishable from F2/F4 must
    not make it blocking. A genuinely fresh/never-initialized project
    (true F1, not the legacy-bundle F2 shape ``test_non_strict_blocked_
    exits_zero`` already covers) still exits 0 without ``--strict``."""
    build_f1_no_charter(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _runner.invoke(charter_app, ["preflight", "--json"])
    assert result.exit_code == 0, result.stdout


def test_f1_and_f4_distinguishable_in_human_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same proof as the JSON tests above, but against the human-readable
    render path (``_render_human`` in ``cli.py`` — the file this WP owns)."""
    monkeypatch.chdir(tmp_path)
    build_f1_no_charter(tmp_path)
    result_f1 = _runner.invoke(charter_app, ["preflight"])
    assert "no charter at all" in result_f1.stdout

    f4_repo = tmp_path / "f4-sibling"
    f4_repo.mkdir()
    build_f4_invalid_charter_yaml(f4_repo)
    monkeypatch.chdir(f4_repo)
    result_f4 = _runner.invoke(charter_app, ["preflight"])
    assert "cannot be parsed" in result_f4.stdout
    assert "no charter at all" not in result_f4.stdout
