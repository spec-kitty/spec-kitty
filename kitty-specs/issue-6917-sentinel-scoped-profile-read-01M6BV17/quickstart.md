# Quickstart — verify the scoped sentinel read

Run from the repository root of a checkout of this branch.

## 0. Environment

```bash
make sync-packs            # once per checkout; fetches the pinned pack trees
uv sync --frozen --all-extras
```

## 1. Bounded profile parses (the issue's acceptance guard)

```bash
uv run pytest tests/charter/test_tasks_status_sentinel_scope_6917.py -q
```

The census case renders a two-profile board through the production entry point and counts
agent-profile YAML documents parsed. On unmodified `main` it counts 26; on this branch it counts at
most 3. The same module asserts the 👤 marker text is unchanged and that an empty board parses no
profile at all.

## 2. Scoped loader parity

```bash
uv run pytest tests/charter/test_agent_profile_scoped_load.py -q
```

Covers: every shipped profile id agrees with the full repository; an org-pack override and a
project overlay of `human-in-charge` agree with the repository (including `sentinel: false`);
language-scoped profiles are excluded exactly as `get()` excludes them; the default (`only_ids=None`)
load is unchanged.

## 3. Structural marker ratchets

```bash
uv run pytest tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py \
              tests/charter_offering/test_human_in_charge_profile.py -q
```

The 👤 marker must survive an activation deny entry and a narrowed `activated_agent_profiles`.

## 4. Sole-door gates

```bash
uv run pytest tests/architectural/test_charter_sole_door_agent_profile_repository.py \
              tests/architectural/test_charter_sole_door_offering_service.py \
              tests/architectural/test_charter_sole_door_inner_reacharound.py \
              tests/architectural/test_charter_sole_door_resolver_imports.py -q
```

Zero violations, zero unresolved constructions, zero new exclusions.

## 5. Manual measurement (optional)

```bash
uv run python - <<'PY'
import time
from pathlib import Path
from charter.activation.active_charter_service_builder import build_agent_profile_sentinels
from charter.activation.active_charter_service_builder import build_active_charter_service

root = Path.cwd()
t0 = time.perf_counter(); svc = build_active_charter_service(root); repo = svc.agent_profile_repository
print("baseline path:", round(time.perf_counter() - t0, 3), "s")
t0 = time.perf_counter(); print(build_agent_profile_sentinels(root, ["human-in-charge"]))
print("scoped path:", round(time.perf_counter() - t0, 3), "s")
PY
```

Baseline on this checkout: ~2.1 s and 26 profile documents. Scoped: ≤ 0.5 s and one document
(second call in the same process is cheaper still, since shipped pack parses are memoised per
change).
