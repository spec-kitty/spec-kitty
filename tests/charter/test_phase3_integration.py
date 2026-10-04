"""Phase 3 integration tests — all Phase 3 acceptance gates from #465.

These tests exercise the complete Phase 3 pipeline components:
- EvidenceBundle structure and populating (Gate 1)
- Evidence enrichment changes inputs_hash (Gate 2)
- ProvenanceEntry has evidence_bundle_hash + corpus_snapshot_id (Gate 3)
- SynthesisRequest.evidence field correctly threaded (Gate 4)
- Neutrality gate _is_generic_scoped scoping logic (Gate 5)
- NeutralityGateViolation field structure (Gate 6)
- CorpusLoader returns CorpusSnapshot for Python profile (Gate 7)
- CodeReadingCollector detects Python project (Gate 8)
- CLI --dry-run-evidence exits 0 and prints summary (Gate 9)

No call to the full orchestrator.synthesize() is required — the components
are tested directly per the WP07 recommended approach.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from charter.activation.synthesizer.evidence import (    CodeSignals,
    CorpusEntry,
    CorpusSnapshot,
    EvidenceBundle,
)
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: trampoline bug: subprocess
pytestmark = pytest.mark.non_sandbox


# ---------------------------------------------------------------------------
# Shared helper: enriched evidence bundle
# ---------------------------------------------------------------------------


def _make_evidence() -> EvidenceBundle:
    """Construct the standard enriched-evidence bundle for Phase 3 tests.

    Uses empty strings for timestamps (excluded from hash computation) so that
    fixture hash lookups are deterministic regardless of when tests are run.
    """
    cs = CodeSignals(
        stack_id="python+django+pytest",
        primary_language="python",
        frameworks=("django",),
        test_frameworks=("pytest",),
        scope_tag="python",
        representative_files=("src/myapp/models.py", "tests/test_models.py"),
        detected_at="",  # excluded from hash
    )
    corpus = CorpusSnapshot(
        snapshot_id="python-v1.0.0",
        profile_key="python",
        entries=(
            CorpusEntry(
                topic="testing philosophy",
                tags=("testing",),
                guidance="Test at multiple levels.",
            ),
        ),
        loaded_at="",  # excluded from hash
    )
    return EvidenceBundle(
        code_signals=cs,
        url_list=("https://docs.djangoproject.com/", "https://docs.pytest.org/"),
        corpus_snapshot=corpus,
        collected_at="",  # excluded from hash
    )


# ---------------------------------------------------------------------------
# Gate 1: EvidenceBundle correctly structures all three evidence source types
# ---------------------------------------------------------------------------


def test_phase3_evidence_bundle_structure() -> None:
    """Gate 1: EvidenceBundle carries code signals, URL list, and corpus snapshot."""
    bundle = _make_evidence()

    assert not bundle.is_empty, "Enriched bundle must not be empty"
    assert bundle.code_signals is not None, "code_signals must be populated"
    assert bundle.code_signals.stack_id == "python+django+pytest"
    assert bundle.code_signals.primary_language == "python"
    assert bundle.code_signals.scope_tag == "python"
    assert "django" in bundle.code_signals.frameworks
    assert "pytest" in bundle.code_signals.test_frameworks
    assert bundle.url_list == (
        "https://docs.djangoproject.com/",
        "https://docs.pytest.org/",
    )
    assert "https://docs.djangoproject.com/" in bundle.url_list
    assert bundle.corpus_snapshot is not None, "corpus_snapshot must be populated"
    assert bundle.corpus_snapshot.snapshot_id == "python-v1.0.0"
    assert bundle.corpus_snapshot.profile_key == "python"
    assert {e.topic for e in bundle.corpus_snapshot.entries} == {"testing philosophy"}
    assert bundle.corpus_snapshot.entries[0].topic == "testing philosophy"


# ---------------------------------------------------------------------------
# Gate 2: Same interview + different evidence → different inputs_hash
# ---------------------------------------------------------------------------


def test_phase3_hash_differentiation() -> None:
    """Gate 2: enriched evidence produces a different inputs_hash than no evidence."""
    from charter.activation.synthesizer.request import compute_inputs_hash

    target = SynthesisTarget(
        kind="tactic",
        slug="how-we-apply-directive-010",
        title="How we apply Directive 010",
        artifact_id="how-we-apply-directive-010",
        source_section="testing_philosophy",
        source_urns=("urn:drg:directive:DIRECTIVE_010",),
    )
    base_kwargs: dict = dict(
        target=target,
        interview_snapshot={"testing_philosophy": "We test at multiple levels."},
        doctrine_snapshot={},
        drg_snapshot={},
        run_id="test",
    )

    req_empty = SynthesisRequest(**base_kwargs)
    hash_empty = compute_inputs_hash(req_empty, "fixture", "1.0.0")

    req_enriched = SynthesisRequest(**base_kwargs, evidence=_make_evidence())
    hash_enriched = compute_inputs_hash(req_enriched, "fixture", "1.0.0")

    assert hash_empty != hash_enriched, (
        "Enriched evidence must change the inputs_hash; "
        f"both produced: {hash_empty[:12]}"
    )


# ---------------------------------------------------------------------------
# Gate 3: ProvenanceEntry has evidence_bundle_hash and corpus_snapshot_id fields
# ---------------------------------------------------------------------------


def test_phase3_provenance_fields_exist() -> None:
    """Gate 3: ProvenanceEntry Pydantic model has evidence_bundle_hash and corpus_snapshot_id."""
    from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry

    # ProvenanceEntry is a Pydantic model (not a dataclass), so use model_fields.
    field_names = set(ProvenanceEntry.model_fields.keys())
    assert "evidence_bundle_hash" in field_names, (
        "ProvenanceEntry must have an evidence_bundle_hash field"
    )
    assert "corpus_snapshot_id" in field_names, (
        "ProvenanceEntry must have a corpus_snapshot_id field"
    )


# ---------------------------------------------------------------------------
# Gate 4: SynthesisRequest.evidence field is correctly set
# ---------------------------------------------------------------------------


def test_phase3_synthesis_request_carries_evidence() -> None:
    """Gate 4: SynthesisRequest.evidence field threads evidence into the pipeline."""
    target = SynthesisTarget(
        kind="tactic",
        slug="how-we-apply-directive-010",
        title="How we apply Directive 010",
        artifact_id="how-we-apply-directive-010",
        source_section="testing_philosophy",
        source_urns=("urn:drg:directive:DIRECTIVE_010",),
    )
    evidence = _make_evidence()
    req = SynthesisRequest(
        target=target,
        interview_snapshot={},
        doctrine_snapshot={},
        drg_snapshot={},
        run_id="test",
        evidence=evidence,
    )

    assert req.evidence is not None, "SynthesisRequest.evidence must be set"
    assert req.evidence.code_signals is not None
    assert req.evidence.code_signals.stack_id == "python+django+pytest"
    assert req.evidence.url_list == (
        "https://docs.djangoproject.com/",
        "https://docs.pytest.org/",
    )
    assert req.evidence.corpus_snapshot is not None
    assert req.evidence.corpus_snapshot.snapshot_id == "python-v1.0.0"


# ---------------------------------------------------------------------------
# Gate 5: Neutrality gate _is_generic_scoped logic is correct
# ---------------------------------------------------------------------------


def test_phase3_is_generic_scoped_logic() -> None:
    """Gate 5: _is_generic_scoped returns correct results for all scope combinations."""
    from charter.activation.synthesizer.write_pipeline import _is_generic_scoped

    # No evidence → all artifacts are generic-scoped
    assert _is_generic_scoped("tactic", "testing-philosophy", None) is True

    # Evidence with no code_signals → all generic
    empty_bundle = EvidenceBundle()
    assert _is_generic_scoped("tactic", "testing-philosophy", empty_bundle) is True

    # Python scope_tag → python-scoped slug is NOT generic
    cs = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="",
    )
    bundle = EvidenceBundle(code_signals=cs)
    assert _is_generic_scoped("tactic", "python-style-guide", bundle) is False, (
        "slug containing scope_tag must be language-scoped, not generic"
    )
    assert _is_generic_scoped("tactic", "testing-philosophy", bundle) is True, (
        "slug not containing scope_tag must be generic-scoped"
    )


# ---------------------------------------------------------------------------
# Gate 6: NeutralityGateViolation has correct structured fields
# ---------------------------------------------------------------------------


def test_phase3_neutrality_violation_structure() -> None:
    """Gate 6: NeutralityGateViolation is a dataclass with artifact_urn, detected_terms, staging_dir."""
    from charter.activation.synthesizer.errors import NeutralityGateViolation

    field_names = {f.name for f in dataclasses.fields(NeutralityGateViolation)}
    assert "artifact_urn" in field_names, (
        "NeutralityGateViolation must have artifact_urn"
    )
    assert "detected_terms" in field_names, (
        "NeutralityGateViolation must have detected_terms"
    )
    assert "staging_dir" in field_names, (
        "NeutralityGateViolation must have staging_dir"
    )


# ---------------------------------------------------------------------------
# Gate 7: CorpusLoader returns CorpusSnapshot for Python profile
# ---------------------------------------------------------------------------


def test_phase3_corpus_loader_returns_snapshot() -> None:
    """Gate 7: CorpusLoader.load() returns a valid CorpusSnapshot for Python."""
    from charter.activation.evidence.corpus_loader import CorpusLoader

    snap = CorpusLoader().load("python+django+pytest")

    assert snap is not None, "CorpusLoader must return a snapshot for 'python+django+pytest'"
    assert snap.profile_key == "python", (
        f"Expected profile_key='python', got {snap.profile_key!r}"
    )
    assert snap.snapshot_id, "snapshot_id must be non-empty (used for provenance)"
    # Verify the snapshot_id matches the expected format
    assert snap.snapshot_id == "python-v1.0.0", (
        f"Expected snapshot_id='python-v1.0.0', got {snap.snapshot_id!r}"
    )
    assert len(snap.entries) > 0, "Python corpus must have at least one entry"


# ---------------------------------------------------------------------------
# Gate 8: CodeReadingCollector detects Python project from filesystem signals
# ---------------------------------------------------------------------------


def test_phase3_code_reader_detects_python(tmp_path: Path) -> None:
    """Gate 8: CodeReadingCollector identifies primary_language='python' for a Python project."""
    from charter.activation.evidence.code_reader import CodeReadingCollector

    # Create minimal Python project structure
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\nversion = '0.1.0'\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main module\n")
    (tmp_path / "conftest.py").write_text("# pytest conftest\n")

    collector = CodeReadingCollector(tmp_path)
    signals = collector.collect()

    assert signals.primary_language == "python", (
        f"Expected primary_language='python', got {signals.primary_language!r}"
    )
    assert signals.scope_tag == "python", (
        "scope_tag must equal primary_language for neutrality gate correctness"
    )
    assert "pytest" in signals.test_frameworks, (
        "conftest.py should be detected as a pytest indicator"
    )


# ---------------------------------------------------------------------------
# Gate 9: CLI --dry-run-evidence exits 0 and prints evidence summary
# ---------------------------------------------------------------------------


def test_phase3_dry_run_evidence_smoke(tmp_path: Path) -> None:
    """Gate 9: charter synthesize --adapter fixture --dry-run-evidence exits 0.

    The subprocess starts in a seeded **test tmp project** (a normal git
    repository, made so by this directory's autouse ``_git_init_tmp_path``),
    not in the checkout pytest was started from. The charter write guard probes
    the subprocess's working directory and refuses a linked worktree, so a
    subprocess started in the invoking checkout fails from a Spec Kitty lane
    worktree (#5317). ``PYTHONPATH`` still points at the invoking checkout's
    ``src/`` so the subprocess runs the sources under test.
    """
    import os

    repo_root = Path(__file__).parent.parent.parent
    src_path = str(repo_root / "src")

    # Seed a minimal Python project so the code-reading collector has signals.
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'\nversion = '0.1.0'\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main module\n")
    (tmp_path / "conftest.py").write_text("# pytest conftest\n")

    # The `synthesize` subcommand lives in the worktree source, not the installed
    # package. We must prepend the worktree src/ to PYTHONPATH so that
    # `python -m specify_cli` picks up the development version of charter.py.
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}:{existing_pythonpath}" if existing_pythonpath else src_path

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specify_cli",
            "charter",
            "synthesize",
            "--adapter",
            "fixture",
            "--dry-run-evidence",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )

    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "Evidence dry-run summary" in result.stdout, (
        f"Expected 'Evidence dry-run summary' in stdout; got:\n{result.stdout}"
    )
    # The seeded tmp project is a Python project — code signals should detect Python
    assert "Code signals:" in result.stdout, (
        f"Expected 'Code signals:' in stdout; got:\n{result.stdout}"
    )
    # "Code signals:" is also printed for the "none (skipped or not detected)" case, so pin real detection.
    assert "lang=python" in result.stdout, (
        f"Expected the seeded Python project to be detected (lang=python); got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Bonus: fixture adapter uses evidence hash for lookup
# ---------------------------------------------------------------------------


def test_phase3_fixture_adapter_evidence_hash() -> None:
    """Evidence changes the hash, and the fixture adapter resolves the enriched-evidence fixture."""
    from charter.activation.synthesizer.fixture_adapter import FixtureAdapter, FixtureAdapterMissingError
    from charter.activation.synthesizer.request import compute_inputs_hash, short_hash

    target = SynthesisTarget(
        kind="tactic",
        slug="how-we-apply-directive-010",
        title="How we apply Directive 010",
        artifact_id="how-we-apply-directive-010",
        source_section="testing_philosophy",
        source_urns=("urn:drg:directive:DIRECTIVE_010",),
    )
    interview = {"testing_philosophy": "We test at multiple levels."}

    req_empty = SynthesisRequest(
        target=target,
        interview_snapshot=interview,
        doctrine_snapshot={},
        drg_snapshot={},
        run_id="test",
    )
    req_enriched = SynthesisRequest(
        target=target,
        interview_snapshot=interview,
        doctrine_snapshot={},
        drg_snapshot={},
        run_id="test",
        evidence=_make_evidence(),
    )

    hash_empty = compute_inputs_hash(req_empty, "fixture", "1.0.0")
    hash_enriched = compute_inputs_hash(req_enriched, "fixture", "1.0.0")

    # Different hashes confirm evidence is included in the hash
    assert hash_empty != hash_enriched, (
        "Evidence must change the inputs_hash for fixture lookup"
    )
    assert short_hash(hash_empty) != short_hash(hash_enriched)

    # Fixture adapter must successfully load the enriched-evidence fixture
    # (the fixture was created at b606c08cd95c.tactic.yaml for this exact hash)
    adapter = FixtureAdapter()
    output = adapter.generate(req_enriched)
    assert output is not None
    assert output.body, "Enriched fixture body must be non-empty"
