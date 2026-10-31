# Quickstart — prove the system status actor by hand

Mission `system-status-actor-01M67HTR`. Every command is run from the repository root of a
checkout on `issue-6722-system-status-actor`.

## 1. The shape, without a mission

```bash
uv run python - <<'PY'
from specify_cli.status.actor import build_system_actor, ActorRole
from specify_cli.status.models import decode_actor, actor_identity_str, is_migration_actor

seed = build_system_actor("migration:backfill_runtime_state")
print(seed)                      # {'tool': 'migration:backfill_runtime_state', 'role': 'system', 'profile': None, 'model': None}
print(ActorRole.SYSTEM)          # system
print(decode_actor(seed) == seed)                 # True  — the CLI reader keeps it
print(actor_identity_str(seed))                   # migration:backfill_runtime_state
print(is_migration_actor(seed))                   # True  — still a seed
print(actor_identity_str(seed) == "migration:backfill_runtime_state")  # True

from spec_kitty_events.diary import decode_actor as shared_decode
print(shared_decode(seed) == seed)                # True  — the shared decoder keeps it too
PY
```

## 2. A bootstrap seed carries it

```bash
# On a mission with uninitialised work packages:
spec-kitty agent mission finalize-tasks --mission <slug>
python - <<'PY'
import json, pathlib
rows = [json.loads(l) for l in pathlib.Path("kitty-specs/<slug>/status.events.jsonl").read_text().splitlines() if l.strip()]
print([r["actor"] for r in rows][:3])
# [{'tool': 'finalize-tasks', 'role': 'system', 'profile': None, 'model': None}, ...]
PY
```

## 3. An existing log still reduces, byte for byte

```bash
# On the base commit, then again on this branch; compare the two snapshots.
git stash list  # expect empty, clean tree
uv run python - <<'PY'
import pathlib, hashlib
from specify_cli.status.reducer import reduce_parsed
from specify_cli.status.store import read_event_stream
out = {}
for d in sorted(pathlib.Path("kitty-specs").glob("*/status.events.jsonl")):
    feature = d.parent
    try:
        snap = reduce_parsed(read_event_stream(feature))
    except Exception as exc:          # a log this CLI cannot reduce today stays that way
        out[feature.name] = f"error: {type(exc).__name__}"
        continue
    out[feature.name] = hashlib.sha256(repr(snap).encode()).hexdigest()
print(hashlib.sha256(repr(sorted(out.items())).encode()).hexdigest())
PY
```

The digest must be identical before and after the change. `tests/status/test_system_actor_6722.py`
pins the same property in-process, so the manual run is a sanity check, not the evidence.

## 4. A mixed-shape log reduces like an all-string log

```bash
uv run --frozen pytest tests/status/test_system_actor_6722.py -k mixed_shape -q
```

## 5. A pre-change corpus still verifies

```bash
uv run --frozen pytest tests/unit/migration/test_system_actor_6722.py -k "verify or seam" -q
```

By hand: seed a fixture mission with the *base* code (string seeds), check out this branch,
then

```bash
spec-kitty migrate backfill-runtime-state --mission <slug> --verify
# expect: verify ok (the immutable string seed row is sound; only its actor shape differs)
```

## 6. The whole family

```bash
uv run --frozen pytest tests/status/test_system_actor_6722.py \
  tests/unit/migration/test_system_actor_6722.py \
  tests/consolidation/test_system_actor_6722.py \
  tests/lanes/test_system_actor_6722.py -q
```

## What "done" looks like

- Every new system event in `status.events.jsonl` reads
  `{"tool": ..., "role": "system", "profile": null, "model": null}`.
- The board, the snapshot's `actor` slot and every seed gate answer exactly as before.
- `docs/architecture/status-model.md` states the rule and the changelog cites `(#6722)`.
