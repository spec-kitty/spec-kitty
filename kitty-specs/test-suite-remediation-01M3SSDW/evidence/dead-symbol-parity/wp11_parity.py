"""WP11 / T053 data-level parity (scratchpad only). Run from the lane root with uv run --frozen python."""

from __future__ import annotations

# TID251: the sha256 calls below digest a JSON parity snapshot, not charter
# content (same rationale as tests/architectural/_symbol_key.py), so
# charter.hasher.hash_content() does not apply.
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from tests.architectural import _dead_symbol_allowlist as a  # noqa: E402
from tests.architectural import test_no_dead_symbols as g  # noqa: E402

BEFORE = Path(sys.argv[1])

old = {(k.module_path or k.source_module, k.bare_name) for k in g._SYMBOL_ALLOWLIST}
new = {(k.module, k.name) for k in a.SYMBOL_ALLOWLIST}
print(f"allowlist: old={len(old)} new={len(new)} equal={old == new}")
assert old == new and len(new) == 293, (sorted(old - new)[:5], sorted(new - old)[:5])

old_w = set(g._WIDENED_SCOPE_GRANDFATHERED_470)
new_w = set(a.WIDENED_SCOPE_GRANDFATHERED_470)
print(f"widened_470: old={len(old_w)} new={len(new_w)} equal={old_w == new_w}")
assert old_w == new_w and len(new_w) == 91

# category parity: old owning category (lower-cased, '_' stripped) == new entry.category for every key
old_cat = {}
for const, keys in g._category_frozensets().items():
    for k in keys:
        old_cat[(k.module_path or k.source_module, k.bare_name)] = const.lstrip("_").lower()
new_cat = {(e.key.module, e.key.name): e.category for e in a.ALLOWLIST.entries}
mismatch = {k: (old_cat[k], new_cat[k]) for k in new_cat if old_cat[k] != new_cat[k]}
print(f"category parity: {len(new_cat)} entries, mismatches={len(mismatch)}")
assert not mismatch, mismatch

# merge_three_layers trap
mtl = [e for e in a.ALLOWLIST.entries if e.key.name == "merge_three_layers"]
print(f"merge_three_layers: {[str(e.key) for e in mtl]}")
assert [str(e.key) for e in mtl] == ["charter.drg::merge_three_layers"]

# module_path-tier entries map to module_path
mp = sorted((k.module_path, k.bare_name) for k in g._SYMBOL_ALLOWLIST if k.module_path is not None)
missing_mp = [x for x in mp if x not in new]
print(f"module_path-tier entries: {len(mp)}, all mapped to module_path: {not missing_mp}")
assert len(mp) == 18 and not missing_mp

# row-level comparison against WP10's before.json (module, name, category) + widened
before = json.loads(BEFORE.read_text(encoding="utf-8"))
after_allowlist = sorted([e.key.module, e.key.name, e.category] for e in a.ALLOWLIST.entries)
after_widened = sorted([e.key.module, e.key.name] for e in a.ALLOWLIST.widened_entries)
rows_equal = after_allowlist == sorted(before["allowlist"])
widened_equal = after_widened == sorted(before["widened_470"])
print(
    f"before.json rows: allowlist {len(before['allowlist'])} vs {len(after_allowlist)} equal={rows_equal}; "
    f"widened {len(before['widened_470'])} vs {len(after_widened)} equal={widened_equal}"
)
assert rows_equal and widened_equal
data_digest = hashlib.sha256(json.dumps({"allowlist": after_allowlist, "widened_470": after_widened}, sort_keys=True).encode()).hexdigest()  # noqa: TID251
before_digest = hashlib.sha256(  # noqa: TID251
    json.dumps({"allowlist": sorted(before["allowlist"]), "widened_470": sorted(before["widened_470"])}, sort_keys=True).encode()
).hexdigest()
print(f"row-digest before={before_digest} after={data_digest} equal={before_digest == data_digest}")
print(f"before.json base_sha={before['base_sha']} lane HEAD={subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}")
print("PARITY OK")

# WP10's digest form (parity_before.py:65): allowlist/widened from the YAML, offenders/stale from before.json
# (the gate is not switched in WP11, so offenders/stale are still the old gate's; WP12 re-takes them).
wp10_form = hashlib.sha256(  # noqa: TID251
    json.dumps(
        {"allowlist": after_allowlist, "widened_470": after_widened, "offenders": before["offenders"], "stale": before["stale"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()
print(
    f"WP10-form digest from YAML rows = {wp10_form} (WP10 baseline c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1) "
    f"equal={wp10_form == 'c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1'}"
)
assert wp10_form == "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
print("WP10 DIGEST MATCH")
