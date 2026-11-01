# Quickstart — verifying the charter activation shard routing (#6336)

All commands run from the repository root of a checkout with the fetched packs
(`make sync-packs`) and a synced venv (`uv sync --frozen --all-extras`).

## 1. The routing answer (the same call `ci-modules.yml` makes)

```bash
PYTHONPATH=. python - <<'PY'
from scripts.ci.gate_selection import gate_selection  # noqa: F401  (module import check)
from scripts.ci.gate_selection import load_router, select_gates, select_modules

router = load_router()
for path in (
    ".kittify/charter/charter.yaml",
    ".kittify/charter/activation.yaml",
    "packs/internal.source.yaml",
    "src/kernel/activation_ledger_store.py",
    "src/charter/activation/activation_ledger.py",
):
    sel = select_gates([path], router=router)
    print(f"{path:52s} groups={sorted(sel.matched_groups)} modules={sorted(select_modules([path], router=router))}")
PY
```

Expected after this mission:

```
.kittify/charter/charter.yaml                 groups=['charter_activation', 'corpus']  modules=['charter']
.kittify/charter/activation.yaml              groups=['charter_activation', 'corpus']  modules=['charter']
packs/internal.source.yaml                    groups=['charter_activation', 'corpus']  modules=['charter']
src/kernel/activation_ledger_store.py         groups=['charter', 'core_misc', 'kernel', 'unit'] modules=['charter', 'core_misc', 'kernel', 'unit']
src/charter/activation/activation_ledger.py   groups=['charter']                       modules=['charter']
```

Before the change the first three print `groups=['corpus'] modules=[]` and the
ledger floor prints `modules=['core_misc', 'kernel', 'unit']`.

## 2. Fail-closed is intact

```bash
PYTHONPATH=. python - <<'PY'
from scripts.ci.gate_selection import load_router, select_gates

router = load_router()
sel = select_gates(["src/specify_cli/__unmapped_probe__/x.py", ".kittify/charter/charter.yaml"], router=router)
print(sel.unmatched_src, len(sel.selected_code_shards), len(router.code_shard_jobs))
PY
```

Expected: `True <n> <n>` — an unmapped `src/**` change still forces run-all even
when the activation store changed in the same diff.

## 3. Targeted gates (never a full heavy suite locally)

```bash
uv run --frozen pytest -q \
  tests/ci/test_charter_activation_routing.py \
  tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_workflow_coherence.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py \
  tests/architectural/test_ci_quality_path_filters.py \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_retirement_scrub.py \
  tests/architectural/test_consumer_census_routing.py \
  tests/ci/test_fanout_derivation.py \
  tests/ci/test_consumer_census.py
```

## 4. Red-first proof (pre-fix)

```bash
git stash push -- .github scripts tests        # keep only the new test module
uv run --frozen pytest -q tests/ci/test_charter_activation_routing.py   # must FAIL
git stash pop
```

The failure is the routing hole: `charter` is absent from each selection and the
router declares no `charter_activation` group.

## 5. Docs freshness (only if a doc/ADR is touched)

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
```
