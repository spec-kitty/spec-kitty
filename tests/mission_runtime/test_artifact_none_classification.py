"""Classifier taxonomy for formerly-unclassified PRIMARY mission files (#5697, WP01)."""

from __future__ import annotations

import pytest

from mission_runtime.artifacts import (
    MissionArtifactKind as K,
    assert_partition_invariant,
    is_primary_artifact_kind,
    kind_for_mission_file,
    mission_file_basenames_for_kind,
)

SLUG = "m"
_RESEARCH_OUTPUTS = frozenset({"findings.md", "report.md", "methodology.md", "synthesis.md", "literature-review.md"})

_NEWLY_CLASSIFIED = [
    ("research/notes.md", K.RESEARCH),
    ("research/deep/nested/data.csv", K.RESEARCH),
    ("research/x.py", K.RESEARCH),
    ("findings.md", K.RESEARCH_OUTPUT),
    ("report.md", K.RESEARCH_OUTPUT),
    ("methodology.md", K.RESEARCH_OUTPUT),
    ("synthesis.md", K.RESEARCH_OUTPUT),
    ("literature-review.md", K.RESEARCH_OUTPUT),
    ("gap-analysis.md", K.ANALYSIS_REPORT),
    ("audit-report.md", K.ANALYSIS_REPORT),
    ("occurrence_map.yaml", K.OCCURRENCE_MAP),
    ("goals.md", K.MISSION_GOALS),
    ("release.md", K.RELEASE_RECORD),
    ("meta.json", K.PRIMARY_METADATA),
]

_EXCLUDED = ["lint-report.json", "docs/x.md", "answers.yaml", "mission-events.jsonl"]


def _classify(rel: str) -> K | None:
    return kind_for_mission_file(f"kitty-specs/{SLUG}/{rel}", mission_slug=SLUG)


@pytest.mark.parametrize(("rel", "expected"), _NEWLY_CLASSIFIED)
def test_newly_classified_path_is_primary(rel: str, expected: K) -> None:
    kind = _classify(rel)
    assert kind is expected
    assert is_primary_artifact_kind(kind)


@pytest.mark.parametrize("rel", _EXCLUDED)
def test_excluded_paths_stay_unclassified(rel: str) -> None:
    # Paired with a positive control so the None assertion is non-vacuous.
    assert _classify("goals.md") is K.MISSION_GOALS
    assert _classify(rel) is None


def test_wrong_mission_slug_is_unclassified() -> None:
    assert kind_for_mission_file(f"kitty-specs/{SLUG}/goals.md", mission_slug="other") is None


def test_partition_invariant_holds() -> None:
    assert_partition_invariant()


def test_inverse_map_is_honest() -> None:
    assert mission_file_basenames_for_kind(K.RESEARCH_OUTPUT) == _RESEARCH_OUTPUTS
    assert {"analysis-report.md", "gap-analysis.md", "audit-report.md"} <= mission_file_basenames_for_kind(K.ANALYSIS_REPORT)
    assert mission_file_basenames_for_kind(K.OCCURRENCE_MAP) == {"occurrence_map.yaml"}
    assert mission_file_basenames_for_kind(K.MISSION_GOALS) == {"goals.md"}
    assert mission_file_basenames_for_kind(K.RELEASE_RECORD) == {"release.md"}
    assert "meta.json" in mission_file_basenames_for_kind(K.PRIMARY_METADATA)
