# Phase 0 Research: Local Write-Safety Hardening

## Design Decisions

### D1 — One canonical no-follow-open primitive, hoisted into `kernel/`
- **Decision**: Create `src/kernel/no_follow.py` (or equivalent kernel-layer surface) as the single canonical symlink-safe open, and have `kernel.locks._LockCore.open_fd` + `force_release` and every specify_cli write site (credentials, mission_state, prompt temp, cold-install sentinel) consume it. Repoint `specify_cli.core.no_follow` to the kernel helper (thin re-export, no behavior fork).
- **Rationale**: `kernel.locks` cannot import `specify_cli.core.no_follow` without violating the enforced `kernel ↛ specify_cli` import direction (`tests/architectural/test_layer_rules.py`). A single kernel primitive satisfies C-001/C-004 (canonical source) and closes the class by construction (every future lock/open inherits safety) rather than per-site `O_NOFOLLOW` copies.
- **Alternatives considered**: (a) inline `O_NOFOLLOW` in `kernel.locks` only and hand-roll it at each specify_cli site — rejected: reproduces the split-brain the mission exists to close (paula/priti). (b) keep the helper in `specify_cli.core` and duplicate for kernel — rejected: layering violation + two sources of truth.
- **Whole-module hoist (architect finding)**: hoist the *entire* `specify_cli.core.no_follow` module (all six symbols — `NoFollowPathError`, `chmod_fd`, `fd_relative_dir_ops_supported`, `open_no_follow`, `read_text_no_follow`, `write_text_no_follow`) to `kernel/no_follow.py`; `core/no_follow.py` becomes `from kernel.no_follow import *` with an identical `__all__`. `NoFollowPathError` stays a single re-exported class (identity preserved for `except NoFollowPathError` at `gitignore_manager.py:18`). WP01 acceptance runs the **11 `core.no_follow` importers** plus the 13 `kernel.locks` consumers.
- **Scope of the class-closure claim (paula HIGH — narrowed)**: this mission routes the shared lock + the four defect write-sites (credentials, mission_state lock, prompt temp, cold-install sentinel) through the canonical helper. It does **NOT** convert the ~7 *already-correct* pre-existing hand-rolled `O_NOFOLLOW` sites (`charter/activation/charter_yaml_io.py:185`, `coordination/atomic_write.py:83,107`, `invocation/writer.py:144,184`, `session_presence/writers/markdown_rules.py:93,262`, `status/store.py:433,437`, `tool_surface/bundles/projection.py:355,981`, `upgrade/migrations/m_3_2_8_provision_kitty_env.py:291,294,416,420`) — those are correct guards, not defects. True codebase-wide class-closure would need a new arch ban-gate ("no hand-rolled `O_NOFOLLOW` outside `kernel.no_follow`"); that is a separate **deferred** item, recorded as a Non-Goal, not silently implied here.

### D2 — `O_NOFOLLOW`, never `O_EXCL`, on the shared lock open
- **Decision**: Add `getattr(os, "O_NOFOLLOW", 0)` to the lock open flags; do **not** add `O_EXCL`.
- **Rationale**: The lock file is designed to be re-opened by later legitimate acquirers (release truncates but never unlinks — the inode persists, `kernel.locks` G3). `O_EXCL` would break normal re-acquisition (C-003). `O_NOFOLLOW` guards only the final path component, which is why the *directory* must also be per-user (D3).
- **Alternatives**: `O_EXCL|O_CREAT` (as some non-lock temp writers correctly use) — rejected for the lock primitive specifically; correct for fresh-temp writers (credentials).
- **Evidence**: pre-spec squad (renata, paula, debugger) unanimous; `kernel/locks.py` release-truncate comment.

### D3 — Relocate world-shared predictable paths under `~/.spec-kitty` (`0700`), reusing the lock authority's parent-chmod
- **Decision**: Move the cold-install sentinel (`asset_preparation.py`) and the prompt temp dir (`_tmp_namespace.py`) from `tempfile.gettempdir()` into the per-user runtime root; obtain the `0700` parent via `machine_file_lock`'s existing `_ensure_dir` chmod (`kernel/locks.py:~288`) rather than a new `mkdir(0700)`. Establish a single canonical owner of `~/.spec-kitty = 0700` (FR-011/C-005).
- **Rationale**: `O_NOFOLLOW` guards only the final component; an attacker-owned world-shared *parent* still traverses. Per-user root + owner-only mode removes the plant vector (defense-in-depth with D2). Reuse avoids a competing chmod path (canonical source).
- **Alternatives**: keep `/tmp` but add a per-repo hash subdir (the partial #4721 shape) — rejected: still world-shared and predictable (renata's explicit warning against copying #4721's incomplete shape).

### D4 — Serialize the decisions index RMW at the **service-level** critical section
- **Decision**: Wrap the full read→mutate→write of `decisions/index.json` under `machine_file_lock` on a dedicated sidecar `decisions/index.json.lock` (never the JSON payload — `kernel.locks` G1), covering the service-level critical section in `decisions/service.py` (open/resolve), not merely `store.save_index`.
- **Rationale**: The check-then-act window spans `service.py` load (dedup/conflict check) → `append_entry`; a lock only inside `store.save_index` leaves that TOCTOU open (renata). Atomicity (`mkstemp`+`os.replace`) prevents torn writes but not lost updates.
- **Alternatives**: lock only the store write — rejected (fakeable, leaves the service TOCTOU). Optimistic retry — rejected (more complex, no reuse of the canonical lock).

### D5 — Reconcile a diverged index by rebuilding from the authoritative event log, via a `spec-kitty doctor` subcommand
- **Decision**: Add `_decisions_doctor.py` reconciler that rebuilds `index.json` from the decision event log by applying the **decisions forward event→IndexEntry mapping**, surfaced through `spec-kitty doctor`, and is a safe no-op when index and log already agree.
- **Rationale**: A go-forward lock does nothing for *already-diverged* corpora; the event log is authoritative (FR-005). The doctor surface mirrors the `_mission_state_doctor.py` *extraction shape* PR #4813 introduces (A1 / soft alignment).
- **Corrected authority (paula HIGH)**: the reconciler does **NOT** mirror `status.reducer.reduce()` — that reduces a different `spec_kitty_events` status-lane schema. The forward writer currently builds the `IndexEntry` from CLI params and derives the event from it; the reconciler needs the **inverse** event→IndexEntry fold, which exists nowhere today. To avoid a second reducer (split-brain), factor **one canonical `event → IndexEntry` fold** consumed by the reconciler (ideally shared with the forward path so they cannot drift). I9 ("index reconstructible from the log") must be **proven** by a round-trip task: the opened + resolved/terminal events must serialize every `IndexEntry` field the index needs; any field that does not round-trip is a prerequisite fix before the reconciler is trusted.
- **Alternatives**: auto-repair on every read — rejected (hidden mutation, perf on hot read path); manual JSON edit — rejected (unsafe, no invariant).

### D6 — Init backs up operator content at **every** destructive site; broaden the idempotency gate
- **Decision**: Route every init destructive-removal site (`template/manager.py::copy_package_tree`, `copy_specify_base_from_local` ×subtrees, and the `init.py` removal site) through a shared "back up operator-authored `.kittify/` content to timestamped `.kittify/.backup-<ts>/`, then proceed" helper; broaden the "already initialized" predicate beyond `config.yaml` presence.
- **Rationale**: `config.yaml` is a correlated sentinel, not the cause; a single-site or single-precondition guard is fakeable (renata HIGH). The invariant is "never rmtree operator-owned content" (epic #4792).
- **Alternatives**: refuse-with-guidance or merge — considered and **rejected by operator decision** (governed Decision Moment `01M2ZQ1G…`: back-up-then-proceed, unattended-friendly for the cold-start path).
- **Vocabulary note (C-006)**: this persistent, operator-reported backup is distinct from `template_render/pipeline.py`'s transactional `.bak-{nonce}` (removed on success). Keep them named separately.

### D7 — Credential files owner-only by construction, both transports
- **Decision**: Both `zeitgeist_client/credentials.py` (add `O_NOFOLLOW`) and `tracker/credentials.py` (replace `write_text`+`chmod` with `os.open(..., O_CREAT|O_EXCL, 0o600)`) create credentials owner-only from creation with no world-readable window.
- **Rationale**: closes the "0600-by-construction" class for the **plaintext-secret transports** (#4812 + #4760). `O_EXCL` is correct here (fresh temp, unlike the persistent lock).
- **Class boundary (paula MED — stated, not asserted)**: the credential class in scope is the plaintext-secret transports **zeitgeist + tracker**. Auth writers (`auth/secure_storage/file_fallback.py:278` session blob, `:136` salt, `auth/session_hot_path.py:137`) still use `write_text`→`chmod`, but are **deliberately out of scope**: the session blob is AES-GCM *ciphertext*, the salt is non-secret, and `file_fallback` enforces read-side `0600` verification (NFR-013). The plaintext AES key (`file_fallback.py:162`) is already `O_EXCL`-correct. Stated so a later agent does not re-litigate `file_fallback:278`.
- **Retire the competing 0700 ladder (paula MED — single owner of `~/.spec-kitty`)**: `zeitgeist_client/credentials.py:220-224` hand-rolls a 3-level `chmod(0o700)` ladder on the runtime root. WP05 must retire it into the canonical authority (the lock's `_ensure_dir` chmod, C-005) so FR-011's single-owner claim is real, or record why it must stay.
- **Alternatives**: chmod-after-write — rejected (the exact 0644 exposure window #4760 reports).

### D8 — #4813 sequencing
- **Decision**: WP04 (#4811) bases on post-#4813 `main` (shares `migration/mission_state.py`); WP02's store-lock + reconciler *core* proceed now, its doctor subcommand aligns to #4813's `_mission_state_doctor.py` once merged.
- **Rationale**: #4813 adds ~180 lines to `mission_state.py` (up to ~line 1712) but does not touch the line-~2339 lock and adds no new locks — so WP04 is not superseded, only rebased. Verified in the pre-spec overlap check.

## Supply-Chain Security (DIRECTIVE_051 / supply-chain-install-safety)

**No dependency is added, upgraded, or removed by this mission.** All work uses the Python standard library (`os`, `fcntl`) and existing first-party surfaces (`kernel.locks`, `typer`/`rich` already present). Registry authenticity, package freshness, lifecycle-script discipline, and Node-LTS considerations are therefore **not applicable** — this is affirmatively examined, not silently skipped. If plan/tasks later introduces any dependency, this section must be revisited before that change lands.

## Adversarial Evidence Ledger

Per `contracts/adversarial-evidence-contract.md`. Two profile-loaded squads challenged this mission (pre-spec: architect/paula/debugger/renata; post-spec: renata/paula/priti). Contested-finding dispositions:

| Finding | Source | Disposition |
|---------|--------|-------------|
| Root cause is `kernel.locks`, not the CLI sentinel | pre-spec architect/paula/debugger | **accepted** — D1/D2; WP01 targets the primitive. |
| `O_EXCL` would break lock re-acquisition | pre-spec renata/paula | **accepted** — D2, C-003. |
| #4757 lock must span service-level RMW, not just store | pre-spec renata; post-spec renata | **accepted** — D4, FR-004. |
| #4759 has ≥3 rmtree sites; single-site fix fakeable | pre-spec paula; post-spec renata (HIGH) | **accepted** — D6, FR-006/NFR-003/SC-003. |
| #4756 relocation needs a measurable SC | post-spec renata | **accepted** — SC-006. |
| Concurrency proof must be red-first + barrier-synchronized | post-spec renata | **accepted** — NFR-002/SC-002. |
| Fold #4760 (credential class) | post-spec paula | **accepted (operator)** — folded into WP05. |
| Fold #4721 fully (prompt temp; DoS + info-disclosure) | post-spec paula | **accepted (operator)** — US3/WP06/FR-010/NFR-005. |
| Add WP01→WP04 and #4813→WP02(soft) edges | post-spec priti | **accepted** — dependency graph in plan.md. |
| Adjacent siblings #3960/#4003/#2627/#4182 belong to other classes | post-spec paula | **deferred_with_rationale** — recorded as Non-Goals in spec.md (different surfaces; avoid over-widening). |
| #4305 (`core/file_lock.py` S3516) | post-spec paula | **deferred_with_rationale** — likely stale (file moved to `kernel/locks.py`); flagged for triage, not in scope. |
| Optional WP01 split (primitive vs sentinel relocation) | post-spec priti | **deferred_with_rationale** — left to /tasks; WP01/WP01b noted as a splittable pair. |
| Kernel-hoist is sound; hoist WHOLE module (6 symbols), preserve `NoFollowPathError` identity + full `__all__` | post-plan architect | **accepted** — D1 whole-module-hoist; contract enumerates full API; WP01 acceptance = 11-importer blast radius. |
| Inline-in-kernel.locks alternative is worse than the shared hoist | post-plan architect | **accepted** — D1; inline would regress existing consolidation. |
| "one canonical helper / no per-site O_NOFOLLOW" claim is aspirational (~7 correct hand-rolled sites survive) | post-plan paula (HIGH) | **changed** — narrowed the claim to the lock + 4 defect sites; censused the ~7 sites as a Non-Goal; a codebase-wide ban-gate is a separate deferred item. |
| Reconciler must mirror the DECISIONS forward mapping, not `status.reducer`; prove I9 | post-plan paula (HIGH) | **accepted** — D5 corrected; one canonical event→IndexEntry fold + I9 round-trip proof task. |
| Enumerate full no-follow API; WP01 blast radius is the 11 importers, not 13 lock consumers | post-plan paula (MED) | **accepted** — contract + D1 updated. |
| Retire zeitgeist's hand-rolled 0700 ladder; state credential-class boundary | post-plan paula (MED) | **accepted** — D7; WP05 retires the ladder; auth ciphertext/salt stated out-of-scope. |

No contested finding was silently dropped.
