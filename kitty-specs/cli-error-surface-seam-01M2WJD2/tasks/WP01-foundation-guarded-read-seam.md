---
work_package_id: WP01
title: 'Foundation: guarded-read primitive + global hook + subclassing'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-013
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-error-surface-seam-01M2WJD2
base_commit: 91b4c6bad939b24690b943c63ad56d6d3ac9c6b3
created_at: '2026-09-19T11:20:38.340461+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/guarded_read.py
- tests/kernel/test_guarded_read.py
- tests/specify_cli/test_error_hook.py
- tests/specify_cli/test_error_backcompat.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/kernel/guarded_read.py
- src/kernel/errors.py
- src/kernel/meta_decode.py
- src/specify_cli/__init__.py
- src/specify_cli/core/paths.py
- src/specify_cli/decisions/store.py
- src/specify_cli/lanes/persistence.py
- src/specify_cli/core/agent_config.py
- src/specify_cli/intake/errors.py
- docs/changelog/CHANGELOG.md
- pyproject.toml
- tests/kernel/test_guarded_read.py
- tests/specify_cli/test_error_hook.py
- tests/specify_cli/test_error_backcompat.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Foundation: guarded-read primitive + global hook + subclassing

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## 🔴 BINDING SQUAD AMENDMENTS (post-tasks fold — read before implementing)

These override any conflicting guidance below. From the post-tasks adversarial + brownfield squads.

1. **T001 — `GuardedReadError` constructor MUST be positional-compatible**, NOT required-kwargs:
   `def __init__(self, *args, path=None, reason=None): super().__init__(*args); self.path = path; self.reason = reason`.
   Three re-parented subclasses pass a **positional message** into the base — `UnsafePathSegmentError` (6 raise sites `core/paths.py:78,85,91,97,103,109`), `MissionMetaReadError` (`core/paths.py:563-569` `super().__init__(f"…")`), `DecisionIndexReadError` (`decisions/store.py:~55-60`). A required-kwargs base → `TypeError` at all of them plus ~85 test constructors. The T006 hook falls back to `str(exc)` when `path`/`reason` are `None`.
2. **T004 — MRO: two subclasses must ALSO keep `ValueError`.** `GuardedReadError(Exception)` (plain Exception, not OSError). Then `class UnsafePathSegmentError(GuardedReadError, ValueError)` (paths.py:42) **and** `class MetaDecodeError(GuardedReadError, ValueError)` (meta_decode.py:41 — its docstring subclasses `ValueError` deliberately). Live `except ValueError` catchers of `MetaDecodeError`: `mission_metadata.py:149,188`, `task_metadata_validation.py:286`, `upgrade/metadata.py:121`, `status/wp_metadata.py:418`. C3 linearization `[X, GuardedReadError, ValueError, Exception]` is valid and keeps both `except` forms matching.
3. **T005 — back-compat regression MUST include the `except ValueError` catchers** for BOTH `UnsafePathSegmentError` and `MetaDecodeError` (parallel assertions), plus the `MissingLanes`/`CorruptLanes` coupled-pair tuple.
4. **T006 — DEFER the `next_cmd.py` emitter-fold.** `next_cmd.py` is owned by NO WP; do NOT delete/rewrite `_emit_meta_read_error` / `_emit_unsafe_mission_slug_error` (defs `next_cmd.py:787/834`, sites 221/306/338). Register the global hook only; record the emitter-fold as the D4 "future consistency follow-up" for the PR body. **Strike "merge's own emitter"** — no guarded-read presentation emitter exists in `src/specify_cli/merge/`.
5. **This WP does NOT touch `core/wps_manifest.py`** — it has no legacy error to re-parent (WP07 mints `WpsManifestReadError` there). Ignore any note implying WP01 edits its type hierarchy.
6. **`pyproject.toml` is now in `owned_files`** — land the version bump with the PO-supplied number (do not invent one); if the PO defers, note in the PR why the interim `__init__.py` change is acceptable.
7. **Branch topology is `coord`**, planning/merge base `fix/cli-error-surface-seam` (authoritative in `lanes.json`). Ignore any "single branch"/"base main" prose in the body.

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

This is the **MVP enabler** for the whole mission (umbrella #2899). WP02–WP07 all
depend on it; nothing else can land until this WP is done/approved. You are building
two collaborating pieces and reconciling the existing typed-error zoo onto them:

1. A **format-agnostic kernel primitive** `read_guarded()` (`src/kernel/guarded_read.py`)
   plus a `GuardedReadError` base (`src/kernel/errors.py`).
2. A **single global Typer error-presentation hook** registered on the top-level
   `spec-kitty` app that catches `GuardedReadError` (+ subclasses), renders a clean
   human line or a JSON envelope at exit 1, and re-raises everything else.
3. The 7 existing legacy typed read errors re-parented **in place** as
   `GuardedReadError` subclasses (never flat-replaced) so the ~85 existing `except`
   sites keep matching.

**Done when**:
- `read_guarded()` matches `contracts/guarded-read-primitive.md` exactly (signature,
  guarantees, non-goals) and has a full kernel unit matrix.
- `kernel/meta_decode.decode_meta` sits on `read_guarded` with #4600/#4642 behavior
  provably unchanged.
- All 7 legacy errors subclass `GuardedReadError` in place; `UnsafePathSegmentError`
  still satisfies `except ValueError`.
- One global hook is registered on the top-level app; it matches
  `contracts/error-envelope.md` exactly (text line / JSON object / exit 1 / exit-2
  passthrough / re-raise non-domain).
- The `except`-site census (src + tests) is reproduced/extended from `research.md`
  and a `tests/specify_cli/test_error_backcompat.py` regression proves every legacy
  type is still caught (NFR-006), including the `MissingLanesError`/`CorruptLanesError`
  coupled pair.
- The `[Unreleased]` `CHANGELOG.md` entry for the whole #2899 mission is added.

## Context & Constraints

- Read `.kittify/charter/charter.md` (Quality & Tech-Debt Standing Orders, esp. SO#5
  architectural gate discipline and DIRECTIVE_043/044).
- Design authority for this WP: `kitty-specs/cli-error-surface-seam-01M2WJD2/plan.md`
  (Architecture section + Module placement), `research.md` (decisions D1–D5 + the
  `except`-site census table), `quickstart.md` (the adoption pattern — follow it,
  do not re-derive it), `contracts/guarded-read-primitive.md`, and
  `contracts/error-envelope.md` (the two contracts this WP must satisfy byte-for-byte
  in shape).
- **D1 (kernel stays dependency-free)**: `read_guarded` takes a caller-supplied
  `parse` callable and a caller-declared exception tuple. It NEVER imports pydantic,
  tomllib, or a YAML decoder — those stay in the caller layer (`specify_cli`/
  `runtime`). Verify against `tests/architectural/test_layer_rules.py`
  (`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`).
- **D2 (hook, not a decorator)**: the hook is registered once, globally — not an
  opt-in per-command decorator (that pattern is the exact omission that produced
  #4642). Fold the shipped bespoke emitters (`_emit_meta_read_error`,
  `_emit_unsafe_mission_slug_error`, merge's own emitter) into the hook wherever the
  fold is behavior-preserving; do not delete an emitter's distinguishing behavior
  without an equivalent path through the hook.
- **D3 (subclass, never flat-replace)**: every legacy error keeps its current
  module path and its current base-class compatibility (e.g. `UnsafePathSegmentError`
  must remain a `ValueError` so `except ValueError:` sites keep matching — use
  multiple inheritance, `class UnsafePathSegmentError(GuardedReadError, ValueError):`,
  and double-check MRO with `UnsafePathSegmentError.__mro__`).
- Charter constraints to hold throughout: cyclomatic complexity ≤ 15 (extract
  helpers rather than nesting); ruff + mypy clean with **zero** new suppressions;
  ≥ 90% new-code coverage; every new kernel symbol declares `__all__` and has ≥ 1
  real caller (C-004/C-007); terminology canon — no new `--feature`/`Feature`
  surface, `--mission` only.
- **Editing `src/specify_cli/__init__.py` requires a `docs/changelog/CHANGELOG.md`
  `[Unreleased]` entry AND a version bump in `pyproject.toml` per `CLAUDE.md`.** Add
  the CHANGELOG entry for the whole umbrella (#2899) as part of this WP — but do
  **not** pick or prescribe the version number; flag the pending bump for the PO in
  your Activity Log / PR notes instead of guessing a semver.

## Branch Strategy

- **Strategy**: Single branch — all WPs land directly on the mission branch.
- **Planning base branch**: `fix/cli-error-surface-seam`
- **Merge target branch**: `fix/cli-error-surface-seam` (the mission branch is later opened as a PR against `main`, per plan.md's STOP note — do not push to `main` yourself)

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – `GuardedReadError` base in `kernel/errors.py`

- **Purpose**: the one exception base the global hook catches and every legacy
  reader-error subclasses.
- **Steps**: Add `GuardedReadError` to `src/kernel/errors.py` alongside the existing
  `KittyInternalConsistencyError` family (do not delete or repurpose that base —
  it serves a different, unrelated concern). Carry `path: str` and `reason: str`
  attributes/constructor params, and an actionable `__str__`/`args` message (the
  same text the hook prints on the non-JSON path — see
  `contracts/error-envelope.md`). Add `"GuardedReadError"` to the module's
  `__all__`.
- **Files**: `src/kernel/errors.py`.
- **Parallel?**: No — everything else in this WP depends on it.
- **Notes**: Keep it a plain `Exception` subclass (not tied to `OSError`) — the
  legacy errors re-parent onto it via multiple inheritance in T004, so it must not
  force an incompatible MRO with `ValueError`/`RuntimeError`.

### Subtask T002 – `read_guarded()` primitive in `kernel/guarded_read.py`

- **Purpose**: the format-agnostic guarded-read primitive per
  `contracts/guarded-read-primitive.md`.
- **Steps**: Implement the signature exactly as the contract's indicative shape:
  `read_guarded(path, parse, *, errors=(), error_cls=GuardedReadError, mode="text")`.
  Read `path` exactly once (`mode="text"` → utf-8 decode via `Path.read_text`;
  `mode="bytes"` → `Path.read_bytes`) — no second `open`, no extra decode pass
  (NFR-003, structural — not a wall-clock micro-benchmark). Apply `parse` to the
  content; on success return its result unchanged. Catch `(OSError,
  UnicodeDecodeError, *errors)` from either the read or `parse` and raise
  `error_cls(path=str(path), reason=<actionable message>)` via `raise … from exc`
  (chain the original for logs, but the hook-printed message carries no stack).
  Any exception outside the declared set propagates unchanged — a real bug in
  `parse` must still traceback. Add `__all__ = ["read_guarded"]`.
- **Files**: `src/kernel/guarded_read.py` (new), `tests/kernel/test_guarded_read.py`
  (new).
- **Parallel?**: No.
- **Notes**: Unit matrix to cover: happy path (returns parsed value, single read
  call — assert via a read-count spy, not wall-clock timing); `OSError` (missing
  file, permission denied); `UnicodeDecodeError` (non-UTF-8 bytes in text mode);
  a declared caller exception (`json.JSONDecodeError` as an example); an
  UNDECLARED exception from `parse` propagating untouched (proves guarantee #4 —
  "any exception not in the declared set propagates unchanged"); `mode="bytes"`
  parity; the raised error carries the original via `__cause__`.

### Subtask T003 – Refactor `meta_decode.decode_meta` onto `read_guarded`

- **Purpose**: prove the primitive works for a real, already-shipped consumer
  without regressing it.
- **Steps**: `kernel/meta_decode.py`'s `decode_meta` is a **pure decode** function
  today (no filesystem I/O — see its docstring: "This module is pure"). Do not
  force it to become a file-reading wrapper if that would violate its documented
  L1/pure-decode contract; instead, refactor its internal malformed-detection logic
  (JSON decode error / UnicodeDecodeError-from-explicit-decode / non-dict top level)
  to share logic with `read_guarded`'s error-collapsing behavior where doing so does
  not require `decode_meta` to take a filesystem path. If a literal call to
  `read_guarded` is not possible while preserving purity, extract the shared
  "collapse these exceptions into one typed error" logic into a small private
  helper both `read_guarded` and `decode_meta` call — record which approach you
  took and why in the Activity Log, since the plan's mermaid diagram shows
  `MDEC --> PRIM` as a dependency arrow, not necessarily a literal function call.
- **Files**: `src/kernel/meta_decode.py`.
- **Parallel?**: No.
- **Notes**: The regression here IS the safety net: assert `decode_meta`'s
  documented behavior for #4600/#4642 (malformed JSON → `MetaDecodeError`;
  non-dict top level → `MetaDecodeError`; bad-bytes decode → `MetaDecodeError`;
  empty/whitespace → the existing `on_malformed` short-circuit) is byte-for-byte
  unchanged before and after the refactor. Do not weaken `on_malformed` semantics.

### Subtask T004 – Re-parent the 7 legacy errors as `GuardedReadError` subclasses

- **Purpose**: D3 — subclass compatibility, never flat replacement.
- **Steps**: In place, for each of the 7 legacy errors, add `GuardedReadError` to
  its base classes while preserving every existing base:
  - `MissionMetaReadError` (`src/specify_cli/core/paths.py`, currently
    `RuntimeError` at ~line 544) → `class MissionMetaReadError(GuardedReadError,
    RuntimeError):`.
  - `UnsafePathSegmentError` (`src/specify_cli/core/paths.py`, currently
    `ValueError` at ~line 42) → `class UnsafePathSegmentError(GuardedReadError,
    ValueError):`. This one is load-bearing: confirm
    `isinstance(UnsafePathSegmentError(...), ValueError)` still holds and every
    `except ValueError:` site still catches it (T005 census covers this).
  - `DecisionIndexReadError` (`src/specify_cli/decisions/store.py`, currently
    `RuntimeError` at ~line 40).
  - `CorruptLanesError` + `MissingLanesError` (`src/specify_cli/lanes/
    persistence.py`, currently plain `Exception` at ~lines 34/38) — re-parent
    **both together**; research.md's census treats the pair as one coupled unit
    (many callers catch both in one tuple).
  - `AgentConfigError` (`src/specify_cli/core/agent_config.py`, currently
    `RuntimeError` at ~line 23).
  - `IntakeFileUnreadableError` (`src/specify_cli/intake/errors.py`, currently a
    subclass of the local `IntakeError` base at ~line 77) — re-parent to also
    inherit `GuardedReadError` alongside `IntakeError`; do not disturb the
    `IntakeError.code`/`detail` contract other intake callers rely on.
  - `MetaDecodeError` (`src/kernel/meta_decode.py`) — re-parent to inherit
    `GuardedReadError` too, so `decode_meta`'s callers are covered by the hook
    without any call-site change.
- **Files**: `src/specify_cli/core/paths.py`, `src/specify_cli/decisions/store.py`,
  `src/specify_cli/lanes/persistence.py`, `src/specify_cli/core/agent_config.py`,
  `src/specify_cli/intake/errors.py`, `src/kernel/meta_decode.py`.
- **Parallel?**: No — WP07 later touches reader *logic* in some of these same
  files (`core/wps_manifest.py`, `decisions/store.py`); keep this WP's edits to
  the *type hierarchy* only so WP07 does not conflict.
- **Notes**: For each re-parented error, check `__init__` signatures — if a legacy
  error's constructor doesn't already accept/store something shaped like
  `path`/`reason`, add compatible attributes without breaking its existing
  positional/keyword call sites (grep all `raise <ErrorName>(` sites first).

### Subtask T005 – `except`-site caller census + NFR-006 back-compat regression

- **Purpose**: de-risk FR-013 — prove the ~85 existing `except` sites (src + tests)
  still match after T004's re-parenting, before anything downstream relies on it.
- **Steps**: Reproduce and extend the census table in `research.md` (`## except-site
  caller census`) by grepping `src/` and `tests/` for `except.*<ErrorName>` for all
  7 legacy names (including tuple-catches like `except (CorruptLanesError,
  MissingLanesError):` and `pytest.raises(...)` sites — those ripple too). Record
  final counts. Then write `tests/specify_cli/test_error_backcompat.py`: for each
  legacy error, construct an instance and assert it is still caught by
  representative `except` clauses mirroring the real call sites (at minimum: the
  base legacy type alone, any tuple-catch combination found in the census, and — for
  `UnsafePathSegmentError` — a bare `except ValueError:`). Also assert every legacy
  error `isinstance(..., GuardedReadError)`.
- **Files**: `tests/specify_cli/test_error_backcompat.py` (new); update the census
  table in `research.md` only if you find drift from what's recorded (note any
  correction in your Activity Log — do not silently overwrite the planning record).
- **Parallel?**: No.
- **Notes**: This is the single regression that lets WP02–WP07 trust the base
  without re-verifying it themselves — be exhaustive, not representative-only, for
  the coupled `CorruptLanesError`/`MissingLanesError` pair specifically (research.md
  flags 10 sites coupling them).

### Subtask T006 – Global Typer error hook + fold bespoke emitters

- **Purpose**: FR-002/D2 — the single CLI-boundary presentation authority.
- **Steps**: Register one hook on the top-level app assembled in
  `src/specify_cli/__init__.py` (see `_assemble_app`/`main()` — `main()` currently
  calls `app = _load_bytecode_heal_invoker()(_assemble_app, ...)` then `app()`
  directly). Wrap the app invocation so a raised `GuardedReadError` (or subclass)
  is caught there: no `--json` → print `Error: <reason>` to stderr, exit 1; `--json`
  → print exactly one JSON object to stdout (`{"error", "kind", "path"}` per
  `contracts/error-envelope.md`) with nothing else on stdout, exit 1. A Typer
  *usage* error (missing arg, bad option) must keep exit 2 unchanged — never
  intercepted or converted by this hook (INV-2). Any exception that is not a
  `GuardedReadError` must re-raise/propagate so it still tracebacks (INV-3). Fold
  the shipped bespoke per-command emitters (`_emit_meta_read_error`,
  `_emit_unsafe_mission_slug_error` in `next`/`accept`/`merge`, and merge's own
  emitter) into this hook wherever doing so is behavior-preserving — grep for
  `_emit_meta_read_error` and `_emit_unsafe_mission_slug_error` across `src/` first
  and confirm what each currently prints before deleting it.
- **Files**: `src/specify_cli/__init__.py`; add the `[Unreleased]` entry to
  `docs/changelog/CHANGELOG.md` describing the whole #2899 seam (mention children
  #4746/#4738/#4724/#4637/#4739/#4720 collectively; do not itemize per-WP — later
  WPs land under the same entry).
  `tests/specify_cli/test_error_hook.py` (new).
- **Parallel?**: No.
- **Notes**: `--json` detection already has a helper (`_argv_requests_json_mode` is
  referenced near the logging bootstrap in `main()`) — reuse it rather than
  re-parsing `sys.argv`. Keep the hook's own logic under complexity 15 by
  extracting the text-vs-JSON render branch into a small helper function.

## Test Strategy

- `tests/kernel/test_guarded_read.py` — the full unit matrix from T002 (happy
  path, `OSError`, `UnicodeDecodeError`, declared-exception collapse, undeclared
  exception propagation, `mode="bytes"` parity, `__cause__` chaining, single-read
  assertion).
- `tests/specify_cli/test_error_hook.py` — hook renders a `GuardedReadError` as a
  clean text line (no `--json`) and as a single JSON object (`--json`), both exit 1;
  a Typer usage error still exits 2 through the same app invocation; a non-domain
  exception still propagates as a traceback (invoke via a throwaway command wired
  into a test-only Typer sub-app, or via the real app if a suitable command already
  raises a controllable error).
- `tests/specify_cli/test_error_backcompat.py` — the NFR-006 regression from T005.
- Run this WP's own new/changed test files, plus `make test-fast`, plus the full
  test directories that own the touched subsystems: `tests/kernel/`,
  `tests/specify_cli/` (targeted to the touched modules — `core/paths`,
  `decisions/store`, `lanes/persistence`, `core/agent_config`, `intake`), and
  `tests/status/` if any status-layer tuple-catch is touched by the census.
- Typecheck: `uv run --frozen mypy -p kernel -p specify_cli` (or the project's
  configured mypy invocation) over every file this WP owns — a passing pytest run
  does not replace a clean mypy run.
- `ruff check .` and `ruff format --check .` over the whole repo before handing off
  (formatting is a separate gate from linting per `CLAUDE.md`).

## Risks & Mitigations

- **Kernel dependency floor**: it is tempting to reach for a schema library inside
  `read_guarded` for convenience — don't. Keep all decode/schema knowledge in the
  caller layer (D1); verify with `tests/architectural/test_layer_rules.py`.
- **`UnsafePathSegmentError` MRO break**: multiple inheritance ordering matters —
  put `GuardedReadError` first only if it doesn't shadow `ValueError`'s
  `args`/`__str__` in a way that breaks existing `str(exc)` call sites; write a
  targeted MRO/`isinstance` test rather than assuming it works.
- **`__init__.py` edit ⇒ version bump + CHANGELOG**: required by `CLAUDE.md`'s
  "Any changes to `__init__.py` require a version bump in `pyproject.toml` and a
  `CHANGELOG.md` entry." Add the CHANGELOG entry now; **do not pick the version
  number** — call this out explicitly in your Activity Log and PR notes so the PO
  can decide the number.
- **Census incompleteness**: a missed `except` site becomes a silent regression
  three WPs downstream, with no attribution back to this WP. Be exhaustive on the
  grep, not sample-based.
- **Emitter-fold regressions**: folding `_emit_meta_read_error`/
  `_emit_unsafe_mission_slug_error` into the hook can silently drop a
  distinguishing detail (e.g. a command-specific hint). Diff old vs. new printed
  output for each folded emitter, don't just delete-and-trust.

## Review Guidance

- Confirm `read_guarded()` matches `contracts/guarded-read-primitive.md` exactly —
  signature, the always-covered `(OSError, UnicodeDecodeError)` pair, chained
  `raise … from exc`, and the non-goals (no schema knowledge, not a string
  validator).
- Confirm the hook matches `contracts/error-envelope.md` exactly — the four-row
  behavior table and all four invariants (INV-1..INV-4), especially that Typer
  usage errors are never touched (exit 2 preserved).
- Confirm every legacy error still satisfies its pre-existing `isinstance` contract
  (`UnsafePathSegmentError` as `ValueError` above all) and that
  `test_error_backcompat.py` actually exercises tuple-catch sites, not just the
  bare type.
- Confirm the CHANGELOG entry exists and no version number was invented.
- If typed sources changed, confirm the implementer ran the configured mypy check
  in addition to pytest and that mypy diagnostics passed.

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
