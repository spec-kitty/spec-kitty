---
work_package_id: WP14
title: Battery per-file timings seed and fast-roster budgets
dependencies:
- WP05
- WP06
requirement_refs:
- FR-004
- NFR-001
- NFR-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
- T029
phase: Phase 3 - Battery partition
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/
create_intent:
- tests/ci/test_battery_roster_budgets.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/ci-shard-timings.json
- .github/ci-module-registry.yml
- tests/ci/test_battery_roster_budgets.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Battery per-file timings seed and fast-roster budgets

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

After WP05 the battery can be partitioned, but `.github/ci-shard-timings.json` holds no battery
timings, so the selector balances the two legs by file count (median weight 1.0 for every file,
with a loud FR-005 warning — D-29). This WP gives the partition **realistic production data
without any local battery run** (C-009) and turns the fast-roster budgets into a deterministic,
static check:

1. `.github/ci-shard-timings.json` gains `battery_file_durations.architectural`
   (`{repo-relative path: seconds}`) seeded from the **68 router `architectural battery` job logs**
   of the 24-hour CI census (2026-09-30T05:32Z → 2026-10-01T04:41Z), plus
   `battery_capture_provenance.architectural` recording exactly how (job ids, window, formula,
   workers, selection) and what supersedes it (WP05's `--suite architectural --from-junit`
   refresh).
2. `tests/ci/test_battery_roster_budgets.py` statically checks, against committed timings:
   every roster file has a timing ≤ its `budget_seconds` ≤ `max_file_budget_seconds`, and
   Σ roster timings ≤ `max_total_measured_seconds` (NFR-002 sizing), plus the predicted
   S1/S2 balance (skew ≤ 20 %, FR-004).
3. Roster budgets in `.github/ci-module-registry.yml` finalised by one stated rule against the
   seed, and roster row 33 (`tests/architectural/test_battery_partition_proof.py`, created by
   WP06) added — this WP owns the registry after WP05; predicted S1/S2 loads recorded in the registry comment and the Activity Log (NFR-001
   input — the measured verdict comes from the Mission PR's CI runs, C-011).

## Context & Constraints

- Read first: `research.md` **D-06, D-29** (the bootstrap is its own step; local capture is
  forbidden), R1 §4b (roster table, the `est` column formula), §4c (timings keys), §9 (sizing);
  `contracts/battery-partition.md` ("Proof obligations": budgets checked statically against
  committed timings); `data-model.md` ("Fast-gate roster", "Shard timings").
- Depends on WP05: registry `special_tiers.architectural` schema (`fast_gate.roster[]` with
  `budget_seconds`, caps, `shards.shard_count`, `shards.timings_key: architectural`) and
  `scripts/ci/capture_shard_timings.py::merge_battery_capture` (writes the two battery keys
  together). WP02 provides `scripts/ci/shard_select.enumerate_base_files` and `battery_parts`.
  Use them; do not re-implement (C-010).
- C-009: **no local run of `tests/architectural`**. A `--collect-only` of the base selection (~3 s)
  is allowed and is how you get per-file test counts.
- The census logs are **session-local scratch data**. The derived table must be copied into the
  repo (the JSON key) with full provenance, so nothing depends on the scratchpad afterwards.
- Lane discipline: `uv run --frozen …`; never `git stash`. Terminology: Mission; "gate selection".
- Runtime overruns stay warnings in the plugin (WP05). This WP's budget check is **static** —
  committed numbers only, no wall-clock assertion (a runtime budget would mint a flake class).

### Inputs (verified 2026-10-01)

- Census logs: `/tmp/claude-1000/-home-stijn-Documents--code-SDD-fork-SHADOW-CLONES-spec-kitty-THREE/9ce64f15-263c-43e7-bb57-e63e51849787/scratchpad/ci-research/battery/logs/<job_id>.log`
  — 68 files, each containing exactly one pytest `slowest durations` section (the battery runs
  with `pytest.ini` `addopts = --durations=0 --durations-min=1.0`, so only phases ≥ 1 s are
  listed; the section ends with `(N durations < 1s hidden.)`). Line shape:
  `2026-09-30T05:55:37.4918691Z 119.53s setup    tests/architectural/test_module_length_agreement.py::test_…`.
  The runs used `-n auto` = 2 workers, so values are contended worker-seconds; they are used as
  relative weights.
- If that directory is gone (different session or host), re-download the same 68 logs — GitHub
  keeps job logs ~90 days, i.e. until about 2026-12-29:
  ```bash
  mkdir -p "$SCRATCH/battery-logs" && cd "$SCRATCH/battery-logs"
  for id in $JOB_IDS; do gh api "repos/spec-kitty/spec-kitty/actions/jobs/$id/logs" > "$id.log"; done
  ```
  `JOB_IDS` (router `architectural battery` jobs, census window):
  `109754448556 109755591286 109758010870 109760118484 109764078427 109767463672 109767536617 109778968422 109779197970 109784366548 109789659806 109792036624 109793655043 109794107712 109833778854 109835359412 109843217789 109851319155 109854599465 109857720749 109862132826 109862753666 109864957339 109866993333 109882511205 109886752644 109888655819 109898925979 109912749866 109914757221 109917610656 109924215433 109927745208 109939003075 109940260446 109942434349 109946739105 109953013088 109966523938 109982034817 110000178640 110006351524 110014479611 110021194731 110026111252 110036547626 110042469700 110055622220 110070110365 110070119339 110074783546 110078860137 110083189284 110085427949 110092144632 110092910713 110094329323 110101931602 110106232578 110120175263 110121794589 110133537512 110178814529 110180888227 110187800086 110217991295 110218065743 110221991679`
  (if logs have expired, stop and ask the orchestrator: the fallback is a dispatched
  `mode=full` router run's junit through WP05's capture mode, per D-29).
- Planning numbers (research R1 §4b, same logs): 132 files have ≥ 1 s tests, Σ medians ≈ 2,206 s;
  roster `est` Σ ≈ **258 worker-s** (max 58.1 s, `test_inline_meta_read_gate.py`); remaining
  201 files ≈ 2,350 worker-s → LPT-2 loads ≈ **1,175 / 1,175** (skew ≈ 0 %).
- **Post-rebase drift (base `bc826fcbcb`, research D-37)**: PR #5503 landed after the census
  window. `test_refresh_dead_symbol_hashes.py` is deleted (its census share drops out of the key
  set automatically); `test_no_dead_symbols.py` was rewritten around a `_real_tree_inputs`
  session cache, so its census median describes the pre-#5503 file; two post-census files exist —
  `test_dead_symbol_allowlist_loader.py` (47 tests, 0.7 s single-file; fast-roster row 34, seed
  ≈ 5.6 s by the formula) and `test_dead_symbol_allowlist_contract.py` (4 tests, **30 s**
  single-file locally, ≈ 0.5 s by the formula; its M11 test builds the `src/` walk that it
  shares with `test_no_dead_symbols.py` through the session cache only when both land on the
  same worker). These are known seed inaccuracies, not seed errors: record them (T028 step 5),
  never hand-tune them (C-009/D-29 — the junit refresh supersedes). The worst case (~60 s CI on
  one leg) is ≈ 5 % of a ≈ 1,175 worker-s leg, inside the 20 % skew bound.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T027 – Red-first: static budget check fails without battery timings

- **Purpose**: Make the NFR-002 sizing rule and the FR-004 balance machine-checked before the data
  exists (ATDD, charter ATDD-First Discipline). It is red today because `battery_file_durations` does not exist.
- **Steps** (new `tests/ci/test_battery_roster_budgets.py`, `pytestmark = pytest.mark.fast`; YAML
  and JSON loaded inside tests, never at import):
  1. Load the registry entry `special_tiers.architectural` and
     `timings = json[...]["battery_file_durations"][shards.timings_key]`.
  2. `test_battery_timings_present_with_provenance`: the key exists and is non-empty;
     `battery_capture_provenance[timings_key]` has `producer`, `captured_at`, `selection`
     (== registry `base.marker`), `workers`, `files_measured` (== `len(timings)`).
  3. `test_every_roster_file_is_timed_and_within_budget`: for each roster entry,
     `path in timings` and `timings[path] <= budget_seconds <= max_file_budget_seconds`;
     failure message names the file, its timing and the remedy ("move it to the shards, or raise
     its budget within the cap after a recapture").
  4. `test_roster_total_within_cap`: `sum(timings[p] for roster) <= max_total_measured_seconds`
     (300 worker-s ≈ 75 s wall at 4 workers; NFR-002 ≤ 5 min with margin).
  5. `test_predicted_legs_balanced`: enumerate the base via
     `shard_select.enumerate_base_files(base.paths, deselect=base.deselect, root=REPO_ROOT)`,
     compute `shard_select.battery_parts(base, roster, shard_count, timings)` and assert the
     leg-load skew `(max-min)/max <= 0.20` (same ceiling the module skew gate uses, NFR-005 of
     the registry's own description). Print the loads (`-s` shows them) for the Activity Log.
  6. `test_timing_keys_are_base_files_or_reported`: stale keys (not in the base) are **allowed**
     — the selector reports them loudly at runtime (FR-005) and a file deletion must not red
     unrelated PRs — but assert their count ≤ 10 % of the keys so a mass rename cannot hide.
  7. Mutation controls (Standing Order #5): feed the same check functions a synthetic
     registry/timings pair where one roster file exceeds its budget, where Σ exceeds the cap, and
     where one leg is 3× the other; each must report. Factor the checks as pure functions taking
     data so the controls do not touch real files.
  8. Run: the four real-data tests are red (`KeyError`/assertion: no `battery_file_durations`);
     the controls are green. Commit the red state.
- **Files**: `tests/ci/test_battery_roster_budgets.py` (new).
- **Parallel?**: No — first commit.
- **Notes**: This file is in `tests/ci` (the `ci` module row runs it per CI-config PR); it is not
  on the fast roster.

### Subtask T028 – Derive per-file medians from the census logs; write the `architectural` key with provenance

- **Purpose**: Seed the timings with realistic production data, reproducibly (D-29).
- **Steps**:
  1. Per-file test counts from the current tree (collect-only, base selection, ~3 s):
     ```bash
     uv run --frozen python -m pytest tests/architectural -m "not performance and not stress and not timing" \
       --deselect tests/architectural/test_no_legacy_terminology.py --deselect tests/architectural/test_layer_rules.py \
       --deselect tests/architectural/test_pyproject_shape.py --deselect tests/architectural/test_archive_root_byte_identical.py \
       --collect-only -q -p no:cacheprovider | grep '::' > "$SCRATCH/battery-collect.txt"
     ```
  2. Derive (keep this script in your scratch space; its full text goes into the PR body so the
     derivation is reproducible from the PR alone):
     ```python
     import collections, glob, json, re, statistics, sys
     from pathlib import Path
     LOGS, COLLECT = Path(sys.argv[1]), Path(sys.argv[2])
     ANSI = re.compile(r"\x1b\[[0-9;]*m")
     ROW = re.compile(r"Z (\d+\.\d+)s (?:setup|call|teardown)\s+(tests/architectural/[^:\s]+\.py)::")
     per_log = []
     for log in sorted(LOGS.glob("*.log")):
         seen, per_file = False, collections.defaultdict(float)
         for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
             line = ANSI.sub("", raw)
             if "slowest durations" in line:
                 seen = True
                 continue
             if seen:
                 if "durations < 1s hidden" in line:
                     break
                 m = ROW.search(line)
                 if m:
                     per_file[m.group(2)] += float(m.group(1))
         assert seen, f"{log.name}: no slowest-durations section"
         per_log.append(per_file)
     counts = collections.Counter(l.split("::", 1)[0] for l in COLLECT.read_text().splitlines() if "::" in l)
     sys.path.insert(0, ".")
     from scripts.ci.shard_select import enumerate_base_files
     base = enumerate_base_files(["tests/architectural"], root=Path("."), deselect=[
         "tests/architectural/test_no_legacy_terminology.py", "tests/architectural/test_layer_rules.py",
         "tests/architectural/test_pyproject_shape.py", "tests/architectural/test_archive_root_byte_identical.py"])
     assert set(counts) <= set(base), sorted(set(counts) - set(base))
     SUB_SECOND_PER_TEST = 0.12   # research R1 §4b `est` column
     seed = {f: round(statistics.median([d.get(f, 0.0) for d in per_log]) + SUB_SECOND_PER_TEST * counts.get(f, 0), 2)
             for f in base}
     json.dump({"n_logs": len(per_log), "seed": seed}, sys.stdout, indent=1)
     ```
     Rules encoded above: median over **all 68 logs** with a file absent from a log counted as
     0 s (its ≥ 1 s phases did not occur that run); plus 0.12 s × the file's current collected
     test count for the hidden sub-second phases; **every** enumerated base file gets a key (the
     one enumeration, D-24), so the selector never reports a permanent "missing" file — a file
     whose every test is marker-deselected (e.g. `test_spec_kitty_home_pin_budget.py`, which is
     `timing`-only) collects 0 tests under the base marker and is seeded at its census median,
     i.e. 0.0, which is its true cost in the battery. Census files that no longer exist are
     dropped automatically (the key set is the current enumeration). Assert `n_logs == 68`.
  3. Write the key through WP05's producer function so the JSON shape is the producer's:
     ```python
     import json, sys
     sys.path.insert(0, ".")
     from scripts.ci.capture_shard_timings import TIMINGS_PATH, merge_battery_capture
     from kernel.clock import now_utc_iso   # canonical clock (capture already uses it)
     derived = json.load(open(sys.argv[1]))
     payload = json.loads(TIMINGS_PATH.read_text(encoding="utf-8"))
     provenance = {
         "producer": "census-seed",
         "method": "median over 68 router `architectural battery` job logs of per-file summed >=1 s phase durations "
                   "(pytest `slowest durations`, --durations-min=1.0; absent = 0) + 0.12 s x collected test count",
         "source": "ci-job-logs", "repository": "spec-kitty/spec-kitty",
         "source_job_ids": [...68 ids...],
         "window": "2026-09-30T05:32Z..2026-10-01T04:41Z", "workers": 2,
         "selection": "not performance and not stress and not timing",
         "files_measured": len(derived["seed"]), "captured_at": now_utc_iso(),
         "known_drift": "post-census #5503 (D-37): test_no_dead_symbols.py rewritten after the window; "
                        "test_dead_symbol_allowlist_{loader,contract}.py post-census (formula-only seed; "
                        "contract measured ~30 s local single-file; WP13's file-end cache_clear() finalizer on "
                        "_real_tree_inputs removes M11's cross-file cache hit, ~30 s more on that worker); "
                        "test_refresh_dead_symbol_hashes.py deleted",
         "superseded_by": "scripts/ci/capture_shard_timings.py --suite architectural --from-junit (D-29)",
     }
     out = merge_battery_capture(payload, "architectural", derived["seed"], provenance)
     TIMINGS_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
     ```
     (Adjust names to what WP05 actually exported; if `merge_battery_capture` is missing, stop and
     raise it — do not hand-edit the JSON.)
  4. `git diff --stat .github/ci-shard-timings.json`: only the two battery keys are added; every
     `module_*` table is byte-identical.
  5. Sanity: one key per enumerated base file (count it on the tip — 235 on `bc826fcbcb`; the 234 of the planning
     census predates #5503, which deleted one battery file and added two); Σ ≈ 2,500-2,600 s
     (the deleted `test_refresh_dead_symbol_hashes.py` share drops out); top entries
     `test_interpreter_shard_coverage.py` (~208), `test_no_dead_symbols.py` (~153, pre-#5503
     census value), `test_module_length_agreement.py` (~121). Confirm
     `test_refresh_dead_symbol_hashes.py` is absent and both `test_dead_symbol_allowlist_*.py`
     files are keyed (formula-only seeds). Record the totals and the D-37 known-drift list in
     the Activity Log.
- **Files**: `.github/ci-shard-timings.json`.
- **Parallel?**: After T027.
- **Notes**: The census logs come from the merge-base tree of each PR in the window; per-file
  weights are robust to that (a file's cost changes slowly). This is a seed, labelled as such.

### Subtask T029 – Finalise roster budgets; record predicted S1/S2 loads

- **Purpose**: Budgets derived by one rule from the committed data; the leg prediction visible
  next to `shard_count`.
- **Steps**:
  1. Rule (research R1 §4b): `budget_seconds = max(10, ceil(1.5 × seed))`, which must stay
     `<= max_file_budget_seconds` (90). Apply it to every roster entry in
     `.github/ci-module-registry.yml` `special_tiers.architectural.fast_gate.roster`. If a roster
     file's rule budget exceeds 90, it does not qualify for the fast gate: move it out of the
     roster (it lands in a shard automatically) and say so in the Activity Log.
  2. **Add roster row 33 — the partition proof** (WP05 T020 deliberately left it out because the
     file did not exist yet; WP06, a dependency of this WP, created it and does not edit the
     registry). Append to `fast_gate.roster`:
     `{path: tests/architectural/test_battery_partition_proof.py, budget_seconds: 10, reason: "static three-way partition proof (FR-004); no collection, must gate every battery change"}`
     (research R1 §4b row 33: est ~2 s, budget 10; it is a new file, so it has no census time —
     its seed is the 0.12 s × test-count term from T028 and the budget is the rule's floor of 10).
     Confirm the WP05 pin `test_fast_roster_is_inside_the_base` stays green (the file now exists
     in the base) and that `--battery-part fast` collect-only includes it.
  3. Confirm Σ seed over the roster ≤ 300 (expected ≈ 266: ≈ 258 for rows 1-32, ≈ 5.6 for row 34
     `test_dead_symbol_allowlist_loader.py` — a post-census file, so its seed is the 0.12 s ×
     test-count term and its budget the rule's floor of 10 — and ≈ 2 for row 33). If not, drop the lowest-priority
     CI-config rows (25-32 of the R1 table) first — never the census-red rows — and record why.
  4. Compute and record the predicted legs:
     ```bash
     # WP02 shipped the CLI without --registry (YAML stays out of the stdlib module):
     # pass the base paths/deselects and the roster from the registry explicitly, e.g.
     uv run --frozen python -m scripts.ci.shard_select battery-parts \
       --path tests/architectural \
       --deselect tests/architectural/test_no_legacy_terminology.py \
       --deselect tests/architectural/test_layer_rules.py \
       --deselect tests/architectural/test_pyproject_shape.py \
       --deselect tests/architectural/test_archive_root_byte_identical.py \
       --roster <file listing the fast-roster paths, one per line> \
       --timings <JSON file: path -> seconds, extracted from ci-shard-timings.json battery key> \
       --shards 2 --root .
     ```
     (or call `scripts.ci.shard_select.battery_parts(...)` directly from a short Python snippet
     that reads the registry + timings — the same function WP05's plugin uses). Expect two legs of
     ≈ 1,130-1,175 worker-s each (post-#5503 key set) and a fast part ≈ 266 worker-s.
  5. Add a comment under `shards:` in the registry: the seed provenance in one line, the predicted
     loads (fast / 1/2 / 2/2 worker-s), the expected wall time (≈ load ÷ ~2.9 effective cores
     + ~40 s overhead → legs ≈ 7-10 min, fast ≈ 2 min; NFR-001 ≤ 14 min, NFR-002 ≤ 5 min), and
     that the verdict comes from ≥ 3 recorded CI runs (C-011), not from this prediction.
  6. Run T027's tests: all green. Run `tests/architectural/test_module_shard_registry.py`: green
     (the roster ⊆ base and schema pins from WP05).
  7. Partition smoke (collect-only; C-009-safe): the three `--battery-part` collect-only counts
     from WP05's Test Strategy must sum to the base count, and the plugin's printed predicted
     loads must match step 3. No FR-005 timing warning should appear (every base file is keyed);
     a later "missing" entry means a battery file was added after the seed — expected until the
     junit refresh.
- **Files**: `.github/ci-module-registry.yml`.
- **Parallel?**: After T028.
- **Notes**: Budgets are re-derived the same way when the first nightly backstop / dispatch junit
  is captured (WP05's `--from-junit` mode); that refresh is out of this WP.

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_battery_roster_budgets.py -q -s
uv run --frozen pytest tests/ci/test_shard_select.py tests/ci/test_capture_shard_timings.py \
  tests/ci/test_battery_partition_plugin.py tests/ci/test_ci_module_wiring.py -q
uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q
make test-fast
uv run --frozen ruff check tests/ci/test_battery_roster_budgets.py
uv run --frozen ruff format --check .
uv run --frozen mypy --strict tests/ci/test_battery_roster_budgets.py
python3 -c "import json,yaml; json.load(open('.github/ci-shard-timings.json')); yaml.safe_load(open('.github/ci-module-registry.yml'))"
```

- Never run `pytest tests/architectural` (only the collect-only commands above).
- `test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent` reads only
  `module_test_durations`; it must be unaffected by the new keys.
- The pinning inventory is green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37); the new test must not mention its subjects
  (`make test-fast`, `ci-quality.yml`, `sonarcloud`) so `--check` stays green.

## Risks & Mitigations

- **Contended `-n 2` census numbers** overstate per-file cost vs a 4-worker run. Budgets and the
  Σ cap are in the same units as the seed, and the junit refresh replaces them (D-29).
- **Hidden sub-second time** is approximated (0.12 s × tests). Documented in provenance;
  replaced by junit `time`, which includes every phase.
- **Logs expire** (~2026-12-29) — the derived table lives in the repo with job ids; the logs are
  only needed to re-derive, not to use.
- **Stale keys after file deletions** — #5503's deletion is already absorbed (the seed key set
  is the tip's enumeration). Later deletions are tolerated with a ≤ 10 % ratchet and loud runtime
  reporting; refresh via junit.
- **Post-census cost drift (D-37)** — `test_dead_symbol_allowlist_contract.py` (≈ 30 s local, seeded
  ≈ 0.5 s) and the rewritten `test_no_dead_symbols.py`: recorded as `known_drift`, ≤ ~5 % of one
  leg; the first junit refresh replaces them. WP13's file-end finalizer on `_real_tree_inputs`
  means M11 never reuses the gate file's walk, even on a shared worker (~30 s on that worker).
  The `known_drift` string names this too.

## Review Guidance

- **Red on planning base, green on WP tip**: `tests/ci/test_battery_roster_budgets.py` red at the
  T027 commit (no battery key), green at the tip; the mutation controls are green at both.
- Re-run the derivation from the PR body's script against the logs (or a sample of 5 job logs)
  and spot-check 5 values in the committed key, including one roster file and one ≥ 100 s file.
- Provenance names all 68 job ids, the window, the formula, `workers: 2`, the base marker and
  `superseded_by`.
- `git diff` of the timings file: only `battery_file_durations` and `battery_capture_provenance`.
- Roster row 33 (`test_battery_partition_proof.py`, budget 10, reason) is present; WP06 did not
  touch the registry.
- Every roster budget equals `max(10, ceil(1.5 × seed))`; Σ seed ≤ 300; predicted legs and
  expected wall times recorded in the registry comment and Activity Log.
- FR-004 (balanced partition from data), NFR-001/NFR-002 inputs recorded (verdicts come later
  from CI runs, C-011).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
