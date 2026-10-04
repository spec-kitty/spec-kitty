"""Tests for the #2758 bundle-incomplete fail-closed preflight (WP02),
re-homed onto charter.yaml by IC-04 (WP04).

Before consolidate-charter-bundle, ``charter.bundle.BUNDLE_CONTENT_HASH_FILES``
was a 4-file tuple (``governance.yaml`` / ``directives.yaml`` /
``references.yaml`` / ``metadata.yaml``), and this suite guarded the
"synced but never generated" dead end: ``compute_bundle_content_hash``
fail-safes to ``None`` when any of the four is missing, and the real-run
``charter synthesize`` write path silently persisted that ``None`` into the
synthesis manifest with no way to self-heal.

WP01 (this mission) inverted the bundle: ``BUNDLE_CONTENT_HASH_FILES`` is now
the single-element ``("charter.yaml",)`` -- charter.yaml is the ONE tracked,
content-hash input (the four legacy derived files are retired). The
"first-missing-file" preflight semantics this suite pins are UNCHANGED in
shape (:func:`first_missing_bundle_file` / :func:`_raise_if_bundle_incomplete`
/ the ``charter synthesize`` CLI preflight), just narrowed to the one file
that now matters: ``charter.yaml`` replaces ``references.yaml`` as the
"missing" name every assertion here checks for (#2758's own T020 follow-up).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.bundle import BUNDLE_CONTENT_HASH_FILES, CHARTER_YAML, compute_bundle_content_hash, first_missing_bundle_file
from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.charter._synthesis import (
    BUNDLE_INCOMPLETE_MESSAGE,
    _raise_if_bundle_incomplete,
)
from specify_cli.task_utils import TaskCliError

pytestmark = pytest.mark.unit

runner = CliRunner()

_MINIMAL_CHARTER_YAML = "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\n"

# NFR-002 pinned expectation: computed once from the UNCHANGED
# compute_bundle_content_hash recipe over this fixed single-file content. If
# this WP ever touches the hashing recipe (it must not), this assertion goes
# red.
_COMPLETE_BUNDLE_PINNED_HASH = (
    "sha256:428280f0c3aaa4ba18a9c2ac0d45f611a742add2e7f6c3171767ac6a240c1cf8"
)


def _seed_charter_md_only(repo_root: Path) -> Path:
    """Mirror a project that has ``charter.md`` but no ``charter.yaml`` yet
    (never bootstrapped / never generated) -- the "nothing to hash" state.
    """
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
    return charter_dir


def _seed_complete_bundle(repo_root: Path) -> Path:
    charter_dir = _seed_charter_md_only(repo_root)
    (repo_root / CHARTER_YAML).write_text(_MINIMAL_CHARTER_YAML, encoding="utf-8")
    return charter_dir


def _seed_generated_artifact_marker(charter_dir: Path) -> None:
    """Make ``_has_generated_artifacts`` True so the fresh-project short-circuit
    in ``charter_synthesize`` is bypassed and the real-run write path is
    reached (the code path this preflight guards)."""
    generated_dir = charter_dir / "generated" / "directives"
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "sample.directive.yaml").write_text("id: PROJECT_001\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# T005 -- red-first: repro the CURRENT dead-end (compute_bundle_content_hash
# side; this contract stays exactly as-is -- see NFR-002 below)
# ---------------------------------------------------------------------------


def test_charter_yaml_absent_bundle_hashes_to_none(tmp_path: Path) -> None:
    """charter.yaml absent -> None (unchanged fail-safe contract of
    compute_bundle_content_hash)."""
    _seed_charter_md_only(tmp_path)

    assert compute_bundle_content_hash(tmp_path) is None


def test_first_missing_bundle_file_identifies_charter_yaml(tmp_path: Path) -> None:
    """The preflight helper names the missing file precisely -- this is
    the signal compute_bundle_content_hash's bare None cannot carry."""
    _seed_charter_md_only(tmp_path)

    assert first_missing_bundle_file(tmp_path) == "charter.yaml"


def test_first_missing_bundle_file_none_when_complete(tmp_path: Path) -> None:
    _seed_complete_bundle(tmp_path)

    assert first_missing_bundle_file(tmp_path) is None


@pytest.mark.parametrize("omit", list(BUNDLE_CONTENT_HASH_FILES))
def test_first_missing_bundle_file_reports_whichever_is_absent(tmp_path: Path, omit: str) -> None:
    """First-missing-in-declared-order semantics -- with a single-element
    tuple this collapses to one case, but the parametrization is kept so a
    future widening of BUNDLE_CONTENT_HASH_FILES re-exercises this test
    without hand-editing it."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    contents = {"charter.yaml": _MINIMAL_CHARTER_YAML}
    for name, text in contents.items():
        if name == omit:
            continue
        (charter_dir / name).write_text(text, encoding="utf-8")

    assert first_missing_bundle_file(tmp_path) == omit


# ---------------------------------------------------------------------------
# T006 -- the fail-closed preflight helper itself
# ---------------------------------------------------------------------------


def test_raise_if_bundle_incomplete_raises_task_cli_error(tmp_path: Path) -> None:
    _seed_charter_md_only(tmp_path)

    with pytest.raises(TaskCliError) as excinfo:
        _raise_if_bundle_incomplete(tmp_path)

    message = str(excinfo.value)
    assert message == BUNDLE_INCOMPLETE_MESSAGE.format(missing="charter.yaml")
    assert "charter generate" in message


def test_raise_if_bundle_incomplete_is_noop_when_bundle_complete(tmp_path: Path) -> None:
    _seed_complete_bundle(tmp_path)

    # Must not raise.
    _raise_if_bundle_incomplete(tmp_path)


# ---------------------------------------------------------------------------
# T007 -- CLI-level: `charter synthesize` fails closed with the actionable
# message instead of silently reaching the write path
# ---------------------------------------------------------------------------


def test_synthesize_json_fails_closed_when_charter_yaml_missing(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    charter_dir = _seed_charter_md_only(tmp_path)
    _seed_generated_artifact_marker(charter_dir)

    evidence_result = SimpleNamespace(warnings=[], bundle=SimpleNamespace())

    charter_cwd_isolation()
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.charter._collect_evidence_result", return_value=evidence_result),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(SimpleNamespace(), SimpleNamespace()),
        ),
    ):
        result = runner.invoke(charter_app, ["synthesize", "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "failure"
    expected_message = BUNDLE_INCOMPLETE_MESSAGE.format(missing="charter.yaml")
    assert any(expected_message in warning for warning in payload["warnings"])
    assert any("charter generate" in warning for warning in payload["warnings"])


def test_synthesize_json_succeeds_past_preflight_when_bundle_complete(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Sanity check the guard is not overbroad: a complete bundle does not
    trip the preflight (the real synthesize() call is mocked out here since
    this test is only proving the preflight did not fire, not exercising the
    full synthesis pipeline)."""
    charter_dir = _seed_complete_bundle(tmp_path)
    _seed_generated_artifact_marker(charter_dir)

    evidence_result = SimpleNamespace(warnings=[], bundle=SimpleNamespace())
    synth_result = SimpleNamespace(
        effective_adapter_id="generated",
        effective_adapter_version="0.0.0",
        target_kind="directive",
        target_slug="synthesize-placeholder",
        inputs_hash="deadbeef",
    )

    charter_cwd_isolation()
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.charter._collect_evidence_result", return_value=evidence_result),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(SimpleNamespace(), SimpleNamespace()),
        ),
        patch("charter.activation.synthesizer.synthesize", return_value=synth_result),
        patch(
            "specify_cli.cli.commands.charter._load_written_artifacts_from_manifest",
            return_value=[],
        ),
    ):
        result = runner.invoke(charter_app, ["synthesize", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "success"


# ---------------------------------------------------------------------------
# NFR-002 -- a COMPLETE bundle's compute_bundle_content_hash is byte-unchanged
# by this WP (this WP adds a guard BEFORE the None path; it never touches the
# hashing recipe itself)
# ---------------------------------------------------------------------------


def test_complete_bundle_hash_is_deterministic_and_pinned(tmp_path: Path) -> None:
    _seed_complete_bundle(tmp_path)

    first = compute_bundle_content_hash(tmp_path)
    second = compute_bundle_content_hash(tmp_path)

    assert first == second == _COMPLETE_BUNDLE_PINNED_HASH
