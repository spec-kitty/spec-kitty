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
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.decision import Decision, _with_guard_failure_paths
from runtime.next.runtime_bridge_io import artifact_search_paths

pytestmark = [pytest.mark.unit]


def _blocked(**overrides: object) -> Decision:
    payload: dict[str, object] = {
        "kind": "blocked",
        "agent": "claude",
        "mission_slug": "qa-run-01M1ZZZZ",
        "mission": "software-dev",
        "mission_state": "review",
        "timestamp": "2026-09-14T00:00:00Z",
        "guard_failures": ["spec.md", "tasks.md"],
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


def test_paths_are_serialized_for_json_consumers(tmp_path: Path) -> None:
    payload = _with_guard_failure_paths(_blocked(), tmp_path).to_dict()

    assert payload["guard_failure_paths"]["spec.md"].endswith("spec.md")
    # The identity strings the SC-007 query/advance parity invariant compares
    # are untouched — the paths ride alongside them, never inside them.
    assert payload["guard_failures"] == ["spec.md", "tasks.md"]


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
    assert decision.guard_failures == ["spec.md", "tasks.md"]
    assert decision.guard_failure_paths == {}
