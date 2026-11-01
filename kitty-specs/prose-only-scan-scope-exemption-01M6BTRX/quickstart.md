# Quickstart: verify the prose-only scan-scope exemption (#6999)

All commands run from the repository root of the mission checkout.

## 1. Reproduce the defect on a base without the fix

```bash
uv run --frozen python - <<'PY'
import yaml, sys
sys.path.insert(0, ".")
from scripts.ci.gate_selection import load_router, select_battery_gates, select_gates
from tests.ci._gh_if import BASE_CONTEXT_ALL_FALSE, eval_gh_if

path = "scripts/release/extract_changelog.py"
print("groups:", sorted(select_gates([path], router=load_router()).matched_groups))
print("declared scan-scope gates:", sorted(select_battery_gates([path])))
wf = yaml.safe_load(open(".github/workflows/ci-router.yml"))
ctx = dict(BASE_CONTEXT_ALL_FALSE)
ctx["changes.arch_scan_scope"] = True  # the routing group: a declared-scope diff
ctx["prose-scan.prose_only"] = True
ctx["prose-scan.scan_scope_match"] = True  # prose-scan's companion output (#6999)
print("battery if: under prose-only:", eval_gh_if(wf["jobs"]["architectural-heavy"]["if"], ctx))
PY
```

Before the fix the last line prints `False` while the gate list is non-empty:
the down-route drops gates that declare the changed path. After the fix it
prints `True` and the selection (with `prose_only=True`) is the declared match
set.

## 2. Run the pinned tests

```bash
uv run --frozen python -m pytest \
  tests/ci/test_battery_scope.py \
  tests/ci/test_ci_module_wiring.py \
  tests/ci/test_ci_config_battery_routing.py \
  tests/architectural/test_battery_scan_scope_routing.py -q
```

## 3. Exercise the CLI the workflow runs

```bash
uv run --frozen --no-sync python -m scripts.ci.battery_scope select \
  --base origin/main --head HEAD --mode pr --prose-only true \
  --battery-part 1/2 --out /tmp/gates-1.txt
```

A prose-only diff over declared scopes prints `mode=scoped`, `run=true` and a
gate file; a full/code answer prints `mode=full`. An unusable base prints
`mode=full` and a `::warning::` — never a narrower run.

## 4. Lint and type-check the touched Python

```bash
uv run --frozen ruff check scripts/ci/battery_scope.py scripts/ci/gate_selection.py tests/ci/test_battery_scope.py
uv run --frozen ruff format --check --force-exclude scripts/ci/battery_scope.py scripts/ci/gate_selection.py tests/ci/test_battery_scope.py
uv run --frozen mypy --explicit-package-bases scripts/ci/battery_scope.py scripts/ci/gate_selection.py
```

## 5. Docs freshness

If `docs/development/reference/ci-gate-mechanics.md` is edited (no new page or
ADR is added by this mission):

```bash
uv run python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
```
