"""Enforcement-allowlist-vs-shape-guard membership guard (E4/C-007/FR-014/NFR-007).

Mission ``ci-pipeline-reinstatement-01M1X35E`` WP16 (closes #3458). The P2
shape-guard demotion needs a **committed, machine-checkable partition** so the
distinction between "always-on P1 enforcement" and "demoted-off-the-gate P2
shape guard" is never a per-PR judgment call, and relabeling the committed
``tests/architectural/shape_guard_membership.yaml`` alone cannot move a test on
or off the blocking gate in either direction:

* An **enforcement allowlist** (``test_no_dead_symbols``/
  ``test_no_retired_subsystems``/``test_no_dead_modules``/
  ``test_integration_boundary``) catches real defects and is ALWAYS-ON. This
  module's own :data:`_ENFORCEMENT_ALLOWLIST_FILES` tuple — a canonical source
  living in test *code*, not the yaml — is what
  :func:`test_enforcement_allowlist_set_is_exactly_the_c007_canon` checks the
  yaml against; editing the yaml alone can neither drop one of these four out
  of ``enforcement-allowlist`` nor add a fifth entry into that class (the
  "gutting P1" and "shape-guard silently promoted" footguns this mission's
  Risks section names).
* A **shape guard** is a test demoted OFF the blocking gate: a breach is
  reported as advisory telemetry, never raised. The golden-count
  frozen-ceiling ratchet was the only ``shape-guard``-classed entry; it was
  retired outright (#4315), leaving the class **defined but empty** —
  :data:`_VALID_CLASSES` keeps the vocabulary available for a future
  demotion, not as dead code.
* **Behavioral** entries (the already-narrowed twelve-agent-parity
  structural/content tests, #3447 WP05) are ordinary tests: neither ratchet
  class, no special treatment.

Every membership key is tied to a real file (and, for a ``::``-qualified key,
a real function defined in it) via AST/import introspection — never a
free-text label with nothing backing it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MEMBERSHIP_PATH = Path(__file__).resolve().with_name("shape_guard_membership.yaml")

_VALID_CLASSES = frozenset({"enforcement-allowlist", "shape-guard", "behavioral"})

# The C-007 enforcement-allowlist canon. Deliberately hardcoded here (in test
# *code*, reviewed like any other diff) rather than derived from the yaml
# itself -- this is the guard's own canonical source, so a yaml-only edit
# cannot silently add or remove a member of the always-on P1 set.
_ENFORCEMENT_ALLOWLIST_FILES: tuple[str, ...] = (
    "tests/architectural/test_no_dead_symbols.py",
    "tests/architectural/test_no_retired_subsystems.py",
    "tests/architectural/test_no_dead_modules.py",
    "tests/architectural/test_integration_boundary.py",
)


def _load_membership() -> dict[str, str]:
    data = yaml.safe_load(_MEMBERSHIP_PATH.read_text(encoding="utf-8"))
    membership = data["membership"]
    if not isinstance(membership, dict):
        raise TypeError(f"{_MEMBERSHIP_PATH}: 'membership' must be an object, got {type(membership)!r}")
    return {str(k): str(v) for k, v in membership.items()}


def _module_relpath(entry: str) -> str:
    """The bare module-path portion of a membership key (strips a `::func` suffix)."""
    return entry.split("::", 1)[0]


# ---------------------------------------------------------------------------
# Schema + real-code-binding checks.
# ---------------------------------------------------------------------------


def test_membership_file_exists_and_parses() -> None:
    assert _MEMBERSHIP_PATH.exists(), (
        f"{_MEMBERSHIP_PATH} is missing -- the P2 shape-guard demotion (C-007/FR-014/E4) requires a committed, machine-checkable membership partition."
    )
    membership = _load_membership()
    assert membership, "membership partition must not be empty"


def test_every_entry_has_exactly_one_recognized_class() -> None:
    membership = _load_membership()
    for entry, cls in membership.items():
        assert cls in _VALID_CLASSES, f"{entry!r} has class {cls!r}, expected one of {sorted(_VALID_CLASSES)}"


def test_every_membership_key_resolves_to_a_real_module_or_function() -> None:
    """A membership entry is tied to real code, not free text: the module file
    must exist, and a `::`-qualified entry's function must actually be defined
    in it.
    """
    membership = _load_membership()
    for entry in membership:
        module_relpath, _, func_name = entry.partition("::")
        module_path = _REPO_ROOT / module_relpath
        assert module_path.is_file(), f"{entry!r}: no such module {module_path}"
        if func_name:
            tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=module_relpath)
            defined = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            assert func_name in defined, f"{entry!r}: no function named {func_name!r} defined in {module_relpath}"


# ---------------------------------------------------------------------------
# C-007 boundary: enforcement allowlists are the fixed, always-on canon.
# ---------------------------------------------------------------------------


def test_enforcement_allowlist_set_is_exactly_the_c007_canon() -> None:
    """Neither direction of relabeling is possible via a yaml-only edit: the
    set of entries classed ``enforcement-allowlist`` must exactly match
    :data:`_ENFORCEMENT_ALLOWLIST_FILES` -- no member can be moved OUT (the
    "gutting P1" footgun) and no other test can be moved IN (a shape guard
    silently "promoted" into the always-on canon without actually being one).
    """
    membership = _load_membership()
    classified_enforcement = {_module_relpath(entry) for entry, cls in membership.items() if cls == "enforcement-allowlist"}
    assert classified_enforcement == set(_ENFORCEMENT_ALLOWLIST_FILES), (
        f"enforcement-allowlist classification drifted from the C-007 canon: got {sorted(classified_enforcement)}, expected {sorted(_ENFORCEMENT_ALLOWLIST_FILES)}"
    )


def test_enforcement_allowlists_still_carry_real_blocking_assertions() -> None:
    """Reverse relabeling guard: an enforcement-allowlist module cannot be
    silently gutted into advisory-only telemetry while the yaml still reads
    ``enforcement-allowlist``. Each must define at least one real ``assert``
    inside a ``test_*`` function -- a mechanical, AST-derived proxy for
    "still actually blocks on failure", not a free-text/docstring claim.
    """
    for relpath in _ENFORCEMENT_ALLOWLIST_FILES:
        module_path = _REPO_ROOT / relpath
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=relpath)
        found_assert = False
        for node in ast.walk(tree):
            is_test_func = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
            if is_test_func and any(isinstance(inner, ast.Assert) for inner in ast.walk(node)):
                found_assert = True
                break
        assert found_assert, f"{relpath!r} is classed enforcement-allowlist but no test_* function contains a real `assert` -- it may have been silently demoted"
