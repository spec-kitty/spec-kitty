"""Tests for FixtureAdapter behaviour (KD-4, R-0-6, T008).

Verifies:
1. Missing fixture raises FixtureAdapterMissingError with correct expected_path.
2. Identical normalized inputs produce identical hashes (key-order permutation invariance).
3. Present fixture returns AdapterOutput with adapter_id == "fixture".
4. Different adapter versions produce different hashes (R-0-6 rule 5).
5. run_id excluded from hash (R-0-6 rule 4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.synthesizer.errors import FixtureAdapterMissingError
from charter.activation.synthesizer.fixture_adapter import FixtureAdapter
from charter.activation.synthesizer.request import (
    SynthesisRequest,
    SynthesisTarget,
    compute_inputs_hash,
    short_hash,
)
from kernel.clock import UTC, datetime, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

def _make_request(
    *,
    run_id: str = "01AAAAAAAAAAAAAAAAAAAAAAAAA",
    adapter_hints: dict | None = None,
    extra_interview: dict | None = None,
) -> SynthesisRequest:
    """Build a minimal SynthesisRequest for fixture adapter tests."""
    interview = {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "tdd",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }
    if extra_interview:
        interview.update(extra_interview)

    target = SynthesisTarget(
        kind="directive",
        slug="project-decision-doc-directive",
        title="Project Decision Documentation Directive",
        artifact_id="PROJECT_001",
        source_section="testing_philosophy",
        source_urns=("directive:DIRECTIVE_003",),
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=interview,
        doctrine_snapshot={
            "directives": {
                "DIRECTIVE_003": {
                    "id": "DIRECTIVE_003",
                    "title": "Decision Documentation",
                    "body": "Document decisions via ADRs.",
                }
            },
            "tactics": {},
            "styleguides": {},
        },
        drg_snapshot={
            "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
            "edges": [],
            "schema_version": "1",
        },
        run_id=run_id,
        adapter_hints=adapter_hints,
    )


# ---------------------------------------------------------------------------
# 1. Missing fixture raises FixtureAdapterMissingError
# ---------------------------------------------------------------------------


class TestMissingFixture:
    def test_missing_fixture_raises_with_correct_expected_path(
        self, tmp_path: Path
    ) -> None:
        """FixtureAdapterMissingError contains the expected fixture path."""
        adapter = FixtureAdapter(fixture_root=tmp_path)
        req = _make_request()
        full_hash = compute_inputs_hash(req, "fixture", "1.0.0")
        sh = short_hash(full_hash, 12)
        expected = tmp_path / "directive" / "project-decision-doc-directive" / f"{sh}.directive.yaml"

        with pytest.raises(FixtureAdapterMissingError) as exc_info:
            adapter.generate(req)

        err = exc_info.value
        assert err.expected_path == str(expected)
        assert err.kind == "directive"
        assert err.slug == "project-decision-doc-directive"
        assert err.inputs_hash == full_hash

    def test_missing_fixture_error_message_contains_hash(self, tmp_path: Path) -> None:
        """Error message includes the short hash for operator diagnosis."""
        adapter = FixtureAdapter(fixture_root=tmp_path)
        req = _make_request()
        full_hash = compute_inputs_hash(req, "fixture", "1.0.0")

        with pytest.raises(FixtureAdapterMissingError) as exc_info:
            adapter.generate(req)

        assert full_hash[:12] in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Key-order permutation invariance
# ---------------------------------------------------------------------------


class TestNormalizationInvariance:
    def test_identical_inputs_produce_identical_hashes(self) -> None:
        """Two requests with identical semantic content hash identically."""
        req_a = _make_request(run_id="run-aaa")
        req_b = _make_request(run_id="run-bbb")  # different run_id, same semantic content
        assert compute_inputs_hash(req_a, "fixture", "1.0.0") == compute_inputs_hash(
            req_b, "fixture", "1.0.0"
        )

    def test_key_order_permutation_does_not_change_hash(self) -> None:
        """Different dict key orderings produce the same hash (sorted-key normalization)."""
        # Python 3.7+ dicts preserve insertion order, so create two dicts with
        # different insertion orders but identical key-value pairs.
        interview_a = {
            "mission_type": "software_dev",
            "language_scope": ["python"],
            "testing_philosophy": "tdd",
            "neutrality_posture": "balanced",
            "selected_directives": ["DIRECTIVE_003"],
            "risk_appetite": "moderate",
        }
        interview_b = {
            "risk_appetite": "moderate",
            "selected_directives": ["DIRECTIVE_003"],
            "neutrality_posture": "balanced",
            "testing_philosophy": "tdd",
            "language_scope": ["python"],
            "mission_type": "software_dev",
        }

        target = SynthesisTarget(
            kind="directive",
            slug="project-decision-doc-directive",
            title="Project Decision Documentation Directive",
            artifact_id="PROJECT_001",
            source_section="testing_philosophy",
            source_urns=("directive:DIRECTIVE_003",),
        )
        doctrine = {
            "directives": {"DIRECTIVE_003": {"id": "DIRECTIVE_003", "title": "D", "body": "B"}},
            "tactics": {},
            "styleguides": {},
        }
        drg = {
            "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
            "edges": [],
            "schema_version": "1",
        }

        req_a = SynthesisRequest(
            target=target, interview_snapshot=interview_a,
            doctrine_snapshot=doctrine, drg_snapshot=drg, run_id="r1",
        )
        req_b = SynthesisRequest(
            target=target, interview_snapshot=interview_b,
            doctrine_snapshot=doctrine, drg_snapshot=drg, run_id="r2",
        )

        assert compute_inputs_hash(req_a, "fixture", "1.0.0") == compute_inputs_hash(
            req_b, "fixture", "1.0.0"
        )

    def test_run_id_excluded_from_hash(self) -> None:
        """Changing run_id does not change the fixture hash (R-0-6 rule 4)."""
        req_a = _make_request(run_id="01AAAAAAAAAAAAAAAAAAAAAAAAA")
        req_b = _make_request(run_id="01BBBBBBBBBBBBBBBBBBBBBBBBB")
        assert compute_inputs_hash(req_a, "fixture", "1.0.0") == compute_inputs_hash(
            req_b, "fixture", "1.0.0"
        )

    def test_adapter_version_changes_hash(self) -> None:
        """Different adapter versions produce different hashes (R-0-6 rule 5)."""
        req = _make_request()
        hash_v1 = compute_inputs_hash(req, "fixture", "1.0.0")
        hash_v2 = compute_inputs_hash(req, "fixture", "2.0.0")
        assert hash_v1 != hash_v2

    def test_adapter_id_changes_hash(self) -> None:
        """Different adapter ids produce different hashes."""
        req = _make_request()
        hash_fixture = compute_inputs_hash(req, "fixture", "1.0.0")
        hash_production = compute_inputs_hash(req, "claude-3-7-sonnet", "1.0.0")
        assert hash_fixture != hash_production

    def test_content_change_changes_hash(self) -> None:
        """A semantic change in interview answers produces a different hash."""
        req_a = _make_request(extra_interview={"testing_philosophy": "tdd"})
        req_b = _make_request(extra_interview={"testing_philosophy": "bdd"})
        assert compute_inputs_hash(req_a, "fixture", "1.0.0") != compute_inputs_hash(
            req_b, "fixture", "1.0.0"
        )


# ---------------------------------------------------------------------------
# 3. Present fixture returns AdapterOutput with adapter_id == "fixture"
# ---------------------------------------------------------------------------


#: The mapping every hermetic fixture below is recorded with.
_RECORDED_BODY = {
    "id": "PROJECT_001",
    "title": "Project Decision Documentation Directive",
    "scope": "Record every architectural decision as an ADR.",
}

#: The adapter's documented deterministic epoch (``fixture_adapter`` module).
_FIXTURE_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def _record_fixture(fixture_root: Path, request: SynthesisRequest) -> str:
    """Write ``_RECORDED_BODY`` where FixtureAdapter looks for ``request``.

    The path is derived through the public hashing API, so the test never
    depends on a pre-recorded file whose hash can drift. Returns the full
    inputs hash.
    """
    full_hash = compute_inputs_hash(request, "fixture", "1.0.0")
    path = (
        fixture_root
        / "directive"
        / "project-decision-doc-directive"
        / f"{short_hash(full_hash, 12)}.directive.yaml"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        "".join(f"{key}: {value}\n" for key, value in _RECORDED_BODY.items()),
        encoding="utf-8",
    )
    return full_hash


class TestPresentFixture:
    """A recorded fixture is served back verbatim with fixture provenance.

    Hermetic: each test records its own fixture in ``tmp_path`` (at the path
    derived from the request's public hash) and never skips, so a lookup or
    path regression fails instead of skipping. Hash stability itself is pinned
    by the golden hashes in ``test_request.py``.
    """

    def test_present_fixture_returns_adapter_output(self, tmp_path: Path) -> None:
        req = _make_request()
        full_hash = _record_fixture(tmp_path, req)

        output = FixtureAdapter(fixture_root=tmp_path).generate(req)

        assert output.body == _RECORDED_BODY
        assert output.adapter_id_override is None
        assert output.adapter_version_override is None
        assert output.notes == f"fixture:{full_hash[:12]}"

    def test_fixture_generated_at_is_deterministic_and_hash_seeded(
        self, tmp_path: Path
    ) -> None:
        req = _make_request()
        other = _make_request(extra_interview={"testing_philosophy": "bdd"})
        full_hash = _record_fixture(tmp_path, req)
        other_hash = _record_fixture(tmp_path / "other", other)
        adapter = FixtureAdapter(fixture_root=tmp_path)

        out_a = adapter.generate(req)
        out_b = adapter.generate(req)
        out_other = FixtureAdapter(fixture_root=tmp_path / "other").generate(other)

        assert out_a.generated_at == out_b.generated_at
        assert out_a.generated_at == _FIXTURE_EPOCH + timedelta(
            microseconds=int(full_hash[:8], 16)
        )
        assert out_other.generated_at == _FIXTURE_EPOCH + timedelta(
            microseconds=int(other_hash[:8], 16)
        )
        assert out_a.generated_at != out_other.generated_at
