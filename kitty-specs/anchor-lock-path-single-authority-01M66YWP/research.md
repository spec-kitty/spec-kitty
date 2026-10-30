# Research — one kernel helper for anchor-keyed lock paths (#6727)

Grounded on `main` at `512567ee` (`origin/main` fast-forwarded, tree clean except the
append-only `kitty-ops/lifecycle.jsonl`). Mission boundary: the three lock families the
issue names.

## 1. The issue still reproduces on current main

The rule "resolve the anchor → `os.path.normcase` it → digest it → place the result under
`<git-common-dir>/spec-kitty-locks/<subdir>/` (or a caller-specific fallback outside git)"
is written out three times, in three modules, with three subtly different implementations:

| Family | Site | Probe | Identity | Placement | Outside git | git unusable |
| --- | --- | --- | --- | --- | --- | --- |
| event-log | `src/kernel/event_log_append.py:154-171` | `git_common_dir(resolved.parent)` | `sha256_digest(...)[:32]` | `<common>/spec-kitty-locks/event-logs/<digest>.lock` | `<anchor>.event-log.lock` (sibling) | raises `EventLogLockUnavailableError` |
| charter synthesis | `src/charter/activation/synthesizer/synthesis_lock.py:82-96` | `git_common_dir(resolved)` | `sha256_digest(...)[:32]` | `<common>/spec-kitty-locks/charter-synthesis/<digest>.lock` | `<root>/.kittify/runtime/locks/charter-synthesis.lock` | raises `SynthesisLockUnavailableError` |
| status (checkout claim) | `src/specify_cli/status/locking.py:362-366` | `_git_common_dir(resolved)` | `sha1(...)[:16]` | `<common>/spec-kitty-locks/__checkout-<digest>__.status.lock` | degrades to `<root>/.git` / `.kittify` / `.spec-kitty` (never raises) | same degrade |

All three are "anchor-keyed": the file name is a digest of the resolved, case-normalised
anchor path, and the directory is the repository's git common dir, so every worktree of one
repository agrees. `normcase` + `resolve` + digest is spelled out three times
(`event_log_append.py:170`, `synthesis_lock.py:95-96`, `locking.py:363-364`), and the
`<common dir>/spec-kitty-locks` join two more times in `locking.py`
(`feature_status_lock_path:190`, `project_event_log_lock:347`).

Not superseded: no commit on `main` introduces a shared helper (`git log -S
"spec-kitty-locks"`, `grep -rn "anchored_lock_path"` both come back empty beyond the
copies above); the changelog has no entry for a lock-path unification; the issue's parent
(#6453) is merged and this is its recorded follow-up. The issue is open, unassigned and
labelled `priority:P3`.

The defect is a *code-shape* defect (DIRECTIVE_044, one canonical source): there is no
runtime failure to reproduce. The reproduction is the three implementations above, and the
proof that the extraction is behaviour-preserving is the existing path tests, which pin all
three shapes:

- `tests/kernel/test_event_log_append.py:243-249` — golden digest
  `5d011f83a018c89fa185a10c696c8293` under `spec-kitty-locks/event-logs` (the Java writer,
  #6193, must compute the same name);
- `tests/kernel/test_event_log_append.py:272-278` — non-git sibling fallback;
- `tests/charter/synthesizer/test_synthesis_lock.py:71-113` — subdir, symlink, worktree and
  non-git placement;
- `tests/status/test_checkout_claim_lock.py`, `tests/status/test_journal_lock_unification.py`
  — checkout-claim lock behaviour and the flat `<key>.status.lock` names.

Baseline (pre-change): `uv run pytest tests/kernel/test_event_log_append.py
tests/charter/synthesizer/test_synthesis_lock.py tests/status/test_checkout_claim_lock.py
tests/status/test_journal_lock_unification.py -q` → **66 passed, 2 skipped**.

## 2. Who consumes these paths

`event_log_lock_path` is used by `specify_cli/state/retention.py` (non-blocking sweeps over
`kitty-ops/*.jsonl`) and by tests that hold a log's lock from another thread;
`synthesis_lock_path` by `charter/activation/bundle_restamp.py` (the refusal message names
the file) and the synthesize/resynthesize command surfaces; the checkout-claim lock only by
`write_checkout_claim_lock`. All three callers only ever *hold* the path — nothing parses,
sorts or pattern-matches it — except `_is_checkout_claim_lock_key`, which pattern-matches the
`__checkout-…__.status.lock` **name**, so that name must not change.

## 3. Decisions

**D1 — the helper lives in `kernel/locks.py`, next to `LOCK_DIRECTORY`.**
`LOCK_DIRECTORY` is already the kernel's single owner of "locks live under
`<git-common-dir>/spec-kitty-locks`", and the kernel tier is importable by `charter` and
`specify_cli` but not vice versa, so one helper can serve all three families without an
inverted dependency. This also matches the issue's proposed `kernel.locks.anchored_lock_path`.
`kernel.locks` stays dependency-free apart from `kernel.clock` and `kernel.git_topology`
(intra-kernel, stdlib-only), so the C-001 "kernel has no third-party deps" rule holds.

**D2 — one helper owns the rule; each family keeps its own policy.**
`anchored_lock_path(anchor, *, common_dir, probe_dir, subdirectory, prefix, suffix,
digest_algorithm, digest_hex_length)` performs exactly the repeated part: resolve the anchor,
`os.path.normcase` it, digest it, join `<common dir>/spec-kitty-locks[/<subdir>]/<prefix><digest><suffix>`.
It **propagates** `NotAGitRepositoryError` / `GitTopologyUnavailableError` instead of deciding
what to do, because the two policies genuinely differ (refuse vs degrade) and the issue's
acceptance criterion is that each lock keeps its behaviour and error handling. `common_dir=`
is the seam for a caller that resolves (and degrades) the common dir itself; when it is
given the helper runs no git probe. `probe_dir=` exists because the event-log anchor is a
*file* that may not exist yet, so the probe has to run in its parent directory
(`kernel.git_topology._probe_dir` only normalises an *existing* file).
Parameters are keyword-only and every one is exercised by a caller, so none is a dead knob.

**D3 — the status family moves too, and its file names do not change.**
`_checkout_claim_lock_path` routes through the helper with `digest_algorithm="sha1"`,
`digest_hex_length=16`, `prefix="__checkout-"`, `suffix="__.status.lock"` and
`common_dir=` set to its own degraded common dir, which keeps the sha1 name byte-identical
(no migration, no re-lock) while removing its private copy of the digest logic.
`feature_status_lock_path` and `project_event_log_lock` keep `_git_common_dir(...)` directly:
they are *not* anchor-keyed (one is keyed by mission directory name, the other by a fixed
sentinel), so they have no digest rule to share. Their docstrings name the helper and say
why they do not use it, so the next reader does not re-open the question.

**D4 — non-git fallbacks stay in the callers.**
They differ per family and are part of each family's documented contract (`<anchor>.event-log.lock`
is deliberately distinct from the glossary repair lock's `<log>.lock`; the synthesis fallback
is a fixed `.kittify/runtime/locks` path). Pushing them into the helper would need a
callback parameter whose only purpose is to preserve three unrelated policies — a worse
abstraction than three two-line `except` clauses, each already covered by a test.

**D5 — the contract is pinned by tests that fail if the helper drifts.**
New `tests/kernel/test_lock_paths.py`:
1. per-shape goldens with independently computed digests (literal hashes, so a change to
   `normcase`, the algorithm, the truncation or the join fails);
2. a cross-family test: for one anchor, the event-log lock and the synthesis lock have the
   same digest and differ only by subdirectory (a drift in either caller's identity fails);
3. the sha1/16 shape: the helper's output equals the literal `__checkout-<sha1[:16]>__.status.lock`
   name, and `write_checkout_claim_lock`'s acquired path equals it (the name
   `_is_checkout_claim_lock_key` pattern-matches);
4. `common_dir=` performs no git probe (monkeypatch `git_common_dir` to raise) and
   `probe_dir=` is what is probed (a file anchor probed from its parent);
5. parameter validation: an unknown digest algorithm raises `ValueError`, and a
   `digest_hex_length` outside 1..64 raises `ValueError` (the helper refuses to mint a name
   it cannot reproduce);
6. a source-shape guard: no module under `src/` outside `kernel/locks.py` builds a
   `spec-kitty-locks` path with its own digest (AST/grep test), so a fourth copy fails CI
   instead of being reviewed by eye.
Existing family tests stay untouched and must stay green — they are the behaviour-preserving
half of the proof.

## 4. Out of scope (recorded, not done)

`specify_cli/review/verdict_commit_queue.py` and `specify_cli/design/receipts.py` also build
lock paths under `<common dir>/spec-kitty-locks/`, but with a fixed file name and a
caller-derived key respectively, no anchor digest. They share no rule with the three
families beyond the directory join; touching them would widen the blast radius of a P3
consolidation without consolidating anything. If a future change gives them an anchor
digest, they call this helper.

## 5. Open questions for specify/plan

- Does any test or doc pin the *number* of lock path helpers (an architectural census)?
  Plan step checks `tests/architectural/` before assuming a clean slate.
- Is a changelog entry warranted? The change is internal (no user-visible behaviour, no
  lock file name change). The brief asks for `[Unreleased]` entries for user-facing
  changes; this one is maintainer-facing, so the decision belongs in the plan with a reason.
