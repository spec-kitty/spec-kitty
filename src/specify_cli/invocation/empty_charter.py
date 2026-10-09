"""Empty-charter generic-agent routing fallback (WP02, #3064; WP01, #3104).

Seam: called ONLY from the executor's auto-route branch
(``ProfileInvocationExecutor.invoke`` -- the ``elif self._router is not None:``
no-profile-hint path). This module is a surgical pre-check that short-circuits
before ``ActionRouter.route()`` when the project charter is wholly empty --
it does NOT touch the shared activation gate (``charter/resolver.py``) or
``ProfileRegistry``, so explicit ``--profile <specialist>`` dispatch under an
empty charter still resolves normally (research.md Decision 2).

Bundle-presence + org-pack-safe predicate (research.md "The dispatch predicate
(#3104) -- corrected, org-pack-safe", #3104 fix): "empty charter" means the
*compiled* charter bundle is ABSENT **and** nothing else makes the project
router-routable --

- ``.kittify/charter/charter.yaml`` (the compiled bundle) does not exist.
  Presence-only: bundle *contents* are never inspected here (a bootstrapped-
  empty bundle still counts as "configured" -- re-importing the #3064
  exhaustiveness trap of inspecting activations inside an existing bundle is
  exactly what this predicate must not do).
- ``PackContext.org_roots == ()`` (no org/project packs registered -- an org
  pack makes the router reach org-provided profiles even without a bundle).
- ``PackContext.activated_agent_profiles is None`` (no explicit agent-profile
  activation -- an explicit `frozenset()` opt-out is still "configured" per
  the three-state semantics ``PackContext`` already carries).

This intentionally drops the non-routing dimensions (directives, tactics,
toolguides, procedures, paradigms, styleguides, mission-step-contracts,
glossary-packs) that the pre-#3104 composite predicate weighed -- none of
them make ``ActionRouter.route()`` able to resolve a profile it otherwise
couldn't, so keeping them in the predicate only produced the #3104 defect
(applying a preset writes activation keys with no bundle and no profile
activation, which used to flip the net off and hand back a bare
``ROUTER_NO_MATCH`` -- worse than the fully empty case it was supposed to
guard). Folds #3118 (previously two config loads: ``charter_activated_urns``
plus ``PackContext.from_config``) into at most one ``PackContext.from_config``
call, only reached when the bundle-presence check already returned False.

Pure of side effects beyond the reads ``Path.exists`` and
``PackContext.from_config`` already perform -- no writes, no logging, no I/O
beyond a `stat()` on the bundle path and (when absent) reading
``.kittify/config.yaml``.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.pack_context import PackContext
from charter.profiles import DEFAULT_ROLE_CAPABILITIES, Role
from specify_cli.invocation.router import CANONICAL_VERB_MAP, RouterDecision, _normalize_tokens

#: Built-in profile pinned when the charter is wholly empty (Decision 2/3).
GENERIC_AGENT_ID = "generic-agent"

#: Repo-relative path to the compiled charter bundle (the read authority --
#: see ``charter.bundle.CHARTER_YAML``, not imported directly here to avoid
#: pulling in that module's pydantic-backed manifest machinery for a single
#: path literal this module only ever calls ``.exists()`` on).
_CHARTER_BUNDLE_PATH = Path(".kittify/charter/charter.yaml")

#: Human-readable reason recorded on the resulting ``RouterDecision`` --
#: surfaced by ``dispatch.py``'s warning panel and useful for audit trails.
_MATCH_REASON = (
    "empty charter: no compiled charter bundle (.kittify/charter/charter.yaml), "
    "no org/project pack, and no explicit agent-profile activation found"
)


def is_charter_empty(repo_root: Path) -> bool:
    """Return ``True`` iff the project is wholly un-routable (#3104 fix).

    See module docstring for the bundle-presence + org-pack-safe predicate.
    A compiled bundle answers "configured" on its own (presence only -- never
    inspect its contents); absent that, an org pack or an explicit
    agent-profile activation still makes the router routable, so the net must
    stay disengaged for those too (the org-pack-safety regression guard).
    """
    if (repo_root / _CHARTER_BUNDLE_PATH).exists():
        return False
    pack_context = PackContext.from_config(repo_root)
    if pack_context.org_roots != ():
        return False
    return pack_context.activated_agent_profiles is None


def _derive_fallback_action(request_text: str) -> str:
    """Derive the canonical action from the request verb.

    Reuses the router's own tokenizer and ``CANONICAL_VERB_MAP`` (ADR-3) --
    NOT duplicated here -- so the fallback's action derivation can never drift
    from the router's. When no token matches a canonical verb, falls back to
    the IMPLEMENTER role's default verb (``generic-agent`` is an implementer
    profile), mirroring ``ActionRouter._derive_action_from_tokens``.
    """
    for token in _normalize_tokens(request_text):
        entry = CANONICAL_VERB_MAP.get(token)
        if entry is not None:
            action, _role = entry
            return action
    caps = DEFAULT_ROLE_CAPABILITIES.get(Role.IMPLEMENTER)
    if caps and caps.canonical_verbs:
        return str(caps.canonical_verbs[0])
    return "implement"


def resolve_generic_fallback(repo_root: Path, request_text: str) -> RouterDecision | None:
    """Pin ``generic-agent`` when the project charter is wholly empty.

    Called at the executor's auto-route branch as
    ``resolve_generic_fallback(...) or self._router.route(...)`` -- returning
    ``None`` here is the short-circuit "not empty, defer to the router" signal.

    Returns
    -------
    RouterDecision | None
        A decision routing to ``GENERIC_AGENT_ID`` with ``confidence=
        "generic_fallback"`` when :func:`is_charter_empty` is ``True``;
        ``None`` otherwise (any activation dimension present).
    """
    if not is_charter_empty(repo_root):
        return None
    return RouterDecision(
        profile_id=GENERIC_AGENT_ID,
        action=_derive_fallback_action(request_text),
        confidence="generic_fallback",
        match_reason=_MATCH_REASON,
        # WP2/#3840: this path never calls route() at all -- it short-circuits
        # before the router runs, so there are no candidates to report.
        alternatives=[],
    )
