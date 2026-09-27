# Contract: manual global-state mutation census gate

Detector: `tests/architectural/_global_state_scan.py`. Gate: `tests/architectural/test_no_manual_global_state_mutation.py` (the only module that reads the allowlist and compares; it does not import `_home_pin_scan`). Allowlist: `tests/architectural/global_state_allowlist/*.yaml`.

## Site

`(file: repo-relative posix path, qualname: enclosing qualname via specify_cli.contracts.anchoring, kind: cwd|sys.path|sys.modules|os.environ|sys.argv)` — line numbers are never part of a key.

## Allowlist row (YAML)

```yaml
# round-trip: skip: illustrative allowlist row shape (plain YAML data, not a Pydantic contract example)
- file: tests/conftest.py
  qualname: pytest_configure
  kind: os.environ
  count: 3                 # exact number of sites with this key
  class: process-bootstrap # transitional-sweep | process-bootstrap | subprocess-entry | leak-sentinel | deferred-01M3EW3Z
  reason: "Process-wide HOME isolation must exist before any fixture runs."
```

Shard files (permanent): `S1.yaml … S8.yaml` — each shard holds rows **only** for the files listed for it in the mission's `research/sweep_shards.tsv`: `transitional-sweep` rows (drained to zero by that shard's sweep WP) plus any justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`) for its files. `deferred-01M3EW3Z.yaml` holds the `deferred-01M3EW3Z` rows (files owned by mission 01M3EW3Z). Non-transitional rows require a non-empty `reason`.

## Verdicts (all fail the gate)

1. **Unallowlisted site** — a key with no row → message: file, qualname, kind, and the scoped replacement for that kind.
2. **Over-count** — actual > `count`.
3. **Under-count / stale** — actual < `count` (incl. 0) → "shrink the allowlist" naming the row (shrink-only; staleness is an error).
4. **Wrong shard** — a transitional row whose file is not owned by that shard.
5. **Parse failure** — any `*.py` under `tests/` outside the explicit fixture-data exclusion list that fails to parse.
6. **Vacuity floor** — fewer than 3000 files scanned.
7. **Sealed invariants** (separate test `tests/architectural/test_global_state_allowlist_sealed.py`, landed by the Seal WP) — no `transitional-sweep` row remains in any shard, and sites per class do not exceed the frozen per-class caps (set from the actual post-sweep counts, never above the plan projection: process-bootstrap 6, subprocess-entry 13, leak-sentinel 2, deferred-01M3EW3Z 16).

## Scoped replacements (message text per kind)

- cwd → `monkeypatch.chdir(...)` or `with contextlib.chdir(...)` for block scope
- os.environ → `monkeypatch.setenv/delenv(...)` or `mock.patch.dict(os.environ, ...)`
- sys.path → `monkeypatch.syspath_prepend(...)` or remove (rootdir + `pythonpath=src` already cover repo/src)
- sys.modules → `monkeypatch.setitem/delitem(sys.modules, ..., raising=False)` (+ parent-package attribute)
- sys.argv → `monkeypatch.setattr(sys, "argv", [...])` or `mock.patch.object(sys, "argv", [...])`
