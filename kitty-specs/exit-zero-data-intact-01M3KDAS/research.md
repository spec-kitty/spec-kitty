# Research: Exit 0 means your data is intact

The evidence comes from the milestone-11 research squad and the post-spec adversarial squad (architect-alphonso, debugger-debbie, reviewer-renata), all run against `main` @ `b7ada760`. File and line references are as observed at that commit. Every claim below was checked against live code or a live CLI run.

## R1 — #4919: why a deferred-then-resolved decision disappears

- **Decision:** fix the fold in this repository. The fold is order-independent: exactly one `deferred` outcome plus one `resolved` outcome folds to `resolved`. Diagnose compares folded status with the index, and repair reports and refuses instead of dropping.
- **Post-plan correction:** an earlier draft said to fold in append order. The event-log merge driver (`status/event_log_merge.py:62-68`) re-sorts the log by `(at, event_id)`, so after a git merge, append order is wall-clock order. The fold therefore must not depend on order.
- **Evidence:**
  - `defer` emits a real `DecisionPointResolved` with `terminal_outcome=deferred` (`decisions/service.py:~720`, `decisions/emit.py:251-330`).
  - `service._is_allowed_terminal_reopen` (`service.py:146-151`) then allows a second `DecisionPointResolved(resolved)`.
  - `index_fold.fold_events` (`index_fold.py:219-221`) rejects the pair as malformed.
  - The `index_fold.py:196` docstring claims order independence, but the fix needs an explicit order: append order, which the emitter already uses as its Lamport proxy (`emit.py:97`).
  - Repair runs only when diagnose sees divergence (`_decisions_doctor.py:400`, `if repair and not report.clean`). Diagnose compares id sets only (`:255-273`). When the index already has an entry, it is kept (`:247-250`).
  - So the loss appears only after the index diverges. Live run: `rm decisions/index.json` then `--repair` gives `malformed_folds:[D]`, `count:0`, exit 0.
- **Consequence for tests:** the red-first repro must delete `index.json`. An open → defer → resolve → repair run on today's code passes.
- **C-004 check:** the fold is in-repo, so no events-package change is needed. The events reducer (`spec_kitty_events/decisionpoint.py:104-128`) flags RESOLVED→RESOLVED as `invalid_transition`; that is an upstream follow-up.
- **Documented contract:** `doctor decisions` is documented to always exit 0 (`doctor.py:1393-1422`, `_decisions_doctor.py:383`). FR-004 changes this for repair, so the help text changes with it (C-007).
- **Live-code correction to the spec's first draft:** the service already refuses resolve-after-resolve and cancel-after-resolve with TERMINAL_CONFLICT (`service.py:605-624`). No new transitions are introduced.
- **Alternatives rejected:** changing the emitter (existing logs stay broken); ordering by `at` (the #4941 bug class).

## R2 — #4900: why every mission is numbered 1

- **Decision:** the driver treats an unassigned target value as unset; the number is baked on the target after the squash; it is read back before being announced.
- **Evidence:**
  - `reconcile_meta_payloads` (`consolidation/drivers.py:295-297`) copies a target-owned key whenever it is present, even when it's `null`. Live: `merge-driver-meta` with ours `null` and theirs `1` gives `null`.
  - The printed number comes from `ordering.py:765`, before the mission → target squash where the driver runs.
  - The planning-only path already writes the number on the target (`ordering.py:782-793`; `executor.py:1770/1825` `mission_number_meta_path`). That is the precedent the fix follows.
  - The forecast path (`forecast.py:162`) already uses `assign_next_mission_number`, so there is no parallel copy.
- **Reuse:** `_is_assigned_mission_number` (`ordering.py:275`) for the "unset" test; `kernel.meta_decode` for read-back (`test_inline_meta_read_gate.py` rejects a new raw read); the MERGE_BOOKKEEPING commit class and compare-and-swap advance for the bake (ADR `2026-09-19-1` terminus safety: gate, then mutate, with rollback).
- **Test note:** the driver shells out to `spec-kitty`, so the venv's `bin/` must be on `PATH` with a fresh editable install. Otherwise the test shows a stale-install false red.

## R3 — #4933: the self-bookkeeping predicate and its callers

- **Decision:** a depth-exact path anchor inside `coherence.is_self_bookkeeping_churn`.
- **Evidence:** `coherence.py:125` exempts by filename. `is_self_bookkeeping_churn("src/app/meta.json")` returns True.
- **Callers** (directly or via `is_toolchain_generated_churn`):

  | Class | Call sites |
  |---|---|
  | Destructive gates | `consolidation/executor.py:2864` (root checkout pre-mutation, `reset --hard`), `executor.py:3082`, `orchestrator_api/commands.py:929`, `lanes/consolidation.py:1234,1316`, `coordination/workspace.py:329` (`worktree remove --force`), `ordering.py:662` and `commit_router.py:1175` (via `advance_branch_ref`, `git/ref_advance.py:~330`) |
  | Refusal gates | `consolidation/git_probes.py:184`, `executor.py:1783`, `acceptance/__init__.py:399`, `mission_record_analysis.py:191`, `review/dirty_classifier.py:112` |
  | Already location-scoped | `bulk_edit/diff_check.py:361` |
  | Routing filter | `implement.py:938` |

- **Anchor adjudication:**
  - The architecture lens proposed root anchoring (`^kitty-specs/`). The code-truth lens showed git porcelain paths are relative to the git root, so a project in a subdirectory shows `sub/kitty-specs/x/meta.json`, and root anchoring would newly block monorepo consolidations.
  - Chosen: `(?:^|/)kitty-specs/[^/]+/meta\.json$` (depth-exact) plus `.kittify/meta.json`. A user file at `kitty-specs/<mission>/research/meta.json` is not exempt.
  - Accepted trade-off: this repository's own test fixtures under `tests/audit/fixtures/*/repo/kitty-specs/*/meta.json` match the anchor. That only affects dogfooding, not consumers.
- **Not changed:** `mission_runtime._MISSION_FILE_KIND_BY_BASENAME` (it would widen `bookkeeping_projection.py:472` and the reconciliation class guard); `git/ref_advance.py:353` (lock-field-only diffs, acceptable).
- **Out of scope:** `conflict_resolver.py:94` resolves take-theirs on `*/meta.json`; it gets a follow-up issue.

## R4 — #4940: the settings file decode path

- **Decision:** use `kernel.text_decode.decode_unambiguous` (BOM or strict UTF-8 only). A typed refusal replaces the `{}` fallback. Original bytes are backed up before an encoding-changing rewrite.
- **Evidence:**
  - `claude_code_hook.py:147-150`: on `UnicodeDecodeError`, `_load` returns `{}` before the backup branch (`:151-160`).
  - `register` (`:195-212`) then saves a lint-only file.
  - Second caller: `live_work/install.py:92` → `register()`.
  - `prepare_commands` (`:77-99`) parses bytes with `json.loads(bytes)`, whose stdlib detection accepts UTF-8, BOM and UTF-16/32, and raises on anything else. It is safe but uses a different rule, so it converges on the shared helper (FR-014).
  - A UTF-8-with-BOM file already gets a `.invalid.<uuid>` backup today (the JSONDecodeError branch). Only UTF-16 and cp1252 lose data silently.
- **Encoding policy** (operator, DM `01M3KDD2`): decode only provable encodings. `charter.encoding_recovery.recover()` would guess cp1252 via `charset_normalizer` (`encoding_recovery.py:97-111`), and its confidence can report 1.0 for a single-winner guess, so it can't be used directly. Its BOM and strict-UTF-8 steps (`_recover_from_bom`, `_recover_strict_utf8`) are standard-library only; they move to `kernel.text_decode`, and `recover()` delegates to them.
- **The "recently merged PR" the operator remembered:** the closest match on this history (shallow clone) is #5170 (#4962), which built the single charter detector. No merged "runtime cycle JSON" encoding PR could be found. The plan reuses #5170's detector steps.
- **Out of scope:** `live_work/capability.py:322` doesn't catch `UnicodeDecodeError`. It crashes without losing data; it gets a follow-up.

## R5 — #4998: CRLF frontmatter doubling

- **Decision:** add `kernel.text_decode.normalize_newlines`, applied inside `ensure_skill_frontmatter` and in the command-skill render right after decoding; add a `.gitattributes` `eol=lf` rule for both source trees.
- **Evidence:**
  - There are two frontmatter regexes, each matching `\n` only. `command_renderer.py:59` (`ensure_skill_frontmatter`) is used by `installer.py:329,733`, `verifier.py:192` and `runtime/agent_skills.py:131`. `command_renderer.py:46` (`_strip_frontmatter`) is used by the command-skill render at `:447`.
  - The installer decodes raw bytes and keeps CRLF, while the verifier uses `read_text` and normalises, so the two sides disagree.
  - `template/renderer.py:29` already strips `\r` (precedent). `charter/hasher.py:40` also strips the BOM and trims whitespace, so it is not reusable as-is.
- **Repair convergence:** `--fix` rewrites from source only when the manifest hash equals the on-disk (corrupted) bytes (`installer.py:795-800` `unchanged_owned`). Otherwise the file lands in `consent_required` (`:894`). FR-017 and FR-018 test both branches.
- **Source locations:** doctrine skills are in `src/charter/offering/skills/**` (55 `SKILL.md`); command templates are in `packs/built-in/missions/mission-steps/**`. `.gitattributes` has no `eol` rules today. `test_merge_reconciliation_class_guard.py` parses `.gitattributes`.
- **Test note:** there is no env override for the skill source root. Linux red-first tests use `CliRunner` plus a monkeypatched `SkillRegistry.from_package` pointing at CRLF fixtures.

## R6 — #4964: migrate group flags

- **Decision:** a single seam in the group callback: forward via `ctx.default_map` or raise `click.UsageError`.
- **Evidence:** `migrate_cmd.py:143` returns early whenever a subcommand is invoked.
  - Subcommands declaring `--dry-run`: backfill-identity, backfill-merge-commit, backfill-mission-type, backfill-provenance, backfill-runtime-state, backfill-topology, charter-encoding, normalize-lifecycle, rebaseline-dossier-hashes, rewrite-opposed-by.
  - `repin-hooks` has no `--dry-run`.
  - No subcommand declares `--force` or `--verbose`.
  - No repository documentation uses the group-flag-before-subcommand form, so refusing unforwardable flags breaks no documented usage.

## Campsite (brownfield standing order 2)

Pre-existing findings in functions this mission touches are cleaned first, as a behaviour-preserving step:
- mypy `no-any-return`: `decisions/service.py:132,151,339`, `_decisions_doctor.py:154`, `skills/installer.py:529,538` (and `:1040` subclass-of-Any), `skills/verifier.py:190`.
- `ruff` (including C901 ≤15) is clean on all touched files today and must stay clean.
