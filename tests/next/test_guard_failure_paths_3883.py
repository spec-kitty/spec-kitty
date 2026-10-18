"""#3883: a blocked decision names where each failing guard looked.

The reported dead end was not only that the advance path disagreed with the
query path — it was that ``blocked — guard_failures: ["qa-traceability.yaml",
"test-report.md"]`` gave an operator nothing to act on. Everything inspectable
said the artifacts were present; the one command that advances said they were
missing; and nothing in the output said which directory it had read. Telling
the two apart required reading ``runtime/next/runtime_bridge.py``.

So the reporter's second remedy stands on its own, independently of the root
cause: name the specific file **and the specific path it looked at**. These
tests pin that, plus the two properties that keep the diagnostics honest — the
path comes from the same placement seam the guard itself reads through, and
producing it can never change the decision.

**#4390 amendment.** The original version of this file fed
``guard_failures=["spec.md", "tasks.md"]`` — bare filenames — straight into a
``mission="software-dev"`` decision. That data shape never occurs for a
registered mission family: every entry in
``runtime_bridge_cores._GUARD_TABLES`` (software-dev/research/documentation/
plan) reports a genuine missing-artifact failure as the human-readable
message ``"Required artifact missing: {name}"``
(``runtime_bridge_cores.MISSING_ARTIFACT_MESSAGE``), not a bare filename —
and mixes it with free-form NON-artifact failures (WP status, source counts,
dependency fields, ...) that name no real artifact at all. Bare filenames are
the shape ``evaluate_guards_strict``'s fail-closed branch returns for an
*unregistered custom* mission family (no ``_GUARD_TABLES`` entry) — a
genuinely different code path, covered separately below by
``TestUnregisteredCustomFamilyBareTags``.

Feeding the registered-family shape bare filenames made every one of these
tests pass against the #4390 bug: ``artifact_search_paths(...,
names=guard_failures)`` treated each bare string as a literal filename either
way, so the test could not tell "resolved a real tag" apart from "echoed
whatever string it was given". The tests below use each shape as it actually
occurs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.missions import MissionTemplateRepository
from runtime.next.decision import Decision, _with_guard_failure_paths
from runtime.next.runtime_bridge_io import artifact_search_paths, guard_failure_artifact_paths

pytestmark = [pytest.mark.unit]


def _blocked(**overrides: object) -> Decision:
    payload: dict[str, object] = {
        "kind": "blocked",
        "agent": "claude",
        "mission_slug": "qa-run-01M1ZZZZ",
        "mission": "software-dev",
        "mission_state": "review",
        "timestamp": "2026-09-14T00:00:00Z",
        "guard_failures": [
            "Required artifact missing: spec.md",
            "Required artifact missing: tasks.md",
        ],
    }
    payload.update(overrides)
    return Decision(**payload)  # type: ignore[arg-type]


def test_blocked_decision_reports_the_path_each_guard_read(tmp_path: Path) -> None:
    decision = _with_guard_failure_paths(_blocked(), tmp_path)

    assert decision.guard_failure_paths == {
        "spec.md": "kitty-specs/qa-run-01M1ZZZZ/spec.md",
        "tasks.md": "kitty-specs/qa-run-01M1ZZZZ/tasks.md",
    }
    # Repo-relative, so the operator can paste it straight into `ls`.
    assert not any(p.startswith("/") for p in decision.guard_failure_paths.values())


def test_the_reported_path_comes_from_the_seam_the_guard_reads(tmp_path: Path) -> None:
    """Not a second reconstruction: one seam, or the report drifts from reality.

    ``artifact_search_paths`` resolves the same ``_ArtifactPresenceHomes`` that
    ``gather_artifact_presence`` uses for its own presence reads.
    """
    feature_dir = tmp_path / "kitty-specs" / "qa-run-01M1ZZZZ"
    direct = artifact_search_paths(
        feature_dir,
        mission_family="software-dev",
        repo_root=tmp_path,
        names=["spec.md", "tasks.md"],
    )

    assert _with_guard_failure_paths(_blocked(), tmp_path).guard_failure_paths == direct


def test_a_non_artifact_guard_failure_grows_no_fabricated_path(tmp_path: Path) -> None:
    """#4390 — the actual reported MAJOR: a genuine missing-artifact failure
    ("Required artifact missing: spec.md") sits next to a free-form,
    non-artifact WP-status failure ("Not all work packages are approved or
    done") in the SAME decision, exactly as ``_evaluate_wp_iteration_guard``
    produces for a real ``review`` block. Only the first may resolve to a
    path — keyed by the real ``spec.md`` tag, never by the WP-status message
    itself, and no entry at all is fabricated for the WP-status failure.
    """
    decision = _with_guard_failure_paths(
        _blocked(
            guard_failures=[
                "Required artifact missing: spec.md",
                "Not all work packages are approved or done",
            ]
        ),
        tmp_path,
    )

    assert decision.guard_failure_paths == {
        "spec.md": "kitty-specs/qa-run-01M1ZZZZ/spec.md",
    }
    assert "Not all work packages are approved or done" not in decision.guard_failure_paths


def test_paths_are_serialized_for_json_consumers(tmp_path: Path) -> None:
    payload = _with_guard_failure_paths(_blocked(), tmp_path).to_dict()

    assert payload["guard_failure_paths"]["spec.md"].endswith("spec.md")
    # The identity strings the SC-007 query/advance parity invariant compares
    # are untouched — the paths ride alongside them, never inside them.
    assert payload["guard_failures"] == [
        "Required artifact missing: spec.md",
        "Required artifact missing: tasks.md",
    ]


def test_a_decision_with_no_guard_failures_is_untouched(tmp_path: Path) -> None:
    """Nothing failed, so there is nothing to locate — and no seam read at all."""
    decision = _with_guard_failure_paths(_blocked(guard_failures=[]), tmp_path)

    assert decision.guard_failure_paths == {}


def test_reporting_never_changes_the_decision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Diagnostics are best-effort by construction: if the path lookup raises,
    the operator still gets the runtime's own verdict, unmodified."""
    import runtime.next.runtime_bridge_io as io_seam

    def _boom(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise RuntimeError("placement seam unavailable")

    monkeypatch.setattr(io_seam, "artifact_search_paths", _boom)

    decision = _with_guard_failure_paths(_blocked(), tmp_path)

    assert decision.kind == "blocked"
    assert decision.guard_failures == [
        "Required artifact missing: spec.md",
        "Required artifact missing: tasks.md",
    ]
    assert decision.guard_failure_paths == {}


# ---------------------------------------------------------------------------
# The #3883-reported shape: an UNREGISTERED custom mission family (no
# ``_GUARD_TABLES`` entry). ``evaluate_guards_strict``'s fail-closed branch
# (``sorted(missing)``) reports bare artifact filenames directly — a
# genuinely different data shape from every registered family's messages
# above, and the scenario the original bug report was about.
# ---------------------------------------------------------------------------

_CUSTOM_MISSION_TYPE = "custom-family"
_CUSTOM_STEP_ID = "custom-step"
_CUSTOM_FILENAME = "custom-artifact.md"

_CUSTOM_EXPECTED_ARTIFACTS_YAML = f"""\
schema_version: "1.0"
mission_type: "{_CUSTOM_MISSION_TYPE}"
manifest_version: "1"
required_always: []
required_by_step:
  {_CUSTOM_STEP_ID}:
    - artifact_key: "output.custom.main"
      artifact_class: "output"
      path_pattern: "{_CUSTOM_FILENAME}"
      blocking: true
optional_always: []
"""


@pytest.fixture
def custom_mission_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ``MissionTemplateRepository.default()`` at a temp missions root
    shipping a custom mission type's own ``expected-artifacts.yaml`` — the
    data-driven custom-family gate mechanism (no ``_GUARD_TABLES`` code
    registration), matching ``tests/runtime/next/test_pertype_presence_gate.py``.
    """
    missions_root = tmp_path / "missions-root"
    custom_dir = missions_root / _CUSTOM_MISSION_TYPE
    custom_dir.mkdir(parents=True)
    (custom_dir / "expected-artifacts.yaml").write_text(_CUSTOM_EXPECTED_ARTIFACTS_YAML, encoding="utf-8")

    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


class TestUnregisteredCustomFamilyBareTags:
    """#3883's own reported scenario: bare tags, not messages."""

    def test_bare_tag_resolves_to_the_real_path(self, tmp_path: Path, custom_mission_repo: None) -> None:
        decision = _with_guard_failure_paths(
            _blocked(mission="custom-family", mission_state=_CUSTOM_STEP_ID, guard_failures=[_CUSTOM_FILENAME]),
            tmp_path,
        )

        assert decision.guard_failure_paths == {
            _CUSTOM_FILENAME: f"kitty-specs/qa-run-01M1ZZZZ/{_CUSTOM_FILENAME}",
        }

    def test_guard_failure_artifact_paths_resolves_the_same_bare_tag_directly(self, tmp_path: Path, custom_mission_repo: None) -> None:
        feature_dir = tmp_path / "kitty-specs" / "qa-run-01M1ZZZZ"

        resolved = guard_failure_artifact_paths(
            feature_dir,
            mission_family="custom-family",
            repo_root=tmp_path,
            guard_failures=[_CUSTOM_FILENAME],
        )

        assert resolved == {_CUSTOM_FILENAME: f"kitty-specs/qa-run-01M1ZZZZ/{_CUSTOM_FILENAME}"}


# ---------------------------------------------------------------------------
# #6388 -- a genuine plan-family miss at ``specify`` must name its path.
# Pre-fix the plan manifest was keyed ``goals``, so no artifact was required at
# ``specify`` and ``guard_failure_paths`` came back empty for a real block.
# ---------------------------------------------------------------------------


def test_plan_specify_miss_reports_the_spec_md_path(tmp_path: Path) -> None:
    from specify_cli.runtime.resolver import required_artifacts_for  # noqa: PLC0415

    feature_dir = tmp_path / "kitty-specs" / "plan-run-01M1ZZZZ"
    feature_dir.mkdir(parents=True)

    assert required_artifacts_for("specify", "plan") == ["spec.md"]
    assert required_artifacts_for("plan", "plan") == ["plan.md"]

    paths = guard_failure_artifact_paths(
        feature_dir,
        mission_family="plan",
        repo_root=tmp_path,
        guard_failures=["Required artifact missing: spec.md"],
    )

    assert set(paths) == {"spec.md"}
    assert paths["spec.md"].endswith("spec.md")
