---
work_package_id: WP01
title: The helper and its pinned contract
dependencies: []
requirement_refs:
- FR-001
- FR-005
- NFR-003
- NFR-004
planning_base_branch: issue-6727-anchor-lock-paths
merge_target_branch: issue-6727-anchor-lock-paths
branch_strategy: Planning artifacts for this mission were generated on issue-6727-anchor-lock-paths. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6727-anchor-lock-paths unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - The helper
history:
- at: '2026-10-30T17:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- tests/kernel/test_lock_paths.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/locks.py
- tests/kernel/test_lock_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The helper and its pinned contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

- FR-001: `kernel.locks.anchored_lock_path` is the one implementation of "resolve the anchor →
  `os.path.normcase` → digest → `<common dir>/spec-kitty-locks[/<subdir>]/<prefix><digest><suffix>`",
  exported from `__all__`, documented with a docstring that states the rule, the parameters and
  the two exceptions it propagates.
- FR-005: `tests/kernel/test_lock_paths.py` pins the contract **by value** for the three shapes
  that exist in `src/` (event-log, charter synthesis, Mission checkout claim), plus the
  parameter validation, the no-probe fast path and the probe directory. The expected digests are
  computed independently in the test (literal `hashlib` expression), never by calling the helper.

Done when:
- `uv run pytest tests/kernel/test_lock_paths.py -q` is green, and was **red before** T002
  (`ImportError: cannot import name 'anchored_lock_path'`).
- `uv run python -c "from kernel.locks import anchored_lock_path"` works, and the symbol is in
  `kernel.locks.__all__` (the `tests/architectural/test_no_dead_symbols.py` gate walks `__all__`;
  WP02 supplies the `src/` callers, so run that gate at the end of WP02, not here).
- `uv run mypy src/kernel/locks.py` is clean; `uv run ruff check src/kernel/locks.py tests/kernel/test_lock_paths.py` and
  `uv run ruff format --check src/kernel/locks.py tests/kernel/test_lock_paths.py` are clean.

## Context & Constraints

- Read `../spec.md` (FR-001, FR-005, NFR-003, NFR-004, C-001), `../plan.md` ("IC-01"),
  `../data-model.md` (the three shapes and the invariants) and `../research.md` (D2, D3).
- Read `src/kernel/locks.py` first: `LOCK_DIRECTORY` already lives there with a docstring naming
  the lock families. Put `anchored_lock_path` in its own clearly separated section
  (`# --- Lock paths ---` style) so the G1-G7 primitive contract above stays readable.
- Import `git_common_dir`, `GitTopologyUnavailableError`, `NotAGitRepositoryError` from
  `kernel.git_topology`. That is an intra-kernel edge and is allowed (NFR-004); do **not** import
  `charter` or `specify_cli` (the kernel is the lowest tier).
- You are **not** rewiring the callers in this WP. Copy the exact expressions from them so the
  shared rule is provably the same one; the callers move in WP02.
- No new third-party dependency. Kernel stays stdlib + intra-kernel (C-001 in the charter's
  kernel rule, NFR-004 here).
- Terminology: "anchor", "lock family", "common dir", "Mission". Never "feature".

## Branch Strategy

Planning branch `issue-6727-anchor-lock-paths`, final merge target the same branch. Topology is
`coord`; run the implement action for the workspace the runtime gives you and commit on that
lane's branch. Never push, never merge, never touch `main`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first contract tests

Create `tests/kernel/test_lock_paths.py` (`pytestmark = pytest.mark.unit`). Write the tests
before the helper exists and run them to see them fail on the missing symbol. Cover:
- **event-log shape**: `anchored_lock_path(anchor, probe_dir=anchor.parent, subdirectory="event-logs")`
  equals `<common>/spec-kitty-locks/event-logs/<sha256[:32] of normcase(resolved anchor)>.lock`.
  Use the same golden anchor and digest as `tests/kernel/test_event_log_append.py`'s
  `test_lock_path_digest_golden_value` (`Path("/srv/repo/kitty-specs/m/decisions.events.jsonl")` →
  `5d011f83a018c89fa185a10c696c8293`), so the two tests agree by value, not by construction.
  Skip it on non-POSIX with the same `reason` that test uses.
- **charter synthesis shape**: `anchored_lock_path(root, subdirectory="charter-synthesis")`
  equals `<common>/spec-kitty-locks/charter-synthesis/<sha256[:32]>.lock`.
- **checkout-claim shape**: `anchored_lock_path(checkout, prefix="__checkout-", suffix="__.status.lock", digest_algorithm="sha1", digest_hex_length=16, common_dir=checkout / ".git")`
  equals `checkout / ".git" / "spec-kitty-locks" / f"__checkout-{sha1[:16]}__.status.lock"`,
  computed with `hashlib.sha1(os.path.normcase(str(checkout.resolve())).encode("utf-8"), usedforsecurity=False)`
  — the same expression `tests/status/test_checkout_claim_lock.py` already uses.
- **no probe with an explicit common dir**: monkeypatch `kernel.locks.git_common_dir` (import it
  into the module namespace so it is patchable) to raise
  `GitTopologyUnavailableError(path, "git missing")`, and assert the checkout-claim shape still
  returns its path.
- **the probe directory is what is probed**: monkeypatch `kernel.locks.git_common_dir` with a
  recorder and assert it received the *parent* for a file anchor, and the anchor itself when
  `probe_dir` is omitted.
- **a not-a-repository anchor propagates**: monkeypatch to raise `NotAGitRepositoryError` and
  assert the helper raises it (it must not fall back — the families own their fallbacks).

### Subtask T002 – `anchored_lock_path`

```python
def anchored_lock_path(
    anchor: Path,
    *,
    common_dir: Path | None = None,
    probe_dir: Path | None = None,
    subdirectory: str | None = None,
    prefix: str = "",
    suffix: str = ".lock",
    digest_algorithm: str = "sha256",
    digest_hex_length: int = 32,
) -> Path:
```

Behaviour, in this order:
1. `resolved = anchor.resolve()` (resolve once; every later step uses `resolved`).
2. `digest = _anchor_digest(resolved, algorithm=digest_algorithm, hex_length=digest_hex_length)`
   where `_anchor_digest` is a private helper computing
   `hashlib.<algorithm>(os.path.normcase(str(resolved)).encode("utf-8"), ...).hexdigest()[:hex_length]`.
   For sha1 pass `usedforsecurity=False` (the existing status code does; it is a file-name
   discriminator, not a security primitive). Do not use `kernel.content_digest.sha256_digest`:
   this digest drops the `sha256:` prefix and truncates, so a raw `hashlib` call with a
   `# noqa: TID251` line and a one-line justification is the honest form (mirror
   `specify_cli/status/locking.py`'s existing sha1 call style).
3. `root = common_dir if common_dir is not None else git_common_dir(resolved if probe_dir is None else probe_dir)`.
   `probe_dir` is passed through as given. It exists because the event-log anchor is a file that
   may not exist yet: `kernel.git_topology._probe_dir` only normalises an *existing* file, so a
   non-existent log path must be probed from its parent.
4. `locks_directory = Path(root) / LOCK_DIRECTORY`
5. `Path(locks_directory, *([subdirectory] if subdirectory else []), f"{prefix}{digest}{suffix}")`.
   Build it without `str` concatenation of paths and without normalising anything further: the
   returned path must be byte-identical to what the three copies return today.

Docstring: state the rule, that it raises `NotAGitRepositoryError` /
`GitTopologyUnavailableError` from the probe and never falls back or writes, that `common_dir`
skips the probe (a caller that degrades), and that `probe_dir` defaults to the resolved anchor.
Add `"anchored_lock_path"` to `__all__` in alphabetical position.

### Subtask T003 – Validation tests

- An unknown `digest_algorithm` (for example `"md5"` and `"not-a-hash"`) raises `ValueError`
  with a message naming the algorithm. Implement with an explicit allowlist of
  `{"sha256", "sha1"}` — the two families that exist — rather than trusting `hashlib.new`, and
  raise a clear `ValueError`. Justify in the docstring: the helper refuses to mint a name it
  cannot reproduce, and an allowlist keeps the algorithm set small and reviewable.
- `digest_hex_length` outside `1..64` raises `ValueError` (0, -1, 65). Keep the bound as named
  module constants, not magic numbers.

### Subtask T004 – Fast path and probe tests

Already listed under T001; implement them here if T001 only carried the shape assertions. Make
sure the "no probe" test is non-vacuous: assert the patched function raises when called, so the
test would fail if the helper probed.

### Subtask T005 – Cross-family parity

One test: for one directory anchor inside a real `git init` repository, the
`event-logs`-shaped and `charter-synthesis`-shaped paths have the same file stem (digest) and
differ only in `parent.name`. This is the invariant that catches a caller (or the helper) that
normalises the anchor differently for one family.

## Test Strategy

Red first. Then `uv run pytest tests/kernel/test_lock_paths.py -q`, and the untouched family
suite as a sanity check that the helper's expressions match:
`uv run pytest tests/kernel/test_event_log_append.py -q`. Record the exact red output (the
ImportError) and the final counts in the Activity Log.

## Risks & Mitigations

- A signature knob that no caller uses. Mitigation: every parameter here is used by WP02's three
  call sites; do not add a fourth without a caller.
- Accidentally changing the digest input (for example normcasing before resolving, or encoding
  the `Path` instead of its `str`). Mitigation: the literal golden digest test.
- Importing the helper into `kernel.locks`' module namespace for patching: use
  `from kernel.git_topology import git_common_dir` so `monkeypatch.setattr(kernel.locks, "git_common_dir", ...)`
  works, and say so in the test.

## Review Guidance

Reviewer: compare the helper's expressions line by line with the three copies in
`kernel/event_log_append.py:154-171`, `charter/activation/synthesizer/synthesis_lock.py:82-96`
and `specify_cli/status/locking.py:362-366`. The helper must reproduce all three exactly. Check
that the tests compute their expectations independently, that the "no probe" test cannot pass
vacuously, and that `__all__` and the docstring obey the charter's conventions.

## Activity Log

- 2026-10-30T17:52:00Z – system – Prompt created.
