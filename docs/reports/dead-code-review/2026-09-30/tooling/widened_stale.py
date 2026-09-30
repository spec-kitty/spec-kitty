"""Replay the dead-symbol gate's widened pass and list stale grandfather entries.

Run from the repository root. Prints every ``_WIDENED_SCOPE_GRANDFATHERED_470``
entry that the gate's own widened offender pass no longer reports (it gained a
caller, moved into ``__all__``, or is no longer declared) or that the gate's
own-module rescue already exempts. The gate asserts only ``any(...)`` over this
set, so nothing else reports these.
"""

from __future__ import annotations

import importlib
import sys


def main() -> None:
    sys.path[:0] = ["src", "."]
    gate = importlib.import_module("tests.architectural.test_no_dead_symbols")
    decls, all_literals, path_to_dotted, path_to_tree, corpus = gate._walk_modules()
    per_symbol, star = gate._imports_by_target(path_to_dotted, path_to_tree)
    collisions = gate.classify_collisions(corpus)
    widened = {mod: left for mod, names in decls.items() if (left := names - all_literals.get(mod, frozenset()))}
    offenders = set(gate._compute_offenders(widened, per_symbol, star, frozenset(), corpus, collisions))
    stale: list[tuple[str, str]] = []
    for entry in sorted(gate._WIDENED_SCOPE_GRANDFATHERED_470):
        module, _, name = entry.partition("::")
        if entry not in offenders:
            if name in all_literals.get(module, frozenset()):
                stale.append((entry, "in __all__"))
            elif name not in decls.get(module, set()):
                stale.append((entry, "not declared"))
            else:
                stale.append((entry, "has a caller"))
            continue
        parsed = corpus.get(module)
        if parsed is not None and gate._used_within_own_module(parsed.tree, name):
            stale.append((entry, "used in own module"))
    for entry, why in stale:
        print(f"{why}\t{entry}")
    print(f"{len(stale)} of {len(gate._WIDENED_SCOPE_GRANDFATHERED_470)} entries are stale")


if __name__ == "__main__":
    main()
