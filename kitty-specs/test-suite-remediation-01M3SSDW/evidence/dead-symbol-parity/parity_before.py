"""WP10 / IC-09 parity snapshot (before.json) of today's dead-symbol allowlist (#5346).

Scratchpad-only; never committed. Run from the repository root:

    PYTHONPATH=. uv run --frozen python <scratch>/parity_before.py > <scratch>/before.json

Freezes the exempted (module, name, category) set of every live ``__all__``
location whose final key is in ``_SYMBOL_ALLOWLIST``, the widened #470 set,
and the offenders/stale lists of the real gate pipeline (both must be []).
The parity digest is printed to stderr.
"""

from __future__ import annotations

# TID251: the sha256 calls below digest a JSON parity snapshot, not charter
# content (same rationale as tests/architectural/_symbol_key.py), so
# charter.hasher.hash_content() does not apply.
import hashlib
import json
import subprocess
import sys

from tests.architectural import test_no_dead_symbols as g
from tests.architectural._symbol_key import classify_collisions

decls, all_literal, p2d, p2t, corpus = g._walk_modules()
per_symbol, star = g._imports_by_target(p2d, p2t)
submodule_index = g._submodule_index(per_symbol)
idx = classify_collisions(corpus)

# SymbolKey -> category id (constant name, lower-cased, leading "_" stripped).
cat_of: dict[object, str] = {}
for const_name, keys in g._category_frozensets().items():
    for k in keys:
        assert k not in cat_of, f"{k} in two categories"
        cat_of[k] = const_name.lstrip("_").lower()

rows = sorted(
    [mod, name, cat_of[key]]
    for mod, names in all_literal.items()
    for name in names
    if (key := g._resolve_final_key(name, mod, corpus.get(mod), corpus, idx)) is not None and key in g._SYMBOL_ALLOWLIST
)
widened = sorted(list(s.split("::", 1)) for s in g._WIDENED_SCOPE_GRANDFATHERED_470)

# Reproduce test_no_public_symbol_in_all_is_unimported's pipeline verbatim.
widened_only = {m: left for m, names in decls.items() if (left := names - all_literal.get(m, frozenset()))}
offenders = g._compute_offenders(all_literal, per_symbol, star, g._SYMBOL_ALLOWLIST, corpus, idx)
pre_rescue = g._compute_offenders(widened_only, per_symbol, star, frozenset(), corpus, idx)
widened_stale = g._compute_widened_stale(g._WIDENED_SCOPE_GRANDFATHERED_470, pre_rescue, corpus)
offenders = g._apply_widened_scope_exemptions(offenders + pre_rescue, all_literal, corpus)
stale = g._compute_stale(all_literal, star, corpus, idx, g._SYMBOL_ALLOWLIST, per_symbol, submodule_index)
dangling = g._compute_dangling(g._SYMBOL_ALLOWLIST, all_literal, idx, offenders)

doc = {
    "base_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
    "allowlist": rows,
    "widened_470": widened,
    "offenders": sorted(offenders),
    "stale": sorted(stale + dangling + widened_stale),
    "counts": {"allowlist": len(rows), "widened_470": len(widened)},
}

assert doc["counts"] == {"allowlist": 293, "widened_470": 91}, doc["counts"]
assert len(set(map(tuple, rows))) == len(rows), "duplicate (module, name, category) rows"
assert doc["offenders"] == [] and doc["stale"] == [], (doc["offenders"], doc["stale"])

digest = hashlib.sha256(  # noqa: TID251
    json.dumps({k: doc[k] for k in ("allowlist", "widened_470", "offenders", "stale")}, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
json.dump(doc, sys.stdout, sort_keys=True, indent=2)
sys.stdout.write("\n")
print(f"parity_digest={digest} counts={doc['counts']} base_sha={doc['base_sha']}", file=sys.stderr)
