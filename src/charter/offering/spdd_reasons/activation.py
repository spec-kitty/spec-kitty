"""SPDD/REASONS pack activation detection.

Single source of truth for "is the SPDD/REASONS charter content active for this
project?". The helper inspects the project's real activation authority --
the source :func:`kernel.activation_ledger_store.resolve_activation_source`
names (the activation ledger ``.kittify/charter/activation.yaml``; before the
ledger migration ``.kittify/config.yaml``'s or, when a ``charter:`` string
pointer resolves, the pointed-at ``charter.yaml``'s) top-level
``activated_paradigms``/``activated_directives``/``activated_tactics`` keys,
the same resolution ``charter.activation.pack_context.PackContext.from_config``
reads through -- and returns ``True`` iff at least one of the four selectors
is present:

- paradigm ``structured-prompt-driven-development``
- tactic ``reasons-canvas-fill``
- tactic ``reasons-canvas-review``
- directive ``DIRECTIVE_038`` (or its numeric-hint slug form)

``charter.offering.spdd_reasons`` cannot import
``charter.activation.pack_context.PackContext`` directly -- C-004 forbids
``charter.offering -> charter.activation`` in any form, enforced
non-vacuously by
``tests/architectural/test_charter_offering_does_not_import_activation.py``.
This module therefore carries its own raw ``ruamel.yaml`` replication of
``PackContext.from_config``'s *reading* half (mission
``spdd-reasons-activation-split-brain-01M1K6VN``, Decision Record 1, Option
A) -- a second, independent implementation of INV-2's read side. The
mandatory parity test
(``tests/charter/test_spdd_reasons_activation_parity.py``) is what proves
the two independent readers stay in agreement; without it they can silently
drift apart again (spec.md Constraint C-003).

Failure modes:

- Missing ``.kittify/config.yaml`` -> returns ``False`` (FR-004's explicit,
  evidence-based carve-out from full ``PackContext`` parity -- see the code
  comment below; this is NOT full byte-for-byte replication of
  ``PackContext.from_config``, which does not treat an absent config.yaml as
  an error either, but this function's own callers rely on the safe-default
  shape specifically).
- Malformed top-level YAML in ``config.yaml`` or the pointed ``charter.yaml``,
  or a dangling/unreadable ``charter:`` pointer target -> raises (FR-005;
  never a silent ``False``/``True``).
- A present-but-non-list ``activated_<kind>`` value -> raises, mirroring
  ``PackContext._read_list_key``'s contract (never silently iterates a bare
  scalar string character-by-character).

Explicit carve-out (Decision Record 1 / plan.md section (a) item 1): this
replication tracks ``PackContext.from_config``'s raw, unconditional per-kind
three-state semantics (absent key -> ``None`` -> "all built-ins available",
independent of any other kind's state) -- NOT ``compile_charter``'s
``project_configured`` gate (``charter.activation.compiler``'s
``_resolve_config_activated_roots``), which additionally narrows an
omitted-but-sibling-configured kind to ``frozenset()`` once a project has
set ANY of the seven ``activated_<kind>`` fields. A project that has
activated some but not all SPDD-relevant kinds may therefore disagree with
``compile_charter``'s real delivered set on the omitted kind -- a named,
evidence-based gap (same treatment as the FR-004 carve-out above), not an
oversight.

No per-process cache is kept (FR-001(e), option (ii)): ``PackContext.
from_config`` itself is always-fresh and reads at most two YAML files,
"<50ms typical" per ``contracts/activation.md`` -- this replication reads
the same at-most-two files, so retiring the cache stays within that budget
while sidestepping any same-process cache-invalidation defect entirely
(both direct-``config.yaml`` and pointer-target mutation cases stay correct
by construction, with no cache key to get wrong). ``clear_activation_cache``
stays exported as a no-op, test-only reset hook for source compatibility
with existing callers.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.activation_ledger_store import (
    ActivationLedgerFormatError,
    ActivationSource,
    ResolvedActivationSource,
    read_activation_ledger_raw,
    resolve_activation_source,
)
from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind

__all__ = ["clear_activation_cache", "is_spdd_reasons_active"]

PARADIGM_ID = "structured-prompt-driven-development"
TACTIC_FILL_ID = "reasons-canvas-fill"
TACTIC_REVIEW_ID = "reasons-canvas-review"
DIRECTIVE_ID = "DIRECTIVE_038"
DIRECTIVE_NUMERIC_HINT = "038"

_KITTIFY = ".kittify"
_CONFIG_YAML = "config.yaml"
#: The ``config.yaml`` key naming the active ``charter.yaml``, handed to the kernel resolver. The activation
#: seam's spelling (``charter.activation.activation_ledger._CHARTER_POINTER_KEY``), which C-004 forbids importing here.
_CHARTER_POINTER_KEY = "charter"
_ACTIVATED_PARADIGMS_KEY = "activated_paradigms"
_ACTIVATED_TACTICS_KEY = "activated_tactics"
_ACTIVATED_DIRECTIVES_KEY = "activated_directives"
_DEACTIVATED_PARADIGMS_KEY = "deactivated_paradigms"
_DEACTIVATED_TACTICS_KEY = "deactivated_tactics"
_DEACTIVATED_DIRECTIVES_KEY = "deactivated_directives"

#: The activation keys a legacy surface may carry, handed to the kernel resolver
#: (it tells an unmigrated project from a fresh one with them). Derived from :class:`ArtifactKind` with the
#: activation seam's spelling (``charter.activation.activation_ledger.LEDGER_KEYS``),
#: which C-004 forbids importing here.
_LEGACY_ACTIVATION_KEYS: frozenset[str] = frozenset(
    {
        "activated_kinds",
        "mission_type_activations",
        *(f"{prefix}{kind.plural}" for kind in ArtifactKind if kind.activatable for prefix in ("activated_", "deactivated_")),
    }
)


class _SpddActivationConfigError(ValueError):
    """Raised when the SPDD activation source is malformed or unreachable.

    A module-local, ``charter.activation``-import-free equivalent of
    ``charter.activation.pack_context.ActiveCharterConfigError`` (FR-005) --
    C-004 forbids importing that class from this package, so this rewrite
    raises its own narrow exception type carrying an equivalent message
    instead of the real one.
    """


def clear_activation_cache() -> None:
    """No-op test-only reset hook, kept for source compatibility (FR-001(e)).

    This module no longer keeps a per-process cache (see the module
    docstring's "No per-process cache is kept" section) -- every call to
    :func:`is_spdd_reasons_active` re-reads the activation source fresh, so
    there is nothing to clear. Existing callers (test suites across this
    mission's siblings) that call this between fixtures continue to work
    unchanged.
    """


def is_spdd_reasons_active(repo_root: Path) -> bool:
    """Return True iff the SPDD/REASONS pack is active for the given project.

    Activation is a disjunction of four selectors (paradigm, two tactics,
    directive), read from the project's real ``activated_*`` authority via a
    raw replication of ``PackContext.from_config``'s INV-2 two-file pointer
    resolution (module docstring). Absent ``.kittify/config.yaml`` returns
    ``False`` (FR-004); malformed YAML, a dangling/unreadable ``charter:``
    pointer target, or a present-but-non-list ``activated_<kind>`` value all
    raise (FR-005) -- never an unexplained silent result (NFR-001). A selector
    the matching ``deactivated_<kind>`` list names is off (``allow and not
    deny``, D-07); the directive deny matches through ``_is_directive_038``.
    """
    config_path = repo_root / _KITTIFY / _CONFIG_YAML
    if not config_path.exists():
        # FR-004: deliberate, evidence-based carve-out -- an absent
        # .kittify/config.yaml pins False rather than following full
        # PackContext parity. Confirmed safe by T003's re-verified call-chain
        # trace: command_renderer.py's apply_spdd_blocks_for_project IS
        # reached before spec-kitty init writes .kittify/config.yaml, and the
        # pre-fix body already returned False for this case (absent
        # .kittify/charter/), so this preserves byte-for-byte behavior on
        # that one confirmed pre-config.yaml call path.
        return False

    config_data = _load_mapping(config_path)
    activation_source, deny_source = _activation_source(repo_root, config_data)

    activated_paradigms = _read_activated_key(activation_source, _ACTIVATED_PARADIGMS_KEY)
    activated_tactics = _read_activated_key(activation_source, _ACTIVATED_TACTICS_KEY)
    activated_directives = _read_activated_key(activation_source, _ACTIVATED_DIRECTIVES_KEY)
    # Deny (D-07): read from the ledger only; a legacy deactivated_<kind> key is
    # never applied (hole 6), so a LEGACY source denies nothing. No org
    # required floor is applied here -- the floor lives in activation, which
    # C-004 forbids importing; ADR 2026-10-19-1 records the residual.
    denied_paradigms = _read_activated_key(deny_source, _DEACTIVATED_PARADIGMS_KEY) or frozenset()
    denied_tactics = _read_activated_key(deny_source, _DEACTIVATED_TACTICS_KEY) or frozenset()
    denied_directives = _read_activated_key(deny_source, _DEACTIVATED_DIRECTIVES_KEY) or frozenset()

    # Second carve-out (Decision Record 1 / plan.md section (a) item 1, see
    # module docstring): this per-kind disjunction does NOT apply
    # compile_charter's project_configured gate. An absent allow list (`None`)
    # in `_selector_admitted` means "selector satisfied" (all built-ins available for that kind),
    # independent of whichever OTHER kinds are explicitly configured.
    #
    # NEVER `x or set()`/`x or frozenset()` here: that idiom collapses an
    # absent key (None, "all built-ins") through the same falsy path as an
    # explicit `[]` ("nothing selected") -- the exact truthiness-collapse
    # bug class this mission exists to close.
    #
    # A deny list, unlike an allow list, has no three-state meaning (absent ==
    # empty), so `or frozenset()` above is the correct collapse there.
    paradigm_active = _selector_admitted(activated_paradigms, denied_paradigms, PARADIGM_ID.__eq__)
    tactic_active = any(_selector_admitted(activated_tactics, denied_tactics, tactic.__eq__) for tactic in (TACTIC_FILL_ID, TACTIC_REVIEW_ID))
    directive_active = _selector_admitted(activated_directives, denied_directives, _is_directive_038)

    return paradigm_active or tactic_active or directive_active


def _selector_admitted(allow: frozenset[str] | None, deny: frozenset[str], matches: Callable[[str], bool]) -> bool:
    """``allow and not deny`` for one selector: a denied match wins; an absent allow list (``None``) admits."""
    if any(matches(entry) for entry in deny):
        return False
    return allow is None or any(matches(entry) for entry in allow)


def _resolve_source(repo_root: Path) -> ResolvedActivationSource:
    """The kernel resolver's answer, with this module's own error type (C-004)."""
    try:
        resolved = resolve_activation_source(repo_root, legacy_keys=_LEGACY_ACTIVATION_KEYS, pointer_key=_CHARTER_POINTER_KEY)
    except ActivationLedgerFormatError as exc:
        raise _SpddActivationConfigError(exc.body) from exc
    return resolved


def _activation_source(repo_root: Path, config_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(allow source, deny source)``: the mappings the activation keys are read from, as the kernel resolver decides (FR-017).

    ``LEDGER`` -> the ledger (``{}`` before its first write) for both.
    ``LEGACY`` -> today's pointer rule for the allow keys: no ``charter:``
    string pointer -> *config_data*; a pointer -> the pointed ``charter.yaml``,
    where a dangling pointer raises. A legacy source denies nothing (``{}``):
    a legacy ``deactivated_<kind>`` key is never applied (hole 6).
    """
    resolved = _resolve_source(repo_root)
    if resolved.source is ActivationSource.LEDGER:
        try:
            ledger = read_activation_ledger_raw(repo_root) or {}
        except ActivationLedgerFormatError as exc:
            raise _SpddActivationConfigError(exc.body) from exc
        return ledger, ledger
    if resolved.pointer is None:
        return config_data, {}
    if not resolved.pointer_exists:
        raise _SpddActivationConfigError(f".kittify/config.yaml 'charter:' pointer names {resolved.pointer}, which does not exist.")
    return _load_mapping(resolved.pointer), {}


def _read_activated_key(data: dict[str, Any], key: str) -> frozenset[str] | None:
    """Three-state read matching ``PackContext._read_list_key``'s contract.

    Absent key (or present as YAML ``null``) -> ``None`` ("all built-ins
    available"). Present as ``[]`` -> explicit empty ``frozenset()``.
    Present non-empty -> the explicit ``frozenset`` of ids.

    **Explicit fail-loud type check (TASKS-FRESH2-002 remediation):** a key
    present with a non-``list`` value (e.g. a bare-scalar authoring mistake
    like ``activated_paradigms: structured-prompt-driven-development``
    instead of a one-item list) raises -- never falls through to a bare
    ``for entry in raw`` loop, which would iterate a ``str``
    character-by-character and silently produce a nonsense
    one-letter-per-entry set instead of the intended fail-loud error
    (NFR-001 forbids exactly this "unexplained silent result for an error
    condition").
    """
    raw = data.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise _SpddActivationConfigError(f"Activation key '{key}' must be a list, got {type(raw).__name__}.")
    return frozenset(str(item) for item in raw)


def _load_mapping(path: Path) -> dict[str, Any]:
    """Load *path* as YAML and return its top-level mapping.

    An empty file (parses to ``None``) is treated as an empty mapping,
    mirroring ``pack_context._load_config``'s exact behavior for
    ``config.yaml``. Any other non-mapping root, or a YAML loader error, is a
    fail-loud raise (FR-005) -- never a silent ``False``/``True``.
    """
    yaml = YAML(typ="safe")
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise _SpddActivationConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _SpddActivationConfigError(f"{path} root must be a mapping.")
    return raw


def _is_directive_038(raw: str) -> bool:
    """Match ``DIRECTIVE_038`` or any slug carrying the ``038`` numeric hint.

    Preserved verbatim from the pre-rewrite body (T004 step (f)): this is
    matching logic, not a source-of-truth question, and is explicitly out of
    scope to change (spec Edge Cases).
    """
    if raw == DIRECTIVE_ID:
        return True
    # Accept short forms like '038' or '038-structured-prompt-boundary'.
    match = re.match(r"^(\d+)", raw)
    if match and match.group(1).zfill(3) == DIRECTIVE_NUMERIC_HINT:
        return True
    if raw.upper() == DIRECTIVE_ID.upper():
        return True
    return False
