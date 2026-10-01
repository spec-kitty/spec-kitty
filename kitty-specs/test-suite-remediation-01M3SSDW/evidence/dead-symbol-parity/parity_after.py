"""WP12 / T060 parity snapshot (after.json) of the re-keyed dead-symbol gate (#5346).

Scratchpad-only; never committed. Run from the lane root:

    PYTHONPATH=. uv run --frozen python <scratch>/parity_after.py <scratch>/before_wp12.json > <scratch>/after.json

Same JSON conventions and digest as WP10's parity_before.py. The rows come from
the NEW path: (module, name) membership in load_allowlist().keys plus the G1
keyability precondition; offenders/stale from the new pipeline (the real-tree
test's own seam calls: _evaluate_allowlist + _evaluate_widened on ONE parse).
"""

from __future__ import annotations

# TID251: the sha256 calls below digest a JSON parity snapshot, not charter
# content (same rationale as tests/architectural/_symbol_key.py), so
# charter.hasher.hash_content() does not apply.
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from tests.architectural import test_no_dead_symbols as g
from tests.architectural._dead_symbol_allowlist import WIDENED_SCOPE_GRANDFATHERED_470, DeadSymbolKey, load_allowlist

allowlist = load_allowlist()
category_of = {entry.key: entry.category for entry in allowlist.entries}
inputs = g._real_tree_inputs()

rows = sorted(
    [mod, name, category_of[DeadSymbolKey(mod, name)]]
    for mod, names in inputs.all_literal_decls.items()
    for name in names
    if DeadSymbolKey(mod, name) in allowlist.keys and g._resolve_final_key(name, mod, inputs.corpus.get(mod), inputs.corpus, inputs.collision_index) is not None
)
widened = sorted(list(s.split("::", 1)) for s in WIDENED_SCOPE_GRANDFATHERED_470)

evaluation = g._evaluate_allowlist(inputs.all_literal_decls, inputs.per_symbol, inputs.star_targets, inputs.corpus, allowlist, inputs.collision_index)
widened_offenders, widened_stale = g._evaluate_widened(
    inputs.decls, inputs.all_literal_decls, inputs.per_symbol, inputs.star_targets, inputs.corpus, inputs.collision_index, allowlist.widened_qualified
)

doc = {
    "base_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
    "allowlist": rows,
    "widened_470": widened,
    "offenders": sorted(evaluation.offenders + widened_offenders),
    "stale": sorted([finding.render() for finding in evaluation.stale] + widened_stale),
    "counts": {"allowlist": len(rows), "widened_470": len(widened)},
}

digest = hashlib.sha256(  # noqa: TID251
    json.dumps({k: doc[k] for k in ("allowlist", "widened_470", "offenders", "stale")}, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
json.dump(doc, sys.stdout, sort_keys=True, indent=2)
sys.stdout.write("\n")

before = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
before_digest = hashlib.sha256(  # noqa: TID251
    json.dumps({k: before[k] for k in ("allowlist", "widened_470", "offenders", "stale")}, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
print(
    f"parity_digest after={digest} before={before_digest} equal={digest == before_digest} "
    f"counts={doc['counts']} star_targets={len(inputs.star_targets)} base_sha={doc['base_sha']}",
    file=sys.stderr,
)
assert doc["counts"] == before["counts"] == {"allowlist": 293, "widened_470": 91}, (doc["counts"], before["counts"])
assert digest == before_digest, "PARITY BROKEN"
print("PARITY OK", file=sys.stderr)
