---
work_package_id: WP01
title: Feedback Domain Core — Models, Preferences, Offer Eligibility
dependencies: []
requirement_refs:
- C-005
- C-006
- FR-011
- FR-013
- FR-018
- NFR-003
- NFR-005
- NFR-007
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: 78483af356ca88d98d38fefce7ef190da9957a32
created_at: '2026-09-30T08:56:41.041683+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Foundation
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/
create_intent:
- src/specify_cli/feedback/__init__.py
- src/specify_cli/feedback/models.py
- src/specify_cli/feedback/preferences.py
- src/specify_cli/feedback/eligibility.py
- tests/specify_cli/feedback/__init__.py
- tests/specify_cli/feedback/conftest.py
- tests/specify_cli/feedback/test_models.py
- tests/specify_cli/feedback/test_preferences.py
- tests/specify_cli/feedback/test_eligibility.py
- tests/specify_cli/feedback/acceptance/__init__.py
- tests/specify_cli/feedback/acceptance/test_offer_rules.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/__init__.py
- src/specify_cli/feedback/models.py
- src/specify_cli/feedback/preferences.py
- src/specify_cli/feedback/eligibility.py
- tests/specify_cli/feedback/__init__.py
- tests/specify_cli/feedback/conftest.py
- tests/specify_cli/feedback/test_models.py
- tests/specify_cli/feedback/test_preferences.py
- tests/specify_cli/feedback/test_eligibility.py
- tests/specify_cli/feedback/acceptance/__init__.py
- tests/specify_cli/feedback/acceptance/test_offer_rules.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Feedback Domain Core — Models, Preferences, Offer Eligibility

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `cursor`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for `task_type: implement` on `src/specify_cli/feedback/`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
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

Create the `specify_cli.feedback` bounded context's foundation. When this WP is done:

- `specify_cli.feedback` exists as a package with a declared `__all__`.
- Value types from `data-model.md` exist and cannot be constructed in an invalid state (for example, a `Rating` outside 1–5).
- `feedback.json` is read and written with the hardening described below, in the per-user **config** directory, never in a project repository (C-006).
- One pure function, `decide_offer()`, answers "may an automatic survey be offered now?" for any combination of inputs, returning an `OfferDecision` with a machine-readable `reason`.
- One transactional function, `claim_offer()`, performs check-and-mark atomically under a **non-blocking** machine-wide lock, so two concurrent processes can never both get `prompt` inside the same 7-day window (NFR-005).
- The eligibility check does no network I/O and completes well under 100 ms (NFR-003).
- mypy `--strict`, ruff, and `ruff format --check` are clean on every file you own; coverage of new code ≥ 90%.

## Context & Constraints

Read before coding:

- `kitty-specs/in-harness-feedback-survey-01M3PK9W/spec.md` — FR-011, FR-013, FR-018, NFR-003, NFR-005, C-005, C-006, and the Edge Cases section.
- `kitty-specs/in-harness-feedback-survey-01M3PK9W/plan.md` — Key Design Decisions 3 and 6; IC-01.
- `kitty-specs/in-harness-feedback-survey-01M3PK9W/data-model.md` — the authoritative field lists, invariants, and state transitions.
- `kitty-specs/in-harness-feedback-survey-01M3PK9W/research.md` — R-04 (storage) and R-07 (what counts as "shown").
- `.kittify/charter/charter.md` — ATDD-first (C-011), single canonical authority, Sonar expectations (complexity ≤ 15).

Existing primitives you **must reuse** (do not re-implement or copy):

| Need | Use |
|---|---|
| Symlink-safe read | `kernel.no_follow.read_text_no_follow` / `kernel.guarded_read.read_guarded` |
| Atomic replace | `kernel.atomic.atomic_write(path, content, mkdir=True)` |
| Permission fix-up | `kernel.no_follow.chmod_no_follow` |
| Machine-wide lock | `kernel.locks.machine_file_lock(lock_path, blocking=False)` → raises `LockNotAcquired` on contention |
| Clock | `kernel.clock` (`UTC`, `datetime`, `parse_iso`) — follow how `specify_cli/compat/cache.py` uses it |
| Config dir | `platformdirs.user_config_dir("spec-kitty")`, with the same OS fallback as `specify_cli/compat/config.py::_resolve_config_dir` (reuse that helper if importable without a cycle; otherwise extract it, never duplicate) |

`kernel/locks.py` is the enforced single authority for OS-level locks; a raw `fcntl`/`msvcrt` call anywhere else fails an architectural gate.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; enter yours with `spec-kitty agent action implement WP01 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first acceptance tests for offer rules

- **Purpose**: Pin the user-observable throttle and opt-out behaviour before any implementation (charter C-011). Commit these tests **as a separate first commit**; they must fail (ImportError or assertion) on the planning base.
- **Steps**:
  1. Create `tests/specify_cli/feedback/acceptance/test_offer_rules.py` (and empty `__init__.py` files as needed; mirror neighbouring test packages).
  2. Use a `tmp_path`-backed preferences location. Add a fixture in `tests/specify_cli/feedback/conftest.py` that monkeypatches the config-dir resolver so no test ever touches the real user profile.
  3. Write scenarios straight from spec US2, driving only `claim_offer()`:
     - First automatic trigger with an endpoint present, interactive, not CI → `prompt` / `eligible`, and `last_shown_at` is now set.
     - Second automatic trigger 6 days 23 hours later → `none` / `throttled`. **Positive control on the same fixture**: at exactly 7 days → `prompt`.
     - After `set_automatic_prompts(False)` → `none` / `prompts_off`; after `set_automatic_prompts(True)` and 7+ days → `prompt`.
     - Non-interactive → `none` / `non_interactive`, and `last_shown_at` is **unchanged** (window not consumed).
     - CI → `none` / `ci`.
     - No endpoint → `none` / `no_endpoint`.
     - `on_demand` → `prompt` even when throttled or prompts are off, and it never writes `last_shown_at`.
- **Files**: `tests/specify_cli/feedback/acceptance/test_offer_rules.py`, `tests/specify_cli/feedback/conftest.py`
- **Parallel?**: No — this is the first commit.
- **Notes**: Inject `now` everywhere; never call the real clock in assertions.

### Subtask T002 – Value types in `feedback/models.py`

- **Purpose**: One home for the domain vocabulary so every later WP speaks the same types.
- **Steps**:
  1. `SurveyTrigger(StrEnum)`: `planning_complete`, `mission_end`, `op_close`, `on_demand`. Add a property or helper `is_automatic` (False only for `on_demand`).
  2. `Rating`: frozen dataclass or `NewType`-plus-constructor that raises `ValueError` outside 1–5. Prefer a frozen dataclass with `__post_init__` validation and an `int` accessor.
  3. `SurveyAnswers`: frozen dataclass `rating: Rating`, `comment: str | None`, `email: str | None`. Keep validation of comment and email **out** of this module (WP03 owns input validation); this type only holds already-validated values.
  4. `Harness`: a small allowlist type. Store as `str`, but construct only through a `normalize_harness(value)` helper that returns `"cli"`, a known agent key, or `"other"`. Source known agent keys from `specify_cli.agent_utils.directories` (`AGENT_DIR_TO_KEY` values), not a hand-written list.
  5. `OfferReason(StrEnum)`: exactly the reasons in `contracts/agent-check.schema.json` (`eligible`, `no_endpoint`, `prompts_off`, `throttled`, `non_interactive`, `ci`, `preferences_unreadable`, `clock_skew`, `lock_busy`, `trigger_not_eligible`).
  6. `OfferDecision`: frozen dataclass `action: Literal["prompt","none"]`, `reason: OfferReason`, `trigger: SurveyTrigger`.
  7. `__init__.py`: module docstring naming the bounded context and the canonical terms (Feedback Survey, Feedback Submission); `__all__` exports the model names only. Later WPs import their own modules by path, so they never need to edit `__init__.py`.
- **Files**: `src/specify_cli/feedback/__init__.py`, `src/specify_cli/feedback/models.py`
- **Parallel?**: Yes, with T003/T004.
- **Notes**: Do not use the word "telemetry" anywhere (C-001).

### Subtask T003 – Hardened preferences read

- **Purpose**: Read `feedback.json` safely and fail toward silence.
- **Steps**:
  1. `SurveyPreferences` frozen dataclass: `schema_version: int = 1`, `automatic_prompts: bool = True`, `last_shown_at: datetime | None = None`, `endpoint_override: str | None = None`. Add `to_dict()` / `from_dict()` with strict type checks (mirror the style of `NagCacheRecord.from_dict` in `specify_cli/compat/cache.py`).
  2. `preferences_path() -> Path`: `<user_config_dir>/feedback.json`; make the directory resolver injectable for tests.
  3. `load_preferences(path) -> SurveyPreferences | Unreadable` where `Unreadable` is a sentinel (a distinct singleton or a small dataclass carrying a reason string for `--status`).
     - File missing → defaults (not `Unreadable`).
     - Symlink at the file or parent → `Unreadable`.
     - Larger than 64 KiB → `Unreadable`.
     - POSIX only: owner ≠ current euid, or mode ≠ 0600 → `Unreadable`.
     - Invalid JSON, wrong types, or `schema_version` > 1 → `Unreadable`.
  4. Never raise to the caller; never log answers (there are none here, but keep the habit); debug-level logs only.
- **Files**: `src/specify_cli/feedback/preferences.py`
- **Notes**: Missing file = defaults is what makes the first-ever offer possible. Corrupt = unreadable is what makes the system fail quiet.

### Subtask T004 – Hardened preferences write + `set_automatic_prompts()`

- **Purpose**: Persist state atomically with owner-only permissions.
- **Steps**:
  1. `save_preferences(path, prefs) -> bool`: ensure the parent exists with mode 0700; refuse if the parent or target is a symlink; `atomic_write(path, json.dumps(prefs.to_dict(), sort_keys=True), mkdir=True)`; then `chmod_no_follow(path, 0o600)` (best effort on Windows). Return `False` on any `OSError` (never raise).
  2. `set_automatic_prompts(enabled: bool, *, path=None, now=None) -> bool`: read-modify-write under the same machine lock as T006 (blocking with a short timeout, e.g. `timeout_s=2`, is acceptable here because this is an explicit user action, not a trigger). If current preferences are `Unreadable`, overwrite them with fresh defaults plus the requested flag (an explicit user action repairs a corrupt file).
  3. Lock file path: `<config_dir>/feedback.lock` (next to `feedback.json`).
- **Files**: `src/specify_cli/feedback/preferences.py`
- **Notes**: Document in the docstring that `atomic_write` creates the temp file with default permissions before the chmod. The file holds no personal data, so this brief window is acceptable; state that rationale in the docstring.

### Subtask T005 – Pure `decide_offer()`

- **Purpose**: A single, table-testable decision with no I/O.
- **Signature** (keyword-only):

```python
def decide_offer(
    *,
    trigger: SurveyTrigger,
    prefs: SurveyPreferences | Unreadable,
    now: datetime,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
) -> OfferDecision: ...
```

- **Order of checks** (first match wins; keep this order so `reason` values are stable):
  1. `not endpoint_available` → `no_endpoint`
  2. `trigger == on_demand` → `prompt` / `eligible` (bypasses everything below)
  3. `ci` → `ci`
  4. `not interactive` → `non_interactive`
  5. `prefs is Unreadable` → `preferences_unreadable`
  6. `not prefs.automatic_prompts` → `prompts_off`
  7. `prefs.last_shown_at` in the future → `clock_skew`
  8. `last_shown_at` set and `now - last_shown_at < 7 days` → `throttled`
  9. otherwise → `prompt` / `eligible`
- **Constant**: `THROTTLE_WINDOW = timedelta(days=7)` at module level.
- **Files**: `src/specify_cli/feedback/eligibility.py`
- **Notes**: Keep cyclomatic complexity ≤ 15. A flat guard-clause chain is fine.

### Subtask T006 – `claim_offer()` locked transaction

- **Purpose**: Make check-and-mark atomic across processes (NFR-005, R-07).
- **Signature**:

```python
def claim_offer(
    trigger: SurveyTrigger,
    *,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
    now: datetime | None = None,
    path: Path | None = None,
) -> OfferDecision: ...
```

- **Steps**:
  1. `on_demand`: call `decide_offer` without the lock and without writing; return.
  2. Otherwise acquire `machine_file_lock(lock_path, blocking=False)`. On `LockNotAcquired` (or any lock error) → `OfferDecision("none", lock_busy, trigger)`.
  3. Inside the lock: load preferences, call `decide_offer`, and if the action is `prompt`, write `last_shown_at = now` via `save_preferences`. If the save fails, return `none` / `preferences_unreadable` so a prompt is never shown without the mark.
  4. Never raise; wrap unexpected exceptions into `none` / `preferences_unreadable` and log at debug.
- **Files**: `src/specify_cli/feedback/eligibility.py`
- **Notes**: This is the function WP04 (agent-check) and WP06 (inline hooks) call. Keep the signature exactly as above.

### Subtask T007 – Unit tests

- **Purpose**: Cover every branch (Sonar new-code coverage) with focused tests.
- **Steps**:
  - `test_models.py`: Rating bounds (0, 1, 5, 6, bool rejected), `normalize_harness` (known key, `cli`, unknown → `other`, empty → `other`), `SurveyTrigger.is_automatic`.
  - `test_preferences.py`: missing file → defaults; round-trip; symlinked file; symlinked parent; oversize; bad JSON; wrong types; future `schema_version`; POSIX foreign owner and wrong mode (use `pytest.mark.skipif(sys.platform == "win32")`); save sets mode 0600 on POSIX; `set_automatic_prompts` repairs an unreadable file.
  - `test_eligibility.py`: one parametrized table covering every row of the T005 order, including boundary `exactly 7 days`; `claim_offer` writes on prompt and not on none; `on_demand` never writes; lock contention → `lock_busy` (hold the lock in the test with `machine_file_lock` in the same process if reentrancy allows, otherwise spawn a helper process that holds it). Also include a two-process race test: start two `multiprocessing` workers calling `claim_offer` concurrently against the same `tmp_path` and assert exactly one `prompt`.
- **Files**: the three unit test files above.
- **Notes**: Mark tests `fast`/`unit` per repository markers (see neighbouring tests). The two-process test may need the `timing` or `stress` marker if it is slow; check `pytest.ini` markers and follow them.

## Test Strategy

Run (from your lane worktree):

```bash
uv run --frozen pytest tests/specify_cli/feedback -q
uv run --frozen mypy --strict src/specify_cli/feedback
uv run --frozen ruff check src/specify_cli/feedback tests/specify_cli/feedback
uv run --frozen ruff format --check src/specify_cli/feedback tests/specify_cli/feedback
uv run --frozen pytest tests/architectural/test_layer_rules.py -q   # import direction stays kernel <- ... <- specify_cli
```

Then the shared baseline: `make test-fast`. Record commands and pass/fail counts in the Activity Log. Do **not** run `make test-full` or the whole `tests/architectural/` directory (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **A raw OS lock sneaks in** → architectural gate failure. Only `kernel.locks` may lock.
- **The real user config dir is touched in tests** → always go through the conftest fixture; add an assertion in the fixture that the resolved path is under `tmp_path`.
- **The race test is flaky** → fix at the root (for example, a barrier to start both workers together); never retry-to-green.

## Review Guidance

- Verify T001 was committed first and was red on the planning base (charter C-011).
- Verify no module other than `kernel.locks` performs OS-level locking and that no `NagCache` private helper was copied.
- Verify the reason order in `decide_offer` matches this prompt and the agent-check contract enum.
- Verify mypy `--strict`, ruff, and format checks were run on owned files, not just pytest.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last). Append at the end using `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC from `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-30T07:59:37Z – system – Prompt created.
