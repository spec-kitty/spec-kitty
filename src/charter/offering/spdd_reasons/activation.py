"""SPDD/REASONS pack activation detection.

Single source of truth for "is the SPDD/REASONS charter content active for this
project?". The helper inspects the project's real activation authority --
``.kittify/config.yaml``'s (or, when a ``charter:`` string pointer resolves,
the pointed-at ``charter.yaml``'s) top-level ``activated_paradigms``/
``activated_directives``/``activated_tactics`` keys, replicating
``charter.activation.pack_context.PackContext.from_config``'s INV-2 two-file
pointer resolution -- and returns ``True`` iff at least one of the four
selectors is present:

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
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

__all__ = ["clear_activation_cache", "is_spdd_reasons_active"]

PARADIGM_ID = "structured-prompt-driven-development"
TACTIC_FILL_ID = "reasons-canvas-fill"
TACTIC_REVIEW_ID = "reasons-canvas-review"
DIRECTIVE_ID = "DIRECTIVE_038"
DIRECTIVE_NUMERIC_HINT = "038"

_KITTIFY = ".kittify"
_CONFIG_YAML = "config.yaml"
_CHARTER_POINTER_KEY = "charter"
_ACTIVATED_PARADIGMS_KEY = "activated_paradigms"
_ACTIVATED_TACTICS_KEY = "activated_tactics"
_ACTIVATED_DIRECTIVES_KEY = "activated_directives"


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
    raise (FR-005) -- never an unexplained silent result (NFR-001).
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

    pointer_path = _resolve_charter_pointer(repo_root, config_data)
    if pointer_path is None:
        activation_source = config_data
    else:
        if not pointer_path.exists():
            raise _SpddActivationConfigError(f".kittify/config.yaml 'charter:' pointer names {pointer_path}, which does not exist.")
        activation_source = _load_mapping(pointer_path)

    activated_paradigms = _read_activated_key(activation_source, _ACTIVATED_PARADIGMS_KEY)
    activated_tactics = _read_activated_key(activation_source, _ACTIVATED_TACTICS_KEY)
    activated_directives = _read_activated_key(activation_source, _ACTIVATED_DIRECTIVES_KEY)

    # Second carve-out (Decision Record 1 / plan.md section (a) item 1, see
    # module docstring): this per-kind disjunction does NOT apply
    # compile_charter's project_configured gate. Each `is None` branch below
    # means "selector satisfied" (all built-ins available for that kind),
    # independent of whichever OTHER kinds are explicitly configured.
    #
    # NEVER `x or set()`/`x or frozenset()` here: that idiom collapses an
    # absent key (None, "all built-ins") through the same falsy path as an
    # explicit `[]` ("nothing selected") -- the exact truthiness-collapse
    # bug class this mission exists to close.
    paradigm_active = activated_paradigms is None or PARADIGM_ID in activated_paradigms
    tactic_active = activated_tactics is None or bool({TACTIC_FILL_ID, TACTIC_REVIEW_ID} & activated_tactics)
    directive_active = activated_directives is None or any(_is_directive_038(entry) for entry in activated_directives)

    return paradigm_active or tactic_active or directive_active


def _resolve_charter_pointer(repo_root: Path, config_data: dict[str, Any]) -> Path | None:
    """Mirror ``pack_context.resolve_charter_yaml_pointer``'s "string-only" rule.

    Only a *string* ``charter:`` value is a pointer -- a mapping/list/scalar
    non-string value (e.g. a legacy inline block) is NOT a pointer and must
    not be stringified into a bogus filesystem path. Returns ``None`` when
    the key is absent (legacy/un-migrated project: activation is read
    directly from ``config.yaml``) or non-string.
    """
    pointer = config_data.get(_CHARTER_POINTER_KEY)
    if not isinstance(pointer, str):
        return None
    pointer_path = Path(pointer)
    return pointer_path if pointer_path.is_absolute() else repo_root / pointer_path


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
