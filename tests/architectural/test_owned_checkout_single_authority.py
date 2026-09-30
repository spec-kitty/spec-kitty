"""Owned-checkout single-authority gate G1-G6 (``contracts/architectural-gate.md``).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB`` (FR-001 / SC-004),
closing WP18 (T095/T097).  The gate composes the AST rules of WP01's scanner
(``tests/architectural/_owned_checkout_scan.py``) over the live ``src/`` tree
-- it does not parse or walk the AST itself beyond locating the G6 consumers.
Comments and docstrings never count as offenders.

============  ==============================================================
Gate          Rule
============  ==============================================================
G1            ``resolve_ownership_claim`` is referenced only in
              ``core/owned_mission.py`` (plus its definition in
              ``core/checkout_ownership.py``).
G2            ``resolve_owned_mission(`` / ``adopt_owned_checkout(`` are called
              only from ``cli/commands/_owned_checkout.py`` and
              ``core/owned_mission.py``.
G3            ``OwnedCheckout._mint`` is referenced only in
              ``core/owned_mission.py``.
G4            The identifier ``effective_root`` appears nowhere in ``src/``
              outside the org-pack module rule.
G5            No parameter or field carries an owned root as a bare path.
G6            Each nine-consumer of ``contracts/owned-checkout-carrier.md`` s7
              declares ``owned: OwnedCheckout | None``.
============  ==============================================================

The org-pack module rule (``ORG_PACK_MODULE_RULE``) is the one written
exemption of G4/G5: ``effective_root`` under ``src/charter/**``,
``src/specify_cli/doctrine/**``, ``_doctrine_collect.py`` and
``analysis_inputs.py`` is ``OrgPackConfig.effective_root`` -- the org-pack
root, a different concept from the owned checkout.  The remaining named
scanner rules (org-pack method call, carrier fields, ``CLI_CLAIM_INPUT_RULE``,
``MIGRATIONS_CHECKOUT_ROOT_RULE``) are each pinned by a self-mutation pair in
``test_owned_checkout_gate_selftest.py``.

There is no ledger and no allowlist (operator decision 01M3M65D): the
allowlist below is empty and its ratchet leaf in ``_baselines.yaml`` is 0.
"""

from __future__ import annotations

import ast
import functools
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file, read_source
from tests.architectural._owned_checkout_scan import (
    ORG_PACK_MODULE_PATHS,
    Offender,
    bare_owned_root_paths,
    claim_references,
    effective_root_identifiers,
    iter_python_sources,
    mint_references,
    owned_signature_pins,
    validator_calls,
)

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_THIS_FILE = Path(__file__).resolve()

#: Entries (``"<rel_path>:<lineno>"``) that G4/G5 tolerate.  Empty by operator
#: decision 01M3M65D; ``_baselines.yaml`` pins the leaf at 0 and
#: ``test_ratchet_baselines.py`` enforces it.  Growth is a gate evasion.
_OWNED_ROOT_BARE_PATH_ALLOWLIST: frozenset[str] = frozenset()

_CLAIM_DEFINITION = "src/specify_cli/core/checkout_ownership.py"
_MINTER = "src/specify_cli/core/owned_mission.py"
_CLI_HELPER = "src/specify_cli/cli/commands/_owned_checkout.py"

_G1_ALLOWED = frozenset({_MINTER, _CLAIM_DEFINITION})
_G2_ALLOWED = frozenset({_MINTER, _CLI_HELPER})
_G3_ALLOWED = frozenset({_MINTER})

#: G6: contract s7 consumers, keyed by defining module then bare def/class name.
_G6_CONSUMERS: dict[str, dict[str, str]] = {
    "src/mission_runtime/resolution.py": {
        "placement_seam": "mission_runtime.placement_seam",
        "mission_context_for": "mission_runtime.mission_context_for",
        "resolve_action_context": "mission_runtime.resolve_action_context",
    },
    "src/specify_cli/task_utils/support.py": {"locate_work_package": "task_utils.support.locate_work_package"},
    "src/specify_cli/workspace/context.py": {"resolve_workspace_for_wp": "workspace.context.resolve_workspace_for_wp"},
    "src/specify_cli/coordination/status_service.py": {"EventLogReadContract": "coordination.status_service.EventLogReadContract"},
    "src/specify_cli/status/models.py": {"TransitionRequest": "status.models.TransitionRequest"},
    "src/runtime/next/runtime_bridge.py": {"DecideNextContext": "runtime.next.runtime_bridge.DecideNextContext"},
    "src/runtime/next/prompt_builder.py": {"build_prompt": "runtime.next.prompt_builder.build_prompt (prompt-builder entry point)"},
}
_G6_CONSUMER_COUNT = 9


def _format(offenders: Iterable[Offender]) -> str:
    return "\n".join(f"  {o.rel_path}:{o.lineno} {o.rule} {o.detail}" for o in sorted(offenders, key=lambda o: (o.rel_path, o.lineno, o.detail)))


def _is_org_pack(rel_path: str) -> bool:
    return any(rel_path == p or rel_path.startswith(p) for p in ORG_PACK_MODULE_PATHS)


@functools.cache
def _parsed_src() -> tuple[tuple[str, ast.Module], ...]:
    """Parse ``src/**/*.py`` once per session (fail-closed via ``parse_file``)."""
    return tuple((rel_path, parse_file(path, display=rel_path)) for path, rel_path in iter_python_sources(_SRC))


def _scan(rule: Callable[[ast.Module, str], list[Offender]], allowed: frozenset[str] = frozenset()) -> tuple[list[Offender], set[str]]:
    """Run ``rule`` over every ``src/**/*.py``; return ``(offenders, scanned rel paths)``."""
    offenders: list[Offender] = []
    scanned: set[str] = set()
    for rel_path, tree in _parsed_src():
        scanned.add(rel_path)
        if rel_path in allowed:
            continue
        offenders.extend(rule(tree, rel_path))
    return offenders, scanned


def _expected_sources(*, minus_org_pack: bool) -> set[str]:
    expected = {p.relative_to(_REPO_ROOT).as_posix() for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts}
    return {p for p in expected if not (minus_org_pack and _is_org_pack(p))}


def _assert_scan_floor(scanned: set[str], *, minus_org_pack: bool) -> None:
    """Non-vacuity: the scanned set equals ``src/**/*.py`` minus the named module rule, as sets."""
    scanned_effective = {p for p in scanned if not (minus_org_pack and _is_org_pack(p))}
    expected = _expected_sources(minus_org_pack=minus_org_pack)
    assert expected, "src/ scan root is empty -- the gate would pass vacuously"
    missing, extra = sorted(expected - scanned_effective), sorted(scanned_effective - expected)
    assert scanned_effective == expected, f"scan set differs from src/**/*.py: missing={missing} extra={extra}"


def _not_allowlisted(offenders: list[Offender]) -> list[Offender]:
    return [o for o in offenders if f"{o.rel_path}:{o.lineno}" not in _OWNED_ROOT_BARE_PATH_ALLOWLIST]


def test_allowlist_is_empty() -> None:
    assert not _OWNED_ROOT_BARE_PATH_ALLOWLIST, "operator decision 01M3M65D: no allowlist, no ledger"


def test_g1_resolve_ownership_claim_only_in_minter() -> None:
    offenders, scanned = _scan(claim_references, _G1_ALLOWED)
    _assert_scan_floor(scanned, minus_org_pack=False)
    assert not offenders, f"G1: resolve_ownership_claim referenced outside {_MINTER}:\n{_format(offenders)}"


def test_g2_validators_called_only_from_cli_helper_and_minter() -> None:
    offenders, scanned = _scan(validator_calls, _G2_ALLOWED)
    _assert_scan_floor(scanned, minus_org_pack=False)
    assert not offenders, f"G2: resolve_owned_mission/adopt_owned_checkout called outside the CLI helper and minter:\n{_format(offenders)}"


def test_g3_mint_referenced_only_in_minter() -> None:
    offenders, scanned = _scan(mint_references, _G3_ALLOWED)
    _assert_scan_floor(scanned, minus_org_pack=False)
    assert not offenders, f"G3: OwnedCheckout._mint referenced outside {_MINTER}:\n{_format(offenders)}"


def test_g4_effective_root_identifier_is_banned() -> None:
    offenders, scanned = _scan(effective_root_identifiers)
    _assert_scan_floor(scanned, minus_org_pack=True)
    remaining = _not_allowlisted(offenders)
    assert not remaining, f"G4: identifier effective_root found in src/ ({len(remaining)} sites):\n{_format(remaining)}"


def test_g5_no_bare_path_owned_root() -> None:
    offenders, scanned = _scan(bare_owned_root_paths)
    _assert_scan_floor(scanned, minus_org_pack=True)
    remaining = _not_allowlisted(offenders)
    assert not remaining, f"G5: bare Path-typed owned root parameter/field ({len(remaining)} sites):\n{_format(remaining)}"


def _defined_names(tree: ast.Module) -> set[str]:
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def test_g6_named_consumers_declare_owned_pin() -> None:
    offenders: list[Offender] = []
    found: set[str] = set()
    for rel_path, required in _G6_CONSUMERS.items():
        tree = parse_file(_REPO_ROOT / rel_path, display=rel_path)
        present = _defined_names(tree) & required.keys()
        found.update(present)
        offenders.extend(Offender("G6", rel_path, 1, f"consumer {name} ({required[name]}) not defined in this module") for name in required.keys() - present)
        offenders.extend(owned_signature_pins(tree, rel_path, required))
    total = sum(len(v) for v in _G6_CONSUMERS.values())
    assert total == _G6_CONSUMER_COUNT, f"G6 consumer table drifted from contract s7: {total} != {_G6_CONSUMER_COUNT}"
    assert len(found) == _G6_CONSUMER_COUNT, f"G6 found {len(found)} of {_G6_CONSUMER_COUNT} consumer definitions"
    assert not offenders, f"G6: consumers missing the `owned: OwnedCheckout | None` pin ({len(offenders)}):\n{_format(offenders)}"


_TRANSITIONAL_MARKER = "TRANSITIONAL" + "(WP18)"


def _marker_hits() -> list[str]:
    hits: list[str] = []
    for root in (_REPO_ROOT / "src", _REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or path.resolve() == _THIS_FILE:
                continue
            for lineno, line in enumerate(read_source(path).splitlines(), start=1):
                if _TRANSITIONAL_MARKER in line:
                    hits.append(f"  {path.relative_to(_REPO_ROOT).as_posix()}:{lineno}")
    return hits


def test_no_transitional_wp18_markers_remain() -> None:
    hits = _marker_hits()
    assert not hits, f"{len(hits)} transitional marker(s) remain (the closing WP deletes them all):\n" + "\n".join(hits)
