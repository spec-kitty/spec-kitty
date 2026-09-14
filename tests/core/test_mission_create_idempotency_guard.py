"""Fail-closed idempotency guard on mission creation (#4033).

`spec-kitty specify` / `agent mission create` invoked twice for the same
intent used to create TWO missions silently (both `{"result": "success"}`,
both exit 0) -- a silent duplicate a trainee hit while following the docs.
`create_mission_core()` now refuses a second create when a LIVE prior
mission shares the same base `mission_slug` AND `mission_type`, unless the
prior is abandoned (canceled, genesis / no lifecycle progress, or its
`spec.md` was never committed) or the caller passes
`allow_duplicate=True`.

``test_second_live_duplicate_create_is_refused_4033`` below started life as
the mandatory red-first ``@pytest.mark.regression`` reproduction (ADR
2026-07-17-1): before the guard existed it asserted the SECOND create
*succeeded* (the #4033 bug), proven red against the pre-fix code. It is
committed here already flipped to the fixed, permanent behavior -- the
guarded refusal -- per the project's "never leave a regression-marked
passing test" convention (a `regression`-marked test asserts a *defect*,
not a fix).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import (
    MissionCreationError,
    MissionCreationResult,
    create_mission_core,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

from tests._factories import provision_test_charter
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _init_git_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "-m", "init", "--allow-empty")


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


def _create(repo: Path, slug: str, **overrides: object) -> MissionCreationResult:
    """Thin wrapper: real create_mission_core() call, SINGLE_BRANCH by default."""
    kwargs: dict[str, object] = {
        "topology": MissionTopology.SINGLE_BRANCH,
        "allow_worktree_context": True,
        **_mission_summary(slug),
        **overrides,
    }
    return create_mission_core(repo, slug, **kwargs)


def _commit_spec(repo: Path, feature_dir: Path) -> None:
    """Commit spec.md so the mission reads as genuinely 'worked' (live)."""
    spec_path = feature_dir / "spec.md"
    spec_path.write_text("# Spec\n\nSubstantive spec content for the guard test.\n", encoding="utf-8")
    rel = spec_path.relative_to(repo)
    _git(repo, "add", str(rel))
    _git(repo, "commit", "-m", f"Add spec for {feature_dir.name}")


_SEED_COUNTER = 0


def _next_event_id() -> str:
    global _SEED_COUNTER  # noqa: PLW0603 -- module-local monotonic counter for unique test event ids
    _SEED_COUNTER += 1
    return f"01GUARDTEST{_SEED_COUNTER:016d}"


def _cancel_only_wp(feature_dir: Path, mission_slug: str, wp_id: str = "WP01") -> None:
    """Seed one WP genesis -> planned -> canceled: the whole mission's only
    recorded work package was called off (the 'canceled' abandonment facet)."""
    seed_wp_to_planned(feature_dir, wp_id, slug=mission_slug)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=_next_event_id(),
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CANCELED,
            at="2026-01-01T00:05:00+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
            reason="test cancellation",
        ),
    )


def _read_meta(feature_dir: Path) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def _cross_mid8_bucket() -> None:
    """Sleep past the mid8 collision window between two same-test creates.

    mid8 is the first 8 Crockford chars of a ULID. The 48-bit millisecond
    timestamp is Crockford-base32 encoded across the ULID's first 10 chars
    (5 bits/char); keeping only the first 8 drops the low 2 chars (10 bits),
    so two creates inside the same ~1024 ms bucket mint the SAME directory
    name and the second silently overwrites the first -- the same class of
    gotcha noted in ``test_mission_create_scaffold_rollback.py`` (squad R3,
    #4051). Empirically measured here: 1.1s reliably crosses the boundary.
    Any test that expects the second create to mint a genuinely distinct
    mission directory must cross this boundary first.
    """
    time.sleep(1.1)


# ---------------------------------------------------------------------------
# Guard fires on a live duplicate (#4033 fix; formerly the red-first repro)
# ---------------------------------------------------------------------------


def test_second_live_duplicate_create_is_refused_4033(tmp_path: Path) -> None:
    """FR-001/FR-002: a second same-slug+same-type create against a LIVE
    prior mission is refused before any scaffold write, naming the existing
    mission (slug + mid8) and the --allow-duplicate override (NFR-002: no
    orphan scaffold survives the refusal)."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "dup-mission-guard")
    _commit_spec(tmp_path, first.feature_dir)  # real work happened: this mission is LIVE

    pre_existing_dirs = {p.name for p in (tmp_path / "kitty-specs").iterdir()}
    assert pre_existing_dirs == {first.feature_dir.name}

    with pytest.raises(MissionCreationError) as excinfo:
        _create(tmp_path, "dup-mission-guard")

    error_message = str(excinfo.value)
    assert "dup-mission-guard" in error_message
    assert str(first.meta["mid8"]) in error_message
    assert "--allow-duplicate" in error_message

    # NFR-002: refusal leaves kitty-specs/ untouched -- no orphan scaffold.
    post_refusal_dirs = {p.name for p in (tmp_path / "kitty-specs").iterdir()}
    assert post_refusal_dirs == pre_existing_dirs


# ---------------------------------------------------------------------------
# Abandonment-aware auto-allow (FR-003) -- no flag needed
# ---------------------------------------------------------------------------


def test_genesis_prior_auto_allows_recreate_with_no_flag(tmp_path: Path) -> None:
    """A prior mission that never advanced past its own create bootstrap
    (no work-package lifecycle events, spec.md never committed) is genesis
    -- abandoned -- so a re-create with NO flag just succeeds."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "genesis-mission-guard")
    # Deliberately do nothing further: spec.md stays uncommitted, no WPs.
    _cross_mid8_bucket()

    second = _create(tmp_path, "genesis-mission-guard")

    assert second.feature_dir != first.feature_dir
    dirs = {p.name for p in (tmp_path / "kitty-specs").iterdir()}
    assert dirs == {first.feature_dir.name, second.feature_dir.name}


def test_canceled_only_prior_auto_allows_recreate_with_no_flag(tmp_path: Path) -> None:
    """A prior mission whose only recorded work package was canceled is
    abandoned, so a re-create with NO flag succeeds."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "canceled-mission-guard")
    _commit_spec(tmp_path, first.feature_dir)
    _cancel_only_wp(first.feature_dir, first.mission_slug)
    _cross_mid8_bucket()

    second = _create(tmp_path, "canceled-mission-guard")

    assert second.feature_dir != first.feature_dir


# ---------------------------------------------------------------------------
# Escape hatch (FR-004)
# ---------------------------------------------------------------------------


def test_allow_duplicate_true_creates_second_live_mission(tmp_path: Path) -> None:
    """--allow-duplicate (allow_duplicate=True) overrides the guard and
    creates a second live same-key mission on purpose."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "deliberate-dup-mission-guard")
    _commit_spec(tmp_path, first.feature_dir)
    _cross_mid8_bucket()

    second = _create(tmp_path, "deliberate-dup-mission-guard", allow_duplicate=True)

    assert second.feature_dir != first.feature_dir
    dirs = {p.name for p in (tmp_path / "kitty-specs").iterdir()}
    assert dirs == {first.feature_dir.name, second.feature_dir.name}


# ---------------------------------------------------------------------------
# Duplicate key edge case: same slug, different mission_type
# ---------------------------------------------------------------------------


def test_same_slug_different_mission_type_is_allowed(tmp_path: Path) -> None:
    """A `research` and a `software-dev` mission sharing a name are
    legitimately different work -- not a duplicate key (spec.md edge case)."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "shared-name-mission-guard", mission="research")
    _commit_spec(tmp_path, first.feature_dir)
    _cross_mid8_bucket()

    second = _create(tmp_path, "shared-name-mission-guard", mission="software-dev")

    assert second.feature_dir != first.feature_dir
    assert _read_meta(second.feature_dir)["mission_type"] == "software-dev"
    assert _read_meta(first.feature_dir)["mission_type"] == "research"


# ---------------------------------------------------------------------------
# Fail-closed on an unreadable prior mission (C-002)
# ---------------------------------------------------------------------------


def test_corrupt_prior_meta_json_fails_closed_and_refuses(tmp_path: Path) -> None:
    """C-002: when a same-slug prior mission's meta.json cannot be read, its
    type/abandonment cannot be established -- the guard fails closed and
    refuses rather than silently allowing a possible duplicate."""
    _init_git_repo(tmp_path)
    first = _create(tmp_path, "corrupt-meta-mission-guard")
    (first.feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(MissionCreationError, match="corrupt-meta-mission-guard"):
        _create(tmp_path, "corrupt-meta-mission-guard")
