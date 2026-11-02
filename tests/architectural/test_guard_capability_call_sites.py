"""Architectural ratchet: GuardCapability call sites in ``src/`` (PR #1850 M1).

``GuardCapability`` is asserted-at-the-surface (FR-008 / C-GUARD-2): each
non-standard member authorizes exactly ONE bookkeeping flow onto a protected
ref. PR #1850 regressed this by sprinkling ``TEST_MODE`` and
``MERGE_BOOKKEEPING`` onto ordinary task/workflow/finalize surfaces, silently
converting "refused on protected main" into "allowed". This ratchet makes the
capability/flow binding structural:

1. **No production module asserts ``TEST_MODE``.** The member exists for test
   fixtures only; the sole ``src/`` reference is the policy module's own
   ``_PROTECTED_FLOW_CAPABILITIES`` set (the enum's home).
2. **Every other protected-flow member has an explicit per-flow allowlist.**
   ``MERGE_BOOKKEEPING`` belongs to the merge done-transitions flow,
   ``UPGRADE_BOOKKEEPING`` to the upgrade flow, ``RELEASE_FLOW`` currently has
   no caller (S6 wire-or-delete debt — adding one requires updating this
   allowlist deliberately).

The scan is AST-based (real ``GuardCapability.<MEMBER>`` attribute
expressions), so prose mentions in docstrings/comments do not trip it.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

# The policy module that defines the enum and its protected-flow set. It is
# the ONLY src/ file allowed to reference GuardCapability.TEST_MODE.
_ENUM_HOME = "src/specify_cli/core/commit_guard.py"

# Per-flow allowlists for the remaining protected-flow members. Each entry is
# a documented ONE-flow authorization (FR-008); extending a set is an explicit
# policy decision, not a convenience.
_PROTECTED_FLOW_ALLOWLISTS: dict[str, frozenset[str]] = {
    # Test-fixture-only: no production caller, ever.
    "TEST_MODE": frozenset({_ENUM_HOME}),
    # The bona-fide merge/close done-transitions bookkeeping flow. Every caller
    # (the merge executor's done-transitions commit AND its birth-cutover COORD
    # seed commit, plus the post-merge retrospective terminus) lands through the
    # ONE shared seam `git/bookkeeping_commit.py` (#2280 / PR #2281) — its two
    # named entry points (`commit_merge_bookkeeping` PRIMARY /
    # `commit_coord_seed_bookkeeping` COORD) both delegate to a single guarded
    # `_commit_bookkeeping` call site. A single sanctioned protected-flow commit
    # surface, not a second guard-capability call site outside this module.
    "MERGE_BOOKKEEPING": frozenset({_ENUM_HOME, "src/specify_cli/git/bookkeeping_commit.py"}),
    # The bona-fide upgrade bookkeeping flow. Main checkout AND every sibling
    # worktree (#2385 / epic #2392) land their upgrade commit through the ONE
    # shared seam `upgrade/autocommit.py` — a single sanctioned protected-flow
    # commit surface, mirroring the MERGE_BOOKKEEPING consolidation above.
    "UPGRADE_BOOKKEEPING": frozenset({_ENUM_HOME, "src/specify_cli/upgrade/autocommit.py"}),
    # No reachable caller today (S6 debt: wire or delete).
    "RELEASE_FLOW": frozenset({_ENUM_HOME}),
    # post-merge-write-authoring-finish-01KYRRM5 WP04 (#3033 FR-003/FR-004):
    # the ONE E2 (published) CONSOLIDATED-surface write flow -- a mission
    # whose Target Ref has been deleted (published to trunk) commits its
    # evidence to the repository-root checkout on the resolved Primary
    # Branch instead. Two authorized call sites, each independently
    # recognising the E2 CONSOLIDATED destination from PUBLIC signals ONLY
    # (``coordination.write_seam.is_post_consolidation_write_target``) before
    # asserting the capability -- never from message text or an ambient env
    # var (C-GUARD-2): ``coordination/write_seam.py`` (the coord-partition
    # write-seam bypass of the frozen, capability-less
    # ``commit_router.commit_for_mission``) and
    # ``cli/commands/safe_commit_cmd.py`` (the mission-aware PRIMARY-kind CLI
    # path, ``spec-kitty safe-commit`` -- the #3033 canonical repro, C-006).
    "POST_CONSOLIDATION_WRITE": frozenset(
        {
            _ENUM_HOME,
            "src/specify_cli/coordination/write_seam.py",
            "src/specify_cli/cli/commands/safe_commit_cmd.py",
        }
    ),
}


def _iter_src_python_files(repo_root: Path = _REPO_ROOT) -> list[Path]:
    return sorted(
        p for p in (repo_root / "src").rglob("*.py") if "__pycache__" not in p.parts
    )


def _rel(path: Path, repo_root: Path = _REPO_ROOT) -> str:
    return path.relative_to(repo_root).as_posix()


def _members_referenced_in_tree(tree: ast.AST) -> set[str]:
    """Return the ``GuardCapability.<MEMBER>`` attribute names used in ``tree``."""
    members: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "GuardCapability"
        ):
            members.add(node.attr)
    return members


def _guard_capability_members_referenced(path: Path) -> set[str]:
    """Return the ``GuardCapability.<MEMBER>`` attribute names used in ``path``.

    Reads ``path`` fresh on every call. This is deliberate: the two-sided
    fault-bite test below rewrites a scratch file and must observe each
    mutation. Real-tree checks use :func:`_build_capability_facts` instead.
    """
    return _members_referenced_in_tree(ast.parse(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class _CapabilityFacts:
    """Read-only ``member -> repo-relative source paths`` map for the live tree."""

    paths_by_member: Mapping[str, frozenset[str]]


def _build_capability_facts(source_tree: Mapping[Path, object]) -> _CapabilityFacts:
    """Derive the live capability-site map from an immutable ``src/`` source tree.

    One walk over the session-cached AST answers every per-member unexpected-site
    and stale-allowlist assertion. It never accepts a mutable scratch root: the
    mutation control keeps using :func:`_unexpected_protected_flow_sites`.
    """
    paths_by_member: dict[str, set[str]] = {
        member: set() for member in _PROTECTED_FLOW_ALLOWLISTS
    }
    for path in sorted(source_tree):
        if "__pycache__" in path.parts:
            continue
        tree = source_tree[path].tree  # type: ignore[attr-defined]
        for member in _members_referenced_in_tree(tree):
            if member in paths_by_member:
                paths_by_member[member].add(_rel(path))
    return _CapabilityFacts(
        MappingProxyType(
            {member: frozenset(paths) for member, paths in paths_by_member.items()}
        )
    )


def _unexpected_protected_flow_sites_from_facts(
    facts: _CapabilityFacts, member: str, allowlist: frozenset[str]
) -> set[str]:
    """Live capability sites outside *allowlist*, from the immutable facts."""
    return set(facts.paths_by_member.get(member, frozenset())) - allowlist


def _stale_allowlist_entries_from_facts(
    facts: _CapabilityFacts, member: str, allowlist: frozenset[str]
) -> set[str]:
    """Allowlist entries with no live site, from the immutable facts."""
    live = facts.paths_by_member.get(member, frozenset())
    return {
        entry
        for entry in allowlist
        if entry not in live
        and entry != _ENUM_HOME  # the enum home may reference members only via the policy set
    }


@pytest.fixture(scope="session")
def live_capability_facts(
    src_source_tree: Mapping[Path, object],
) -> _CapabilityFacts:
    """Build the real-tree capability map once per session from cached ASTs."""
    return _build_capability_facts(src_source_tree)


def _unexpected_protected_flow_sites(
    repo_root: Path, member: str, allowlist: frozenset[str]
) -> set[str]:
    """Run the live protected-flow enforcement oracle for one capability."""
    actual = {
        _rel(path, repo_root)
        for path in _iter_src_python_files(repo_root)
        if member in _guard_capability_members_referenced(path)
    }
    return actual - allowlist


def test_guard_capability_enforcement_has_two_sided_fault_bite(tmp_path: Path) -> None:
    probe = tmp_path / "src" / "probe.py"
    probe.parent.mkdir()
    probe.write_text("capability = GuardCapability.STANDARD\n", encoding="utf-8")
    assert _unexpected_protected_flow_sites(
        tmp_path, "TEST_MODE", frozenset()
    ) == set()

    probe.write_text("capability = GuardCapability.TEST_MODE\n", encoding="utf-8")
    assert _unexpected_protected_flow_sites(
        tmp_path, "TEST_MODE", frozenset()
    ) == {"src/probe.py"}


@pytest.mark.parametrize("member", sorted(_PROTECTED_FLOW_ALLOWLISTS))
def test_protected_flow_capability_call_sites_are_allowlisted(
    member: str, live_capability_facts: _CapabilityFacts
) -> None:
    """Each protected-flow GuardCapability member binds to its ONE flow.

    ``STANDARD`` is freely assertable (it grants nothing on protected refs);
    every other member is restricted to the allowlisted module(s) above. A new
    site must either assert ``STANDARD`` (refused on protected refs — almost
    always correct for status bookkeeping) or extend the allowlist with a
    rationale comment naming the ONE flow it authorizes.
    """
    allowlist = _PROTECTED_FLOW_ALLOWLISTS[member]
    unexpected = _unexpected_protected_flow_sites_from_facts(
        live_capability_facts, member, allowlist
    )
    assert not unexpected, (
        f"GuardCapability.{member} is asserted outside its flow: "
        f"{sorted(unexpected)}. Each non-standard capability authorizes "
        "exactly ONE bookkeeping flow (FR-008 / C-GUARD-2); ordinary status "
        "bookkeeping must assert STANDARD so protected destinations are "
        "refused. PR #1850's guard-bypass regression is exactly this misuse."
    )

    stale = _stale_allowlist_entries_from_facts(
        live_capability_facts, member, allowlist
    )
    if member in {"MERGE_BOOKKEEPING", "UPGRADE_BOOKKEEPING"}:
        assert not stale, (
            f"Allowlisted GuardCapability.{member} flow module(s) no longer "
            f"assert it: {sorted(stale)}. Remove them from "
            "_PROTECTED_FLOW_ALLOWLISTS so the binding stays exact."
        )


# --------------------------------------------------------------------------- #
# Regression pins for the immutable-facts reuse (CI speed hardening).
# --------------------------------------------------------------------------- #
def test_live_capability_facts_are_reusable_without_scanning_disk(
    live_capability_facts: _CapabilityFacts, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session facts replace per-test whole-tree reads and AST parses.

    RED before the reuse change: ``_CapabilityFacts`` and the facts-based
    helpers did not exist, so the real-tree checks re-walked ``src/`` once per
    capability member and once more per allow-list entry. Green afterwards
    proves both the unexpected-site and stale-entry assertions can be answered
    from the read-only ``src_source_tree`` fixture alone.
    """

    def _unexpected_disk_access(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "live capability facts must come from the immutable source-tree "
            "fixture, not a fresh disk scan"
        )

    monkeypatch.setattr(Path, "read_text", _unexpected_disk_access)
    monkeypatch.setattr(Path, "rglob", _unexpected_disk_access)

    for member, allowlist in _PROTECTED_FLOW_ALLOWLISTS.items():
        assert (
            _unexpected_protected_flow_sites_from_facts(
                live_capability_facts, member, allowlist
            )
            == set()
        )
        assert (
            _stale_allowlist_entries_from_facts(
                live_capability_facts, member, allowlist
            )
            == set()
        )
