"""Mandatory parity test: ``is_spdd_reasons_active`` vs. ``PackContext.from_config``.

Mission ``spdd-reasons-activation-split-brain-01M1K6VN``, WP01. This is the
mission's **load-bearing artifact** (spec.md Constraint C-003 / Decision
Record 1): ``activation.py`` cannot import
``charter.activation.pack_context.PackContext`` directly (C-004 forbids
``charter.offering -> charter.activation`` in any form), so the rewritten
``is_spdd_reasons_active`` carries its own raw, independent replication of
``PackContext.from_config``'s INV-2 two-file pointer resolution. Nothing but
this test proves the two independent readers stay in agreement -- without
it, the two implementations can silently drift apart again, reproducing the
exact defect class this mission exists to close.

Also carries T001's FR-004 absent-``.kittify/config.yaml`` pin (both the
``is_spdd_reasons_active`` helper in isolation and the real
``apply_spdd_blocks_for_project`` entry point FR-004's own falsifiable
Acceptance Criterion names).

Every fixture in T002's matrix, both same-process mutation cases (step 4 and
step 4a), and the step-6 non-list fixture are RED against the pre-fix
``activation.py`` body and GREEN after T004's rewrite -- see this WP's final
report for the captured RED-run output (C-011).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from charter.activation.pack_context import PackContext
from charter.offering.spdd_reasons.activation import (
    DIRECTIVE_ID,
    DIRECTIVE_NUMERIC_HINT,
    PARADIGM_ID,
    TACTIC_FILL_ID,
    TACTIC_REVIEW_ID,
    _is_directive_038,
    clear_activation_cache,
    is_spdd_reasons_active,
)
from charter.offering.spdd_reasons.template_renderer import (
    REASONS_BLOCK_END,
    REASONS_BLOCK_START,
    apply_spdd_blocks_for_project,
    process_spdd_blocks,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

# A directive id that matches DIRECTIVE_038 via the numeric-hint slug form
# rather than the canonical "DIRECTIVE_038" string (Edge Cases matching-logic
# note; `_is_directive_038` is preserved verbatim by T004 step (f), out of
# scope to change).
_DIRECTIVE_NUMERIC_HINT_SLUG = f"{DIRECTIVE_NUMERIC_HINT}-structured-prompt-boundary"

_ACTIVATION_KEYS = ("activated_paradigms", "activated_tactics", "activated_directives")


@pytest.fixture(autouse=True)
def _reset_activation_cache() -> None:
    """Clear the module's activation cache before and after every test.

    Whether or not T004's rewrite keeps a cache, ``clear_activation_cache``
    stays a safe, idempotent test-only reset hook (FR-001(e)) -- calling it
    here keeps every test's fixture reads independent of any earlier test's
    cache state.
    """
    clear_activation_cache()
    yield
    clear_activation_cache()


# ---------------------------------------------------------------------------
# Fixture construction helpers
# ---------------------------------------------------------------------------


def _yaml_list_line(key: str, value: list[str] | None) -> str:
    """Render one ``key: [...]`` YAML line. ``None`` means "omit the key"."""
    if value is None:
        return ""
    if not value:
        return f"{key}: []\n"
    return f"{key}: [{', '.join(value)}]\n"


def _activation_block(tested_key: str, tested_value: list[str] | None) -> str:
    """Render all three activation keys as YAML text.

    The kind under test (*tested_key*) gets *tested_value* (``None`` => the
    key is omitted entirely -- the "absent" state). The other two kinds are
    pinned to an explicit ``[]`` so the tested kind's effect on the
    disjunction is isolated: an *omitted* other kind would itself satisfy
    the disjunction via "``None`` = all built-ins", masking whatever the
    tested kind's own state contributes.
    """
    lines = [_yaml_list_line(key, tested_value if key == tested_key else []) for key in _ACTIVATION_KEYS]
    return "".join(lines)


def _write_activation_fixture(tmp_path: Path, tested_key: str, tested_value: list[str] | None, *, pointer: bool) -> None:
    """Write a ``.kittify/config.yaml`` fixture, pointer-present or absent.

    Pointer-absent (legacy/un-migrated shape): the activation block is
    written directly onto ``config.yaml``. Pointer-present (this repo's own
    dogfood shape, INV-2's migrated shape): ``config.yaml`` carries a
    ``charter:`` string pointer to a separate ``charter.yaml``, which itself
    carries the activation block at its top level -- mirroring this repo's
    own real ``.kittify/config.yaml`` (``charter: .kittify/charter/charter.yaml``).
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    block = _activation_block(tested_key, tested_value)
    if pointer:
        charter_dir = kittify / "charter"
        charter_dir.mkdir(parents=True, exist_ok=True)
        (charter_dir / "charter.yaml").write_text(block, encoding="utf-8")
        (kittify / "config.yaml").write_text("charter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    else:
        (kittify / "config.yaml").write_text(block, encoding="utf-8")


def _expected_active(pack_context: PackContext) -> bool:
    """Hand-computed disjunction oracle over ``PackContext``'s real fields.

    MUST NOT use ``x or set()``/``x or frozenset()``: an absent key
    (``None``) means "all built-ins available" and must stay distinct from
    an explicit ``[]`` ("nothing selected") -- collapsing the two through
    Python truthiness is the exact bug class this mission exists to close
    (see the module docstring above, and T002 step 3 / plan.md section (b)).
    """
    paradigm_active = pack_context.activated_paradigms is None or PARADIGM_ID in pack_context.activated_paradigms
    tactic_active = pack_context.activated_tactics is None or bool({TACTIC_FILL_ID, TACTIC_REVIEW_ID} & pack_context.activated_tactics)
    directive_active = pack_context.activated_directives is None or any(_is_directive_038(entry) for entry in pack_context.activated_directives)
    return paradigm_active or tactic_active or directive_active


# ---------------------------------------------------------------------------
# T001: baseline-adjacent FR-004 pins (not red-on-main; see docstrings)
# ---------------------------------------------------------------------------


_TEMPLATE_TEXT = (
    "preceding line\n"
    "\n"
    f"{REASONS_BLOCK_START}\n"
    "\n"
    "### REASONS Guidance -- SPDD content\n"
    "some SPDD-scoped guidance text here\n"
    "\n"
    f"{REASONS_BLOCK_END}\n"
    "\n"
    "following line\n"
)


def test_apply_spdd_blocks_for_project_strips_when_config_absent(tmp_path: Path) -> None:
    """FR-004's own falsifiable Acceptance Criterion, through the real entry
    point (T001 step 4) -- distinct from ``is_spdd_reasons_active(tmp_path)
    is False`` above, which exercises the activation helper in isolation
    rather than the real template-stripping entry point FR-004's AC names.

    PIN, not red-on-main (same rationale as the pin above): the pre-fix body
    already returns ``False`` for an absent ``.kittify/charter/`` directory,
    so ``apply_spdd_blocks_for_project`` already strips the blocks for an
    absent-``.kittify/config.yaml`` project today. RED only against a
    hypothetical naive ``PackContext``-parity rewrite that dropped this
    carve-out (which would return ``True`` for an absent-config project and
    leave the blocks in) -- FR-004's own falsifiable AC.
    """
    assert not (tmp_path / ".kittify").exists()

    rendered = apply_spdd_blocks_for_project(_TEMPLATE_TEXT, tmp_path)

    assert rendered == process_spdd_blocks(_TEMPLATE_TEXT, active=False)
    assert REASONS_BLOCK_START not in rendered
    assert REASONS_BLOCK_END not in rendered


# ---------------------------------------------------------------------------
# T002: the mandatory parity matrix (FR-002) -- 3 states x 5 kind-variants x
# 2 pointer shapes = 30 fixtures.
# ---------------------------------------------------------------------------

_KIND_VARIANTS = (
    ("activated_paradigms", PARADIGM_ID, "paradigm"),
    ("activated_tactics", TACTIC_FILL_ID, "tactic_fill"),
    ("activated_tactics", TACTIC_REVIEW_ID, "tactic_review"),
    ("activated_directives", DIRECTIVE_ID, "directive_canonical"),
    ("activated_directives", _DIRECTIVE_NUMERIC_HINT_SLUG, "directive_numeric_hint"),
)

# (state label, value-builder over the variant's target id) -- "present"
# builds a one-item list containing the variant's own target id.
_STATES: tuple[tuple[str, object], ...] = (
    ("absent", None),
    ("explicit_empty", []),
    ("explicit_present", "TARGET"),
)

_POINTER_SHAPES = (("no_pointer", False), ("pointer", True))

_MATRIX: list[tuple[str, list[str] | None, bool]] = []
_MATRIX_IDS: list[str] = []
for _key, _target_id, _variant_label in _KIND_VARIANTS:
    for _state_label, _state_value in _STATES:
        _value: list[str] | None = [_target_id] if _state_value == "TARGET" else _state_value  # type: ignore[assignment]
        for _pointer_label, _pointer_flag in _POINTER_SHAPES:
            _MATRIX.append((_key, _value, _pointer_flag))
            _MATRIX_IDS.append(f"{_variant_label}-{_state_label}-{_pointer_label}")


@pytest.mark.parametrize(("tested_key", "tested_value", "pointer"), _MATRIX, ids=_MATRIX_IDS)
def test_parity_matrix(tmp_path: Path, tested_key: str, tested_value: list[str] | None, pointer: bool) -> None:
    """``is_spdd_reasons_active`` agrees with a hand-computed disjunction
    over ``PackContext.from_config``'s real ``activated_*`` fields, across
    every state/kind/pointer-shape combination in the mandated matrix
    (User Story 1 Scenario 4, FR-002, plan.md section (b)).

    Why every non-``absent_config`` fixture is RED on ``main`` today,
    concretely (T002 step 5): the pre-fix body never reads
    ``.kittify/config.yaml`` or any ``activated_*`` key at all -- it reads
    ``.kittify/charter/charter.yaml``'s ``governance:``/``directives:``
    sections exclusively. Every fixture this test constructs writes ONLY
    ``.kittify/config.yaml`` (optionally with a ``charter:`` pointer) and
    deliberately leaves ``governance.charter.selected_*`` absent/empty -- so
    on ``main``, the old body sees an absent/empty ``governance:``/
    ``directives:`` section regardless of what ``activated_*`` says, and
    returns ``False`` unconditionally for every fixture in this matrix whose
    oracle expects ``True``. This is a real, structural RED, not a
    coincidence of one fixture's values.
    """
    _write_activation_fixture(tmp_path, tested_key, tested_value, pointer=pointer)

    pack_context = PackContext.from_config(tmp_path)
    expected = _expected_active(pack_context)

    assert is_spdd_reasons_active(tmp_path) == expected


def test_same_process_mutation_reflects_config_yaml_edit(tmp_path: Path) -> None:
    """FR-002's same-process, two-call mutation case (direct, non-pointer
    shape): a same-process edit to ``.kittify/config.yaml`` invalidates the
    cache -- the direct regression test for T004's cache-key fix.

    RED on ``main`` today: the old body never reads ``.kittify/config.yaml``
    at all (it reads ``.kittify/charter/charter.yaml``'s stale sections,
    absent here), so both calls return ``False`` and the assertion that the
    second call differs from the first fails.
    """
    _write_activation_fixture(tmp_path, "activated_paradigms", [], pointer=False)
    assert is_spdd_reasons_active(tmp_path) is False

    time.sleep(0.01)  # guarantee a distinguishable mtime on the rewrite below
    _write_activation_fixture(tmp_path, "activated_paradigms", [PARADIGM_ID], pointer=False)

    assert is_spdd_reasons_active(tmp_path) is True


def test_same_process_mutation_reflects_pointer_target_edit(tmp_path: Path) -> None:
    """Analyze-phase Finding ANALYZE-COVER-002 (severity 3): a same-process
    edit to the POINTED-AT ``charter.yaml`` -- never ``.kittify/config.yaml``
    itself -- also invalidates the cache. This is this repo's own dogfood
    shape (a ``charter:`` pointer from ``.kittify/config.yaml`` to
    ``.kittify/charter/charter.yaml``, where the real ``activated_*`` keys
    live), and step 4 above cannot exercise it: a cache-key implementation
    that composes its key from only ``config.yaml``'s own mtime (omitting
    the resolved pointer target's mtime) would go uncaught by step 4 alone.

    RED on ``main`` today for the same structural reason as step 4: the old
    body never reads ``activated_*`` at all, so both calls return ``False``.
    """
    _write_activation_fixture(tmp_path, "activated_paradigms", [], pointer=True)
    assert is_spdd_reasons_active(tmp_path) is False

    time.sleep(0.01)  # guarantee a distinguishable mtime on the rewrite below
    # Mutate ONLY the pointed-at charter.yaml; .kittify/config.yaml itself is
    # left completely untouched.
    charter_yaml = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.write_text(_activation_block("activated_paradigms", [PARADIGM_ID]), encoding="utf-8")

    assert is_spdd_reasons_active(tmp_path) is True


@pytest.mark.parametrize("key", _ACTIVATION_KEYS, ids=_ACTIVATION_KEYS)
def test_non_list_activated_value_raises(tmp_path: Path, key: str) -> None:
    """TASKS-FRESH2-002 remediation (T002 step 6): a present-but-non-list
    ``activated_<kind>`` value (a bare scalar authoring mistake, e.g.
    ``activated_paradigms: structured-prompt-driven-development`` instead of
    a one-item list) must raise -- never silently iterate the string
    character by character and build a nonsense one-letter-per-entry set.

    RED on ``main`` today for the same structural reason as the parity
    matrix (the old body never reads ``activated_*`` at all, so it returns
    ``False`` unconditionally instead of raising). ALSO RED against a naive,
    partially-correct T004 rewrite that implements the three-state
    absent/``[]``/non-empty semantics but omits this type check -- such an
    implementation would iterate the scalar string character-by-character
    (Python happily iterates a ``str`` in a ``for entry in raw`` loop)
    instead of raising, which is exactly why this fixture exists as its own
    case rather than being assumed covered by the three-state matrix above.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(f"{key}: {PARADIGM_ID}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=key):
        is_spdd_reasons_active(tmp_path)
