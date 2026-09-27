"""Hosted-readiness evaluator for the SaaS-backed tracker providers.

Re-homed from ``specify_cli.saas.readiness`` when that package died with the
sync transport (issue #5); only its two deleted imports were repointed.
Stability contract: ``kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/hosted_readiness.md``

Every non-``READY`` state produces a ``ReadinessResult`` whose ``message`` names the
missing prerequisite explicitly (NFR-002) and whose ``next_action`` gives one
concrete actionable step.  Wording is frozen in ``_WORDING`` and asserted
byte-for-byte by ``tests/saas/test_readiness_unit.py``.

Call :func:`evaluate_readiness` with keyword-only arguments; it **never raises** —
any unexpected exception is converted into a ``HOST_UNREACHABLE`` result with
the exception type in ``details["error"]``.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from collections.abc import Mapping


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ReadinessState(StrEnum):
    """Discrete readiness states in check order.

    The evaluator checks states in *declaration order* — cheapest and most
    consequential first.  The first failing state short-circuits the chain.
    Adding new members is additive; removing or renaming requires a follow-up
    mission.
    """

    ROLLOUT_DISABLED = "rollout_disabled"
    MISSING_AUTH = "missing_auth"
    MISSING_HOST_CONFIG = "missing_host_config"
    AMBIGUOUS_HOST_CONFIG = "ambiguous_host_config"
    HOST_UNREACHABLE = "host_unreachable"
    MISSING_MISSION_BINDING = "missing_mission_binding"
    READY = "ready"


@dataclass(frozen=True)
class ReadinessResult:
    """Immutable snapshot of the hosted-readiness evaluation.

    ``is_ready`` is a convenience property; callers should switch on ``state``
    for structured handling.
    """

    state: ReadinessState
    message: str
    next_action: str | None
    details: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """True iff ``state`` is :attr:`ReadinessState.READY`."""
        return self.state is ReadinessState.READY


# ---------------------------------------------------------------------------
# Stable failure-message catalog (module-private)
# ---------------------------------------------------------------------------
#
# Each entry is (message_template, next_action_template).  Entries for
# HOST_UNREACHABLE and MISSING_MISSION_BINDING contain ``{server_url}`` /
# ``{feature_slug}`` placeholders, resolved at construction time by
# ``_build_result``.  Do not use f-strings here — keep the catalog as plain
# string literals so tests can assert them byte-for-byte.

_WORDING: dict[ReadinessState, tuple[str, str]] = {
    ReadinessState.ROLLOUT_DISABLED: (
        "Hosted SaaS sync is disabled on this machine.",
        "Unset `SPEC_KITTY_ENABLE_SAAS_SYNC` (or set it to `1`) to re-enable it.",
    ),
    ReadinessState.MISSING_AUTH: (
        "No SaaS authentication token is present.",
        "Run `spec-kitty auth login`.",
    ),
    ReadinessState.MISSING_HOST_CONFIG: (
        "No SaaS host URL is configured.",
        "Set `SPEC_KITTY_SAAS_URL` in your environment.",
    ),
    ReadinessState.AMBIGUOUS_HOST_CONFIG: (
        "SaaS host configuration is ambiguous: `config.toml` names `{configured_server_url}` while `SPEC_KITTY_SAAS_URL` names `{env_server_url}`.",
        "Reconcile the two: update `config.toml`'s `[sync].server_url` to match, or change/unset `SPEC_KITTY_SAAS_URL`, so both name the same host.",
    ),
    ReadinessState.HOST_UNREACHABLE: (
        "The configured SaaS host did not respond within 2 seconds.",
        "Check network connectivity to `{server_url}` and retry.",
    ),
    ReadinessState.MISSING_MISSION_BINDING: (
        "No tracker binding exists for feature `{feature_slug}`.",
        "Run `spec-kitty tracker bind` from this repo.",
    ),
}


def _build_result(state: ReadinessState, **fmt_kwargs: str) -> ReadinessResult:
    """Look up wording, format placeholders, and return a ``ReadinessResult``.

    For ``READY``, returns a result with empty ``message`` and ``None``
    ``next_action`` — no lookup needed.
    """
    if state is ReadinessState.READY:
        return ReadinessResult(state=state, message="", next_action=None)

    message_tmpl, next_action_tmpl = _WORDING[state]
    message = message_tmpl.format(**fmt_kwargs) if fmt_kwargs else message_tmpl
    next_action = next_action_tmpl.format(**fmt_kwargs) if fmt_kwargs else next_action_tmpl
    return ReadinessResult(state=state, message=message, next_action=next_action)


# ---------------------------------------------------------------------------
# Private probe helpers (no-raise contract)
# ---------------------------------------------------------------------------
#
# Each helper catches its own exceptions and returns a signal value.  They are
# module-level so unit tests can monkeypatch them via
# ``monkeypatch.setattr("specify_cli.tracker.saas_readiness._probe_auth", ...)``.


def _probe_rollout() -> bool:
    """Return True iff SaaS sync is enabled via the environment variable."""
    from specify_cli.core.saas_sync_config import is_saas_sync_enabled  # avoid circular at module level

    try:
        return bool(is_saas_sync_enabled())
    except Exception:
        return False


def _probe_auth(repo_root: Path) -> bool:
    """Return True iff the process-wide TokenManager reports an active session.

    Monkeypatch target for unit tests:
        ``specify_cli.tracker.saas_readiness._probe_auth``

    The ``repo_root`` parameter is accepted for API consistency and may be
    used by future callers that need per-repo credential isolation.  The
    current TokenManager is process-wide (``specify_cli.auth.get_token_manager``).
    """
    # ``repo_root`` is reserved for future per-repo credential isolation.
    _ = repo_root
    try:
        from specify_cli.auth import get_token_manager  # local import — auth may not be in path

        return bool(get_token_manager().is_authenticated)
    except Exception:
        return False


def _probe_host_config() -> str | None:
    """Return the resolved SaaS base URL, or ``None`` if it cannot be resolved.

    Two invariants are reconciled here:

    * **Endpoint opt-in (mission ``hosted-opt-in-drain-ledger``, FR-011/
      FR-012, reversing #3980 D-5)**: ``SPEC_KITTY_SAAS_URL`` is the env
      override and ``config.toml [sync].server_url`` the per-machine
      configured target — there is no packaged default target any more.
      With neither set the resolver raises ``HostedEndpointUnconfigured``,
      which this function's own tolerant except (below) degrades to
      ``None``, so the "env var/config unset ⇒ ``MISSING_HOST_CONFIG``" gate
      is restored (T028 item 4: this file needed no code change for that —
      the pre-existing broad ``except Exception`` already covered it).
    * **Target authority** (WP02, contract §1): the URL returned is the
      canonical ``resolved_server_url`` from
      :func:`~specify_cli.auth.server_target.resolve_server_target`, i.e. the
      **same** target the hosted surfaces key off. So readiness can never
      green-light a different URL than they use, even when the env var
      overrides ``config.toml`` (SC-008).

    No-raise contract, with one named exception: any failure degrades to
    ``None`` (treated as an absent host) rather than propagating, **except**
    :class:`~specify_cli.auth.server_target.ServerTargetSplitBrainError`, which
    propagates so the caller can report ``AMBIGUOUS_HOST_CONFIG`` with both
    disagreeing URLs named instead of the misleading ``MISSING_HOST_CONFIG``
    remedy (#305 — the operator has already set ``SPEC_KITTY_SAAS_URL``, so
    telling them to set it again is a dead end).
    """
    from specify_cli.auth.server_target import ServerTargetSplitBrainError, resolve_server_target

    try:
        # process_wide_override=False (#117): readiness is a no-human-in-the-loop
        # probe, so an ambiguous env/config disagreement must fail closed rather
        # than silently reporting the env-overridden URL as ready. Unlike other
        # resolution failures, this one is let through (see docstring) so the
        # evaluator can name both URLs instead of degrading to ``None``.
        return str(resolve_server_target(process_wide_override=False).resolved_server_url)
    except ServerTargetSplitBrainError:
        raise
    except Exception:
        return None


def _probe_reachability(server_url: str, timeout_s: float = 2.0) -> bool:
    """Return True iff a HEAD request to ``server_url`` succeeds within the budget.

    Uses only ``urllib.request`` (stdlib) so there is no dependency on
    ``httpx`` / ``requests`` here.  Any exception — connection refused, DNS
    failure, timeout, etc. — returns ``False``.
    """
    try:
        req = urllib.request.Request(server_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_s):  # nosec B310
            return True
    except Exception:
        return False


def _probe_mission_binding(repo_root: Path) -> bool:
    """Return True iff a tracker binding exists in ``repo_root``.

    Delegates to ``specify_cli.tracker.config.load_tracker_config`` — the
    same path used by tracker CLI commands.  Returns ``False`` if no binding
    is configured or if any error occurs.
    """
    try:
        from specify_cli.tracker.config import load_tracker_config

        config = load_tracker_config(repo_root)
        return bool(config.is_configured)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public evaluator
# ---------------------------------------------------------------------------


def evaluate_readiness(
    *,
    repo_root: Path,
    feature_slug: str | None = None,
    require_mission_binding: bool = False,
    probe_reachability: bool = False,
) -> ReadinessResult:
    """Evaluate all hosted-sync prerequisites in contract-defined order.

    Returns a :class:`ReadinessResult` whose ``state`` identifies the first
    failing prerequisite (or ``READY`` when all pass).  **Never raises** —
    any unexpected exception inside the evaluator body is converted to a
    ``HOST_UNREACHABLE`` result with ``details["error"]`` set to the exception
    type name.

    Check order (short-circuits on first failure):

    1. Rollout gate (``SPEC_KITTY_ENABLE_SAAS_SYNC`` — opt-out-only, #3980)
    2. Auth (``TokenManager.is_authenticated``)
    3. Host config (``resolve_server_target``: env override over
       ``config.toml [sync].server_url``; neither set yields
       ``MISSING_HOST_CONFIG``); an env/``config.toml`` disagreement yields
       ``AMBIGUOUS_HOST_CONFIG`` instead (#305)
    4. Reachability — only when ``probe_reachability=True``
    5. Mission binding — only when ``require_mission_binding=True``
    6. ``READY``

    Args:
        repo_root: Absolute path to the repository root; used to locate auth,
            config, and tracker bindings.
        feature_slug: Active feature slug.  Required when
            ``require_mission_binding=True`` (otherwise ignored).
        require_mission_binding: When ``True``, an absent tracker binding
            causes ``MISSING_MISSION_BINDING``; otherwise binding is not
            checked.
        probe_reachability: When ``True``, issue a single bounded HTTP
            ``HEAD`` against the configured URL.  Adds up to 2 seconds of
            latency; omit for fast local-only checks.

    Returns:
        A frozen :class:`ReadinessResult`.
    """
    from specify_cli.auth.server_target import ServerTargetSplitBrainError

    try:
        # Step 1: rollout gate
        if not _probe_rollout():
            return _build_result(ReadinessState.ROLLOUT_DISABLED)

        # Step 2: auth
        if not _probe_auth(repo_root):
            return _build_result(ReadinessState.MISSING_AUTH)

        # Step 3: host config — also captures server_url for later steps
        try:
            server_url = _probe_host_config()
        except ServerTargetSplitBrainError as exc:
            return _build_result(
                ReadinessState.AMBIGUOUS_HOST_CONFIG,
                configured_server_url=exc.configured_server_url or "(unset)",
                env_server_url=exc.env_server_url or "(unset)",
            )
        if server_url is None:
            return _build_result(ReadinessState.MISSING_HOST_CONFIG)

        # Step 4: reachability (optional)
        if probe_reachability and not _probe_reachability(server_url):
            return _build_result(ReadinessState.HOST_UNREACHABLE, server_url=server_url)

        # Step 5: mission binding (optional)
        if require_mission_binding and not _probe_mission_binding(repo_root):
            return _build_result(
                ReadinessState.MISSING_MISSION_BINDING,
                feature_slug=feature_slug or "",
            )

        # All applicable checks passed.
        return _build_result(ReadinessState.READY)

    except Exception as exc:
        return ReadinessResult(
            state=ReadinessState.HOST_UNREACHABLE,
            message=_WORDING[ReadinessState.HOST_UNREACHABLE][0],
            next_action=_WORDING[ReadinessState.HOST_UNREACHABLE][1].format(server_url=""),
            details={"error": type(exc).__name__},
        )
