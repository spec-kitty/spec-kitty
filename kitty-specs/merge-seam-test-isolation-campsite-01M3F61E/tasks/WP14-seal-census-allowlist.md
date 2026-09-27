---
work_package_id: WP14
title: Seal the manual global-state census allowlist (#5118)
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
- WP12
- WP13
requirement_refs:
- C-004
- FR-008
- NFR-003
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: 3831ad835c933a0d084220d56dc479aacc399bcb
created_at: '2026-09-27T04:56:51.679741+00:00'
subtasks:
- T066
- T067
- T068
phase: Phase 4 - Seal
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_global_state_allowlist_sealed.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_global_state_allowlist_sealed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Seal the manual global-state census allowlist (#5118)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` — read `packs/built-in/agent_profiles/python-pedro.agent.yaml` and adopt its identity, boundaries and TDD discipline.
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` Standing Order 5 (non-vacuous gates, frozen-baseline shrink-only ratchet).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status --mission merge-seam-test-isolation-campsite-01M3F61E` or the Activity Log below).
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

Issue **#5118**. WP01 landed the census gate with a transitional class so the sweep could proceed in eight parallel lanes (WP06–WP13). Every sweep WP has now drained its own shard's `transitional-sweep` rows. This WP **freezes the end state** so the transitional escape hatch can never be reused and the justified remainder can only shrink.

Done means:

1. New `tests/architectural/test_global_state_allowlist_sealed.py` asserts, over the real `tests/architectural/global_state_allowlist/*.yaml`:
   - **No `transitional-sweep` row** remains in any shard.
   - **Per-class caps** frozen at the *actual* post-sweep site counts, and each cap is never above the plan projection: `process-bootstrap` ≤ 6, `subprocess-entry` ≤ 13, `leak-sentinel` ≤ 2, `deferred-01M3EW3Z` ≤ 16.
   - **Total allowlisted sites** ≤ 95 (NFR-003: ≤ 20% of the 471-site pre-sweep census).
2. Self-mutation tests prove each seal assertion fails on a planted violation (T067).
3. The Activity Log records the final census: **471 → N** allowlisted sites (expected N ≈ 37), with the per-class breakdown.
4. Full `tests/architectural/` and `make test-fast` green; ruff check/format + mypy clean.

Requirements covered: NFR-003, FR-008 (and NFR-006, C-009); SC-003.

## Context & Constraints

- `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` — FR-008, NFR-003, SC-003, C-002, C-007.
- `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/contracts/global-state-allowlist.md` — verdict 7 "Sealed invariants".
- `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research.md` — R7 (projected 37 justified sites; per-class projection), R8 (amended: shards permanent; Seal adds a *separate* test so no two WPs own the gate).
- `tests/architectural/test_no_manual_global_state_mutation.py` (WP01, not owned here) — reuse its allowlist loader if it is exposed as a helper; otherwise load the YAML shards directly in your test. **Do not edit the WP01 gate file, the detector, or any shard YAML** — this WP owns only the new sealed test.
- **Ownership**: if a shard still carries a `transitional-sweep` row when you start, that is a sweep-WP defect — stop and report it rather than draining it yourself.
- **C-007 deferral**: central baselines-registry registration (`tests/architectural/_baselines.yaml` / `test_ratchet_baselines.py`) is **deferred** until mission `01M3EW3Z` merges (C-002 forbids touching those files). The caps live only in this test for now; note the follow-up in the Activity Log.
- Do not touch any ratchet-owned file (C-002 list in the spec).

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`

The execution worktree is allocated per computed lane from `lanes.json` (**but** a multi-dependency lane is cut at the mission base, not at a merge of its dependencies — stack it first, see T066 step 0). Start with:

```bash
.venv/bin/spec-kitty agent action implement WP14 --agent claude
```

Use `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest` (never a bare `uv run`).

## Subtasks & Detailed Guidance

### Subtask T066 – Sealed-invariant test

- **Purpose**: Make the post-sweep state permanent and shrink-only (NFR-003, FR-008).
- **Steps**:
  0. **Stack the lane**: rebase onto the WP01 lane tip, then cherry-pick each dependency lane's commits in order WP02, WP03, WP04, WP05, WP06 … WP13 (files are disjoint, so this is clean; record the stacked SHAs). Verify green **before sealing**: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_layer_rules.py tests/merge/test_merge_driver_goldens.py tests/architectural/test_home_owner_behaviour.py -q`. The final census must count WP02–WP05's new test files too.
  1. Measure first. Run the gate and collect the real per-class counts:
     ```bash
     .venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q
     .venv/bin/python - <<'EOF'
     import collections, pathlib, yaml
     c = collections.Counter()
     for p in sorted(pathlib.Path("tests/architectural/global_state_allowlist").glob("*.yaml")):
         for r in (yaml.safe_load(p.read_text()) or {}).get("rows", []):
             c[r["class"]] += r["count"]
     print(dict(c), sum(c.values()))
     EOF
     ```
  2. Create `tests/architectural/test_global_state_allowlist_sealed.py` with module constants:
     ```python
     # Frozen at the post-sweep counts (WP14). Shrink-only: lower a cap when a site is
     # converted; never raise it. Plan ceilings: 6 / 13 / 2 / 16 (research R7).
     SEALED_CLASS_CAPS: Final[Mapping[str, int]] = {
         "process-bootstrap": <actual>,
         "subprocess-entry": <actual>,
         "leak-sentinel": <actual>,
         "deferred-01M3EW3Z": <actual>,
     }
     PLAN_CEILINGS: Final[Mapping[str, int]] = {"process-bootstrap": 6, "subprocess-entry": 13, "leak-sentinel": 2, "deferred-01M3EW3Z": 16}
     TOTAL_SITE_CAP: Final = 95   # NFR-003: <= 20% of the 471-site pre-sweep census
     ```
  3. Tests (each a pure function over loaded rows, so T067 can reuse them):
     - `test_no_transitional_rows` — any `class == "transitional-sweep"` fails, naming shard/file/qualname/kind.
     - `test_only_known_classes` — the class set ⊆ `SEALED_CLASS_CAPS` keys.
     - `test_class_caps_hold` — per-class sums ≤ cap; message: "class X has N sites > sealed cap M — convert the site, never raise the cap".
     - `test_caps_never_exceed_plan_ceiling` — `SEALED_CLASS_CAPS[c] <= PLAN_CEILINGS[c]` (guards against someone raising a cap).
     - `test_caps_are_tight` — per-class sums == cap (a converted site must lower the cap in the same change — this is the shrink-only ratchet). If you judge exact equality too strict for the repo's conventions, check sibling ratchets; the charter's `frozen-baseline-shrink-only-ratchet` favours exact.
     - `test_total_under_nfr_cap` — total ≤ 95.
     - `test_every_justified_row_has_reason` — non-empty `reason` for every row (defence in depth; WP01's gate also checks it).
  4. If a cap would exceed its plan ceiling, **stop**: that means a sweep WP allowlisted instead of converting. Report it in the Activity Log and hand back rather than raising the ceiling.
- **Files**: `tests/architectural/test_global_state_allowlist_sealed.py` (new, ~150 lines).
- **Notes**: Keep YAML I/O in this test file; do not import `tests/architectural/_home_pin_scan.py`. Avoid "census"/"baseline" path literals in YAML paths (the directory is `global_state_allowlist/`).

### Subtask T067 – Seal self-mutation tests

- **Purpose**: NFR-004 non-vacuity — prove each seal assertion bites.
- **Steps**:
  1. Copy the real shard YAMLs to `tmp_path` (or build rows in memory) and plant, one test each:
     - a `transitional-sweep` row → `no_transitional_rows` fails;
     - an unknown class → `only_known_classes` fails;
     - an extra `subprocess-entry` site (count + 1) → `class_caps_hold` fails;
     - a row removed (converted) without lowering the cap → `caps_are_tight` fails;
     - a cap raised above its plan ceiling (patched constant) → `caps_never_exceed_plan_ceiling` fails;
     - rows summing to 96 → `total_under_nfr_cap` fails.
  2. Assert on the *verdict function's* return value, not on pytest failure — i.e. factor each check as `def violations(rows, caps) -> list[str]` and assert the list is non-empty for plants and empty for the real tree.
  3. Negative control: the real, unmodified shards yield zero violations.
- **Files**: same test file.
- **Parallel?**: No (builds on T066's helper functions).

### Subtask T068 – Final census report and full runs

- **Purpose**: Close #5118's numbers honestly and prove nothing regressed.
- **Steps**:
  1. Record in the Activity Log: pre-sweep 471 sites / 155 files → post-sweep N allowlisted sites, with per-class breakdown and the number of files still carrying any row. Also record the reduction percentage (SC-003 target ≥ 80%).
  2. Run:
     ```bash
     .venv/bin/python -m pytest tests/architectural/ -q -p no:randomly
     make test-fast
     uv run --frozen ruff check tests/architectural/test_global_state_allowlist_sealed.py
     uv run --frozen ruff format --check tests/architectural/
     .venv/bin/python -m mypy tests/architectural/test_global_state_allowlist_sealed.py
     ```
  3. Classify any red per the CLAUDE.md baseline-red gotcha (compare against `upstream/main` before calling it pre-existing). Record commands and counts.
  4. Note the C-007 follow-up in the Activity Log: "Register `SEALED_CLASS_CAPS` in the central baselines registry once mission 01M3EW3Z merges."

- **Tracer**: **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`); do not commit them from the lane — the orchestrator commits them in the lifecycle trail.

## Test Strategy

- The sealed test runs over the real allowlist (green) and over planted variants (each fails its assertion).
- No product code changes; no changes to WP01's files.

## Risks & Mitigations

- **A sweep WP left transitional rows** → the seal test fails on day one; report the offending shard to the orchestrator rather than editing it.
- **Caps set above actual** (loose ratchet) → `test_caps_are_tight` prevents it.
- **Registry drift** once 01M3EW3Z merges → explicit follow-up note (C-007).

## Review Guidance

- Re-run the count script from T066 and compare with `SEALED_CLASS_CAPS`.
- Check every cap ≤ its plan ceiling and the total ≤ 95.
- Check each seal assertion has a planted-violation test.
- Confirm no edits outside `tests/architectural/test_global_state_allowlist_sealed.py` (`git diff --stat`).
- Confirm mypy + ruff (check and format) are clean and no suppressions were added.
- **Tracer append** evidence: dated 1–3 sentence entries in the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` for anything non-obvious (the orchestrator commits them in the lifecycle trail).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-26T16:40:00Z – system – Prompt created.
- 2026-09-27T05:15:00Z – claude-sonnet-5 – Verified lane already stacks WP01–WP13 (12 dependency-lane merge commits present); zero `transitional-sweep` rows in any shard; pre-seal baseline (test_no_manual_global_state_mutation, test_layer_rules, test_merge_driver_goldens, test_home_owner_behaviour) green: 191 passed.
- 2026-09-27T05:30:00Z – claude-sonnet-5 – Measured post-sweep census: process-bootstrap 6, subprocess-entry 12, leak-sentinel 2, deferred-01M3EW3Z 16 — total 36 sites across 13 files (471 pre-sweep → 36, 92.4% reduction; SC-003 target ≥80%). All four counts are at or under their plan ceilings (6/13/2/16), so no cap needed raising and no offending shard to report.
- 2026-09-27T06:45:00Z – claude-sonnet-5 – Created `tests/architectural/test_global_state_allowlist_sealed.py` (T066): froze `SEALED_CLASS_CAPS` at the measured counts, `PLAN_CEILINGS` at 6/13/2/16, `TOTAL_SITE_CAP=95`. Reused WP01's `load_allowlist`/`AllowlistRow`/`Allowlist` from `test_no_manual_global_state_mutation.py` — no second YAML parser. 7 seal-invariant tests over the real allowlist, all green.
- 2026-09-27T06:50:00Z – claude-sonnet-5 – Added T067 self-mutation tests (8): negative control over the real allowlist plus one planted-violation test per verdict function (transitional row, unknown class, over-cap, converted-site-without-lowering-cap, ceiling-raised-above-plan, total-over-95, missing-reason). All assert on the pure verdict functions' returned violation lists, not on pytest failure. 15/15 tests green; ruff check + format clean; mypy clean.
- 2026-09-27T07:05:00Z – claude-sonnet-5 – T068: full `tests/architectural/` (-n4 --dist loadfile): 2948 passed, 3 failed, 4 skipped, 2 xfailed. Failures classified: `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` (known, operator-ruled closeout item); `test_module_length_agreement.py::test_non_allowlisted_modules_agree_with_live_collection` and `::test_charter_is_not_allowlisted_and_agrees` (pre-existing `charter` module committed/collected drift, 6161 vs 6162 — reproduced identically with the new test file removed, confirming it is unrelated base red, not caused by this WP). Fast-tier equivalent (`tests/unit tests/status tests/cli tests/specify_cli/runtime -m "fast or unit"`, -n4): 2309 passed, 3 failed (all `test_charter_json_error_contract.py`, the known "charter linked-worktree refusal" base red — this lane is a linked worktree). ruff check/format and mypy clean on the owned file and on `tests/architectural/` as a whole. C-007 follow-up noted in the module docstring: register `SEALED_CLASS_CAPS` in the central baselines registry once mission `01M3EW3Z` merges. Committed as `6c9521f321`.

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP14 --to <status> --mission merge-seam-test-isolation-campsite-01M3F61E` to change WP status.
