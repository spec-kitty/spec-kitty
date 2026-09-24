"""WP04 (terminus-integrity-followups) — WS2 resume strategy authority + lane-tip CAS.

Covers FR-003 (resume strategy precedence + H1 strategy-flip refusal) and
FR-004 (additive ``MergeState`` fields + the pure lane-tip CAS helper), the two
halves WP05 later wires into the executor reseed / resume anchoring.

Red-first: the symbols under test (``_resolve_effective_merge_strategy``,
``_persisted_strategy``, ``MergeStrategyFlipError`` in
``specify_cli.cli.commands.merge``; ``lane_tip_cas_ok`` and the three additive
``MergeState`` fields in ``specify_cli.merge.state``) do not exist yet.

Real git fixtures throughout for the CAS cases — no mocking of git object
reachability, since that reachability IS the invariant being proven.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

from specify_cli.cli.commands.merge import (
    MergeStrategyFlipError,
    _persisted_strategy,
    _resolve_effective_merge_strategy,
)
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState, lane_tip_cas_ok

MISSION_ID = "057-terminus-followups"


# ---------------------------------------------------------------------------
# Real-fixture git helpers (no mocking)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", ref)


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-qb", "main", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "f.txt").write_text("0\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "c0")
    return root


def _commit(repo: Path, content: str, msg: str) -> str:
    (repo / "f.txt").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", msg)
    return _rev(repo, "HEAD")


def _make_state(**overrides: object) -> MergeState:
    base: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": "terminus-followups",
        "target_branch": "main",
        "wp_order": ["WP01"],
    }
    base.update(overrides)
    return MergeState(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T018 — strategy precedence table (pure resolution)
# ---------------------------------------------------------------------------


class TestResumeStrategyPrecedence:
    """explicit > persisted > config > SQUASH (persisted only consulted on resume)."""

    def test_explicit_only_fresh(self) -> None:
        resolved = _resolve_effective_merge_strategy(explicit=MergeStrategy.REBASE, persisted=None, config=None, is_resume=False)
        assert resolved is MergeStrategy.REBASE

    def test_explicit_wins_over_everything_on_resume(self) -> None:
        resolved = _resolve_effective_merge_strategy(
            explicit=MergeStrategy.MERGE,
            persisted=MergeStrategy.MERGE,
            config=MergeStrategy.SQUASH,
            is_resume=True,
        )
        assert resolved is MergeStrategy.MERGE

    def test_persisted_used_on_resume_when_no_explicit(self) -> None:
        resolved = _resolve_effective_merge_strategy(
            explicit=None,
            persisted=MergeStrategy.MERGE,
            config=MergeStrategy.SQUASH,
            is_resume=True,
        )
        assert resolved is MergeStrategy.MERGE

    def test_config_fallback_on_resume(self) -> None:
        resolved = _resolve_effective_merge_strategy(explicit=None, persisted=None, config=MergeStrategy.REBASE, is_resume=True)
        assert resolved is MergeStrategy.REBASE

    def test_squash_default_when_all_absent(self) -> None:
        resolved = _resolve_effective_merge_strategy(explicit=None, persisted=None, config=None, is_resume=True)
        assert resolved is MergeStrategy.SQUASH

    def test_fresh_run_ignores_persisted(self) -> None:
        # A fresh (non-resume) run never consults the persisted value; with no
        # explicit and no config it collapses to SQUASH, not the persisted MERGE.
        resolved = _resolve_effective_merge_strategy(explicit=None, persisted=MergeStrategy.MERGE, config=None, is_resume=False)
        assert resolved is MergeStrategy.SQUASH

    def test_equal_explicit_and_persisted_is_not_a_flip(self) -> None:
        resolved = _resolve_effective_merge_strategy(
            explicit=MergeStrategy.SQUASH,
            persisted=MergeStrategy.SQUASH,
            config=None,
            is_resume=True,
        )
        assert resolved is MergeStrategy.SQUASH


class TestStrategyFlipRefusal:
    """H1 — an explicit --strategy contradicting the persisted value REFUSEs."""

    def test_flip_merge_over_persisted_squash_refuses(self) -> None:
        with pytest.raises(MergeStrategyFlipError):
            _resolve_effective_merge_strategy(
                explicit=MergeStrategy.MERGE,
                persisted=MergeStrategy.SQUASH,
                config=None,
                is_resume=True,
            )

    def test_flip_squash_over_persisted_merge_refuses(self) -> None:
        with pytest.raises(MergeStrategyFlipError):
            _resolve_effective_merge_strategy(
                explicit=MergeStrategy.SQUASH,
                persisted=MergeStrategy.MERGE,
                config=None,
                is_resume=True,
            )

    def test_equal_explicit_does_not_refuse(self) -> None:
        # No exception — an equal explicit value is honored, not a flip.
        _resolve_effective_merge_strategy(
            explicit=MergeStrategy.MERGE,
            persisted=MergeStrategy.MERGE,
            config=None,
            is_resume=True,
        )

    def test_fresh_run_never_flip_refuses(self) -> None:
        # On a fresh run the persisted value is irrelevant; a differing explicit
        # is not a flip.
        resolved = _resolve_effective_merge_strategy(
            explicit=MergeStrategy.MERGE,
            persisted=MergeStrategy.SQUASH,
            config=None,
            is_resume=False,
        )
        assert resolved is MergeStrategy.MERGE


class TestPersistedStrategyCoercion:
    """``_persisted_strategy`` maps a persisted str field to the enum, safely."""

    def test_valid_value_maps_to_enum(self) -> None:
        assert _persisted_strategy(_make_state(strategy="merge")) is MergeStrategy.MERGE
        assert _persisted_strategy(_make_state(strategy="squash")) is MergeStrategy.SQUASH
        assert _persisted_strategy(_make_state(strategy="rebase")) is MergeStrategy.REBASE

    def test_empty_value_yields_none(self) -> None:
        assert _persisted_strategy(_make_state(strategy="")) is None

    def test_unparseable_value_yields_none(self) -> None:
        assert _persisted_strategy(_make_state(strategy="bogus")) is None


# ---------------------------------------------------------------------------
# T018 — lane-tip CAS (real git objects)
# ---------------------------------------------------------------------------


class TestLaneTipCas:
    """``lane_tip_cas_ok`` compares the persisted SHA as a git OBJECT."""

    def test_persisted_equals_live_ok(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _git(repo, "checkout", "-qb", "lane-a")
        c1 = _commit(repo, "1\n", "c1")
        assert lane_tip_cas_ok(repo, "lane-a", c1) is True

    def test_live_descendant_ok(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _git(repo, "checkout", "-qb", "lane-a")
        c1 = _commit(repo, "1\n", "c1")
        _commit(repo, "2\n", "c2")  # lane-a now a descendant of the persisted c1
        assert lane_tip_cas_ok(repo, "lane-a", c1) is True

    def test_live_strict_ancestor_behind_head_ok(self, tmp_path: Path) -> None:
        # #4982 window (post-plan D/F8): the persisted tip is AHEAD of the live
        # branch (the interrupted advance left the ref behind its own HEAD). The
        # CAS MUST NOT refuse this — it is the exact bug being preserved.
        repo = _init_repo(tmp_path / "repo")
        _git(repo, "checkout", "-qb", "lane-a")
        c1 = _commit(repo, "1\n", "c1")
        c2 = _commit(repo, "2\n", "c2")
        _git(repo, "checkout", "-q", "main")  # leave lane-a so it can be force-moved
        _git(repo, "branch", "-f", "lane-a", c1)  # move live tip BACK to c1
        assert lane_tip_cas_ok(repo, "lane-a", c2) is True

    def test_divergent_refuses(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        c0 = _rev(repo, "HEAD")
        _git(repo, "checkout", "-qb", "lane-a")
        _commit(repo, "a\n", "c1a")  # lane-a diverges
        c1a_absent_side = _rev(repo, "lane-a")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "reset", "-q", "--hard", c0)
        persisted_divergent = _commit(repo, "b\n", "c1b")  # unrelated line on main
        # live lane-a is c1a; persisted is c1b — neither is an ancestor of the other.
        assert c1a_absent_side != persisted_divergent
        assert lane_tip_cas_ok(repo, "lane-a", persisted_divergent) is False

    def test_branch_ref_absent_but_object_reachable_ok(self, tmp_path: Path) -> None:
        # The lane branch was already consolidated (ref gone); the persisted
        # commit still resolves as an object, so the tip is preserved in history.
        repo = _init_repo(tmp_path / "repo")
        persisted = _commit(repo, "1\n", "c1")  # reachable from main
        assert lane_tip_cas_ok(repo, "never-existed-lane", persisted) is True

    def test_absent_base_empty_sha_refuses(self, tmp_path: Path) -> None:
        # H4: an absent required base ⇒ the helper refuses (never proceeds).
        repo = _init_repo(tmp_path / "repo")
        assert lane_tip_cas_ok(repo, "lane-a", "") is False

    def test_unresolvable_persisted_object_refuses(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _git(repo, "checkout", "-qb", "lane-a")
        _commit(repo, "1\n", "c1")
        bogus = "0" * 40
        assert lane_tip_cas_ok(repo, "lane-a", bogus) is False


# ---------------------------------------------------------------------------
# T016 — additive MergeState fields + legacy deserialization
# ---------------------------------------------------------------------------


class TestMergeStateAdditiveFields:
    def test_new_fields_default_safely(self) -> None:
        state = _make_state()
        assert state.pre_mutation_coord_sha is None
        assert state.pre_mutation_coord_ref is None
        assert state.pre_interrupt_lane_tips == {}

    def test_legacy_state_deserializes_without_new_fields(self) -> None:
        # A pre-mission state file (new keys absent) loads with safe defaults.
        legacy = {
            "mission_id": MISSION_ID,
            "mission_slug": "terminus-followups",
            "target_branch": "main",
            "wp_order": ["WP01", "WP02"],
            "completed_wps": ["WP01"],
            "strategy": "merge",
        }
        state = MergeState.from_dict(legacy)
        assert state.pre_mutation_coord_sha is None
        assert state.pre_mutation_coord_ref is None
        assert state.pre_interrupt_lane_tips == {}
        assert state.strategy == "merge"

    def test_new_fields_roundtrip_through_to_dict(self) -> None:
        state = _make_state(
            pre_mutation_coord_sha="abc123",
            pre_mutation_coord_ref="refs/heads/kitty/coord",
            pre_interrupt_lane_tips={"lane-a": "deadbeef", "lane-b": "cafef00d"},
        )
        restored = MergeState.from_dict(state.to_dict())
        assert restored.pre_mutation_coord_sha == "abc123"
        assert restored.pre_mutation_coord_ref == "refs/heads/kitty/coord"
        assert restored.pre_interrupt_lane_tips == {"lane-a": "deadbeef", "lane-b": "cafef00d"}

    def test_lane_tips_default_is_not_shared(self) -> None:
        # ``field(default_factory=dict)`` — two instances must not share a dict.
        a = _make_state()
        b = _make_state()
        a.pre_interrupt_lane_tips["lane-a"] = "x"
        assert b.pre_interrupt_lane_tips == {}
