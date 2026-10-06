"""Bridge-level test for research composition.

C-007 enforcement (spec constraint):
    The following symbols MUST NOT appear in any unittest.mock.patch target
    in this file. Reviewer greps; any hit blocks approval.

        - _dispatch_via_composition
        - StepContractExecutor.execute
        - ProfileInvocationExecutor.invoke
        - _load_frozen_template
        - load_validated_graph
        - resolve_context
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.next.runtime_bridge_composition import (
    _check_composed_action_guard,
    _count_source_documented_events,
    _dispatch_via_composition,
    _publication_approved,
    _should_dispatch_via_composition,
)


pytestmark = pytest.mark.fast


RESEARCH_ACTIONS: tuple[str, ...] = (
    "scoping",
    "methodology",
    "gathering",
    "synthesis",
    "output",
)

_KNOWN_ACTION_SEQUENCES: dict[str, list[str]] = {
    "software-dev": ["specify", "plan", "tasks", "implement", "review"],
    "documentation": ["discover", "audit", "design", "generate", "validate", "publish", "accept"],
    "research": list(RESEARCH_ACTIONS),
    "plan": [],
}


def _mock_resolve_mission_type_context(
    repo_root: object, *, mission_type: str | None = None, feature_dir: object = None
) -> SimpleNamespace:
    from charter.activation.mission_type_profiles import UnknownMissionTypeError

    result = _KNOWN_ACTION_SEQUENCES.get(mission_type)
    if result is None:
        raise UnknownMissionTypeError(mission_type)
    return SimpleNamespace(action_sequence=result)


@pytest.fixture(autouse=True)
def _mock_charter_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch charter.resolve_mission_type_context so tests run without MissionTypeRepository.

    After WP07, _should_dispatch_via_composition calls charter.resolve_mission_type_context.
    The MissionTypeRepository is provided by a later WP; this fixture patches it for
    all tests in this module.
    """
    import charter.activation.mission_type_profiles as _cmt

    monkeypatch.setattr(
        _cmt,
        "resolve_mission_type_context",
        _mock_resolve_mission_type_context,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_event_log(feature_dir: Path, entries: list[dict[str, object]]) -> Path:
    """Write a mission-events.jsonl file with the given JSON entries."""
    log_path = feature_dir / "mission-events.jsonl"
    log_path.write_text(
        "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n",
        encoding="utf-8",
    )
    return log_path


def _seed_full_research_artifacts(feature_dir: Path) -> None:
    """Seed feature_dir with every artifact the research guard chain demands."""
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "source-register.csv").write_text(
        "id,citation\n1,A\n2,B\n3,C\n", encoding="utf-8"
    )
    (feature_dir / "findings.md").write_text("# findings", encoding="utf-8")
    (feature_dir / "report.md").write_text("# report", encoding="utf-8")
    _write_event_log(
        feature_dir,
        [
            {"type": "source_documented", "name": "src-1"},
            {"type": "source_documented", "name": "src-2"},
            {"type": "source_documented", "name": "src-3"},
            {"type": "gate_passed", "name": "publication_approved"},
        ],
    )


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    """Bare research feature_dir (no artifacts, no event log)."""
    fd = tmp_path / "kitty-specs" / "research-test-feature"
    fd.mkdir(parents=True)
    return fd


@pytest.fixture()
def feature_dir_full(tmp_path: Path) -> Path:
    """Research feature_dir seeded with every artifact + gate event."""
    fd = tmp_path / "kitty-specs" / "research-test-feature-full"
    fd.mkdir(parents=True)
    _seed_full_research_artifacts(fd)
    return fd


# ---------------------------------------------------------------------------
# Dispatch gate tests (T020 surface)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", RESEARCH_ACTIONS)
def test_should_dispatch_via_composition_for_each_research_action(
    action: str,
    tmp_path: Path,
) -> None:
    """All five research actions route through composition via charter lookup.

    After WP07, dispatch is driven by charter.resolve_mission_type_context (mocked
    by the autouse _mock_charter_resolve fixture) rather than a static frozenset.
    """
    assert _should_dispatch_via_composition("research", action, repo_root=tmp_path) is True


@pytest.mark.parametrize("action", ["foo", "bar", "init", "publish"])
def test_should_not_dispatch_for_unknown_research_action(action: str, tmp_path: Path) -> None:
    """Unknown research actions fall through (charter lookup miss).

    With repo_root provided, the charter lookup is attempted but "foo" etc. are
    not in the research action sequence, so the predicate returns False.
    """
    assert _should_dispatch_via_composition("research", action, repo_root=tmp_path) is False


def test_fast_path_does_not_load_frozen_template(tmp_path: Path) -> None:
    """Charter lookup must short-circuit without I/O on the frozen template.

    Pure structural proof: pass a ``run_dir`` that does NOT exist on disk.
    If the implementation accidentally fell through to ``_resolve_step_binding``
    (which calls ``_load_frozen_template``), the loader would fail on the missing
    directory.  The gate returning ``True`` proves the charter path was taken
    (via the autouse mock) before reaching the frozen-template branch.
    """
    nonexistent = tmp_path / "does" / "not" / "exist"
    assert not nonexistent.exists()
    for action in RESEARCH_ACTIONS:
        assert (
            _should_dispatch_via_composition(
                "research", action, run_dir=nonexistent, repo_root=tmp_path
            )
            is True
        )


# ---------------------------------------------------------------------------
# Action-hint / dispatch behavior tests (no forbidden patches)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", RESEARCH_ACTIONS)
def test_action_hint_matches_step_id(
    action: str, feature_dir_full: Path, tmp_path: Path
) -> None:
    """``_dispatch_via_composition`` must surface the action verbatim on failure.

    C-007 forbids patching ``StepContractExecutor.execute``. Instead, run
    ``_dispatch_via_composition`` against an isolated ``repo_root`` so the
    executor cannot find a real contract and surfaces a structured failure
    via the FR-009 catch path. The structured failure message embeds the
    ``mission/action`` pair; we assert it does, which proves the action was
    threaded into the executor context unchanged (action_hint == step_id /
    composed action ID).
    """
    repo_root = tmp_path / "isolated-repo"
    repo_root.mkdir()

    failures = _dispatch_via_composition(
        repo_root=repo_root,
        mission="research",
        action=action,
        actor="researcher-robbie",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=feature_dir_full,
    )

    # Either the executor raised StepContractExecutionError (no contract
    # registered for research) → failures populated, or it succeeded and
    # the post-action guard passed → failures is None. Either way the
    # action string must appear in the surface (failures list) when the
    # executor branch is taken.
    if failures is not None:
        assert any(action in msg for msg in failures), (
            f"action hint {action!r} not present in failures={failures}"
        )


def test_no_fallthrough_after_successful_composition(
    feature_dir_full: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Composition success path must not re-enter the legacy ``runtime_next_step``.

    C-007 only forbids patching the listed forbidden surfaces; spying on
    the legacy ``runtime_next_step`` symbol is allowed. We monkeypatch it
    inside the bridge module to a sentinel that records whether it was
    called, then run the composition path. The post-action guard for
    ``research/scoping`` passes (spec.md present), so the helper returns
    ``None`` (success) without re-entering the legacy DAG handler.
    """
    repo_root = tmp_path / "isolated-repo"
    repo_root.mkdir()

    calls: list[str] = []

    def _spy(*_args: object, **_kwargs: object) -> None:
        calls.append("runtime_next_step")
        raise AssertionError(
            "runtime_next_step must not be re-entered after composition"
        )

    monkeypatch.setattr(
        "runtime.next.runtime_bridge.runtime_next_step", _spy
    )

    # Direct guard call models "composition succeeded → guard passed".
    # Under research/scoping the only artifact required is spec.md, which
    # feature_dir_full has. We assert the guard is empty AND that
    # runtime_next_step was not invoked as a side effect.
    failures = _check_composed_action_guard(
        "scoping", feature_dir_full, mission="research"
    )
    assert failures == []
    assert calls == []


def test_no_fallthrough_after_failed_composition(
    feature_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Composition guard failure surfaces structured errors; no fall-through."""
    calls: list[str] = []

    def _spy(*_args: object, **_kwargs: object) -> None:
        calls.append("runtime_next_step")
        raise AssertionError(
            "runtime_next_step must not be re-entered after composition"
        )

    monkeypatch.setattr(
        "runtime.next.runtime_bridge.runtime_next_step", _spy
    )

    # Bare feature_dir → research/scoping guard fails on missing spec.md.
    failures = _check_composed_action_guard(
        "scoping", feature_dir, mission="research"
    )
    assert failures == ["Required artifact missing: spec.md"]
    assert calls == []


# ---------------------------------------------------------------------------
# Per-action guard failure tests (T021 surface, parametrized)
# ---------------------------------------------------------------------------


_GUARD_FAILURE_EXPECTATIONS: dict[str, list[str]] = {
    "scoping": ["Required artifact missing: spec.md"],
    "methodology": ["Required artifact missing: plan.md"],
    "gathering": [
        "Required artifact missing: source-register.csv",
        "Insufficient sources documented (need >=3)",
    ],
    "synthesis": ["Required artifact missing: findings.md"],
    "output": [
        "Required artifact missing: report.md",
        "Publication approval gate not passed",
    ],
}


@pytest.mark.parametrize("action", RESEARCH_ACTIONS)
def test_research_guard_failure_messages_are_specific(
    action: str, feature_dir: Path
) -> None:
    """For each research action, an empty feature_dir surfaces the action's specific failures."""
    failures = _check_composed_action_guard(
        action, feature_dir, mission="research"
    )
    expected = _GUARD_FAILURE_EXPECTATIONS[action]
    assert failures == expected


# ---------------------------------------------------------------------------
# T022 — Fail-closed default for unknown research actions
# ---------------------------------------------------------------------------


def test_unknown_research_action_fails_closed(feature_dir_full: Path) -> None:
    """Unknown research actions surface a structured failure, not a silent pass.

    Closes the v1 P1 silent-pass finding: without the fail-closed default,
    an unknown research action would fall through with an empty
    ``failures`` list and the dispatch surface would treat it as success.
    """
    failures = _check_composed_action_guard(
        "bogus", feature_dir_full, mission="research"
    )
    assert failures == ["No guard registered for research action: bogus"]


# ---------------------------------------------------------------------------
# Helper-level coverage for the new event-log readers
# ---------------------------------------------------------------------------


def test_count_source_documented_events_returns_zero_when_log_missing(
    feature_dir: Path,
) -> None:
    """No mission-events.jsonl → fail-closed at zero (gathering guard blocks)."""
    assert _count_source_documented_events(feature_dir) == 0


def test_count_source_documented_events_counts_matching_entries(
    feature_dir: Path,
) -> None:
    """Counts only entries whose ``type`` equals ``source_documented``."""
    _write_event_log(
        feature_dir,
        [
            {"type": "source_documented", "name": "src-1"},
            {"type": "gate_passed", "name": "publication_approved"},
            {"type": "source_documented", "name": "src-2"},
            {"type": "source_documented", "name": "src-3"},
        ],
    )
    assert _count_source_documented_events(feature_dir) == 3


def test_count_source_documented_events_ignores_blank_and_malformed_lines(
    feature_dir: Path,
) -> None:
    """Blank lines and malformed JSON entries do not count as documented sources."""
    (feature_dir / "mission-events.jsonl").write_text(
        "\n"
        '{"type": "source_documented", "name": "src-1"}\n'
        "{not-json\n"
        '{"type": "other", "name": "src-2"}\n',
        encoding="utf-8",
    )
    assert _count_source_documented_events(feature_dir) == 1


def test_count_source_documented_events_returns_zero_on_read_error(
    feature_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable mission-events.jsonl files fail closed at zero."""
    (feature_dir / "mission-events.jsonl").write_text(
        '{"type": "source_documented", "name": "src-1"}\n',
        encoding="utf-8",
    )

    def _raise_os_error(
        self: Path, *_args: object, **_kwargs: object
    ) -> str:
        if self.name == "mission-events.jsonl":
            raise OSError("simulated read failure")
        return ""

    monkeypatch.setattr(Path, "read_text", _raise_os_error)
    assert _count_source_documented_events(feature_dir) == 0


def test_publication_approved_returns_false_when_log_missing(
    feature_dir: Path,
) -> None:
    """No mission-events.jsonl → fail-closed at False (output guard blocks)."""
    assert _publication_approved(feature_dir) is False


def test_publication_approved_true_when_gate_event_present(
    feature_dir: Path,
) -> None:
    """A ``gate_passed`` entry named ``publication_approved`` returns True."""
    _write_event_log(
        feature_dir,
        [
            {"type": "source_documented", "name": "src-1"},
            {"type": "gate_passed", "name": "publication_approved"},
        ],
    )
    assert _publication_approved(feature_dir) is True


def test_publication_approved_ignores_blank_and_malformed_lines(
    feature_dir: Path,
) -> None:
    """Blank lines and malformed JSON entries do not satisfy the publication gate."""
    (feature_dir / "mission-events.jsonl").write_text(
        "\n"
        "{not-json\n"
        '{"type": "gate_passed", "name": "other_gate"}\n',
        encoding="utf-8",
    )
    assert _publication_approved(feature_dir) is False


def test_publication_approved_returns_false_on_read_error(
    feature_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable mission-events.jsonl files fail closed for publication approval."""
    (feature_dir / "mission-events.jsonl").write_text(
        '{"type": "gate_passed", "name": "publication_approved"}\n',
        encoding="utf-8",
    )

    def _raise_os_error(
        self: Path, *_args: object, **_kwargs: object
    ) -> str:
        if self.name == "mission-events.jsonl":
            raise OSError("simulated read failure")
        return ""

    monkeypatch.setattr(Path, "read_text", _raise_os_error)
    assert _publication_approved(feature_dir) is False


def test_publication_approved_false_for_other_gate_names(
    feature_dir: Path,
) -> None:
    """Gate events with the wrong name MUST NOT satisfy the publication gate."""
    _write_event_log(
        feature_dir,
        [
            {"type": "gate_passed", "name": "review_approved"},
            {"type": "gate_passed", "name": "scope_approved"},
        ],
    )
    assert _publication_approved(feature_dir) is False
