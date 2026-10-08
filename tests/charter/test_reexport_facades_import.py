"""Coverage + smoke gate: the doctrine→charter re-export facades import cleanly.

Five facades — ``charter.assets``, ``charter.glossary_packs``, ``charter.missions``,
``charter.model_routing`` and ``charter.spdd_reasons`` — are pure re-export doors
for the future ``spec-kitty-doctrine`` wheel. Nothing under ``src/`` imports them
yet, so their only importer was the architectural facade-identity gate
(``tests/architectural/test_charter_facades_reexport_offering.py``). That gate runs
in the ``arch-adversarial`` shard, which measures ``--cov=specify_cli`` /
``--cov=mission_runtime`` but **not** ``--cov=charter`` — so the facades' only
lines (their ``from charter.offering.… import …`` block and ``__all__``) had zero recorded
coverage in every report the critical-path ``diff-coverage`` gate aggregates, and
the gate failed at 0%.

This test lives in ``tests/charter/`` — the ``fast-tests-charter`` shard, which
runs ``--cov=charter`` and emits ``coverage-fast-charter.xml`` (consumed by the
``diff-coverage`` aggregator). Importing each facade here records their module
lines. It also asserts every name each facade advertises in ``__all__`` resolves,
a cheap re-export smoke that would catch a stale or broken door.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.fast

_FACADE_MODULES = (
    "charter.assets",
    "charter.glossary_packs",
    "charter.missions",
    "charter.model_routing",
    "charter.pack_paths",
    "charter.spdd_reasons",
    "charter.template_catalog",
)


@pytest.mark.parametrize("module_name", _FACADE_MODULES)
def test_reexport_facade_imports_and_all_symbols_resolve(module_name: str) -> None:
    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None)
    assert exported, f"{module_name} must declare a non-empty __all__"
    unresolved = [name for name in exported if getattr(module, name, None) is None]
    assert not unresolved, f"{module_name} advertises unresolved/None __all__ names: {unresolved}"
