---
work_package_id: WP08
title: Non-vacuous closed-by-construction gate (#4746/FR-011)
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- FR-011
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T028
- T029
- T030
phase: Phase 3 - Capstone
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_cli_error_surface_seam.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- tests/architectural/test_cli_error_surface_seam.py
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Non-vacuous closed-by-construction gate (#4746/FR-011)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## 🔴 BINDING SQUAD AMENDMENTS (post-tasks fold — read before implementing)

1. **T028 — the in-scope READ-module list is wrong; use the modules that actually read**: `cli/commands/workflow.py`, `cli/commands/mission_type.py`, `cli/commands/accept.py`, `cli/commands/agent/release.py`, `release/payload.py` (holds `_read_current_version` — the #4637 read), `cli/commands/intake.py`, `intake/scanner.py`, `cli/commands/lifecycle.py`, plus the 7 audit-tail readers. **Remove the mislabeled `agent/status.py (release prep)`** — `agent/status.py` holds WP03's `-f` flags, not a read path; release prep lives in `agent/release.py` → `release/payload.py`. A gate over the wrong module leaves #4637's read uncovered.
2. **T028/T030 — the shrink-only floor MUST be derived from a real scan** of those modules, not assumed zero. `workflow.py:85` (`_copy_workflow` `read_bytes`) is guarded by WP02, so it should NOT appear; any residual raw read gets a justified baseline entry with an inline `# justification:` note. State in the test that the floor came from a scan.
3. **This WP lands LAST** (deps WP01..WP07). Reuse the AST/call-graph pattern in `tests/architectural/_gate_read_callshape.py`. `tests/architectural/_baselines.yaml` is a SHARED ratchet — add ONLY this gate's new top-level key; never touch an existing one.

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This is the mission's **capstone WP** (spec.md US3, FR-011, SC-003). It
does not fix another defect — it builds the architectural gate proving the
defect *class* stays closed after every other WP lands. Per charter
Standing Order #5 and DIRECTIVE_043, a gate that cannot fail is not a
gate; this WP's job is to make the gate demonstrably capable of failing,
then prove the hardened tree passes it.

Success means:

- The gate asserts the **named invariant** from FR-011, and only that
  invariant — not a broader, vaguer "everything is fine" check:
  1. the global Typer error hook (WP01) is registered on the top-level
     `spec-kitty` app, and
  2. no in-scope command reaches a read/decode/resolver outside
     `kernel.read_guarded` — checked by an AST/call-graph scan against a
     **concrete, shrink-only floor** (a named allowlist/count, recorded in
     `tests/architectural/_baselines.yaml`), not a vague heuristic.
- A **self-mutation non-vacuity test** proves the gate fails when (i) the
  hook registration is removed, and separately when (ii) a simulated
  in-scope command with a bare read/decode outside `read_guarded` is
  introduced. Per DIRECTIVE_043, a gate whose failure mode is never
  exercised is not trustworthy — this test IS the trust.
- The gate is wired into the always-on architectural battery, and its
  baseline entry in `_baselines.yaml` follows that shared file's existing
  shrink-only ratchet contract.
- This WP lands **last**, after WP01–WP07, so the floor it encodes is the
  clean, hardened tree — not a tree with known-red adoption gaps.

## Context & Constraints

- **Dependencies**: WP01 (primitive + hook + subclassing), WP02, WP03,
  WP04, WP05, WP06, WP07 (all adoption). Do not start writing the gate's
  concrete floor until those land — the floor is only meaningful once
  every named command boundary is actually hardened. If any dependency WP
  is genuinely incomplete when you pick this up, the gate is **allowed**,
  even expected, to be red — that is the honest signal, not a bug in this
  WP (per the memory note: "P0 escalation implies redding test" and
  "honest-red not greenwash" — do not paper over an incomplete adoption
  WP by loosening the gate's floor).
- Read `contracts/guarded-read-primitive.md` and `contracts/error-envelope.md`
  again before writing the scan — the gate's job is to assert those two
  contracts hold structurally, not to re-describe them.
- Read `spec.md`'s US3 (all 4 acceptance scenarios) and FR-011/NFR-002's
  INV-1..INV-4 invariants from the error-envelope contract — the gate's
  assertions must map 1:1 to those, not invent new ones.
- **Prior art already exists** — read `tests/architectural/_gate_read_callshape.py`
  before writing your own AST helpers. It's the same shape (a different
  mission's coord-read authority gate): walk `ast.FunctionDef`/`ast.Call`,
  flag calls to a named "raw read" set not wrapped by the sanctioned
  primitive. Reuse its idioms (`_call_func_name`, `ast.walk` over
  `ast.Call`, frozenset allowlists) rather than a parallel style.
- **`tests/architectural/_baselines.yaml` is a SHARED ratchet file** used
  by many unrelated gates (`test_layer_rules`, `test_no_dead_modules`,
  `test_ratchet_baselines.py`, etc. — see the file's own header comment).
  You own only the **new top-level key** you add for this gate (e.g.
  `test_cli_error_surface_seam: in_scope_boundary_count: N  #
  justification: ...`). Never edit or renumber an existing key while
  working this WP — that is a different gate's baseline and a collision
  there is a sign you grabbed the wrong line.
- The "in-scope command" universe is finite and named by this mission:
  `workflow import`/`export`, `mission close`, `accept`, `agent release
  prep`, `intake -`, `specify`, plus the 7 audit-tail readers' reachable
  commands from WP07. Do not attempt to scan the entire CLI surface —
  that would silently widen scope past what WP02–WP07 actually hardened
  and produce a gate that's red for reasons unrelated to this mission.

## Branch Strategy

- **Strategy**: coord (coordination-branch topology; this WP's lane
  worktree branches off the mission coordination branch
  `kitty/mission-cli-error-surface-seam-01M2WJD2`).
- **Planning base branch**: `fix/cli-error-surface-seam`
- **Merge target branch**: `fix/cli-error-surface-seam`

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### T028 – Author the gate: hook registration + call-graph floor

- **Purpose**: Build the actual gate test asserting FR-011's two-part
  invariant against the concrete, named in-scope command universe.
- **Steps**:
  1. Create `tests/architectural/test_cli_error_surface_seam.py`. Add a
     module docstring naming FR-011, the umbrella issue (#4746/#2899), and
     the invariant in one sentence — follow the header-comment style of
     `tests/architectural/_gate_read_callshape.py` / `_baselines.yaml`.
  2. **Part (a) — hook registration**: import the top-level Typer `app`
     object (WP01's home for the registered hook — confirm the exact
     module/attribute WP01 landed it at; do not guess a path that doesn't
     exist) and assert the hook callable is present in the app's
     exception-handler registration (Typer/Click's `except` machinery —
     inspect via the app's `registered_callback`/`exception_handlers` or
     whatever concrete mechanism WP01 used; read WP01's actual diff before
     writing this assertion, not the contract doc's "indicative" language).
  3. **Part (b) — call-graph floor**: write (or extend, following
     `_gate_read_callshape.py`'s pattern) an AST helper module — e.g.
     `tests/architectural/_gate_guarded_read_callshape.py` — that:
     - Defines a frozenset of "raw read" callee names that are NOT
       `read_guarded` (`open`, `Path.read_text`, `Path.read_bytes`,
       `json.load`, `json.loads`, `yaml.safe_load`, `YAML().load`,
       `tomllib.load`) — the same shape WP01's primitive wraps.
     - Walks the AST of each in-scope command module (named explicitly —
       `cli/commands/workflow.py`, `cli/commands/mission_type.py`,
       `cli/commands/accept.py`, `cli/commands/agent/status.py` (release
       prep), `cli/commands/intake.py`, `cli/commands/lifecycle.py`, plus
       the WP07 reader files) and their reachable helper functions, and
       flags any call to a raw-read callee that is not inside a
       `read_guarded(...)` call or a function whose only caller path is
       already covered by one.
     - Compares the violation count (should be **zero** on the hardened
       tree) against the shrink-only floor recorded in
       `tests/architectural/_baselines.yaml` under a new
       `test_cli_error_surface_seam:` key, following that file's existing
       `# justification:` comment convention.
  4. Do not scan the whole repository — build an explicit list of the
     in-scope module paths (from `plan.md`'s "Project Structure" source
     map) and only walk those. A repo-wide scan is both slow and would
     flag pre-existing, out-of-scope raw reads that are not this
     mission's job to fix.
- **Files**: `tests/architectural/test_cli_error_surface_seam.py` (new),
  `tests/architectural/_gate_guarded_read_callshape.py` (new, optional
  helper split — keep the test file itself readable), `_baselines.yaml`
  (new key only).
- **Parallel?**: No — foundation for T029/T030.
- **Notes**: keep the AST walker's cyclomatic complexity ≤ 15; extract
  helpers per the `_gate_read_callshape.py` style (small, named,
  single-purpose functions) rather than one large nested-conditional
  function.

### T029 – Self-mutation non-vacuity test (DIRECTIVE_043)

- **Purpose**: Prove the gate is not vacuous. A gate that always passes
  regardless of the code it inspects has zero value and actively misleads
  — DIRECTIVE_043 and charter Standing Order #5 require every
  closed-by-construction gate to carry proof it can fail.
- **Steps**:
  1. Write a test (in the same file, or a clearly-named sibling test in
     the same module) that **simulates hook removal**: construct or patch
     an in-memory stand-in for "the app with its error hook unregistered"
     (do not actually mutate the real `app` object at import time — use a
     fresh `typer.Typer()` instance built the same way WP01's bootstrap
     does, minus the hook registration call, OR monkeypatch the specific
     registration call to a no-op for the duration of this one test) and
     assert Part (a)'s check **fails** against it.
  2. Write a second test that **simulates an unguarded in-scope command**:
     write a small temporary/synthetic Python source string (or a fixture
     file under `tests/architectural/_fixtures/` — check that directory's
     existing convention first) containing a function shaped like an
     in-scope command that calls `open(...)` or `json.loads(...)` directly,
     not through `read_guarded`. Feed that source into the SAME AST walker
     Part (b) uses (call the walker function directly with the synthetic
     module's AST, not the real file) and assert it reports a violation.
  3. Both self-mutation tests must be clearly distinguished from the
     "real tree, must pass" tests in T028/T030 — name them explicitly,
     e.g. `test_gate_fails_when_hook_registration_removed` and
     `test_gate_fails_when_unguarded_read_introduced`, and add a short
     comment citing DIRECTIVE_043 so a future reader understands why a
     test in an architectural-gate file is *expected* to construct a
     broken tree.
  4. Confirm neither self-mutation test can accidentally pass for the
     wrong reason (e.g. an import error masquerading as "the check
     failed") — assert on the specific violation/failure the walker or
     hook-check reports, not just "raised an exception."
- **Files**: `tests/architectural/test_cli_error_surface_seam.py` (same
  file as T028, or a clearly-linked sibling — keep the non-vacuity tests
  next to the gate they prove).
- **Parallel?**: Depends on T028's walker existing as a callable unit
  (not just inlined in one big test function) — if T028 wrote the walker
  as an importable helper (recommended, mirrors
  `_gate_read_callshape.py`'s module-level functions), this subtask is
  straightforward; if not, refactor first.
- **Notes**: this is the single most important subtask in the mission's
  capstone WP — a plausible-looking gate with a vacuous self-mutation
  test is worse than no gate (false confidence). Do not accept "the test
  exists" as done; verify by temporarily reverting T028's real fix (in a
  scratch checkout, not in the PR) and confirming the self-mutation tests
  would have caught it, then discard that scratch revert.

### T030 – Wire into the arch battery + shrink-only baseline

- **Purpose**: Make the gate part of the standing, always-on architectural
  battery (not an orphaned file nobody runs), and record its baseline
  per the shared ratchet-file contract.
- **Steps**:
  1. Confirm `tests/architectural/test_cli_error_surface_seam.py` is
     picked up by the existing `tests/architectural/` collection
     mechanism (check `conftest.py` / `_gate_collect_plugin.py` for any
     opt-in registration step other gates use — most `test_*.py` files
     under `tests/architectural/` are auto-collected by pytest's normal
     discovery, but confirm there is no allowlist this file must also
     join, per the "new CI module = 5-surface coupling" memory note —
     that note is about CI *module* shards, not this per-file battery, but
     verify there isn't an analogous local registration list).
  2. Add the new baseline key to `tests/architectural/_baselines.yaml`
     with a `# justification:` comment naming this mission and FR-011,
     following the file's documented schema
     (`kitty-specs/slice-f-multi-context-extensibility-01KRX5C8/contracts/ratchet-baseline-format.md`
     — read it before inventing a different shape for your key).
  3. Run this WP's own test file in isolation —
     `pytest tests/architectural/test_cli_error_surface_seam.py -v` —
     and confirm it is fast and self-contained (per the memory note: a
     full `tests/architectural/` run is heavy and should not be required
     to validate this WP locally).
  4. Run `tests/architectural/test_ratchet_baselines.py` (targeted, not
     the full architectural suite) to confirm your new baseline entry is
     recognized and consistent with the live allowlist/count it guards.
  5. Do NOT run the full `tests/architectural/` suite as your local
     verification step (memory: "no full arch suite locally" — it can
     break the session); targeted runs of this file plus
     `test_ratchet_baselines.py` are sufficient evidence for this WP. The
     CI aggregate job owns the full battery.
- **Files**: `tests/architectural/_baselines.yaml` (new key), no other
  file changes expected beyond T028/T029's test file.
- **Parallel?**: No — final subtask, confirms the whole WP is wired.
- **Notes**: if WP01–WP07 landed cleanly, this gate should be green on
  first run once the floor matches reality; if it is red, that is either
  a genuine incomplete-adoption signal (leave it honestly red per the
  "honest-red not greenwash" doctrine and note which dependency WP is
  short) or a floor-count mismatch you introduced (fix the count, not the
  gate's logic).

## Test Strategy

- `pytest tests/architectural/test_cli_error_surface_seam.py -v` — must
  be runnable standalone, fast, with no dependency on the rest of the
  architectural battery having run first.
- `pytest tests/architectural/test_ratchet_baselines.py -v` (targeted) to
  confirm the new baseline key is consistent.
- The two self-mutation tests (T029) are the load-bearing proof for this
  WP's review — a reviewer should be able to read them and understand
  exactly what breaking change each one detects.
- mypy: run the project's configured mypy invocation over the new test
  file(s) — architectural tests are still typed source and must be clean.
- Do not run `make test-full` or the whole `tests/architectural/`
  directory locally; that is the CI agent's job per CLAUDE.md's test
  policy and this mission's own guidance above.

## Risks & Mitigations

- **Risk**: the gate's AST walker is too narrow and silently misses a
  raw-read call shape (e.g. `pathlib.Path(...).open()` vs the top-level
  `open()` builtin, or an aliased import). **Mitigation**: T029's
  self-mutation test using a *synthetic* unguarded command is exactly the
  safety net for this — if it doesn't catch an equivalent-shape violation
  to what T028 is meant to police, the walker is incomplete; broaden it
  until the synthetic case is caught.
- **Risk**: vacuous self-mutation test (asserts something trivially true
  regardless of the walker's correctness). **Mitigation**: T029 step 4
  explicitly calls for verifying the negative — temporarily break the
  real fix and confirm the test would have caught it.
- **Risk**: landing this WP before WP02–WP07 are actually done, producing
  a gate that's red for the wrong reason (incomplete adoption, not gate
  bugs) and confusing later reviewers. **Mitigation**: this WP's
  `dependencies` list is exhaustive (WP01–WP07); do not claim/start until
  they are `approved`/`done` per the dependency-gating rule in
  `status/` doctrine.
- **Risk**: colliding with an unrelated key in the shared
  `_baselines.yaml` ratchet file. **Mitigation**: add only a new
  top-level key; diff the file before/after to confirm no existing key's
  value changed.

## Review Guidance

- Confirm the gate asserts exactly the FR-011 invariant (hook registered +
  no in-scope unguarded read) — not a broader or vaguer check.
- **Run both self-mutation tests yourself and read them line by line** —
  this is the capstone WP's single most important review checkpoint per
  DIRECTIVE_043. A gate PR without a genuinely falsifiable self-mutation
  test should be rejected regardless of how clean the rest of the diff is.
- Confirm the in-scope command list matches what WP02–WP07 actually
  hardened — no silent scope creep, no silent scope gap.
- Confirm `_baselines.yaml` only gained one new key and no existing key's
  value or comment changed.
- Confirm this WP's test file runs standalone and fast, and that the
  reviewer did not have to run the full `tests/architectural/` suite to
  validate it.
- If the gate is red at review time, confirm whether that's an honest
  incomplete-adoption signal (acceptable, document which WP is short) or
  a bug in this WP's own logic (not acceptable).

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

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-19T10:45:02Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
