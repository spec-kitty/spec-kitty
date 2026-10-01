---
work_package_id: WP10
title: Dead-symbol ATDD contract pins and parity snapshot
dependencies: []
requirement_refs:
- FR-009
- FR-011
- NFR-003
- NFR-005
- C-001
- C-007
- SC-003
- NFR-004
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 4c851b3e43df308f679459b65bc4c66433df011a
created_at: '2026-09-30T20:52:37.071441+00:00'
subtasks:
- T045
- T046
- T047
- T048
- T049
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_dead_symbol_allowlist_contract.py
create_intent:
- tests/architectural/test_dead_symbol_allowlist_contract.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- tests/architectural/test_dead_symbol_allowlist_contract.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Dead-symbol ATDD contract pins and parity snapshot

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

- **ATDD-first (charter C-011, Standing Order 4)**: The acceptance contract of the FR-009 re-key is committed **before** the re-key.
  - A new file `tests/architectural/test_dead_symbol_allowlist_contract.py` holds **M1, M7, M8 and M11** from `contracts/dead-symbol-allowlist.md` §3.
  - The file **collects cleanly today**. **Every test is committed as a strict XFAIL** (rule 7), with `raises=(ImportError, AttributeError)`. Under `--runxfail`, each one is RED on the missing seam (`ModuleNotFoundError` until WP11, then `AttributeError: _evaluate_allowlist` until WP12). A module-scope import that errors at collection is **not** an acceptable red.
- **SC-003 real-tree red observation**: plant a behaviour-neutral **code-token** body edit to an allowlisted symbol. In `src/specify_cli/status/lifecycle_events.py::append_lifecycle_event` (`:608-645`), rename the local `envelope` to `persisted_envelope` (all 4 occurrences). Today `tests/architectural/test_no_dead_symbols.py` goes RED. Revert and record it. WP12 later shows the same plant GREEN.
  - A docstring or comment edit does **not** change the content-tier hash (`code_tokens_by_line` drops STRING/COMMENT tokens, `src/specify_cli/contracts/anchoring.py:87-117`), so it must **not** be used as the plant.
- **Parity snapshot (`before.json`)**: freeze the exact exempted `(module, name, category)` set plus the widened #470 set, with offenders and stale both `[]`. The snapshot lives **outside the repository** (scratchpad). Its script, parity digest and counts (293 / 91 on today's base) go into the evidence, so WP12 can regenerate and verify it.
- **NFR-003 / FR-009**: M1 is the executable form of "a body edit costs 0 edits".

## Context & Constraints

- Read first, in this order:
  1. `contracts/dead-symbol-allowlist.md`: all of it, especially §2 (G1–G8), §3 (M1–M13 and the ATDD rule) and §4 (migration and parity).
  2. `data-model.md` §1 (YAML shape, in-memory model, stale semantics).
  3. `research/dead-symbol-rekey.md` §3, §5 and §6.
  4. `plan.md` IC-09 and IC-10.
- **Target the contract, never today's internals.** If these tests encode `SymbolKey`, body hashes or tiers, WP12 has to rewrite them (plan risk).
- **The seam API is binding for WP11 and WP12.** The contract leaves exact call shapes open, so this WP fixes them. WP11 and WP12 implement exactly this surface:
  - **Loader module** `tests/architectural/_dead_symbol_allowlist.py` (created by WP11):
    - `DeadSymbolKey(module: str, name: str)`: a frozen dataclass; `str(key) == f"{module}::{name}"`.
    - `load_allowlist(path: Path = ALLOWLIST_PATH) -> DeadSymbolAllowlist`, where `DeadSymbolAllowlist.keys: frozenset[DeadSymbolKey]` and `.widened_qualified: frozenset[str]`.
    - `AllowlistSchemaError(ValueError)`.
    - `StaleVerdict`: a `StrEnum` with members `INVALID`, `GONE`, `REVIVED`, `SUPERSEDED`, `MOOT`, whose values are the upper-case names.
    - `ALLOWLIST_PATH`, `ALLOWLIST` (the single parsed `DeadSymbolAllowlist`), `SYMBOL_ALLOWLIST` and `WIDENED_SCOPE_GRANDFATHERED_470`. The last two are views of `ALLOWLIST` (F-05 / analysis F5).
  - **Gate module** `tests/architectural/test_no_dead_symbols.py` (rewritten by WP12):
    - `_real_tree_inputs() -> RealTreeInputs`: session-cached (`functools.lru_cache(maxsize=1)`), with attributes `decls`, `all_literal_decls`, `corpus`, `per_symbol`, `star_targets` and `collision_index`.
    - `_evaluate_allowlist(all_literal_decls, per_symbol, star_targets, corpus, allowlist, collision_index=None) -> AllowlistEvaluation`:
      - `allowlist` is a `DeadSymbolAllowlist`;
      - `collision_index=None` means compute it from `corpus`;
      - `AllowlistEvaluation.offenders` is a sorted `list[str]` of `module::name` (the `__all__` scope only, before the widened merge);
      - `AllowlistEvaluation.stale` is a `list[StaleFinding]`.
    - `StaleFinding(key: DeadSymbolKey, verdict: StaleVerdict, hint: str)`, with `render() -> str` giving `f"{key} [{verdict}] {hint}".rstrip()`. A GONE finding whose name appears as an offender in another module `X` has a hint containing `probably moved to \`X\``.
- **Minimal YAML** that the tests write (schema from data-model §1):
  ```yaml
  schema_version: 1
  categories:
    category_contract_test: {rationale: "ATDD contract fixture", requires_issue: false}
  entries:
    - {module: pkg.m, name: Baz, category: category_contract_test}
  widened_grandfathered_470: {rationale: "ATDD contract fixture", issue: "#5346", entries: []}
  ```
- This WP changes **no** existing file. It adds one test file.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. WP10 heads the dead-symbol chain: WP10 → WP11 → WP12 → {WP13, WP14} → WP15. Start with:

```bash
spec-kitty agent action implement WP10 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** `tests/architectural/test_no_dead_symbols.py` takes about 4 minutes. It is a **named gate file**, not a sweep, so running it is allowed. Never run `tests/architectural/` as a directory, never `make test-full`, and no heavy suites. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** The SC-003 plant is a scratch edit in `src/`; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Evidence.** Write data-model §4 YAML records, **plus** the parity-snapshot script text, its digest and its counts, into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report. WP12 needs the script text.
4. **Quality (NFR-005).** `uv run --frozen ruff check` and `uv run --frozen ruff format --check` on the new file. The file is not format-excluded. Add no new `noqa`.
5. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-opus-5-5`.
6. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits.
7. **Red-first through strict xfail, not a red hand-off (orchestrator ruling).** Each ATDD contract test that is red by contract against today's gate (M1, M7, M8, M11) is committed with `@pytest.mark.xfail(strict=True, raises=(ImportError, AttributeError), reason="pending the dead-symbol re-key (WP12, #5346)")`.
   - `raises=` makes a wrong-reason failure (a typo `NameError`, or a WP11 `AllowlistSchemaError`) a real FAIL, not a silent XFAIL.
   - Record in your evidence that each one fails for the stated reason: run it with `--runxfail` and show the red failure.
   - The strict marker then keeps the pre-review gate green, and it flips to XPASS, which fails the run, the moment the re-key lands. WP12 removes the markers.
   - Never pass `--skip-pre-review-gate`.

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
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. This WP's new or rewritten typed modules also run `uv run --frozen mypy tests/architectural/test_dead_symbol_allowlist_contract.py`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T045 – Scaffold the contract test file

- **Purpose**: A collectable file with shared helpers, so each M-test is short and red for the right reason.
- **Files**: `tests/architectural/test_dead_symbol_allowlist_contract.py` (new).
- **Steps**:
  1. Write a module docstring. Say that this is the FR-009 ATDD contract (contracts/dead-symbol-allowlist.md §3: M1, M7, M8, M11), and that tests import the seam **inside** their bodies so the file collects before the seam exists. Point to #5346.
  2. Add `pytestmark = [pytest.mark.architectural]`.
  3. Imports at module scope must be only stdlib, `pytest`, `yaml` and `tests.architectural._symbol_key` (it exists today: `CorpusModule`). **No** import of `_dead_symbol_allowlist`, and no gate attribute access, at module scope.
  4. Helpers:
     ```python
     def _seam():  # -> (allowlist module, gate module); raises ImportError/AttributeError today (the ATDD red)
         from tests.architectural import _dead_symbol_allowlist as allowlist_mod
         from tests.architectural import test_no_dead_symbols as gate
         if not callable(getattr(gate, "_evaluate_allowlist", None)):
             raise AttributeError("_evaluate_allowlist")  # the gate seam lands in WP12
         return allowlist_mod, gate

     def _write_allowlist(tmp_path: Path, entries: list[tuple[str, str]]) -> Path: ...
     def _synthetic_corpus(modules: dict[str, str]) -> tuple[dict[str, frozenset[str]], dict[str, CorpusModule]]: ...
     ```
     - `_write_allowlist` writes the minimal YAML shape shown in Context, with `yaml.safe_dump`.
     - `_synthetic_corpus` takes `{dotted_module: source}` and returns `(all_literal_decls, corpus)`. Parse `__all__` with `ast`: take the list literal from the `__all__ = [...]` assignment. `CorpusModule(tree=ast.parse(src), source=src, containing_pkg=<the module's package, e.g. "pkg">)`.
  5. Run `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py --collect-only -q`. It must collect with **no** errors.
- **Edge cases**: `CorpusModule`'s constructor fields must match `tests/architectural/_symbol_key.py` (`tree`, `source`, `containing_pkg`). Read it before using it.

### Subtask T046 – M1: a body edit of an allowlisted dead symbol costs 0 edits

- **Purpose**: The FR-009 acceptance test and SC-003. It **inverts** `bite_g`'s body-edit arm (today a body edit is an offender).
- **Steps**:
  1. `test_m1_body_edit_of_allowlisted_dead_symbol_stays_green(tmp_path)`:
     - `allowlist_mod, gate = _seam()`;
     - `path = _write_allowlist(tmp_path, [("pkg.m", "Baz")])`, then `allowlist = allowlist_mod.load_allowlist(path)`;
     - for `body` in `("Baz = 1\n", "Baz = 2\n")`, with the source `'__all__ = ["Baz"]\n' + body`:
       ```python
       decls, corpus = _synthetic_corpus({"pkg.m": source})
       result = gate._evaluate_allowlist(decls, {}, set(), corpus, allowlist)
       assert result.offenders == [] and result.stale == []
       ```
       Name the body in the assertion message.
  2. Make the second body structurally different too, e.g. a `def Baz(x: int) -> int: return x + 1` vs `return x + 2`, so the test exercises "body edit", not "constant change". These are code-token edits, which do change the runtime content hash.
  3. **Positive control on the same fixture** (tactic `acceptance-criteria-non-vacuity`, step 3). Evaluate the same `_synthetic_corpus` output against an allowlist of `[("pkg.m", "Other")]` and assert `result.offenders == ["pkg.m::Baz"]`. This proves that the probe sees the dead symbol when it is not exempted; without the control, an `_evaluate_allowlist` that ignored the corpus or the allowlist would also pass M1.
- **Red today**: `_seam()` raises (no loader module). After WP11 it still raises `AttributeError` (no `_evaluate_allowlist`). It goes green only after WP12.

### Subtask T047 – M7 (a rename is reported) and M8 (a move is reported with a hint)

- **Purpose**: Spec Edge Case 5. A rename or move is **not** a body edit, so the entry must be reported, never silently passed. M8 supersedes `bite_b` and `bite_j`'s relocation arm.
- **Steps**:
  1. `test_m7_rename_reports_gone_and_new_offender(tmp_path)`:
     - the allowlist is `[("pkg.m", "Old")]`, and the corpus is `{"pkg.m": '__all__ = ["New"]\nNew = 1\n'}`;
     - assert `result.offenders == ["pkg.m::New"]`;
     - assert exactly one stale finding, with `key == DeadSymbolKey("pkg.m", "Old")` and `verdict == StaleVerdict.GONE`.
  2. `test_m8_move_reports_gone_with_moved_hint_and_new_offender(tmp_path)`:
     - the allowlist is `[("pkg.a", "N")]`, and the corpus is `{"pkg.a": '__all__ = ["Other"]\nOther = 1\n', "pkg.b": '__all__ = ["N"]\nN = 1\n'}`;
     - `Other` would be an offender too. Either allowlist it as well (a second entry, so offenders stay focused) or assert the offender set exactly: `{"pkg.a::Other", "pkg.b::N"}`, or `{"pkg.b::N"}` if `Other` is allowlisted. Prefer allowlisting `Other`, for a crisp assertion.
     - Assert `result.offenders == ["pkg.b::N"]`, a GONE finding for `(pkg.a, N)`, and "probably moved to `pkg.b`" contained in `finding.hint` and in `finding.render()`.
- **Edge cases**: Keep the synthetic modules free of imports, so no caller edges exist (`per_symbol={}`).

### Subtask T048 – M11: authority parse over the real cached corpus

- **Purpose**: Prove that the gate reads the file it claims to read, not a cached copy (the `architectural-gate-non-vacuity` authority-parse step).
- **Steps**:
  1. `test_m11_gate_reads_the_allowlist_file_it_is_given(tmp_path)`:
     - `allowlist_mod, gate = _seam()`;
     - `inputs = gate._real_tree_inputs()`, the session-cached walk. It adds no second walk when it shares a process with the gate, but under CI's `-n auto --dist loadfile` it costs one extra walk on its own xdist worker. Say that in the docstring.
     - `raw = yaml.safe_load(allowlist_mod.ALLOWLIST_PATH.read_text(encoding="utf-8"))`.
     - **(a) Removed entry**: copy `raw` and pop one entry. Choose deterministically: the first entry, sorted by `(module, name)`, **whose category has ≥ 2 entries**, so that the loader's L9 rule (no tombstone categories) cannot trip. Dump it to `tmp_path / "removed.yaml"`, load it, evaluate against `inputs`, and assert `f"{module}::{name}"` is in `result.offenders`.
     - **(b) Bogus entry**: copy `raw` and append `{module: "specify_cli", name: "DefinitelyNotARealSymbol5346", category: <an existing category id>}`. Dump, load and evaluate, then assert a GONE finding for that key.
     - **Control**: evaluate the real `load_allowlist()` against `inputs`, and assert `offenders == []` and `stale == []`. This proves that (a) and (b) are caused by the edits.
  2. Keep it in **one** test function, so the real inputs are computed once even if lru caching is disturbed.
- **Red today**: the missing seam. **Cost**: after WP12 this test walks the real tree once per xdist worker (about the same as the gate). Note that in the docstring.
- WP12 adds an M11(c) arm for the widened section in its own gate file (F-05). Do not add it here.

### Subtask T049 – Parity snapshot (`before.json`), SC-003 real-tree red, evidence

- **Purpose**: Freeze exactly what today's allowlist exempts, so WP12 can prove the re-key is lossless (contract §4, data-model §1.7). Also record the real-tree red that SC-003 compares against.
- **Steps**:
  1. Write a **scratchpad-only** script, `parity_before.py`, in your session scratchpad (never in the repository). Run it from the repository root with `PYTHONPATH=. uv run --frozen python <scratch>/parity_before.py > <scratch>/before.json`. Its logic:
     ```python
     from tests.architectural import test_no_dead_symbols as g
     from tests.architectural._symbol_key import classify_collisions
     decls, all_literal, p2d, p2t, corpus = g._walk_modules()
     per_symbol, star = g._imports_by_target(p2d, p2t)
     idx = classify_collisions(corpus)
     cat_of = {}  # SymbolKey -> category id (constant name, lower-cased, leading "_" stripped)
     for const_name, keys in g._category_frozensets().items():
         for k in keys:
             cat_of[k] = const_name.lstrip("_").lower()
     rows = sorted(
         [mod, name, cat_of[key]]
         for mod, names in all_literal.items()
         for name in names
         if (key := g._resolve_final_key(name, mod, corpus.get(mod), corpus, idx)) is not None and key in g._SYMBOL_ALLOWLIST
     )
     widened = sorted(list(s.split("::", 1)) for s in g._WIDENED_SCOPE_GRANDFATHERED_470)
     # offenders/stale: reproduce test_no_public_symbol_in_all_is_unimported's pipeline
     # (offenders after widened rescue; stale + dangling + widened_stale) -> both must be [].
     ```
     Emit JSON with `sort_keys=True, indent=2` and the keys `base_sha` (`git rev-parse HEAD`), `allowlist`, `widened_470`, `offenders`, `stale` and `counts` (`{"allowlist": len(rows), "widened_470": len(widened)}`).
     - Check `_category_frozensets`'s real return shape (`test_no_dead_symbols.py:2468`) and adapt the snippet; it may key by constant name.
  2. Assert, in the script: `counts == {"allowlist": 293, "widened_470": 91}` on this base (re-measure and record if the base moved), `len(set(map(tuple, rows))) == len(rows)`, and `offenders == stale == []`.
  3. Compute the **parity digest**:
     ```python
     sha256(json.dumps({k: d[k] for k in ("allowlist", "widened_470", "offenders", "stale")}, sort_keys=True, separators=(",", ":")).encode())
     ```
  4. **SC-003 real-tree red (planted)**:
     - Confirm `append_lifecycle_event` is allowlisted (it appears in `before.json`; it is defined in `src/specify_cli/status/lifecycle_events.py`, around `:608-645`).
     - Scratch edit: rename the local `envelope` to `persisted_envelope` in its body, all 4 occurrences (the assignment, `if envelope is not None`, the `fanout_lifecycle_event_hosted(...)` argument and the `return`). **Not** a docstring edit: string and comment tokens are dropped from the hash, so a docstring edit would stay green and prove nothing.
     - Run `uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q -k test_no_public_symbol_in_all_is_unimported`. Expect **RED**: the symbol shows up as an offender, because its code-token body hash changed.
     - Revert with `git checkout -- <that file>`, re-run, and confirm GREEN.
  5. Run the contract file twice:
     - `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q -rxX`: expect every test **XFAIL (strict)**, never a collection error;
     - `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q --runxfail`: expect every test **FAIL** on the missing seam (`ModuleNotFoundError: tests.architectural._dead_symbol_allowlist`).

     Record the failure lines.
  6. Commit:
     ```
     test(architectural): ATDD contract pins for the dead-symbol (module, name) re-key (red) (#5346)
     ```
- **Evidence records**:
  - **EV-IC09-01**: the contract file red, per test.
  - **EV-IC09-02**: the SC-003 plant red on the base gate (command, output excerpt, reverted).
  - **EV-IC09-03**: the parity snapshot: the full script text, counts, digest and `base_sha`.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py --collect-only -q
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q -rxX     # expect: every test XFAIL (strict)
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q --runxfail  # expect: every test FAIL on the missing seam
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q                          # expect: GREEN before the plant
uv run --frozen ruff check tests/architectural/test_dead_symbol_allowlist_contract.py
uv run --frozen ruff format --check tests/architectural/test_dead_symbol_allowlist_contract.py
make test-fast
```

## Risks & Mitigations

- **Encoding internals.** No `SymbolKey`, `body_hash` or tier in the new file. Only `DeadSymbolKey`, `StaleVerdict`, `load_allowlist`, `_evaluate_allowlist`, `_real_tree_inputs` and `StaleFinding`.
- **A collection-time red.** Keep every seam import inside the test bodies, through `_seam()`.
- **Base drift** before WP12. WP12 re-runs your script at its own start and compares the digest. Make the script self-contained and deterministic.

## Definition of Done (C-011)

- **C-011 (D1 reading, `traces/design-decisions.md`)**: the ATDD contract tests are committed first, as `xfail(strict=True, raises=(ImportError, AttributeError))`. At this WP's final commit they are strict XFAIL, and RED under `--runxfail` on the missing seam. The GREEN half is verified at chain level, when WP12 removes the markers and they PASS. The SC-003 red observation (the code-token plant, RED on the base gate) is recorded.

## Review Guidance

- The file collects, and every test is strict XFAIL with `raises=(ImportError, AttributeError)`. `--runxfail` shows each one failing on the missing seam (`ModuleNotFoundError`, or `AttributeError: _evaluate_allowlist`), never on a typo.
- M1 has its same-fixture positive control (`[("pkg.m", "Other")]` → `offenders == ["pkg.m::Baz"]`).
- M11(a) pops from a category with ≥ 2 entries.
- The seam API described in Context is exactly what the tests call. That is the binding surface for WP11 and WP12.
- The parity snapshot script is in the evidence, with counts 293 / 91 and the digest.
- The SC-003 red observation uses the `envelope` → `persisted_envelope` code-token plant (never a docstring edit), and it is recorded with its revert.

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
spec-kitty agent tasks mark-status T045 T046 T047 T048 T049 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP10 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records incl. parity script + digest>"
```
