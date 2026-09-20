"""Deterministic mission-state repair and TeamSpace dry-run helpers.

This module is the mutating counterpart to ``specify_cli.audit``.  The audit
package remains read-only; this module is only reached from
``doctor mission-state --fix`` or ``--teamspace-dry-run``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from specify_cli.status.dup_key_repair import ArtifactRepairPlan, DuplicateKeyFinding

from packaging.version import Version
from pydantic import BaseModel, ConfigDict

from specify_cli.core.atomic import atomic_write
from specify_cli.core.checkout_identity import (
    FailClosedRefusal,
    Intent,
    resolve_checkout_identity,
)
from specify_cli.core.paths import (
    WorkspaceRootNotFound,
    assert_safe_path_segment,
    load_meta_fail_closed,
    resolve_canonical_root,
)
from specify_cli.mission_metadata import (
    _normalize_change_mode,
    load_meta_or_empty,
    mission_number_from_slug,
    validate_meta,
    write_meta,
)
from specify_cli.migration.canonicalization import (
    CanonicalPipelineResult,
    CanonicalRule,
    CanonicalStepResult,
    MigrationContext,
    apply_rules,
)
from specify_cli.status import ULID_PATTERN, Lane, StatusEvent
from specify_cli.status import materialize_snapshot, materialize_to_json
from specify_cli.status import (
    ANNOTATION_KIND,
    LIFECYCLE_EVENT_TYPES,
    is_retrospective_lifecycle_event,
)

MIGRATION_SCHEMA_VERSION = "1.0.0"
CANONICAL_ENVELOPE_SCHEMA_VERSION = "3.0.0"
REQUIRED_EVENTS_PACKAGE = Version("5.0.0")

EVENTS_FILENAME = "status.events.jsonl"
STATUS_FILENAME = "status.json"
META_FILENAME = "meta.json"
MANIFEST_ROOT = Path(".kittify/migrations/mission-state")

# ---------------------------------------------------------------------------
# Repair manifest file-classification policy (Mission 8, #930)
# ---------------------------------------------------------------------------

# Glob-style patterns describing which paths the repair walks and mutates.
_POLICY_TRACKED: tuple[str, ...] = (
    "kitty-specs/*/meta.json",
    "kitty-specs/*/status.events.jsonl",
    "kitty-specs/*/status.json",
    ".kittify/migrations/mission-state/*.json",
)
# Patterns the repair will repair only when present (no-op when absent).
_POLICY_OPTIONAL: tuple[str, ...] = ("kitty-specs/*/status.json",)
# Patterns the repair never touches.
_POLICY_IGNORED: tuple[str, ...] = (
    ".git/",
    ".worktrees/",
    "__pycache__/",
    "*.pyc",
)


def _build_policy() -> dict[str, list[str]]:
    """Return the manifest ``policy`` block with sorted, deterministic lists."""
    return {
        "tracked": sorted(_POLICY_TRACKED),
        "optional": sorted(_POLICY_OPTIONAL),
        "ignored": sorted(_POLICY_IGNORED),
    }


# ---------------------------------------------------------------------------
# Secret-scrub helper for repair manifest ``command_args`` (Mission 8, #930)
# ---------------------------------------------------------------------------

# Long-form CLI flags whose value can be a secret. The redaction logic
# accepts either ``--flag VALUE`` (two argv slots) or ``--flag=VALUE``
# (one argv slot). Matching is case-insensitive (compare via .lower()).
#
# NOTE: ``--client-id`` is intentionally NOT in this set. Client IDs are
# public identifiers (OAuth2 spec treats them as non-secret); the
# corresponding ``--client-secret`` belongs here instead.
_SECRET_FLAG_NAMES: frozenset[str] = frozenset(
    {
        "--token",
        "--auth",
        "--password",
        "--secret",
        "--api-key",
        "--bearer",
        # Expanded coverage (PR #1031 follow-up): real-world secret-flag
        # shapes that the original WP02 helper missed.
        "--access-token",
        "--refresh-token",
        "--id-token",
        "--client-secret",
        "--private-key",
        "--ssh-key",
        "--aws-secret-access-key",
        "--gh-token",
    }
)

# Regex set used to redact standalone argv items. Each pattern matches a
# string that is *probably* a secret on its own (i.e. without an explicit
# ``--flag`` carrier).
_GITHUB_TOKEN_RE = re.compile(r"^gh[pousr]_[A-Za-z0-9_]{34,}$")
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}$")
_BEARER_RE = re.compile(r"^Bearer\s+\S{16,}$", re.IGNORECASE)

# Env-var-style argv item: ``NAME=VALUE`` where NAME is an UPPER_SNAKE
# identifier ending in a sensitive suffix (TOKEN / SECRET / KEY /
# PASSWORD / PASSPHRASE). Matches e.g. ``SPEC_KITTY_TOKEN=foo``,
# ``GITHUB_TOKEN=bar``, ``OPENAI_API_KEY=...``. The name is preserved
# so reviewers know what was passed; only the value is redacted.
_ENV_VAR_SECRET_RE = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD|PASSPHRASE))=(?P<value>.+)$")

_REDACTED = "<redacted>"


def _looks_like_slack_token(value: str) -> bool:
    """Return True for Slack token shapes without regex backtracking risk."""
    prefixes = ("xoxb-", "xoxp-", "xoxa-", "xoxr-", "xoxs-")
    if not value.startswith(prefixes):
        return False
    parts = value.split("-")
    if len(parts) < 3 or any(not part for part in parts):
        return False
    return all(all(ch.isalnum() for ch in part) for part in parts)


def _looks_like_authorization_header(value: str) -> bool:
    """Return True for ``Authorization: <value>`` headers in argv."""
    name, sep, remainder = value.partition(":")
    return sep == ":" and name.strip().lower() == "authorization" and bool(remainder.strip())


def _is_standalone_secret_item(value: str) -> bool:
    """Return True when *value* matches any standalone secret shape."""
    return (
        _GITHUB_TOKEN_RE.match(value) is not None
        or _looks_like_slack_token(value)
        or _JWT_RE.match(value) is not None
        or _looks_like_authorization_header(value)
        or _BEARER_RE.match(value) is not None
    )


def _scrub_secret_args(argv: Sequence[str]) -> list[str]:
    """Return a copy of *argv* with secret-bearing values replaced by ``<redacted>``.

    Behaviour (see Priivacy-ai/spec-kitty#930 and the PR #1031 follow-up):

    - For each sensitive long-form flag in ``_SECRET_FLAG_NAMES`` (matched
      case-insensitively), ``--flag VALUE`` becomes
      ``["--flag", "<redacted>"]`` and ``--flag=VALUE`` becomes
      ``"--flag=<redacted>"``. The flag name itself is preserved (in its
      original casing) so reviewers can still tell which option was passed.
    - Env-var-style argv items shaped like ``NAME=VALUE`` where NAME is an
      UPPER_SNAKE identifier ending in TOKEN / SECRET / KEY / PASSWORD /
      PASSPHRASE become ``"NAME=<redacted>"``. Non-secret env-style items
      like ``GITHUB_USERNAME=robert`` pass through unchanged.
    - Standalone argv items that match any pattern in
      ``_STANDALONE_SECRET_RES`` (GitHub tokens, Slack tokens, JWT-shaped
      strings, ``Authorization:`` headers, bare ``Bearer …`` tokens) are
      replaced wholesale.
    - Everything else passes through unchanged.

    The function is pure: same input list always returns an equal output
    list, with no side effects on logging or external state.
    """
    result: list[str] = []
    i = 0
    while i < len(argv):
        item = argv[i]
        # --flag=VALUE form (case-insensitive flag match)
        if "=" in item and item.startswith("--"):
            flag, _, _value = item.partition("=")
            if flag.lower() in _SECRET_FLAG_NAMES:
                result.append(f"{flag}={_REDACTED}")
                i += 1
                continue
        # --flag VALUE form (consumes the next argv slot)
        if item.startswith("--") and item.lower() in _SECRET_FLAG_NAMES and i + 1 < len(argv):
            result.append(item)
            result.append(_REDACTED)
            i += 2
            continue
        # Env-var-style ``NAME=VALUE`` with secret-shaped NAME
        env_match = _ENV_VAR_SECRET_RE.match(item)
        if env_match is not None:
            result.append(f"{env_match.group('name')}={_REDACTED}")
            i += 1
            continue
        # Standalone secret-shaped item
        if _is_standalone_secret_item(item):
            result.append(_REDACTED)
            i += 1
            continue
        result.append(item)
        i += 1
    return result


def _resolve_cli_version() -> str:
    """Return the installed ``spec-kitty-cli`` version, or ``"unknown"``."""
    try:
        return importlib.metadata.version("spec-kitty-cli")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


FORBIDDEN_LEGACY_KEYS = frozenset(
    {
        "feature_slug",
        "feature_number",
        "mission_key",
        "legacy_aggregate_id",
    }
)
STATUS_ROW_ALIASES = {
    "feature_slug": "mission_slug",
    "work_package_id": "wp_id",
}
META_LEGACY_ALIASES = frozenset({"feature_slug", "feature_number", "mission_key", "legacy_aggregate_id", "mission"})
LANE_ALIASES = {"doing": "in_progress"}
VALID_LANES = frozenset(lane.value for lane in Lane)
VALID_EXECUTION_MODES = frozenset({"worktree", "direct_repo"})

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ACTOR_SAFE = re.compile(r"[^a-z0-9_.:-]+")
_MISSION_PREFIX_RE = re.compile(r"^(\d{3})-")
_MID8_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
_UUID_HYPHEN_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_UUID_BARE_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_REMOTE_URL_SCHEMES = frozenset({"http", "https"})


class MissionStateRepairError(RuntimeError):
    """Raised when mission-state repair cannot proceed safely."""


class MissionStateDryRunError(RuntimeError):
    """Raised when TeamSpace dry-run validation cannot proceed."""


@dataclass(frozen=True)
class FileChange:
    """Digest evidence for a file touched by the repair."""

    path: str
    old_sha256: str | None
    new_sha256: str | None
    old_size: int | None
    new_size: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "old_sha256": self.old_sha256,
            "new_sha256": self.new_sha256,
            "old_size": self.old_size,
            "new_size": self.new_size,
        }


@dataclass(frozen=True)
class RowTransformation:
    """Audit evidence for one status.events.jsonl row transformation."""

    artifact_path: str
    line_number: int
    event_id: str | None
    actions: tuple[str, ...]
    old_sha256: str
    new_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_path": self.artifact_path,
            "line_number": self.line_number,
            "event_id": self.event_id,
            "actions": list(self.actions),
            "old_sha256": self.old_sha256,
            "new_sha256": self.new_sha256,
        }


@dataclass
class MissionRepairResult:
    """Repair result for a single mission directory."""

    mission_slug: str
    mission_id: str | None
    status: Literal["updated", "unchanged", "error"]
    file_changes: list[FileChange] = field(default_factory=list)
    row_transformations: list[RowTransformation] = field(default_factory=list)
    quarantined_rows: int = 0
    validation_errors: list[str] = field(default_factory=list)
    meta_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_slug": self.mission_slug,
            "mission_id": self.mission_id,
            "status": self.status,
            "file_changes": [change.to_dict() for change in self.file_changes],
            "row_transformations": [row.to_dict() for row in self.row_transformations],
            "quarantined_rows": self.quarantined_rows,
            "validation_errors": list(self.validation_errors),
            "meta_actions": list(self.meta_actions),
        }


@dataclass
class RepairReport:
    """Top-level repair manifest.

    Mission 8 (Priivacy-ai/spec-kitty#930) added the ``cli_version``,
    ``command_args``, ``generated_ids``, and ``policy`` fields so a
    reviewer can explain a migration commit from the manifest alone.
    """

    run_id: str
    repo_head: str | None
    target_missions: list[str]
    manifest_path: str
    missions: list[MissionRepairResult]
    schema_version: str = MIGRATION_SCHEMA_VERSION
    cli_version: str = "unknown"
    command_args: list[str] = field(default_factory=list)
    generated_ids: list[str] = field(default_factory=list)
    policy: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "repo_head": self.repo_head,
            "target_missions": list(self.target_missions),
            "manifest_path": self.manifest_path,
            "cli_version": self.cli_version,
            "command_args": list(self.command_args),
            "generated_ids": list(self.generated_ids),
            "policy": {key: list(value) for key, value in self.policy.items()},
            "summary": {
                "missions_total": len(self.missions),
                "missions_updated": sum(1 for m in self.missions if m.status == "updated"),
                "missions_unchanged": sum(1 for m in self.missions if m.status == "unchanged"),
                "missions_error": sum(1 for m in self.missions if m.status == "error"),
                "quarantined_rows": sum(m.quarantined_rows for m in self.missions),
            },
            "missions": [mission.to_dict() for mission in self.missions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class TeamspaceDryRunRowMapping:
    """Mapping from one local status row to its synthesized TeamSpace event."""

    mission_slug: str
    artifact_path: str
    line_number: int | None
    source_event_id: str
    synthesized_event_id: str
    synthesized_event_type: str
    aggregate_id: str
    row_sha256: str | None
    envelope_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_slug": self.mission_slug,
            "artifact_path": self.artifact_path,
            "line_number": self.line_number,
            "source_event_id": self.source_event_id,
            "synthesized_event_id": self.synthesized_event_id,
            "synthesized_event_type": self.synthesized_event_type,
            "aggregate_id": self.aggregate_id,
            "row_sha256": self.row_sha256,
            "envelope_sha256": self.envelope_sha256,
        }


@dataclass(frozen=True)
class TeamspaceDryRunReport:
    """Validation report for canonical envelopes synthesized from local state."""

    schema_version: str
    events_package_version: str
    envelope_count: int
    valid: bool
    errors: tuple[dict[str, object], ...]
    row_mappings: tuple[TeamspaceDryRunRowMapping, ...] = ()
    context_warnings: tuple[dict[str, object], ...] = ()
    side_logs: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "events_package_version": self.events_package_version,
            "envelope_count": self.envelope_count,
            "valid": self.valid,
            "errors": list(self.errors),
            "row_mappings": [mapping.to_dict() for mapping in self.row_mappings],
            "context_warnings": list(self.context_warnings),
            "side_logs": list(self.side_logs),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class _RawJsonlRow:
    line_number: int
    text: str
    data: dict[str, Any]


@dataclass(frozen=True)
class _CanonicalRowResult:
    row: dict[str, Any] | None
    actions: tuple[str, ...]
    error: str | None = None

    @classmethod
    def from_pipeline(cls, result: CanonicalPipelineResult[dict[str, Any]]) -> _CanonicalRowResult:
        """Adapt a generic pipeline result to the existing _CanonicalRowResult shape."""
        return cls(
            row=result.state if result.error is None else None,
            actions=result.actions,
            error=result.error,
        )


def deterministic_ulid(seed: bytes | str) -> str:
    """Return a deterministic 26-char Crockford identifier from *seed*."""
    raw = seed.encode("utf-8") if isinstance(seed, str) else seed
    value = int.from_bytes(hashlib.sha256(raw).digest()[:16], "big")  # noqa: TID251 - production raw SHA-256 owner
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def envelope_sha256(envelope: Mapping[str, Any]) -> str:
    """Canonical-JSON SHA-256 of a TeamSpace envelope (single recipe owner).

    The migration dry-run's ``TeamspaceDryRunRowMapping.envelope_sha256`` hashes
    envelopes with this exact shape; hoisted here so callers cannot drift
    (#2884). (The import-history provenance manifest's own use of this recipe,
    #2262, was removed with the sync transport -- issue #5 -- and its
    re-export seam, ``migration.envelope_seam``, was pruned as dead collateral
    -- issue #116.)
    """
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()  # noqa: TID251 - production raw SHA-256 owner (canonical envelope body checksum)


def _anchor_repair_root(repo_root: Path, *, scan_root: Path | None) -> Path:
    """Re-anchor the invocation root to the canonical PRIMARY main-checkout.

    ``doctor mission-state --fix`` is a repo-level canonicalization whose write
    target is the *primary* checkout's ``kitty-specs/<slug>`` — the durable
    per-mission status home for flattened / merged missions (those carrying no
    live ``coordination_branch``). When the CLI is invoked from inside a
    worktree (a coordination or lane worktree), the raw invocation root points
    at that worktree, so the repair would land there instead: it (a) leaves the
    primary ``status.json`` stale, so an ``--audit`` re-run still reports
    ``SNAPSHOT_DRIFT`` (the materialize step ran against the wrong checkout),
    and (b) writes uncommitted changes into a possibly-stale coordination
    worktree — both symptoms of issue #2320.

    Route through the single canonical worktree-pointer parser
    (:func:`specify_cli.core.paths.resolve_canonical_root`) so repair always
    operates on the primary checkout regardless of CWD.

    ``scan_root`` (``--fixture-dir`` / packaged-fixtures mode) is a deliberate
    override that points discovery at an arbitrary directory tree; re-anchoring
    would drag the manifest/quarantine roots onto an enclosing real repo, so in
    that mode the resolved input is honored verbatim. When no enclosing git repo
    is found (ad-hoc test fixtures outside a git tree) the resolved input is also
    returned unchanged, preserving the prior no-git behavior.
    """
    if scan_root is not None:
        return repo_root.resolve()
    try:
        canonical: Path = resolve_canonical_root(repo_root)
    except WorkspaceRootNotFound:
        return repo_root.resolve()
    return canonical


# ---------------------------------------------------------------------------
# Checkout-identity reconciliation (WP04, FR-004; #3051/#3541)
#
# ``_anchor_repair_root`` above **deliberately** keeps the #2320 primary
# status-home: a ``--fix`` write always lands on the primary checkout's
# ``kitty-specs/<slug>`` regardless of CWD. That canonicalization is correct —
# but when it is triggered from a *foreign* lane worktree it must not happen
# **silently**. The squad surfaced the tension (#3129/#3051): the same
# collapse-to-primary is both the deliberate #2320 anchor AND, when unannounced,
# a defect. Resolution: preserve the primary target, add checkout-identity
# awareness so a foreign-lane ``--fix`` fails closed, and an ``--audit`` reports
# the honest invoking-checkout-vs-primary disagreement rather than a false-green
# produced by reading the redirected primary path at both ends.
# ---------------------------------------------------------------------------


class MissionStateWriteRefused(MissionStateRepairError):
    """Fail-closed refusal of a foreign-lane ``--fix`` canonicalization.

    Carries the WP01 :class:`FailClosedRefusal` value object (the single
    write-refusal seam). ``str(exc)`` is ``refusal.message()``, which names the
    primary ``canonical_target`` verbatim, so the operator sees exactly which
    checkout the invocation declined to canonicalize.
    """

    def __init__(self, refusal: FailClosedRefusal) -> None:
        super().__init__(refusal.message())
        self.refusal = refusal


def enforce_primary_write_ownership(cwd: Path, resolved_root: Path) -> None:
    """Fail closed when a foreign lane would silently canonicalize the primary.

    ``resolved_root`` is the already-re-anchored ``--fix`` write target (the
    #2320 primary). Consulting the WP01 guard with :data:`Intent.WRITE`:

    * When the guard's ``canonical_target`` differs from ``resolved_root`` the
      invocation is writing to a checkout it owns (or to an explicitly supplied
      root that is *not* this invocation's re-anchored primary) — proceed
      silently. This keeps owner ``--fix`` and explicit ``repo_root=`` callers
      (tests, fixtures) unaffected.
    * When ``canonical_target == resolved_root`` **and** the invoking checkout
      does not own it (a foreign lane worktree pointing at that primary), raise
      :class:`MissionStateWriteRefused` naming the primary — never a silent
      canonicalization.

    An owner invocation (``cwd`` *is* the primary) has ``is_owner`` true, so
    :meth:`CheckoutIdentity.write_refusal` returns ``None`` and this is a no-op.
    """
    identity = resolve_checkout_identity(cwd, Intent.WRITE)
    if identity.canonical_target != resolved_root:
        return
    refusal = identity.write_refusal()
    if refusal is not None:
        raise MissionStateWriteRefused(refusal)


@dataclass(frozen=True)
class CheckoutDisagreement:
    """One honest invoking-checkout-vs-primary mission-state mismatch.

    ``invoking_sha256`` / ``primary_sha256`` are the SHA-256 of the artifact in
    the invoking checkout and the primary respectively; ``None`` means the
    artifact is absent on that side. A row exists only when the two differ, so a
    populated list is exactly the disagreement an ``--audit`` from a foreign lane
    must surface instead of a false-green.
    """

    mission_slug: str
    artifact: str
    invoking_sha256: str | None
    primary_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_slug": self.mission_slug,
            "artifact": self.artifact,
            "invoking_sha256": self.invoking_sha256,
            "primary_sha256": self.primary_sha256,
        }


_DISAGREEMENT_ARTIFACTS: tuple[str, ...] = (STATUS_FILENAME, EVENTS_FILENAME)


def _artifact_sha256(path: Path) -> str | None:
    """SHA-256 of ``path``'s bytes, or ``None`` when it is absent/unreadable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 - content-identity checksum only


def _compare_checkout_mission_state(invoking_root: Path, primary_root: Path, *, mission: str | None) -> list[CheckoutDisagreement]:
    """Return the honest per-artifact mismatches between two checkouts.

    Compares ``kitty-specs/<slug>/status.json`` and ``status.events.jsonl`` in
    the invoking checkout against the primary. A disagreement is recorded when
    the two sides' content SHA differs (including one side being absent).
    """
    invoking_specs = invoking_root / "kitty-specs"
    primary_specs = primary_root / "kitty-specs"
    slugs: set[str] = set()
    for specs_root in (invoking_specs, primary_specs):
        if specs_root.is_dir():
            slugs.update(p.name for p in specs_root.iterdir() if p.is_dir())
    if mission is not None:
        slugs &= {mission}

    disagreements: list[CheckoutDisagreement] = []
    for slug in sorted(slugs):
        for artifact in _DISAGREEMENT_ARTIFACTS:
            invoking_sha = _artifact_sha256(invoking_specs / slug / artifact)
            primary_sha = _artifact_sha256(primary_specs / slug / artifact)
            if invoking_sha != primary_sha:
                disagreements.append(
                    CheckoutDisagreement(
                        mission_slug=slug,
                        artifact=artifact,
                        invoking_sha256=invoking_sha,
                        primary_sha256=primary_sha,
                    )
                )
    return disagreements


def audit_invocation_disagreement(cwd: Path, resolved_root: Path, *, mission: str | None = None) -> list[CheckoutDisagreement]:
    """Report the invoking-checkout-vs-primary disagreement for ``--audit``.

    The false-green this removes: from a foreign lane the audit root is
    re-anchored to the primary, so the engine reads the primary at *both* ends
    and reports agreement. Here the invoking checkout is resolved **directly**
    from its own ``.git`` via the WP01 guard (:data:`Intent.PRIMARY_READ`, which
    never flips the target) and its own mission state is compared against the
    primary ``resolved_root``.

    Returns ``[]`` when the invoking checkout *is* the primary (``resolved_root``
    == ``invoking_root``) or when ``resolved_root`` is not this invocation's
    re-anchored primary (explicit-root / fixture callers) — there is no
    cross-checkout read to disagree about in those cases.
    """
    identity = resolve_checkout_identity(cwd, Intent.PRIMARY_READ)
    if identity.invoking_root == resolved_root:
        return []
    if identity.canonical_target != resolved_root:
        return []
    return _compare_checkout_mission_state(identity.invoking_root, resolved_root, mission=mission)


def repair_repo(
    repo_root: Path,
    *,
    scan_root: Path | None = None,
    mission: str | None = None,
    manifest_path: Path | None = None,
    allow_dirty: bool = False,
) -> RepairReport:
    """Canonicalize historical mission state on disk and write a manifest."""
    resolved_repo_root = _anchor_repair_root(repo_root, scan_root=scan_root)
    # Self-protecting guard (#3567 landing-pass coherence fold): every caller of
    # ``repair_repo`` -- the CLI shell's ``_refuse_foreign_lane_fix`` (an earlier,
    # formatted duplicate of this same check) and the TeamSpace gate
    # (``_teamspace_mission_state_gate.py``, previously ungated) -- must fail
    # closed on a foreign-lane invocation instead of silently canonicalizing the
    # primary. No-ops for owner invocations and explicit-root-from-non-lane-cwd
    # callers (tests/fixtures); see ``enforce_primary_write_ownership``.
    enforce_primary_write_ownership(Path.cwd(), resolved_repo_root)
    mission_dirs = _select_mission_dirs(resolved_repo_root, scan_root=scan_root, mission=mission)
    if not mission_dirs:
        raise MissionStateRepairError("No mission directories found to repair.")

    run_id = _compute_run_id(resolved_repo_root, mission_dirs)
    manifest_rel = manifest_path or MANIFEST_ROOT / f"{run_id}.json"
    manifest_abs = _resolve_repo_relative(resolved_repo_root, manifest_rel)
    relevant_paths = [_repo_relpath(resolved_repo_root, path) for path in mission_dirs]
    relevant_paths.append(str(MANIFEST_ROOT))

    _assert_git_safe(resolved_repo_root, relevant_paths, allow_dirty=allow_dirty)
    with _git_lock(resolved_repo_root):
        results: list[MissionRepairResult] = []
        # Mission 8 (#930): collect every deterministic ID minted during
        # the run so the manifest can list them all under ``generated_ids``.
        generated_ids: list[str] = [run_id]
        for mission_dir in mission_dirs:
            results.append(
                _repair_mission(
                    resolved_repo_root,
                    mission_dir,
                    run_id=run_id,
                    generated_ids=generated_ids,
                )
            )

        # Mission 8 (#930): scrub argv before persisting it into the manifest.
        try:
            raw_args = list(sys.argv[1:])
        except Exception:  # pragma: no cover - defensive
            raw_args = []
        command_args = _scrub_secret_args(raw_args)

        report = RepairReport(
            run_id=run_id,
            repo_head=_git_head(resolved_repo_root),
            target_missions=[p.name for p in mission_dirs],
            manifest_path=_repo_relpath(resolved_repo_root, manifest_abs),
            missions=results,
            cli_version=_resolve_cli_version(),
            command_args=command_args,
            generated_ids=sorted(set(generated_ids)),
            policy=_build_policy(),
        )
        atomic_write(manifest_abs, report.to_json(), mkdir=True)
        return report


# ---------------------------------------------------------------------------
# Duplicate-key artifact repair (FR-008, #3372)
#
# Legacy dual-key ``review_feedback`` artifacts (an empty ``''`` write followed
# by a real ``review-cycle://`` pointer) are invalid YAML that fails closed at
# the frontmatter boundary and trips an upgrade. This heals them BEFORE upgrade,
# reusing this module's ADR 2026-05-10-1 repair framework (git-safety preflight,
# run lock, ``atomic_write``, ``FileChange`` / ``RepairReport`` evidence). The
# detector is the raw-text scanner in ``specify_cli.status.dup_key_repair`` (the
# boundary cannot parse a dup-key file to detect it).
# ---------------------------------------------------------------------------

_DUP_KEY_MANIFEST_PREFIX = "dup-key-"
_DUP_KEY_POLICY_TRACKED: tuple[str, ...] = ("kitty-specs/**/*.md",)


def _build_dup_key_policy() -> dict[str, list[str]]:
    """Return the dup-key repair manifest ``policy`` block (deterministic)."""
    return {
        "tracked": sorted(_DUP_KEY_POLICY_TRACKED),
        "optional": [],
        "ignored": sorted(_POLICY_IGNORED),
    }


def _dup_key_scan_dir(resolved_repo_root: Path, scan_root: Path | None) -> Path:
    """Resolve the directory tree scanned for dual-key artifacts."""
    return (scan_root or resolved_repo_root / "kitty-specs").resolve()


def _plan_duplicate_key_batch(
    findings: Sequence[DuplicateKeyFinding],
) -> list[ArtifactRepairPlan]:
    """Plan + validate EVERY affected artifact before any write (NFR-004).

    One un-repairable artifact raises ``DuplicateKeyRepairError`` here, before
    the caller has mutated a single file — the batch-atomic abort.
    """
    from specify_cli.status import plan_artifact_repair

    plans: list[ArtifactRepairPlan] = []
    seen: set[Path] = set()
    for finding in findings:
        if finding.path in seen:
            continue
        seen.add(finding.path)
        plan = plan_artifact_repair(finding.path, finding.path.read_text(encoding="utf-8"))
        if plan is not None:
            plans.append(plan)
    return plans


def _dup_key_mission_slug(scan_dir: Path, path: Path) -> str:
    """Best-effort mission slug for report grouping (first path segment)."""
    try:
        rel = path.resolve().relative_to(scan_dir)
    except ValueError:
        return path.parent.name
    return rel.parts[0] if len(rel.parts) > 1 else path.name


def _compute_dup_key_run_id(repo_root: Path, plans: Sequence[ArtifactRepairPlan]) -> str:
    """Deterministic run id derived from the repaired-content set."""
    payload = "spec-kitty:dup-key-repair:v1\n"
    for plan in sorted(plans, key=lambda item: str(item.path)):
        payload += _repo_relpath(repo_root, plan.path) + "\0" + plan.repaired_text + "\0"
    return _sha256_text(payload)[:16]


def _write_duplicate_key_plans(repo_root: Path, plans: Sequence[ArtifactRepairPlan]) -> list[FileChange]:
    """Write every validated plan atomically, returning digest evidence."""
    changes: list[FileChange] = []
    for plan in plans:
        before = _file_fingerprint(plan.path)
        atomic_write(plan.path, plan.repaired_text)
        after = _file_fingerprint(plan.path)
        if before != after:
            changes.append(_file_change(repo_root, plan.path, before, after))
    return changes


def _safe_argv() -> list[str]:
    try:
        return list(sys.argv[1:])
    except Exception:  # pragma: no cover - defensive
        return []


def _build_dup_key_report(
    repo_root: Path,
    scan_dir: Path,
    run_id: str,
    plans: Sequence[ArtifactRepairPlan],
    file_changes: Sequence[FileChange],
    manifest_abs: Path,
) -> RepairReport:
    """Assemble the shared :class:`RepairReport` grouped by mission slug."""
    changes_by_path = {change.path: change for change in file_changes}
    grouped: dict[str, MissionRepairResult] = {}
    for plan in plans:
        slug = _dup_key_mission_slug(scan_dir, plan.path)
        result = grouped.setdefault(
            slug,
            MissionRepairResult(mission_slug=slug, mission_id=None, status="unchanged"),
        )
        change = changes_by_path.get(_repo_relpath(repo_root, plan.path))
        if change is not None:
            result.file_changes.append(change)
            result.status = "updated"
    return RepairReport(
        run_id=run_id,
        repo_head=_git_head(repo_root),
        target_missions=sorted(grouped),
        manifest_path=_repo_relpath(repo_root, manifest_abs),
        missions=[grouped[slug] for slug in sorted(grouped)],
        cli_version=_resolve_cli_version(),
        command_args=_scrub_secret_args(_safe_argv()),
        generated_ids=[run_id],
        policy=_build_dup_key_policy(),
    )


def repair_duplicate_key_artifacts(
    repo_root: Path,
    *,
    scan_root: Path | None = None,
    manifest_path: Path | None = None,
    allow_dirty: bool = False,
) -> RepairReport:
    """Heal legacy dual-key ``review_feedback`` artifacts (FR-008, #3372).

    BATCH-ATOMIC (NFR-004): every artifact's repair is planned and validated
    before ANY file is written; a single un-repairable artifact raises
    ``DuplicateKeyRepairError`` and the corpus is left untouched. NON-DESTRUCTIVE
    (NFR-002): the keep-last-non-empty policy preserves the recorded pointer.
    Opt-in — reached only from ``doctor mission-state --fix`` (``doctor`` itself
    is unconditionally SAFE).
    """
    from specify_cli.status import detect_duplicate_key_artifacts

    resolved_repo_root = _anchor_repair_root(repo_root, scan_root=scan_root)
    scan_dir = _dup_key_scan_dir(resolved_repo_root, scan_root)

    # Detect + plan + validate the entire batch BEFORE taking the lock or
    # writing anything (NFR-004 batch-atomicity). Any un-repairable artifact
    # raises out of the planner here, so nothing on disk is touched.
    plans = _plan_duplicate_key_batch(detect_duplicate_key_artifacts(scan_dir))
    run_id = _compute_dup_key_run_id(resolved_repo_root, plans)
    manifest_rel = manifest_path or MANIFEST_ROOT / f"{_DUP_KEY_MANIFEST_PREFIX}{run_id}.json"
    manifest_abs = _resolve_repo_relative(resolved_repo_root, manifest_rel)

    rel_paths = [_repo_relpath(resolved_repo_root, plan.path) for plan in plans]
    _assert_git_safe(resolved_repo_root, [*rel_paths, str(MANIFEST_ROOT)], allow_dirty=allow_dirty)
    with _git_lock(resolved_repo_root):
        file_changes = _write_duplicate_key_plans(resolved_repo_root, plans)
        report = _build_dup_key_report(resolved_repo_root, scan_dir, run_id, plans, file_changes, manifest_abs)
        if file_changes:
            atomic_write(manifest_abs, report.to_json(), mkdir=True)
        return report


def teamspace_dry_run(
    repo_root: Path,
    *,
    scan_root: Path | None = None,
    mission: str | None = None,
) -> TeamspaceDryRunReport:
    """Synthesize TeamSpace envelopes from local status logs and validate them."""
    event_cls, validate_event, package_version = _load_events_contract()
    mission_dirs = _select_mission_dirs(repo_root.resolve(), scan_root=scan_root, mission=mission)
    audit_errors = _teamspace_audit_blockers(repo_root.resolve(), scan_root=scan_root, mission_dirs=mission_dirs)
    audit_errors = [error for error in audit_errors if not _is_nonfatal_side_log_record(error)]
    if audit_errors:
        return TeamspaceDryRunReport(
            schema_version=CANONICAL_ENVELOPE_SCHEMA_VERSION,
            events_package_version=package_version,
            envelope_count=0,
            valid=False,
            errors=tuple(audit_errors),
            side_logs=tuple(side_log for mission_dir in mission_dirs for side_log in _classify_side_logs(repo_root.resolve(), mission_dir)),
        )
    project_uuid = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "spec-kitty:teamspace-dry-run:" + "|".join(path.name for path in mission_dirs),
    )
    errors: list[dict[str, object]] = []
    side_logs: list[dict[str, object]] = []
    count = 0
    repo_slug = _repo_slug(repo_root.resolve())
    project_slug = repo_slug or repo_root.resolve().name
    row_mappings: list[TeamspaceDryRunRowMapping] = []
    context_warnings = _teamspace_context_warnings(repo_root.resolve(), project_uuid)

    from specify_cli.status import read_events

    for mission_dir in mission_dirs:
        side_logs.extend(_classify_side_logs(repo_root.resolve(), mission_dir))
        raw_status_errors = _scan_raw_status_rows(repo_root.resolve(), mission_dir)
        errors.extend(raw_status_errors)
        if raw_status_errors:
            continue
        row_locations = _status_row_locations(mission_dir)
        try:
            events = read_events(mission_dir)
        except Exception as exc:
            errors.append(
                {
                    "mission_slug": mission_dir.name,
                    "error": "STATUS_EVENTS_UNREADABLE",
                    "message": str(exc),
                }
            )
            continue
        for index, status_event in enumerate(sorted(events, key=lambda e: (e.at, e.event_id)), start=1):
            count += 1
            envelope = _status_event_to_teamspace_envelope(
                status_event,
                project_uuid=project_uuid,
                lamport_clock=index,
                project_slug=project_slug,
                repo_slug=repo_slug,
            )
            row_location = row_locations.get(status_event.event_id)
            row_mappings.append(
                TeamspaceDryRunRowMapping(
                    mission_slug=status_event.mission_slug,
                    artifact_path=_repo_relpath(repo_root.resolve(), mission_dir / EVENTS_FILENAME),
                    line_number=row_location.line_number if row_location is not None else None,
                    source_event_id=status_event.event_id,
                    synthesized_event_id=envelope["event_id"],
                    synthesized_event_type=envelope["event_type"],
                    aggregate_id=envelope["aggregate_id"],
                    row_sha256=(
                        hashlib.sha256(row_location.text.encode("utf-8")).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
                        if row_location is not None
                        else None
                    ),
                    envelope_sha256=envelope_sha256(envelope),
                )
            )
            try:
                event_cls.model_validate(envelope)
            except Exception as exc:
                errors.append(
                    {
                        "mission_slug": status_event.mission_slug,
                        "event_id": status_event.event_id,
                        "error": "ENVELOPE_INVALID",
                        "message": str(exc),
                    }
                )
                continue
            payload_result = validate_event(envelope["payload"], envelope["event_type"])
            if not payload_result.valid:
                errors.append(
                    {
                        "mission_slug": status_event.mission_slug,
                        "event_id": status_event.event_id,
                        "error": "PAYLOAD_INVALID",
                        "model_violations": [
                            {
                                "field": v.field,
                                "message": v.message,
                                "violation_type": v.violation_type,
                            }
                            for v in payload_result.model_violations
                        ],
                    }
                )

    fatal_errors = [error for error in errors if not _is_nonfatal_side_log_record(error)]
    return TeamspaceDryRunReport(
        schema_version=CANONICAL_ENVELOPE_SCHEMA_VERSION,
        events_package_version=package_version,
        envelope_count=count,
        valid=not fatal_errors,
        errors=tuple(fatal_errors),
        row_mappings=tuple(row_mappings),
        context_warnings=tuple(context_warnings),
        side_logs=tuple(side_logs),
    )


def _teamspace_audit_blockers(
    repo_root: Path,
    *,
    scan_root: Path | None,
    mission_dirs: Sequence[Path],
) -> list[dict[str, object]]:
    """Return audit findings that must block TeamSpace historical import."""
    from specify_cli.audit import AuditOptions, run_audit
    from specify_cli.audit.models import is_teamspace_blocker

    report = run_audit(AuditOptions(repo_root=repo_root, scan_root=scan_root))
    selected_slugs = {path.name for path in mission_dirs}
    errors: list[dict[str, object]] = []
    for result in report.missions:
        if result.mission_slug not in selected_slugs:
            continue
        for finding in result.findings:
            if not is_teamspace_blocker(finding):
                continue
            if _is_out_of_scope_side_log_path(finding.artifact_path):
                continue
            errors.append(
                {
                    "mission_slug": result.mission_slug,
                    "artifact_path": finding.artifact_path,
                    "error": "MISSION_STATE_AUDIT_BLOCKER",
                    "finding_code": finding.code,
                    "severity": finding.severity.value,
                    "message": finding.detail or finding.code,
                    "remediation": (
                        "Run `spec-kitty doctor mission-state --audit --fail-on "
                        "teamspace-blocker`, then `--fix`, then "
                        "`--teamspace-dry-run` before TeamSpace import/sync."
                    ),
                }
            )
    return sorted(
        errors,
        key=lambda item: (
            str(item["mission_slug"]),
            str(item["artifact_path"]),
            str(item["finding_code"]),
        ),
    )


def _is_out_of_scope_side_log_path(artifact_path: str) -> bool:
    return (
        artifact_path.endswith("/mission-events.jsonl")
        or "/decisions/events.jsonl" in artifact_path
        or "/handoff/events.jsonl" in artifact_path
        or "/_archive/" in artifact_path
        or artifact_path.endswith("/run.events.jsonl")
    )


def _is_nonfatal_side_log_record(record: Mapping[str, object]) -> bool:
    return record.get("reason") == "out_of_scope_for_launch_import" and str(record.get("disposition", "")).startswith("skipped_")


def _teamspace_context_warnings(repo_root: Path, project_uuid: uuid.UUID) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    try:
        from specify_cli.identity.project import load_identity

        identity = load_identity(repo_root / ".kittify" / "config.yaml")
    except Exception:
        identity = None

    if identity is None or identity.project_uuid is None:
        warnings.append(
            {
                "code": "TEAMSPACE_PROJECT_CONTEXT_MISSING",
                "message": ("No persisted project.uuid was found; dry-run used a deterministic offline project_uuid for schema validation only."),
                "dry_run_project_uuid": str(project_uuid),
            }
        )

    warnings.append(
        {
            "code": "TEAMSPACE_TEAM_CONTEXT_NOT_VALIDATED",
            "message": "Team/private TeamSpace membership is not checked by offline dry-run.",
        }
    )
    return warnings


def _status_row_locations(mission_dir: Path) -> dict[str, _RawJsonlRow]:
    status_path = mission_dir / EVENTS_FILENAME
    if not status_path.exists():
        return {}
    try:
        rows = _read_jsonl_rows(status_path)
    except Exception:
        return {}

    locations: dict[str, _RawJsonlRow] = {}
    for row in rows:
        event_id = _event_id(row.data)
        if event_id is not None:
            locations.setdefault(event_id, row)
    return locations


def _load_events_contract() -> tuple[type[Any], Any, str]:
    import spec_kitty_events
    from spec_kitty_events import Event
    from spec_kitty_events.conformance import validate_event

    package_version = Version(spec_kitty_events.__version__)
    if package_version < REQUIRED_EVENTS_PACKAGE:
        raise MissionStateDryRunError(f"TeamSpace dry-run requires spec-kitty-events >= {REQUIRED_EVENTS_PACKAGE}; installed {package_version}.")
    return Event, validate_event, str(package_version)


class _TeamspaceEnvelope(BaseModel):
    """The SINGLE TeamSpace replay-envelope shape (#2891, CP001/CP002 #2884).

    The migration ``WPStatusChanged`` builder assembles the 15-key envelope
    this model owns, so a new envelope-level field cannot be added and silently
    forgotten elsewhere -- ``extra="forbid"`` turns a mismatched key set into a
    construction-time error instead of a silent drift. (The history-import
    creation-prefix builder that formerly shared this recipe via the
    ``envelope_seam`` re-export was removed with the sync transport -- issue
    #5 -- and the seam itself was pruned as dead collateral -- issue #116.)
    Callers compute the field VALUES (``build_id`` /
    ``correlation_id`` / ... differ per producer); the KEY SET and
    ``schema_version`` live here.

    Fields deliberately keep their raw wire types (``str`` for ``timestamp``
    and ``project_uuid``, not ``datetime``/``UUID``): this is a structural
    shape guard for the replay/synthesis producers, not the
    ``spec_kitty_events.Event`` wire contract (that separate validation
    already happens via ``event_cls.model_validate(envelope)`` in
    ``teamspace_dry_run``). Constructing through ``Event`` here instead would
    silently drop ``aggregate_type``/``repo_slug`` -- fields ``Event`` does not
    declare -- and coerce ``timestamp``/``project_uuid`` to
    ``datetime``/``UUID``, changing the on-wire envelope shape asserted by
    ``tests/sync/test_history_import_synthesize.py``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    payload: dict[str, Any]
    timestamp: str
    build_id: str
    node_id: str
    lamport_clock: int
    causation_id: str | None = None
    project_uuid: str
    project_slug: str
    repo_slug: str | None
    correlation_id: str
    schema_version: str = CANONICAL_ENVELOPE_SCHEMA_VERSION


def _build_teamspace_envelope(
    *,
    event_id: str,
    event_type: str,
    aggregate_id: str,
    aggregate_type: str,
    payload: dict[str, Any],
    timestamp: str,
    build_id: str,
    node_id: str,
    lamport_clock: int,
    project_uuid: str,
    project_slug: str,
    repo_slug: str | None,
    correlation_id: str,
    causation_id: str | None = None,
) -> _TeamspaceEnvelope:
    """Construct the SINGLE TeamSpace replay-envelope shell (#2891).

    Callers that need the wire-format dict (JSONL rows, hashing, upload
    payloads) call ``.model_dump()`` at their own serialization boundary --
    this builder's job is only to close the "hand-rolled dict, key typo, or
    forgotten key" defect class by construction.
    """
    return _TeamspaceEnvelope(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        payload=payload,
        timestamp=timestamp,
        build_id=build_id,
        node_id=node_id,
        lamport_clock=lamport_clock,
        causation_id=causation_id,
        project_uuid=project_uuid,
        project_slug=project_slug,
        repo_slug=repo_slug,
        correlation_id=correlation_id,
        schema_version=CANONICAL_ENVELOPE_SCHEMA_VERSION,
    )


# canonical-producer-exempt: #1198 -- historical migration-replay envelope builder.
def _status_event_to_teamspace_envelope(
    status_event: StatusEvent,
    *,
    project_uuid: uuid.UUID,
    lamport_clock: int,
    project_slug: str,
    repo_slug: str | None,
) -> dict[str, Any]:
    evidence = status_event.evidence.to_dict() if status_event.evidence else None
    if str(status_event.to_lane) in {"approved", "done"}:
        evidence = _historical_teamspace_evidence(
            status_event,
            evidence=evidence,
            project_slug=project_slug,
            repo_slug=repo_slug,
        )

    from_lane = str(status_event.from_lane)
    to_lane = str(status_event.to_lane)
    if status_event.from_lane is Lane.IN_PROGRESS and status_event.to_lane is Lane.IN_REVIEW:
        # Older local logs skipped the explicit for_review queue lane.
        from_lane = str(Lane.FOR_REVIEW)

    payload = {
        "mission_slug": status_event.mission_slug,
        "wp_id": status_event.wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "actor": status_event.actor,
        "force": status_event.force,
        "reason": status_event.reason,
        "execution_mode": status_event.execution_mode,
        "review_ref": status_event.review_ref,
        "evidence": evidence,
    }
    return _build_teamspace_envelope(
        event_id=status_event.event_id,
        event_type="WPStatusChanged",
        aggregate_id=status_event.wp_id,
        aggregate_type="WorkPackage",
        payload=payload,
        timestamp=status_event.at,
        build_id="mission-state-dry-run",
        node_id="mission-state-dry-run",
        lamport_clock=lamport_clock,
        project_uuid=str(project_uuid),
        project_slug=project_slug,
        repo_slug=repo_slug,
        correlation_id=deterministic_ulid(f"teamspace-dry-run:{status_event.mission_slug}:{status_event.event_id}"),
    ).model_dump()


def _historical_teamspace_evidence(
    status_event: StatusEvent,
    *,
    evidence: dict[str, Any] | None,
    project_slug: str,
    repo_slug: str | None,
) -> dict[str, Any]:
    """Return deterministic evidence for historical approval/done rows.

    Older local status rows may have no evidence at all, or may have review
    evidence without repo evidence. The TeamSpace 5.0.0 event contract requires
    evidence for both approved and done transitions, including at least one repo
    entry, so dry-run/import synthesis fills only the missing historical facts.
    """
    resolved = dict(evidence or {})
    if not resolved.get("review"):
        resolved["review"] = {
            "reviewer": status_event.actor or "historical-mission-state-repair",
            "verdict": "approved",
            "reference": status_event.review_ref or f"historical-mission-state-repair:{status_event.mission_slug}:{status_event.wp_id}:{status_event.event_id}",
        }
    if not resolved.get("repos"):
        resolved["repos"] = [
            {
                "repo": repo_slug or project_slug,
                "branch": "historical-mission-state-repair",
                "commit": "historical-mission-state-repair",
            }
        ]
    resolved.setdefault("verification", [])
    return resolved


def _scan_raw_status_rows(repo_root: Path, mission_dir: Path) -> list[dict[str, object]]:
    status_path = mission_dir / EVENTS_FILENAME
    if not status_path.exists():
        return []
    try:
        rows = _read_jsonl_rows(status_path)
    except Exception as exc:
        return [
            {
                "mission_slug": mission_dir.name,
                "artifact_path": _repo_relpath(repo_root, status_path),
                "error": "STATUS_EVENTS_UNREADABLE",
                "message": str(exc),
            }
        ]

    errors: list[dict[str, object]] = []
    rel = _repo_relpath(repo_root, status_path)
    for row in rows:
        # Preserved-class non-lane rows (retrospective + canonical lifecycle
        # events, issue #2376) legitimately live in status.events.jsonl and are
        # left in place by the repair. They are not lane events, so the
        # lane-event scans below (typed-row + forbidden-legacy-key, which recurse
        # into another subsystem's payload) do not apply to them.
        if _is_preserved_non_lane_row(row.data):
            continue
        if "event_type" in row.data or "event_name" in row.data:
            errors.append(
                {
                    "mission_slug": mission_dir.name,
                    "artifact_path": rel,
                    "line_number": row.line_number,
                    "event_id": _event_id(row.data),
                    "error": "STATUS_ROW_NOT_REPAIRED",
                    "message": "typed side-log row remains in status.events.jsonl; run --fix before dry-run",
                }
            )
        for path, key in _find_forbidden_key_paths(row.data):
            errors.append(
                {
                    "mission_slug": mission_dir.name,
                    "artifact_path": rel,
                    "line_number": row.line_number,
                    "event_id": _event_id(row.data),
                    "error": "FORBIDDEN_LEGACY_KEY",
                    "path": path,
                    "key": key,
                }
            )
    return errors


def _classify_side_logs(repo_root: Path, mission_dir: Path) -> list[dict[str, object]]:
    candidates: list[Path] = [
        mission_dir / "decisions" / "events.jsonl",
        mission_dir / "handoff" / "events.jsonl",
        mission_dir / "mission-events.jsonl",
    ]
    archive = mission_dir / "_archive"
    if archive.exists():
        candidates.extend(sorted(archive.glob("*.events.jsonl")))

    side_logs: list[dict[str, object]] = []
    for path in candidates:
        if not path.exists():
            continue
        side_logs.append(
            {
                "artifact_path": _repo_relpath(repo_root, path),
                "row_count": _count_jsonl_rows(path),
                "disposition": "skipped_local_side_log",
                "reason": "out_of_scope_for_launch_import",
            }
        )

    runtime_root = repo_root / ".kittify" / "runtime"
    if runtime_root.exists():
        for path in sorted(runtime_root.glob("**/run.events.jsonl")):
            side_logs.append(
                {
                    "artifact_path": _repo_relpath(repo_root, path),
                    "row_count": _count_jsonl_rows(path),
                    "disposition": "skipped_runtime_side_log",
                    "reason": "out_of_scope_for_launch_import",
                }
            )
    return side_logs


def _find_forbidden_key_paths(value: Any, *, prefix: str = "$") -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_LEGACY_KEYS:
                findings.append((child_path, str(key)))
            findings.extend(_find_forbidden_key_paths(child, prefix=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_key_paths(child, prefix=f"{prefix}[{index}]"))
    return findings


def _count_jsonl_rows(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _repair_mission(
    repo_root: Path,
    mission_dir: Path,
    *,
    run_id: str,
    generated_ids: list[str] | None = None,
) -> MissionRepairResult:
    """Repair a single mission directory.

    When *generated_ids* is supplied, every deterministic ULID minted
    during the repair is appended for inclusion in the top-level manifest
    (Mission 8, Priivacy-ai/spec-kitty#930).
    """
    mission_slug = mission_dir.name
    mission_id: str | None = None
    file_changes: list[FileChange] = []
    row_changes: list[RowTransformation] = []
    validation_errors: list[str] = []
    quarantined_rows = 0
    # Bind before the try so the except path can still report canonicalizer
    # actions (e.g. normalized_change_mode) that were applied and persisted
    # before a later step raised — an error result must not silently drop the
    # record of what repair already changed on disk (report-fidelity, #4780).
    meta_actions: tuple[str, ...] = ()

    try:
        raw_rows = _read_jsonl_rows(mission_dir / EVENTS_FILENAME)
        meta, meta_actions = _canonicalize_meta(mission_dir, raw_rows, generated_ids=generated_ids)
        mission_slug = str(meta.get("mission_slug") or mission_slug)
        mission_id = str(meta.get("mission_id") or "")
        before_meta = _file_fingerprint(mission_dir / META_FILENAME)
        if meta_actions:
            write_meta(mission_dir, meta)
        after_meta = _file_fingerprint(mission_dir / META_FILENAME)
        if before_meta != after_meta:
            file_changes.append(_file_change(repo_root, mission_dir / META_FILENAME, before_meta, after_meta))

        status_path = mission_dir / EVENTS_FILENAME
        if status_path.exists():
            canonical_rows, row_transforms, quarantine_lines, row_errors = _canonicalize_status_rows(
                repo_root,
                mission_dir,
                raw_rows,
                mission_slug=mission_slug,
                mission_id=mission_id,
                generated_ids=generated_ids,
            )
            row_changes.extend(row_transforms)
            validation_errors.extend(row_errors)
            if row_errors:
                return MissionRepairResult(
                    mission_slug=mission_slug,
                    mission_id=mission_id,
                    status="error",
                    file_changes=file_changes,
                    row_transformations=row_changes,
                    quarantined_rows=len(quarantine_lines),
                    validation_errors=validation_errors,
                    meta_actions=list(meta_actions),
                )
            before_events = _file_fingerprint(status_path)
            status_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in canonical_rows)
            # Backstop (#2376): never silently empty a previously-populated event
            # log. Legitimate non-lane events are now preserved in
            # ``canonical_rows``, so an empty result despite non-empty input means
            # every row was dropped as genuinely foreign — an extraordinary
            # outcome that fails loud (recorded as a mission error with a reason)
            # rather than wiping the canonical log. Originals remain in the
            # quarantine directory.
            if raw_rows and not canonical_rows:
                raise MissionStateRepairError(
                    f"Refusing to empty {_repo_relpath(repo_root, status_path)}: "
                    f"all {len(raw_rows)} row(s) were dropped by repair. This "
                    "usually indicates a row-classification bug; the original "
                    "rows are preserved verbatim in the quarantine directory."
                )
            if status_path.read_text(encoding="utf-8") != status_text:
                atomic_write(status_path, status_text)
            after_events = _file_fingerprint(status_path)
            if before_events != after_events:
                file_changes.append(_file_change(repo_root, status_path, before_events, after_events))

            if quarantine_lines:
                quarantined_rows = len(quarantine_lines)
                # FR-001: mission_slug may originate from untrusted meta.json content
                # (meta.get("mission_slug")); validate before joining into the quarantine path.
                _safe_mission_slug = assert_safe_path_segment(mission_slug)
                quarantine_path = repo_root / MANIFEST_ROOT / "quarantine" / run_id / _safe_mission_slug / EVENTS_FILENAME
                before_quarantine = _file_fingerprint(quarantine_path)
                quarantine_text = "".join(line.rstrip("\n") + "\n" for line in quarantine_lines)
                atomic_write(quarantine_path, quarantine_text, mkdir=True)
                after_quarantine = _file_fingerprint(quarantine_path)
                if before_quarantine != after_quarantine:
                    file_changes.append(_file_change(repo_root, quarantine_path, before_quarantine, after_quarantine))

            before_status = _file_fingerprint(mission_dir / STATUS_FILENAME)
            snapshot = materialize_snapshot(mission_dir)
            status_json = materialize_to_json(snapshot)
            if not (mission_dir / STATUS_FILENAME).exists() or (mission_dir / STATUS_FILENAME).read_text(encoding="utf-8") != status_json:
                atomic_write(mission_dir / STATUS_FILENAME, status_json)
            after_status = _file_fingerprint(mission_dir / STATUS_FILENAME)
            if before_status != after_status:
                file_changes.append(_file_change(repo_root, mission_dir / STATUS_FILENAME, before_status, after_status))

        return MissionRepairResult(
            mission_slug=mission_slug,
            mission_id=mission_id,
            status="updated" if file_changes or row_changes or quarantined_rows else "unchanged",
            file_changes=file_changes,
            row_transformations=row_changes,
            quarantined_rows=quarantined_rows,
            validation_errors=validation_errors,
            meta_actions=list(meta_actions),
        )
    except Exception as exc:
        validation_errors.append(str(exc))
        return MissionRepairResult(
            mission_slug=mission_slug,
            mission_id=mission_id,
            status="error",
            file_changes=file_changes,
            row_transformations=row_changes,
            quarantined_rows=quarantined_rows,
            validation_errors=validation_errors,
            meta_actions=list(meta_actions),
        )


def _canonicalize_meta(
    mission_dir: Path,
    raw_rows: Sequence[_RawJsonlRow],
    *,
    generated_ids: list[str] | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    loaded = load_meta_fail_closed(mission_dir)
    meta = dict(loaded or {})
    actions: list[str] = []
    mission_slug = str(meta.get("mission_slug") or meta.get("slug") or meta.get("feature_slug") or mission_dir.name)
    meta["mission_slug"] = mission_slug
    meta.setdefault("slug", mission_slug)
    meta.setdefault("friendly_name", mission_slug)
    meta["mission_type"] = str(meta.get("mission_type") or meta.get("mission") or "software-dev")
    meta.setdefault("target_branch", "main")
    if not meta.get("created_at"):
        meta["created_at"] = _first_event_timestamp(raw_rows) or "1970-01-01T00:00:00+00:00"
        actions.append("created_at_defaulted")

    number_raw = meta.get("mission_number")
    if number_raw is None or number_raw == "":
        number_raw = meta.get("feature_number")
    mission_number = _coerce_mission_number(number_raw)
    if mission_number is None:
        mission_number = mission_number_from_slug(mission_slug)
    meta["mission_number"] = mission_number

    existing_id = meta.get("mission_id")
    if not isinstance(existing_id, str) or not ULID_PATTERN.match(existing_id):
        minted = deterministic_ulid(_mission_seed(mission_dir, meta, raw_rows))
        meta["mission_id"] = minted
        if generated_ids is not None:
            generated_ids.append(minted)
        actions.append("mission_id_deterministically_backfilled")

    for key in sorted(META_LEGACY_ALIASES):
        if key in meta:
            meta.pop(key, None)
            actions.append(f"removed_meta_key:{key}")

    # FR-001/002/003, FR-011: heal a legacy/malformed ``change_mode`` (anything
    # other than ``"bulk_edit"``) to ABSENT before validation, so ``--fix``
    # repairs the mission instead of aborting on it. Recorded conditionally —
    # mirroring ``removed_meta_key:{key}`` -- so a re-run is a no-op (NFR-002).
    # The dropped value is captured in the action tag itself (fidelity, #4780),
    # the same way ``removed_meta_key:{key}`` names the specific key it dropped.
    dropped_change_mode = _normalize_change_mode(meta)
    if dropped_change_mode is not None:
        actions.append(f"normalized_change_mode:{dropped_change_mode}")

    errors = validate_meta(meta)
    if errors:
        raise ValueError(f"Invalid canonical meta.json for {mission_dir.name}: {'; '.join(errors)}")
    return meta, tuple(actions)


def _canonicalize_status_rows(
    repo_root: Path,
    mission_dir: Path,
    rows: Sequence[_RawJsonlRow],
    *,
    mission_slug: str,
    mission_id: str,
    generated_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[RowTransformation], list[str], list[str]]:
    canonical_rows: list[dict[str, Any]] = []
    row_changes: list[RowTransformation] = []
    quarantine_lines: list[str] = []
    errors: list[str] = []
    seen_event_ids: set[str] = set()
    rel = _repo_relpath(repo_root, mission_dir / EVENTS_FILENAME)

    for row in rows:
        result = _canonicalize_status_row(
            row.data,
            mission_slug=mission_slug,
            mission_id=mission_id,
            line_number=row.line_number,
            generated_ids=generated_ids,
        )
        old_sha = _sha256_text(row.text)
        if result.error is not None:
            errors.append(f"{rel}:{row.line_number}: {result.error}")
            continue
        if result.row is None:
            quarantine_lines.append(row.text)
            row_changes.append(
                RowTransformation(
                    artifact_path=rel,
                    line_number=row.line_number,
                    event_id=_event_id(row.data),
                    actions=result.actions,
                    old_sha256=old_sha,
                    new_sha256=None,
                )
            )
            continue

        event_id = _event_id(result.row)
        actions = list(result.actions)
        if event_id in seen_event_ids:
            actions.append("duplicate_event_id_dropped")
            # Quarantine before dropping: duplicates observed so far have been
            # byte-identical to their survivor, but a *divergent* duplicate would
            # otherwise be deleted leaving only a sha256 behind.
            quarantine_lines.append(row.text)
            row_changes.append(
                RowTransformation(
                    artifact_path=rel,
                    line_number=row.line_number,
                    event_id=event_id,
                    actions=tuple(actions),
                    old_sha256=old_sha,
                    new_sha256=None,
                )
            )
            continue
        seen_event_ids.add(event_id or "")
        canonical_rows.append(result.row)
        new_text = json.dumps(result.row, sort_keys=True)
        if new_text != row.text.strip() or actions:
            row_changes.append(
                RowTransformation(
                    artifact_path=rel,
                    line_number=row.line_number,
                    event_id=event_id,
                    actions=tuple(actions),
                    old_sha256=old_sha,
                    new_sha256=_sha256_text(new_text),
                )
            )

    sorted_rows = sorted(canonical_rows, key=_row_sort_key)
    return sorted_rows, row_changes, quarantine_lines, errors


# ---------------------------------------------------------------------------
# Per-rule pure functions for _canonicalize_status_row
# Tactics: chain-of-responsibility-rule-pipeline (Transformer flavor),
#          refactoring-extract-first-order-concept
# ---------------------------------------------------------------------------

# Type alias for the row state used by all rules below.
_Row = dict[str, Any]


def _row_sort_key(item: Mapping[str, Any]) -> tuple[str, str]:
    """Chronological sort key for a status-log row.

    Lane rows date themselves with ``at``; the preserved non-lane rows
    (lifecycle / retrospective envelopes) use ``timestamp``. Reading only ``at``
    collapses every one of the latter to ``""`` and hoists them to the head of
    an append-only log, so both spellings are honoured here.
    """
    when = item.get("at") or item.get("timestamp") or ""
    return (str(when), str(item.get("event_id", "")))


def _is_preserved_non_lane_row(row: Mapping[str, Any]) -> bool:
    """Return True for non-lane rows the repair MUST keep in status.events.jsonl.

    ``status.events.jsonl`` is a *shared* append log. Lane-transition rows are
    flat (``wp_id`` / ``from_lane`` / ``to_lane``); other subsystems co-locate
    ``event_type`` / ``type`` / ``kind`` rows. Three of those classes have **no
    other per-mission home**, so quarantining them is real data loss (#2376):

    - **Retrospective lifecycle rows** (``type`` envelope) — contracted
      provenance read back by retrospective consumers.
    - **Canonical lifecycle events** whose ``event_type`` is in
      ``LIFECYCLE_EVENT_TYPES`` (``MissionCreated``, ``SpecifyStarted``,
      ``WPCreated``, …). :mod:`specify_cli.status.lifecycle_events` is their
      sole durable per-mission writer and declares this stream "a safe target
      for repair / replay tooling".
    - **``InnerStateChanged`` annotations** (``kind: "annotation"`` envelope) —
      load-bearing runtime state the reducer folds into the per-WP slots. They
      carry no lane fields by construction, so omitting them here does not just
      drop data: the row reaches ``_rule_require_to_lane`` and hard-errors the
      entire mission repair.

    Other ``event_type`` rows (e.g. Decision-Moment ``DecisionPoint*``) are NOT
    preserved here: their canonical store is elsewhere
    (``decisions/index.json`` + ``DM-*.md``), so the copy in status.events.jsonl
    is a prunable mirror — quarantining it (the shipped #980 behaviour) loses
    nothing.

    Kept in lock-step with the durable reader
    :func:`specify_cli.status.store.is_non_lane_event`: a THIRD reader-preserved
    class is the ``event_name``-envelope retrospective stream (rows whose
    ``event_name`` starts with ``"retrospective."`` — written by
    :func:`specify_cli.retrospective.events.emit_retrospective_event`, read back
    as load-bearing state by the reducer / retrospective gate + summary, with no
    other per-mission home). Omitting it re-opened the #2376 data-loss class in
    a different event format (a mixed log with a ``retrospective.completed`` row
    silently strips it). The reader's broader ``"event_type" in obj`` branch is
    deliberately NOT mirrored here: the repair's ``LIFECYCLE_EVENT_TYPES``
    narrowing is the intentional pruning divergence for Decision-Moment mirrors.
    """
    # ``InnerStateChanged`` annotations are preserved FIRST, mirroring the
    # placement of the durable reader's own leading branch
    # (:func:`specify_cli.status.store.is_non_lane_event`). They carry no
    # ``from_lane``/``to_lane`` by construction, so without this branch they
    # fall through to ``_rule_require_to_lane`` and hard-error the whole
    # mission repair. Quarantining them is NOT an option: the reducer folds
    # their typed ``WPInnerStateDelta`` into the per-WP runtime slots, so
    # dropping them is the #2376 data-loss class in a fourth event format.
    if row.get("kind") == ANNOTATION_KIND:
        return True

    event_name = row.get("event_name")
    if isinstance(event_name, str) and event_name.startswith("retrospective."):
        return True
    return is_retrospective_lifecycle_event(row) or row.get("event_type") in LIFECYCLE_EVENT_TYPES


_LEGACY_TYPED_LANE_EVENT_TYPE = "WPStatusChanged"
_LEGACY_TYPED_LANE_FIELDS = ("wp_id", "from_lane", "to_lane")


def _is_legacy_typed_lane_transition(row: Mapping[str, Any]) -> bool:
    """Return True for a legacy canonical-writer ``WPStatusChanged`` lane row.

    The mission's own ``WPStatusChanged`` writer emits
    ``event_type == "WPStatusChanged"`` alongside the TOP-LEVEL lane fields
    ``wp_id`` / ``from_lane`` / ``to_lane`` (see
    :func:`_status_event_to_teamspace_envelope`, which stamps the same
    ``event_type``). Such a row is a fully-formed lane transition that merely
    carries a typed discriminator: routing it via passthrough lets the rest of
    the canonicalization pipeline strip ``event_type`` through the
    ``_build_canonical_row`` allowlist and fold it into ``status.json``.

    Quarantining it — the shipped defect #3066, where
    :func:`_is_preserved_non_lane_row` omits ``WPStatusChanged`` and the
    ``event_type`` branch of :func:`_rule_reject_non_status_event` sweeps it out
    — drops live lane history and regenerates a **zero-WP** ``status.json``, a
    data-destroying repair.

    ONLY the flat canonical-writer shape passes here. TeamSpace replay envelopes
    also carry ``event_type == "WPStatusChanged"`` but nest ``wp_id`` /
    ``from_lane`` / ``to_lane`` under ``payload`` (their top level is
    ``aggregate_id`` / ``aggregate_type``), and ``DecisionPoint*`` mirrors carry
    a different ``event_type`` — both fail this predicate and stay quarantined.
    """
    if row.get("event_type") != _LEGACY_TYPED_LANE_EVENT_TYPE:
        return False
    return all(field in row for field in _LEGACY_TYPED_LANE_FIELDS)


def _rule_reject_non_status_event(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 1: route non-lane rows that share status.events.jsonl.

    - Legacy typed lane transitions (:func:`_is_legacy_typed_lane_transition`:
      the mission's own ``WPStatusChanged`` writer shape, with top-level
      ``wp_id`` / ``from_lane`` / ``to_lane``) are PASSED THROUGH to the rest of
      the pipeline, which strips the typed discriminator and folds them into
      ``status.json``. This check runs FIRST, ahead of the quarantine branches,
      so #3066's zero-WP regeneration can no longer eat live lane history.
    - Rows whose only per-mission home is this file
      (:func:`_is_preserved_non_lane_row`: retrospective + canonical lifecycle
      events) are PRESERVED in place — the runtime reader skips them during lane
      reduction but they are contracted data; quarantining them (issue #2376)
      emptied healthy mission logs.
    - Any other ``event_type`` / ``event_name`` row is QUARANTINED (its canonical
      state, if any, lives elsewhere). ``_scan_raw_status_rows`` flags the same
      class before a TeamSpace dry-run.
    """
    if _is_legacy_typed_lane_transition(row):
        return CanonicalStepResult.passthrough(row)
    if _is_preserved_non_lane_row(row):
        return CanonicalStepResult(
            state=row,
            actions=(),
            error="preserved_non_lane_event",
        )
    if "event_name" in row or "event_type" in row:
        return CanonicalStepResult(
            state=row,
            actions=("quarantined_non_status_event",),
            error="quarantined_non_status_event",
        )
    return CanonicalStepResult.passthrough(row)


def _rule_apply_aliases(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 2: rename legacy STATUS_ROW_ALIASES keys to their canonical names."""
    new_row = dict(row)
    new_actions: list[str] = []
    for old, new in STATUS_ROW_ALIASES.items():
        if old in new_row:
            if new not in new_row or not new_row.get(new):
                new_row[new] = new_row[old]
            new_row.pop(old, None)
            new_actions.append(f"renamed_key:{old}->{new}")
    if not new_actions:
        return CanonicalStepResult.passthrough(row)
    return CanonicalStepResult(state=new_row, actions=tuple(new_actions))


def _rule_strip_legacy_keys(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 3: remove FORBIDDEN_LEGACY_KEYS (except feature_slug, handled by aliases)."""
    new_row = dict(row)
    new_actions: list[str] = []
    for key in sorted(FORBIDDEN_LEGACY_KEYS - {"feature_slug"}):
        if key in new_row:
            new_row.pop(key, None)
            new_actions.append(f"removed_key:{key}")
    if not new_actions:
        return CanonicalStepResult.passthrough(row)
    return CanonicalStepResult(state=new_row, actions=tuple(new_actions))


def _rule_stamp_identity(row: _Row, ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 4: stamp mission_slug and mission_id onto the row."""
    new_row = dict(row)
    new_row["mission_slug"] = str(new_row.get("mission_slug") or ctx.mission_slug)
    new_row["mission_id"] = ctx.mission_id
    return CanonicalStepResult(state=new_row, actions=())


def _rule_mint_event_id(row: _Row, ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 5: mint a deterministic event_id when missing or invalid."""
    if _valid_event_id(row.get("event_id")):
        return CanonicalStepResult.passthrough(row)
    new_row = dict(row)
    minted = deterministic_ulid(json.dumps(new_row, sort_keys=True, default=str) + f":line:{ctx.line_number}")
    new_row["event_id"] = minted
    if ctx.generated_ids is not None:
        ctx.generated_ids.append(minted)
    return CanonicalStepResult(
        state=new_row,
        actions=("event_id_deterministically_backfilled",),
    )


def _rule_default_at(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 6: default 'at' to the UNIX epoch when missing or empty."""
    if row.get("at"):
        return CanonicalStepResult.passthrough(row)
    new_row = dict(row)
    new_row["at"] = "1970-01-01T00:00:00+00:00"
    return CanonicalStepResult(state=new_row, actions=("at_defaulted",))


def _rule_default_from_lane(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 7: default 'from_lane' to 'planned' when absent (None)."""
    if row.get("from_lane") is not None:
        return CanonicalStepResult.passthrough(row)
    new_row = dict(row)
    new_row["from_lane"] = "planned"
    return CanonicalStepResult(state=new_row, actions=("from_lane_defaulted",))


def _rule_require_to_lane(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 8: short-circuit with error when 'to_lane' is missing."""
    if row.get("to_lane"):
        return CanonicalStepResult.passthrough(row)
    return CanonicalStepResult(state=row, actions=(), error="missing required to_lane")


def _rule_require_wp_id(row: _Row, _ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 9: short-circuit with error when 'wp_id' is missing."""
    if row.get("wp_id"):
        return CanonicalStepResult.passthrough(row)
    return CanonicalStepResult(state=row, actions=(), error="missing required wp_id")


def _normalize_lane_keys(new_row: _Row, new_actions: list[str]) -> str | None:
    """Apply LANE_ALIASES to from_lane/to_lane. Returns error message or None."""
    for key in ("from_lane", "to_lane"):
        lane = str(new_row[key])
        normalized = LANE_ALIASES.get(lane, lane)
        if normalized not in VALID_LANES:
            return f"unknown {key} {lane!r}"
        if normalized != lane:
            new_actions.append(f"lane_alias:{key}:{lane}->{normalized}")
            new_row[key] = normalized
    return None


def _normalize_actor_field(new_row: _Row, new_actions: list[str]) -> None:
    """Normalize the actor field in-place, recording any action taken."""
    actor = new_row.get("actor")
    if isinstance(actor, Mapping):
        metadata = dict(new_row.get("policy_metadata") or {})
        metadata.setdefault("migration_original_actor", actor)
        new_row["policy_metadata"] = metadata
        new_row["actor"] = _actor_label(actor)
        new_actions.append("actor_dict_labelled")
        return
    if not isinstance(actor, str) or not actor.strip():
        new_row["actor"] = "migration"
        new_actions.append("actor_defaulted")
        return
    normalized_actor = _normalize_actor(actor)
    if normalized_actor != actor:
        new_row["actor"] = normalized_actor
        new_actions.append("actor_normalized")


def _default_force_and_mode(new_row: _Row, new_actions: list[str]) -> None:
    """Apply default values for force and execution_mode in-place."""
    if "force" not in new_row:
        new_row["force"] = False
        new_actions.append("force_defaulted")
    if new_row.get("execution_mode") not in VALID_EXECUTION_MODES:
        new_row["execution_mode"] = "direct_repo"
        new_actions.append("execution_mode_defaulted")


def _build_canonical_row(new_row: _Row, mission_id: str) -> _Row:
    """Build the canonical shape from a normalized row.

    This is an allowlist: any ``StatusEvent`` field omitted here is dropped from
    the repaired log. ``review_result`` in particular is a hard FSM guard input
    (every transition out of ``in_review`` is rejected without it), so omitting
    it silently converts valid history into unvalidatable events.
    """
    return {
        "event_id": str(new_row["event_id"]),
        "mission_slug": str(new_row["mission_slug"]),
        "wp_id": str(new_row.get("wp_id") or ""),
        "from_lane": str(new_row["from_lane"]),
        "to_lane": str(new_row["to_lane"]),
        "at": str(new_row["at"]),
        "actor": str(new_row["actor"]),
        "force": bool(new_row["force"]),
        "execution_mode": str(new_row["execution_mode"]),
        "reason": new_row.get("reason"),
        "reason_source": new_row.get("reason_source"),
        "review_ref": new_row.get("review_ref"),
        "evidence": new_row.get("evidence"),
        "review_result": new_row.get("review_result"),
        "policy_metadata": new_row.get("policy_metadata"),
        "mission_id": mission_id,
    }


def _rule_normalize_lanes(row: _Row, ctx: MigrationContext) -> CanonicalStepResult[_Row]:
    """Rule 10: normalize and validate lane values; also normalizes actor, force, execution_mode, builds canonical shape.

    Applies LANE_ALIASES and validates both from_lane and to_lane against VALID_LANES.
    Then normalizes the actor field, defaults force and execution_mode, and
    builds the final canonical row dict, which is validated via StatusEvent.from_dict.
    """
    new_row = dict(row)
    new_actions: list[str] = []

    lane_error = _normalize_lane_keys(new_row, new_actions)
    if lane_error is not None:
        return CanonicalStepResult(state=new_row, actions=tuple(new_actions), error=lane_error)

    _normalize_actor_field(new_row, new_actions)
    _default_force_and_mode(new_row, new_actions)

    canonical = _build_canonical_row(new_row, ctx.mission_id)
    # FR-009 manifest honesty: ``_build_canonical_row`` is an allowlist, so any
    # field present on the normalized row but absent from the canonical shape is
    # dropped. Enumerate those removals so the manifest lists every field the
    # repair touches — including removed fields — not just renames/normalizations.
    for dropped in sorted(set(new_row) - set(canonical)):
        new_actions.append(f"removed_field:{dropped}")
    try:
        StatusEvent.from_dict(canonical)
    except Exception as exc:
        return CanonicalStepResult(state=new_row, actions=tuple(new_actions), error=str(exc))
    return CanonicalStepResult(state=canonical, actions=tuple(new_actions))


# Ordered rule tuple — order is part of the contract.
# Tactics: chain-of-responsibility-rule-pipeline (Transformer flavor)
# See: contracts/canonicalization-rule-pipeline.md
# cast: each function matches CanonicalRule[_Row] by structural subtyping;
# mypy cannot infer Protocol compliance from bare callables in a tuple literal.
_CANONICAL_STATUS_ROW_RULES: tuple[CanonicalRule[_Row], ...] = cast(
    "tuple[CanonicalRule[_Row], ...]",
    (
        _rule_reject_non_status_event,
        _rule_apply_aliases,
        _rule_strip_legacy_keys,
        _rule_stamp_identity,
        _rule_mint_event_id,
        _rule_default_at,
        _rule_default_from_lane,
        _rule_require_to_lane,
        _rule_require_wp_id,
        _rule_normalize_lanes,
    ),
)


def _canonicalize_status_row(
    data: Mapping[str, Any],
    *,
    mission_slug: str,
    mission_id: str,
    line_number: int,
    generated_ids: list[str] | None = None,
) -> _CanonicalRowResult:
    """Canonicalize a single status-event row via the typed rule pipeline.

    Delegates to :func:`apply_rules` with :data:`_CANONICAL_STATUS_ROW_RULES`.
    The pipeline is a Transformer-flavor chain: each rule checks applicability,
    optionally transforms the state, and returns a :class:`CanonicalStepResult`.
    Short-circuits on the first error.

    Non-lane rows are handled by ``_rule_reject_non_status_event`` via two
    sentinel errors translated here: ``quarantined_non_status_event`` becomes
    ``row=None`` (the caller routes the original line to the quarantine file),
    and ``preserved_non_lane_event`` returns the original row untouched (the
    caller keeps it in status.events.jsonl exactly as the runtime reader
    expects to find it).
    """
    ctx = MigrationContext(
        mission_slug=mission_slug,
        mission_id=mission_id,
        line_number=line_number,
        generated_ids=generated_ids,
    )
    result = apply_rules(_CANONICAL_STATUS_ROW_RULES, dict(data), ctx)
    # Special case: quarantined_non_status_event is surfaced as row=None with no error
    # (the caller _canonicalize_status_rows checks result.row is None, not result.error)
    if result.error == "quarantined_non_status_event":
        return _CanonicalRowResult(row=None, actions=result.actions, error=None)
    # Special case: preserved_non_lane_event keeps the original row in the
    # event log untouched — these rows are contracted data other subsystems
    # read back, not corruption (see _rule_reject_non_status_event).
    if result.error == "preserved_non_lane_event":
        return _CanonicalRowResult(row=dict(data), actions=(), error=None)
    return _CanonicalRowResult.from_pipeline(result)


def _select_mission_dirs(repo_root: Path, *, scan_root: Path | None, mission: str | None) -> list[Path]:
    root = (scan_root or repo_root / "kitty-specs").resolve()
    if not root.exists():
        return []
    all_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if mission is None:
        return all_dirs
    matches = [path for path in all_dirs if _mission_handle_matches(path, mission)]
    if not matches:
        raise MissionStateRepairError(f"Mission not found: {mission!r}")
    if len(matches) > 1:
        candidates = ", ".join(path.name for path in matches)
        raise MissionStateRepairError(f"Ambiguous mission handle {mission!r}: {candidates}")
    return matches


def _mission_handle_matches(path: Path, handle: str) -> bool:
    if path.name == handle:
        return True
    prefix = _MISSION_PREFIX_RE.match(path.name)
    if prefix and prefix.group(1) == handle:
        return True
    stripped = path.name[4:] if prefix else path.name
    if stripped == handle:
        return True
    meta = load_meta_or_empty(path)
    mission_id = meta.get("mission_id")
    if isinstance(mission_id, str):
        if mission_id == handle:
            return True
        if _MID8_RE.match(handle) and mission_id.startswith(handle):
            return True
    return False


def _read_jsonl_rows(path: Path) -> list[_RawJsonlRow]:
    if not path.exists():
        return []
    rows: list[_RawJsonlRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError(f"Invalid JSONL row on line {line_number}: expected object")
            rows.append(_RawJsonlRow(line_number=line_number, text=stripped, data=data))
    return rows


def _first_event_timestamp(rows: Sequence[_RawJsonlRow]) -> str | None:
    values = sorted(str(row.data["at"]) for row in rows if row.data.get("at"))
    return values[0] if values else None


def _mission_seed(mission_dir: Path, meta: Mapping[str, Any], rows: Sequence[_RawJsonlRow]) -> str:
    stable_meta = {
        "mission_slug": meta.get("mission_slug") or mission_dir.name,
        "slug": meta.get("slug"),
        "friendly_name": meta.get("friendly_name"),
        "created_at": meta.get("created_at"),
        "target_branch": meta.get("target_branch"),
        "mission_type": meta.get("mission_type"),
    }
    first_event = rows[0].data if rows else {}
    return json.dumps(
        {
            "meta": stable_meta,
            "first_event_id": first_event.get("event_id"),
            "first_event_at": first_event.get("at"),
        },
        sort_keys=True,
        default=str,
    )


def _coerce_mission_number(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"mission_number must be int or null, got bool {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped.lstrip("0") or "0")
    raise ValueError(f"mission_number must be int or numeric string, got {value!r}")


def _normalize_actor(value: str) -> str:
    actor = _ACTOR_SAFE.sub("-", value.strip().lower()).strip("-_.:")
    return actor or "migration"


def _actor_label(actor: Mapping[str, Any]) -> str:
    for key in ("profile", "role", "display_name", "actor_id", "name"):
        value = actor.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_actor(value)
    return "structured-actor"


def _event_id(row: Mapping[str, Any]) -> str | None:
    value = row.get("event_id")
    return str(value) if value is not None else None


def _valid_event_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(ULID_PATTERN.match(value) or _UUID_HYPHEN_RE.match(value) or _UUID_BARE_RE.match(value))


def _compute_run_id(repo_root: Path, mission_dirs: Sequence[Path]) -> str:
    digest = hashlib.sha256()  # noqa: TID251 - production raw SHA-256 owner
    digest.update(b"spec-kitty:mission-state:v1\n")
    for mission_dir in mission_dirs:
        for name in (META_FILENAME, EVENTS_FILENAME, STATUS_FILENAME):
            path = mission_dir / name
            rel = _repo_relpath(repo_root, path)
            digest.update(rel.encode("utf-8") + b"\0")
            if path.exists():
                digest.update(path.read_bytes())
            else:
                digest.update(b"<missing>")
            digest.update(b"\0")
    return digest.hexdigest()[:16]


def _file_fingerprint(path: Path) -> tuple[str | None, int | None]:
    if not path.exists():
        return None, None
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)  # noqa: TID251 - production raw SHA-256 owner


def _file_change(
    repo_root: Path,
    path: Path,
    old: tuple[str | None, int | None],
    new: tuple[str | None, int | None],
) -> FileChange:
    return FileChange(
        path=_repo_relpath(repo_root, path),
        old_sha256=old[0],
        new_sha256=new[0],
        old_size=old[1],
        new_size=new[1],
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def _repo_relpath(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _resolve_repo_relative(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return repo_root / path


def _is_remote_url(slug: str) -> bool:
    """Return True when *slug* is an HTTP(S) remote URL."""
    return urlsplit(slug).scheme in _REMOTE_URL_SCHEMES


def _repo_slug(repo_root: Path) -> str | None:
    result = _git(repo_root, "config", "--get", "remote.origin.url", check=False)
    remote = result.stdout.strip()
    if not remote:
        return repo_root.name
    slug = remote.removesuffix(".git").rstrip("/")
    if ":" in slug and not _is_remote_url(slug):
        slug = slug.rsplit(":", 1)[1]
    elif "/" in slug:
        parts = slug.split("/")
        slug = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    return slug or repo_root.name


def _git_head(repo_root: Path) -> str | None:
    result = _git(repo_root, "rev-parse", "HEAD", check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _assert_git_safe(repo_root: Path, rel_paths: Sequence[str], *, allow_dirty: bool) -> None:
    if allow_dirty or not _is_git_repo(repo_root):
        return
    dirty: list[str] = []
    for worktree in _git_worktrees(repo_root):
        result = _git(worktree, "status", "--porcelain", "--", *rel_paths, check=False)
        if result.stdout.strip():
            dirty.append(f"{worktree}: {result.stdout.strip()}")
    if dirty:
        raise MissionStateRepairError(
            "Refusing mission-state repair with dirty relevant paths. Commit/stash them first or pass --allow-dirty.\n" + "\n".join(dirty)
        )


def _is_git_repo(repo_root: Path) -> bool:
    return _git(repo_root, "rev-parse", "--is-inside-work-tree", check=False).returncode == 0


def _git_worktrees(repo_root: Path) -> list[Path]:
    result = _git(repo_root, "worktree", "list", "--porcelain", check=False)
    if result.returncode != 0:
        return [repo_root]
    worktrees: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            worktrees.append(Path(line.removeprefix("worktree ")))
    return worktrees or [repo_root]


class _git_lock:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._path: Path | None = None
        self._fd: int | None = None

    def __enter__(self) -> None:
        if not _is_git_repo(self._repo_root):
            return
        result = _git(self._repo_root, "rev-parse", "--git-common-dir", check=False)
        if result.returncode != 0:
            return
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = self._repo_root / common
        common.mkdir(parents=True, exist_ok=True)
        self._path = common / "spec-kitty-mission-state.lock"
        try:
            self._fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._fd, str(os.getpid()).encode("ascii"))
        except FileExistsError as exc:
            raise MissionStateRepairError(f"Another mission-state repair appears to be running: {self._path}") from exc

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
        if self._path is not None:
            with suppress(FileNotFoundError):
                self._path.unlink()


def _git(repo_root: Path, *args: str, check: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=check,
        text=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Canonical per-mission event-rebuild entry (WP13, Priivacy-ai/spec-kitty#1754)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionEventRebuildResult:
    """Count-shaped outcome of rebuilding one mission's canonical event log.

    This is the single canonical reporting contract for per-mission event
    rebuild (FR-032). It preserves the per-feature counts the migration runner
    and lifecycle normalizer depend on (``events_generated`` /
    ``events_corrected``) plus the ``errors`` / ``warnings`` channels, without
    leaking the richer internal :class:`RebuildResult` shape across the seam.
    """

    mission_slug: str
    events_generated: int
    events_corrected: int
    errors: list[str]
    warnings: list[str]
    skipped: bool = False


def rebuild_mission_event_log(
    feature_dir: Path,
    mission_slug: str,
    *,
    wp_id_map: Mapping[str, str] | None = None,
) -> MissionEventRebuildResult:
    """Rebuild one mission's canonical ``status.events.jsonl`` from legacy state.

    This is the **single canonical** per-mission event-rebuild entry point
    (FR-032, NFR-002). Both live legacy-migration callers — the one-shot
    migration runner (Step 4) and the lifecycle normalizer — route through here
    instead of importing the underlying rebuild symbol directly.

    The rebuild logic itself lives once in
    :mod:`specify_cli.migration.rebuild_state`; this entry adapts its richer
    :class:`RebuildResult` down to the stable count-shaped
    :class:`MissionEventRebuildResult` contract. Behavior is preserved exactly:
    the same legacy fixture produces byte-identical ``status.events.jsonl``
    output regardless of which seam invokes the rebuild (NFR-004).

    Args:
        feature_dir: Path to the mission directory (e.g. ``kitty-specs/057-…``).
        mission_slug: Slug of the mission (e.g. ``"057-…"``).
        wp_id_map: Optional mapping of ``wp_code → work_package_id`` used to
            enrich events that lack ``work_package_id``. Defaults to empty.

    Returns:
        :class:`MissionEventRebuildResult` with per-mission counts and channels.
    """
    # Imported at point of use: the rebuild implementation is an internal detail
    # of the migration package, and deferring the import keeps unrelated
    # importers of this module off the rebuild dependency chain.
    from specify_cli.migration.rebuild_state import rebuild_event_log

    result = rebuild_event_log(feature_dir, mission_slug, dict(wp_id_map or {}))
    return MissionEventRebuildResult(
        mission_slug=result.feature_slug,
        events_generated=result.events_generated,
        events_corrected=result.events_corrected,
        errors=list(result.errors),
        warnings=list(result.warnings),
        skipped=result.skipped,
    )


__all__ = [
    # CANONICAL_ENVELOPE_SCHEMA_VERSION, MIGRATION_SCHEMA_VERSION,
    # MissionEventRebuildResult, RepairReport, TeamspaceDryRunRowMapping,
    # deterministic_ulid: demoted — migration-internal; no cross-module
    # src/ from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    # The former sanctioned cross-module surface, migration/envelope_seam.py
    # (#2262/#2884), re-exported the shared subset (envelope constants,
    # deterministic_ulid, envelope_sha256, the status-envelope builder, and the
    # selection/audit seams) under public names for the import-history
    # pipeline. That pipeline was deleted with the sync transport (issue #5)
    # and the seam itself was pruned as dead collateral (issue #116); any new
    # cross-module consumer of these internals would need a fresh seam, not a
    # direct import.
    "CheckoutDisagreement",
    "MissionStateDryRunError",
    "MissionStateRepairError",
    "MissionStateWriteRefused",
    "TeamspaceDryRunReport",
    "audit_invocation_disagreement",
    "enforce_primary_write_ownership",
    "rebuild_mission_event_log",
    "repair_duplicate_key_artifacts",
    "repair_repo",
    "teamspace_dry_run",
]
