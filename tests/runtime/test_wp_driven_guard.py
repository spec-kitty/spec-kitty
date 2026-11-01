"""A WP-driven custom family keeps the WP-advance guard at implement/review (FR-003/FR-004).

Before the fix the composed guard set ``wp_advance_ready`` only for the literal
``software-dev`` family, and the unregistered custom family degraded to a neutral
empty result, so the guard was silently skipped with work packages pending.

#6330 hardens the fact behind that decision: the guard reads the run directory the
caller already resolved, never a re-resolution from ``feature_dir.name`` (which
``AGENTS.md`` says is not a mission handle). The tests below fail if the fact is
derived from the directory name again.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.runtime._next_mission_scaffold import (
    CUSTOM_ANALYZE_FAMILY,
    scaffold_custom_analyze_mission,
    scaffold_software_dev,
)

pytestmark = [pytest.mark.git_repo]

_PENDING = "Not all work packages have required status (for_review, approved, or done)"
_PLAN_FAMILY = "acme-plan"
_PLAN_STEPS = ("specify", "research", "plan", "review")
#: A planning-directory name that is deliberately NOT the mission handle.
_NOT_A_HANDLE = "status-home"


def _guard(repo: Path, slug: str, family: str, action: str) -> list[str]:
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_composition import _check_composed_action_guard

    run_ref = get_or_start_run(slug, repo, family)
    return _check_composed_action_guard(
        action,
        repo / "kitty-specs" / slug,
        mission=family,
        repo_root=repo,
        run_dir=Path(run_ref.run_dir),
    )


def _rename_away_from_the_handle(feature_dir: Path) -> Path:
    """Move the planning dir to a name that is not the mission slug."""
    renamed = feature_dir.with_name(_NOT_A_HANDLE)
    feature_dir.rename(renamed)
    return renamed


def test_wp_driven_custom_family_holds_at_implement_with_a_pending_wp(tmp_path: Path) -> None:
    slug = scaffold_custom_analyze_mission(tmp_path)

    assert _guard(tmp_path, slug, CUSTOM_ANALYZE_FAMILY, "implement") == [_PENDING]


def test_software_dev_still_holds_at_implement_with_a_pending_wp(tmp_path: Path) -> None:
    scaffold_software_dev(tmp_path, "042-ctl", with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})

    assert _guard(tmp_path, "042-ctl", "software-dev", "implement") == [_PENDING]


def test_non_wp_driven_family_is_unaffected(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_io import mission_declares_wp_iteration

    slug = scaffold_custom_analyze_mission(tmp_path, family=_PLAN_FAMILY, steps=_PLAN_STEPS)

    run_ref = get_or_start_run(slug, tmp_path, _PLAN_FAMILY)
    assert mission_declares_wp_iteration(Path(run_ref.run_dir)) is False
    assert _guard(tmp_path, slug, _PLAN_FAMILY, "review") == []


def test_presence_fact_takes_wp_driven_from_the_threaded_run(tmp_path: Path) -> None:
    """The fact port: ``run_dir`` wins, an explicit slug is the only fallback.

    #6330 item 1 removes the implicit ``feature_dir.name`` derivation. The same
    fixture is asked three ways: with the run directory (authoritative), with an
    explicit mission slug (read-only fallback), and with neither (no fact — never
    a guess from the directory name, even when that name happens to be the slug).
    """
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_io import gather_artifact_presence

    slug = scaffold_custom_analyze_mission(tmp_path)
    run_ref = get_or_start_run(slug, tmp_path, CUSTOM_ANALYZE_FAMILY)
    feature_dir = tmp_path / "kitty-specs" / slug

    def _fact(**kwargs: object) -> object:
        return gather_artifact_presence(
            feature_dir,
            mission_family=CUSTOM_ANALYZE_FAMILY,
            step_id="implement",
            repo_root=tmp_path,
            **kwargs,  # type: ignore[arg-type]
        ).wp_driven

    assert _fact(run_dir=Path(run_ref.run_dir)) is True
    assert _fact(mission_slug=slug) is True
    assert _fact() is False


def test_composed_guard_reads_the_threaded_run_when_the_dir_name_is_not_a_handle(tmp_path: Path) -> None:
    """#6330 item 1: ``run_dir`` decides ``wp_driven``; the dir name never does.

    Same fixture, two calls: the control (real directory) proves the assertion can
    observe the guard firing; the renamed directory proves the fact no longer
    re-resolves the run from ``feature_dir.name``. Pre-fix this call could not even
    be expressed (the guard took no ``run_dir``), and the production path — which
    supplied none — returned ``[]``: the fail-open this mission closes.
    """
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_composition import _check_composed_action_guard

    slug = scaffold_custom_analyze_mission(tmp_path)
    run_ref = get_or_start_run(slug, tmp_path, CUSTOM_ANALYZE_FAMILY)
    feature_dir = tmp_path / "kitty-specs" / slug

    control = _check_composed_action_guard(
        "implement",
        feature_dir,
        mission=CUSTOM_ANALYZE_FAMILY,
        repo_root=tmp_path,
        run_dir=Path(run_ref.run_dir),
    )
    assert control == [_PENDING]

    renamed = _rename_away_from_the_handle(feature_dir)
    threaded = _check_composed_action_guard(
        "implement",
        renamed,
        mission=CUSTOM_ANALYZE_FAMILY,
        repo_root=tmp_path,
        run_dir=Path(run_ref.run_dir),
    )
    assert threaded == [_PENDING]


def test_cli_guard_reads_the_threaded_run_when_the_dir_name_is_not_a_handle(tmp_path: Path) -> None:
    """The legacy CLI guard path takes the same threaded run directory."""
    from runtime.next.runtime_bridge import _check_cli_guards, get_or_start_run

    slug = scaffold_custom_analyze_mission(tmp_path)
    run_ref = get_or_start_run(slug, tmp_path, CUSTOM_ANALYZE_FAMILY)
    feature_dir = _rename_away_from_the_handle(tmp_path / "kitty-specs" / slug)

    assert _check_cli_guards(
        "implement",
        feature_dir,
        mission_family=CUSTOM_ANALYZE_FAMILY,
        repo_root=tmp_path,
        run_dir=Path(run_ref.run_dir),
    ) == [_PENDING]


def test_dispatch_via_composition_forwards_the_run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The production dispatch path forwards the caller's run to the guard.

    ``StepContractExecutor`` is stubbed so the assertion is about the threaded
    run directory reaching the *real* post-action guard, not about composition.
    """
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_composition import _dispatch_via_composition
    from specify_cli.mission_step_contracts import executor as executor_module

    slug = scaffold_custom_analyze_mission(tmp_path)
    run_ref = get_or_start_run(slug, tmp_path, CUSTOM_ANALYZE_FAMILY)
    feature_dir = _rename_away_from_the_handle(tmp_path / "kitty-specs" / slug)

    class _StubExecutor:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def execute(self, _context: object, contract: object = None) -> SimpleNamespace:
            return SimpleNamespace(invocation_ids=(), steps=())

    monkeypatch.setattr(executor_module, "StepContractExecutor", _StubExecutor)

    failures = _dispatch_via_composition(
        repo_root=tmp_path,
        mission=CUSTOM_ANALYZE_FAMILY,
        action="implement",
        actor="agent-x",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=feature_dir,
        run_dir=Path(run_ref.run_dir),
    )

    assert failures == [_PENDING]


def test_an_unreadable_frozen_template_logs_the_fail_closed_downgrade(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """#6330: a threaded run whose frozen DAG cannot be read is not silently ignored.

    The fact stays ``False`` (fail-closed, unchanged), but skipping the WP-advance
    guard must be visible in the log — the same "no silent downgrade" rule the
    mission applies to ``requires_substantive_evidence``.
    """
    import logging

    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_io import gather_artifact_presence

    slug = scaffold_custom_analyze_mission(tmp_path)
    run_ref = get_or_start_run(slug, tmp_path, CUSTOM_ANALYZE_FAMILY)
    run_dir = Path(run_ref.run_dir)

    with caplog.at_level(logging.WARNING, logger="runtime.next.runtime_bridge_io"):
        # Positive control first: the healthy template logs nothing.
        healthy = gather_artifact_presence(
            tmp_path / "kitty-specs" / slug,
            mission_family=CUSTOM_ANALYZE_FAMILY,
            step_id="implement",
            repo_root=tmp_path,
            run_dir=run_dir,
        )
        assert healthy.wp_driven is True
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

        (run_dir / "mission_template_frozen.yaml").write_text("not: a runtime template\n", encoding="utf-8")
        broken = gather_artifact_presence(
            tmp_path / "kitty-specs" / slug,
            mission_family=CUSTOM_ANALYZE_FAMILY,
            step_id="implement",
            repo_root=tmp_path,
            run_dir=run_dir,
        )

    assert broken.wp_driven is False, "an unreadable template is still fail-closed"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, [r.getMessage() for r in caplog.records]
    assert str(run_dir) in warnings[0].getMessage()
