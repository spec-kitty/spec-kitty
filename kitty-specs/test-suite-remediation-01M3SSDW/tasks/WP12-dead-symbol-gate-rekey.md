---
work_package_id: WP12
title: Dead-symbol gate re-key and bite battery
dependencies:
- WP11
requirement_refs:
- FR-008
- FR-009
- FR-011
- NFR-003
- NFR-005
- C-001
- C-003
- C-007
- SC-003
- C-002
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 76e906840754612b1da9aa783f313a5aaf7b1a3c
created_at: '2026-09-30T22:11:00.102102+00:00'
subtasks:
- T054
- T055
- T056
- T057
- T058
- T059
- T060
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-30T20:30:00Z'
  actor: planner-priti
  action: 'Post-tasks squad fold. Sanctioned out-of-map edits (not in owned_files, to avoid overlap): tests/architectural/test_dead_symbol_allowlist_contract.py (remove strict-xfail markers only) and tests/architectural/dead_symbol_allowlist.yaml (regenerate only on base drift).'
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_no_dead_symbols.py
create_intent: []
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- tests/architectural/test_no_dead_symbols.py
- tests/architectural/test_p1_planted_regression.py
- tests/architectural/_refresh_dead_symbol_hashes.py
- tests/architectural/test_refresh_dead_symbol_hashes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Dead-symbol gate re-key and bite battery

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- **FR-009 / SC-003 / NFR-003**: `tests/architectural/test_no_dead_symbols.py` exempts `__all__` symbols by **`(module, name)`**, loaded from `dead_symbol_allowlist.yaml` through WP11's loader.
  - A body edit to an allowlisted symbol needs **0** edits.
  - A newly dead symbol reds and is named.
  - A deleted, renamed, moved, revived, superseded or moot entry is reported stale, with exactly one verdict (G3).
- **WP10's contract tests go GREEN**: M1, M7, M8 and M11. The seam API they call is binding (see Context).
- **The persisted-hash surface is deleted** (G6):
  - the T016 one-signal suppression;
  - `_compute_dangling`;
  - the `source_module` provenance guards (`:2408`, `:2425`);
  - the cross-category duplicate guards (`:2506`, `:2537`, replaced by L8/M12 in WP11);
  - all 42 `_CATEGORY_*` literals, `_category_frozensets` and `owning_category`.
- **The refresh helper and its 17 tests are retired**, because they import `_compute_dangling`, `_compute_offenders` and `_compute_stale` from the gate and would break with it. The C-002 covering guard: a planted new dead symbol reds the real-tree gate (the M2 path) and names it. `test_p1_planted_regression` stays green on its own synthetic plant, which proves the `_compute_offenders` path is live.
- **Parity**: `after.json` equals WP10's `before.json` on `allowlist`, `widened_470`, `offenders` and `stale` (293 / 91 on today's base).
- **One authority, one evaluation seam (F-05)**: both YAML sections (`entries` and `widened_grandfathered_470`) are evaluated from the **same** parsed `DeadSymbolAllowlist` instance. The widened #470 path takes its grandfather set as a parameter instead of reading an import-time global. A new M11(c) bite proves that the gate reads the widened section it claims to read.
- **C-003**: nothing is loosened. The #470 widened semantics are **unchanged** (G4). Auto-exempt condition (1), `final_key.module_path is None`, is **kept** (G5).
- **C-007 canon**: the file keeps its **name**, its `architectural` marker and its real asserts inside `test_*` functions. It is pinned in three places: `test_shape_guard_membership.py:54-55`, `shape_guard_membership.yaml:37`, and `_p1_census_oracle.py:62-66` with `test_p1_planted_regression.py` `_ENFORCEMENT_GATE_NAMES`.

## Context & Constraints

- Read first: `contracts/dead-symbol-allowlist.md` (all of it); `data-model.md` §1.4–§1.7; `research/dead-symbol-rekey.md` §1, §3, §5, §6 and §8; `plan.md` IC-10 and IC-11; WP10's contract file; WP11's loader.
- **Binding seam API** (from WP10; implement exactly):
  - `_real_tree_inputs() -> RealTreeInputs`:
    - `@functools.lru_cache(maxsize=1)`;
    - a frozen dataclass with `decls`, `all_literal_decls`, `corpus`, `per_symbol`, `star_targets` and `collision_index`;
    - built from `_walk_modules()`, `_imports_by_target(...)` and `classify_collisions(corpus)`.
  - `_evaluate_allowlist(all_literal_decls, per_symbol, star_targets, corpus, allowlist: DeadSymbolAllowlist, collision_index=None) -> AllowlistEvaluation`:
    - `.offenders`: a sorted `list[str]` over the **`__all__` scope only**;
    - `.stale`: a `list[StaleFinding]`, ordered deterministically by `(module, name)`.
  - `StaleFinding(key: DeadSymbolKey, verdict: StaleVerdict, hint: str)`, with `render()` giving `f"{key} [{verdict}] {hint}".rstrip()`.
- **Keep these signatures** (pinned elsewhere):
  - `_find_facade_lazy_dict_name` and `_resolve_relative_module` are imported lazily by `_symbol_key.py:397` (LOW-5 pin).
  - `_record_facade_edges` is byte-frozen (C-005 of an earlier mission).
  - The caller detectors are unchanged (contract §0 non-goal).
  - `_compute_offenders(decls, per_symbol, star_targets, allowlist, corpus, collision_index)` keeps its **positional shape**; only the allowlist element type changes to `DeadSymbolKey`. `test_p1_planted_regression.py` calls it positionally.
- **Do not change**: the `_SYMBOL_ALLOWLIST` / `_WIDENED_SCOPE_GRANDFATHERED_470` attribute **names** (G8; they become aliases of the loader constants). The widened #470 tests (`:3932-4134`), the dynamic-accessor tests (`:4169-4389`) and the **behaviour** of `_compute_widened_stale` / `_apply_widened_scope_exemptions` stay as they are (G4). The only permitted change to those two helpers is F-05's parameter threading (T055 step 6).
- `test_no_dead_symbols.py`, `test_p1_planted_regression.py` and the two refresh files are **not** format-excluded.
- `tests/unit/test_symbol_key.py` and `_symbol_key.py` belong to **WP13**. Do not touch `SymbolKey.source_module` here; the field simply becomes unused by the gate.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`. This WP depends on WP11, and transitively on WP10. Start with:

```bash
spec-kitty agent action implement WP12 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** `test_no_dead_symbols.py` takes about 4 minutes; it is a named gate file. Batch your runs so you do not re-walk needlessly. Never run `tests/architectural/` as a directory, never `make test-full`, and no heavy suites. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** The SC-003 and M2 plants are scratch edits in `src/`; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Evidence.** Write data-model §4 YAML records, plus the before/after parity digests, into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
4. **Quality (NFR-005).** Run `uv run --frozen ruff check` and `ruff format --check` on the owned files. **Complexity ≤ 15 per function**: the verdict classifier and the real-tree test must be split into helpers (message building, verdict classification, widened pass). Hoist repeated message literals (S1192). Add no new `noqa` or `type: ignore`.
   - **C-007 canon (F-11)**: extract message **building** only. `test_no_public_symbol_in_all_is_unimported` must keep its `assert not messages, …` and the corpus-floor asserts literally in its own body. The canon check passes on any `ast.Assert` in any `test_*`, so an extraction could otherwise leave the real gate asserting nothing directly.
   - Do not write the literal token `source_module` into the rewritten gate (say "the retired provenance field"). WP13's grep gate looks for field usage (m2 / F-01).
5. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-opus-5-5`.
6. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits. Suggested commits: (1) re-key the gate plus the battery (T055–T057); (2) migrate p1 (T058); (3) retire the refresh helper (T059). Every commit must leave the named files green.

### Additional mission-wide rules (analysis folds)

- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1).** If an unmasked or converted test exposes a **new** product defect, never re-mask it.
  - If the fix fits this WP: make it red-first, as a failing test commit followed by a **separate** `fix(...)` commit touching only the product file(s). It is a sanctioned out-of-map `src/` edit: record a one-line rationale in your WP notes, file an issue (`gh issue create`) and add its issue-matrix row (`spec-kitty agent issue-verdict ... --verdict fixed`). The "`git diff --stat src/` must be empty" rule is lifted for exactly that commit.
  - Otherwise: mark the test `xfail(strict=True, reason="<newly filed open issue>")` and tell the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. This WP's new or rewritten typed modules also run `uv run --frozen mypy tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py` (the new dataclasses and `Mapping` views). Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T054 – Re-take `before.json` before any edit

- **Purpose**: Parity must be measured against the tree this WP starts from (contract §4; research §9 risk "parity drift").
- **Steps**:
  1. Before touching any file, recreate WP10's `parity_before.py` in your scratchpad **verbatim**, from WP10's evidence (the hand-off note or the orchestrator's relay), and run it: `PYTHONPATH=. uv run --frozen python <scratch>/parity_before.py > <scratch>/before.json`.
  2. Compute the parity digest (see WP10 T049) and compare it with WP10's recorded digest.
     - Equal: record "base unchanged since WP10".
     - Different (the base moved): record both digests and both counts, and use **your** `before.json` for parity. Note the delta, e.g. "base gained one allowlist entry in commit X".
  3. Also confirm that WP11's YAML still matches the old constants (WP11 T053's scratch parity check). If it does not, the base moved after WP11: regenerate the YAML with WP11's recorded converter **before** proceeding, and record both digests.
     - This is a **sanctioned out-of-map edit** of WP11-owned `tests/architectural/dead_symbol_allowlist.yaml` (F-02a). The rationale: WP12 depends on WP11, so there is no parallel collision. Record it as a one-line out-of-map note in your hand-off.
     - Only regenerate, and only for base drift. Never hand-edit entries to make parity pass.
- **Edge cases**: If the script is not available, reconstruct it from WP10's prompt (T049 has the core logic), and flag that in the evidence.

### Subtask T055 – Wire the gate to the loader (G1, G5, G7, G8) and add the seam

- **Purpose**: Replace hash-keyed membership with `(module, name)` membership, keep keyability fail-closed, and expose the seam WP10 tests.
- **Files**: `tests/architectural/test_no_dead_symbols.py`.
- **Steps**:
  1. Imports: `from tests.architectural._dead_symbol_allowlist import ALLOWLIST, DeadSymbolAllowlist, DeadSymbolKey, StaleVerdict, SYMBOL_ALLOWLIST, WIDENED_SCOPE_GRANDFATHERED_470, load_allowlist`. `ALLOWLIST` is the loader's single parsed instance (WP11 exports it); `SYMBOL_ALLOWLIST` and `WIDENED_…` are views of it.
  2. **G8**: `_SYMBOL_ALLOWLIST: frozenset[DeadSymbolKey] = SYMBOL_ALLOWLIST` and `_WIDENED_SCOPE_GRANDFATHERED_470: frozenset[str] = WIDENED_SCOPE_GRANDFATHERED_470`, replacing the literal definitions.
  3. **G1**, in `_compute_offenders`: the exemption holds **iff** `DeadSymbolKey(mod_dotted, name) in allowlist` **and** `final_key is not None`, where `final_key` is the existing `_resolve_final_key(...)` result. That is the keyability precondition; `__all__ = ['Ghost']` stays an offender. The allowlist element type becomes `DeadSymbolKey`. Keep the positional signature.
  4. **G5**: keep the `_is_auto_exempt(mod_dotted, name, module, final_key, per_symbol, submodule_index)` call and condition (1) exactly as they are.
  5. **Seam**: add `RealTreeInputs`, the cached `_real_tree_inputs()`, `StaleFinding`, `AllowlistEvaluation` and `_evaluate_allowlist(...)`. It computes `collision_index` from `corpus` when it is `None`, runs `_compute_offenders` over `all_literal_decls` with `allowlist.keys`, and runs the stale classifier (T056).
  6. **Real-tree test**: `test_no_public_symbol_in_all_is_unimported` (`:3799`) uses `_real_tree_inputs()`, and **one** allowlist instance (`allowlist = ALLOWLIST`, or one `load_allowlist()` call) for **both** sections.
     - **F-05, widened threading** (behaviour unchanged, G4):
       - `_apply_widened_scope_exemptions` gains a `grandfathered: frozenset[str]` parameter instead of reading `_WIDENED_SCOPE_GRANDFATHERED_470` at `:3767`;
       - `_compute_widened_stale` already takes it; keep that.
     - Add `_evaluate_widened(decls, all_literal_decls, per_symbol, star_targets, corpus, collision_index, grandfathered) -> tuple[list[str], list[str]]`. It returns `(post_rescue_offenders, widened_stale)` and wraps the existing widened-only pass **exactly**: `widened_only_decls`, the `frozenset()` allowlist for it, the pre-rescue "known entry is an offender" assertion, `_compute_widened_stale` and the rescue.
     - The real-tree test calls `_evaluate_allowlist(..., allowlist)` and `_evaluate_widened(..., allowlist.widened_qualified)`, then merges them. This addition to WP10's seam is **additive**; do not change the binding names.
     - Render `stale` through `StaleFinding.render()`.
     - Update the fix-options text: option 4 becomes "add a `(module, name)` entry to `tests/architectural/dead_symbol_allowlist.yaml` with category and rationale (and issue where the category requires it)".
  7. Point the other real-tree walkers (`test_auto_exempt_disjoint_from_hand_allowlist` at `:4438`, `bite_k`, …) at `_real_tree_inputs()`, so the file walks the tree **once** per session (G7).
- **Edge cases**:
  - `_resolve_final_key`'s tiering still computes collision tiers. That is fine: it is used only for keyability and auto-exempt condition (1).
  - **Read-only views are mandatory (F-06)**: `RealTreeInputs` exposes `types.MappingProxyType` views, and `frozenset` values for `per_symbol` and `star_targets`. Readers are typed as `Mapping`. A test that mutated the cached inputs (e.g. added a caller to `per_symbol`) would silently rescue dead symbols for every later real-tree test on that worker.

### Subtask T056 – Stale verdicts (G3), deletions (G6) and the corpus floor

- **Purpose**: One verdict per entry, in the order INVALID → GONE → REVIVED → SUPERSEDED → MOOT (data-model §1.5), and removal of the machinery that only existed for persisted hashes.
- **Steps**:
  1. Implement the classifier, e.g. `_classify_entry(key, *, all_literal_decls, corpus, collision_index, per_symbol, submodule_index, star_targets) -> StaleVerdict | None`. The first matching rule wins:
     1. **INVALID**: `name ∈ all_literal_decls.get(module, ∅)` and `_resolve_final_key(...) is None`.
     2. **GONE**: `name ∉ all_literal_decls.get(module, ∅)`.
     3. **REVIVED**: `_symbol_has_caller(name, module, per_symbol, submodule_index)`.
     4. **SUPERSEDED**: `_is_auto_exempt(module, name, corpus.get(module), final_key, per_symbol, submodule_index)`.
     5. **MOOT**: `module ∈ star_targets`.
     6. otherwise `None`, i.e. live.
  2. **The GONE hint**: if some offender `X::name` exists with `X != module`, the hint is ``probably moved to `X`; update `module:` ``. Otherwise the hint is "deleted, renamed, or dropped from `__all__`".
  3. **Delete** (G6):
     - `_compute_dangling` (`:3555`) and its T016 suppression;
     - the old `_compute_stale` (`:3517`), now replaced by the classifier;
     - `_content_tier_symbolkey_calls`, `_bare_name_of`, `_source_module_of`, `test_every_content_tier_entry_has_source_module` (`:2408`) and `test_every_content_tier_source_module_is_live_and_declares_symbol` (`:2425`);
     - `_category_frozensets` (`:2468`), `owning_category` (`:2489`), `test_no_dead_symbol_key_is_listed_in_more_than_one_category` (`:2506`) and `test_symbol_allowlist_aggregates_every_discovered_category` (`:2537`);
     - all `_CATEGORY_*` frozensets (`:153-~2290`) and the old `_SYMBOL_ALLOWLIST` union (`:2296`).

     Before deleting, run `git grep -n "<name>" -- tests scripts` for every name. The only external users should be the refresh files (T059) and `test_p1_planted_regression.py` (T058).
  4. **Corpus floor (contract §2.1)**, asserted inside the real-tree test:
     ```python
     assert sum(len(v) for v in inputs.all_literal_decls.values()) >= 3500   # live: 3,922 names
     assert len(inputs.all_literal_decls) >= 600                               # live: 656 modules
     ```
     Use named module constants with a comment saying "non-vacuity floor on the scanned corpus, not a pin".
  5. **Module docstring**: rewrite the "Allowlist" section (`:73-97`). The identity is `(module, name)` in `dead_symbol_allowlist.yaml`, loaded by `_dead_symbol_allowlist.py`. Hashes are runtime-only (keyability plus auto-exempt condition (1)). Cite the ADR in `docs/adr/4.x/` (WP15) generically, and remove the `owning_category` and cross-category duplicate-gate guidance.
- **Edge cases**: MOOT is stricter than today. There are 0 star targets on this tree, so there is no day-one red; confirm with `inputs.star_targets` and record it.

### Subtask T057 – Rebase the bite battery (M2–M6, M9, M10, M13)

- **Purpose**: Keep the gate non-vacuous (`architectural-gate-non-vacuity`) under the new identity. Every case goes through the production `_compute_offenders` / `_evaluate_allowlist` path with synthetic corpora or scratch YAML (C-007 practice).
- **Map** (contract §3):
  - **M2**, a new dead `New` in an allowlisted module → offender `m::New`: keep `test_gate_still_flags_a_truly_dead_symbol` (`:4391`), rebased so its allowlist control uses `frozenset({DeadSymbolKey("synthetic.deadmod", "NeverImported")})` with a keyable corpus.
  - **M3**: the allowlist has `(a, Shared)`; `b::Shared` is dead with a different body → offender `b::Shared`. Rebase `bite_c` (`:4471`).
  - **M4**: allowlist `(sanctioned, GateDecision)` plus a byte-identical `rogue::GateDecision` → offender `rogue::GateDecision`, with **no** escalation logic involved. Simplify `bite_i` (`:4547`).
  - **M5**: an allowlisted symbol gains a direct caller → stale REVIVED. Rebase `bite_d` (`:4678`).
  - **M6**: an allowlisted symbol is deleted → stale GONE. Replaces `bite_g`'s dangling arms (`:4733`).
  - **M9**: `__all__ = ['Ghost']`, allowlisted → offender `m::Ghost` **and** stale INVALID. Rebase `bite_f` (`:4527`).
  - **M10**: an allowlisted name removed from `__all__` while the symbol still exists → stale GONE. **New.**
  - **M13**: a quarter of the modules → the §2.1 floor assertion reds. **New.** Drive the floor check through an extracted helper, e.g. `_assert_corpus_floor(all_literal_decls)`, and call it on a **truncated copy** of the mapping. **Rule (F-06)**: no test may monkeypatch `_walk_modules` and then call `_real_tree_inputs()`. That is order-dependent against the cache: it either reads the cached full tree (a false green) or seeds the cache with a partial tree for the real gate.
  - **M11(c)**, new (F-05): pop one widened entry from a scratch copy of the YAML (`widened_grandfathered_470.entries`), load it, and run `_evaluate_widened(...)` over `_real_tree_inputs()` with `scratch.widened_qualified`. The popped `module::name` appears as an offender. This proves the gate reads the widened section of the file it is given.
  - **Keep, rebased**:
    - `bite_e` (`:4495`);
    - `bite_k` (`:4596`), which becomes "every allowlist entry is keyable" (no INVALID on the real tree, using `_real_tree_inputs()`);
    - `test_auto_exempt_disjoint_from_hand_allowlist` (`:4438`), folded into SUPERSEDED: assert no SUPERSEDED verdict on the real tree, or keep it as a real-tree assertion over `DeadSymbolKey` membership;
    - the widened tests;
    - the dynamic-accessor tests.
  - **Retire** (they encoded the old identity; M1, M7 and M8 in WP10 replace them; the ADR records the reason):
    - `bite_b` (`:4636`);
    - `bite_g`'s body-edit arm;
    - `bite_j`'s relocation arm (`:4799`), keeping any non-relocation arm;
    - `bite_j_gate_annassign_whitespace_zero_false_red` (`:4770`): **RETIRE it**. Its subject, the whitespace sensitivity of a persisted hash key, no longer exists, and M1 covers body-edit tolerance. The one exception: if it asserts AnnAssign **keyability** (`_resolve_final_key(...) is not None`), keep only that assertion, in a small renamed test.
- **Steps**: Name the tests `test_m2_…` through `test_m13_…`, or keep the `bite_*` names with a docstring mapping them to M-ids. Either way, each docstring says which M-id it implements.

### Subtask T058 – Migrate `test_p1_planted_regression.py`

- **Purpose**: That file drives the gate's `_compute_offenders` with a `SymbolKey`-based neutralizer (`:180-213`), and asserts `isinstance(dead_symbols_gate._SYMBOL_ALLOWLIST, frozenset)` (`:252`).
- **Files**: `tests/architectural/test_p1_planted_regression.py`.
- **Steps**:
  1. Neutralizer #2 (`:203-213`): replace the `symbol_key.resolve_symbol_key`/`key_tier` key with `DeadSymbolKey(module_dotted, symbol_name)`. Keep the **real** keyable corpus: G1 requires keyability, so `NeverImportedPlanted = object()` in the corpus stays. The allowlist argument becomes `frozenset({DeadSymbolKey(...)})`.
  2. Keep the `import _symbol_key as symbol_key` only if still used (`CorpusModule`, `classify_collisions`).
  3. `:252` is unchanged: `_SYMBOL_ALLOWLIST` is still a frozenset (G8).
  4. Run the file: green.
- **Parallel?**: Yes, once T055 lands.

### Subtask T059 – Retire the refresh helper and its tests (C-002)

- **Purpose**: `_refresh_dead_symbol_hashes.py` exists only to rewrite persisted `body_hash` literals, which no longer exist. `test_refresh_dead_symbol_hashes.py` (17 tests) imports `_compute_dangling`, `_compute_offenders`, `_compute_stale` and `_submodule_index` from the gate (`:44-49`), so it cannot survive T056. Retiring both in the same WP keeps every commit green. This was planned under IC-11 and moved here because of that import coupling.
- **Files**: delete `tests/architectural/_refresh_dead_symbol_hashes.py` and `tests/architectural/test_refresh_dead_symbol_hashes.py` (`git rm`).
- **Steps**:
  1. `git grep -n "refresh_dead_symbol" -- ':!kitty-specs' ':!docs/changelog' ':!docs/reports'` → only the two files, plus doc references owned by WP15 (`docs/development/reference/ci-gate-mechanics.md`) and WP13 (`tests/architectural/README.md`, `_symbol_key.py` docstrings). List them in the evidence for those WPs.
  2. **C-002 covering-guard proof**: plant a new dead `__all__` symbol in `src/`, e.g. add `"PlantedDead5346"` to some module's `__all__` plus a `PlantedDead5346 = 1` definition (scratch).
     - `test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` must go **RED**, naming `module::PlantedDead5346` (M2 at real-tree scale).
     - `test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate` stays green on its own synthetic plant; run it to show the M2 path is live.
     - Revert.
  3. Delete both files and run the named gates.

### Out-of-map edits (orchestrator ruling; sanctioned; do NOT add these files to `owned_files`)

1. **`tests/architectural/test_dead_symbol_allowlist_contract.py`**, WP10-owned: remove the strict-xfail markers. The rationale: this WP depends on WP10, so there is no parallel collision. Adding the file to `owned_files` would overlap WP10.
2. **`tests/architectural/dead_symbol_allowlist.yaml`**, WP11-owned: regenerate it **only** on base drift (T054 step 3, F-02a).

Record both, if used, as one-line out-of-map notes in the hand-off.

For the markers:
- Once the re-key is in, remove the `xfail(strict=True, raises=(ImportError, AttributeError), reason="pending the dead-symbol re-key …")` markers from M1, M7, M8 and M11. Make **no other edit** to that file.
- The tests must then PASS. Record the flip, strict-XFAIL to PASS, in your evidence as the red→green proof.
- Any remaining XFAIL means the re-key is incomplete.

### Subtask T060 – `after.json` parity, SC-003 plant, M2 plant, evidence

- **Steps**:
  1. **`after.json`**: write `parity_after.py` in the scratchpad.
     - `allowlist` rows are `[mod, name, entry.category]` for every live `__all__` location with `DeadSymbolKey(mod, name) ∈ load_allowlist().keys` **and** a keyable `_resolve_final_key`;
     - `widened_470` rows are the split `WIDENED_SCOPE_GRANDFATHERED_470`;
     - `offenders` / `stale` come from the new pipeline (offenders after the widened rescue; rendered stale, plus widened stale);
     - use the same JSON conventions and digest as WP10.

     Assert **digest equality** with T054's `before.json`, and `counts == {"allowlist": 293, "widened_470": 91}` (or T054's re-measured counts). Record the `diff` output (it must be empty).
  2. **SC-003 (quickstart Break #19)**: apply the same **code-token** plant as WP10. In `src/specify_cli/status/lifecycle_events.py::append_lifecycle_event` (`:608-645`), rename the local `envelope` to `persisted_envelope` (all 4 occurrences, scratch). `test_no_dead_symbols.py` stays **GREEN** with 0 edits; it was RED on the base, per WP10's EV-IC09-02. Revert. Never use a docstring edit: `code_tokens_by_line` drops STRING and COMMENT tokens, so it would prove nothing.
  3. **Quickstart Break #21**: import an allowlisted symbol from another `src/` module (scratch). The gate reports `module::name [REVIVED]`. Revert.
  4. Run WP10's contract file after removing only the xfail markers: **all PASS** (M1, M7, M8, M11). With the markers still present they would XPASS, which strict mode fails.
  5. **Wall time (F-07)**: record the before and after wall time of `test_no_dead_symbols.py`. Also record that `test_dead_symbol_allowlist_contract.py` costs one extra real walk on its own xdist worker in CI.
  6. The named-file run (Test Strategy), then `make test-fast`.
  7. **Evidence records**:
     - **EV-IC10b-01**: the parity digests (before and after), counts, and an empty diff;
     - **EV-IC10b-02**: SC-003 green;
     - **EV-IC10b-03**: M2 plant red (the C-002 guard for T059);
     - **EV-IC10b-04**: REVIVED plant;
     - **EV-IC10b-05**: the contract suite flips from strict-XFAIL to PASS, with no edit other than the marker removal;
     - **EV-IC10b-06**: M11(c), the widened authority-parse red;
     - the list of retired and rebased bite tests with their M-ids.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py tests/architectural/test_shape_guard_membership.py tests/architectural/test_ratchet_positional_anchor_ban.py -n0 -q
uv run --frozen pytest tests/unit/test_symbol_key.py tests/architectural/test_timing_coverage_invariant.py -n0 -q
uv run --frozen ruff check tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py
uv run --frozen ruff format --check tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py
make test-fast
```

`tests/unit/test_symbol_key.py` is run read-only here, to prove the gate change did not break `_symbol_key` consumers. WP13 edits it.

## Risks & Mitigations

- **Silent exemption drift.** The digest parity is the proof, and it is non-negotiable.
- **Re-blinding T004 (byte-identical siblings).** M3 and M4 on the production path, plus the structural uniqueness of `(module, name)`.
- **Widening the auto-exempt set.** Condition (1) is unchanged, and SUPERSEDED reds any overlap.
- **Complexity creep** in the real-tree test. Extract message builders and pass helpers.
- **Runtime.** The cached `_real_tree_inputs()` should make the file faster (several real walks today). Record the before and after wall time.

## Definition of Done (C-011)

- **C-011 (D1 reading, `traces/design-decisions.md`)**: this WP flips WP10's contract tests from strict XFAIL to PASS (chain-level GREEN; marker removal is the only edit to that file). Its own rebased bite battery and the SC-003 / M2 / REVIVED / M11(c) plants carry the planted-break red→green proof.

## Review Guidance

- The parity digest is equal, with 293 / 91.
- WP10's contract tests PASS after the removal of **only** their xfail markers (no other edit to `test_dead_symbol_allowlist_contract.py`, a sanctioned out-of-map edit).
- Both YAML sections come from one parsed instance, `_apply_widened_scope_exemptions` takes `grandfathered` as a parameter, and M11(c) is present.
- `RealTreeInputs` is read-only (`MappingProxyType` / `frozenset`), and M13 does not monkeypatch the walker.
- `test_no_public_symbol_in_all_is_unimported` still contains its own literal `assert` statements.
- There are no `_CATEGORY_*`, no `body_hash` literals and no `source_module` in the gate: `rg -n "body_hash|source_module|_CATEGORY_" tests/architectural/test_no_dead_symbols.py` returns only runtime-hash **usage** inside `_resolve_final_key`/auto-exempt paths, if any, and no data.
- Re-run Break #20 (the new dead symbol reds and is named; `test_p1_planted_regression.py` stays green on its own synthetic plant) and Break #19 (the `envelope` → `persisted_envelope` code-token edit stays green) yourself.
- The file name, the marker and the widened semantics are unchanged.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-opus-5-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T054 T055 T056 T057 T058 T059 T060 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP12 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records incl. parity digests>"
```
