---
work_package_id: WP02
title: Route the three families, and gate the fourth copy
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
planning_base_branch: issue-6727-anchor-lock-paths
merge_target_branch: issue-6727-anchor-lock-paths
branch_strategy: Planning artifacts for this mission were generated on issue-6727-anchor-lock-paths. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6727-anchor-lock-paths unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Routing and the gate
history:
- at: '2026-10-30T17:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/architectural/test_anchor_lock_path_single_owner.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/event_log_append.py
- src/charter/activation/synthesizer/synthesis_lock.py
- src/specify_cli/status/locking.py
- tests/architectural/test_anchor_lock_path_single_owner.py
- docs/architecture/event-ledger-writers-and-readers.md
- docs/development/reference/lock-interop-spike.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Route the three families, and gate the fourth copy

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

- FR-002 / FR-003 / FR-004: `event_log_lock_path`, `synthesis_lock_path` and
  `_checkout_claim_lock_path` call `kernel.locks.anchored_lock_path` and produce **byte-identical**
  paths, keep their own non-git fallback and keep their own git-unavailable behaviour.
- FR-006: a new architectural gate fails when a module under `src/` other than `kernel/locks.py`
  both names a file under `LOCK_DIRECTORY` and derives a digest from a path.
- FR-007: the docstrings name the single owner, and the two status lock builders that are not
  anchor-keyed say why they do not use it.
- FR-008: the two doc pages that state the contract name `kernel.locks.anchored_lock_path` as its
  one implementation.

Done when:
- The four family suites are green **with zero edits**, i.e. you did not change one assertion in
  `tests/kernel/test_event_log_append.py`, `tests/charter/synthesizer/test_synthesis_lock.py`,
  `tests/status/test_checkout_claim_lock.py`, `tests/status/test_journal_lock_unification.py`
  (baseline before this Mission: 66 passed, 2 skipped).
- `uv run pytest tests/architectural/test_anchor_lock_path_single_owner.py tests/architectural/test_no_dead_symbols.py -q`
  is green, and the new gate was red before T007–T009 (it names all three copies).
- `uv run mypy src/kernel/event_log_append.py src/charter/activation/synthesizer/synthesis_lock.py src/specify_cli/status/locking.py`
  is clean, and ruff check/format is clean on every touched file.

## Context & Constraints

- Read `../spec.md`, `../plan.md` ("IC-02"), `../data-model.md` (the shape table) and
  `../research.md` (D2, D3, D4).
- **Lock names are frozen** (C-001): the event-log golden digest
  `5d011f83a018c89fa185a10c696c8293` and the `__checkout-<sha1[:16]>__.status.lock` name.
  `specify_cli.status.locking._is_checkout_claim_lock_key` pattern-matches that **name**, so the
  prefix/suffix must be exactly `__checkout-` and `__.status.lock`.
- **Fallbacks stay in the families** (C-003): the helper propagates `NotAGitRepositoryError` and
  `GitTopologyUnavailableError`; each family keeps its own `except` clauses and its own error
  type. Do not push a callback into the helper.
- **Blast radius** (C-002): only the six files in `owned_files`. `feature_status_lock_path`,
  `project_event_log_lock`, `review/verdict_commit_queue.py` and `design/receipts.py` keep their
  current construction.
- No changelog entry (C-005): no user-visible behaviour changes.
- Terminology: "anchor", "lock family", "common dir", "Mission". Never "feature".

## Branch Strategy

Planning branch `issue-6727-anchor-lock-paths`, final merge target the same branch. Topology is
`coord`; this WP depends on WP01, so claim it through the runtime after WP01 is done. Commit on
the lane branch the runtime gives you. Never push, never merge, never touch `main`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first no-fourth-copy gate

Create `tests/architectural/test_anchor_lock_path_single_owner.py`. Follow the style of the
existing gates in `tests/architectural/` (module docstring saying what defect class it closes,
a `_scan` helper, and a non-vacuity section). Requirements:
- Walk `src/**/*.py`. Skip `src/kernel/locks.py`.
- For each file, read the text. A file is a **copy** when it references `LOCK_DIRECTORY` (or the
  literal `"spec-kitty-locks"`) **and** derives a digest from a path — detect that by any of:
  a `hashlib.` attribute call, an import of `kernel.content_digest`/`sha256_digest`, or a call to
  a name matching `.*digest.*`. Report `path:line` for the offending line, not just the file.
- Fixed-name lock files must pass: `src/specify_cli/review/verdict_commit_queue.py` and
  `src/specify_cli/design/receipts.py` name files under `LOCK_DIRECTORY` but digest nothing.
  Assert that explicitly (a positive control), so the gate is not vacuously green.
- Non-vacuity: assert the scan flags a synthetic snippet (a tmp `src`-shaped file with
  `LOCK_DIRECTORY` + `hashlib.sha256(...)`) and does not flag a snippet with only
  `LOCK_DIRECTORY`. If you prefer, run the scan over a `tmp_path` fixture directory through the
  same helper rather than monkeypatching the repo root.
- Run it on the base and record the failure (three modules named).

### Subtask T007 – `event_log_lock_path`

Replace the inline body with:

```python
resolved = anchor.resolve()
try:
    return anchored_lock_path(resolved, probe_dir=resolved.parent, subdirectory=EVENT_LOG_LOCK_SUBDIRECTORY)
except NotAGitRepositoryError:
    return resolved.with_name(resolved.name + NON_GIT_LOCK_SUFFIX)
except GitTopologyUnavailableError as exc:
    raise EventLogLockUnavailableError(...) from exc
```

Keep the error message text character-for-character (a test matches
`Error code: EVENT_LOG_LOCK_UNAVAILABLE\.$`). Drop the now-unused imports (`os`,
`sha256_digest`, `git_common_dir`) only if nothing else in the module uses them — check first:
`os` is used elsewhere in the module. Update the module docstring bullet 1 to say the rule is
implemented once in `kernel.locks.anchored_lock_path` and that this function adds the
non-git sibling fallback and the refusal.

### Subtask T008 – `synthesis_lock_path`

Same shape: `anchored_lock_path(resolved, subdirectory=_SYNTHESIS_LOCK_SUBDIRECTORY)`, keeping the
`SynthesisLockUnavailableError` refusal and the `_NON_GIT_LOCK_PATH` fallback, and deleting
`_DIGEST_LENGTH` / `_DIGEST_PREFIX` if they become unused (check with grep). Update the module
docstring's placement section to point at the helper.

### Subtask T009 – `_checkout_claim_lock_path`

The status family's probe **degrades** instead of raising, so pass the common dir it resolved:

```python
def _checkout_claim_lock_path(write_checkout: Path) -> Path:
    return anchored_lock_path(
        write_checkout,
        common_dir=_git_common_dir(write_checkout),
        prefix=_CHECKOUT_LOCK_PREFIX,
        suffix=_CHECKOUT_LOCK_SUFFIX + _STATUS_LOCK_SUFFIX,
        digest_algorithm="sha1",
        digest_hex_length=_CHECKOUT_DIGEST_LENGTH,
    )
```

Remove the now-unused `hashlib`/`os` imports if nothing else in `locking.py` uses them (grep
first: `os` is used for `os.getpid()`; `hashlib` may become unused). The result must equal the
literal name in `tests/status/test_checkout_claim_lock.py`
(`__checkout-<sha1[:16]>__.status.lock`) with no test edit.

### Subtask T010 – Docstrings for the non-anchor-keyed status locks

In `specify_cli/status/locking.py`, extend the docstrings of `feature_status_lock_path` and
`project_event_log_lock` with one sentence each: they are not anchor-keyed (one is keyed by the
Mission directory name, the other by a fixed sentinel), so they join the lock directory directly;
`kernel.locks.anchored_lock_path` owns the anchor-digest rule. Same for `_git_common_dir` if a
sentence helps a reader understand it is the *degrading* resolver the claim lock feeds into the
helper.

### Subtask T011 – Docs name the owner

- `docs/architecture/event-ledger-writers-and-readers.md` (the "One interim lock for every other
  event log (#6606)" bullet): after the path, add one clause saying the anchor digest and the
  `<git-common-dir>/spec-kitty-locks` placement are computed once, by
  `kernel.locks.anchored_lock_path`, and that this module adds the event-log subdirectory and the
  sibling fallback.
- `docs/development/reference/lock-interop-spike.md` ("Lock path" bullet): name
  `kernel.locks.anchored_lock_path` as the one implementation whose output a Java peer must
  reproduce. Do **not** change the contract wording (`sha256` of
  `os.path.normcase(resolved anchor path)`, UTF-8, first 32 hex, `event-logs` subdirectory, the
  `<anchor>.event-log.lock` fallback) — only add the owner.
- Both pages carry frontmatter; do not touch `updated:`/`doc_status:` unless the repository's
  docs-freshness script requires it (it is not run for these two pages; if
  `uv run python -m scripts.docs.check_docs_freshness --ci` complains about them, report it
  rather than guessing).

## Test Strategy

Red first (T006). Then, in this order:
1. `uv run pytest tests/architectural/test_anchor_lock_path_single_owner.py -q` (green after routing).
2. `uv run pytest tests/kernel/test_event_log_append.py tests/charter/synthesizer/test_synthesis_lock.py tests/status/test_checkout_claim_lock.py tests/status/test_journal_lock_unification.py -q` — the unchanged suites (≥66 passed, 2 skipped).
3. `uv run pytest tests/kernel/test_lock_paths.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_lock_primitive_ban.py -q`.
4. `uv run pytest tests/core/test_event_log_retention.py tests/specify_cli/cli/commands/test_implement_claim_concurrency.py tests/status/test_concurrent_mission_writers.py -q` — the consumers of these paths.
Record commands and counts in the Activity Log.

## Risks & Mitigations

- The status family starts raising. Mitigation: it passes `common_dir=`, so no probe happens; the
  existing degrade tests stay untouched and green.
- A dropped import breaks a module-level name another test patches. Mitigation: grep each import
  before removing it, and run the four family suites plus the consumer suites.
- The gate fires on the fixed-name lock files. Mitigation: the positive-control assertions in T006.

## Review Guidance

Reviewer: check each family's diff line by line against the pre-change body — the only permitted
differences are (a) the digest/join delegation, (b) the removal of the duplicated expression and
its imports, (c) docstring text. Any change to a fallback path, an error type, a message, a
prefix or a suffix is a defect. Confirm the four family suites are untouched (`git diff --stat`
shows no test edits) and that the gate's positive and negative controls both exist.

## Activity Log

- 2026-10-30T17:52:00Z – system – Prompt created.
