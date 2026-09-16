"""Runner for ``spec-kitty charter preflight`` (FR-006, FR-007, FR-008).

This module exposes a single public callable :func:`run_charter_preflight`
that:

1. Asks WP02's :func:`specify_cli.charter_runtime.freshness.compute_freshness` for
   the current freshness payload.
2. Translates each :class:`FreshnessSubState` into a
   :class:`CharterPreflightCheck`.
3. Optionally runs the safe refresh sequence (the freshness-computed
   ``charter_source`` remediation — ``charter generate`` or
   ``upgrade --yes``, never a hardcoded ``charter sync``, H1/#2831 — →
   ``charter synthesize`` → ``charter bundle validate``) when the caller
   passes ``auto_refresh=True`` AND the worktree has no uncommitted
   generated artifacts (FR-008). See :func:`_attempt_auto_refresh`'s
   docstring for why step one is no longer ``charter sync``.
4. Returns a frozen :class:`CharterPreflightResult` whose
   ``blocked_reason`` names one exact recovery command for every check that
   has one — and, for a check on the declared exemption set (no effective
   self-service remediation, C-EFF-2), names the check and explains why
   instead of fabricating a command it cannot act on (R-006).

Boundary heal semantics (WP04, charter-synthesize-reconciliation-01KZJQN6):
the ``charter synthesize`` call inside the refresh sequence is invoked
flagless — no ``--prune``, no ``--dry-run`` — which selects
``SynthesizeMode.preserve`` (the library default): a successful heal never
drops backed content, and ``synthesized_drg`` self-clears to ``fresh``
because ``rewrite_manifest`` re-stamps the manifest's
``bundle_content_hash`` on every write. This is a "never silently drops
content" guarantee, NOT a "never refuses" guarantee: orphaned
(backing-artifact-deleted) content and an unparseable on-disk doctrine
overlay still make the subprocess exit non-zero, and this runner surfaces
that as an actionable ``blocked_reason`` exactly like any other refresh
failure — it never coerces that outcome to ``passed=True``.

Performance contract (NFR-001):

* warm path (everything fresh) — < 300 ms;
* cold path (refresh runs) — < 1 s;
* dirty-detection (``git status --porcelain -- .kittify/charter/
  .kittify/doctrine/``) — < 100 ms on a clean tree.

The runner MUST NOT raise on filesystem or subprocess errors — every
failure produces a result with a sensible ``blocked_reason``.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.charter_runtime.preflight.ambient_warning import dedupe_warnings

from .result import CharterPreflightCheck, CharterPreflightResult, CheckState

if TYPE_CHECKING:  # pragma: no cover — used only for type hints.
    from specify_cli.charter_runtime.freshness import CharterFreshness

__all__ = ["SYNTHESIZED_DRG_LAYER", "run_charter_preflight"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


#: Canonical freshness-check name for the synthesized-DRG layer. This is the
#: single source of truth for the string ``"synthesized_drg"`` — both
#: ``_LAYER_ORDER`` below and ``references_refresh``'s references-parity
#: cause matching (:func:`references_refresh.is_references_parity_cause`)
#: consume this constant rather than re-declaring the literal, so a rename
#: here cannot silently desync the references-parity heal from the runner's
#: actual layer set.
SYNTHESIZED_DRG_LAYER = "synthesized_drg"

# Layer ordering is part of the contract — consumers MAY index by name but
# humans scanning ``--json`` output rely on this order.
_LAYER_ORDER: tuple[tuple[str, str], ...] = (
    ("charter_source", "charter source"),
    ("synced_bundle", "synced bundle"),
    (SYNTHESIZED_DRG_LAYER, "synthesized DRG"),
)

# Passing states — see contracts/charter-preflight-json.md "State semantics".
_PASS_STATES: frozenset[str] = frozenset({"fresh", "skipped", "built_in_only"})

_FRESH_PROJECT_MISSING_CHARTER_WARNING = (
    "project charter is not initialized; run `spec-kitty charter generate` "
    "when this project is ready for charter-governed workflows"
)

#: Distinct from ``_FRESH_PROJECT_MISSING_CHARTER_WARNING`` per FR-003 — a
#: legacy ``charter.md``-only bundle means governance intent already
#: existed and needs migration, not initial setup, so the message names the
#: legacy file and the exact migration command explicitly.
_LEGACY_CHARTER_BUNDLE_WARNING = (
    "a legacy charter.md-only bundle was detected "
    "(.kittify/charter/charter.md exists but .kittify/charter/charter.yaml "
    "does not); this project has governance intent that predates the "
    "charter.yaml bundle format — run "
    "`spec-kitty charter generate --no-from-interview` to migrate it forward"
)

# Refresh-step timeout.  Overridable via env so very slow CI runners can
# extend the deadline without code changes (risk note in WP03 spec).
_REFRESH_TIMEOUT_ENV = "SPEC_KITTY_PREFLIGHT_TIMEOUT_SECS"
_REFRESH_TIMEOUT_DEFAULT = 30.0

# git-status timeout — kept tight; NFR-001 wants this <100 ms on a clean
# tree, so a 5 s ceiling is purely a defensive cap against frozen FUSE
# mounts / hung antivirus hooks.
_GIT_STATUS_TIMEOUT_SECS = 5.0

# Paths whose dirty-state blocks auto-refresh.  Per FR-008 we name the
# directories rather than individual files so future additions under
# ``.kittify/charter/`` or ``.kittify/doctrine/`` are covered automatically.
_DIRTY_SCOPE_PATHS: tuple[str, ...] = (
    ".kittify/charter/",
    ".kittify/doctrine/",
)

# Shared prefix for the refresh-sequence subprocess commands that always
# stay under ``spec-kitty charter`` (#2157a campsite — S1192): ``synthesize``
# and ``bundle validate``. The tails differ, so only the common
# ``["spec-kitty", "charter"]`` tokens are hoisted; each call site appends
# its own tail. The step-one command (H1, #2831) is NOT built from this
# prefix — it is `shlex.split` straight from the freshness computer's own
# `remediation` string, which may or may not sit under `charter` (e.g.
# `spec-kitty upgrade --yes`).
_SPEC_KITTY_CHARTER_PREFIX: tuple[str, ...] = ("spec-kitty", "charter")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_charter_preflight(
    repo_root: Path,
    *,
    auto_refresh: bool = False,
    allow_missing_charter: bool = False,
    strict: bool = False,
) -> CharterPreflightResult:
    """Compute charter freshness, optionally refresh, return a result.

    In addition to the freshness layers, the result carries advisory
    ``warnings`` (never affecting ``passed``) for shipped mission-step
    default profiles the activation state has deactivated (#4115) — a
    project that deactivated e.g. ``researcher-robbie`` still reports
    FRESH on every freshness layer while its built-in missions are one
    dispatch away from a role fallback (or a blocked step when no
    same-role profile is activated); the warning names that state instead
    of leaving it invisible.

    Args:
        repo_root: Path to the repository root.  Must contain ``.kittify/``
            for non-trivial results; missing artifacts produce ``missing``
            checks rather than exceptions.
        auto_refresh: When ``True`` AND the worktree has no uncommitted
            generated artifacts, attempt the safe refresh sequence.
        allow_missing_charter: Treat a canonically missing charter stack as
            advisory. Dashboard, next, and implement enable this for projects
            that have no charter source or synced bundle and whose synthesized
            layer is either absent or built-in-only. Stale, invalid, or other
            partial state still fails closed.
        strict: Accepted for API symmetry with the CLI flag.  The runner
            itself does not change behaviour based on ``strict`` — the CLI
            wrapper translates ``passed=False`` + ``strict=True`` into exit
            code 1.  Kept in the signature so callers (``spec-kitty next``,
            ``implement``, dashboard) can forward their own ``strict``
            config without an extra branch.

    Returns:
        A frozen :class:`CharterPreflightResult`.  Never raises.
    """
    result = _run_charter_preflight_freshness(
        repo_root,
        auto_refresh=auto_refresh,
        allow_missing_charter=allow_missing_charter,
        strict=strict,
    )
    profile_warnings = _deactivated_mission_default_profile_warnings(repo_root)
    if not profile_warnings:
        return result
    return replace(result, warnings=[*result.warnings, *profile_warnings])


def _deactivated_mission_default_profile_warnings(repo_root: Path) -> list[str]:
    """#4115: advisory warnings for deactivated mission-step default profiles.

    Reads the three-state ``activated_agent_profiles`` set from project
    config: ``None`` (default-allow) is inert and yields no warnings; an
    explicit set yields one warning per
    ``mission_step_contracts.profile_defaults._ACTION_PROFILE_DEFAULTS``
    profile it does not contain. Never raises (the runner's own contract):
    a config that cannot be read produces no warnings and a DEBUG note, not
    a crash — a broken config is the freshness layers' problem to block on,
    not this advisory note's.
    """
    try:
        from charter.activation.pack_context import PackContext  # noqa: PLC0415

        activated = PackContext.from_config(repo_root).activated_agent_profiles
    except Exception:  # noqa: BLE001 — the never-raise contract above; the
        # freshness layers own fail-closed treatment of a malformed config.
        logger.debug(
            "could not read activation state for the mission-default-profile "
            "preflight warning at %s; skipping the advisory",
            repo_root,
        )
        return []
    if activated is None:
        return []
    from specify_cli.mission_step_contracts.profile_defaults import (  # noqa: PLC0415
        _ACTION_PROFILE_DEFAULTS,
        mission_default_profile_warning,
    )

    warnings: list[str] = []
    for profile_id in sorted(set(_ACTION_PROFILE_DEFAULTS.values())):
        if profile_id in activated:
            continue
        warning = mission_default_profile_warning(profile_id)
        if warning is not None:
            warnings.append(warning)
    return warnings


def _run_charter_preflight_freshness(
    repo_root: Path,
    *,
    auto_refresh: bool = False,
    allow_missing_charter: bool = False,
    strict: bool = False,
) -> CharterPreflightResult:
    """Freshness-only core of :func:`run_charter_preflight` (pre-#4115 body)."""
    del strict  # kept for caller symmetry; consumed by the CLI exit-code mapping, not by the runner itself.
    freshness = compute_freshness(repo_root)
    checks = _build_checks(freshness)

    # C-001 / FR-016: only canonical freshness states decide pass/block.
    # charter.md is display-only and may select advisory copy only after the
    # canonical state has independently qualified for the exemption.
    if allow_missing_charter and _is_optional_missing_charter_stack(checks):
        legacy_bundle = _is_legacy_charter_bundle(repo_root)
        return _advisory_missing_charter_result(
            checks,
            detail=(
                "legacy charter.md-only bundle; charter.yaml not yet migrated"
                if legacy_bundle
                else "project charter is not initialized"
            ),
            warning=(
                _LEGACY_CHARTER_BUNDLE_WARNING
                if legacy_bundle
                else _FRESH_PROJECT_MISSING_CHARTER_WARNING
            ),
        )

    passed = all(c.state in _PASS_STATES for c in checks)

    if passed:
        return CharterPreflightResult(
            passed=True,
            checks=checks,
            auto_refresh_applied=False,
            auto_refresh_actions=[],
            blocked_reason=None,
        )

    # Failure path.  Either refresh, or block.
    if auto_refresh:
        return _attempt_auto_refresh(repo_root, freshness, checks)

    blocked_reason = _derive_blocked_reason(checks)
    return CharterPreflightResult(
        passed=False,
        checks=checks,
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=blocked_reason,
    )


# ---------------------------------------------------------------------------
# Helpers — check construction
# ---------------------------------------------------------------------------


def _build_checks(freshness: CharterFreshness) -> list[CharterPreflightCheck]:
    """Convert the WP02 freshness payload into preflight checks.

    Mapping rules:

    * ``state`` is copied through directly.
    * ``detail`` is the WP02 ``detail`` when present, otherwise a synthesised
      human-readable string of the form ``"<layer> is <state>"``.
    * ``remediation`` is copied from WP02 (``None`` when no action is
      required).
    """
    result: list[CharterPreflightCheck] = []
    payload = freshness.to_dict()
    for layer_key, layer_label in _LAYER_ORDER:
        sub = payload[layer_key]
        # Fail-closed default: an absent ``state`` must NOT be advisory-eligible.
        # ``FreshnessSubState.state`` is always set today, so this only guards a
        # future freshness regression — but on a preflight safety gate the safe
        # fallback is a blocking value (``invalid``), never advisory-eligible
        # ``missing``.
        state = str(sub.get("state", "invalid"))
        detail = sub.get("detail") or _default_detail(layer_label, state, sub.get("last_change"))
        remediation = sub.get("remediation")
        result.append(
            CharterPreflightCheck(
                name=layer_key,
                # FreshnessState is a strict subset of CheckState and the fail-closed
                # "invalid" fallback above is itself a CheckState member, so the cast
                # narrows an honest value; it is not a suppression.
                state=cast(CheckState, state),
                detail=str(detail),
                remediation=str(remediation) if remediation else None,
            )
        )
    return result


def _is_optional_missing_charter_stack(checks: list[CharterPreflightCheck]) -> bool:
    """Return True only for canonically safe missing-charter states.

    The source and synced bundle must both be absent. The synthesized layer
    may also be absent, or may be ``built_in_only`` (a passing state carrying
    no project charter content). Any stale, invalid, or other partial residue
    remains blocking.
    """
    states = {c.name: c.state for c in checks}
    return (
        states.get("charter_source") == "missing"
        and states.get("synced_bundle") == "missing"
        and states.get("synthesized_drg") in {"missing", "built_in_only"}
    )


def _is_legacy_charter_bundle(repo_root: Path) -> bool:
    """Return whether display-only legacy prose exists for advisory copy.

    A project may carry governance intent captured in
    ``.kittify/charter/charter.md`` from before the charter.yaml-based
    bundle inversion. This predicate runs only after
    ``_is_optional_missing_charter_stack`` has decided the outcome from
    canonical freshness state. It chooses warning text and never changes
    pass/block behavior.

    NFR-001: this adds exactly one additional filesystem existence check
    (``Path.exists()`` on ``charter.md``) beyond the existing freshness
    computation.

    FR-016 clause (b): this allow-listed ``.exists()`` call is an
    informational readout, matching ``_collect_charter_sync_status``; the
    canonical state predicate above has already fixed the outcome.
    """
    # Keep this chokepoint import off the `next` startup path. Importing any
    # charter.* submodule executes charter.__init__ and its heavyweight graph.
    from charter.bundle import CHARTER_MD

    return bool((repo_root / CHARTER_MD).exists())


def _advisory_missing_charter_result(
    checks: list[CharterPreflightCheck],
    *,
    detail: str,
    warning: str,
) -> CharterPreflightResult:
    """Build the shared "advisory, not blocking" missing-charter result shape.

    Both warning presentations of the canonical missing-charter exemption
    produce an identical result shape (every check marked ``"skipped"``, no
    ``blocked_reason``) differing only in the per-check ``detail`` text and
    which warning constant is attached — factored out once a second call
    site made the duplication real (DIRECTIVE_025 Boy Scout Rule).

    #3971: the ``warnings`` list is de-duplicated at birth
    (:func:`ambient_warning.dedupe_warnings`) so every consumer — the stderr
    seam, the dashboard's persisted banner, the JSON contract — receives a
    duplicate-free list without each having to re-filter.
    """
    return CharterPreflightResult(
        passed=True,
        checks=[
            CharterPreflightCheck(
                name=c.name,
                state="skipped",
                detail=detail,
                remediation=None,
            )
            for c in checks
        ],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
        warnings=dedupe_warnings([warning]),
    )


def _default_detail(label: str, state: str, last_change: str | None) -> str:
    """Build a fallback detail string when WP02 does not supply one."""
    base = f"{label} is {state}"
    if last_change:
        return f"{base} (last_change={last_change})"
    return base


def _derive_blocked_reason(checks: list[CharterPreflightCheck]) -> str:
    """Enumerate every non-passing check into one ``blocked_reason`` string.

    #2157a: previously this picked only the FIRST non-passing check, which
    made the operator fix charter-owed prerequisites one at a time (fix,
    re-run, discover the next). It now reports every non-passing check in
    ``checks`` order so a single pass surfaces the whole remediation list.

    Per-check formatting is unchanged from the prior single-check behaviour
    for a check that names a remediation (``"<name> <state>; run
    `<remediation>`"``) — for exactly one non-passing check this still
    returns that identical single-line string; for multiple, the lines are
    joined with a newline into one string (the ``blocked_reason`` field
    stays a single ``str`` — see the output-shape pin in ``result.py``).

    R-006 / C-EFF-2: a check with ``remediation is None`` used to have a
    default command (``spec-kitty charter status``, itself a pure reporter
    that cannot change any check's state) fabricated in its place — the
    same defect class as BC-2, sitting on the default path. That backfill is
    gone: see :func:`_blocked_reason_line`.
    """
    lines = [_blocked_reason_line(check) for check in checks if check.state not in _PASS_STATES]
    if not lines:
        # Should not happen — callers only enter this path when passed=False.
        return "charter preflight failed; no non-passing check found (internal inconsistency)"
    return "\n".join(lines)


def _blocked_reason_line(check: CharterPreflightCheck) -> str:
    """Compose one ``blocked_reason`` line for a single non-passing check.

    When the check names a remediation, the operator is shown the exact
    command (unchanged from prior behaviour). When ``remediation`` is
    ``None`` the check is a declared exemption (C-EFF-2) — the operator
    still learns which check failed, its state, and why (``check.detail``),
    but no command is manufactured in its place (R-006). This must not
    degrade to a silent or empty line — the diagnostic stays, only the
    fabricated command goes.
    """
    if check.remediation:
        return f"{check.name} {check.state}; run `{check.remediation}`"
    return f"{check.name} {check.state}: {check.detail}"


# ---------------------------------------------------------------------------
# Helpers — uncommitted-artifact detection (FR-008 / T018)
# ---------------------------------------------------------------------------


def _detect_dirty_artifacts(repo_root: Path) -> tuple[bool, list[str], str | None]:
    """Return ``(is_dirty, dirty_paths, error_reason)``.

    Implements the binding detection mechanism documented in
    ``contracts/charter-preflight-json.md`` §"Detection mechanism": a
    single ``git status --porcelain`` invocation scoped to the two
    directories we care about, parsed line-by-line.

    Failure-mode handling:

    * ``FileNotFoundError`` (git missing) → ``error_reason`` =
      ``"git CLI not available; cannot determine worktree cleanliness"``;
      ``is_dirty=False``.
    * ``returncode != 0`` → ``error_reason`` =
      ``"git status failed (exit N): <first stderr line>"``;
      ``is_dirty=False``.
    * Non-empty stdout → ``is_dirty=True``; ``dirty_paths`` lists every
      pathname reported (path component starts at column 4 in porcelain
      v1 output).
    """
    try:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                *_DIRTY_SCOPE_PATHS,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_STATUS_TIMEOUT_SECS,
            check=False,
        )
    except FileNotFoundError:
        return False, [], "git CLI not available; cannot determine worktree cleanliness"
    except subprocess.TimeoutExpired:
        return False, [], "git status timed out; cannot determine worktree cleanliness"

    if result.returncode != 0:
        stderr_first = ""
        if result.stderr:
            stderr_first = result.stderr.splitlines()[0] if result.stderr.splitlines() else ""
        return (
            False,
            [],
            f"git status failed (exit {result.returncode}): {stderr_first}".rstrip(": "),
        )

    if not result.stdout.strip():
        return False, [], None

    dirty_paths: list[str] = []
    for raw_line in result.stdout.splitlines():
        # Porcelain v1: ``XY <path>`` where ``XY`` is exactly two status
        # chars + a space.  Slicing at index 3 is the documented contract.
        if len(raw_line) <= 3:
            continue
        dirty_paths.append(raw_line[3:].strip())
    return True, dirty_paths, None


# ---------------------------------------------------------------------------
# Helpers — auto-refresh (T019)
# ---------------------------------------------------------------------------


def _refresh_timeout_secs() -> float:
    """Resolve the per-step refresh timeout from env, falling back to 30 s."""
    raw = os.environ.get(_REFRESH_TIMEOUT_ENV)
    if not raw:
        return _REFRESH_TIMEOUT_DEFAULT
    try:
        value = float(raw)
    except ValueError:
        return _REFRESH_TIMEOUT_DEFAULT
    if value <= 0:
        return _REFRESH_TIMEOUT_DEFAULT
    return value


def refresh_references_if_needed(repo_root: Path, cause: str) -> bool:
    """References-parity extension point (T019 install / WP06 implement, #2777).

    Delegates to :func:`specify_cli.charter_runtime.preflight.
    references_refresh.refresh_references_if_needed`, WP06's implementation
    of the real references-parity ``generate`` call (FR-011). The import is
    deferred to call time — not module-import time — so this rarely-taken
    branch does not grow ``run_charter_preflight``'s hot-path import surface
    (mirrors the lazy-import discipline this package already uses for
    ``charter.bundle``/``charter.activation.synthesizer`` elsewhere, LD-3/NFR-003).

    Args:
        repo_root: Repository root the just-completed heal ran against.
        cause: Comma-joined names of the freshness checks that triggered the
            heal (e.g. ``"synthesized_drg"``). See ``references_refresh``'s
            module docstring for why ``synthesized_drg`` is the
            references-parity signal.

    Returns:
        ``True`` iff a targeted ``generate`` was attempted (i.e. *cause*
        named the references-parity layer) — the caller uses this to decide
        whether ``charter.yaml``'s derived catalog may have just changed and
        the synthesis manifest needs re-stamping (MAJOR-1, WP06 rejection
        cycle 1) before the post-refresh freshness recompute. ``False`` for
        a non-references-parity cause (true no-op, nothing to re-stamp).
    """
    from .references_refresh import refresh_references_if_needed as _refresh_references

    result: bool = _refresh_references(repo_root, cause)
    return result


def _attempt_auto_refresh(
    repo_root: Path,
    freshness: CharterFreshness,
    initial_checks: list[CharterPreflightCheck],
) -> CharterPreflightResult:
    """Run the safe refresh sequence, honouring FR-008 cleanliness.

    The sequence is:

    1. The freshness-computed ``charter_source`` remediation — skipped iff
       both ``charter_source`` and ``synced_bundle`` are already ``fresh``.
       H1 (#2831 HIGH finding): this used to be a hardcoded
       ``spec-kitty charter sync``, but ``charter sync`` is a pure
       staleness reporter (``src/charter/sync.py``'s own docstring: "it
       always reports ``synced=False`` / ``files_written=[]``") that can
       never create or repair ``charter.yaml`` — so for a missing or
       invalid ``charter_source`` this step always failed and the sequence
       stopped here, never reaching ``synthesize``/``bundle validate`` (a
       real F2 legacy-bundle probe: auto-refresh ran only ``sync``, exited
       1, left every state unchanged). This step now runs whatever command
       :func:`~specify_cli.charter_runtime.freshness.computer.compute_freshness`
       already derived for ``charter_source`` (H3's F1/F2-aware
       ``remediation`` — ``spec-kitty charter generate --no-from-interview``
       for "no charter at all", ``spec-kitty upgrade --yes`` for a legacy
       bundle) — the same command the non-refresh blocking path shows the
       operator, so auto-refresh can never claim to have "tried" something
       the operator's own ``blocked_reason`` already proves is a no-op.
       When ``remediation`` is ``None`` (the ``invalid``/cascading-``stale``
       exempt states, C-EFF-2 — no write path repairs broken or
       non-bundle-shaped YAML), no command is attempted; the sequence stops
       and surfaces the check's own detail, exactly like the non-refresh
       blocking path does for the same exempt states.
    2. ``spec-kitty charter synthesize`` — skipped iff ``synthesized_drg``
       is already ``fresh``.
    3. ``spec-kitty charter bundle validate`` — always run when we reach
       this branch.
    4. ``refresh_references_if_needed`` (WP06, #2777) — a targeted
       ``spec-kitty charter generate``, gated on the references-parity
       cause. When it fires, step 5 (below) re-runs ``synthesize`` once
       more to re-stamp the manifest against generate's rewritten
       ``charter.yaml`` — see that step's own comment for why.

    On any non-zero exit, we stop, surface the failing command's first
    stderr line via ``blocked_reason``, and mark
    ``auto_refresh_applied=True`` so callers know an attempt was made
    even when it failed.
    """
    is_dirty, dirty_paths, dirty_error = _detect_dirty_artifacts(repo_root)

    if dirty_error is not None:
        return CharterPreflightResult(
            passed=False,
            checks=initial_checks,
            auto_refresh_applied=False,
            auto_refresh_actions=[],
            blocked_reason=dirty_error,
        )

    if is_dirty:
        annotated = _annotate_dirty(initial_checks, dirty_paths)
        return CharterPreflightResult(
            passed=False,
            checks=annotated,
            auto_refresh_applied=False,
            auto_refresh_actions=[],
            blocked_reason="uncommitted generated artifacts; commit or stash and retry",
        )

    # Worktree is clean — run the sequence.
    actions: list[str] = []
    timeout_secs = _refresh_timeout_secs()

    source_fresh = freshness.charter_source.state == "fresh"
    bundle_fresh = freshness.synced_bundle.state == "fresh"
    drg_fresh = freshness.synthesized_drg.state == "fresh"

    if not (source_fresh and bundle_fresh):
        # H1 (#2831 HIGH finding): run the SAME command the freshness
        # computer already derived for this exact state — never a
        # hardcoded `charter sync` (a pure staleness reporter that can
        # never create/repair `charter.yaml`, see this function's
        # docstring). `synced_bundle` mirrors `charter_source`'s F1/F2
        # answer whenever it differs from fresh, so `charter_source`'s
        # remediation is authoritative here; the `or` is a defensive
        # fallback only.
        source_remediation = freshness.charter_source.remediation or freshness.synced_bundle.remediation
        if source_remediation is None:
            # Exempt state (`invalid` charter.yaml / cascading `stale`
            # synced_bundle, C-EFF-2) — no command can repair this. Stop
            # here rather than run something known to be a no-op.
            return CharterPreflightResult(
                passed=False,
                checks=initial_checks,
                auto_refresh_applied=True,
                auto_refresh_actions=actions,
                blocked_reason=_derive_blocked_reason(initial_checks),
            )
        source_cmd = shlex.split(source_remediation)
        ok, reason = _run_refresh_step(source_cmd, repo_root, timeout_secs)
        actions.append(source_remediation)
        if not ok:
            return CharterPreflightResult(
                passed=False,
                checks=initial_checks,
                auto_refresh_applied=True,
                auto_refresh_actions=actions,
                blocked_reason=reason,
            )

    if not drg_fresh:
        # WP04: flagless invocation — no --prune, no --dry-run — selects
        # SynthesizeMode.preserve (the library default). See the module
        # docstring's "Boundary heal semantics" section: this never drops
        # backed content, but orphaned/unparseable causes still exit
        # non-zero and are surfaced below via `reason`, never swallowed.
        synth_cmd = [*_SPEC_KITTY_CHARTER_PREFIX, "synthesize"]
        ok, reason = _run_refresh_step(synth_cmd, repo_root, timeout_secs)
        actions.append(" ".join(synth_cmd))
        if not ok:
            return CharterPreflightResult(
                passed=False,
                checks=initial_checks,
                auto_refresh_applied=True,
                auto_refresh_actions=actions,
                blocked_reason=reason,
            )

    validate_cmd = [*_SPEC_KITTY_CHARTER_PREFIX, "bundle", "validate"]
    ok, reason = _run_refresh_step(validate_cmd, repo_root, timeout_secs)
    actions.append(" ".join(validate_cmd))
    if not ok:
        return CharterPreflightResult(
            passed=False,
            checks=initial_checks,
            auto_refresh_applied=True,
            auto_refresh_actions=actions,
            blocked_reason=reason,
        )

    # References-parity extension point (WP04 install / WP06 implement,
    # #2777): fires a targeted `generate` once the refresh sequence has
    # succeeded, before the post-refresh freshness recompute. Gated, not
    # unconditional — `synthesized_drg` is the post-#2759 proxy for
    # "references-parity drift" (the stand-alone parity check it used to
    # name is retired; see `references_refresh`'s module docstring), so this
    # only fires when the ORIGINAL stale-cause set actually named that
    # layer.
    stale_cause = ",".join(sorted({c.name for c in initial_checks if c.state not in _PASS_STATES}))
    references_refreshed = refresh_references_if_needed(repo_root, cause=stale_cause)

    if references_refreshed:
        # MAJOR-1 (WP06 rejection cycle 1): `generate` rewrites
        # `charter.yaml`'s derived catalog but — unlike `synthesize` — never
        # re-stamps the synthesis manifest's `bundle_content_hash` itself.
        # Left alone, the freshness recompute below would then see
        # stored_hash (pre-generate) != current_hash (post-generate) and
        # report `synthesized_drg="stale"`, turning a heal that genuinely
        # succeeded into `passed=False`. Re-running the same flagless
        # `synthesize` step (`SynthesizeMode.preserve`, never --prune/
        # --dry-run) re-stamps the manifest against the NEW `charter.yaml`
        # — the same self-clearing mechanism the module docstring's
        # "Boundary heal semantics" section already documents for the
        # first synthesize call — so the recompute below sees a
        # manifest-coherent state.
        restamp_cmd = [*_SPEC_KITTY_CHARTER_PREFIX, "synthesize"]
        ok, reason = _run_refresh_step(restamp_cmd, repo_root, timeout_secs)
        actions.append(" ".join(restamp_cmd))
        if not ok:
            return CharterPreflightResult(
                passed=False,
                checks=initial_checks,
                auto_refresh_applied=True,
                auto_refresh_actions=actions,
                blocked_reason=reason,
            )

    # Refresh succeeded — recompute freshness and rebuild checks so
    # callers see the post-refresh state.
    post_freshness = compute_freshness(repo_root)
    post_checks = _build_checks(post_freshness)
    post_passed = all(c.state in _PASS_STATES for c in post_checks)

    return CharterPreflightResult(
        passed=post_passed,
        checks=post_checks,
        auto_refresh_applied=True,
        auto_refresh_actions=actions,
        blocked_reason=None if post_passed else _derive_blocked_reason(post_checks),
    )


def _annotate_dirty(
    checks: list[CharterPreflightCheck],
    dirty_paths: list[str],
) -> list[CharterPreflightCheck]:
    """Append the dirty pathnames to the matching check's ``detail``.

    Per FR-008 and the contract's Safety-rule section: each affected file
    MUST be named in the ``detail`` of the corresponding check.  We bucket
    by directory prefix so ``.kittify/charter/...`` lands on the
    ``charter_source`` / ``synced_bundle`` rows and ``.kittify/doctrine/...``
    on ``synthesized_drg``.
    """
    charter_dirty = [p for p in dirty_paths if p.startswith(".kittify/charter/")]
    doctrine_dirty = [p for p in dirty_paths if p.startswith(".kittify/doctrine/")]

    annotated: list[CharterPreflightCheck] = []
    for c in checks:
        suffix: str | None = None
        if c.name in ("charter_source", "synced_bundle") and charter_dirty:
            suffix = "uncommitted: " + ", ".join(charter_dirty)
        elif c.name == "synthesized_drg" and doctrine_dirty:
            suffix = "uncommitted: " + ", ".join(doctrine_dirty)
        if suffix:
            annotated.append(
                CharterPreflightCheck(
                    name=c.name,
                    state=c.state,
                    detail=f"{c.detail}; {suffix}",
                    remediation=c.remediation,
                )
            )
        else:
            annotated.append(c)
    return annotated


def _run_refresh_step(
    cmd: list[str],
    repo_root: Path,
    timeout_secs: float,
) -> tuple[bool, str | None]:
    """Run one refresh subprocess.

    Returns ``(ok, blocked_reason_or_none)``.  On non-zero exit, the reason
    is the first stderr line, prefixed with the command's tail (e.g.
    ``"charter synthesize failed: <stderr>"``) so the operator can copy the
    fix straight into a terminal.
    """
    label = " ".join(cmd[1:]) if len(cmd) > 1 else cmd[0]
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            check=False,
        )
    except FileNotFoundError:
        return False, f"{cmd[0]} not on PATH; cannot run `{' '.join(cmd)}`"
    except subprocess.TimeoutExpired:
        return False, f"`{' '.join(cmd)}` timed out after {timeout_secs:.0f}s"

    if result.returncode == 0:
        return True, None

    stderr_first = ""
    if result.stderr:
        lines = result.stderr.splitlines()
        if lines:
            stderr_first = lines[0]
    if not stderr_first and result.stdout:
        stdout_lines = result.stdout.splitlines()
        if stdout_lines:
            stderr_first = stdout_lines[-1]
    return False, f"{label} failed (exit {result.returncode}): {stderr_first}".rstrip(": ")
