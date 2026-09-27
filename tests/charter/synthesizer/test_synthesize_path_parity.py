"""Dry-run / non-dry-run path-parity guards (WP02 — Charter Contract Cleanup Tranche 1).

These tests pin two contracts the mission spec calls out as load-bearing:

* **FR-004 (path parity).** ``charter synthesize --dry-run --json`` MUST
  report ``written_artifacts[*].path`` byte-equal to the path a subsequent
  non-dry-run with the same ``SynthesisRequest`` writes. The two code
  paths share a single derivation function
  (:func:`charter.activation.synthesizer.write_pipeline.compute_written_artifacts`)
  so this test exists as a regression guard against drift.
* **FR-005 (no user-visible PROJECT_000).** No envelope value (string,
  key, or substring) emitted on stdout contains the placeholder
  ``PROJECT_000``. Internal-only use is acceptable; user-visible
  appearance is a hard failure.

The first test exercises the in-memory ``compute_written_artifacts``
helper directly so the parity check is independent of the CLI envelope
shape (the CLI test files in ``tests/integration/`` and
``tests/agent/cli/commands/`` cover the wire-level shape).

The second test invokes the actual ``charter synthesize --json`` command
through Typer's ``CliRunner`` and grep-asserts the placeholder is absent
from the entire JSON-serialised envelope.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget
from charter.activation.synthesizer.synthesize_pipeline import run_all
from charter.activation.synthesizer.write_pipeline import (
    _artifact_id_from_provenance,
    compute_written_artifacts,
)


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parity_interview_snapshot() -> dict[str, Any]:
    """Interview snapshot that exercises a non-PROJECT_000 directive target.

    The provenance pipeline keys every produced artifact off the target's
    ``artifact_id``; we deliberately use ``PROJECT_001`` (per spec
    ``research.md`` §R-004 example) so the path-parity assertion is testing
    a live, non-placeholder code path.
    """
    return {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }


@pytest.fixture
def minimal_doctrine_snapshot() -> dict[str, Any]:
    return {
        "directives": {
            "DIRECTIVE_003": {
                "id": "DIRECTIVE_003",
                "title": "Decision Documentation",
                "body": "Document significant architectural decisions via ADRs.",
            }
        },
        "tactics": {},
        "styleguides": {},
    }


@pytest.fixture
def minimal_drg_snapshot() -> dict[str, Any]:
    return {
        "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
        "edges": [],
        "schema_version": "1",
    }


@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "synthesizer"


@pytest.fixture
def fixture_adapter(fixture_root: Path) -> FixtureAdapter:
    return FixtureAdapter(fixture_root=fixture_root)


@pytest.fixture
def parity_request(
    parity_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
) -> SynthesisRequest:
    """A SynthesisRequest whose provenance yields a non-placeholder artifact_id.

    ``artifact_id="PROJECT_001"`` — never ``PROJECT_000`` — so a regression
    that leaks the placeholder into a written-artifact path would fail the
    path parity assertion AND the no-PROJECT_000 grep below.
    """
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=parity_interview_snapshot,
        doctrine_snapshot=minimal_doctrine_snapshot,
        drg_snapshot=minimal_drg_snapshot,
        run_id="01KQATS4PARITYTEST00000001",
        adapter_hints={"language": "python"},
    )


# ---------------------------------------------------------------------------
# T010 / FR-004 — dry-run path == real-run path
# ---------------------------------------------------------------------------


def _entries_to_comparable(entries: list[Any]) -> list[tuple[str, str | None]]:
    """Project to ``(path, artifact_id)`` tuples sorted by path.

    ``run_all`` order is deterministic but we sort defensively so the
    assertion holds even if a future ordering change ships separately
    from the CLI surface.
    """
    return sorted([(e.path, e.artifact_id) for e in entries], key=lambda t: t[0])


def test_dry_run_paths_match_real_run_paths(
    parity_request: SynthesisRequest,
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """``compute_written_artifacts`` MUST be deterministic across two ``run_all`` calls.

    This is the unit-level proof of FR-004: the typed staged-artifact
    entries the CLI surfaces in ``written_artifacts`` are byte-equal on
    ``path`` and ``artifact_id`` whether the run is a dry-run or a
    non-dry-run, given the same ``SynthesisRequest`` and adapter.
    """
    # Two independent ``run_all`` invocations using the SAME request +
    # adapter — analogous to a dry-run followed by a non-dry-run.
    results_a = run_all(parity_request, adapter=fixture_adapter)
    results_b = run_all(parity_request, adapter=fixture_adapter)

    entries_a = compute_written_artifacts(results_a, tmp_path)
    entries_b = compute_written_artifacts(results_b, tmp_path)

    # Both runs must produce non-empty entries (otherwise the test is a
    # no-op). The fixture set delivers at least one directive artifact
    # for the parity_request inputs (PROJECT_001 directive).
    assert len(entries_a) >= 1, "expected at least one staged artifact"
    assert len(entries_b) == len(entries_a), f"entry count drifted: a={len(entries_a)} vs b={len(entries_b)}"

    # Per-element path + artifact_id must match (FR-004 byte-equal).
    cmp_a = _entries_to_comparable(entries_a)
    cmp_b = _entries_to_comparable(entries_b)
    assert cmp_a == cmp_b, f"dry-run vs real-run paths drifted:\n  a={cmp_a}\n  b={cmp_b}"

    # Each entry path is repo-relative POSIX (no leading '/'; uses '/'
    # separator). This nails the wire-shape contract from data-model §E-3.
    for entry in entries_a:
        assert not entry.path.startswith("/"), entry.path
        assert "\\" not in entry.path, entry.path
        # FR-005: the placeholder must NOT be embedded in the path.
        assert "PROJECT_000" not in entry.path, entry.path

    # The PROJECT_001 directive in particular must surface a directive
    # entry whose artifact_id is the symbolic id (not None), so the
    # parity guard is testing real provenance.
    directive_entries = [e for e in entries_a if e.kind == "directive"]
    assert directive_entries, "expected at least one directive entry"
    for entry in directive_entries:
        assert entry.artifact_id is not None, f"directive entry lacks artifact_id (regression): {entry}"
        assert entry.artifact_id != "PROJECT_000", f"directive surfaced placeholder PROJECT_000: {entry}"


@pytest.mark.parametrize(
    "artifact_urn",
    ["directive:", "directive:PROJECT_000", "not-a-directive-urn"],
)
def test_directive_provenance_rejects_missing_or_placeholder_ids(
    artifact_urn: str,
) -> None:
    """Directive provenance must fail closed instead of falling back to a 000 path."""
    prov = SimpleNamespace(artifact_kind="directive", artifact_urn=artifact_urn)

    with pytest.raises(ValueError):
        _artifact_id_from_provenance(prov)


# ---------------------------------------------------------------------------
# T010 / FR-005 — no user-visible PROJECT_000 in the JSON envelope
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    """Initialize a minimal git repo so ``find_repo_root`` succeeds."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _seed_minimal_interview(repo: Path) -> None:
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: PROJECT_000-leak guard test fixture.\n",
        encoding="utf-8",
    )
    # ``charter generate``/``synthesize`` both read ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority
    # for mission types) -- provision ``mission_type_activations`` on this
    # fresh-seed project so the CLI invocations below don't hard-fail on a
    # genuinely absent key that's unrelated to this test's own subject
    # (the PROJECT_000 placeholder-leak guard).
    kittify = repo / ".kittify"
    (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")


def test_no_user_visible_placeholder_in_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The placeholder ``PROJECT_000`` MUST NOT appear in the envelope (FR-005).

    Drives the actual ``charter synthesize --json`` CLI through a fresh
    project (the fresh-seed path is the simplest deterministic envelope
    producer that does not require LLM-authored YAMLs). The JSON envelope
    is parsed and re-serialised; the assertion is a substring search over
    the full serialised form.
    """
    from specify_cli.cli.commands.charter import app as charter_app

    runner = CliRunner()
    _git_init(tmp_path)
    _seed_minimal_interview(tmp_path)

    # Run charter generate to produce charter.md (fresh-seed precondition).
    monkeypatch.chdir(tmp_path)
    gen = runner.invoke(charter_app, ["generate", "--from-interview"], catch_exceptions=False)
    assert gen.exit_code == 0, f"charter generate failed: {gen.stdout!r}"

    result = runner.invoke(charter_app, ["synthesize", "--json"], catch_exceptions=False)

    assert result.exit_code == 0, f"synthesize failed: {result.stdout!r}"

    # FR-001: full stdout MUST be a single JSON document.
    envelope = json.loads(result.stdout)

    # FR-005: re-serialise and grep — covers keys, values, nested values.
    serialised = json.dumps(envelope)
    assert "PROJECT_000" not in serialised, f"PROJECT_000 leaked into the user-visible envelope: {serialised!r}"
