"""WP05 / T028(b) — status emission resolves ``feature_dir`` from the SEAM (FR-009).

Non-vacuous-pass discipline (renata): ``status/emit.py`` canonicalizes
``feature_dir`` (the ``canonicalize_feature_dir`` backstop), which would RESCUE a
wrong caller path and let a single happy-path test pass anyway. These tests prove
the CALLER (the transactional identity boundary, ``_identity_for_request``)
supplies the seam-resolved ``feature_dir`` — NOT that ``emit.py`` rescued it — by
**neutralizing the emit.py canonicalize backstop** and showing the event STILL
lands on the seam-resolved coordination surface.

If a caller regressed to handing an ad-hoc worktree-local path AND the backstop
were removed, the event would land on the wrong surface and the assertion below
would go RED. With the seam-resolved caller boundary in place, neutralizing the
backstop changes nothing — the proof the prompt demands.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import status_transition as st
from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest

pytest_plugins = ("tests.conftest_saas_sink",)
pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_FULL_ULID = "01KVPR00WP05EMIT000000000B"
_MID8 = _FULL_ULID[:8]
_SLUG = f"emit-seam-feature-dir-{_MID8}"
_DIRNAME = _SLUG
_COORD_BRANCH = f"kitty/mission-{_DIRNAME}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / _DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": _FULL_ULID,
                "mid8": _MID8,
                "coordination_branch": _COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", _COORD_BRANCH)
    return repo


def _seed_planned_on_coord(repo: Path) -> None:
    """Seed genesis→planned on the coord branch via a throwaway worktree (no fanout)."""
    seed = StatusEvent(
        event_id="01SEEDGENESIS00000000WP05B",
        mission_slug=_SLUG,
        mission_id=_FULL_ULID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-06-21T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(worktree), _COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / _DIRNAME
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))


def test_caller_supplies_seam_feature_dir_even_with_backstop_neutralized(
    coord_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transactional emit lands on the coord surface even with emit.py's backstop OFF.

    Neutralizing ``emit.py``'s ``canonicalize_feature_dir`` to the identity function
    proves the CALLER (``_identity_for_request``) already supplied the seam-resolved
    surface — the event lands on the coord branch regardless of the backstop. A
    caller that handed an ad-hoc worktree-local path would, with the backstop off,
    land on the wrong surface and fail this assertion.
    """
    _seed_planned_on_coord(coord_repo)

    # Neutralize the emit.py canonicalize backstop (identity passthrough). If the
    # event still lands on the coord surface, the CALLER supplied the seam path.
    import specify_cli.status.emit as emit_mod

    monkeypatch.setattr(emit_mod, "canonicalize_feature_dir", lambda p: p)

    event = st.emit_status_transition_transactional(
        TransitionRequest(
            feature_dir=coord_repo / "kitty-specs" / _DIRNAME,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane="claimed",
            actor="wp05-fr009-test",
            repo_root=coord_repo,
        ),
    )

    # The event landed on the coordination branch (the seam-resolved surface),
    # not the primary checkout — proven by reading the coord branch event log.
    show = _git(
        coord_repo,
        "show",
        f"{_COORD_BRANCH}:kitty-specs/{_DIRNAME}/status.events.jsonl",
    )
    assert event.event_id in show.stdout, (
        "the transactional emit did NOT land on the seam-resolved coordination "
        "surface with the emit.py backstop neutralized — the caller boundary "
        "(_identity_for_request) is not supplying the seam-resolved feature_dir."
    )
    # And the primary checkout carries NO status events file (the wrong surface).
    assert not (coord_repo / "kitty-specs" / _DIRNAME / "status.events.jsonl").exists(), (
        "a status events file leaked onto the primary checkout — the write did not "
        "converge on the single seam-resolved surface (FR-009)."
    )


def test_transactional_identity_feature_dir_is_seam_resolved_primary(
    coord_repo: Path,
) -> None:
    """The identity boundary resolves the CWD-invariant primary feature dir (the seam).

    Captures the value the caller boundary computes (``identity.feature_dir``) and
    asserts it is the canonical primary mission dir — independent of ``emit.py``'s
    later canonicalize. This is the value every downstream emit consumes.
    """
    identity = st._identity_for_request(
        TransitionRequest(
            feature_dir=coord_repo / "kitty-specs" / _DIRNAME,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane="claimed",
            actor="wp05-fr009-test",
            repo_root=coord_repo,
        )
    )
    assert identity.feature_dir == (coord_repo / "kitty-specs" / _DIRNAME)
    assert identity.feature_dir.is_absolute()
    assert ".worktrees" not in identity.feature_dir.parts, (
        "the identity feature_dir must be the canonical PRIMARY dir, never a "
        "worktree-local path (the seam-resolved surface FR-009 converges on)."
    )
