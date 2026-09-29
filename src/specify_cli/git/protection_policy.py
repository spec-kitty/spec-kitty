"""Boundary-resolved protected-branch configuration carrier (FR-004/006/007/008).

This module is the **sole sanctioned source** of the resolved protection set.
Every caller that needs to decide "is this ref protected?" must go through
:class:`ProtectionPolicy` — specifically its :meth:`ProtectionPolicy.resolve`
class method — rather than reading ``.kittify/config.yaml`` or calling git
directly for this purpose.

Design basis
------------
ADR ``docs/adr/3.x/2026-06-21-1-protected-branch-config-boundary-resolved-value.md``
and design squad research ``protected-branch-carrier-decision.md`` establish the
standalone-value-object shape.  The existing ``core.commit_guard.evaluate`` /
``ProtectionState`` seam is *reused unchanged*; this module only resolves the
**input** that is fed into it.

Resolution rules (from ``contracts/protection-config.md``)
----------------------------------------------------------
+--------------------------------------------------+----------------------------------------------+
| ``.kittify/config.yaml`` state                   | ``protected_branches`` resolved as           |
+==================================================+==============================================+
| No ``protection:`` block (key absent)            | ``{main, master}`` ∪ {remote default branch} |
+--------------------------------------------------+----------------------------------------------+
| ``protection.protected_branches: [a, b]``        | ``{a, b}`` exactly — no name-default union   |
+--------------------------------------------------+----------------------------------------------+
| ``protection.protected_branches: []``            | ``frozenset()`` — nothing protected          |
+--------------------------------------------------+----------------------------------------------+
| Malformed value (non-list under the key)         | Raises :class:`ProtectionConfigError`        |
+--------------------------------------------------+----------------------------------------------+
| Non-mapping top level (e.g. a bare scalar)       | Raises :class:`ProtectionConfigError`        |
+--------------------------------------------------+----------------------------------------------+

The operator hatch ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` (FR-006) is
resolved onto ``operator_hatch_active``; when active, :meth:`is_protected`
returns ``False`` for every ref.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HATCH_ENV_VAR = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_DEFAULT_PROTECTED_BRANCHES: frozenset[str] = frozenset({"main", "master"})


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class ProtectionConfigError(RuntimeError):
    """Raised when ``.kittify/config.yaml`` has a malformed ``protection:`` block.

    Fail-closed: a malformed value is never silently replaced by a default.
    """


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtectionPolicy:
    """Frozen, boundary-resolved carrier for the protection decision inputs.

    Constructed exclusively via :meth:`resolve` — the ONLY sanctioned producer.
    After construction, no further git/filesystem/env reads are needed for
    protection decisions (NFR-003).

    Attributes:
        protected_branches: Resolved set of branch names that must not receive
            direct spec-kitty status commits.  The contents depend on the
            ``.kittify`` config state; see module docstring for the resolution
            table.
        operator_hatch_active: ``True`` when the operator escape hatch
            ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` is set to a truthy
            value (``"1"``, ``"true"``, or ``"yes"``).  When active,
            :meth:`is_protected` always returns ``False``.
    """

    protected_branches: frozenset[str]
    operator_hatch_active: bool
    #: Mission-scoped fold of the operator-hatch concept (#5100 FR-008): the ONE
    #: branch a mission with ``meta.commit_to_target: true`` may write to
    #: directly. ``None`` (the default) means no mission scope. Set only via
    #: :meth:`scoped_to_mission` / :meth:`resolve_for_mission`, never by env.
    mission_bypass_branch: str | None = None

    # ------------------------------------------------------------------
    # Constructor / resolver
    # ------------------------------------------------------------------

    @classmethod
    def resolve(cls, repo_root: Path) -> ProtectionPolicy:
        """Resolve the protection policy for *repo_root*.

        This is the ONLY sanctioned function that reads git/filesystem/env for
        the protection set (FR-007, NFR-003).  All I/O is confined here; the
        returned value is frozen and I/O-free.

        Args:
            repo_root: Repository root (the directory that contains ``.kittify/``).

        Returns:
            A frozen :class:`ProtectionPolicy` with the resolved protection set
            and hatch state.

        Raises:
            :class:`ProtectionConfigError`: The ``protection.protected_branches``
                value exists but is not a list.
        """
        operator_hatch_active = _resolve_hatch()
        protected = _resolve_protected_branches(repo_root)
        return cls(
            protected_branches=protected,
            operator_hatch_active=operator_hatch_active,
        )

    # ------------------------------------------------------------------
    # Decision method
    # ------------------------------------------------------------------

    def is_protected(self, ref: str) -> bool:
        """Return ``True`` iff *ref* is in the protected set and the hatch is off.

        This folds the duplicated ``not hatch and ref in protected`` idiom that
        previously appeared at ≥3 callsites.

        Args:
            ref: A short branch name (e.g. ``"main"``).  Must NOT be
                fully-qualified (``refs/heads/…``).

        Returns:
            ``True`` when *ref* is protected; ``False`` when the hatch is active
            or *ref* is not in the protected set.
        """
        if self.mission_bypass_branch is not None and ref == self.mission_bypass_branch:
            return False
        return ref in self.protected_branches and not self.operator_hatch_active

    # ------------------------------------------------------------------
    # Mission-scoped hatch fold (#5100 FR-008, WP08 cycle 4)
    # ------------------------------------------------------------------

    def scoped_to_mission(self, meta: Mapping[str, Any] | None) -> ProtectionPolicy:
        """Return a copy that honours *meta*'s ``commit_to_target`` for its own target.

        ``commit_to_target: true`` is a MISSION-SCOPED operator hatch (C-002:
        the same hatch concept as ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``,
        no second mechanism and no new env var). It un-protects exactly the
        mission's own ``target_branch`` and only on the policy returned here;
        the receiver, other missions and non-mission commits stay protected.

        Fail-closed: a non-bool ``commit_to_target`` (see
        :func:`specify_cli.core.paths.read_commit_to_target`) or a missing
        ``target_branch`` yields NO bypass -- it refuses, never grants.
        """
        bypass = _mission_bypass_branch(meta)
        return self if bypass is None else replace(self, mission_bypass_branch=bypass)

    def for_mission(self, repo_root: Path, mission_slug: str | None) -> ProtectionPolicy:
        """Return this policy scoped to *mission_slug*'s persisted ``commit_to_target``.

        The single I/O step of the mission-scoped fold: loads the mission's
        primary ``meta.json`` (fail-closed) and delegates the decision to
        :meth:`scoped_to_mission`. A ``None``/unknown slug or an unreadable
        ``meta.json`` leaves the policy unchanged (protected).
        """
        if not mission_slug:
            return self
        meta = _load_mission_meta(repo_root, mission_slug)
        return self if meta is None else self.scoped_to_mission(meta)

    @classmethod
    def resolve_for_mission(cls, repo_root: Path, mission_slug: str | None) -> ProtectionPolicy:
        """:meth:`resolve` followed by :meth:`for_mission` -- the mission-write entry point."""
        return cls.resolve(repo_root).for_mission(repo_root, mission_slug)

    def is_protected_target(self, branch: str, *, primary_branch: str) -> bool:
        """Return ``True`` iff *branch* is protected under the #5100 rule.

        The #5100 operator decision (comment 5870360497, option E) defines a
        single_branch mission's "protected target" as **primary plus
        configured** — the repository's Primary Branch (``primary_branch``,
        e.g. the resolved default branch) counts as protected even when it is
        not itself named in ``.kittify/config.yaml``'s configured
        ``protected_branches`` list (or that list is empty/absent). This
        differs from :meth:`is_protected` alone in exactly the two ways
        ``research.md`` R-5 documents: an explicit configured list *replaces*
        the defaults, so a primary branch with a non-default name (e.g.
        ``trunk``) drops out of :attr:`protected_branches` the moment the
        operator configures ANY other list; and a primary branch with no
        ``origin/HEAD`` resolves unprotected under the plain defaults
        (:func:`_default_branches_with_remote` only adds ``{main, master}``
        plus the remote default, which is ``None`` with no ``origin/HEAD``).

        One query on the existing authority (C-002: no second protection
        check) closes both gaps: ``branch == primary_branch`` is checked
        FIRST and unconditionally (still gated by the operator hatch, so the
        escape hatch keeps working identically to :meth:`is_protected`), then
        falls back to the configured-set check for every other branch.

        Args:
            branch: The candidate target branch (short name, not
                ``refs/heads/…``).
            primary_branch: The repository's resolved Primary Branch name
                (e.g. from :func:`specify_cli.core.git_ops.resolve_primary_branch`).
                Required keyword — there is no default, so a caller cannot
                silently pass no primary and get the plain :meth:`is_protected`
                answer without naming it.

        Returns:
            ``True`` when *branch* is the primary branch or is in the
            configured protected set, and the operator hatch is not active.
        """
        if self.operator_hatch_active or (self.mission_bypass_branch is not None and branch == self.mission_bypass_branch):
            return False
        return branch == primary_branch or self.is_protected(branch)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mission_bypass_branch(meta: Mapping[str, Any] | None) -> str | None:
    """The mission's own ``target_branch`` iff ``commit_to_target`` is the JSON ``true``, else ``None``.

    Fail-closed: a non-bool ``commit_to_target`` (via the canonical
    :func:`specify_cli.core.paths.read_commit_to_target`) or a missing
    ``target_branch`` yields ``None`` -- refuse, never bypass.
    """
    from mission_runtime import MissionTopology

    from specify_cli.core.paths import CommitToTargetMetaError, read_commit_to_target
    from specify_cli.migration.backfill_topology import stored_topology

    # ``commit_to_target`` is single_branch-only: a hand-edited meta on any other
    # (or unstored) topology must never un-protect the target.
    if meta is None or stored_topology(meta) is not MissionTopology.SINGLE_BRANCH:
        return None
    try:
        opted_out = read_commit_to_target(dict(meta) if meta is not None else None)
    except CommitToTargetMetaError:
        logger.warning("meta.json commit_to_target is not a boolean; keeping the target protected (fail-closed).")
        return None
    target = (meta or {}).get("target_branch")
    return target if opted_out and isinstance(target, str) and target else None


def mission_write_bypass(repo_root: Path, mission_slug: str | None, branch: str) -> bool:
    """``True`` iff *branch* is *mission_slug*'s own ``commit_to_target`` target (#5100 FR-008).

    The mission-scoped hatch fold for call sites that ask a resolved
    ``ProtectionPolicy`` first and then consult this only for a would-be
    refusal (``policy.is_protected(b) and not mission_write_bypass(...)``).
    Same decision as :meth:`ProtectionPolicy.for_mission`; ``False`` for a
    ``None`` slug, unknown mission, unreadable meta or non-bool flag.
    """
    if not mission_slug:
        return False
    meta = _load_mission_meta(repo_root, mission_slug)
    return meta is not None and _mission_bypass_branch(meta) == branch


def _load_mission_meta(repo_root: Path, mission_slug: str) -> dict[str, Any] | None:
    """Load the mission's primary ``meta.json``; ``None`` when absent or unreadable."""
    from specify_cli.core.paths import MissionMetaReadError, get_main_repo_root, load_meta_fail_closed
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    try:
        main_root = get_main_repo_root(repo_root)
        feature_dir = _compose_primary_feature_dir(main_root, _canonicalize_primary_read_handle(main_root, mission_slug))
        return load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        logger.warning("mission meta.json unreadable for %s; keeping the target protected (fail-closed).", mission_slug)
        return None
    except MissionSelectorAmbiguous as exc:
        # An ambiguous selector must yield NO bypass, never raise out of
        # ``preflight_commit`` for every kitty-specs-only commit (fail closed).
        logger.warning("mission selector %s is ambiguous (%s); keeping the target protected (fail-closed).", mission_slug, exc)
        return None


def _resolve_hatch() -> bool:
    """Return ``True`` when the operator escape hatch env var is truthy."""
    return os.environ.get(_HATCH_ENV_VAR, "").lower() in ("1", "true", "yes")


def _load_kittify_config(repo_root: Path) -> dict:  # type: ignore[type-arg]
    """Load ``.kittify/config.yaml`` and return its parsed content.

    Returns an empty dict when the file does not exist (normal for non-SK
    repos or repos without a ``protection:`` block).

    Raises:
        ProtectionConfigError: The file fails to parse, or parses to a
            non-mapping top level (e.g. a bare scalar or a list). A YAML
            document need not be a mapping, and the unguarded ``.get(...)``
            calls in :func:`_resolve_protected_branches` raised a bare
            ``AttributeError`` on that shape (same defect class as ledger
            SK-16's ``charter status --json`` leak) -- fail-closed with a
            typed, message-carrying error instead, per this module's own
            documented "malformed value -> ``ProtectionConfigError``" contract.
    """
    config_file = repo_root / ".kittify" / "config.yaml"
    if not config_file.exists():
        return {}

    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        with open(config_file, encoding="utf-8") as fh:
            loaded = yaml.load(fh) or {}
    except Exception as exc:
        raise ProtectionConfigError(
            f"Failed to parse {config_file}: {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        raise ProtectionConfigError(
            f"{config_file} must be a YAML mapping at the top level; found "
            f"{type(loaded).__name__} instead."
        )

    return loaded


def _resolve_protected_branches(repo_root: Path) -> frozenset[str]:
    """Resolve the protected-branch set from ``.kittify`` config and git state.

    Implements the four-row resolution table from ``contracts/protection-config.md``.
    The remote-default augmentation is applied ONLY on the absent-key path.
    """
    data = _load_kittify_config(repo_root)
    protection_block = data.get("protection")

    if protection_block is None or not isinstance(protection_block, dict):
        # Key absent entirely → default {main, master} ∪ {remote default}
        return _default_branches_with_remote(repo_root)

    raw_value = protection_block.get("protected_branches")

    if raw_value is None:
        # ``protection:`` block exists but key is absent → treat as absent
        return _default_branches_with_remote(repo_root)

    if not isinstance(raw_value, list):
        raise ProtectionConfigError(
            f"protection.protected_branches in .kittify/config.yaml must be a list, "
            f"got {type(raw_value).__name__}: {raw_value!r}"
        )

    # Explicit list (possibly empty) → exactly that set; no remote union
    return frozenset(str(b) for b in raw_value)


def _default_branches_with_remote(repo_root: Path) -> frozenset[str]:
    """Return ``{main, master}`` augmented with the remote default branch.

    Preserves the byte-identical default behaviour of the pre-refactor
    ``protected_branches()`` function (NFR-004).
    """
    branches = set(_DEFAULT_PROTECTED_BRANCHES)
    remote_default = _remote_default_branch(repo_root)
    if remote_default:
        branches.add(remote_default)
    return frozenset(branches)


def _remote_default_branch(repo_root: Path) -> str | None:
    """Return the remote default branch name, or ``None`` if unavailable.

    Mirrors the logic in ``git/commit_helpers._remote_default_branch``; this
    copy is intentional so the resolver is self-contained (FR-007).
    """
    import subprocess  # local import keeps module-level deps minimal

    def _run(args: list[str]) -> str | None:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    symbolic_ref = _run(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if symbolic_ref and "/" in symbolic_ref:
        return symbolic_ref.rsplit("/", 1)[1]

    remote_show = _run(["remote", "show", "origin"])
    if remote_show:
        for line in remote_show.splitlines():
            if "HEAD branch:" in line:
                return line.rsplit(":", 1)[1].strip() or None
    return None
