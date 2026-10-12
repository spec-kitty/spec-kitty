---
title: "Code grounding — derive the mission-state audit's CI trigger list"
mission: audit-trigger-derivation-01M4RKRD
issue: 6090
type: explanation
updated: 2026-10-12
audience: agentic-framework-core-team
---

# Code grounding: mission-state audit trigger derivation (#6090)

Read-only investigation performed on `origin/main` @ `8a911083` before any edit.
All module sets below are reproduced from live runs of the audit, not from memory.

## 1. The defect (two hand-copied lists that can drift)

`#6087` (landing of the `#6058` follow-up) added, from **a one-time call trace**
of `spec-kitty doctor mission-state --audit`, a hand-written list of "the modules
the audit executes". That list exists in **two** places that can drift from
reality and from each other:

1. **`.github/workflows/ci-router.yml`** — the `mission_state` dorny
   paths-filter group (`ci-router.yml:265-292`): the globs that decide when the
   `mission-state-audit` job runs on a PR.
2. **`tests/ci/test_mission_state_audit_routing.py::AUDIT_INPUT_PATHS`**
   (`:154-181`) — a second copy of the same list, consumed by
   `test_audit_inputs_match_the_group_directly` and
   `test_the_reducer_bump_commit_selects_the_audit_job`.

`#6087`'s own landing note names the drift risk and defers it here: *"keeping the
router's audit-module list in step with the modules the audit executes is tracked
as #6090 (the list is a one-time trace; the nightly is the backstop)."*

### How `#6058` happened (the motivating incident)

CI invokes `uv run --frozen --no-sync spec-kitty doctor mission-state --audit
--fail-on teamspace-blocker --json` (`ci-router.yml`, the `mission-state-audit`
job). The router gate counts a **skipped** job as a pass. When a change touches a
module (or dependency) the audit's verdict depends on but which is **outside** the
`mission_state` globs, the audit job is not selected, the PR goes green, and the
nightly `mission-state-audit` job (`ci-nightly.yml`) catches it only **after
merge**. In `#6058` the trigger miss was a `spec-kitty-events` bump that changed
only `uv.lock`/`pyproject.toml`; `#6087` added the manifests to the group. #6090
closes the *module* half of the same class: a refactor that makes the audit
import/execute a new `src/` module silently un-guarded.

## 2. Audit entry point and executed-module call graph

- CLI surface: `src/specify_cli/cli/commands/_mission_state_doctor.py`
  → `_run_audit_mode` → `specify_cli.audit.run_audit(AuditOptions(...))`.
- Engine: `src/specify_cli/audit/engine.py::run_audit` — documented
  **read-only**: "no files are written, no processes are spawned, and no network
  calls are made." It walks `scan_root` for mission dirs and runs 7 classifiers +
  identity adapter per mission; `classify_status_json` runs the **reducer**
  (`specify_cli.status.materialize_snapshot` / `materialize_to_json`) for the
  `SNAPSHOT_DRIFT` check when a `status.json` exists and the event log is not
  corrupt. This reducer path is the `#6058` surface.

In-process driver (what the derived test and the probes use):

```python
from specify_cli.audit import AuditOptions, run_audit
run_audit(AuditOptions(repo_root=<root>, scan_root=<kitty-specs>,
                       mission_filter=None, fail_on=None, invoking_cwd=<root>))
```

### Ground-truth executed set (real corpus)

Running the audit over the **real repo `kitty-specs/` corpus (604 missions)** —
exactly what CI audits — and capturing the `src/` modules whose functions execute
yields **33 modules, every one already matched by a `mission_state` glob (zero
uncovered)**. The 33: the `audit/` package (engine, models, detectors,
shape_registry, identity_adapter, 7 classifiers) + `status/{reducer, store,
models, identity_audit, lane_reader, lifecycle_events}` + `migration/mission_state`
+ `context/mission_resolver` + `core/{paths,utils,checkout_identity}` +
`mission_metadata` + `frontmatter` + `identity/aliases` + `lanes/branch_naming` +
`kernel/{meta_decode,guarded_read,git/{listing,paths,runner}}` +
`charter/activation/mission_type_key`.

**Pivotal conclusion: the audit currently executes NO `src/` module outside the
existing `mission_state` globs.** Therefore this mission does **not** need to edit
`ci-router.yml` (no missing glob today); it only needs to ADD the derived test and
REMOVE the hand copy. The `.github/workflows/` push-scope caveat is thus not in
play. (If a future run surfaces a genuinely uncovered module, the fix is a new
`**/`-prefixed glob — see §5.)

## 3. How other router groups are validated (fit the convention)

`tests/ci/test_mission_state_audit_routing.py` reads the parsed router through the
single authority `scripts/ci/gate_selection.py::load_router` / `select_gates`
("Every assertion reads the parsed router … never a restated copy."). Group→glob
matching is `fnmatch.fnmatch(path, pattern)` (`gate_selection._match_groups`), so
`**/specify_cli/audit/**` matches `src/specify_cli/audit/engine.py`. Sibling
guards:

- `tests/architectural/test_ci_router_transcription_guards.py` pins the router's
  three hand-transcriptions (filter block, `changes.outputs`, FR-004 `unmatched`
  loop) to their single sources of truth — the same "no second hand copy" ethos.
- `test_scrub_documentation_copy_equals_the_router_group` pins
  `tests/release/ci_retirement_scrub.json`'s `non_src_router_groups[mission_state]`
  to the router filter. Because this mission does **not** change the globs, that
  scrub copy stays valid (no edit needed).

The derived check therefore uses `load_router`/`select_gates` for coverage (canon)
and **removes** a restated copy (`AUDIT_INPUT_PATHS`) — a `canonical-source-unification`
(Standing Order 6) win, aligned with the transcription-guard doctrine.

## 4. Feasibility: in-process audit under `sys.setprofile` — and the pitfalls

Confirmed the audit can be driven in-process on a small fixture with no network /
side effects (`run_audit` is read-only). Reliably capturing the **executed
modules**, however, required resolving two real pitfalls (documented so the test
is not fragile):

- **A cold interpreter over-captures.** Starting `setprofile` before importing
  `specify_cli.audit` in a fresh process captures **~360 `src/` modules** — the
  whole `specify_cli`/`charter` **package-initialization** tree (registries, DRG
  graphs built at first import). That is exactly the rejected "trigger on all of
  `specify_cli/`+`kernel/`+`charter/`" set; it is NOT the audit's footprint.
- **Naive in-process (no warm-up) is order-sensitive.** `setprofile`'s `call`
  event fires on module-body execution at import time, so whether an import-only
  module (e.g. the eagerly-imported `migration/*` siblings pulled by
  `migration/__init__`) is captured depends on whether an earlier test already
  imported it — flaky across a full run.

**Reliable mechanism (deterministic, order-independent):** run the audit **once to
warm up** (so every lazy import is resolved), then profile a **second**
`run_audit` call, recording only **function-call** frames (`co_name !=
"<module>"`, i.e. exclude import-time bodies). This yields the audit's true
execution footprint. Verified `A == B` across repeated runs, and verified the
warm in-process set equals the real-corpus set.

### The small fixture

A one-mission git repo (`meta.json` + `status.events.jsonl` + a reducer-generated
`status.json` + `spec.md` + `tasks/WP01.md`, committed so git-tracked detection
runs) reproduces the **exact 33-module real-corpus footprint in ~0.01 s with zero
artifacts**. Two fixture pitfalls were found and eliminated:

- A legacy `feature_slug` key on events sent the audit down a slug-resolution path
  that pulled in `kernel/resolution.py` (an artifact absent from the real corpus).
  Modern events key on `mission_id` only — removing `feature_slug` eliminated it.
- The reducer path only runs when `status.json` exists and the event log is not
  corrupt (`classify_status_json`, `skip_drift`); the bundled
  `src/specify_cli/audit/fixtures/` have no `status.json`, so they do **not**
  exercise the `#6058` reducer surface. The fixture therefore ships its own
  `status.json`.

## 5. Rejected alternatives (must not regress into either)

- **Static import-graph closure** over the audit entry point: ~534 modules —
  massive over-trigger. The runtime executed set is 33 because runtime loading
  pulls only what the audit actually runs, not the full static transitive closure.
- **Trigger on all of `specify_cli/` + `kernel/` + `charter/`**: ~1 min of audit
  on almost every PR. The cold-interpreter capture (§4) is a mechanical twin of
  this and is explicitly avoided by the warm, function-call-scoped capture.

## 6. Gates / references that touch the router or these files

- `ci-router.yml` and `ci-nightly.yml` carry **comments** pointing at
  `tests/ci/test_mission_state_audit_routing.py`; editing the test file does not
  require a workflow edit.
- No gate requires `AUDIT_INPUT_PATHS` to exist under that name; its two consuming
  tests live in the same file we own and are re-pointed onto the derived set (for
  executed modules) while keeping the manifest/alignment assertions (manifests,
  the workflow, and the renderer are legitimate trigger inputs that the audit does
  **not** execute in-process and so cannot be derived — they stay an explicit
  small list).
- `tests/ci/test_mission_state_audit_routing.py` is `pytest.mark.fast`; it imports
  `scripts.ci.gate_selection` and `tests.ci._gh_if`.

## 7. 90-day churn of the touched files

- `.github/workflows/ci-router.yml` — 18 commits / 90 days (hot; derivation
  earns its keep).
- `tests/ci/test_mission_state_audit_routing.py` — 8 commits / 90 days.
- `scripts/ci/gate_selection.py` — 1 commit / 90 days (stable authority to reuse).

## 8. Shape of the fix (feeds the spec)

1. Add a non-vacuous test (in `tests/ci/test_mission_state_audit_routing.py`, the
   conventional home) that drives the audit in-process on the small git fixture,
   warm-captures the executed `src/` modules, and asserts each is matched by the
   `mission_state` group via `select_gates`/`load_router`. **RED** when a module
   is executed outside the globs (self-mutation-proven both directions).
2. Remove `AUDIT_INPUT_PATHS`; re-point its two consumer tests onto the derived
   set (executed modules) plus a small explicit non-executed-input list
   (manifests + workflow + renderer) for the alignment assertions.
3. No `ci-router.yml` edit (all 33 executed modules already covered). No scrub
   edit. No runtime/product behaviour change.

### Observation (out of scope, not fixed here)

The reducer's own `materialize_to_json` output carries `schema_version`, which the
audit's shape registry flags `UNKNOWN_SHAPE` (info) on a freshly-reduced
`status.json`. This is a reducer/shape-registry info-level mismatch, not a
`teamspace-blocker`, and is unrelated to trigger derivation — noted for a possible
future ticket, deliberately untouched (no behaviour change in this mission).
