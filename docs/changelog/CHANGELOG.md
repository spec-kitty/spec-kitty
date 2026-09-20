---
title: Changelog
description: Canonical changelog for the Spec Kitty CLI and templates, following Keep a Changelog and Semantic Versioning, with added, breaking, and fixed entries per release.
doc_status: active
updated: '2026-09-20'
---
# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to the Spec Kitty CLI and templates are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 4.0.0rc4

_4.0.0rc4 candidate cycle. Entries land here until the release chore finalizes
this section at publish._

### Added

- **`spec-kitty zeitgeist activity --person`/`--project` and `watch --seed` close #4215's remaining read-surface scope (the 2026-09-17 narrowing over the 2026-09-14 re-scope).** `activity`'s two missing selectors are client-side membership rules over the retained frames — `--person` keeps only frames whose actor `user` names that teammate (unattributed frames never match), `--project` keeps only frames whose mission correlation (`focus_ref`, or an event frame's `ref`) is the slug or begins `<slug>.`, with BOTH ref kinds grammar-routed so prose that merely contains — or starts with — a slug cannot attach itself to a mission. Both are reported with their own matched/withheld counts in a `selector` block, so an empty result under a selector never reads as an empty relay; the relay's `/managed/events` route has no such filter, so the narrowing happens on this side of the wire. `watch --seed <seconds>` (and the MCP `zeitgeist_watch` tool's `seed_window_s`) switches to the relay's race-safe `follow=1` handoff (zeitgeist#296): the preface `SnapshotDocument` seeds presence/focus state from the registries at the cut, its retained history is delivered first through the same novelty/receipt policy, and live frames that duplicate a history frame are dropped by `(epoch, seq)` — whole, never state-applied, so a duplicated pre-cut signal cannot wipe the just-seeded registries — the overlap the relay's reserve-before-snapshot ordering makes correct. The preface read is bounded by the watch call's own `idle_timeout_s` (a relay trickling only SSE heartbeat lines gets a named `TimeoutError`, never an indefinite hang), a requested seed against a relay without the follow route is reported as the missing route it is (not a connectivity fault), and the MCP `seed_window_s` parameter is schema-strict (`>= 0`, no bool/string coercion — same rejection the CLI's `min=0.0` applies). `0`/omitted stays future-only; a relay that serves no snapshot answers 404 and an unusable preface raises — a requested seed is never silently degraded. The preface's coverage metadata rides the result as `seed`, so a truncated backfill is visible. CLI and MCP call the same `subscription.agent_activity`/`agent_watch` service; `docs/api/cli-commands.md`'s `zeitgeist status`/`watch`/`activity` sections are regenerated to match. Deferred with evidence: credential renewal on an expired capability stays with auth epic #3892 (no renewal seam exists for readers to call yet; a denied read already fails legibly as a fault, never as an empty team). The same PR folds #4335's two squad MINORs on the slice-1 status surface: `status`'s fallback listen now reports the **measured** listen time instead of the configured bound (a relay that closes the stream early no longer prints "listened for 2.0s"), and snapshot entry ages are derived **skew-free** from the document's own `observed_at` anchor (anchor − entry `observed_at`, both on the relay's clock, plus only the locally-measured time since fetch) instead of subtracting a relay timestamp from the local wall clock — a relay an hour ahead of the client no longer clamps a 40-second-old observation to a lying `observed 0s ago`. The anchor and fetch time ride the JSON result as top-level `observed_at`/`fetched_at`; the listen path (no anchor exists there) keeps the legacy derivation and says so in `_observation_age`'s docstring.

### Fixed

- **`spec-kitty agent action implement` no longer refuses to re-claim an approved work package with a bogus "review feedback artifact is missing" error, and a long review note can no longer drop the Team Kitty status moment** (#4801; refs #4327, closes the #3954 note-overflow class on the status-attr lane). The `review_ref` status attribute is now a pointer only. **Before:** when a work package was approved or rejected without an explicit `--approval-ref`/`--review-ref`, the operator's `--note` prose was written into `review_ref` itself — a long note overflowed the codec's 240-UTF-8-byte wire attribute (the #3954 dropped/mangled-moment class), and on the read side an approved WP whose newest `review_ref` was that prose made `agent action implement` try to resolve it as a feedback artifact and refuse the re-claim. **After:** approval/rejection references carry only a real pointer or a synthetic marker token (`approval:<WP>` / `review:<WP>` / `auto-approval:<WP>:<date>`); the operator's note stays whole in the durable `reason` (which the pinned codec keeps off the wire), the read seam skips the synthetic markers instead of mis-resolving them, and the #3954 interim wire-side truncation is removed so the events codec's own byte bound is the single authority again. The one remaining prose path — an over-long `--review-ref` an operator types themselves — now fails closed loudly (logged warning, zero network attempts), never silently truncated or dropped.
- **The pre-review regression gate no longer fires in a consumer repo that never declared a review test command** (#3821). The gate binding ships built-in with the `software-dev` review contract, so binding resolution alone could not tell a repo that configured a gate from one that never did. **Before:** moving a work package to `for_review` in a repo with no declared `review.test_command` still tried to run the gate and surfaced an internal-sounding `no_coverage` concern, leaking a gate the repo never asked for. **After:** the repo's own declaration is the signal — the move probes the same activation-selected test-command authority the dispatch would use, and when the binding is active but nothing is declared it records one quiet `skipped` verdict (no console line, a calm consumer-facing reason that names no internal concept) instead of dispatching. A configured-but-malformed `review.test_command` still counts as declared, so a broken declaration surfaces a visible warning rather than a silent skip; a repo that did declare the gate is unaffected.
- **A failed charter preflight under `spec-kitty next` now says `consumer=next` instead of `consumer=dashboard`** (#4731). Query mode (`next` without `--result`) is read-only, so it reuses the dashboard's warn-and-continue preflight helper. **Before:** that helper hardcoded its own name in the log line it emits, so the only charter output an operator saw from `next` was labelled as the dashboard's — misleading when working out which surface tripped the preflight. **After:** the helper takes the consumer name from its caller (still `dashboard` by default), and `next` passes its own, so the warning names the command you actually ran. The remediation text, the warn-and-continue behaviour, and the dashboard's own label are unchanged.
- **`doctor tool-surfaces --fix` / `upgrade` now repair every detected-stale agent surface and converge in one run**: root-level orientation files (GEMINI.md, LLXPRT.md) refresh regardless of a harness command dir; the managed-skills completion re-check and the doctrine command-parent check are host-aware so Windows upgrades converge in one pass (command + doctrine skills) with no phantom dry-run repairs; command-skills manifest content is deterministic; residual drift is reported as a failure instead of exit-0 (#4782, #4776, #4777, #4134).
- **Activating a built-in charter directive now keeps the compiled `catalog.references` coherent by construction, and charter authoring is worktree-safe** (#4785; folds the CLI-write half of #4250). Four coupled tooling gaps are closed. **`charter activate`/`deactivate`** — **Before:** a config-only write that left `charter.yaml`'s compiled `catalog.references` stale, tripping the suite-tier coherence guard (the #2524 dangler class); only `--resynthesize` recompiled. **After:** activation/deactivation recompile the catalog by default through the single `compile_charter` authority (the `charter pack apply --compile` pattern, `from_interview=False`) when a compiled `charter.yaml` already exists, so the coherence guard stays green with no manual edit; a new `--no-compile` flag preserves the fast config-only write with an explicit "not recompiled" notice (a not-yet-synthesized config-only project is left untouched — no bootstrap, no activation-authority split). **Remediation guidance** — **Before:** the coherence-guard message and `--resynthesize` help pointed operators at `charter synthesize`, which is architecturally incapable of recompiling `catalog.references` and, on an established store with no `.kittify/charter/generated/`, short-circuited to a fresh-project seed. **After:** the guard message and help name `charter generate`; `synthesize`'s fresh-project detection keys on actual catalog establishment (an active `activated_*` entry, or a real prior synthesis manifest with interview answers), not on `generated/` absence, so an established store is no longer misclassified while a genuinely-incomplete store is still repaired. **Worktree safety** — **Before:** charter write commands (`activate`/`deactivate`/`generate`/`synthesize`/`resynthesize`) resolved the project root to the PRIMARY checkout, so running from a linked git worktree silently wrote into the primary repo. **After:** they fail closed from a linked worktree ("use a repository-root checkout or dedicated clone for charter authoring", non-zero exit) via a shared resolver built on the kernel `git_topology` probe (git-dir vs git-common-dir; git-absent degrades safely), and the `activate --resynthesize` chdir split-brain is eliminated. **Complete summaries** — **Before:** a full recompile left directive entries reading `summary: Definition unavailable in bundled doctrine.` when the transitive-closure surfaced a directive absent from the activation-filtered doctrine repository. **After:** summary lookup routes through the raw (unfiltered) doctrine repository, so transitively-reached directives resolve to their real summary, a genuinely-unresolvable id is reported through the existing unresolved-reference diagnostics (never a silent placeholder row), catalog membership is unchanged (still driven by the DRG closure), and `catalog.references` is emitted in a canonical deterministic order with `metadata.generated_at` preserved when the catalog is byte-unchanged. The dead, uncalled `_build_references_from_yaml` reference-builder is removed. **Known cost:** recompile-on-activate adds ~2.4–2.5 s (the single-authority `compile_charter` DRG/doctrine resolution) — accepted over a competing minimal-writer, which the charter's single-canonical-authority principle forbids. Cross-referenced, out of scope: #4250's hosted-binding-recovery half + saas#1713; the synthesize-recovery siblings #4042/#4226; the generate-honesty siblings #4618/#4615/#4614.
- **`spec-kitty merge` and `merge --abort` no longer silently destroy uncommitted operator work** (#4752, #4753, #4754). Three merge/abort-lifecycle paths fired destructive git commands against operator state with no dirty/branch/state guard. **Before:** (a) `spec-kitty merge` ran `git reset --hard HEAD` on the repository-root checkout unconditionally after advancing the target ref — a checkout on another branch with uncommitted tracked edits lost them, and the merge then crashed mid-bookkeeping with a raw `SafeCommitHeadMismatch` (#4752); (b) lane cleanup ran `git worktree remove --force` on every lane worktree with no dirty check, deleting uncommitted implementer work never on the lane branch, exit 0 (#4753); (c) `merge --abort` ran `git merge --abort` on the primary checkout whenever `MERGE_HEAD` existed — even with no spec-kitty merge state — destroying the user's own in-progress merge while printing "No active merge state to abort." immediately followed by "Aborted in-progress git merge." (#4754). **After:** a single git-plumbing-pure refuse-before-destroy guard (`git/destructive_guard.py`, reusing `ref_advance._dirty_entries` with the injected toolchain-churn classifier — no new parallel dirty predicate) runs as a pre-mutation preflight before any ref advance: `spec-kitty merge` refuses fail-closed and byte-identical to pre-invocation when the primary checkout is off-target or dirty, or when any lane/coord worktree is dirty and removal is requested (`--resume` honors the same guard); lane, coordination, and orchestrator-api worktree removal all route through `guarded_worktree_remove` so a dirty worktree is never force-removed and the coordination triple is held back atomically; and `merge --abort` aborts a git merge only when active spec-kitty merge state exists, scoped to the merge workspace, never `repo_root`. The defect class is closed by construction by a non-vacuous architectural routing gate (`tests/architectural/test_destructive_op_routing.py`, proven fail-able by self-mutation). Deferred with rationale: standalone `git branch -D` unmerged-commit loss (a distinct loss surface needing an is-branch-merged guard) is tracked as a follow-up mission.
- **`spec-kitty merge` under the default `warn` gate mode no longer consolidates an unapproved mission and wedges it beyond recovery** (#4764). **Before:** with `policy.merge_gates.mode: warn` (the default), a merge on a mission whose work packages were still `in_progress` printed the missing-approval gate as a *warning*, then went ahead and consolidated the lane branches onto the coordination branch and baked `mission_number` into the coord `meta.json` — and only then failed the post-merge backstop with exit 1, rolling nothing back. The lane was left with zero commits beyond coordination (so the `for_review` gate rejected it forever), coord and primary `meta.json` disagreed on `mission_number` (split-brain), and the work package could never be reviewed again without `--force` or hand git surgery — and the unreviewed code was now on the mission branch a later successful merge would squash to the mainline. **After:** an unconditional *merge-ready* precondition (`_assert_mission_terminal_ready`) runs before any mutation, regardless of gate mode: if any non-cancelled work package is not `approved`/`done` (a work package with no status event is treated as not-ready, never silently dropped), the merge refuses with exit 1 naming the missing work packages and changes nothing. `warn` still softens evidence-*quality* gates (review verdict, risk, hollow-review); it can no longer soften the terminal-lane invariant. As defense-in-depth, the lane-consolidation and primary-tree `mission_number` bake are wrapped in a transactional rollback that resets the coordination ref/worktree **and** the target branch on a post-mutation failure, so a later failure can no longer strand the mission or orphan a bookkeeping commit on the target branch. Red-first `@pytest.mark.regression` coverage drives the real `spec-kitty merge` entry point.
- **`spec-kitty mission close` (without `--discard`) on an unmerged in-flight mission is refused instead of fabricating a completion record on the mainline** (#4765). **Before:** it exited 0, printed "closed", committed a `retrospective.yaml` with `kind: runtime_post_completion` to the target branch, and tore down the coordination worktree — despite its own `--help` promising it "requires that the mission has already been merged"; `retrospect summary` and downstream tooling then counted the in-flight mission as completed, and `next`/`implement` reported it blocked until the operator guessed to re-run `finalize-tasks`. **After:** the non-discard path checks `is_mission_merged` before any write; an unmerged mission is refused with exit 1 pointing at `--discard`, writing no retrospective, emitting no `RetrospectiveCaptured` event, and leaving the coordination worktree intact. The guard keys on *merged* (a recorded merge baseline), not *all-terminal*, so an all-cancelled-but-unmerged mission is correctly sent to `--discard` rather than torn down as a completion. A genuinely-merged mission still runs the teardown as before.
- **A successful merge no longer silently loses `mission_number` on a coordination-topology mission** (#4474). **Before:** the `mission_number` write-back composed the `meta.json` path inside the detached mission-branch worktree and, when it was absent there — which on a coordination topology it structurally is, because `meta.json` is a primary-partition artifact — logged a warning and returned without writing, so `mission_number` was lost everywhere and `doctor` stayed stuck at `pending` forever (the opposite failure mode from #4764's too-early bake). **After:** the bake is topology-aware — it writes and commits `mission_number` to the primary checkout's own `meta.json` (where a coordination mission's canonical copy lives); only when no reachable surface exists does it fall back to an observable merge-summary notice instead of a silent log-only skip. The `path_is_under_worktrees` guard is preserved, and the bake now participates in the merge rollback (above) so a failed merge never orphans the number on the target branch.
- **A mission whose work was implemented directly on the target branch can now be completed and closed cleanly, and its half-termination paths are made safe** (#2745, facets 1 & 3). **Before:** the sanctioned direct-on-target fallback (a work package committed on the target branch with no lane branch) was a dead end — `spec-kitty merge` hard-failed on the missing lane branch, and `mission close` choked on an orphaned `coordination_branch` marker (with a doubled slug and no `--json`); worse, a completion on that path could half-terminate the mission. **After:** `spec-kitty merge --skip-lanes` (alias `--no-lanes`) transactionally completes a merge-ready direct-on-target mission with no lane branch — while still enforcing the merge-ready precondition (no bypass), so a not-merge-ready mission refuses *before* advancing the target ref (making the half-terminated state unreachable), and the choice is persisted so `--resume` honors it without re-passing the flag; `mission close` tolerates an orphaned coordination-branch marker without a traceback, renders the mission slug once, and honors `--json`. Consolidation: all three terminus commands (`merge`, `accept`, `mission close`) now derive terminal readiness from one shared authority — the per-lane `is_acceptable_ending` predicate plus a new provenance-aware `mission_terminal_acceptability` aggregate — rather than re-inlined loops, and the duplicate terminal-lane set in `status/doctor.py` was retired. The direct-on-target rollback-*after*-target-advance arm is tracked as a follow-up under epic #3897; the refuse-before-advance guard keeps the interim state safe. Red-first `@pytest.mark.regression` coverage per facet.
- **`accept` on a protected-primary mission with no lane branch already names a followable escape hatch — verified, no code change needed** (#2745 facet 2, FR-014). Liveness confirmation: the historical impossible guidance ("run status commit operations from the mission lane branch/worktree" — impossible to satisfy when no lane branch exists) was already replaced by `accept.py`'s `commit_for_mission` routing, whose refusal now names a concrete, followable command (`spec-kitty agent mission finalize-tasks --mission <slug> --target-branch <feature-branch>`) or the documented `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1` env hatch. A new `@pytest.mark.regression` probe (`tests/specify_cli/cli/commands/test_accept_guidance_liveness.py`) pins this as an enduring guard against regressing back to the impossible instruction.
- **A single canonical guarded-read + CLI error-presentation seam replaces the scattered per-command crash/emitter patchwork** (umbrella #2899; children #4746/#4738/#4724/#4637/#4739/#4720). A format-agnostic kernel primitive, `kernel.guarded_read.read_guarded(path, parse, *, errors=(), error_cls=GuardedReadError, mode="text")`, reads a file once and collapses `(OSError, UnicodeDecodeError, *caller-declared exceptions)` into one typed `GuardedReadError` subclass (chained via `raise ... from exc`); a single global Typer error-presentation hook registered on the top-level `spec-kitty` app catches the `GuardedReadError` family and renders a clean `Error: <reason>` line (stderr, exit 1) or a `{"error", "kind", "path"}` JSON object (stdout, exit 1) under `--json` — a Typer usage error keeps its existing exit 2 unchanged, and any non-domain exception still re-raises as a traceback. The 7 pre-existing typed reader errors (`MissionMetaReadError`, `DecisionIndexReadError`, `CorruptLanesError`/`MissingLanesError`, `AgentConfigError`, `UnsafePathSegmentError`, `IntakeFileUnreadableError`, `kernel.meta_decode.MetaDecodeError`) are re-parented onto `GuardedReadError` **in place** via multiple inheritance — every pre-existing `except <LegacyError>` and `except ValueError` call site (the `UnsafePathSegmentError`/`MetaDecodeError` `ValueError` contract is preserved) keeps matching, verified by a dedicated back-compat regression over the ~85-site caller census. Every in-scope command adopts the seam, so a bad file/handle/stream now yields a clean actionable error instead of a raw traceback: **`workflow import`/`export`** on malformed/wrong-schema/wrong-type/unreadable YAML (#4738), **`mission close`** and **`accept`** on an invalid `--mission` (plus the `-f`=`--mission` footgun removed on all four sites) (#4724), **`agent release prep`** on a missing/incomplete/malformed `pyproject.toml` (#4637), **`intake -`** on non-UTF-8 stdin (now at parity with the file path) (#4739), and **`specify --json`** name validation — which now raises a hook-owned domain error instead of a `typer.BadParameter` Rich panel, emits a proper JSON error object, and **rejects non-ASCII names explicitly** with no silent character loss (#4720). Seven still-unguarded state readers (`decisions/service`, `merge/state`, `review/{baseline,lock,artifacts}`, `status/validate`, `core/wps_manifest`) are hardened through the primitive while preserving each reader's missing-vs-corrupt return contract, and the `runtime_bridge` requirement-mapping mask is narrowed so a corrupt work-package manifest surfaces as a typed finding (#4746). The class is closed **by construction**: a non-vacuous architectural gate (`test_cli_error_surface_seam.py`, proven fail-able by a self-mutation test) rejects any new in-scope command that reads/decodes/resolves outside the primitive or drops the global hook. `next`'s existing bespoke emitters, the residual `next`(exit 2)/others(exit 1) inconsistency, and the org-pack cascade non-vacuity reds surfaced during the mission (#4773) are tracked as explicit follow-ups, not silently folded.
- **`spec-kitty routes` in a checkout with no `origin` remote now tells you to add one, instead of sending you to a "Spec Kitty mission repository" you are already in** (#4626). **Before:** the error diagnosed the cause correctly (no `origin` remote) but closed with "run this from inside a Spec Kitty mission repository", and Rich swallowed the `[kitty "quarantine"]` config-section name as markup, leaving an unexplained "no quarantine record". **After:** the message ends with the fix that matches the diagnosis — add an `origin` remote (`git remote add origin <url>`); repository identity is derived from it, never from the directory name — and the quarantine record is named as what it is (a `[kitty "quarantine"]` record in `.git/config` preserving a former origin). The refusal itself is unchanged: an identity is still never minted from a directory name.
- **CLI hints that name a `/spec-kitty.<command>` slash command now say it runs inside your coding agent, not in the shell** (#4624). Several error and next-step messages listed a slash command next to shell commands with nothing to tell them apart, and typing the slash command into a terminal fails with "no such file or directory". **Before:** `spec-kitty charter generate` without interview answers said "Run `/spec-kitty.charter` so the agent can capture guidance, run `spec-kitty charter interview --defaults` ..." as if both were shell commands. **After:** every such hint names the surface — "Run `/spec-kitty.charter` inside your coding agent (Claude Code, Codex, Cursor) ... run `spec-kitty charter interview --defaults` here ..." — across `charter generate`, `implement`, `research`, the plan-unfilled check, the mission-ticket and removed-`mission switch` hints, the `init` mission-template note, the implement analysis gate, and the dashboard's next-action line. Shell alternatives are unchanged.
- **`spec-kitty agent tasks status` no longer needs `--mission` when there is only one active mission** (#4677). **Before:** the help's own first example (`spec-kitty agent tasks status`) exited 1 with `--mission <slug> is required`, even in a project with a single mission, and `--mission` was listed as an ordinary option. **After:** with exactly one mission that is not completed (merged, or every work package terminal), the command defaults to it; with zero or several active missions the existing error is unchanged, and the help now says when the flag can be omitted.
- **A corrupt per-mission state file fails closed with a clean operator error instead of crashing with a raw traceback** (#4642). A malformed-JSON, non-UTF-8, or wrong-shape `meta.json` or `decisions/index.json` (realistic after a partial write or merge conflict) crashed two command paths. **Before:** `spec-kitty next` — the central agent control loop — died with an uncaught `MissionMetaReadError` traceback on a corrupt `meta.json`, and `spec-kitty agent decision verify`/`resolve` (and the other decision subcommands) died with a raw `JSONDecodeError`/`UnicodeDecodeError`/pydantic `ValidationError` on a corrupt `decisions/index.json`. **After:** both fail closed — a single operator-readable error naming the corrupt file plus the `run: spec-kitty doctor` hint, exit 1, no traceback (a valid JSON error payload under `--json`). `next` now catches `MissionMetaReadError` at the real downstream escape site (the query-mode/`decide_next` calls, not the slug-resolution guard), and `decisions/store.py:load_index` wraps its decode/validate into a typed `DecisionIndexReadError` (reusing the canonical kernel decoder), fixing all six decision subcommands at the one reader. The four `orchestrator-api` decision write verbs (open/resolve/defer/cancel-decision) — a JSON-first machine-contract surface — now fail closed with a valid error payload too, instead of leaking a raw traceback with empty output. Mirrors the existing `MissionMetaReadError` precedent; the remaining un-guarded readers (the interview and accept-gate command paths) are tracked as a follow-up hardening mission subsuming #4600 and #4642. Red-first `@pytest.mark.regression` coverage drives the real commands over all three corruption classes.
- **`spec-kitty upgrade --help` points at documentation that exists again** (#4688). Its "See also" line named `docs/guides/install-and-upgrade.md`, a path that no longer exists; it now names `docs/guides/how-to/installation/install-and-upgrade.md`, where the install-and-upgrade guide lives, and a test keeps every documentation path in that help text honest.
- **`spec-kitty charter sync` now says it is a no-op instead of looking like a failure** (#4679). The command is kept for compatibility only: the charter.md-to-YAML extraction it used to perform is retired, so there is never anything to sync. **Before:** it printed a red `Charter was not synced` and exited 1 (or reported `success: false` under `--json`), which reads as something to fix. **After:** it prints an explicit `No-op:` line and exits 0, `--json` reports `result: "noop"` / `success: true` with the same message, and the `--help` text and `--force` description no longer claim it syncs anything.
- **A bare `spec-kitty doctor` no longer looks like a passing health check** (#4678). The group runs nothing by itself — every diagnostic is a subcommand. **Before:** `spec-kitty doctor` printed the help and exited 0, indistinguishable from a check that ran and passed. **After:** it still lists the available diagnostics, but states that no diagnostic ran and exits 2 (usage error), so neither a person nor a script can mistake it for a clean bill of health. Every `spec-kitty doctor <subcommand>` is unchanged.
- **`spec-kitty doctor ops --close-stale` no longer slows down quadratically as the closure history grows** (#4424). A sweep closes each stale Op through one executor, but the shared idempotency guard re-read the entire append-only closure spine (`kitty-ops/op-closures.jsonl`) once per Op. **Before:** closing N stale Ops re-parsed the ever-growing spine N times — O(N²) — so a large backlog on a long-lived project made the sweep drag. **After:** the sweep reads the spine once into a per-run snapshot and extends it after each close, so the whole sweep is linear; a pinning test asserts exactly one spine read per sweep. The individual-agent close path is unchanged (it reads fresh — a single close has no such cost), and Op-close idempotency is preserved.
- **The session orientation block can report `upgrade-available` again instead of always saying `healthy`** (#4707). The banner derives its health from a background version cache, but that cache was written for the stable channel only and an out-of-date cached version was never refreshed — so the health line was pinned to `(healthy)` even when an upgrade was published. **Before:** the orientation block never surfaced an available upgrade. **After:** the cache refresh queries the configured release channel and records that channel with the result, a cache written for a different channel is rejected, and a cache past its TTL triggers a background refresh while still returning the last known version — so `health` reflects a real upgrade. SessionStart stays free of foreground network calls (the refresh is a detached, fire-and-forget subprocess, at most one per session).
- **A yanked pre-release no longer shadows the real latest version on the pre-release channel** (#4705). Version selection took the highest version across every entry in PyPI's release list, without checking whether any of its files were still installable — so a fully **yanked** pre-release (`4.2.0a1`) outranked the live `4.0.0rc3`, even though `pip`, reading the same index, correctly skips it. **Before:** an opted-in pre-release user was told to "upgrade" to a version that cannot be installed. **After:** a shared `installable_release_versions()` filter (PEP 592) drops releases that have no files or only yanked files before picking the highest, and both the compatibility provider and the background upgrade probe use it, so they never disagree on what is installable. The stable channel is unchanged.
- **`spec-kitty upgrade --cli` and `upgrade --dry-run --json` report the real latest version again when output is piped or `CI` is set** (#4704). These are the environments agents and CI actually run in, and an explicit upgrade query is exactly when you want the answer. **Before:** an over-correction (the earlier RISK-3 nag-suppression fix) routed explicit queries through the same network suppression as the passive per-command nag, so under a redirected stdout or `CI=1`, `upgrade --cli` printed no guidance and `upgrade --dry-run --json` reported a null version and `is_outdated: false` — silently wrong. **After:** an explicit query resolves the latest published version regardless of TTY/CI (fail-soft — the provider has a 2-second timeout and returns nothing on error), while the passive nag stays suppressed exactly as before and the read-only query never writes the nag cache. Nag preferences and a fresh nag cache no longer mask the factual status of an explicit query.
- **`agent action implement --agent <tool:model:profile:role>` completes on first use instead of rejecting its own claim** (#4665). A fresh implementation claim with the documented compact agent identity created the lane, moved the WP to `in_progress`, then refused its own claim and printed no prompt. **Before:** the compact-string workspace-create claim recorded the actor verbatim while the workflow claim recorded a structured dict; the ownership comparison projected the dict to its bare tool but the string verbatim, so the two representations of one agent compared unequal and raised `WorkPackageClaimConflict`. **After:** the CLI-local claim-comparison layer (`_actor_key`) parses a compact-string actor to the same tool-scoped key a dict yields, so a first-time full-identity claim renders the prompt in one invocation; same-identity resume stays idempotent, a genuinely different agent is still refused, the generic-actor re-claim allowance is preserved, and the shared identity projection is left byte-unchanged.
- **An agent's review verdict is attributed to the reviewing agent, not the configured Git user** (#4670). The generated review-completion command omitted `--agent`, so running it recorded the verdict as `actor.tool: user` with null model/profile even though an independent agent performed the review. **Before:** approvals and rejections were misattributed to the Git user whenever the generated command was used as printed. **After:** an agent-driven completion that omits `--agent` resolves the active claimed reviewer from the event log, and the generated completion commands (both approve and the `--to planned` rejection) carry the resolved identity through a single render seam; genuine human approvals stay attributed to the human, the review evidence is retained, and no historical event is rewritten.
- **A fix-mode implementation claim after a rejection records the new implementer, so the correction submits for review without `--force`** (#4673). After a reviewer rejected a WP and an implementer successfully claimed it in fix mode, the reduced ownership still pointed at the previous reviewer and the ordinary `move-task --to for_review --agent <implementer>` was refused. **Before:** the rejection's runtime delta re-stamped the reviewer into the very delta that released the claim (defeating the release), and the move-task ownership guard compared identities by raw string. **After:** the rejection no longer re-stamps the reviewer when the same identity rolls the WP back (the release takes effect), the fix-mode claim's owner folds through the same latest-wins per-transition channel the role slot already uses, and the move-task ownership guard reconciles identity representations through the tool-scoped key; a genuinely different agent is still refused.
- **`move-task --agent <identity>` persists the acting identity into the reduced ownership slot** (#3029, representation half — verified). The originally-reported "no agent key at all" symptom is stale on the 4.0.0rc4 line: the claim fold and the per-transition runtime delta already persist the acting identity, and a downstream ownership check enforces it (a differing agent is refused). A characterization regression pins the behavior; no code change was required.
- **The session orientation block shows your real project name again instead of `project: unknown`** (#4706). The SessionStart banner read the project slug off `AgentConfig`, which has no such field, so it always fell back to `unknown` (a regression introduced in 3.2.7). **Before:** every session opened with `project: unknown (healthy)` regardless of the project you were in. **After:** the banner reads `project.slug` through the canonical project-identity loader (`.kittify/config.yaml`) — the same source the rest of the CLI uses — and the dry-run preview now reads that same source too, so live and preview agree. A project without a persisted slug still renders `unknown`, which is the honest value.
- **Shell-completion help text is refreshed, and a stale completion manifest can no longer sit red on `main` unnoticed** (#4479; narrow part of #4374). The pre-generated completion manifest (`_completion_manifest.json`, shipped in the wheel so `spec-kitty` shell completion serves command metadata without importing the whole CLI) had drifted from the live CLI help in four commands: `agent tests stale-check` was missing its `info` confidence level, `context info` and `context mission-resolve` still carried legacy `feature` wording and example slugs (`010-feature-lane-a`, `057-my-feature`), and `zeitgeist status` showed an outdated one-line description. **Before:** the drift only reddened under `make test-full` — the parity test's directory is recorded out-of-matrix, so no per-PR lane selected it, and the sibling CLI-reference gate checks command-path presence but not help *text* — so it sat red on `main` unnoticed. **After:** the manifest is regenerated to match the live help (which also clears the forbidden `feature` wording from a shipped file), and a new always-on architectural gate (`test_completion_manifest_freshness.py`) reds every PR the moment the manifest drifts, help text included. The full 128-directory out-of-matrix promotion/retire sweep (#4374) remains a separate mission.
- **Spec Kitty is usable on Windows again — every command stopped failing with `[Errno 13] Permission denied`** (#4703). On Windows `msvcrt.locking()` is a *mandatory* lock, so when the runtime bootstrap held its own owner lock file (`%LOCALAPPDATA%\spec-kitty\cache\.update.lock`) and then re-read that same file during asset verification, the OS refused the read even to the locking process. **Before:** on 4.0.0rc3/rc4 every command except `--version` aborted with `RuntimeError: [Errno 13] Permission denied` and exit 1 — `ensure_runtime()` runs before every command, so the tool was completely unusable on Windows (3.2.7 worked; the regression arrived with the #4017 re-assess-under-lock landing, whose under-lock recheck first read the held lock — POSIX `flock` is advisory so the read succeeds there, which is why CI never caught it). **After:** the under-lock recheck no longer reads an owner lock file's own bytes in any of the three places it was read — `check_assets` skips the lock node (its parent directory's membership is still verified), and both the re-assessment's `finish()` and the batch-owner `include()` fallback record the lock by `lstat` only (`node_state(..., read_content=False)`). A lock file is a self-managed, definitionally-empty artifact whose content is never verified or used, so source-drift and concurrent-peer detection are unchanged. All three sites are shared across owners (runtime, global skills, global commands), so the same one fix covers every asset owner.
- **A swallowed asset-read failure now names the file it could not read** (#4703). **Before:** a `PermissionError` during recheck surfaced as the bare `[Errno 13] Permission denied` — a Windows `PermissionError` drops `exc.filename`, so the diagnostic named no path and the failure was undiagnosable as shipped. **After:** `check_assets` annotates a read failure with the offending path (`Could not read global asset <path>: ...`), which also sharpens diagnosis for the wider "Global asset input changed" recheck family (#3998, #4017).
- **`spec-kitty session-start` honours its unconditional exit-0 contract again** (#4703). The Claude Code `SessionStart` hook documents that it must never fail a session, but its exit-0 guard could not catch a failure in `main_callback` *before* dispatch. **Before:** `ensure_runtime()` (the Windows crash above) or the startup schema gate (`SystemExit` on a stale project) aborted the hook with exit 1. **After:** `session-start` gets the same startup-fast-path posture as the live-work hook — neither the global runtime repair nor the startup project gates run before it — so `session_start()` alone owns the exit-0 guarantee.
- **Upgrade/repair can delete read-only managed assets on Windows** (#4703 cross-OS family). Managed content is materialized read-only (`0o444`); Windows `DeleteFile`/`RemoveDirectory` refuse a read-only target (POSIX ignores the mode). **Before:** an upgrade or skill re-install that removed a stale managed asset could crash with `PermissionError`. **After:** every managed-asset delete (in `runtime/asset_preparation.py` and `skills/installer.py`) clears the write bit and retries — the same pattern already used for skill teardown, now applied to the delete sites that were missed.
- **The owner lock is acquired through a writable handle** (#4703 cross-OS family). **Before:** `recheck_assets` opened the lock read-only to lock it; POSIX `flock` allows that, but Windows `msvcrt.locking()` needs write access and is fragile on a read-only handle. **After:** the recheck opens the existing lock `r+`, aligning with the apply path's write handle.
- **Cold installs serialize concurrent runs on Windows too** (#4703 cross-OS family). **Before:** the cold-install serializer flock'd the anchor directory, which is POSIX-only — a first-time Windows install had no cross-process guard, so two concurrent cold installs could race. **After:** on Windows a machine-temp sentinel keyed to the anchor (kept out of the managed asset tree) serializes cold installers; the exclusive owner-lock create remains the final arbiter. (A related symlink-creation fallback for Windows without developer-mode privilege is tracked as a follow-up: a naive symlink→copy in the managed-asset writer would make re-assessment see a file where it expects a symlink and re-apply forever, so it needs the assessor's cooperation.)
- **The cross-OS lock, safe-delete, and OS-detection primitives now have one canonical owner each — the recurring Windows `PermissionError` class (root of #4703) is closed by construction** (#4714). #4703 kept recurring because file-locking, managed-asset deletion, and Windows detection were forked across the runtime with no canonical owner, so any site could reintroduce the mandatory-lock read crash or a boundary-leaking delete. **Before:** ~12 lock sites across three families (raw `msvcrt`/`fcntl`, the `filelock` library, a scoped `fcntl`); 3 duplicate safe-delete helpers with a silent contract split (one followed symlinks and cleared the *target's* write bit, a boundary leak); and 4 `is_windows`/`os.name`/`sys.platform` definitions. **After:** (1) one sync+async, sidecar-model lock primitive in `kernel/locks.py` that **structurally cannot expose a held lock for reading** — it yields only holder metadata, never a handle to the protected file, and derives/locks a dedicated `.lock` sidecar, so the #4703 read-your-own-held-lock shape is impossible by construction; (2) one `specify_cli/core/safe_delete.py` with the correct no-follow (`lstat` + `S_IMODE`, skip-symlink) contract; (3) one promoted `kernel/paths.py::is_windows()` seam that the routable OS-detection zoo now calls. Two non-vacuous DIRECTIVE_043 gates (`test_lock_primitive_ban.py`, `test_os_detection_ban.py`) ban raw locking and inline OS-detection outside their canonical modules and fail on any new site (empty allowlists). `filelock` is removed entirely — from runtime dependencies **and** the four test-infrastructure users, which migrated onto `kernel.locks` (closes #4719). Also folded: `tracker/credentials` now locks a sidecar instead of the credential payload (closing the #4703 shape there too); the kernel lock primitive hardens only lock directories it creates (never a shared cache dir); and the cold-install serializer uses one uniform machine-temp sentinel on both Windows and POSIX. Follow-up: #4727 (`windows_paths._current_platform` 3-way normalizer, gate-tracked fail-closed).
- **Consistent mission-handle resolution across CLI commands** (#4631, #4682). A
  nonexistent `--mission <handle>` now produces one clear `Mission not found:
  <handle>` across `research`, `plan`, `tasks`, and `merge` (fresh and
  `--resume`), matching the commands that were already correct. Previously
  `plan`/`tasks` misreported it as a multi-mission "pass --mission to
  disambiguate" ambiguity, `merge` blamed a missing `lanes.json`, and — most
  seriously — `research` silently scaffolded a phantom `kitty-specs/<handle>/`
  mission directory. `research` (and every in-scope command) now refuses before
  writing anything; `merge --abort` stays tolerant of an unresolvable handle;
  the identity-aware "run `spec-kitty migrate backfill-identity`" remediation and
  `reconcile`'s distinct "dossier not found" wording are preserved. Bare
  `spec-kitty next` (no `--mission`) now discovers missions — auto-selecting the
  sole mission, listing available handles (`slug (mid8) — name`, legacy missions
  included) when several exist, or pointing to `specify` when none do — instead
  of dead-ending on a `--mission is required` usage error.
- **An ambiguous `--mission <handle>` now says so instead of "not found"** (#4723).
  When a bare human slug matches more than one mission (e.g. two `payment-*`
  missions, both typed as `--mission payment`), every command **before** reported
  `Mission not found: payment` — telling you nothing matched when in fact several
  did, and pointing at a recovery command that could not reveal the collision.
  **After:** the commands surface the ambiguity (`Mission handle 'payment' matches
  multiple missions: … — re-run with a more specific handle`) and name the
  colliding handles, matching how an ambiguous `mid8`/numeric handle already
  behaved. The misleading not-found hint also changed from `spec-kitty mission
  list` (which lists mission *types*) to `spec-kitty doctor topology` (which lists
  real mission handles).
- **`spec-kitty doctor mission-state` now repairs a legacy `change_mode` instead
  of aborting, normalizing it to absent**; `--fix` and `--teamspace-dry-run`
  report per-mission detail in the terminal and `--json` (dry-run parity), so
  triage no longer requires reading a gitignored manifest; aligned the
  bulk-edit-gate reader so normalization is behavior-preserving (#4778, #4780,
  #4779).

## [4.0.0rc3] - 2026-09-15

Third public release candidate for the Team Kitty 4.x line, cut from `main` for
the MVP launch cold-start walkthrough. This is a testing prerelease, not stable
launch acceptance. Install explicitly with `uv tool install 'spec-kitty-cli==4.0.0rc3'`.

### Changed

- **Built-in minutes agent is now `minutes-mahad` (chat-first, dual format).** The profile formerly shipped as `minutes-maker-mahad` is renamed to `minutes-mahad` / Minutes Mahad. It asks whether to produce decision minutes or discussion notes, posts one validated Markdown response in the originating chat, and treats wiki/knowledge-base publication as optional human-operated reuse of that Markdown. Companion doctrine: `ACTION_ITEM_ATTRIBUTION`, `MINUTES_STAND_ALONE`, paradigm `extract-then-publish-separation`, updated `meeting-minutes-pipeline` / `meeting-minutes-format`, and templates `meeting-minutes.md` plus `meeting-discussion-notes.md`. No Confluence, MCP, or vendor publisher is shipped in the built-in pack.
- **The release runbook now opens the next development cycle right after every tag** (#4314). `RELEASE_CHECKLIST.md` gains Release Process step 8, "Open the Next Development Cycle", mirrored in the Release Process summary in `docs/development/contributing.md`. Branch-mode release validation requires `main`'s version to advance beyond the latest tag, so the scheduled Release Readiness Check went red after `v4.0.0rc1` and again after `v4.0.0rc2` until the next cycle opened (#4290, fixed for rc3 by #4313). The step lists the edits that open a cycle — the next version in `pyproject.toml`, the project entry in `uv.lock` and `.kittify/metadata.yaml`, and a new `## [Unreleased] - <next version>` heading — and a release test now pins it in both documents.

- **A green test run no longer counts as a typecheck when a mission changes typed sources (`#4191`; DIRECTIVE_030).** **Before:** the quality gate treated the test runner as the whole story, so a work package whose Vitest/Jest/pytest suite passed could be handed off and accepted even though the project's compiler would have flagged unused locals/parameters or other diagnostics a runner never applies. **After:** DIRECTIVE_030, the implement/review/accept skills, the quality-gate-verification tactic, and the software-dev work-package template all state that when typed sources change the implementer runs the project's configured compiler typecheck (`npm run typecheck`, `tsc -b`, or `tsc --noEmit`, matching CI) and records its exit code, and a reviewer rejects a work package where that check was skipped, is red, or was masked by a fallback command. This is doctrine/prompt guidance only — no CLI behavior changes.

- **Every pull request now measures its tests once instead of twice** (#4334). The per-PR SonarCloud reporter in `ci-quality.yml` re-ran the fast test tier under coverage to build its own report — a median of **22m32s** per pull request (n=12, 2026-09-10..14) duplicating work the `CI Modules` shard matrix had already done for the same commit. That job is retired; the per-change report is now a `sonar-pr` job in `ci-aggregate.yml` consuming the coverage the matrix already produced, on the existing `workflow_run` chain. `ci-quality.yml` drops from six jobs to five.

- **Coverage measurement is no longer truncated at module boundaries** (#4334). Each shard measured only its own module's package, so a line a test executed in *another* module was silently **dropped** rather than recorded as uncovered — leaving 58 of 72 `specify_cli` subpackages measured only through one broad-target row whose tests do not exercise them. Shards now measure the full top-level package set derived from `src/`; one representative shard alone recovered **30,226** cross-module covered statements. Registry `cov_targets` keep their meaning as census-derived ownership records and are unchanged. Measured cost is **+7.8% to +11.6%** per shard with the reconciled artefact set growing roughly six-fold — traded deliberately for measurement accuracy.

- **`tests/unit` and `tests/specify_cli/runtime` are declared in the CI module registry** (#4334). They previously ran per-change only through the retired job's fast tier, so retiring it would have removed their per-change execution.

- **Four census-count architectural gates that demanded manual re-pins on ordinary changes are retired, keeping only checks with a real defect-catch record** (#4315, adjudicated by ADR `2026-09-14-1`). The routed-`meta.json`-read floor (`ROUTED_LOAD_META_FLOOR`) is deleted outright rather than re-pinned — it had been re-pinned 23 times in 63 days for zero catches, and once failed a build for reading `meta.json` through the canonical reader the gate exists to reward; re-pinning it would only keep its vocabulary and ADR alive as load-bearing for the next person to move the count. The advisory golden-count gate is deleted outright, and its 381 `# golden-count: cardinality-is-contract` annotations are swept from 190 test files; the C-007 enforcement canon it sat beside is preserved. The `arch_shard_*` / `next_shard_*` marker family and its hand-maintained assignment tables are removed — no live CI job has selected those shards since the pre-programme workflows were deleted. The genuinely protective checks — the inline-`meta.json`-read ceiling with its allowlist stale-entry detection, the tier-marker and module-shard completeness gates, and the four enforcement allowlists — are untouched and still blocking. Net: ~2,050 fewer lines of gate machinery and zero new pinned integers. Supersedes #3977 and #3927.

### Added

- **`spec-kitty doctor bytecode` flags a corrupt installed-package `.pyc` before it crashes every command** (#4130; complements #4124). A truncated `pip`/`uv tool install` write — common on Windows under file-locking or antivirus — can leave a `__pycache__/*.pyc` whose 16-byte header Python still trusts but whose body no longer unmarshals, so the next import dies with a raw `bad marshal data` / `co_filename` traceback that names no fix and takes down *every* command, not just the one that touched the cache. The reactive self-heal from #4124 recovers at crash time; this adds the proactive counterpart — a read-only audit that scans the installed package and reports each corrupt cache file with a delete-the-`.pyc` hint (Python recompiles from source on the next import), in human or `--json` form. A cache Python would recompile anyway (bad magic, stale timestamp/size) is deliberately not flagged, since it never bites. The command never deletes anything and exits 1 when a finding is present, so CI can gate on it.

- **`spec-kitty agent decision list` lists a mission's recorded decision moments** (#3951). The `agent decision` subgroup previously had no read command — an orchestrating agent asking "what decisions exist for this mission" hit `No such command` and had to read `decisions/index.json` by hand. The new read-only subcommand resolves the mission through the same guarded read-path seam as `verify`, supports an optional `--status open|resolved|deferred|canceled` filter, and emits one JSON document (`decision_list_v1`) with the count and each decision's id, status, question, and answer fields; a mission with no decisions yet lists cleanly with count 0.

- **`spec-kitty next` publishes the six runtime moments to the team's Zeitgeist relay** (#3929): mission run started/completed, step issued/auto-completed, and decision input requested/answered. A producer registered at the runtime emitter seam publishes each transition the runtime journals through the existing bounded lifecycle fan-out, under the journal record's own timestamp and an `event_id` derived from that record, so a re-emitted transition is the same moment. Decision question, option and answer text stay out of moment attrs, and relay or credential failures never change local runtime state.

- **LLxprt Code (`--ai llxprt`) is now a supported agent.** `spec-kitty init --ai llxprt` installs the canonical Spec Kitty slash commands as TOML custom commands under `.llxprt/commands/`, and `spec-kitty agent config add llxprt` wires it into an existing project. LLxprt Code is a fork of Gemini CLI, so it reads the same command schema (`prompt`, optional `description`, `{{args}}` placeholder) and the commands appear as `/spec-kitty.*`. User-global commands are installed to the envPaths('llxprt-code') config root (`~/Library/Preferences/llxprt-code/commands/` on macOS, `~/.config/llxprt-code/commands/` on Linux, overridable via `LLXPRT_CONFIG_HOME`) — the legacy `~/.llxprt/` tree is migrated away by llxprt itself and is no longer read. LLxprt also consumes `SKILL.md` Agent Skills, so it is registered as a shared-root skill agent (`.agents/skills/` plus its own `.llxprt/skills/`): an llxprt project now receives the Spec Kitty skill pack in the cross-tool `.agents/skills/` root, and skill upgrades also sweep `.llxprt/skills/`. Session presence writes to `LLXPRT.md`, and `spec-kitty verify-setup` reports whether the `llxprt` binary is installed. The charter agent dispatch matrix now also instructs an agent to call `todo_pause` with the question as the reason before asking a user process question under llxprt, since the todo continuation auto-advances any turn that ends without a tool call.

- **`spec-kitty charter org init` can now render an org doctrine pack from a local directory or git template, not just the fixed minimal scaffold** (#2719; closes #2718). **Before:** `org init` only wrote the three-file skeleton (`org-charter.yaml`, `drg/fragment.yaml`, `README.md`), so an operator standing up an organization's doctrine from an existing template had to copy and rewrite the tree by hand. **After:** `spec-kitty charter org init <path> --template <src> --org-name <name>` (also reachable through the deprecated `spec-kitty doctrine org init`) copies a local or git template — HTTPS or SSH, selecting a branch via `--branch` or a `#ref`/`@ref` suffix — honouring `.templateignore` (and always excluding `.git/` and `.templateignore`) and substituting `{{ORG_NAME}}`/`{{LOCAL_PATH}}` into the rendered pack. Rendering is fail-closed and atomic: the org name and paths are validated up front, the tree is staged beside the destination and promoted with a same-filesystem rename, the prior pack is restored if a forced replacement fails, and overlapping source/output paths, destination symlinks, option-like git refs, and malformed template URLs are refused before anything is written. HTTPS template fetches do not inject `GIT_TOKEN`. Omitting `--template` keeps today's minimal scaffold unchanged.

- **Discarding a mission with `spec-kitty mission close --discard` now takes it off the dashboard** (#704). The command already deleted the mission's branches and worktrees, but the mission kept showing on the dashboard as live work. It is now marked discarded and filtered from the dashboard's mission list; its `kitty-specs/<slug>/` files stay on disk on purpose, so the abandonment retrospective survives.
- **A permanent fault-injection battery against duplicate suite execution** (#4334). `tests/architectural/test_no_duplicate_suite_execution.py` fails on every way the duplicate could return — canonical, inlined, behind a shell/script/make indirection, or in a net-new workflow file — and on removal of either declaration keeping the report advisory. The workflow-trigger classifier fails **closed**: list-form, bare-scalar, `pull_request_target`, `merge_group`, malformed and absent `on:` blocks all count as change-triggered, so a duplicate cannot hide behind an ordinary trigger spelling.

- **A derived pinning-rule inventory** (#4334). `scripts/ci/derive_pinning_inventory.py` mechanically derives every rule pinning the CI job topology (102 sites, 43 real dependencies) into `tests/release/pinning_rule_inventory.json`, each with an explicit disposition, and a freshness gate re-derives and diffs it. Rules that go red are caught by CI; rules that go *greener by deletion* previously were not.

- **A reproducible shard-timings capture script** (#4334). `scripts/ci/capture_shard_timings.py` replaces ad-hoc tooling that no longer existed in the tree, so `.github/ci-shard-timings.json` can be regenerated rather than reconstructed by archaeology.

- **Live Work harness capture: `spec-kitty live-work` publishes supported agent-harness activity (tools, files, tests, delegation) and retrospective outcomes as live Zeitgeist relay frames through the existing `event.publish` path** (#4268, re-scoped 2026-09-14 per planning#2269 — Zeitgeist carries NOW, Git carries DONE; no local journal, spool, or durable offsets anywhere). A new `specify_cli.live_work` package owns the canonical hook-adapter API (`get_adapter`), the Claude Code hook adapter (SessionStart/SessionEnd/PreToolUse/PostToolUse → session, tool, file, test, and delegation observations with exact session attribution), the Codex `notify` adapter (turn-level only — its tool/file/test non-observability is an explicit matrix row, never laundered), an executable capability matrix (`live-work matrix` exits non-zero when a configured harness has no capture hooks — no silent green), content-safety redaction (token-bearing arguments, secret files, env values, raw output, and private reasoning never enter a frame; repository-relative paths and sanitized command summaries do — including `Bearer`/JWT tokens in any `-H`/`--header` form, basic-auth `user:pass` after `-u`/`--user`, and URL userinfo, #4353 fix round), edit-burst coalescing (first edit publishes promptly; repeats coalesce into one count/interval/delta update), mission-worktree binding resolution (a mission is bound only from a worktree's own confirmed identity, never guessed), the labeled repository-watcher fallback (`live-work watch` — changed files only, sampled attribution, never claims reads), and hook installation (`live-work install/uninstall`, reusing the canonical Claude settings registrar and a comment-preserving Codex config.toml merge). Frames carry the shared `WorkObservation` contract's exact `work.<kind>.v1` payload IDs (events 10.1.0, events#55/#56); the typed codec is capability-gated on the installed events version per that contract's own COMPATIBILITY rule and planning#2000's launch-train pin (`spec-kitty-events>=9,<10`), so the gate state is a visible matrix row, not a silent green. The retrospective captured/failed/skipped seam now publishes its outcome frame after the local append (the folded #4267 lifecycle continuity). The capability matrix also carries the whole-mission lifecycle family demanded by #4268's 2026-09-14 clarification: first specify, plan, task generation, implementation, review/rework, acceptance/merge and retrospective, each mapped to the existing event contract, the concrete producer seam, and the live consumer — with the phases that have no live producer (review/rework, acceptance/merge) explicit `not_observable` rows, never silence. The bounded wake-up retry stays #4311's shared mechanism — this publisher makes exactly one offer per frame and never builds a second retry loop. The `live-work hook` invocation takes the `next` command's startup fast path (#4353 fix round): only the live-work group is registered, the init/charter import chain and the global runtime bootstrap stay unloaded, and neither startup gate runs (the schema gate's `SystemExit` would break the hook's own always-exit-0 contract) — so the 4 s hook budget bounds the capture work itself instead of a ~12 s command-registry import that preceded it.

### Fixed

- **Approving or rejecting a work package with a long review note no longer silently drops its Team Kitty status broadcast** (#3954). **Before:** a `WPStatusChanged` moment whose `review_ref` carried a review note longer than 240 UTF-8 bytes made the events codec raise on the over-bound attr, so the CLI dropped the whole moment and the team relay never saw the transition — every approval or rejection with a real review note went unbroadcast. **After:** the wire projection bounds only legacy-prose `review_ref` (whitespace collapsed to one line, then capped at 240 UTF-8 bytes with a trailing `…`, codepoint-safe, byte-identical to the codec's own truncation) so the moment broadcasts, while the canonical local status event log keeps the full note untouched; pointer-shaped values ride verbatim, and there is still exactly one publish offer per emitted event. This is the MVP interim fix — the structural replacement (a dedicated CLI-validated `summary` attr with `review_ref` restored to pointer-only) stays tracked in #4327.
- **A corrupt `.kittify/config.yaml` no longer bricks every `spec-kitty` command** (cli-boundary-robustness; #4600, #4601, #4643, #4597, #4598, #4533, #4532). **Before:** if the project config held non-UTF-8 bytes or malformed content, startup raised an uncaught error that took down **every** command — including `--version` and `doctor`, the operator's own repair path. **After:** commands that do not need config content (`--version`, `doctor`) survive, and commands that genuinely need it fail with a message that names the offending file and the decode/encoding problem — never a raw traceback. Malformed-but-readable config degrades to a named domain error instead of a crash. Git-encoding and env-file reads on the same boundary were hardened alongside.
- **`spec-kitty … --json` now emits valid JSON on every exit path** (cli-boundary-robustness; #4643, #4533). **Before:** several commands printed human prose to stdout, or emitted a partial/empty envelope, on their error, empty, and zero-result paths — so a machine consumer parsing `--json` received a broken payload (for example, a zero-work-package status exited non-zero instead of returning a well-formed empty result). **After:** stdout is well-formed JSON on success, error, and empty paths alike, with human text routed to stderr, across the affected command surfaces (context, dashboard, doctor, doctrine, glossary, materialize, mission-type, archive, agent tasks).
- **Command defaults no longer leak an internal placeholder as a real value** (cli-boundary-robustness; #4601, #4597, #4598). **Before:** on paths reached off the normal argument-binding flow, an internal `OptionInfo` sentinel could reach command output or logic as though it were a resolved value. **After:** the resolved default is used and no internal placeholder reaches output or program logic.

- **`spec-kitty doctor mission-state --audit` no longer flags a completed mission's frozen snapshot as a TeamSpace blocker** (#4690). **Before:** the audit raised a hard `SNAPSHOT_DRIFT` teamspace-blocker whenever a mission's committed `status.json` no longer matched the current status reducer — including for **completed, archived** missions under `kitty-specs/`, whose dossiers are immutable (the archive-preservation gate forbids editing them). The drift was therefore unfixable yet permanently red'd the corpus audit on every pull request. **After:** for a mission whose every work package has reached `done` (the reducer's own authoritative view), snapshot drift is reported as a non-blocking `SNAPSHOT_DRIFT_TERMINAL` **warning** instead of a blocking error — the drift stays visible but no longer gates TeamSpace readiness. Active (in-progress) missions are unchanged: their drift is a live staleness bug and still raises the hard `SNAPSHOT_DRIFT` error, since regenerating the snapshot before merge is the fix.

- **A blocked `spec-kitty next` decision now names where each unmet guard looked** (#3883). **Before:** when `next --result success` blocked at review, the operator saw only `Guards pending:` with the guard names — even when the guard was looking for an artifact its own query mode reported present — leaving no way to see *what path* the guard checked and no recovery signal (a #3883 P0 dead-end). **After:** each pending guard renders `- <name>: looked for <path>`, so the operator can see the exact path the guard evaluated and reconcile it against what exists. The advance path (`--result …`) carries these paths; query mode is unchanged (see the PR note).

- **The mission dashboard no longer serves files from outside a mission's artifact directory** (#4249). **Before:** the dashboard's artifact endpoints — the `contracts`, `checklists`, and `research` listing and file-download routes — confined a file request only to the mission root, so a `..`-relative path could reach a file in a *different* artifact directory of the same mission, and a symlinked artifact root (or an individual symlinked file inside one) could escape the mission tree entirely; a symlinked `research/` directory could even 500 the endpoint. **After:** every listing entry and file read must resolve below **both** the mission root **and** the named artifact directory, reusing the canonical `ensure_within_directory` containment seam and failing closed on any unresolvable path (including a symlink loop) — a request that escapes either boundary now returns `404`. The same pass also rejects non-canonical `.kittify/scripts/` references in the packaging manifest (a `..` traversal in a command-template `sh:` frontmatter no longer enters the manifest), fixes a fragile invocation-log filter that hid any log whose name contained `index` (such as `reindex.jsonl`), and simplifies two upgrade-migration guards without changing their behaviour.

- **`spec-kitty accept` no longer rejects a mission whose approved lane introduces the first `tests/` or `docs/` tree** (#4254). **Before:** strict acceptance validated mission-declared build paths against the canonical **primary checkout**, which is evaluated *before* the approved lane's source is integrated — so a lane that added the repository's first `tests/` and `docs/` failed acceptance because those paths did not yet exist in the pre-integration tree. **After:** acceptance also checks the tree actually being accepted (the approved lane's `candidate_source_roots`), so a build path satisfied by the candidate tree passes; mission-artifact paths are still validated strictly and are never satisfied by a lane worktree.

- **`spec-kitty charter activate` no longer silently deactivates everything else in force when a kind has no explicit activation set** (#4253). **Before:** activating one artifact for a kind whose `config.yaml` activation key was absent treated the absent key as "start from the default pack" and wrote a bare one-element list — silently dropping every *effective* artifact outside `default.yaml` (observed: 15 directives and 11 procedures, including adversarial-squad-deployment, lost on a single unrelated activation). **After:** an absent key is correctly read as the unrestricted state, so the first activation materializes everything currently in force (the resolver's effective set, spanning the full declared org chain and in the keyspace it filters on) and appends the new artifact — nothing in force is deactivated. Unknown-id validation still runs first (nothing is written on a bad id), and an already-restricted key behaves exactly as before.

- **`spec-kitty doctor coordination --fix --mission <slug>` no longer rewrites every other mission's `meta.json`** (#4501; fixes #4050). **Before:** a single mission-scoped invocation stamped `topology` and `flattened` into 77 missions' `meta.json`, 76 of them unrelated to the selected mission — the flatten and its topology backfill walked the whole repository instead of the `--mission` scope, and the saas repo had to revert those files by hand (saas#1465). **After:** the `--fix` flatten and topology backfill are bounded to the selected mission; an unrelated mission's `meta.json` stays byte-unchanged while the scoped mission's own topology is re-derived, and a regression test pins both directions.

- **`spec-kitty agent acceptance-verdict` now runs at the `agent` level next to `issue-verdict`** (#3951). **Before:** the two verdict commands lived at different nesting levels — `agent issue-verdict` but `agent mission acceptance-verdict` only — so an agent following the one-level pattern of `agent --help` hit `No such command` for the sibling. **After:** both verdict commands resolve at the `agent` level; the `agent mission acceptance-verdict` registration stays (mission-step prompts and the docs name it).

- **The issue-matrix approve-gate blocker now names the command that fills a verdict row** (#3951). **Before:** the blocker said only "Fill in verdicts before approving", so orchestrating agents guessed at `agent mission issue-verdict` / `agent tasks issue-verdict` — both `No such command` — and lost round-trips per mission. **After:** both the unresolved-entries and the missing-artifact blocker carry the runnable remedy, `spec-kitty agent issue-verdict --mission <handle> --issue <#NNN> --verdict <fixed|verified-already-fixed|deferred-with-followup|in-mission> --actor <actor>`, alongside the existing regenerate hint.

- **Mission-agnostic commands now accept-and-ignore `--mission` instead of exiting 2** (fixes #3953). **Before:** the shipped mission-step skill text instructs agents to pass `--mission <handle>` to *every* spec-kitty command in multi-mission repos, but any command that is not mission-scoped rejected it — `spec-kitty agent profile list --mission …` exited 2 with `No such option: --mission`, contradicting the skill text once per session. **After:** every leaf command that does not declare a real `--mission` (matched by option name, since several declare it behind a `feature` parameter) gets a hidden, non-exposed `--mission` option: the value parses and is discarded, the callback never sees it, `--help` output is unchanged, and `--mission` without a value still fails loudly rather than becoming a silent boolean flag. Both leaf shapes are covered — registered commands (`agent profile list`) via a `MissionAgnosticCommand` class and callback-owned sub-apps (`charter list`) via a `MissionAgnosticGroup` class — and a tree-wide guard test pins the invariant that no command a step prompt can name exits 2 on `--mission` alone. Mission-scoped commands are byte-identical: their real `--mission` still reaches the callback.

- **A machine login that cannot reach the SaaS now names the network fix instead of a generic auth error** (#4465; closes #4308). **Before:** `spec-kitty login --machine` caught `AuthenticationError` before its subclass `NetworkError`, so a connection failure — DNS, a firewall, or a wrong `SPEC_KITTY_SAAS_URL` on a CI runner — fell through to the generic "Network error exchanging machine credentials" line and never reached the tailored guidance; the operator was told nothing about checking the URL or network access, and the transport exception was rendered through Rich un-escaped. **After:** the network branch is caught first, so a failure prints "Could not reach the SaaS: …" followed by "Check SPEC_KITTY_SAAS_URL and network access from this runner.", with the exception text Rich-escaped like the adjacent authentication boundary. The flow still exits non-zero, writes no session, and keeps the client secret out of the output; a new end-to-end regression drives a real `httpx.ConnectError` through the CLI to prove the previously unreachable branch.

- **`spec-kitty init` no longer aborts when Git is missing or its local config is unusable** (#4481; closes #4159). **Before:** init wired the custom merge drivers into git config as a best-effort step, but if the `git` binary had disappeared after detection, or a stale `.git` entry made `git config` fail, that optional step raised and turned a nearly-complete scaffold into a hard init failure — leaving the operator with a half-initialized project. **After:** the merge-driver wiring is caught as best-effort: init prints one warning ("Could not configure Spec Kitty merge drivers; continuing without local git configuration.") and finishes, and the merge path self-heals the config the next time it runs. Only the optional git-config step is softened — provisioning and every other init failure still stop init as before.

- **A pull request that changes only test files no longer wears a red CI aggregate gate it did not cause** (#4512). **Before:** a diff-scoped PR that selected zero modules (e.g. one touching only `tests/performance/`) correctly emptied `ci-modules.yml`'s shard matrix and skipped its test job by design — but GitHub Actions then emitted one placeholder job carrying the un-interpolated matrix template as its name (`module-tests (${{ matrix.module }} shard ${{ matrix.shard }})`), and the aggregate's artefact selector (`scripts/ci/select_source_artifacts.py`) raised `unrecognized module shard job name` on it, aborting the collect job before the selection-aware reconciler — which already tolerates zero selection — could run. Every test-only-path PR therefore went red on `ci-aggregate` through no fault of its own. **After:** the selector treats that un-interpolated placeholder as "no shard ran" and skips it, so a zero-selection PR aggregates green; genuinely malformed shard names still fail closed, and a regression test pins both directions.

- **`spec-kitty moments off --help` and `moments status` no longer name an internal command a user cannot run** (#4453; closes #4447). **Before:** both surfaces spelled out `spec-kitty zeitgeist mcp-serve` — a hidden MCP-launcher entry point that is not a public CLI surface — teaching a command path that only ever looks broken when typed by hand. **After:** they describe it as the internal agent-context bridge (`moments off`: "exits cleanly with one line"; `moments status`: "refuses to start while agents = off"), keeping the exact behaviour while keeping the hidden path out of user-facing output. This also restores the docs-freshness gate, which had gone red on `main` because the hidden name leaked into the generated CLI reference without an Internal banner.

- **`spec-kitty mission close --discard` no longer prints the mission ULID twice, and `implement`/review notices render instead of showing raw markup** (closes #4163, #4507). **Before:** the "Coordination worktree torn down for …" line composed the identity as `<slug>-<mid8>` even though the slug already embedded the mid8, so an operator saw the ULID doubled (`relcheck-01M21R2T-01M21R2T`); and `implement`'s three baseline notices plus the review-lock refusal were written with the builtin `print`, so Rich markup reached the terminal literally (`[dim]Baseline: …[/dim]`, `[red]…[/red]`). **After:** the teardown line — and the coordination-worktree-missing error message — compose the identity through the idempotent `coord_mission_dir_name` seam, so the mid8 appears exactly once for slugs with or without it embedded; and every notice renders through the CLI console seam with its exception text escaped, so a git refusal like `! [rejected] main -> main` is shown verbatim instead of losing its bracketed word or raising a misleading `MarkupError`. A regression guard also fails the build if a builtin `print()` under `cli/` ever carries Rich markup again. Output only; no behaviour, exit-code, or artifact change.
- **A workspace-allocation failure during `spec-kitty implement` left the work package stuck, and the only way out was to invent a review rejection that never happened** (#4245; closes #3937). **Before:** when allocation hit a dependency-lane or planning-commit merge conflict, the error handler moved the work package to `blocked` — even though it was still `planned` and the allocator had already cleaned up after itself. `blocked` cannot legally go back to `planned`, so every re-run printed "cannot start implementation" forever, and the one escape (`move-task --to planned`) demands a `--review-feedback-file` that cannot be skipped with `--force`. Clearing a tooling hiccup therefore meant writing a fake review finding, after which the claim ran in "Fix mode" as though a reviewer had rejected the work. **After:** an allocation failure leaves the work package `planned` and prints the conflict's actual resolution step, so a plain re-run works once the cause is fixed — the same behaviour the orchestrator-api path already had. The escape hatch is no longer reached, so nobody has to fabricate a review finding; the review-feedback gate itself is deliberately left exactly as it is, and #3937 stays open for the separate question of how that refusal should read.
- **Refusing `move-task --to planned` on a `blocked` work package no longer tells the operator to fabricate review feedback** (blocked-planned-refusal-message; #4689, closes #3937). **Before:** the refusal was source-blind — every lane got the same "Moving `<WP>` to 'planned' requires review feedback" message, even `blocked`, `canceled`, and `done`, where `planned` is not a legal target at all. For a `blocked` work package (the common tooling-hiccup case, now that #4245 keeps allocation failures in `planned`) that message pointed at the wrong recovery and trained operators to write a fake review file. **After:** the refusal is source-aware, message-only. When `planned` is a legal rollback target (`in_review`, `in_progress`, `approved`, `genesis`) the review-feedback message is unchanged; otherwise the message names the source lane's real legal targets read from the state machine itself — `blocked` points at the honest one-hop resume `--to in_progress`, and `canceled`/`done` are reported terminal. The guard stays unconditional and force-proof: every `--to planned` move without valid feedback still refuses, for every source lane, with and without `--force` — the source lane shapes only the words, never the decision. This closes the remaining F-51 half of #3937 (F-50 shipped in #4245).

- **`docs/development/reference/coverage-signals.md` described a pipeline that does not exist** (#4011). It claimed this repository runs no GitHub Actions, that diff-coverage and `sonar_project_version.py` were retired, and gave the wrong nightly schedule. Corrected against the live tree.

- **The gate model could not see a suite invocation reached through a make target** (#4334). `tests/architectural/_gate_coverage.py` now resolves make targets by reading the Makefile, and a `uv run --frozen pytest` invocation is no longer parsed as "no pytest command here" — a defect that had been hiding every gate in `ci-router.yml` and `packs.yml`. Before this, an assertion that `ci-quality.yml` ran no test suite passed while a 22-minute duplicate tier ran inside it.

### Known limitations

- The per-change Sonar report is **wired but not yet publishing**. SonarCloud Automatic Analysis is enabled on the project and refuses every CI-side upload (#4350); the project currently holds no coverage metric at all. This change makes the suite run once and connects the report to the existing measurement — it does **not** restore a published report, and a green pipeline is not evidence of publication. See also #4367 (further gate-model indirection forms), #4368 (packages with no declared routing group), #4351 and #4365 (pre-existing test gaps surfaced during the work).

### Fixed

- **The issue-matrix approve gate now names the file it actually reads and shows the exact rule each row broke** (#4330). **Before:** every approve-blocker message hardcoded `ERROR: issue-matrix.md`, but the gate reads the matrix JSON-first — so an operator on a JSON-format mission (every scaffolded and migrated mission) was sent hunting for an `issue-matrix.md` their mission does not have; and an unknown-verdict row was flattened to a bare `Unknown: #NNN` id list that dropped the concrete rule it violated, findable only by reading the validator source. **After:** the header names the artifact the gate resolves (`issue-matrix.json`, or the legacy `issue-matrix.md` only for an `.md`-only mission), and each failing row is surfaced verbatim with the rule it broke (e.g. `verdict is 'deferred-with-followup' but evidence_ref contains no follow-up handle`). Diagnostics only — the conditions that block approval, the read surface, and every pass/fail outcome are unchanged.
- **Built-in doctrine guidance no longer points at the retired `src/doctrine/<kind>.graph.yaml` fragment home** (#2715). The `common-docs-find` tactic and the `brownfield-onboarding` paradigm now name `packs/built-in/<kind>.graph.yaml`, and the agent-profile repository's lineage-graph docstring no longer describes a monolith that is gone. The dead-path architectural gate now also flags `doctrine/<kind>.graph.yaml` and `doctrine/*.graph.yaml` paths, not only the `doctrine/graph.yaml` monolith, and its failure message no longer recommends the dead path.
- **`spec-kitty specify` / `agent mission create` now refuse a silent duplicate of a live mission instead of creating a second mission under a different slug (`#4033`).** **Before:** running create twice for the same intent (same `mission_slug` **and** `mission_type`) produced two missions, both `{"result":"success"}`, both exit 0 — a trainee following the docs silently ended up with a duplicate. **After:** `create_mission_core` fails closed with `MissionCreationError` *before* any scaffold or branch is written when a live same-key mission exists, naming the existing mission (slug + `mid8`) and the `--allow-duplicate` override. An abandoned prior mission — explicitly canceled, or *genesis*-abandoned (zero lifecycle events **and** a spec that was never committed) — does not block a fresh create, so a bare never-used scaffold re-creates cleanly with no flag. The legitimate high-volume factory case is served by an explicit `--allow-duplicate` / `--allow-dup` flag on both `agent mission create` and `/spec-kitty.specify`, threaded to `create_mission_core(allow_duplicate=True)`; abandonment detection fails closed, so an indeterminate prior mission is treated as live and refused.

- **`spec-kitty merge` no longer lets an older mission-branch planning copy silently clobber a target-newer one during the squash** (#3942). The mission→target `git merge --squash -X theirs` step forces the source (mission branch) to win every add/add conflict, which is correct for source code and the driver-covered `kitty-specs/**` bookkeeping classes but false for PRIMARY-partition planning artifacts (`spec.md`, `plan.md`, `tasks/WP*.md`, `research/`, `data-model.md`) — those are authored on the primary/target surface, so the target can carry a legitimately newer copy. A merge driver cannot fix this (it sees only three blobs, no history), so target-newer recency is now resolved after the squash by a pure three-way rule (`src/specify_cli/merge/planning_recency.py`): a path is target-authoritative when the target diverged from the merge-base while the lane copy is base-or-ancestor, with committer-date (never mtime) as the tiebreak and the target winning on a tie. Preserved paths are amended into the single squash commit and reported to the operator, never silent (FR-002). Driver-covered reconcilers (#2709/#2804) are unchanged. Advances epic #2907.
- **The post-merge `merged_at` completion marker has a production writer again, and the merged-state guard is reopen-aware** (#4090). The primary-wins guard that re-anchors post-merge reads to the PRIMARY surface (`is_mission_merged` → `meta["merged_at"]`) had been dormant since its writer was deleted in #2258, so retrospect and doctor could still read a stale diverged coordination husk. The writer is restored as a sibling of `record_baseline_merge_commit` (`src/specify_cli/merge/baseline.py`), the meta-write authority — the executor is untouched — and `is_mission_merged` (`src/specify_cli/status/lifecycle.py`) is now event-sourced: a mission is merged iff `merged_at` is present and no later `MissionReopened` event postdates it, so a reopened mission correctly reads as not-merged and a re-merge re-stamps a fresh marker. Advances epic #2160 (keeps the single canonical post-merge authority on PRIMARY, overriding the husk rather than freshening it).
- **Characterization guard confirming post-merge `event_count` union consistency** (#4091, verified-already-fixed). `event_count` is by definition the count of unique `WPStatusChanged` transition events (annotations, lifecycle, and decision events are not transitions), and `_project_status_bookkeeping_to_target` already unions and re-reduces under a coordination husk. A red-first repro on a coord fixture confirmed the count is already correct on HEAD, so #4091 is closed with a regression-locking characterization test rather than a code change.

### Security

- **The three release-critical GitHub Actions workflows are hardened per SonarCloud, closing the surface deferred from #4342** (#4352). `release.yml`, `release-readiness.yml`, and `ci-nightly.yml` are not exercised by PR CI, so they were split out of the primary hardening mission for a manual dry-run before merge. **Before:** third-party actions floated on mutable tags (`astral-sh/setup-uv@v8.1.0`, `softprops/action-gh-release@v3.0.0`, `pypa/gh-action-pypi-publish@release/v1`, `dorny/paths-filter@v4`); `release.yml` granted `contents: write` workflow-wide; the release-readiness `workflow_dispatch` `inputs.tag` was interpolated straight into a shell `run:` body (a script-injection surface); and several installs were unpinned (`twine==6.*`/`tomli==2.*`, a bare `pip install pyyaml`, a non-`--frozen` `uv sync`, three non-`--frozen` `uv run pytest` calls). **After:** every flagged third-party action is pinned to a full 40-char commit SHA — the PyPI publish action to `dc37677b`, which is tag `v1.14.2` **and** the current `release/v1` branch tip, so OIDC trusted publishing is preserved; write permissions are relocated to the jobs that need them (`publish-pypi` keeps `contents: write` + `id-token: write`, everything else drops to `contents: read`); `inputs.tag` flows through an `env:` binding instead of the script body; and the installs are exact-pinned (`twine==6.2.0`, `tomli==2.4.1`, `pyyaml==6.0.3 --only-binary=:all:`) with `--frozen` added to the release `uv sync` and the three nightly `uv run pytest` calls. Behavior-identical, security-only; the remaining first-party self-install / frozen-lock findings are adjudicated won't-fix in the mission dossier (`kitty-specs/ghactions-sonar-hardening-01M2FYX1/adjudication.md`, Section E).

## [4.0.0rc2] - 2026-09-14

Second public release candidate for the Team Kitty 4.x line, cut from `main` for
the Team Kitty launch walkthroughs. This is a testing prerelease, not stable launch
acceptance. Install explicitly with `uv tool install 'spec-kitty-cli==4.0.0rc2'`.

The CLI keeps the public shared-package targets: events 9.1.6 and tracker 0.5.2.
Live Work is not included in this candidate. Stable 4.0.0 launch acceptance remains
tracked in planning#1999.

### Added

- **`spec-kitty auth login --machine` authenticates CI runners and other unattended environments for hosted operations with no browser, TTY or device-flow approval** (#3277; #4306). It exchanges a ServicePrincipal client ID and secret, read from `SPEC_KITTY_MACHINE_CLIENT_ID` plus `SPEC_KITTY_MACHINE_CLIENT_SECRET` or `SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE`, through the OAuth `client_credentials` grant. Missing or rejected credentials fail closed with one remediation message, never a prompt, and the secret is never printed. `--machine` cannot be combined with `--headless`. `auth status` labels the session `Machine / CI (Client Credentials Grant)`, and `auth doctor` (text and `--json`) reports the additive `session.auth_method` field. Browser and device-flow login remain the default for people; the runner setup and credential rotation runbook is `docs/operations/ci-machine-auth.md`.

### Added

- **`spec-kitty accept --mode pr --merge-commit <sha>` records the PR's real merge as the mission's post-merge review baseline** (#4231). A mission accepted through a GitHub PR never passes through `spec-kitty merge`, so its `meta.json` never carried `baseline_merge_commit` — leaving `spec-kitty review --mode post-merge` unreachable (`MISSION_REVIEW_MODE_MISMATCH`) and the lightweight dead-code gate failing a cleanly merged mission. The supplied commit is verified against git before anything is written (it must resolve, carry `kitty-specs/<slug>/meta.json`, its first parent must not, and it must have landed on the target branch — an unmerged mission-branch commit satisfies every first-introduction check, so only the target-branch membership check separates it from a real landing); `baseline_merge_commit` is then recorded as that first parent, with the provenance pair `pr_merge_commit` (the landing commit) and `pr_merge_evidence` (what the anchor's completeness rests on), through the same canonical seam `spec-kitty merge` uses. Also exposed as `spec-kitty agent mission accept --merge-commit`, and backfillable for missions whose PR already merged via the new `spec-kitty migrate backfill-merge-commit --mission <handle> --merge-commit <sha>` (idempotent; an already-recorded baseline is never overwritten). Both seams accept `--target-branch` for the PR's base branch, defaulting to the mission's declared `target_branch`, else the repository's primary branch.
- **The PR-recorded anchor names its evidence class, and EVERY landing shape needs an explicit operator attestation** (#4231 fix rounds). Post-landing git history cannot prove a supplied landing commit's first parent is the pre-landing target tip for ANY shape: an internal merge (the corpus branch merged into the implementation branch, the target then fast-forwarded to the result) is graph-identical to a merge performed on the target branch and its first parent is an implementation commit, and a single-parent landing (squash, or a corpus-first stack) whose implementation commits preceded the corpus has an earlier same-PR commit there — graph-identical to pre-existing target work. Recording an unattested anchor in either shape would silently under-scan the dead-code gate while the command's reason string claimed git had proved the parent was the tip. Both shapes are therefore refused unless the operator passes `--attest-first-landing-commit` (for a two-parent merge: the merge was performed on the target branch; for a single-parent landing: the supplied commit was the first commit of the landing), and record as `pr_merge_evidence: merge-commit-parent-attested` / `corpus-parent-attested` respectively, so the anchor's completeness rests on a recorded operator attestation, never on a claim git did not make; `spec-kitty review --mode post-merge` honours the field, surfacing `MISSION_REVIEW_DEAD_CODE_EVIDENCE_INCOMPLETE` instead of a green scan for any present value it does not recognize as complete. Full forge commit-list evidence, which would prove the tip outright, is tracked in #4277.

### Fixed

- **The lightweight review `dead_code_baseline_missing` finding now distinguishes a PR-accepted mission from one that never merged** (#4231). Both states previously produced the identical `verdict: fail`, so a cleanly PR-merged mission was indistinguishable from a real fidelity failure. The finding now carries a `reason` — `pr_accepted_merge_unrecorded` (with a remediation naming `backfill-merge-commit`) vs `never_merged_via_spec_kitty_merge` — while keeping the same hard-fail verdict weight, since the dead-code gate cannot run without an anchor either way.
- **An explicitly-set `SPEC_KITTY_SAAS_URL` is a real opinion again, even when its value equals the packaged default `https://team.spec-kitty.ai`** (#4259). The 4.0.0rc1 resolver treated such a value as "no opinion", so a stale `config.toml [sync].server_url` naming the retired first-party app endpoint `https://app.spec-kitty.ai` won resolution and login targeted dead infrastructure. An explicit env value now wins in a whole-process context (login) and fails closed as a split-brain against a different configured target in setup-only contexts, exactly like any other env/config disagreement.
- **A new 4.0.0 upgrade migration rewrites exactly the retired first-party address in `config.toml [sync].server_url` to the canonical hosted target** (#4259). Machine-scoped and idempotent; hostname-exact matching only (never substring), so custom and self-hosted endpoints, ports, paths, and every unrelated setting are untouched. A missing, unreadable, or unparseable `config.toml` is a no-op.
- **`spec-kitty auth login` now shows the resolved target and its configuration source before any OAuth flow starts**, and warns — never rejects — when the target is the retired first-party endpoint or another noncanonical `spec-kitty.ai` host, naming the canonical endpoint and the upgrade remedy (#4259). A custom/self-hosted endpoint is labelled custom and left unchanged.
- **`spec-kitty auth login` never relabels or forwards a stored session minted for a different endpoint** (#4259). Plain `login` on an issuer mismatch now refuses with the stale-session remedy instead of reporting "Already logged in"; only `--force` re-authenticates, minting fresh credentials against the resolved target (the non-interactive bridge already enforced this boundary since #234).
- **`spec-kitty tracker discover` leaked a raw Python traceback instead of a clean CLI error whenever the SaaS control plane rejected the discovery request (observed on HTTP 403; `#4233`).** **Before:** `discover` guarded the service call with a hand-rolled `except TrackerServiceError` only, but a SaaS non-2xx surfaces as `SaaSTrackerClientError` — a *sibling* of `TrackerServiceError` (both derive from `RuntimeError`, neither from the other) — so any 403/404/429/5xx propagated uncaught and printed a full Rich traceback exposing internal module paths (`tracker/saas_client.py`, `tracker/service.py`, `cli/commands/tracker.py`). `discover` was the lone tracker command that did not route its service call through the shared `_run_or_exit` helper (which catches the `RuntimeError` family), which is exactly why every other tracker command was immune. **After:** `discover`'s service call goes through `_run_or_exit`, so any `RuntimeError`-family failure — the SaaS sibling included — renders as a single-line stderr message + `Exit(1)` with no traceback and no internal paths. The shared boundary now also preserves the structured server error data (the September #4233 extension): the error envelope parser reads the PRI-12 canonical `code` key (with the legacy `error_code` and a string `error` message field as fallbacks, coordinated with `#2944` rather than a second taxonomy), the raised error's machine code now outranks the envelope category, and `_run_or_exit` renders the code, HTTP status and one actionable hint distinguishing disabled rollout (`FEATURE_DISABLED`), missing/stale binding, expired authorization, permission denial, rate limiting and server failure. Under `--json`, the same failure is additionally emitted as a machine-readable object on stdout (`{"ok": false, "error": ..., "error_code": ..., "http_status": ..., "action": ...}`) — failures are never converted into successful empty results, only whitelisted fields are rendered (no envelope internals, no credentials), and the exit code stays nonzero. Regression tests drive the real command with mocked HTTP error responses (not just injected service errors), including the exact observed `FEATURE_DISABLED` 403 payload, and assert no traceback, no leaked bearer token, and valid JSON on stdout in `--json` mode.
- **Starting a mission's specify, plan or tasks phase publishes its moment to Team Kitty again** (#4214). The Zeitgeist bridge validated the persisted Started payload unchanged, so the local-only `artifact_path` it carries failed the strict canonical model and the moment was dropped before any publish. The bridge now projects that field off at the wire boundary through the lifecycle module's canonical projection; the persisted event keeps it, any other undeclared field is still rejected, and Completed phases are unchanged. The issue's final acceptance row — the accepted event demonstrated on a managed test relay and decodable for Team Kitty's existing "Specify started" presentation — is pinned by a docker-local integration test (`tests/status/test_zeitgeist_specify_started_moment_docker_local.py`): a real `create_mission_core` run publishes through the registered lifecycle handler to a real `dkr-m1-02-zeitgeist:contract` relay container, and the accepted frame is read back through the real `GET /managed/events` pull path with the panel reader's own two-header discipline, its attrs decoding through the exact `from_zeitgeist_attrs` call behind the lifecycle-beat presentation.
- **`finalize-tasks` rewrites legacy string-form `dependencies` frontmatter (`"[]"`, `"WP01, WP02"`, bare `WP01`) to the canonical list form** (#3941). Previously a string value that coerced to the resolved dependencies was left on disk verbatim; `--validate-only` previews the normalization and still writes nothing.
- **`spec-kitty agent mission record-analysis` no longer refuses with `DIRTY_WORKTREE` after specify or plan opens Decision Moments** (#3928). The Decision Moment ledger (`decisions/index.json`, `decisions/DM-*.md`) is now classified as coordination-partition state, like the status event log.
- **`mission create` records the `mid8` identity in `meta.json` alongside `mission_id`** (#3474), so readers take it from the canonical identity source instead of re-deriving it. The value is unchanged.
- **`spec-kitty next` and `spec-kitty research` reject a traversal-shaped `--mission` slug with a clean typed error instead of a raw `ValueError` traceback** (#2878). Both commands now print the canonical safe-path-segment diagnostic as a single `Error:` line and exit 2; `next --json` emits a structured JSON error envelope.

### Changed

- **Hosted references and examples use `https://team.spec-kitty.ai`** (#4258). The retired hostname is removed from checked-in material; historical records use a reserved example hostname.

## [4.0.0rc1] - 2026-09-13

First public release candidate for the Team Kitty 4.x line. This is a testing
prerelease, not stable launch acceptance. Install explicitly with
`uv tool install 'spec-kitty-cli==4.0.0rc1'`.

The CLI keeps the public shared-package targets: events 9.1.6 and tracker 0.5.2.
Hosted end-to-end qualification, independent cold starts and final launch sign-off
remain tracked in planning#1999 and spec-kitty/spec-kitty-saas#1381. RC publication
makes this exact package available for that qualification; it does not claim those
checks have passed.

Runtime lookup now reports `RUN_IDENTITY_MIGRATION_REQUIRED` when identity backfill leaves an older run without a recorded mission ID. It preserves the existing cursor and journal instead of silently starting over. The error identifies the run and explains how to bind its index entry after verifying ownership.

### 💥 Breaking

- **`specify_cli.status` no longer re-exports the raw event-log writers** (`append_event`, `append_event_verified`, `append_events_atomic_verified`, `append_event_stream_atomic_verified`, `append_annotations_atomic_verified`, `append_primary_checkout_event*`) (mission `fsm-write-path-integrity-01M1TZV6`). Every status-event write now goes through the status-owned transition pipeline (`specify_cli.status.transition_pipeline.prepare_transition`) behind one of two shells — the flat `emit_status_transition` or the transactional `coordination.status_transition` — and holds the mission status lock for its duration. Raw writers live in `specify_cli.status._unsafe` behind an explicit allowlist that `tests/architectural/test_status_unsafe_allowlist.py` and the AST writes gate `tests/architectural/test_status_events_writes_gate.py` enforce; `from specify_cli.status import append_event` is now an `ImportError`.
- **`mission_runtime`'s root surface shrinks from 42 to 31 names and `ActionContext` is gone** (mission `dead-port-disposition-01M1TZVN`, WP03). Eleven test-only re-exports (`ArtifactPlacementFragment`, `BranchRefFragment`, `IdentityFragment`, `MissionArtifactContext`, `StatusSurfaceFragment`, `WorkspaceFragment`, `MissionArtifactHome`, `artifact_home_for`, `ResolvedSurface`, `SurfaceLocations`, `translate_surface`) are still defined at their modules but no longer re-exported from `mission_runtime`; the `ActionContext = MissionExecutionContext` alias and the `specify_cli.team_projection` tombstone package are deleted. Two more names dropped in the same pass are easy to miss here because they belong to different packages, not `mission_runtime`: `get_packs_root_default` is gone from `kernel.paths.__all__`, and `content_present_at_primary_tip` is gone from `mission_runtime.lifecycle_phase.__all__`. Both remain importable by their own module path, so neither breaks a caller outright, but `kernel`'s public surface shrank alongside `mission_runtime`'s. `tests/architectural/test_mission_runtime_surface.py` now asserts the exact public surface.
- **`specify_cli.mission_v1.read_events` is gone — both `from specify_cli.mission_v1 import read_events` and `from specify_cli.mission_v1.events import read_events` are now `ImportError`** (mission `dead-port-disposition-01M1TZVN`, WP01/WP04). The reader had no production caller left once `runtime.next.decision`'s legacy DSL readers were deleted; it is renamed to the private `_read_events` and `specify_cli.mission_v1.__all__` now lists only `emit_event`. No public reader remains.
- **`specify_cli.mission_v1.load_mission`, `load_mission_by_name`, and the `MissionProtocol` runtime-checkable protocol are gone — importing any of the three from the package root is now an `ImportError`** (mission `dead-port-disposition-01M1TZVN`, WP01). All three were defined directly in `mission_v1/__init__.py` itself (`load_mission` was documented there as the "Auto-detecting entry point (v0 vs v1)"), not in the `compat`/`runner`/`guards`/`schema` submodules named below — they went with the v1 DSL runtime they dispatched to, and had no production caller.
- **A third-party charter pack whose `mission.yaml` still authors an `orchestration:` block now fails to load loudly instead of the field being silently dropped** (mission `dead-port-disposition-01M1TZVN`, WP03 rider T014b). The dead `MissionOrchestration`/`MissionStateObject`/`MissionTransition` models and the required `Mission.orchestration` field are removed from the charter offering schema — `src/charter/offering/schemas/mission.schema.yaml` is regenerated without the `orchestration` definition, and the matching inert-slot baseline rows are retired — but the `Mission` model still declares `extra="forbid"`, so a pack that kept authoring the key is refused at load rather than tolerated (`tests/doctrine/fixtures/mission/invalid/retired-orchestration-key.yaml` pins the refusal). Nothing in this repo constructed these models. Unlike the 3.2.6 `context-sources` removal (below), **there is no upgrade migration** for this key — a pack author must delete the block by hand.

### Changed

- **A stale or mistyped org-directive activation entry no longer resolves silently, and directive resolution does less repeated filesystem work (charter directive-resolution hardening; `#4239`, `#4240`; epic `#2519`).** **Before:** when an `activated_directives` entry named no real directive, the delivered directives service best-effort normalized it (e.g. `007-ghost` → `DIRECTIVE_007`) and could co-activate an unrelated directive with no signal — an operator got no indication their entry was unresolved. Separately, resolving a directive re-walked every doctrine layer once per candidate filename stem (O(directives×stems) filesystem scans per resolution). **After:** the service emits a per-token WARNING naming the unresolved token and the form it fell back to, so a stale/typo'd entry is visible; and a single resolution pass now walks each doctrine layer at most once. Neither change alters which directives resolve — resolution outcomes and the layer-precedence authority are unchanged.

- **Forward-port the 3.2.6.1 first-run recovery fixes.** Mission creation rejects an unborn write checkout before creating artifacts, cleans up disposable scaffolds on actual commit refusals, and delays lifecycle publication until creation succeeds. Main retains its existing protected-branch bootstrap success and uncommitted-file disclosure. The tutorials continue one mission through specification and planning, active repository links use the current organization, and release tooling accepts four-component hotfix versions.

- **The plain batch status door (`emit_status_transition_batch`) is fail-closed again on `claimed -> in_progress` without a `workspace_context`** (operator decision 2026-09-07; #946; mission `fsm-write-path-integrity-01M1TZV6` design note WP02 row D-2, mission-review DRIFT-3). WP02 had dropped the deliberate #946 skip for door parity, so a direct batch caller that omitted the context was handed a synthetic `<execution_mode>:<root>`. The skip is reinstated as an explicit pipeline policy knob, `prepare_transition(default_workspace_context=...)`: the plain batch door passes `False` and the guard refuses with the historical `requires workspace context` message, persisting nothing; the flat single door and both transactional doors keep applying the default. Production callers (`status/work_package_lifecycle.py`) always supply the context and are unaffected.
- **Dependency gating for `claimed`/`in_progress` now resolves readiness once, in-lock, with a tri-state verdict** (mission `fsm-write-path-integrity-01M1TZV6`): a work package whose declared dependencies are not all `approved`/`done` is refused at claim and implement time with the blocking WP ids named. Two cases behave differently, and the difference is deliberate: a work package with **no** prompt file declares nothing, so the gate opens; a prompt file whose declarations cannot be **read** — unparseable frontmatter, a `dependencies` value the metadata model would itself refuse, or two files matching the same WP id after a half-finished rename — yields an *unsatisfied* verdict and fails **closed**, refusing `planned -> claimed` and `claimed -> in_progress` with the reason logged. `force` plus an actor and a reason still overrides, and `-> blocked`, `-> canceled` and the review edges are never affected by a corrupt planning artifact. The verdict lives in `specify_cli.status.dependency_verdict`.
- **Status locks are keyed by the mission directory name and bounded** (mission `fsm-write-path-integrity-01M1TZV6`): the mission status lock (`BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`, 10 s) now times out with the holder named instead of waiting forever; the run-state index is keyed by `mission_id` and a missing entry raises `RunStateMissing` instead of silently re-seeding; the decision-log emitter and `migrate rebuild-state` take the same lock as every other status writer.
- **The glossary-runner registration story is documented as it actually works** (mission `dead-port-disposition-01M1TZVN`, WP02): the kernel registry is populated lazily by `charter.offering.missions.glossary_hook` at first use (self-bootstrap), not "at import time by `specify_cli`"; the contract is pinned by `tests/doctrine/missions/test_glossary_hook.py`. `execute_with_glossary` remains documented-but-unwired (operator decision OD6; tracked on #1868).
- **`runtime.next.decision` no longer carries the legacy DSL readers `derive_mission_state` and `evaluate_guards`** (mission `dead-port-disposition-01M1TZVN`, WP04). See the `read_events` removal under Breaking, above.

### Removed

- **The CLI release train no longer compares itself against a SaaS consumer (`#3979`).** `Check Shared Package Drift` and the tag-time `release.yml` used to fetch `spec-kitty-saas/pyproject.toml` and `contracts/consumer-compatibility.json` from a sibling repository and fail the CLI when that repository's pins disagreed. The repository they read (`Priivacy-ai/spec-kitty-saas`) is retired, and the live Team Kitty repository pins both shared packages by exact git revision under its own constitution rather than consuming the public PyPI train, so there is no SaaS consumer contract for a CLI release to check against. **Before:** every PR touching `pyproject.toml` reddened on a comparison with no valid target, and a tag push could not publish without a cross-repo read token. **After:** the drift check validates the CLI's own `pyproject.toml`, `uv.lock` and release manifest against each other; `release.yml` publishes on that evidence plus the existing build and exact-install gates. Removed with it: `scripts/release/check_candidate_consumer_compat.py`, the `--saas-pyproject` option, the manifest's `consumers` block, and the `SPEC_KITTY_SAAS_READ_TOKEN` requirement. Fork PRs gain real enforcement in the exchange — the drift job used to *skip* entirely when that token was absent, so it now checks the CLI's own manifest where it previously reported a green skip.

- **The `downstream-consumer-verify` release job is removed, so a tag push publishes without a manual waiver (`#3979`).** This one failed for a different reason than the SaaS comparison above, and the distinction matters: the job checked out `${{ github.repository_owner }}/spec-kitty-end-to-end-testing`, which resolved to a path that no longer exists after the end-to-end suite moved to the programme org. **The scenario it ran is not retired** — `contract_drift_caught.py` is alive in `spec-kitty/EXPERIMENTAL-spec-kitty-end-to-end-testing` and remains a **hard gate at mission review** (`spec-kitty-mission-review` SKILL, FR-041; ADR `docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md`, still Accepted). What is removed is the duplicate of that gate in the publish workflow, which had been 404-ing on every tag push and forcing a `skip_downstream=true` waiver to release at all. **Before:** no release could publish without a maintainer waiver. **After:** the tag path publishes on its build and exact-install evidence, and the e2e scenario keeps gating at mission review, where it is owned.

  Whether the CLI (`spec-kitty-events` 9.x from PyPI) and Team Kitty (10.x by git rev) agree on the event wire contract is a shared-package publication question, not a CLI CI gate. The surface that owns it is that same e2e scenario at mission review — the removed workflow job never exercised a wire, only compared declared pins.
- **The mission-DSL v1 runtime and its `transitions` dependency are removed** (mission `dead-port-disposition-01M1TZVN`, WP01). `specify_cli.mission_v1.{compat,runner,guards,schema}` — the `transitions`-backed state machine, guard compiler, JSON-Schema validator and v0 wrapper — had no production caller; the surviving module `specify_cli.mission_v1.events` keeps `emit_event` (used by the `spec-kitty next` runtime loop), but its reader is renamed to the private `_read_events` and the package no longer re-exports a public reader — see Breaking, above. The `states:`/`transitions:` blocks are deleted from both built-in `mission.yaml` catalogs for `software-dev`, `plan` and `research` — the `packs/built-in/` tier-5 defaults and the `src/specify_cli/missions/` catalog the v0 loader ships in the wheel — and a new architectural detector keeps them from returning to either; the keys stay tolerated in third-party and `.kittify/overrides` `mission.yaml` files via `MISSION_COMPAT_IGNORED_FIELDS`. `transitions` (and the `six` it dragged in) no longer load when a mission event is emitted; the subprocess ratchet `tests/specify_cli/mission_v1/test_import_hygiene.py` pins that invariant permanently. No version bump (the rc cycle is already open).

- **The Convergence (`#3881`, merged 2026-09-05) folded the EXPERIMENTAL development line onto public `main`.** The merge relocated the doctrine Python package `src/doctrine/` → `src/charter/offering/` (mission `charter-code-topology-01M152G1`, CR-06; `src/doctrine.py` remains as a deprecation shim), retired the local CLI→SaaS sync transport, the `delivery`/`event-journal` emit stack, and the `src/specify_cli/saas/` package (mission status is now ephemeral by design; team artifacts render server-side), and removed SonarCloud from CI (the `sonarcloud` job died with the old 4118-line `ci-quality.yml`). Architectural gates (`tests/architectural/test_no_retired_subsystems.py` + a `pyproject.toml` TID251 ban block) keep the retired subsystems from silently returning. Living architecture docs and `CLAUDE.md`/`AGENTS.md` were realigned to the post-convergence topology in this cycle, and the self-declared module-ownership manifest `docs/architecture/05_ownership_manifest.yaml` was deleted (`#3888`) — it had drifted to naming trees the convergence removed, and its schema gate pinned that stale vocabulary, so correcting it reddened the gate. Module boundaries are now owned by the enforced pair (`pyproject.toml` wheel packages + the `test_layer_rules.py` layer chain); `05_ownership_map.md` survives as a demoted narrative pointing at it.

### Added

- **Drupal work now has a specialist agent profile — Drupal Dries — so a Drupal mission gets an implementer that already knows the framework's conventions instead of a generic one you have to coach.** **Before:** a Drupal work package could only be routed to a generic implementer or a wrong-stack specialist (Java Jenny, Node Norris), so module structure, dependency injection, the Entity API, configuration management and Drupal's test tiers had to be explained by hand on every task, and mistakes surfaced in review rather than being avoided. **After:** `drupal-dries` ships in the built-in pack as an implementer-role specialist covering Drupal 10.x/11.x backend work (modules, services and DI, Entity API, plugins, hooks, Forms API, routing, configuration management, Batch/Queue/Migration) and Drupal-native theming (Twig, `*.libraries.yml`, `Drupal.behaviors`, render arrays, preprocess). It arrives with two styleguides — `drupal-conventions` and `drupal-security-performance`, carrying all fourteen of the community "never do this" anti-patterns as paired wrong/right examples — and a `drupal-review-checks` toolguide naming the phpcs, phpstan, drupal-check, composer audit and PHPUnit tier commands a reviewer should expect, written so they work whether or not the project runs in a container. Where its territory meets Frontend Freddy's, both profiles now say so: Dries owns Drupal-native theming, and Freddy defers framework-native theming layers to the stack specialist for that framework. The profile ships **inactive** — activate it with `spec-kitty charter activate agent-profile drupal-dries` when you want it. Distilled from amazee.io's community `drupal-agents-md` guide, with one factual error in that source corrected against Drupal's own change record (implicit entity-query access checking was deprecated in 9.2.0 and throws from 10.0.0 — it is not, as the source states, deferred to Drupal 12).

- **The `migrate-project-guidance-to-spec-kitty-charter` procedure now captures the source's vocabulary in the glossary** (#4103). A new step between classification and drafting extracts the terms the guidance defines or uses with a specific meaning, triages them through the `glossary-maintenance-workflow` procedure into the narrowest owning scope, and makes the accepted surfaces the vocabulary the drafted artifacts must use verbatim. The exit condition and the parity-comparison step now require every defined term to resolve in the glossary or be excluded with a reason, and the procedure references `procedure:glossary-maintenance-workflow` in the DRG.

- **The glossary skill now pressure-tests a contested or load-bearing domain-model term before recording it, instead of accepting the first plausible definition (`#3835`).** **Before:** `spec-kitty-glossary-context` curated terminology and checked drift, but had no step that challenged a proposed domain-model term against the actual code or a concrete edge case, and no guidance on when a term decision warranted an ADR — so a shaky model claim could be written into the glossary as if it were settled. **After:** a new "Pressure-Test Domain Model Terms" step cross-checks the claim against the real domain types, API contracts, and tests (labelling it a hypothesis when code evidence is missing), challenges it with at least one concrete edge case, and raises an ADR only when the decision is hard to reverse, surprising without context, and a genuine trade-off. Two triggers ("shape a domain model's terms", "validate domain language against code") route that work in, and `spk-doctrine-glossary` now hands contested-term and domain-model work to the detailed workflow. The step points at the canonical `domain-aware-decision-interview` procedure and `adr-drafting-workflow` tactic it summarises. Instruction-only, and it skips cleanly for an ordinary canonical usage correction.
- **GitHub CI is back on public `main` — every push and pull request runs a bounded, path-scoped test pipeline again, and SonarCloud analysis returns (`#3995`).** The Convergence (`#3881`) had removed the heavyweight CI and SonarCloud, leaving public `main` with only the archived EXPERIMENTAL Blacksmith producer — so a contributor's pull request got no real test signal on GitHub and had to be validated externally. **Before:** no shift-left test/coverage/quality signal on a pull request, and the sole producer pointed at a retired private repository. **After:** a lean set of artifact-sharing GitHub Actions — a path router feeding a single gate-selection authority, a duration-balanced per-module test matrix, coverage/xunit aggregation with a diff-cover >=90% changed-lines gate, a nightly full/performance/interpreter run, a packs lane, and a fork-safe SonarCloud workflow — runs on stock runners with no privileged token on public jobs. On a pull request the pipeline is fail-fast (a red predecessor short-circuits its successors, and a skipped job never counts as green); the nightly and manual runs execute everything. The reinstated pipeline is the sole/primary public producer, and machine oracles keep dead/retired code out of the selected suite and prove no test is selected by zero gates.

- **`spec-kitty routes` tells you which team this checkout is connected to and where its activity goes — the question `spec-kitty sync routes` used to answer, before the old sync transport was removed (Priivacy-ai/spec-kitty#10).** **Before:** once the CLI→SaaS sync transport (and its `sync routes` command) was removed, there was no way to check whether a checkout was actually connected to a team, or where its mission updates were going. **After:** `spec-kitty routes` reports, for this checkout, which team has admitted it and which relay — the server that carries a team's live mission updates — receives its activity; if no team has admitted the checkout, it says so plainly, and that is a normal, expected answer, not a failure. It answers instantly from a local cache when it can (a previously stored authorization, or a remembered "not admitted" answer, both usable without being logged in) and only contacts Team Kitty over the network — to request, or "mint," a fresh authorization — when nothing is cached. It always reports honestly which of those it found: admitted, confirmed not admitted, or "couldn't get an answer this run" — never dressing up silence as "not admitted".
- **`spec-kitty events tail` streams a mission's event log as JSON lines, so an external consumer (a dashboard, a CI watcher, a native driver) can follow status changes live and resume exactly where it left off (#3858; closes #3841).** **Before:** there was no supported way to observe a mission's `status.events.jsonl` incrementally — a consumer had to re-read the whole file and diff it, and because that log is _not_ append-only (it is truncated in place on a coordination rollback) a naive tailer silently desynced when the file shrank or was rewritten. **After:** `spec-kitty events tail --mission <slug> --json` emits each event as a JSON line, injecting a `tail_offset` + `tail_invariant` cursor a consumer persists and supplies back with `--from-offset`/`--from-invariant` to resume; a mismatched resume cursor is **refused** (structured stderr, non-zero exit — never a silent reset). All three truncation shapes — a mid-append tear, a clean record-boundary shrink, and a truncate-then-regrow within one poll — are detected (size check + SHA-256 content invariant, evaluated independently every poll), so the stream stays correct across rollbacks. `--once` and `--max-events N` bound the stream for scripted use. See [CLI reference § `spec-kitty events`](../api/cli-commands.md#spec-kitty-events). _(Moved here from the 3.2.6 section: this landed 2026-09-05, after the 2026-09-03 `v3.2.6` tag, and belongs to 3.2.7rc1.)_

### Fixed

- **`spec-kitty doctor <cmd> --json` printed the human string `Error: Not in a spec-kitty project` on stdout (exit 1) instead of JSON whenever it ran outside a spec-kitty project, so `doctor <cmd> --json | jq` got a parse error indistinguishable from a crash (`#4242`).** The not-in-project guard ran before the `if json_output:` branch and never consulted `json_output`, while the same commands' success path emitted well-formed JSON — a contract inconsistency between exit paths. **Before:** sixteen `--json` doctor subcommands leaked prose on stdout on this path — twelve in `doctor.py` (`state-roots`, `workspaces`, `identity`, `topology`, `mission-type`, `shim-registry`, `contracts`, `invocation-pairing`, `ops`, `doctrine`, `cutover`, `review-cycle-reconcile`) and four in sibling modules (`command-files`, `provenance`, `env-file`, `coordination`); `mission-state --json` leaked identically on its real not-in-project path (`locate_project_root` *returns* `None` outside a project rather than raising, and the terminal error inside `_resolve_audit_root` ignored `--json`); and `tool-surfaces`' raise branch emitted the raw exception text as the error message instead of the canonical one. **After:** every doctor `--json` command routes its not-in-project error through one canonical renderer (`_doctor_shared._emit_not_in_project`), so `--json` stdout is a machine-parseable `{"ok": false, "error": {"code": "not_in_project", "message": "Not in a spec-kitty project"}}` object on both failure modes (raise and returned `None`) and the human path keeps its Rich prose. `mission-state` threads `json_output` through to that renderer (a `None` root *with* `--fixture-dir`/`--include-fixtures` is still the valid fixtures-only state; a `None` root *without* fixtures is the terminal not-in-project error and now honors `--json`). Each command keeps its own documented not-in-project exit code (1 for most; 2 for the config-error family `shim-registry`/`contracts` and for `skills`/`tool-surfaces`). A parametrized class-closing gate (`tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py`) pins the contract for every affected command on both the `None` and the raise path.

- **`spec-kitty charter generate` and `interview` could not adopt an org-pack directive whose declared ID differs from its filename — the very IDs `doctor doctrine` and the delivered `DoctrineService.directives` resolved fine (`#4194`; closes `#4185`).** **Before:** the activation path matched directives by filename stem and legacy alias only, so a declared ID that did not resemble its stem was invisible to selection, promotion, and delivery; worse, when an ambiguous mandatory directive was selected, generation skipped it silently and still reported success, and an ambiguous ID could persist and later resolve to the *wrong* org policy. **After:** resolution accepts an exact declared directive ID after a filename-stem miss, selection prefers a declared ID over a coincident filename, interview promotion reports ambiguous selections while keeping valid siblings, and generation refuses an ambiguous mandatory org directive before it changes any charter/configuration state. A filename stem that two layers bind to different identities is rejected as unrepresentable, so an ambiguous ID fails closed instead of resolving to the wrong policy. Writers still persist identity-preserving filename stems; unknown IDs and non-directive kinds keep their existing validation.

- **Every shipped step contract's governance-context bootstrap command failed to parse, so `spec-kitty charter context` exited 2 with `No such option: --role` for every mission action (`#4049`; closes `#4031`).** The bootstrap step of all 17 built-in step contracts — specify, plan, tasks, implement, review, the five research steps and the seven documentation steps — declared `spec-kitty charter context --action <x> --role <x> --json`, but the CLI has no `--role` option. **Before:** an operator or agent host that ran the declared command verbatim (the governance-context bootstrap every mission action begins with) hit an exit-2 parse error, not the governance context; the flag was pure noise — its value was always identical to `--action`. **After:** the `--role` flag is dropped from all 17 contracts (and the five research `prompt.md` mirrors); the command parses and returns governance context. A new corpus guard (`tests/doctrine/mission_step_contracts/test_declared_commands_parse.py`) walks the real Click tree and parses every command a shipped contract declares, so a contract can no longer advertise a flag the parser does not have.

- **Two `spec-kitty` commands started at the same moment against a shared home directory could crash the second one with `Global asset input changed` instead of both succeeding (`#4017`; `#4174`).** The first run of `spec-kitty` on a machine (or the first after an upgrade) installs its runtime assets into `~/.spec-kitty`; a lock already serialized those cold installers so only one wrote at a time. **Before:** the waiting run re-checked against the *stale* empty-home picture it had captured before the lock, then tried to apply non-idempotent create steps (`mkdir`, exclusive-create) over files the winner had just written — and aborted with `Global asset input changed` (or, after a naive narrowing, `File exists`). Anyone running two agents, a CI fan-out, or two shells that shared one home hit it. **After:** the waiting run re-assesses *under* the lock against the now-warmed home, finds nothing left to do, and returns cleanly; a warm home still takes no lock and checks exactly once. A genuine change to the packaged asset *sources* between check and apply is still caught and refused, so the fix narrows only harmless races, not real drift.

- **A corrupt `__pycache__/*.pyc` left by an interrupted `pip`/`uv tool` install crashed *every* `spec-kitty` command at startup with a raw traceback instead of self-healing (`#4124`; observed on a Windows training machine as `AttributeError: 'bytes' object has no attribute 'co_filename'` traced to `specify_cli/upgrade/migrations/base.py`).** **Before:** `cli/commands/upgrade.py` imports `specify_cli.upgrade.runner` → `migrations.base` at module level, so one truncated bytecode cache killed app assembly for every command — including `spec-kitty dashboard` — before any command ran, and the only recovery was insider knowledge (find the installed package, delete its `__pycache__`). **After:** CLI app assembly, the compat-planner migration-registry load (the upgrade-nag hook on every command's startup path), and `spec-kitty upgrade`'s discovery step each run through a bytecode self-heal seam (`specify_cli.bytecode_heal`): an import failure plausibly caused by a stale cache — `ValueError: bad marshal data`, `EOFError: marshal data too short`, `ImportError: Non-code object in '…pyc'`, or the field `co_filename` AttributeError — purges the installed package's derived `*.pyc` caches (always safe: Python recompiles from source), invalidates the import caches, and retries exactly once, with a one-line warning telling the operator what was repaired. Genuine failures still propagate: the planner seam degrades loudly to "migrations unavailable" (empty registry, upgrade nag/preview skipped, warning names the manual fix) instead of the old silent `except: pass`, and `spec-kitty upgrade` still surfaces real discovery errors. Deleting a `.pyc` never deletes source; a fully-zeroed cache file was already self-healing via the bytecode magic-number check.
- **`finalize-tasks` froze `planning_commit_sha` with no refresh path, so a mission that amended its planning mid-execution needed `--force` on every subsequent `move-task` (`#4141`; reported from a real 9-WP mission whose every WP required overrides).** **Before:** once execution began (any WP past `planned`), a re-finalize correctly PRESERVED the recorded planning SHA (#3311) — but preserve-only meant a legitimate planning amendment that landed afterward (a WP dependency-field fix, an `/spec-kitty.analyze` remediation) could never advance it: every subsequently allocated lane merged the stale planning snapshot, the `move-task` branch-currency / `kitty-specs/`-contamination / uncommitted-changes gates fired on the resulting drift, and the only in-tool path was `--force` (or hand-editing `lanes.json`). **After:** `spec-kitty agent mission finalize-tasks --refresh-planning-commit` re-points the recorded SHA to the current target-branch tip so lanes merge the amended planning state at their next allocation — advance-only: it is refused, with `lanes.json` untouched, when the recorded SHA is not an *ancestor* of the tip (a history rewrite, not an amendment). Without the flag the #3311 preserve behavior is unchanged, but a re-finalize that detects drift (recorded SHA ≠ branch tip) now says so on the console and names the flag, and the `--json` success payload carries the decision under `planning_commit` (`action`/`sha`/`previous_sha`/`branch_tip`); the orchestrator-api `tasks` verb passes it through (contract 1.5.0). See [`finalize-tasks` internals §3](../api/finalize-tasks-internals.md).
- **`spec-kitty init` and `spec-kitty upgrade` crashed on Windows the first time they wrote a skill, command, or agent-rules file (`#3173`, and its siblings across the install path).** **Before:** the skills/tool-surface/session-presence writers and the coordination confined-write used POSIX-only primitives — `os.fchmod`, a bare `os.O_NOFOLLOW`, and `dir_fd`-relative writes — that do not exist on Windows, so a fresh onboarding died with an `AttributeError`/`ValueError` before the user reached a single mission. **After:** every one of those writers routes through one shared capability check and falls back to a path-based write on platforms without `dir_fd`, preserving the same no-symlink-following and containment guarantees; on Linux/macOS the original fd-relative path is unchanged. A Windows user can now `init` and `upgrade` a project.
- **`spec-kitty dashboard` reported a running dashboard on Windows that was silently dead (`#4125`).** **Before:** the background server was launched with `python -c "<script>"`, whose child crashes on import (Windows has no `__main__.__file__`), and its output went to a black hole (`DEVNULL`) with no check that it ever came up — so the CLI printed "✅ Started" for a process that had already exited, and the ephemeral-port path additionally raised outright on Windows. **After:** the server launches as a real module (`python -m specify_cli.dashboard._server_main`), its output goes to a log file under the runtime state dir, and the CLI now waits for the port to actually serve *this project's* dashboard identity over `/api/health` (resolved `project_path`, plus the token when one was handed to the child — the same contract the lifecycle health check enforces), reaping the child and surfacing its log tail if it dies, before reporting success; a foreign dashboard that won the same free-port race can never stand in for the spawn. The same `python -c` fix was applied to the background upgrade-check refresh.
- **Resynthesis resolves activated IDs across built-in, org and project layers** (#4101). Project profiles use the same precedence as profile inspection. Eager activation checks synthesis prerequisites and the proposed selection before writing activations; lookup errors identify the charter activation store and searched layers.

- **Agent-profile cascade reaches directly authored project guidance** (#4100). `--cascade all` activates referenced procedures, directives, tactics and styleguides from a clean deactivated state, and missing project references produce explicit warnings.

- **Directly authored project doctrine enters the project graph and provenance during activation** (#4097). Procedures and agent profiles are registered alongside directives, tactics and styleguides without rewriting their source files. Charter status counts all five kinds and the shipped authoring skill documents their paths.

- **Glossary show resolves seed-only terms** (#4102). When no compiled entity page exists, `glossary show` reads the same seed and event store as `glossary list`, rendering each scoped definition without requiring compilation.

- **Charter exposes project authoring and org pack commands** (#4098). `charter new`, `validate`, `org` and `fetch` delegate to the existing doctrine handlers. Deprecation guidance identifies commands that remain under `doctrine`.

- **A coord-topology mission's per-work-package completion check silently did nothing, so `spec-kitty next` would advance a mission out of `implement` even when a work package had never been claimed (`#3981`; closes `#3884`).** **Before:** for any mission that routes lifecycle through a coordination worktree, the per-WP completion gate looked for `tasks/WP*.md` under the coordination worktree's own directory — files that only ever live on the PRIMARY partition — so the lookup always missed and the gate reported "all work packages done" unconditionally on `implement`, skipping the per-WP loop entirely regardless of any package's lane. A work package that was scaffolded but never claimed (or merely in progress and not yet handed off) was never caught. **After:** the completion check anchors its `tasks/` read to the PRIMARY partition through the placement seam, and a never-claimed (`uninitialized`) or never-lifecycled (`genesis`) work package correctly blocks the `implement -> review` advance; an ambiguous mission handle blocks with a structured message rather than silently falling through. **Operator note:** any coord-topology mission currently sitting in `implement` with a work package not yet handed off, blocked, or rejected-with-operator-provenance will newly — and correctly — block on its next advance, so spot-check in-flight coord-topology missions after upgrading.

- **A future runtime event producer could crash `spec-kitty next` at import time, or be silently replaced by a second one, instead of failing safely (`#3983`; follow-up to `#3921`, ADR `2026-09-06-2`).** The runtime emitter seam that `#3921` opened for a real event producer had two unguarded edges. **Before:** registering a producer twice — which happens on an ordinary double import — raised an uncaught error that killed the command outright; two different producers registering resolved by import order, last one silently winning, with nothing logged to say which; and a producer whose constructor failed (missing config, an unreachable credential lookup) took `spec-kitty next` down with it. **After:** re-registering the same producer is a no-op, a genuinely different second producer is refused with a message naming both, and a producer that fails to construct is logged at WARNING and degrades to the do-nothing seam — the run continues. No producer ships yet, so nothing changes for users today; this is the seam being made safe before the first one arrives.

- **Decision requests raised under the strict retrospective policy (`before_completion` + `block`) and on composition dispatch were never written to the mission's `decisions.events.jsonl` (ADR `2026-09-06-2`; mission `dead-port-disposition-01M1VRA2`).** The runtime bridge buffered those decision events correctly but flushed them to the plain no-op emitter seam instead of the decision-log wrapper, and handed the same plain seam to the composition dispatch path, so the events were dropped in silence -- the operator saw a decision gate with no record of the request behind it. **Before:** the runtime's decision log had gaps exactly where the strictest policy ran. **After:** every buffered decision request is appended to the mission's decision log exactly once, and the rollback on a refused gate is unchanged. The permanently no-op concrete `RuntimeEventEmitter` class (`runtime.next.event_emitter`) that shadowed the canonical runtime seam was deleted and consolidated onto the runtime Protocol / `NullEmitter` in `runtime.next._internal_runtime.events`, which now exposes a `runtime_emitter_for_mission` factory and a `register_runtime_emitter_factory` hook for a future real producer; an architectural guard (`tests/architectural/test_runtime_emitter_seam.py`) keeps the single-class seam and the decision-log wiring from regressing.

- **A project could be handed the wrong governance — SPDD/REASONS guidance, org-required directives, tactics and paradigms — whenever its _active_ configuration had drifted from what it originally authored (`#3871`; closes `#3838`).** Four charter surfaces decided what doctrine to deliver by reading the authoring record (`selected_*`) instead of the resolved authority (`activated_*`), so a project whose activation differed from its authored set quietly received doctrine it never activated — and missed doctrine it did — with no error and no warning. Activation is now the single authority across all four surfaces: every directive, tactic and paradigm identifier is canonicalized at the moment it enters a union, an identifier whose form cannot be canonicalized fails loud instead of being silently dropped, and an absent activation set resolves to the documented built-in catalog default rather than collapsing to an empty set.

## [3.2.6] - 2026-09-03

_The stabilization release: fail-loud honesty across the workflow, plus `orchestrator-api` 1.4.0 opening the full design pipeline to external hosts. Consolidated operator-facing notes: [release-notes-3.2.6.md](release-notes-3.2.6.md)._

### 💥 Breaking / 🗑️ Removed

- **Breaking — the redundant `context-sources.*` agent-profile surface is removed from the schema; profiles author references solely on the top-level `*-references` fields** (mission `doctrine-drg-silent-drop-boundary-01M0PE7E`, WP02; #3629 p1). The `context-sources` block (`directives` / `tactics` / `toolguides` / `styleguides` / `doctrine-layers` / `additional`) duplicated the canonical, DRG-provisioned `directive-references` / `tactic-references` / `toolguide-references` / `styleguide-references` surface and was mostly inert; only `context-sources.directives` minted a DRG edge, and every shipped profile already carried the same ids on `*-references`. **Before:** two parallel reference surfaces, one of which was silently dropped on delivery. **After:** one canonical surface — the model now declares `extra="forbid"` without a `context-sources` field, so a profile still authoring the block **fails to load loudly** rather than dropping it in silence. The extractor now projects `agent_profile` DRG edges from `*-references` (`directive-references` → `requires`, `tactic-references` → `requires`, and `toolguide-references` / `styleguide-references` → `suggests`). A consumer project that authored custom profiles with `context-sources` is migrated automatically by the `3_3_1_context_sources_consolidation` upgrade migration, which **set-merges** every reference id onto the matching `*-references` field (deduped, never appended) and drops the edge-less `doctrine-layers` / `additional` names with a logged note. Run `spec-kitty upgrade` (the migration is idempotent and safe to re-run); free-text `additional` bindings with no artifact-id shape are reported, not silently discarded.

- **Breaking/removal — the legacy CLI→SaaS sync transport and its 22 subcommands are gone: `routes`, `share`, `unshare`, `opt-out`, `opt-in`, `import-history`, `workspace`, `server`, `now`, `gc`, `archive`, `purge`, `project_store_preview`, `project_store_migrate`, `project_store_status`, `project_store_quarantine`, `project_store_history`, `migrate`, `mode`, `status`, `diagnose`, and `doctor`.** The `delivery`, `event_journal`, and legacy `saas` packages, the `websockets` runtime dependency, and `doctor restart-daemon` / `doctor orphan-daemons` are removed with it. `auth doctor --reset` and its sync-era diagnostic sweep are also gone; the narrowly scoped `auth doctor --unstick-lock` token-refresh repair remains live. The `tracker` command group is registered unconditionally and gated at invocation by `SPEC_KITTY_ENABLE_SAAS_SYNC`, while the plugin-facing `disable_public_pypi_notifier` rename to `disable_no_upgrade_notifier` is recorded below.

- **The D1 publish path is deleted: `spec-kitty team-projection publish`, the
  `.kittify/derived/` team-index / team-snapshot / public-projection /
  attestation-manifest artifacts, and the `dossier/emitter_adapter.py`
  sync-emitter bridge (Epic E4, planning issue #6).** Consumers read the
  tracked repository at an exact pushed commit instead of a published
  gitignored projection, so nothing publishes one any more. The
  `team_projection` package survives as its one ported seam,
  `TEAM_WP_ALLOWED_FIELDS` (Team Kitty applies the same allowlist on read);
  `dossier/events.py` emitters still validate their envelopes but drop them
  locally — no transport consumes `MissionDossier*` events since the CLI→SaaS
  sync transport's deletion began. Full removal of the remaining emission
  surface lands with the `sync/dossier_pipeline.py` deletion.

- **A `SPEC_KITTY_SAAS_TOKEN` (env-supplied) session no longer picks up a SaaS URL from a repo-local `.kittify/saas-auth.json` — export `SPEC_KITTY_SAAS_URL` (or set `[sync].server_url` in `config.toml`) alongside the token, or the CLI now fails closed with `SaaS URL not configured` (EXPERIMENTAL-spec-kitty#237, EXPERIMENTAL-spec-kitty#264).** Before, a token from the environment paired with a URL supplied only by the checkout-controlled auth file silently resolved — letting that file redirect a longer-lived, more broadly-scoped service token to a host of the checkout's choosing. `.kittify/saas-auth.json`'s `saas_url` is now honoured only alongside its own `token`, never paired with an env-resolved one; the separate, documented `.kitty.env` trust surface remains unchanged (EXPERIMENTAL-spec-kitty#289).

- **Stale PyPI-era vocabulary on the upgrade-check path is renamed, with no compatibility aliases (EXPERIMENTAL-spec-kitty#245).** The upgrade-check path queries private GitHub Releases, not PyPI, and has for several releases — but it still carried four PyPI-named symbols from before that migration. Renamed: `upgrade_probe.probe_pypi()` → `probe_github_releases()`; `UpgradeProbeResult.latest_pypi_version` → `latest_release_version`; `UpgradeChannel.AHEAD_OF_PYPI` (value `"ahead_of_pypi"`) → `AHEAD_OF_RELEASE` (value `"ahead_of_release"`); and, on the plugin-facing `DistributionProfile` dataclass, `disable_public_pypi_notifier` → `disable_no_upgrade_notifier`. **Migration for forks with a registered `spec_kitty.distribution_profile` entry point:** rename the keyword argument in your factory from `disable_public_pypi_notifier` to `disable_no_upgrade_notifier`; a factory still passing the old name now raises `TypeError` inside `resolve_distribution_profile()`, which logs the failure at `ERROR` (previously silent) and falls back to the stock profile rather than your fork's configuration. **On-disk cache compatibility:** `~/.cache/spec-kitty/upgrade-check.json` written by an older build is still read — the deserializer falls back to the legacy `latest_pypi_version` key when `latest_release_version` is absent — but a cached `"channel": "ahead_of_pypi"` value no longer matches any `UpgradeChannel` member, so that one entry is treated as a cache miss and re-probed (safe; not a crash).

- **`pack validate` (and `doctrine org validate`) now fails (exit code `1`) for
  three previously-passing org-pack shapes (mission
  `org-pack-authoring-diagnostics-01KZY463`; `#3387`).** All three close a
  silent-success authoring gap where a pack passed validation cleanly and only
  failed — or silently misbehaved — at runtime or on adoption. Concretely: a
  merge-time-skipped agent profile (a profile that individually passes schema
  validation but fails to field-merge onto a same-ID built-in profile) now
  surfaces as a `profile_skipped` error, sourced from
  `AgentProfileRepository.skipped_profiles()` rather than requiring a separate
  `spec-kitty doctor doctrine --json` invocation. A nested
  `assets/<pack>/x.asset.yaml` manifest with a schema violation is now scanned
  recursively, matching what `AssetRepository` loads at runtime (previously
  invisible to validation). DRG content living only under `drg/*.graph.yaml`
  fragments with no pack-root `*.graph.yaml` now produces a
  `drg_root_graph_missing` error — the runtime
  (`src/charter/_drg_helpers.py:load_validated_graph`) reads only the pack
  root, never `drg/` fragments, so this shape previously validated cleanly and
  then silently zeroed the pack's DRG content on adoption (per sibling mission
  `org-pack-drg-root-graph-guard-01KZY0QT`, `#3384`). `validate_pack()` gains a
  keyword-only `check_drg_root: bool = True` parameter for the new DRG check;
  `pack_assembler.py`'s internal round-trip validation of its own
  drg/-fragments-only output passes `check_drg_root=False` unconditionally (a
  structural carve-out — the assembler never writes a pack-root graph).
- **Breaking — `spec-kitty dispatch` (no `--profile`) now always lets a canonical-verb match outrank a domain-keyword match, regardless of `routing_priority`.** (mission `dispatch-dry-run-route-only-01M1HKV2`, WP03; SK-08, SPEC-KITTY-LEDGER.md:2727; #3840; narrowed by operator ruling after the initial WP03 commit — see below) **Before:** `ActionRouter.route()` picked the auto-routed winner by `routing_priority` across _every_ matched candidate regardless of confidence tier, so a request whose tokens matched only a generic domain keyword for a high-`routing_priority` profile could outrank the request's own canonical-verb match, opening an Op under a possibly-wrong profile at low confidence — this is SK-08's reported defect. **After:** a canonical-verb candidate always wins over a domain-keyword candidate, regardless of `routing_priority` (`routing_priority` still breaks ties _within_ the canonical-verb tier only, unchanged). **Some previously-succeeding no-`--profile` `spec-kitty dispatch "<request>"` calls will now select a different profile than before** when their tokens matched both a canonical verb and a competing domain keyword; callers wanting a stable profile across a mission's lifetime should pass an explicit `--profile <id>` hint, which this change does not affect (`tk-watch`'s existing `TK_WATCH_PROFILE` pin continues to work unmodified, and becomes unnecessary as an SK-08-specific workaround for the competition case). The router's already-computed candidate list is exposed on every successful route via `RouterDecision.alternatives` (mission WP02) so a consumer can inspect routing confidence directly, and `spec-kitty dispatch --dry-run` (mission WP01) lets a consumer query the routing signal without opening governance history.

  **Narrowed after initial landing:** WP03's first implementation also made the router raise `ROUTER_AMBIGUOUS` (exit 1) on _every_ zero-canonical-verb-candidate resolution, including a request whose tokens carried no canonical verb at all and matched only a lone or unopposed domain keyword — a **no-competition** case SK-08 never reported (SK-08 is specifically about a domain keyword _outranking_ the request's own verb). That broke a real shipped profile (`diagram-daisy`, routed via its `chart` domain-keyword signal) and was reverted by operator ruling: when zero canonical-verb candidates exist, `route()` now falls back to its pre-existing (pre-WP03) selection over the domain-keyword candidates — a unique keyword-tier match still auto-selects, and `routing_priority` still breaks ties among multiple keyword-tier-only candidates; `ROUTER_AMBIGUOUS` is reserved for a genuine tie at the top priority, exactly as before this fix. No previously-succeeding no-`--profile` `dispatch` call newly exits 1 as a result of this fix — the only user-visible effect is the cross-tier rerank described above.

- **Breaking — the redundant `context-sources.*` agent-profile surface is removed from the schema; profiles author references solely on the top-level `*-references` fields** (mission `doctrine-drg-silent-drop-boundary-01M0PE7E`, WP02; #3629 p1). The `context-sources` block (`directives` / `tactics` / `toolguides` / `styleguides` / `doctrine-layers` / `additional`) duplicated the canonical, DRG-provisioned `directive-references` / `tactic-references` / `toolguide-references` / `styleguide-references` surface and was mostly inert; only `context-sources.directives` minted a DRG edge, and every shipped profile already carried the same ids on `*-references`. **Before:** two parallel reference surfaces, one of which was silently dropped on delivery. **After:** one canonical surface — the model now declares `extra="forbid"` without a `context-sources` field, so a profile still authoring the block **fails to load loudly** rather than dropping it in silence. The extractor now projects `agent_profile` DRG edges from `*-references` (`directive-references` → `requires`, `tactic-references` → `requires`, and `toolguide-references` / `styleguide-references` → `suggests`). A consumer project that authored custom profiles with `context-sources` is migrated automatically by the `3_3_1_context_sources_consolidation` upgrade migration, which **set-merges** every reference id onto the matching `*-references` field (deduped, never appended) and drops the edge-less `doctrine-layers` / `additional` names with a logged note. Run `spec-kitty upgrade` (the migration is idempotent and safe to re-run); free-text `additional` bindings with no artifact-id shape are reported, not silently discarded.

### ✨ Added

- **`--owned-checkout` now works across the whole single-branch mission lifecycle, so an agent operating from a task-owned Git worktree can run a mission end-to-end without a command targeting the wrong checkout.** (mission `explicit-worktree-commands`; #3843; extends #3346 / #3787 and ADR 2026-08-12-1) **Before:** only `spec-kitty agent mission create` and `spec-kitty next` accepted `--owned-checkout`; the rest of the lifecycle — `check-prerequisites`, `finalize-tasks`, `spec-commit`, `accept`, `agent tasks move-task`, and `agent tasks mark-status` — could only rediscover the repository-root checkout, so a valid single-branch worktree workflow either refused or silently wrote to the wrong mission surface. **After:** all six commands accept `--owned-checkout PATH` and route mission reads, writes, status events, and commits through one validated owned root (the new `core/owned_mission.py` preflight), which fails closed on a foreign or nested path, a detached or mismatched branch, a pre-staged index, or an unsupported topology. Owned mode is deliberately `single_branch`-only for now — a `lanes`/`coord` mission opted in is refused with a structured `OWNED_TOPOLOGY_UNSUPPORTED` rather than mis-routed. Flagless (non-opted-in) behavior is byte-for-byte unchanged. Design record: ADR `docs/adr/3.x/2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md`.
- **A new architectural gate catches stale references to relocated `charter` modules at construction time, so future package moves stop shipping dead import paths.** (enabler mission `tidy-charter-cutover-surface`; closes #3818, #3808) After a `src/charter/**` relocation, stale _string_ references to a module's old path — arch-gate path-literal allowlist tuples, `patch("charter.<old>…")` mock targets, and markdown relative links — used to survive the import rewrite and only surface as a red CI shard afterward. `tests/architectural/test_no_stale_charter_path_literals.py` now fails on any such literal or link in `src/`, `tests/`, or live `docs/` (AST-driven, word-boundary-safe, historical archives excluded), giving the remaining `retire-doctrine-term` waves a guardrail. Riding along, the three always-on charter consistency-check gates now share **one** DRG load and one fail-closed wrapper (was three independent loads) — behaviour-preserving, verdicts byte-identical (#3808).
- **`charter` is now the canonical governing term in the Charter + glossary authority; the legacy `governance.doctrine` selection key still loads with a one-time deprecation warning.** (mission `charter-authority-flip-01M14RB3`, wave M1 of `retire-doctrine-term-01M0JMK9`; #3664, #3732) This is the first, authority-only wave of the doctrine→charter terminology retirement — the `src/doctrine` package, `spec-kitty doctrine` CLI, and the `drg`/`doctrine artifact`/`doctrine pack` domain vocabulary are deliberately unchanged and land in later waves. **Before:** the glossary authorities carried both a `doctrine` and a `charter` term (with `charter` even defined as synthesizing "…and doctrine"), and the charter selection key was `governance.doctrine`. **After:** the three glossary authorities (seed YAML, built-in pack, `docs/context/charter.md` — renamed from `doctrine.md`) speak `charter` as the single governing term; a new `### charter` Terminology-Canon entry disambiguates its overloaded senses (Charter Bundle / Charter Pack / the `src/charter/` package / the `spec-kitty charter` CLI group / Active-Inactive Charter artefact / **Pack Default Charter**) with "do-NOT-use" guards. The selection key becomes `governance.charter`; a dict-level compat reader maps the legacy `governance.doctrine` key forward and warns once (`LegacyGovernanceKeyWarning`, public `apply_legacy_governance_selection_key_compat`), so existing projects keep loading. `spec-kitty` migrates `interview/answers.yaml` via the new `scripts/migrate_charter_interview_answers.py` (preserves every answer, unknown key, and the historical `doctrine-catfooding-2196` slug; restores the pre-image on failure). A shrink-only architectural ratchet (`test_transition_guard_shrink_only`) and an archive-immutability gate (`test_archive_root_byte_identical`) prevent the governing term from being re-introduced.
- **Status moments now carry live presence/focus frames: every broadcast at the status fan-out seam also publishes one `presence.publish` frame (and, for a WP transition, one `focus.start` naming `<mission>.<WP>`), so Team Kitty's live panel shows who is on which repo/WP (EXPERIMENTAL-spec-kitty#186).** The moment stream alone could never power the panel — zeitgeist treats `event.publish` as activity _about_ a session that extends nothing's TTL — so GOAL.md's MVP test ("presence shows the member on that repo/WP") had nothing to render. Presence rides the stored `presence`-kind credential (the kind grants both ops); focus mints its own `focus`-kind lease via the new `resolve_focus_capability`, stored merged into the same credential-store entry (`store_focus_capability`) so a re-mint of either lease never drops the other. Presence binds repo/branch to git truth via `ClientConfig.for_repository`; a ref that cannot fit the relay's 64-char ident grammar or a checkout whose identity cannot be verified drops only the liveness frame, never the moment, and a focus denial never writes a negative answer over the shared store entry.

- **New `spec-kitty moments off|on|status` command gives agents an off switch and filters for Zeitgeist status moments (EXPERIMENTAL-spec-kitty#190, "Moments in agent context").** A per-developer setting — global `~/.kittify/config.toml`, overridable per repo in `<repo>/.kittify/config.toml` — `[moments] agents = off | mine | team`, defaulting to **mine** (only moments about missions this checkout knows) and never "everything": `team` requires an explicit opt-in, and an unreadable or unknown value fails closed to `off`. Filters ride the same table (`repos`, `missions`, `teammates`, `kinds`) and are applied client-side in the stream client (`filtered_stream.FilteredStream`'s new optional `frame_filter`) — the relay stays a per-team firehose. A rate cap (`rate_per_minute`, default 10) bounds what one MCP session surfaces per rolling minute; everything beyond it is summarised as "+k more", never silently dropped. With `agents = off`, `spec-kitty zeitgeist mcp-serve` refuses to start: one line on stderr (stdout stays protocol-clean), exit 0. New `specify_cli/zeitgeist_client/moments.py`.

- **New `spec-kitty team-projection publish` command produces read-only, byte-deterministic team-index and per-mission snapshot artifacts (plus an explicit-opt-in public variant and an attestation manifest) with exact-commit provenance (D1-T1).** Every artifact is a closed, allowlist-filtered projection of the existing status event log — orchestration-only runtime state (`shell_pid`, unbounded operator `notes`) never reaches a team or public consumer — and public output stays absent unless a project explicitly sets `public_projection.enabled: true` in `.kittify/config.yaml`. Refuses (non-zero exit, zero files written) on a dirty working tree, since the attestation manifest's whole purpose is a truthful commit-to-content binding for downstream consumers. New `specify_cli/team_projection/` package; no new runtime dependency.

  > **⚠️ Superseded within this same release.** The `spec-kitty team-projection publish` D1 publish path added here was **deleted later in 3.2.6** — see the "The D1 publish path is deleted" entry under 💥 Breaking / 🗑️ Removed above. Consumers read the tracked repository at an exact pushed commit instead of a published projection; the `team_projection` package survives only as its `TEAM_WP_ALLOWED_FIELDS` seam. This Added entry is retained for historical fidelity but the command it describes does not exist in the shipped 3.2.6.

- **`spec-kitty upgrade`'s auto-commit no longer names the _old_ path of a staged rename.** (#2491 follow-up; salvaged from #2492) `git_status_paths` read `git status --porcelain -z` rename entries with the fields backwards — real git emits `R  <new>\0<old>\0` — so a staged rename put the pre-rename path into the commit-set. The unit-test fixture encoded the same wrong order, so the test passed against the bug. Fixed with a structured porcelain record that keeps the destination as the current path while retaining the source identity: clean renames stage both the destination and source deletion, and a source already dirty at baseline taints the destination so operator work is never swept. Covered through the real `commit_touched_checkout` seam, not only the parser.

- **`spec-kitty upgrade` now auto-commits root-level files it wrote during the run — `.gitattributes`, `.claudeignore`, `AGENTS.md`, `GEMINI.md` — exactly as it already did for files in subdirectories; pre-existing edits to any file, root or not, are still never swept into the commit.** (#2491 follow-up; #2492 superseded by #3679; #2392 invariant) **Before:** the commit-set filter skipped every root-level file except `.gitignore`, on the theory that root files are operator-owned. But upgrade's own migrations write at the root — the merge-driver/diff-attribute migrations (`.gitattributes`, seven of them, several in this rc cycle, and they run in worktrees too), `m_3_2_8_provision_kitty_env` (`.claudeignore`), and surface repair (`AGENTS.md`/`GEMINI.md`) — so a fully successful `upgrade --yes` routinely ended with `M .gitattributes  M .claudeignore  ?? AGENTS.md  ?? GEMINI.md`, and a modified `.gitattributes` in every live worktree tripped the `spec-kitty merge` dirty-worktree guard (the #2385 class again). The hand-kept exception list drifted four times in six months. **After:** ownership is decided by the pre-run baseline alone — a file clean before the run and dirty after was written by the run and lands in the one auto-commit; a file already dirty at baseline stays out, whatever its depth. The path-depth rule is gone. Porcelain now requests per-file untracked paths, so a file the run creates beneath a pre-existing operator-owned untracked directory remains visible to the baseline diff instead of being collapsed into the same directory entry. Rename/copy identity and run-local filesystem mutation provenance carry source ownership across moves and transformed relocations; if that bounded provenance history is exhausted, auto-commit fails closed for manual review. Exact NUL-delimited path identity is preserved, including valid leading/trailing spaces. Two guards remain: paths outside the checkout (`../`) are never committed, and when the checkout **is** `$HOME` (the #3652 hazard) neither `~/.kittify` nor any root-level file is committed — those are the operator's dotfiles. A real-git test drives `commit_touched_checkout` end-to-end on a main checkout and a worktree and asserts the tree ends clean except for the pre-existing operator edit. Behaviour note for operators: if you edit a root file _while_ an upgrade is running (a seconds-long window), that edit can now land in the upgrade commit, as an edit to a subdirectory file always could; `git reset --soft HEAD~1` undoes it. Decided via an adversarial-squad review of the allowlist alternative (see #3686).

- **`spec-kitty zeitgeist operability` gives the bundled Zeitgeist client a
  payload-free self-report of its own liveness/connection/subscription/
  outbox status, plus local failure drills (`O1-C`).** `operability report`
  is one snapshot of seven signals — offer/drop/lease/revoke/mcp/repair,
  each carrying its own denominator where one applies (`OfferSignal.
  budget_s` is always the hard 750ms bound; `LeaseSignal.ttl_s` is always
  the 90s current-focus ceiling, present even when no focus is active) —
  built from state the already-landed `transport`/`credentials`/
  `outbox_approval`/`mcp_stdio` modules already own; there is no second
  data store. A repo with no stored checkout gets an honestly stale/
  inactive report rather than a fabricated live one. `drill-timeout`
  (relay unreachable), `drill-rotation` (auth expiry — reads only the
  stored `token_issued_at` timestamp, never the token), and
  `drill-rollback` (proves `outbox_approval.revoke()` fails closed on a
  never-approved item, without ever opening `/dev/tty`) are network-free
  and deterministic. No sensitive field ever appears in a report — proven
  by running it through `sanitizer.py`'s own forbidden-key gate, the same
  one the rest of the client already trusts.

- **`spec-kitty zeitgeist outbox` gives a human a bundled, outside-model
  approval surface over locally queued Zeitgeist prose (`Z8-C`).** `list`/
  `show` inspect pending items (exact content is disclosed only via `show`
  or the decision prompt itself — never in `list`'s redacted preview);
  `approve`/`reject`/`revoke` require the human to type back a per-item
  challenge at the real controlling terminal (`outbox_approval.py`'s
  `_capture_human_gesture`), and raise `HumanGestureRequired` whenever none
  is available — there is no `--yes`/`--force`/`--non-interactive` flag on
  any of the three, no environment-variable escape hatch, and the hidden
  stdio MCP adapter (`mcp_stdio.py`) is untouched: a model talking over MCP
  has no tool that reaches this surface. Pending items are content-addressed
  (SHA-256 over repo/audience/content/context) and TTL-bounded
  (default-deny: an expired item can never be approved); receipts are
  content-addressed and idempotent on retry.

- **`spec-kitty zeitgeist status`/`watch` and a hidden stdio MCP adapter give a
  terminal or an MCP client bounded, read-only access to one team's live
  Zeitgeist presence/focus stream (`Z7-C`).** Both surfaces call the same
  shared `zeitgeist_client.subscription` functions over the already-landed
  `filtered_stream.FilteredStream` client — one team context per call (the
  existing `credentials.py` checkout, never a `--relay-url`/`--token` flag),
  a <=90s honest reported-live timeout ceiling, a bounded frame count on
  `watch`, and no payload ever written to disk. The MCP adapter
  (`zeitgeist_client/mcp_stdio.py`) uses the official `mcp` SDK
  (`mcp>=1.27.1,<2.0.0`) and exposes the matching `zeitgeist_status`/
  `zeitgeist_watch` tools.

- **The charter package is now a real two-module split — `charter.offering` (offer catalogue) and `charter.activation` (mutation/activation layer) — with the `offering ↛ activation` boundary enforced as a package wall.** (mission `charter-activation-split-01M16ZSE`, wave M2b of `retire-doctrine-term-01M0JMK9`; #3664) Completes the split M2 deferred: the activation-side charter modules (`sync`, `compiler`, `resolver`, `interview`, `pack_context`, `context`, `cascade`, the synthesizer, …) relocate from top-level `charter.*` into `src/charter/activation/`, and `charter/__init__.py` becomes lazy (PEP-562) so importing `charter.offering.*` no longer transitively drags the activation layer. **Before:** the offer/activate boundary was enforced against an interim explicit module list because `charter.activation` did not yet exist as a package. **After:** `charter.activation` is a real package and the C-004 architectural gate collapses to forbid `charter.offering` → `charter.activation.*` directly. The 13 offering-facade re-export surfaces and the layer-neutral primitives (`parser`, `bundle`, `resolution`) intentionally stay at top-level `charter.*`; the `charter.drg` facade keeps its offering-type re-exports while the org-activation graph logic moves to `charter.activation.drg_activation`. Internal reorganization: the retired `doctrine` compatibility shims from M1/M2 are unchanged, so no operator-facing surface changes.

- **The internal `doctrine` code package is retired and relocated to `charter.offering`; every operator-facing `doctrine` surface keeps working with a one-time deprecation warning.** (mission `charter-code-topology-01M152G1`, wave M2 of `retire-doctrine-term-01M0JMK9`; #3664) M2 moves the 265-file `src/doctrine/**` catalogue to `src/charter/offering/**` — the pure offer-side catalogue under the charter package — and closes every importer. It is the code-topology continuation of the M1 authority flip. **Before:** the offer catalogue was a separate top-level `doctrine` package (`import doctrine`, `spec-kitty doctrine …`, `doctrine.org.packs`, `doctrine:<kind>:<id>` URNs, `.kittify/doctrine/`, a tracker `doctrine` ownership mode). **After:** the canonical home is `charter.offering`, and six compatibility shims (each read-both / canonical-wins / warn-once) keep the retired surfaces functional through the deprecation window: `import doctrine` / `from doctrine import X` (a module shim, submodule imports must move to `charter.offering.X`); the `spec-kitty doctrine` CLI group (deprecated alias of `spec-kitty charter`); the `governance`/tracker `doctrine` mode → **`ownership`**; `doctrine.org.packs` → `charter_packs.org.packs`; the `doctrine:` synthesizer URN prefix → `charter:` (durable event logs keep parsing both); and a `.kittify/doctrine/` → `.kittify/charter-packs/` dual-root reader. A new architectural gate enforces that `charter.offering` never imports the charter activation/mutation layer (C-004). **Deferred (mission M2b):** the physical `charter.offering ↔ charter.activation` two-module split — the activation-side charter modules stay at their current top-level paths for now, and the C-004 gate is enforced against them until M2b relocates them.

- **`spec-kitty accept` now honors a project-declared source layout, so repos that do not use `src/` (Django `apps/`, Go `internal/`) stop failing the accept gate — and stop being pushed to `mkdir` empty directories just to fake a green.** (#3016; folds #3785, #2330 Item 1) A project declares its real layout once in `.kittify/config.yaml` under `project.path_conventions` (for example `workspace: apps/`, `tests: tests/`), and `accept` remaps the directories it checks to match. **Before:** the software-dev path convention hardcoded `src/`, so `accept` failed every mission in a non-`src` repo with _"These directories are required by the active mission. Create them before continuing."_ — steering operators into fabricating empty directories or reaching for a blanket `--lenient`. **After:** the project override takes precedence over the mission-type doctrine default (project override → doctrine default → unchanged blocking + `--lenient`), applies across all four mission types through one shared validation seam, and is remap-only — it never adds a new required path. The blocking-by-default policy from #3783 is deliberately unchanged: an override pointing at a directory that is still absent under strict mode still blocks. `deliverables` is excluded from the override vocabulary (its default value is a mission artifact token that routes `feature_dir`↔`project_root`), a malformed `path_conventions` section fails closed with a message naming the offending key, and a missing or corrupt `config.yaml` stays lenient. Layout auto-detection (`manage.py` / `go.mod` signals) is the deliberate next step (#2744). Design record: ADR `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md`.

- **`charter` is now the canonical governing term in the Charter + glossary authority; the legacy `governance.doctrine` selection key still loads with a one-time deprecation warning.** (mission `charter-authority-flip-01M14RB3`, wave M1 of `retire-doctrine-term-01M0JMK9`; #3664, #3732) This is the first, authority-only wave of the doctrine→charter terminology retirement — the `src/doctrine` package, `spec-kitty doctrine` CLI, and the `drg`/`doctrine artifact`/`doctrine pack` domain vocabulary are deliberately unchanged and land in later waves. **Before:** the glossary authorities carried both a `doctrine` and a `charter` term (with `charter` even defined as synthesizing "…and doctrine"), and the charter selection key was `governance.doctrine`. **After:** the three glossary authorities (seed YAML, built-in pack, `docs/context/charter.md` — renamed from `doctrine.md`) speak `charter` as the single governing term; a new `### charter` Terminology-Canon entry disambiguates its overloaded senses (Charter Bundle / Charter Pack / the `src/charter/` package / the `spec-kitty charter` CLI group / Active-Inactive Charter artefact / **Pack Default Charter**) with "do-NOT-use" guards. The selection key becomes `governance.charter`; a dict-level compat reader maps the legacy `governance.doctrine` key forward and warns once (`LegacyGovernanceKeyWarning`, public `apply_legacy_governance_selection_key_compat`), so existing projects keep loading. `spec-kitty` migrates `interview/answers.yaml` via the new `scripts/migrate_charter_interview_answers.py` (preserves every answer, unknown key, and the historical `doctrine-catfooding-2196` slug; restores the pre-image on failure). A shrink-only architectural ratchet (`test_transition_guard_shrink_only`) and an archive-immutability gate (`test_archive_root_byte_identical`) prevent the governing term from being re-introduced.

- **`spec-kitty charter context --json` now exposes a top-level `directives_source` provenance field, and directive resolution emits fail-loud diagnostics.** (#3728; mission `directives-additive-resolution`) `charter context --action <action> --json` reports where the resolved directive set came from — for example `catalog_fallback` for a bare project, or `catalog_fallback+project_local` when a project-local `directives:` entry is merged onto the catalog default — carried by a `CONTEXT_SCHEMA_VERSION` bump. The human-readable `charter context` output now prints a diagnostic whenever the directive catalog-default fallback is used or project-local directives are merged, so the resolution branch is never silent.

- **Work-package cards in the dashboard kanban board now show a small colored avatar for the currently assigned agent profile.** (#647) **Before:** the card only listed the profile/role/agent as text badges, so scanning a busy board for "who's on what" meant reading every badge row. **After:** each card renders a deterministic colored-circle avatar (initials derived from a hash of the identity string) next to its WP ID, falling back through `agent_profile` → `role` → `agent` → `assignee` and rendering nothing for a WP with none of those set (legacy shape, or the scanner's encoding-error path) rather than a broken/empty circle. No image upload involved — the color and initials are generated client-side, so the same profile always gets the same avatar. Historical multi-participant avatars (Phase 2 of the issue) are out of scope here; they need explicit backend provenance support that doesn't exist yet.

- **The operator-signal / fail-loud discipline is now a citable, named directive in the internal dogfooding pack.** (#3410, #3549) A new `operator-signal-contract` directive lives in `packs/internal/directives/` (registered in the internal DRG fragment; provenance `org`, layer 1) and codifies **"a path that decides must also signal"**: whenever a code path reaches a correct machine-readable outcome — a correct `error_code`, a byte-stable file, a truthy return, a completed state transition — it MUST also emit the human-readable half through an **existing** operator-visible surface, never a new sink that can itself be swallowed. It adopts the existing #3410 (charter/doctrine silent-drop) and #3549 (event-log integrity) vocabulary rather than minting a new term, and it explicitly does **not** ship to consumers (it stays out of `packs/built-in`). `spec-kitty doctor doctrine --json` reports the internal pack healthy with the directive resolved through the DRG (`artifact_counts.directives: 1`, no skipped/inert artifact).

- **The `--base` / topology-drop class from #3571 now has a structural home: one shared allocation seam every route flows through, plus a CI guard that fails when a new route tries to bypass it — so the "override reaches only one of two routes" bug can't silently recur.** (mission rc3-lane-allocation-single-seam; delivers #3460 / #3462 / #3536; #3571 recurrence-prevention) M1 (#3616) shipped the #3571 point-fix; M8 generalizes it. **Before:** `--base` honoring lived in two independent helpers (a positive parent-chooser and a separate fail-loud guard), the read-side degrade was hand-rolled at each site, the topology-availability predicate had look-alike surrogate checks, and a `lanes`/`single_branch` mission refused a protected-branch bookkeeping commit with an **un-followable** remedy ("target the coordination branch" — which that topology never mints). **After:** (1) **one seam** `resolve_lane_base_or_refuse` (honor-or-raise, never a silent degrade) is the sole computer of a lane's parent ref across all four routes — fresh-coord, fresh-legacy, reuse, crash-recovery — with byte-identical parentage when no `--base` is supplied (NFR-preserving); (2) a **structural anti-bypass guard** (`tests/architectural/test_lane_allocation_single_seam.py`) fails, naming the offending `file:line`, when any new allocation route computes a parent ref outside the seam or a new read-degrade site skips the companion — proven non-vacuous by a synthetic-bypass fixture; (3) the topology-availability authority (`_transaction_topology_available`) is **pinned by an anti-divergence guard** so no future site can gate on a `coordination_branch is None` surrogate (#3460 — the census found zero live surrogates to remove; the win is the guard, not a code change, and the #2939 off-axis-annotation exception is explicitly preserved); (4) a **read-side degrade companion** `resolve_read_dir_or_degrade` mirrors the write-side helper and consolidates the genuine degrade-to-dir read sites (#3462), while the #1848 data-loss re-raise at `status/aggregate.py` is deliberately left bespoke (never collapsed); and (5) the **#3536** protected-branch refusal now branches its remedy on real coord-availability — a coord topology keeps the coordination-transaction remedy, a no-coord (`lanes`/`single_branch`) topology gets a **followable** one (commit to a non-protected branch, or declare the ref unprotected via `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`), never the impossible coordination-branch instruction; the ref-only commit guard (`commit_guard.evaluate`) stays topology-blind and the no-coord answer is sourced from the commit-router SSOT (converging with epic #2739). The anti-bypass guard's read-degrade check is **tree-wide** — it walks every coord-catch `try/except` under `src/specify_cli` + `src/mission_runtime` (27 sites classified: seam-routed, family-bespoke, or explicitly not-a-read-dir-degrade with a stated reason), so a new un-dispositioned coord read-degrade anywhere in the tree fails CI naming its `file:line`. (One borderline site, `migrate/backfill_provenance.py`, is documented as a residual: it degrades a read to a dir but deliberately skips _silently_ per AM-4, which the WARNING-emitting seam can't yet express without a new silent-degrade strategy.)

- **Legacy missions now carry a canonical `mission_type`, so upgrading past the M3/M5 mission-type changes no longer breaks them.** (#3614) A new `spec-kitty migrate backfill-mission-type` command mints a **profile-resolving** `mission_type` into every legacy `meta.json` whose only type signal is the deprecated `mission` field, and the existing `spec-kitty doctor mission-type --fail-on …` census gate proves a project is safe before it upgrades. **Before:** a project carrying `mission`-only missions resolved fine today, but would go type-unresolvable once M5 drops the legacy reader, then hard-fail once M3 rejects unresolvable types — breaking on upgrade with no migration path. **After:** run `spec-kitty migrate backfill-mission-type` (idempotent; never overwrites an existing `mission_type`; a `--dry-run`/`--json`/`--mission` surface; a value that resolves no governance profile at any layer is reported `needs_manual_resolution`, never masked into a broken state), then gate the release with `spec-kitty doctor mission-type --fail-on legacy-key-only,typeless,error` (the states that actually break under M3+M5). The write decision is keyed on the same activation-independent `MissionTypeProfileRepository` tolerance M3 uses, so a valid built-in type resolves and backfills even on a project that has not activated it. **Program ordering:** this backfill must land and be run against a project **before** the M3 (#3596/#3598) and M5 mission-type-reader changes reach it.

- **CI now measures its own false-red rate weekly instead of relying on a manual squad re-derivation, and draft PRs iterate faster without weakening the ready-for-review signal (mission `ci-flake-report-workflow-01M0M9D8`; `FR-002`/`FR-006`–`FR-010`/`FR-018`).** A new scheduled `ci-flake-report.yml` workflow (weekly + `workflow_dispatch`) classifies every completed `CI Quality` failure into `perf_timing_flake` / `infra_flake` / `real` / `needs_review`, reports the false-red rate and per-test timing cost, and uploads the findings (`metrics.json`, `durations.json`, `report.md`, `state.json`) as artifacts only — it never commits to the repo, never edits docs, and is not a required status check. Separately, `CI Quality` now behaves differently by PR state: a **draft** PR fails fast (a new `draft-fail-fast-cancel` job cancels the run the moment `lint` or `kernel-tests` fails, so you get the first failure cheaply — a red draft run is therefore inherently partial), while a **ready** PR still runs every diff-relevant chain to completion so a reviewer sees the full _relevant_ failure list in one pass, with untouched domains staying un-triggered exactly as before. A new push to a previously-red PR also re-runs the previously-failed tests first (`--ff`) in the `fast-tests-cli` suite (a first-cut pilot; other suites are not yet reordered), so a still-broken fix surfaces fastest. The merge-gate is unchanged in both modes. See the CI contract for draft versus ready runs and green-before-RFR for the full contract and the "watch your draft run green before flipping to ready" rule contributors and agents now follow.

- **Wall-clock performance tests no longer run on the PR path — a dedicated, statistical performance pipeline runs them off-band instead, so a slow shared runner can never again turn `main` red or block an unrelated PR (contributor/maintainer DevEx; ADR `2026-08-22-1`).** A false-red audit found **58.6% of CI failures were inactionable flake**, dominated by single-shot wall-clock budget asserts (`assert elapsed < N`) that trip on cold-start, not on real regressions. **Before:** ~60 budget tests ran in contended parallel PR shards and a single-shot `timing-nfr-serial` gate blocked merge on them — the largest false-red source. **After:** every wall-clock/CPU-budget test carries `@pytest.mark.performance` and is held out of every PR/blocking run (env-gated via `SPEC_KITTY_RUN_PERFORMANCE`); a new scheduled + `workflow_dispatch` **`performance.yml`** runs them **per-domain** (mirroring `CI Quality`'s split) through **`pytest-benchmark`** — calibrated rounds with warmup discard, percentile reporting, and `--benchmark-compare-fail` against a committed per-domain baseline, so a regression is caught **statistically off-band** and alerts on the scheduled run only, never a single-shot ceiling on a PR. The on-PR `timing-nfr-serial` gate is retired; the separate daemon-health `restart-daemon-nfr-timing` gate and genuine behavioral non-hang/timeout guards (ReDoS bounds, "didn't block on the network" checks) deliberately **stay** on the PR path — they assert correctness, not a budget. Never retry-to-green. This closes the long-term half of #3595 (the interim `performance` marker landed in #3593).

### ♻️ Changed

- **`merge/baseline.py`'s committed-`meta.json` reader now shares the one kernel L1 malformed-JSON authority instead of re-implementing it.** (#3330, follow-up to #3259/#3319) `_read_committed_meta_json` decoded the `git show <target>:meta.json` blob with its own `json.loads`/`isinstance` pair — a second, gate-invisible re-implementation of the malformed contract #3259 consolidated everywhere else. **Before:** two independent decoders could drift on what counts as malformed. **After:** the same `git show`-blob text is decoded via `kernel.meta_decode.decode_meta`, matching the sibling git-plumbing site (`git/ref_advance.py`); the two `BaselineMergeCommitError` message shapes callers depend on are unchanged.

- **Untangled the three-way `ExecutionMode` name/token collision — one class named `ExecutionMode` no longer means three different things.** (#3416, prereq for #3590) Three unrelated classes were all named `ExecutionMode`, and two collided on a `code_change` member that meant **contradictory** things. **Before:** `mission_runtime.context.ExecutionMode` (`worktree`/`code_change`) was a dead, never-consumed local duplicate of the external `spec_kitty_events.status.ExecutionMode` (`worktree`/`direct_repo`) axis, while `specify_cli.ownership.models.ExecutionMode` (`code_change`/`planning_artifact`) modelled the unrelated "what a WP produces" axis — so a reader of `ExecutionMode.code_change` could not tell which axis they were on. **After:** the dead `mission_runtime` enum is **retired** (removed from the package `__all__` and the canonical-surface ADR); the live ownership enum is **renamed** to `WorkProductKind` (its member string values `code_change`/`planning_artifact` are **unchanged**, so WP frontmatter stays wire-compatible); and the external `spec_kitty_events.status.ExecutionMode` is now the single live class of that name, owning the worktree-vs-direct axis. A re-drift guard (`tests/architectural/test_execution_mode_no_redrift.py`) fails if a `class ExecutionMode` or a local `worktree`+`code_change` enum reappears in `src/`, while permitting `WorkProductKind` to gain future members. Behaviour-preserving: no lane, worktree, or status-payload behaviour changed. The five-`Severity`-enum ladder co-located under #3416 is a separate acceptance block and remains open.

- **`analysis_report`/`acceptance`'s artifact-filename constants no longer fail at `import` time.** (#3622, follow-up to #3599/#3617) `_HASH_INPUTS` (`analysis_report.py`) and `SPEC_FILE`/`PLAN_FILE`/`TASKS_FILE`/`PRIMARY_ARTIFACT_FILES` (`acceptance/__init__.py`) resolved their filenames from the `expected-artifacts.yaml` authority as module-level constants, so a malformed built-in manifest would raise on `import specify_cli.analysis_report` / `import specify_cli.acceptance` — a broad blast radius for a data fault, for two widely-imported CLI modules. **After:** resolution is deferred to first access via a module `__getattr__` (PEP 562) plus call-time helper functions at each former call site, preserving the existing `from specify_cli.acceptance import SPEC_FILE`-style API and byte-identical resolved values; the failure now surfaces at point-of-use instead of at import.

- **Spec Kitty now ships a `spk-doctrine-show-me` skill that guides any agent to
  explain work with compact, checkable visuals — the smallest diagram,
  pseudocode, or tree that answers the question — recommended from the specify
  and plan surfaces (`#3528`).** Before, agents had no shared doctrine for _when_
  a visual earns its place or _which_ shape fits the point (call tree, sequence,
  state diagram, C4, or a `diff` over the matching tree), so visual explanations
  were ad-hoc and often missing. The skill routes to Spec Kitty's canonical
  Mermaid, PlantUML, C4, and diagram-review sources — bundling byte-pinned
  portable copies of the guides and themes so it keeps working once installed in
  a consumer project — and documents faithful `/spec-kitty.status` TUI rendering
  from `--json` (lifecycle lanes vs the five-group display, and done-progress vs
  weighted-readiness, so a custom board never mislabels weighted readiness as
  completed work). Adapted from HumanLayer's MIT-licensed `show-me` skill with
  full attribution and license notice preserved.

- **An organisation doctrine pack can now ship templates and mission-FSM
  content, and `spec-kitty` actually resolves them at runtime — before, an org
  pack could declare a template or mission that no resolution path would ever
  find (`#3524`; closes `#3523`).** The two forked template resolvers
  (`doctrine/resolver.py` and `specify_cli/runtime/resolver.py`) and the FSM
  mission-discovery walks consulted only the built-in, project-legacy, and
  user-global tiers — `resolve_org_roots()` existed but nothing on those paths
  called it, so a configured, validated, activated org pack stayed inert for
  templates and mission discovery. Now an `ORG` tier sits between the
  project-legacy and user-global tiers in the asset chain (6 tiers) and in FSM
  discovery (8 tiers); the two resolvers' tier-1 mission-scoped override probe is
  reconverged (they had silently drifted, so the same lookup behaved differently
  depending on which resolver ran); and `charter list` now reports org-sourced
  entries with the correct `ORG` origin instead of mislabelling them
  `GLOBAL_MISSION` and reading them from the wrong directory. Projects with no
  org pack are unaffected — `resolve_org_roots()` returns `[]` and every new
  lookup is a no-op.

- **`spec-kitty doctor mission-type` reports whether every mission's
  `mission_type` actually resolves, so a broken or unregistered type is visible
  before it misbehaves (mission `mission-type-guard-registry`; `#3402`,
  `#3386`).** Modelled on `doctor identity`, it walks every mission under
  `kitty-specs/` and classifies each into one of six distinguishable states —
  `resolved`, `activated-unresolvable`, `unknown`, `typeless`,
  `legacy-key-only`, or `error` — and supports `--json` for machine output and
  `--fail-on <state,...>` for CI gating (e.g.
  `--fail-on unknown,activated-unresolvable` exits non-zero when any mission
  sits in those states). Before, a mission whose type failed to resolve gave no
  signal until the runtime silently applied the wrong rules; now the condition
  is inspectable on demand.

- **A pack — built-in, org, fetched, or a charter bundle — now has one canonical
  `pack-manifest.yaml` schema instead of two divergent formats (mission
  `pack-metadata-manifest-unification-01M052PT`; closes `#3500`, `#3501`, `#3502`,
  `#3503`, slice of keystone `#2467`; ADR `2026-08-16-1`).** Before, org packs'
  `pack-manifest.yaml` stored per-kind `artifact_counts` (no lineage, and never
  written for the built-in pack every pack extends), while charter bundles'
  `synthesis-manifest.yaml` enumerated `constituents[]` in an unrelated shape —
  two formats that could drift, with neither covering the reference pack. Now the
  unified schema (enumerated `constituents:[{kind,id,path,content_hash}]`, stored
  `artifact_counts` retired for a derived `counts_by_kind` view, charter-only
  fields in an optional `charter:` profile block) is defined and the built-in pack
  emits it: a generated manifest (265 constituents, wired into `spec-kitty doctrine
  regenerate-graph`) plus new authored `packs/built-in/pack.yaml` + `pack.md`
  carrying a stable, immutable ULID `pack_id` and declared `parent_pack` /
  `accompanies_doctrine_pack` lineage edges, resolved exclusively through the
  existing `org_extends.resolve_extends_order` (no second lineage walker —
  enforced by a non-vacuous architectural ratchet). `pack_version` is
  derive-else-fallback: authored in `pack.yaml` when present, else generated, so
  fetched/org packs keep genuine fetch-time provenance. This slice lands the
  schema, models, and the built-in-pack writer; org/fetched/charter manifest
  writers and the `pack_id` resolver cutover are fast-follow, and the broader
  "compound packs" slice of `#2467` remains future work.

- **A new `spk-run-verdict-capture` skill so every agent harness records a WP
  review verdict the same way (`#3121`).** The sole authority for a verdict is the
  `review_result` event in `status.events.jsonl` (the `review-cycle-N.md` render
  is non-authoritative); the skill documents the deterministic CLI seam
  (`spec-kitty agent tasks move-task <WP> --to approved|planned
  --review-feedback-file`) and its verdict vocabulary, and `spk-run-review-wp`
  now references it.

- **Committed doctrine provenance is now portable across machines, checkouts,
  and wheels — no more baked-in absolute paths (mission
  `operator-config-ergonomics`, WP01/WP03/WP04; `#3494`;
  `FR-001`/`FR-002`/`FR-003`/`FR-006`/`FR-007`/`FR-008`).** Committed
  `charter.yaml` and `agent_profiles_manifest.json` used to record each
  built-in doctrine pack under the authoring machine's absolute filesystem
  path, so the same files broke on a teammate's checkout, an installed wheel,
  or CI. Both provenance carriers now emit a portable
  `${SPEC_KITTY_PACKS_ROOT}/built-in/...` token through one shared normalizer
  and **never** a resolved path — even when `SPEC_KITTY_PACKS_ROOT` is already
  exported to an absolute path at emit time (the re-bake case is
  regression-guarded). A single kernel expansion seam (`src/kernel/env_expand.py`,
  `expand_env_template`) backs both this token and the `.kitty.env` pointer
  below, and `SPEC_KITTY_PACKS_ROOT` is its canonical packs-root authority. An
  idempotent `spec-kitty upgrade` migration (`m_3_2_7_heal_provenance_paths`)
  rewrites any already-committed absolute built-in path back to the portable
  token with zero manual steps — this repo's own leaked paths in
  `.kittify/charter/charter.yaml` and `.kittify/agent_profiles_manifest.json`
  were healed the same way. A new `doctor provenance` facet reports any
  remaining leak with a heal hint.

- **Operator environment (SaaS tokens, org slugs, path overrides) now has one
  file to point at, loaded before anything else runs (mission
  `operator-config-ergonomics`, WP02; `#3495`; `FR-004`/`FR-004a`/`FR-005`).**
  Previously these values had to live in your real shell environment or be
  re-typed per project. A two-tier `.kitty.env` file — `${SPEC_KITTY_HOME}/.kitty.env`
  machine-wide, overridden by `<repo>/.kittify/.kitty.env` per-repo — is now
  loaded into `os.environ` **before** any other `spec-kitty` module is
  imported, so even import-time-gated behaviour picks it up. Precedence is
  **real-env > per-repo > home**: an explicit shell value always wins, and a
  per-repo file only arms the project it lives in (unlike a global `export`,
  which arms every project the shell later touches). `.kittify/config.yaml`
  gains a single `env_file` pointer (default `${SPEC_KITTY_HOME}/.kitty.env`).
  Fail policy is explicit: an absent file is skipped (the default for almost
  every project today); a present-but-unreadable `env_file` fails loud and
  names the file, because it gates auth; a malformed `KEY=VALUE` line is
  skipped; and a `SPEC_KITTY_HOME=` line inside the file is dropped with a
  warning to prevent locator recursion. An idempotent `spec-kitty upgrade`
  migration (`m_3_2_8_provision_kitty_env`) seeds the per-repo scaffold,
  registers the `env_file` pointer, and adds `.gitignore`/`.claudeignore`
  rules — seeding only values already present in the environment, never a live
  secret (secret-shaped vars are written as commented, blank templates). A new
  `doctor env-file` facet reports presence, tier, readability, pointer, and
  ignore-rule health with every value redacted through a fail-closed allowlist.

- **Opt-in release-candidate channel — catfood an rc without ever nagging
  operators who did not ask (mission `operator-config-ergonomics`, WP05;
  `#3496`; `FR-009`/`FR-010`).** A default-off `SPEC_KITTY_PRERELEASE`
  preference makes every "latest version" surface — `spec-kitty upgrade
  --agent-check` and the throttled startup nag — pre-release-aware only when
  explicitly opted in. Left unset (the default, unchanged for every existing
  project), only the latest **stable** release is ever surfaced, even when a
  newer rc exists on the index. Opted in, the newest PEP 440 pre-release is
  surfaced and the proposed upgrade is a **pinned** `spec-kitty-cli==<rc>`
  install, never a floating `--pre` flag. A new `doctor channel` facet reports
  the active channel. This ships the consumer half only; CI's rc build/publish
  cadence stays in `#3047`.

- **New architecture references tie the SaaS opt-in, `.kitty.env`, and rc-channel
  decisions together (mission `operator-config-ergonomics`, WP06; `FR-011`).**
  Two ADRs record the decisions:
  [`2026-08-16-5-operator-config-env-expansion-seam.md`](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
  (the kernel env-expansion seam, token provenance, and `.kitty.env` layering)
  and
  [`2026-08-16-4-rc-release-channel.md`](../adr/3.x/2026-08-16-4-rc-release-channel.md)
  (the default-off rc channel). A new
  [`team-kitty-saas.md`](../architecture/team-kitty-saas.md) architecture doc
  walks the full opt-in → project-store migration → admission/delivery-target →
  auth → history-disclosure → `sync now` flow with an end-to-end Mermaid
  interaction diagram. Consumption docs and the `spk-team-{sync,auth,tracker}`
  skills now point operators at the durable `.kitty.env` mechanism instead of a
  per-shell `export`.

- **An agent working the mission lifecycle — hitting a merge-gate rejection,
  an issue-matrix verdict, or an undrained SaaS sync — previously had to
  already know the mechanics, because they lived only in a maintainer's
  private notes (mission `self-documenting-repo` Bucket 2; `#3464`, follows
  `#3448`).** A second audit of that private memory routed the durable
  workflow / CI / git / status-&-sync mechanics into the repo's canonical
  homes: `docs/development/how-to/review-gates.md` now carries the
  (event-sourced) review-cycle + merge-gate mechanics and the issue-matrix
  discovery surface; a new `docs/operations/sync-drain.md` documents the real
  3-gate drain (`saas_disabled` → `missing_auth` → `missing_team`) and the
  `sync doctor` false-green trap; `coverage-signals.md` and
  `known-friction-points.md` gain the critical-path-move coverage remedy and
  the CI-label skip guard; `pr-landing.md` gains true-base/stale-stack
  diagnostics and a new `compress-mission-history.md` how-to; the
  architecture docs correct a **live stale-doc regression** (`AGENTS.md`
  claimed a `lanes.json`-absent `-WP##` fallback the resolver actually raises
  `MissingLanesError` for); three review-discipline heuristics enrich the
  doctrine tactics, and the `gh` "Closes #A,#B links only #A" trap lands in
  the tracker toolguide. A committed
  `agent-memory-workflow-migration-manifest.md` (with a completeness test)
  maps all 49 audited memories to a repo home, an already-home citation, a
  learned-fact note, or "keep-private". Dogfooding payoff: verifying against
  current code caught several _stale_ memories — the review-gate frontmatter
  mechanism was retired for an event-sourced one, and the drain's second gate
  was mis-remembered as `sync migrate` (retired).

- **An agent tripping a gate, hunting the right doctrine template source, or
  recovering a split-brain mission previously had to already know the
  answer — that knowledge lived only in a maintainer's private notes, not in
  the repo (mission `self-documenting-repo`; `#3448`).** A maintainer audit
  found this tribal knowledge nowhere in the shipped repo. Now it does:
  architectural/docs gate assertions (`write-side re-derivation`, `inert
  schema slots`, `relative-link fixer`) print a **content-anchored remedy
  derived from the gate's own logic**, so tripping a gate tells you how to
  satisfy it; `AGENTS.md` corrects the stale `src/doctrine/missions/…`
  template-source path to `packs/built-in/missions/…` (with a grep guard);
  six operator recovery runbooks for coord/lane split-brain scenarios are
  published under `docs/operations/`, each leading with the shipped
  `spec-kitty doctor … --fix` where one exists; and the docs-inventory
  freshen, mission wrap-up, and env/tracker conventions are now findable in
  `docs/development/`. A committed `agent-memory-migration-manifest.md`
  (with a completeness test) maps every audited gap-filler to its new repo
  home, its tracking issue, or an explicit "behaviour retired" — the audit
  surfaced five memories that were already stale (e.g. the shard-registration
  guidance retired by `#2671`'s auto-cover, and a `mission-gate-artifact`
  gate that never existed). Deleting the matching entries from a
  maintainer's live `MEMORY.md` stays a manual, per-operator checklist
  tracked in the manifest — this mission migrates the knowledge into the
  repo, it does not touch anyone's private memory file. Three behaviour
  quirks found along the way were filed, not fixed (`#3450`, `#3451`,
  `#3452`).

- **CI now builds each shippable module as its own reusable workflow, and a new
  `spec-kitty regen` lets contributors fix generated-asset drift themselves
  (mission `modular-per-package-ci-01M025GV`; `#3447`, closes `#3379`).** The
  monorepo already ships separately-packaged modules (`src/kernel`,
  `src/doctrine`, the `packs/built-in` data pack), but CI ran them as
  path-filtered jobs inside one monolithic `ci-quality` workflow, and the
  generated agent-command baselines + codex/vibe skill snapshots drifted
  silently when their source prompt templates changed — a contributor's
  one-line edit tripped a dozen parity gates a maintainer had to regenerate by
  hand (`#3379`). Now `kernel`, `doctrine` (fast + integration legs), and
  `packs` each build in an `on: workflow_call` module workflow invoked as a
  `uses:` job inside `ci-quality`, so a module has its own build boundary while
  its coverage still aggregates into the single run the Sonar reporter reads
  (reusable workflows, not `workflow_run` — coverage never fragments across
  runs). The architectural CI-model guards learned to resolve `uses:`
  delegation through one seam so a reusable-workflow caller is modeled as if it
  ran inline. `spec-kitty regen [--check]` regenerates the committed generated
  fixtures from source, byte-identical to a `PYTEST_UPDATE_SNAPSHOTS` run, from
  a single shared version pin; `--check` is the fork-safe freshness gate (it
  fails with the exact command + diff, since a fork PR's read-only token cannot
  commit back). A trust-tiered `regen-assets` workflow runs check-only on every
  PR, auto-commits on same-repo pushes, and offers a maintainer-label
  privileged path that ships disabled pending a security review. The 12-agent ×
  N byte grid that caused the churn is retired for structural invariants plus
  one canonical byte snapshot per render branch (markdown + TOML), so a
  source-prompt edit now regenerates at most one canonical fixture instead of
  ~14.

- **An org- or project-tier doctrine pack can now contribute a mission type
  that works end to end (mission `up-mission-type-seam-01KZY1JB`; `#3424`,
  closes `#3397`).** Before, a mission type shipped by an org or project pack
  could be declared and activated but not used: `mission create`, charter
  activation, and action-sequence projection all resolved against a
  built-in-only roster, so a custom type either hard-failed or — worse —
  silently resolved to an empty action sequence that planned nothing yet
  reported success. Now a layered, pack-aware lookup resolves built-in, org,
  and project mission types in that precedence order with a genuine action
  sequence and template set, and four operator-facing surfaces stop reporting
  falsehoods: `charter mission-type list` shows the real source layer,
  `mission-type show` succeeds for an activated non-built-in type, `doctrine
  mission-type list` actually layers, and `charter activate`'s step-removal
  warnings compare real sequences. Three previously silent degradations —
  malformed mission-type YAML, an unreadable roster directory, and an empty
  action sequence from a non-built-in layer — now fail loud, naming the
  offending file and layer. This is the availability slice only; mission-type
  is deliberately not promoted to a first-class doctrine artifact kind (ADR
  `2026-08-13-1`).

- **Hosted-sync consent is now per-project: one immutable `project_uuid` owns
  one physically separate sync store and one explicit consent decision
  (mission `per-project-sync-consent-ledgers-01KZKMQZ`; `#3262`, pairs with
  SaaS `#585`).** Before, a shared journal/ledger/queue mixed every project's
  rows and a filter defect could deliver another project's data (the #3030
  consent incident). Now each project's consent, consent epochs, journal,
  delivery results, body/offline queue, target binding, and migration state
  live in a UUID-owned `ProjectSyncStore` no other project's operation can
  open; `spec-kitty sync opt-in` records the only local grant authority
  (offline-capable, never inherited from login/URL/slug/path/env), opt-out is
  an immediate epoch-sealing barrier that never deletes captured rows, and
  `SPEC_KITTY_ENABLE_SAAS_SYNC` is strictly deny-only — arming it grants
  nothing. Local consent additionally pairs with an independent target-scoped
  SaaS admission generation, and `project_not_admitted` refusals park
  terminally instead of retrying. Operators migrate legacy shared state with
  the new copy-only, resumable project-store cutover commands
  (`spec-kitty sync project-store-preview` / `-migrate` / `-status` /
  `-quarantine` / `-history`); the retired shared-store `sync migrate`
  refuses with guidance.
  See [Per-Project Sync Consent](../guides/project-sync-consent.md).

- **The declarative transition-gate design is now documented as architecture,
  and two mission-doctrine docs point at the right paths again (`#3378`).**
  Before, the settled model for how transition gates work — the declarative
  `gate` artefact kind, where a gate executes, the trusted-publisher rule, and
  the typed-severity outcome — lived only in scattered discussion, and
  `mission-type-resolution.md` / `doctrine-kinds.md` still named the
  pre-relocation `src/doctrine/missions/` source of truth. Now six Proposed
  ADRs plus a `mission-gates.md` explanation page (with three render-verified
  diagrams) capture the design in one place, and those two docs are retargeted
  to the live `packs/built-in/missions/` paths.

- **Documentation can now be marked `durable` — a standing reference that is
  never flagged as stale draft (mission `docs-plans-closeout-01KZTK2J`;
  `#3368`).** Before, a long-lived throughline doc could only be `active`, so the
  freshness SLA eventually nagged it toward "review or retire" like any aging
  draft. Now `durable` is a reserved `doc_status` across the whole authority
  chain (the `042-common-docs` directive, the `DocStatus` enum, the common-docs
  styleguide and tactics, and the never-stale freshness rule), so a deliberate
  standing document is left alone. This closeout also retires ~60 shipped or
  superseded working notes in place (content preserved, evidence-cited) and
  gathers the domain plans under `docs/plans/domains/`.

- **`spec-kitty intake` now recognises an optional v1 handoff packet so upstream
  requirements tools can seed a mission without the agent re-inventing FR/AC
  ids.** A packet is ordinary Markdown; YAML frontmatter with `handoff_packet: 1`
  is additive. Unknown versions and malformed YAML degrade to today's prose
  intake. `intake --auto` also scans `.handoff/*.md`. Contract:
  `docs/contracts/handoff-packet-v1.md`.

- **The doctrine documentation site now shows rendered schema diagrams of the
  doctrine artefacts, drawn locally with no network egress (mission
  `doctrine-schema-diagrams-01KZTQTH`; `#3366`, `#3354`).** Before, the doctrine
  layer's shape — the relationship graph, the mission-step contract and action
  index, the cross-kind overview and the full agent-profile schema — lived only
  in prose, and the docsite had no way to render PlantUML at all. Now
  code-grounded `@startyaml` diagrams are authored for each and **drift-guarded
  against the live frozen models** (a diagram that falls out of sync with the
  code reds the build), then rendered offline by a version+sha256-pinned
  PlantUML running inside a network-isolated container — so building the docs
  sends nothing off-machine. Each rendered figure carries derived alt/aria text
  for accessibility.

- **A shrink-only census gate now guards the 40 test sites that pin
  `SPEC_KITTY_HOME`, so the collision can only get smaller from here (mission
  `isolated-home-pin-guard-r1a-01KZNMA3`; `#3121`).** Before, nothing stopped a
  41st ad-hoc home pin from landing, and a naive "converge them all" cleanup
  would silently delete the load-bearing isolation those fixtures carry. Now a
  content-addressed census — pinned as debt at a frozen SHA — plus a canonical
  `canonical_home` owner fixture, a falsifiability probe, and a halt gate red the
  build if the pinned set grows. Contributor-facing test infrastructure only (no
  `src/` change); this lands the _instrument_ ahead of the follow-on adoption
  (R1b), so `Refs #3121` rather than `Closes`.

- **The dead-symbol allowlist's provenance is now a machine-readable
  `source_module=` field instead of a parsed comment, so refreshing a still-dead
  allowlisted symbol no longer depends on comment hygiene (mission
  `symbolkey-source-module-01M0B0SF`; `#3552`).** Before, a content-tier entry's
  originating module lived only in its free-form `# module::Name` comment,
  which the refresh helper (`_refresh_dead_symbol_hashes.py`) had to
  tokenize-parse to recover — a fragile source of truth that had drifted into
  multiple comment formats, and same-name symbols from different modules
  couldn't be told apart structurally. Now every content-tier `SymbolKey`
  carries an optional, provenance-only `source_module=` keyword as the single
  canonical source; the `# module::Name` comment stays in place as
  human-readable audit trail, but the machine comment-parsing path is retired,
  and same-name entries disambiguate on the field rather than on comment
  convention. Test infrastructure only, no `src/` change (no version bump).

- **`spec-kitty --version` / `-v` output is now a single copyable line (mission `copyable-version-output-01KW6N9V`).** The version callback no longer renders the ASCII-art banner before the distribution-aware version string, ready to paste into an issue report. Community contribution by @zohar.

- **`merge/baseline.py`'s committed-`meta.json` reader now shares the one kernel L1 malformed-JSON authority instead of re-implementing it.** (#3330, follow-up to #3259/#3319) `_read_committed_meta_json` decoded the `git show <target>:meta.json` blob with its own `json.loads`/`isinstance` pair — a second, gate-invisible re-implementation of the malformed contract #3259 consolidated everywhere else. **Before:** two independent decoders could drift on what counts as malformed. **After:** the same `git show`-blob text is decoded via `kernel.meta_decode.decode_meta`, matching the sibling git-plumbing site (`git/ref_advance.py`); the two `BaselineMergeCommitError` message shapes callers depend on are unchanged.

- **One canonical mission-type reader; the legacy `{"mission": …}` field is no longer resolved and the silent `software-dev` default is gone — so the dashboard, retrospectives, and identity now show a mission's _true_ type instead of masking everything as `software-dev`.** (#3598, epic #3410) ~10–12 hand-rolled `meta.json` mission-type readers each re-derived their own field order and default, and they disagreed: the charter path read only `mission_type` while the CLI path also honored the legacy `mission` field (so `{"mission": "software-dev"}` resolved _typeless_ one way and _software-dev_ the other), four readers silently defaulted `software-dev` (masking typeless/typo'd missions), and a dashboard reader read **only** the legacy field. **Before:** a typeless or `mission`-only mission was silently shown/recorded as `software-dev` across the dashboard, retrospective records, and mission-identity resolution (including the context/status/acceptance/merge-gate identity payloads, via a downstream normalizer that re-defaulted to `software-dev`). **After:** every runtime reader resolves through one shared `read_mission_type(meta)` seam (canonical `mission_type` only — no legacy fallback, no default), and the machine-facing identity normalizer no longer re-masks the neutral result; a typeless mission surfaces as neutral typeless / `Unknown (…)` on the dashboard, records its true type (or empty) in retrospectives, and resolves neutrally in the identity/status/acceptance/merge payloads. A structural gate (`test_mission_type_reader_invariants.py`) pins every reader to the shared seam and fails the build on any new legacy read or `software-dev` fallback (genuine create-time/upgrade writers and the field-aware audit tool carry encoded, rationale-bearing allow-list exemptions). **Deliberate behavior change with blast radius:** a legacy mission carrying only `{"mission": …}` **stops resolving** (goes typeless), and this _compounds_ with M3's per-type hard-fail (silently-resolving → typeless → hard-fail). The safety net is the M0 `spec-kitty migrate backfill-mission-type` command (#3614), which **must be run against a project before this change reaches it** — it mints a profile-resolving `mission_type` into legacy `mission`-only missions and never fabricates an unresolvable type. Folds: #2901 (WP-frontmatter tolerant reader — verified already landed) and #2477–#2480 (inline meta reads — already exempted in `inline_meta_read_allowlist.yaml`). See ADR 2026-08-22-1.

### 🐛 Fixed

- **Every `spec-kitty` CLI command no longer eagerly loads the full status-orchestration and workspace machinery at import time — restoring the cold-import boundary the explicit owned-checkout work had quietly broken.** (landing fix; restores the #1461 boundary regressed by #3843) **Before:** the owned-checkout lifecycle wired `core.owned_mission` into the `task_utils.support` leaf that 37 CLI command modules cold-import, and `owned_mission`'s module-level imports pulled the entire `specify_cli.status` package (30+ submodules) plus `workspace` into every command's import path — a needless startup cost and a re-entrancy hazard the boundary exists to prevent. It surfaced as a red guard on `main` (`test_charter_package_cold_import_keeps_status_orchestration_out`). **After:** `owned_mission` defers those two status-heavy imports to the one function that uses them (`resolve_owned_mission`), so cold-importing any command loads zero status/workspace modules; runtime behavior is unchanged. A new architectural gate (`test_cold_import_status_boundary.py`) now enforces the boundary at _any_ edge across the charter package, the `task_utils` leaf, and `owned_mission`, so a future reconnection is caught at its source rather than only through one command.

- **Coord-topology missions now agree on one authoritative commit surface across create-time, `spec-commit`/`commit_router`, and the task commands — closing a class of stranded-coordination-branch and silent-misroute defects.** (mission `coord-commit-surface-authority-01M1M553`; parent epic #2160; closes #2533 and #2300; B16-clause-2 of #2739 investigated and disproven — folds into #2533) A single kind-aware rule (`src/specify_cli/coordination/surface_authority.py`: `coord_topology_reachable` + `resolve_surface_authority`) is now the canonical authority all three loci consult. **Before:** three layers disagreed. (1) `mission create --pr-bound --start-branch <feature>` unconditionally minted `topology: coord` (the `pr_bound` arm short-circuited before any protection check), stranding an empty coordination branch on an unprotected feature branch and driving `spec-commit` into a split-brain "materialized but carries no mission dir" primary-fallback (#2533). (2) The three task commands diverged for the same coord+protected situation — `move-task` skipped the redundant primary commit (exit 0, correct), `map-requirements` refused (exit 1), and `mark-status` had drifted to event-log-only (no commit) — with each hardcoding its own verdict (#2300). (3) `commit_router` had four silent `→ primary` fallbacks (unresolvable `mid8` and coord-worktree-resolution exceptions) that could misroute a coordination-kind write to the primary checkout without signalling. **After:** create-time mints `COORD` only when coordination routing is actually reachable (`pr_bound AND (primary_protected(target) OR current==primary)`) — `--pr-bound --start-branch <unprotected>` now yields `SINGLE_BRANCH` with no stranded coord branch (keyed on the primary **target** branch's protection, preserving the #2581 pr-bound-on-feature-branch-with-protected-target → coord contract); `move-task`/`map-requirements` derive their verdict from the shared rule (behavior preserved — lifecycle-kind routes to coordination at exit 0, planning-kind on a protected primary refuses at exit 1 with a unified remedy), and `mark-status` stays event-log-only by construction; and all four `commit_router` corrupt-state fallbacks now fail loud (`CoordWorktreeResolutionError`) instead of silently writing to primary, while the two legitimate primary-routing early-returns (primary-kind / coord-less topology) are preserved and documented. The shipped `#2739` typed no-op contract (`unchanged` → exit 0) is unaffected. The `coordination/` layer takes no new `cli` import (the rule module depends only on `mission_runtime`).
- **Custom mission types are now first-class across dispatch, the plan-substantiveness gate, and the CLI's fallback signal — instead of quietly degrading or crashing.** (landing fold for mission `custom-mission-type-second-class-citizens-01M1FQXD`; #3830, #3831, #3832) **Before:** three related gaps. (1) The composition-dispatch probe logged a full ERROR traceback via `logger.exception` for every custom-type dispatch, because `UnknownMissionTypeError` — the ordinary, expected outcome for any non-charter-activated custom type — was treated as a genuine resolution failure. (2) A pack-provided `plan-field-declaration.yaml` resolved through `resolve_template`'s mission-agnostic tiers (global override, legacy, global non-mission) would gate **every** undeclared custom mission type's plan against one unrelated type's fields, and a present-but-broken declaration (unreadable, mis-encoded, or carrying an unknown/typo'd key) failed with an unguarded exception instead of a diagnosable error. (3) `mission-type current`'s CLI-visible software-dev fallback signal (#3831/FR-005) silently dropped any _other_ warning raised in the same captured block. **After:** the dispatch probe logs `UnknownMissionTypeError` at DEBUG (still diagnosable, never an ERROR on the happy path) and reserves ERROR/`logger.exception` for genuine failures; `_pack_provided_declaration` only honors a mission-scoped resolution (path containing `/missions/{mission_type}/`) and the parser now fails loud (`_PackDeclarationError`) on an unreadable/mis-encoded file or an unknown key, mirroring `expected-artifacts.yaml`'s `extra="forbid"` posture; and `mission-type current` re-emits every non-fallback warning through `warnings.warn_explicit` instead of dropping it. A dead pre-#3832 helper (`_has_substantive_technical_context`) is also removed as a campsite fold, superseded by the generalized `_is_plan_substantive_for_type`.
- **`spec-kitty upgrade` no longer silently drops skill-content migrations on Windows when the managed `SKILL.md` is read-only.** (mission `upgrade-surface-durability`; fixes #3771) **Before:** managed skill trees are set read-only by `_make_tree_read_only`, and on Windows the atomic `Path.replace` inside `write_text_within_directory` fails with `[WinError 5]` when the target is read-only. The `2.1.2_fix_*` skill-content migrations (glossary-context, orchestrator-api, runtime-next) route through that write path, caught the `PermissionError` as an `OSError`, recorded the migration as `failed` in the ledger, and left the old skill content in place — the upgrade still reported overall success, so the stale content was invisible. **After:** `write_text_within_directory` restores the target's write bit before the atomic replace (mirroring the already-blessed `runtime/generated_writer` pattern, skipping symlinks so it never chmods through a link), so the rewrite lands on Windows and every migration entry point on that path is fixed at once. The replaced file keeps the temp file's writable mode exactly as on POSIX today. Regression coverage simulates the Windows `os.replace` failure on Linux CI (a bare `chmod(0o444)` does not reproduce it off Windows, since the rename keys on the directory bit) plus a native `skipif(win32)` contract test.
- **`spec-kitty upgrade` now refreshes a stale `.claude/CLAUDE.md` orientation surface (and every other harness context file) instead of leaving an outdated version string that contradicts the live `SessionStart` hook.** (mission `upgrade-surface-durability`; fixes #2265) **Before:** the `<!-- spec-kitty:orientation -->` block was stamped at `init` and never re-emitted on an up-to-date upgrade — `session-start` is stdout-only, the one-shot `rc39` refresh migration is version-gated and never fires on the "already up to date" path, and the always-on surface-repair leg's `SessionPresenceProvider` did only a bare marker-existence check (never reporting the block stale) while its repair actioned only missing files. An agent then loaded an orientation block frozen at the init-time version. **After:** the provider is version-aware — `probe()` reports `STATE_STALE` for a present context file whose stamped `**Spec Kitty v…**` version differs from the installed CLI, and `repair()` actions `STATE_STALE` alongside missing, rewriting the block in place via the canonical `SessionPresenceContent` emitter. Because surface-repair runs on every `upgrade` (including "already up to date"), the refresh is idempotent and version-independent, and it covers every version-stamped orientation surface uniformly — both context files (`.claude/CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, copilot instructions) and rule/steering files (`.cursor/rules/spec-kitty.mdc`, `.kiro/steering/spec-kitty.md`). The version stamp is parsed only inside the `<!-- spec-kitty:orientation -->` marker block (so a stray stamp elsewhere in the file cannot fool it), and the comparison is version-only, so a legitimate health-line change at the same version does not churn the block; a hand-edited block with no parseable stamp is left alone.
- **Adjudicated the #2316 uv-tool auto-upgrade "env/`--python` drift" as a stale-test artifact, not a product regression, and added the missing end-to-end coverage.** (mission `upgrade-surface-durability`; closes #2316) The issue asked to restore threading of a custom `UV_TOOL_DIR` and the receipt `--python` pin into the `uv tool install` auto-upgrade argv, and to un-skip two tests. Investigation as the upgrade owner found the behavior is **not** lost: the argv/env assembly moved into `compat.remediation` during the god-module decomposition and is wired end-to-end through `run_upgrade_ux`; the two tests were deleted (in an ancestor of `main`) as inert bodies pinned to the retired inline seam. The genuine gap was end-to-end coverage — nothing proved the `run_upgrade_ux → plan_remediation → _default_upgrade_runner → subprocess.run(env=…)` chain still delivers both. A new hermetic regression pins it at the correct seam (patching `detect_runtime`), verified non-vacuous against the exact #2316 failure signature. No product change.
- **Lifecycle commands on a protected-primary / coordination-topology mission no longer leave the working tree dirty, report false success, or refuse with un-followable guidance — the commit-router, the protected-primary refusal, and the create/discard commit boundaries now agree on where planning artifacts land.** (mission `commit-boundary-router-integrity`; epic #2739; fixes #3784, #2693, #3716; B02 of #2739 was already fixed on main) A single shared defect class — the commit-router's file-kind filter, the protected-primary refusal path, and coordination-topology routing disagreeing on the primary/planning commit surface — surfaced as four distinct failures, each fixed red-first (`@pytest.mark.regression` reproduction through the real entry point, then relocated to a permanent guard):
  - **#3784** — On a coordination topology, `implement`'s claim-commit bundle dropped only the two `STATUS_STATE` files (`status.events.jsonl` / `status.json`) from the primary-root commit but let the coordination-worktree `tasks.md` (a `TASKS_INDEX` kind) survive, so `safe_commit(worktree_root=repo_root, …)` tripped `SafeCommitPathPolicyError` ("refusing to stage path under `.worktrees/`") and left the WP file uncommitted. **After:** the bundle excludes **any** `.worktrees/`-nested path (the real #2155 invariant — "no `.worktrees/` path reaches a primary-surface `safe_commit`"), via a single extracted `_primary_surface_status_paths` helper.
  - **#2693** — `mission create` committed only `meta.json`; the step-8 event emission then mutated `status.events.jsonl` **after** the commit, and `tasks/README.md`/`tasks/.gitkeep` were left untracked and unreported, so a create that "succeeded" left a dirty, undisclosed scaffold. **After:** event emission runs **before** one transactionally-complete commit of the create-owned scaffold (`meta.json` + `status.events.jsonl` + `tasks/` scaffolding); `spec.md` (deliberately owned by `/spec-kitty.specify`, per #846) stays uncommitted but is now **disclosed** in the `--json` payload's `uncommitted_artifacts` with its responsible command — nothing generated is ever untracked _and_ undisclosed.
  - **#3716** — `mission close --discard` reported success while leaving the `meta.json` flatten (popping `coordination_branch`/`topology`) uncommitted — it was the last write on the discard path and had no commit leg — and stamped the persisted retrospective `provenance.kind: runtime_post_completion` on an abandoned mission. **After:** the flatten is committed to the **primary** surface (the coordination branch is already deleted, so the primary `target_branch` is both destination and degrade ref; the sibling retrospective commit degrade was fixed the same way, so `--discard` leaves a clean tree), and a new `runtime_abandoned` `ProvenanceKind` is threaded through the discard leg so an abandoned mission is no longer recorded as completed.
  - **#2739** — Protected-primary `spec-commit` surfaced un-followable and misleading outcomes. **After:** B01 — the command `--help` and the `no_op_wrong_surface` remedy text drop the impossible "materialise the coordination worktree and retry" hint (primary/planning artifacts never route to coordination) and name the two real remedies (`--start-branch <feature-branch>` or `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`, the latter also added to the router diagnostic); B03 — an `unchanged` no-op now carries a machine-readable `reason` (`no_op_already_committed` vs `no_op_no_changes`) so a real success is distinguishable from a silent no-op; B11 — a directory argument is rejected early with a clear files-only message instead of the opaque staging-area backstop; B16 — a coordination-partition file written to the primary tree that routes to coordination where nothing stages is now refused as `no_op_wrong_surface` (via `_paths_uncommitted_in_primary`) instead of falsely reporting `success` while landing nowhere.
- **`spec-kitty charter context --include directive:<id>` now resolves the exact directive IDs the `--json` surface advertises, at parity with the `tactic:`/`agent-profile:` selectors.** (mission `charter-command-honesty`; fixes #3816; parent epic #3809) **Before:** the directive selector returned `EXIT 1 "No directive found"` for a valid, active slug ID (`025-boy-scout-rule`, `001-architectural-integrity-standard`) — the very IDs `charter context --action <x> --json` enumerates — while resolving only the `DIRECTIVE_NNN` form. The two identity spaces diverged: `--json` advertises the file-stem **slug**, but the directive lookup ran the id through a numeric-only formatter that let the slug fall through and miss the `DIRECTIVE_NNN`-keyed repository, so an injected directive ID was a dead end for the compaction path (#3811). **After:** `DirectiveRepository.get` normalizes every identifier through the single canonical authority (`normalize_directive_id`) — slug, numeric shorthand, and `DIRECTIVE_NNN` all resolve the same directive — and the `--include` renderer hands the identifier through verbatim, echoing the resolved canonical id in its header. The same slug-vs-`DIRECTIVE_NNN` divergence also silently dropped **every** directive from the gated `DoctrineService.directives` property whenever `activated_directives` was configured (item keys spoke `DIRECTIVE_NNN`, the activated set spoke slugs); it is closed by comparing both sides in canonical space. A close-by-construction regression test asserts every advertised built-in directive slug resolves `EXIT 0`. Verified red-first through the real `charter context --include` entry point.
- **`spec-kitty charter generate --from-interview` now reports a present-but-corrupt `answers.yaml` honestly, instead of claiming no answers exist.** (mission `charter-command-honesty`; #2940) **Before:** the read boundary degraded BOTH a genuinely-missing file AND a present-but-unreadable one (invalid YAML, or a top level that is not a mapping) to the same `"No charter interview answers found"` error — which sends the operator to re-run the interview, when the real fault is a corrupt file that a fresh interview would silently overwrite, masking the problem. **After:** a present-but-malformed answers file produces a distinct diagnostic that names the file and its malformed shape and points at repair/`--no-from-interview`, while the genuinely-missing case keeps its original "run the interview" message. The interview→generate round-trip itself was already correct on current main; a close-by-construction regression test now pins it end-to-end (real `charter interview` write → `charter generate --from-interview` read, asserting the answers are consumed rather than silently replaced by defaults) so it can never regress. (The original report — Spec Kitty 3.2.6, macOS, `uv tool` install — could not be reproduced from source; the round-trip lock guards the contract regardless.)
- **`spec-kitty charter lint`'s clean-working-tree contract is now pinned by a regression guard (no behavioral change) — the report it writes stays gitignored, so it never trips a downstream dirty-tree guard.** (mission `charter-command-honesty`; #3435) `charter lint` writes `.kittify/lint-report.json` — a load-bearing artifact the dashboard decay tile and the SaaS dossier read from disk — so the read-only-diagnostic honesty contract is met by shipping the gitignore entry (`spec-kitty init` authors it; a backfill migration heals upgraded projects), not by suppressing the write. That entry was already shipped on current main; this change adds a close-by-construction regression guard that runs the real engine write through the real init gitignore authoring and asserts the tree stays clean (with a control proving the same write would surface as untracked without the ignore entry), so a future regression that either stops writing the report or drops the ignore entry is caught.
- **`spec-kitty next` no longer restarts a merged mission or stalls on an operator-canceled work package — the loop now decides from the committed status authority, not a stale coordination worktree or a lane-only predicate.** (mission `next-committed-state-authority`; #2947, #3780; milestone 3.2.6; parent epic #1619) **Before:** two independent defects. (1) With a stale coordination worktree checkout left at an old commit, `spec-kitty next` ignored the committed `status.json` (all WPs `done`) and the assigned `mission_number`, fabricated a fresh runtime run from `discovery`/`research` pointed at the stale checkout where the mission artifacts were missing, and `agent tasks status` rolled the mission up all-`planned` — completed work looked unstarted (#2947). (2) The review-step advancement predicate `_wp_blocks_step` was lane-only (`lane not in (DONE, APPROVED)`), so an operator-canceled WP — an honest ending post-#3774 on the accept/merge axes — was treated as not-handed-off and stalled the loop (#3780). **After:** (1) `next` resolves committed state **before** selecting a coordination workspace: a merged mission (committed `mission_number` assigned **and** committed status all-accepted) returns `kind: terminal` in advancing mode (creating **no** run) and `kind: query` / `mission_state: done` in read-only query mode; a merge/status conflict, or an actionable step whose workspace checkout lacks the mission's artifacts, fails closed with a structured `kind: blocked`; and `agent tasks status` reads committed lanes. The merge signal is the committed `mission_number` only — never transient merge-state / an active `MERGE_HEAD`, which are absent precisely when a mission is finished. (2) `_should_advance_wp_step` threads the reduced snapshot's provenance (derived from a **single** status reduction that preserves the `CanonicalStatusNotFoundError` fail-loud contract) and routes the review/implement advancement predicate through the shipped `is_acceptable_ending` / `has_operator_provenance` authority — a canceled-**with-operator-provenance** WP advances, a **synthetic** cancellation stays blocking (fail-closed). Both surfaces consume one committed-authority module (`src/runtime/next/committed_authority.py`); the shipped acceptable-ending authority and the lane state machine are unchanged. Verified red-first through the real `next` entry points with live before/after execution. Two secondary observations from the surfacing squad (a redundant coordination read in `merge/done_bookkeeping.py`; a `reason_source` denylist gap in `core/upstream_contract.json`) are tracked as separate follow-ups.
- **`spec-kitty merge` now honors a mission's declared retention policy instead of silently deleting branches and worktrees a mission asked to keep.** (mission `merge-honor-retention-policy-01M1CA0E`; fixes #3131) **Before:** post-merge cleanup was driven entirely by the `--delete-branch`/`--keep-branch` and `--remove-worktree`/`--keep-worktree` flags, both defaulting to delete/remove; a mission had no machine-readable way to express "keep my branches and worktrees," so a prose constraint in `spec.md` was invisible to merge — on one observed mission, merge deleted six lane worktrees, six lane branches, and the mission branch with no warning that the cleanup contradicted the mission's stated intent. **After:** a mission's `meta.json` can carry `retain_branches`/`retain_worktrees`; merge resolves effective cleanup via one resolver (`resolve_merge_retention`, `core/paths.py` — an I/O-performing resolver that reads the mission's `meta.json`, like `resolve_merge_target_branch`) with precedence **explicit CLI flag > meta.json retention > default**, failing closed toward retention on any ambiguity (a corrupt `meta.json` aborts the merge; a malformed non-boolean value retains + warns, never truthiness-coerced to delete). An explicit CLI delete override still works but is never silent — it prints a recorded notice naming the contradicted policy. The coordination branch, worktree, and marker are torn down (or retained) as one coupled decision so partial retention can never leave a half-torn coordination state, and `merge --abort` honors the same coupled decision. The internal merge scratch worktree is unaffected and always cleans up. Retention is mintable at creation via `spec-kitty agent mission create --retain-branches --retain-worktrees`. Non-retaining missions are unchanged — cleanup behavior stays byte-identical.

- **Adversarial review squads run _profiled_ again — the two doctrine lenses the squad relies on (`doctrine-daphne`, `randy-reducer`) are re-activated, so delegates stop silently dispatching with no profile, boundaries, or directives applied.** (enabler mission `tidy-charter-cutover-surface`; closes #3810) **Before:** the shipped charter activation allowlist (`src/charter/activation/packs/default.yaml`) omitted exactly those two lenses, so the FR-014 activation gate returned `EXIT 1 "is not activated"` and a compliant delegate — whose only sanctioned raw-YAML fallback is for CLI-less harnesses — had no recovery and proceeded **unprofiled, with nothing erroring at the orchestrator**. **After:** both lenses are activated in the default pack (nothing deactivated), the gate resolves them cleanly, and a regression test pins the squad's hardcoded lenses as a subset of the activated set. The near-term half of profile-load epic #3809; the durable orchestrator-inject seam remains #3811.
- **`spec-kitty charter bundle validate` now catches byte-identical _doubled-leaf_ synthesis artifacts (`.../provenance/provenance/*`, `.../styleguide/styleguide/*`) — a corruption class its name-keyed pairing checks previously missed.** (enabler mission `tidy-charter-cutover-surface`; closes #3819) Investigation found **no reproducible defect in the current artifact writer** — every path-join is flat and a twice-run re-synthesis produces zero doubles, so the historical doubled files came from a superseded writer or manual tooling. The risk is therefore closed by a **detection guard**, not a phantom code fix. Charter synthesis artifacts remain a **trackable-by-design** surface (per the KD-2 commit-ready contract); they are _not_ gitignored.
- **Coding agents — especially smaller models — no longer stall mid-implementation to demand human approval and build "prove every step was signed off" scaffolding; and the review/accept gates now capture real, bound evidence instead of unattributed notes.** (mission `governance-at-the-gate`; #3685, #3682) **Before:** the decision-documentation directive (`DIRECTIVE_003`, `required`) was delivered into the `implement` action bundle — directly, and transitively via an implement-scoped procedure whose `references` link the resolver promoted to an unconditional `requires` — so a literal reader composing the `required` directives landed on "author a durable decision artifact, alternatives, rationale, traceable" _during implementation_ and stopped to ask a human. Compounding it, the doctrine-delivery resolver was enforcement-flat and tension-blind: the `Enforcement` levels had no ordering, and the tension arbiter (`reconcile-change-scope-tensions`, itself the weakest `advisory`) never reached the agent _as_ an arbiter — so a weak model had no signal that a brake outranked a do-more rule. Separately, at the deciding gates the evidence was thin — an `in_review → approved` transition recorded an unattributed prose note (no `policy_metadata`, no `review_ref`), a first-pass approval wrote no `review-cycle` artifact at all, and `spec-kitty accept` left `acceptance-matrix.json` an unfilled `pending` scaffold. **After:** decision-documentation is delivered at the deciding gate (`review`) and removed from `implement`, with a class-level gate that fails if any `required` decision-documentation directive is ever scoped back onto implement (directly or transitively); the `Enforcement` levels carry an explicit rank and a structural gate forbids a `reconciles_tension` arbiter ranked below what it arbitrates (the arbiter is promoted to match its operands and is now delivered _as_ an arbiter, with co-delivered tensions annotated on the bundle); and the approve/accept gates capture real evidence — the approval event carries the reviewer's `policy_metadata` (tool/profile/model/shell-pid) and a `review_ref`, a first-pass approval auto-authors an `approved` `review-cycle` carrying a reproduction command, and `accept` populates `acceptance-matrix.json` criterion rows from the recorded review evidence (only from a genuine `approved` verdict — a stale rejection can never fabricate a pass). Follow-up #3805 tracks the durable resolver fix for the soft-`references`-as-`requires` modeling that made the transitive leak possible.

- **`auth status` and `auth doctor` no longer hand-roll an all-clear beside contradicting token details.** A new typed `HealthVerdict` authority derives the headline from a closed `ok`/`unknown`/`fail` state and requires evidence for definite claims. Offline, an expired access token with an unproven refresh chain renders “Cannot verify”; `auth doctor --server` can resolve that same state to a real `ok` or `fail`, and a present-but-unhealthy session raises F-008 instead of “No problems detected.”

- **Auth readiness now evaluates the canonical stored session without leaking storage failures, and lifecycle emission separates local persistence from hosted fan-out.** `TokenManager.session_assessment` records whether evaluation completed, whether the session is usable, and a closed non-empty reason; readiness consumes that assessment instead of treating an unreadable store as a simple logged-out state. Lifecycle artifact phases can now be persisted locally without fan-out, while the existing composed entry point still offers the same persisted envelope to registered hosted adapters. `setup-plan` builds its gate and final result through side-effect-free local outcome objects, so local verification remains authoritative and reporting remains a separate final step.

- **HTTPS doctrine bundle fetches now persist ETags separately from pack versions and safely resolve Artifactory `version` metadata.** Existing `source_type: https` URLs with a valid `/artifactory/<repository>/<item>` path are recognized automatically; `source_type: artifactory` is also available to enforce that intent. Successful downloads are buffered before one exact-item AQL response co-attests the `version` property and SHA-256, and the checksum must match those exact bytes before extraction or snapshot promotion. Conditional validators are reused only for the same query-free source and an intact local snapshot; query-bearing URLs always fetch unconditionally rather than collapsing distinct resources or persisting signed parameters. A 304 deliberately leaves the prior snapshot and sampled version byte-for-byte unchanged.

- **A checkout-controlled `.kittify/saas-auth.json` carrying only `team_slug` no longer scopes the operator's stored OAuth session (EXPERIMENTAL-spec-kitty#765).** Before, with no service token in the environment or auth file, the file could choose the per-request team while `load_auth_context` supplied the personal OAuth bearer and canonical server target. `team_slug` from that file is now honoured only alongside the file's own `token`; set `SPEC_KITTY_TEAM_SLUG` to choose a team for an OAuth-backed session.

- **`ZeitgeistClient.offer()` now posts presence/focus/session control envelopes to a real relay's `/managed/control` endpoint with the headers it actually requires, instead of a route that always rejected them (`FIX-M2-10`).** Every `offer()` call — `presence()`, `focus_start/heartbeat/pause/end()` — was POSTing its `{op, request_id, args}` envelope to `<relay_url>/events`, the baseline Beacon-shaped route (`zeitgeist/server.py`), which has no `op` dispatch of any kind and structurally cannot process it; against a real, correctly-configured relay this was a 422 on every single call, discovered by `DQA-M2-02`'s Docker-local suite. `offer()` now targets `/managed/control` (`zeitgeist/managed.py`'s real presence/focus/session op dispatcher), includes the `schema_version` field `managed_control.schema.json`'s `ControlEnvelope` requires, and sends both gates a real relay enforces on that route: `Authorization: Bearer <token>` (the outer, unconditional `AuthenticationMiddleware` gate every route but `/health` sits behind) and `X-Zeitgeist-Capability: <token>` (`managed.py`'s own capability check, verified against a separate secret). Both headers carry the same single credential `credentials.py`'s `checkout` flow already stores per repo — the same value `subscription.py`/`operability.py`'s already-landed callers already forward as the capability header — rather than introducing a second stored secret. Covered by a new protocol-faithful local double (`tests/zeitgeist_client/conftest.py`'s `ManagedControlDouble`, mirroring `managed_auth.SharedSecretCapabilityVerifier`'s real HMAC wire shape and kind-scoped capability grants) in addition to the existing recording double.

- **`FilteredStream.watch()` now sends `Authorization: Bearer <token>` on its `GET /managed/stream` connection, not just `X-Zeitgeist-Capability` — the same header-omission class `FIX-M2-10` fixed for `offer()`'s `POST /managed/control` path, discovered from that bead's own `HANDOFF.json` open issues (`FIX-M2-13`).** `GET /managed/stream` sits behind the SAME outer, unconditional `AuthenticationMiddleware` gate every route but `/health` sits behind (`zeitgeist/auth.py`, checked before `managed.py`'s own handler ever runs); sending only the capability header — the pre-fix behaviour — meant a real relay answered every `watch()` connection attempt 401, regardless of whether the capability credential itself was valid. Both headers now carry the same single stored credential (`TeamStreamConfig.capability_credential`, sourced from `credentials.py` via `subscription.resolve_stream` exactly as before), the identical "one credential, two headers" model `transport.py`'s `offer()` already uses. Reconnect/backoff behaviour and `TeamStreamConfig`'s shape are unchanged. Covered by a new protocol-faithful local double for `GET /managed/stream` (`tests/zeitgeist_client/conftest.py`'s `ManagedStreamAuthDouble`, enforcing the same two real gates in the same order/401-vs-403 split `managed.py`/`managed_auth.py` do) and a real `dkr-m1-02-zeitgeist:contract` container contract test proving a genuine frame is received when authorized and a wrong credential is genuinely, fail-closed 401'd.

- **The bundled Zeitgeist client now carries TWO independent credentials — a shared relay bearer and a per-actor capability JWT — instead of one value doing double duty for both `Authorization` and `X-Zeitgeist-Capability`, so the real CLI can finally publish presence/watch a REAL SaaS-provisioned per-team relay (`FIX-M2-15`).** `FIX-M2-10`/`FIX-M2-13`'s "one credential, two headers" fix only ever worked against a relay whose `ZEITGEIST_TOKEN` happened to equal the capability JWT presented — exactly how their own test suites (and a self-hosted, single-secret deployment) set things up, but NOT how `spec-kitty-saas` provisions a real per-team relay (`apps.live_capability.provisioning_docker`'s `ZEITGEIST_TOKEN`/`ZEITGEIST_CAPABILITY_KEY` are two independently random secrets). `DQA-M2-05`'s real-container walkthrough reproduced this by hand: a capability JWT presented as `Authorization` gets a real `401`; the shared token presented as `X-Zeitgeist-Capability` gets a real `403`. `transport.ClientConfig` gains `capability_credential` (optional, `X-Zeitgeist-Capability`) alongside its existing `token` (`Authorization`); `filtered_stream.TeamStreamConfig` gains `relay_token` (optional, `Authorization`) alongside its existing `capability_credential` (`X-Zeitgeist-Capability`); `credentials.py`'s on-disk `StoredCredential` gains the identically-optional `capability_credential` field, threaded through by `subscription.resolve_stream` and `cli/commands/zeitgeist.py`'s operability probe client. **Backward compatible by construction**: whichever new field is left at its `None` default, both headers fall back to the ONE configured value — every config/checkout written before this fix, and every self-hosted single-secret deployment, keeps working unchanged. `spec-kitty-saas` gained a new member-facing credential-issuance endpoint (`apps.live_capability.views.mint_cli_credential`, `POST /api/v1/live/capability/cli/`) returning `relay_url`/`relay_token`/`capability_credential` together — the shape a real team member's CLI checkout now needs, closing the gap `mint_actor_capability_tokens_probe.py`'s ORM-bypass previously had to work around. Proven by new regression-pin unit tests against both fixed-secret local doubles (mirroring the exact `_kinded_client`/`_authed_config` shape those beads' own tests used, but now with the double's `shared_token`/`capability_key` genuinely different, never equal) AND a new real-container contract test (`tests/zeitgeist_client/test_managed_relay_docker_local.py`, own `zg-fix15-*` network/container/volume against the same `dkr-m1-02-zeitgeist:contract` image, provisioned exactly like `spec-kitty-saas`'s own driver) showing the real, unmodified `offer()`/`watch()` reach `202`/receive a real frame with two independent secrets, while the old single-credential shape genuinely, fail-closed 401s/403s against that same relay.

- **`charter activate --cascade` now follows an org-pack dependency edge no
  matter which pack in the chain declares it, and activating from an org pack
  that ships no dependency graph no longer crashes the command (`#3534`; closes
  `#3527`).** Before, cascade activation, `charter context --json`, and dossier
  rebaseline each saw only the first configured org pack — a `requires`/`suggests`
  edge into or out of any second-or-later pack was silently ignored, so
  `--cascade` under-activated whenever doctrine lived across more than one org
  pack. Now the full declaration-ordered org-pack chain is threaded through all
  three, so an edge cascades regardless of which pack authored it. As part of
  landing, activating a directive or profile from an org pack that carries
  doctrine artifacts but no root-level DRG graph now degrades that pack to "no
  DRG layer" and activates normally, instead of aborting with `DRGLoadError: No
  DRG graph files found` — each configured pack is handled on its own, so one
  graphless pack no longer takes a healthy sibling down with it.

- **Rejecting a work package no longer costs a wasted cycle: the feedback-file
  path `agent action review` prints in its rejection command is now one
  `move-task` will actually accept (`#3554`; closes `#3430`).** Before, the
  review prompt told the reviewer to write feedback to
  `tasks/<wp>/review-cycle-N.md` and then pass that same file to `move-task
  --review-feedback-file` — but inside the WP's own directory that exact
  filename is the tool-authored verdict artifact, which the provenance guard
  refuses as a feedback source. So the rejection command printed verbatim always
  failed, and the reviewer only discovered it after burning a cycle. The
  advertised path is now `tasks/<wp>/review-feedback-N.md` — still committed in
  the WP's own in-repo directory — and the name is owned in `review/cycle.py`
  beside the guard that decides what is acceptable, so the printed path and the
  accepted path cannot drift apart again.

- **The two `kitty-specs/` lane guards no longer disagree about a bulk-edit
  mission's own occurrence map, so it can be kept current from the implementing
  lane without a manual unwind (`#2980`).** The pre-commit ownership guard warned
  (and let the commit through) while `move-task` blocked the later transition,
  so `kitty-specs/<mission>/occurrence_map.yaml` — which DIRECTIVE_035 requires
  the lane to update as the sweep proceeds — tripped the gate after the work was
  committed. The exception is now expressed once (`is_occurrence_map_path` in
  `core.constants`) and honored by both guards: the map is permitted on the lane
  at both, while every other `kitty-specs/` path stays governed (a sibling
  `spec.md` on the lane is still blocked). The commit-guard `mode` semantics for
  non-exception paths are unchanged.

- **The lane "no kitty-specs on lane branches" `move-task` guard no longer
  false-positives on inherited planning artifacts in `coord` topology, so lane
  transitions stop demanding `--force` on every step (`#3271`; closes `#2274`).**
  The guard is a two-pass content delta (the shipped `#2274`/FR-007 fix), but
  both passes keyed off the lane's coordination/mission base ref, whose
  merge-base predates the `kitty-specs/**` a lane legitimately holds — prior
  missions' committed artifacts inherited from the base, plus this mission's own
  planning artifacts merged in via the recorded planning commit (ADR
  `2026-07-29-1` / `#2993`). Both are ancestors of the planning branch but not of
  the coord base, so they surfaced as lane-introduced contamination and the
  guard's own "clean the branch" remedy would have deleted other missions'
  artifacts — leaving `--force`, documented as "not recommended", as the only
  safe path. The delta is now measured against the planning branch
  (`planning_base_branch`, else the mission's `target_branch`), falling back to
  the lane base ref only for legacy/flat missions without `meta.json`. The
  sibling branch-currency and implementation-commit gates keep the coordination
  ref, which is correct for them.

- **Three architectural-gate tolls that only ever fired in CI, on legitimate
  additive change, are gone (mission `frozen-baseline-toll-reduction`; closes
  `#2853`).** For a developer working in this repo: editing the body of an
  allowlisted still-dead symbol no longer forces a hand-edited "rehashed WPxx"
  baseline — a new fail-closed helper
  (`tests/architectural/_refresh_dead_symbol_hashes.py`) refreshes the
  `body_hash` for you and is structurally incapable of admitting a _new_ dead
  symbol (it iterates the existing allowlist only and refuses on an
  unrecoverable or ambiguous `module_path`, proven by a non-fakeable
  regression). Adding a migration no longer needs a baseline bump: the
  `category_1_auto_discovered_migrations` count now derives from the frozenset
  authority in both loop arms, so the 105→107 file drift that a hard-pinned
  count would red on passes clean. And a legitimate new skip no longer
  hard-fails CI — `skip_marker_blocks` growth is now reviewable-with-teeth
  (asserted via `record_property`, with the mandatory co-located skip-reason
  line as the review signal) instead of a wall. Also drained the inert
  `test_no_dead_symbols` baseline key (closing a silent re-entry hole) and
  fast-marked the two sub-second gates for local pre-push runs. Every
  load-bearing gate is untouched — P0-security boundaries, still-shrinking
  burn-downs, zero-pins, and change-detectors all stay frozen behind the C-001
  do-not-touch fence; 108 gates green, ruff + mypy `--strict` clean. Test
  infrastructure only, no runtime or user-facing change (no version bump).

- **`finalize-tasks` no longer rejects a `planning_artifact` work package that
  owns its `kitty-specs/` deliverables, so a decision checkpoint, freeze/measurement
  snapshot, or bulk-edit occurrence map can be a first-class WP (mission
  `planning-artifact-kitty-specs-ownership`; closes `#3222` and its repro `#2643`).**
  The ownership model already blessed `kitty-specs/` ownership for
  `planning_artifact` (`ownership.validation._PLANNING_PREFIXES`,
  `validate_execution_mode_consistency`) and the lane layer already routes such
  WPs to the repo-root planning lane — only the `finalize-tasks` ban disagreed,
  rejecting any `kitty-specs/` owned file unconditionally (a later over-reach whose
  own rationale was scoped to `code_change` lane branches). The ban is now
  execution-mode-aware: it exempts a `planning_artifact` WP whose `owned_files`
  are **all** confined to the planning surfaces (`kitty-specs/`, `docs/`), and
  stays fail-closed for `code_change` and for any WP that also owns code — so a
  mislabelled planning WP cannot become a backdoor to owning `src/`. Planning-
  artifact WPs never reach a lane branch, so the lane commit-guard and move-task
  hygiene guards are unaffected.

- **A spec that writes some requirements as plain prose sentences no longer
  passes the coverage gate as if they were covered — `spec-kitty next` and
  `finalize-tasks` now block and name the uncounted ids (mission
  `bare-prose-requirements-uncounted`; closes `#3396`).** When a spec declared
  some requirements in a recognised shape (a table row, heading, bullet, or
  bold-led paragraph) and wrote others as bare sentences, the plain ones were
  silently mapped to nothing while both commands reported full coverage. Now
  `spec-kitty next` refuses to advance past the tasks boundary and
  `finalize-tasks` exits non-zero, each listing the bare-prose requirement ids;
  `map-requirements` surfaces them in its JSON (`bare_prose_requirement_ids`)
  without gating, since it registers mappings rather than advancing. The
  detector was measured against all 368 real `kitty-specs/*/spec.md` files — 1
  flagged (0.27%), zero true positives — and that figure is frozen into a
  shrink-only CI ratchet.

- **A mission whose `meta.json` recorded `target_branch: "main"` no longer
  wedges permanently at `finalize-tasks`, and the `--target-branch` escape
  hatch now actually rescues it (`#3482`; closes `#3466`).** `specify
  --topology single_branch` run from a checkout on `main` writes
  `target_branch: "main"`; finalize-tasks then resolved its WP-status
  bookkeeping destination from that literal field, tripped the protected-branch
  guard, and refused with `PROTECTED_BRANCH_REFUSED` — and passing
  `--target-branch <feature>` produced a byte-identical refusal still naming
  `main`, because the override never reached that consumer. There was no
  sanctioned way out (no retarget migration, hand-editing `meta.json` is
  prohibited). The override now persists into the canonical `target_branch`
  field before the commit pipeline, so every consumer converges on it and the
  mission finalizes; a failed persist is reported to `--json` callers instead
  of silently returning false.

- **`retrospect synthesize` now tells you the one thing that is actually
  wrong with a retrospective instead of burying it under ~100 errors about a
  schema the file was never meant to satisfy (`#3537`; closes `#3533`).** When
  a hand-edited retrospective had a single invalid finding category, the
  command printed a wall of Pydantic `extra_forbidden` / `Field required`
  errors describing the nested reader's schema — twice leading readers to
  believe the tool contradicted itself when one enum value was wrong. It now
  reports the generator reader's accurate one-line diagnosis (e.g.
  `not_helpful[0].category is invalid`) and appends the categories that field
  actually allows — findings and proposals draw from different sets — so the
  fix is obvious instead of a guess.

- **Writing an honest cardinality assertion in a test no longer costs you an
  annotation toll: the golden-count architectural gate
  (`tests/architectural/test_golden_count_ban.py`) stopped flagging
  dynamic-result `len(x) == N` checks (mission
  `test-friction-ratchet-remediation`; closes `#3458`).** Before, an ambiguous
  `len(result) == 3` over a runtime-computed collection defaulted to `convert`,
  so authors had to add `# golden-count: cardinality-is-contract` just to quiet
  the gate — on PR #3456 that toll fired twice for zero real catches. The
  classifier now treats an ambiguous dynamic-result count as `keep`, so genuine
  cardinality asserts pass untouched. The gate's real job is preserved:
  enumerable-domain golden counts like `len(Lane) == 10`, which silently drift
  when the domain grows, still convert. Companion guard added in the same slice:
  a new CT7 recurrence check (`test_ratchet_positional_anchor_ban.py`) bans
  reintroducing raw `("file.py", <int>)` 2-tuple ratchet keys in
  ratchet-substrate-importing seed containers, so the file:line-drift friction
  engine cannot regrow. Dev-facing only — no runtime or user-visible behaviour
  changes. (Also folds 12 dangling references to the retired
  `test_bridge_compat_surface.py` across 9 files — campsite cleanup of the
  already-landed #3285 deletion; refs `#2853`, `#3285`, `#2633`.)

- **A mission running under a non–software-dev workflow no longer gets blocked
  by a guard about objects its workflow does not have — for example a `plan`
  mission's `review` step demanding "Not all work packages are approved or done"
  when a `plan` mission has no work packages at all (mission
  `mission-type-guard-registry`; `#3402`, `#3386`).** Before, runtime guard
  dispatch branched explicitly on the `research` and `documentation` mission
  families and then silently fell through to the software-dev guard table for
  everything else — including `plan` and any unregistered mission type — so a
  mission could be held back by a guard about artifacts it can never possess,
  with nothing explaining why. Now guard dispatch is an explicit registry keyed
  by mission family: `plan` has its own guard table authored from its real state
  machine, and an unregistered family fails loudly on the legacy path and
  degrades to an explicit, logged neutral result on the composed extension path
  — instead of inheriting the wrong rules by accident.

- **An organisation doctrine pack you registered, validated, and activated
  delivered none of its step contracts, artifact requirements, or graph nodes to
  `spec-kitty` at runtime — it does now (`#3520`; closes `#3516`).** Before, the
  runtime consumers (the step-contract executor and its review gate bindings, the
  mission-type governance profile, runtime dispatch, and mission-load validation)
  all resolved doctrine from the built-in pack plus the project tier only — they
  had the org-tier parameter but the callers never passed it, so an org pack was
  silently inert past activation. Now a shared `resolve_org_dirs` helper threads
  the org tier through each of them; an org `expected-artifacts.yaml` overrides the
  governance artifact slot **and** the dossier completeness index (so an
  org-mandated artifact is actually enforced by the missing-artifact detector); and
  a configured-but-broken org pack warns (a dropped path or a malformed manifest)
  instead of failing silently. **A chain of multiple org packs now works too**
  (`#3525`): before, the DRG graph merged only the first org pack, so a second
  pack's step contracts loaded but their `delegates_to`/graph edges silently did
  not resolve — the runtime now merges the full declared chain in order (later
  pack wins on collision, matching the doctrine overlay), and a malformed pack in
  the chain is dropped on its own without erasing the others. Projects with no org
  pack are unaffected — every path is byte-identical without one.

- **The `SPEC_KITTY_HOME` pin census (`arch-adversarial (arch_shard_3)`) was red
  on main because a legitimate new isolation pin (`#3497`) landed after the R1a
  freeze, and the "shrink-only" ratchet — as landed — could not actually shrink
  (`#3509`, `#3121`).** The acute red is fixed by the design-sanctioned owner
  adoption (the drifting test requests the exempt `canonical_home` fixture and
  drops its own `setenv`), with no edit to any frozen artefact. Beyond that, R1b's
  tombstone burn-down is now wired end to end: `t023` subtracts the tombstoned
  set from the anchor, and the production regeneration command
  (`_home_pin_scan.render_baseline`) emits tombstones from a new auditable
  manifest (`tests/architectural/census/spec_kitty_home_pin_tombstones.yaml`) and
  freezes the key-set hash over `census ∪ tombstones`. Regeneration fails closed
  if a tombstoned member's pin is still in the tree, and the ratchet still bites
  (a spurious pin reds; a tombstone over a live pin reds). On that seam the
  provable class was converged onto the canonical owner — census `40 → 26` — with
  the ~23 genuinely-different seams documented out of scope (`#3121`'s confirmed
  thesis: a name collision, not a duplicated seam). The subsystem is a no-op while
  the manifest is empty (committed artefacts byte-identical). The same convergence
  also greens a second, separate gate — limb (g) of the §0.9 `_home_pin_gate`
  verdict oracle (`arch-adversarial (arch_shard_2)`), which recomputes the
  published end-SHA sites against the tree — by teaching it the same tombstone
  term: a converged member's site is excused only when it is in the manifest, and
  the anti-vacuity floor now counts keys that recompute _live_ so the gate can't be
  bought off by tombstoning the population away.

- **Machines that never ran the layout migration silently captured zero sync
  events while reporting success — now they capture for real (`#3425`;
  `#3497`).** Before, an un-migrated machine defaulted to a legacy capture
  layout where live event/body writes were refused deep in the stack and
  swallowed — a **silent zero-capture** that never surfaced to the operator. A
  `#3293` regression compounded this by also refusing authenticated hosts
  entirely. Now a fresh root resolves to project-only capture _before_ any
  legacy persist; a legacy-with-data root auto-migrates through the canonical
  `migrate_journal`/`project_store_migration` engines under a deterministic,
  crash-safe migration id (re-entry never bricks the root); the live emit path
  completes its cutover via a resolve-before-unit-of-work seam so both emitter
  swallow sites are observable instead of silent (never-raises contract kept
  intact); and credential parsing is restored as a pure auth signal (never a
  physical-store selector), so an already-authenticated host stops being
  refused.

- **`spec-kitty next`/`implement` no longer block on a fully-absent or legacy
  `charter.md`-only charter — both are now advisory, matching `specify`/`plan`'s
  existing tolerance (`#3498`).** The shared preflight hook
  (`run_preflight_or_abort` in `charter_runtime/preflight/hook.py`) never
  forwarded `allow_missing_charter=True` to the runner, so a brand-new project
  with no `.kittify/charter/` contents at all, or a pre-inversion project
  carrying only `.kittify/charter/charter.md` (`charter.yaml` absent, #2831's
  shape), hard-blocked `next`/`implement` even though the dashboard already
  tolerated both states. `run_charter_preflight()`
  (`charter_runtime/preflight/runner.py`) gains a new `_is_legacy_charter_bundle`
  wording selector and a distinct, more detailed warning constant for the
  legacy-bundle case. Canonical layer state alone decides the exemption:
  source and synced bundle must be `missing`, and synthesized DRG must be
  `missing` or `built_in_only`; display-only `charter.md` only selects warning
  copy after that decision. Stale, invalid, or other partial residue therefore
  keeps blocking even when `charter.md` exists. Advancing/query and human/JSON
  `next` modes plus `implement` emit the advisory to stderr without polluting
  JSON stdout; dashboard persists/renders it. The canonical `CHARTER_MD` import
  stays lazy so `next` does not pull the heavyweight charter graph at startup.
  The legacy warning
  names the executable migration command explicitly:
  `spec-kitty charter generate --no-from-interview`.

- **A reviewer running a different agent profile than the implementer can now
  claim a completed work package for review — the false "WP already claimed for
  review by `<implementer>`" refusal is gone (`#3455`).** Before, claiming a WP
  for review (`for_review → in_review`) compared the claim holder's identity,
  which at `for_review` is structurally the _implementer_ — so any cross-profile
  reviewer (e.g. `reviewer-renata` reviewing `python-pedro`'s work) was rejected
  as a self-review collision, and the block surfaced on the status aggregate
  seam rather than the `move-task` command. Now the `for_review → in_review` edge
  is allow-only, and a genuine reviewer-vs-reviewer collision is decided by a
  single pure predicate at the `in_review` re-claim site (a real second reviewer
  is still blocked, and the message names the holder). Role is read from the
  reduced status slot, never by splitting the compact actor string (`#2861`).

- **Coord/primary partition-authority residuals: out-of-loop callers now resolve
  the correct partition surface, so coordination-topology missions stop deadlocking
  and mis-reporting (mission `partition-authority-residuals-01M021K9`; epics `#2160`
  / `#2720`).** Under coordination topology a cluster of out-of-loop and
  cross-function callers still read PRIMARY-partition artifacts off the `-coord`
  husk, or wrote lifecycle evidence to the wrong partition — degrading silently or
  **deadlocking `spec-kitty merge`**. Eleven fixes, each a caller reroute through
  the canonical `mission_runtime.artifacts` placement seam (STATUS reads stay on
  COORD): the coord **merge deadlock** is gone — the review-override write now lands
  on the surface the merge gate reads, and `spec-kitty merge` gains a
  `--skip-review-artifact-check`/`--note` escape hatch that records the bypass as
  durable override evidence (`#2959`); merge risk/dependency gates and the bulk-edit
  diff base stop silently SKIPping / seeing an empty graph on coord missions
  (`#3439`); the review handoff renders true per-WP lanes instead of a blanket stale
  `planned` (`#2698`); `move-task` commits its post-transition annotation atomically,
  leaving a clean status tree (`#2939`); the 4th safe-commit target resolves through
  the shared degrade helper with refusal-parity preserved (`#2966`); and
  `finalize-tasks` versions `wps.yaml` so a finalized checkpoint reproduces its own
  state (`#2937`). Diagnostic-output fidelity (`#2720`): `check-prerequisites`
  sources its inventory from canonical mission writer metadata (`#2692`); mission
  doctors validate `meta.json` against the writer schema — killing false
  `UNKNOWN_SHAPE` findings — and `doctor coordination` gains `--mission` scoping
  (`#2696`); `retrospect summary` discovers missions under the canonical
  `kitty-specs/*` root (`#2717`); `status doctor` no longer reports Healthy over
  blanked runtime attribution (`#2960`); and mission-state repair stops quarantining
  legacy `WPStatusChanged` lane transitions into a zero-WP `status.json` (`#3066`).

- **Review rejections now reach the hosted dashboard instead of being silently
  dropped by sync (`#3307` P0; `#3444`).** Before, when a reviewer sent a work
  package back for rework — any backward review-rejection move (`* → planned`,
  or `in_review → in_progress`) — the CLI stamped the status event `force=False`
  and, for `in_review → in_progress`, left off the `review_ref`. Those events
  were accepted on your machine but violated the shared `spec-kitty-events` wire
  contract the hosted ingestion endpoint enforces, so hosted sync silently
  rejected them: a rejection that looked applied locally never propagated to the
  team dashboard (in the reported case a whole batch surfaced 11+ days later as
  bulk sync failures). Root cause was two same-named `validate_transition`
  functions giving opposite answers — the emit path consulted only the
  CLI-local state machine, never the wire contract the server enforces. The
  emit-force decision now gates on **both**, so the review-rejection family
  emits `force=True` (still carrying the structured rewind rationale) and threads
  the `review_ref` on the wire, producing events the project's own vendored
  contract accepts. Reviewers are now told — at the `move-task` tool surface and
  in the review skills — that a rejection rationale (`--review-feedback-file` or
  `--note`) is mandatory, because it travels on the wire as that `review_ref`.

- **Coordination-topology missions no longer wedge lane allocation by
  committing PRIMARY planning artifacts onto the coordination branch (mission
  `write-path-integrity-01KZZD69`; `#3371` P0, `#2549`, `#3128`, `#3373`;
  advances `#2160`/`#1878`).** Before, `implement`'s planning auto-commit routed
  the whole batch verbatim to the coordination branch under coord topology, so a
  PRIMARY `lanes.json` landed on coord and the lane allocator's recorded-planning
  merge hit an add/add conflict — blocking every work-package claim on a
  PR-bound `--start-branch` + coord mission with no self-service recovery. Root
  cause was one layer deeper than the commit site: `BookkeepingTransaction.acquire`
  _unconditionally_ redirected writes to the coordination worktree, so this fix
  adds an opt-in `commit_to_primary_target` that PRIMARY planning commits use to
  land on the mission's own target branch (every status/coord caller keeps the
  default — zero regression to coord routing). A partition guard at the
  planning-commit seam now fails loud on any PRIMARY→coord / COORD→lane
  mis-route (excluding self-bookkeeping `meta.json` co-travel), closing the same
  class for `move-task --force` (`#2549`). `implement`'s lane-state **read** now
  resolves `lanes.json` from that same PRIMARY partition (via the kind-aware
  placement seam, matching its canonical `LANE_STATE` classification), so the
  read and write agree for coord-topology missions — previously the read still
  looked on the coordination surface, which broke `implement` end-to-end.
  Separately, mission-mutating
  `implement`/`review` now **fail closed** when invoked from a checkout the
  mission does not own (`#3128`): a `write_intent`-gated `CheckoutIdentityError`
  at the real workspace chokepoint (`workspace/context.py::resolve_workspace_for_wp`)
  refuses foreign-checkout writes without ever refusing reads or planning. The
  four re-implementations of the git-common-dir/toplevel probe are unified behind
  one primitive (`#3373`), and a static `tests/architectural/` gate plus a
  cross-partition repo scan keep the P0 class from silently regressing. The
  frontmatter/upgrade-wedge slice (`#3372`) and `#2702` were confirmed already
  closed (by mission `#3383` and prior work) and left out of scope.

- **Activating a charter directive no longer silently drops every org-pack
  artifact from the doctrine graph (mission `org-activation-scan-dirs-01KZY1PT`;
  `#3399`, closes `#3385`).** Before, the charter activation allow-list scanned
  org packs at a phantom `<root>/<plural>/built-in` layout that no org pack
  actually uses, while the live doctrine loader reads the flat `<root>/<plural>`
  layout. The two disagreed silently: the moment an operator ran
  `charter activate directive <stem>`, every org-pack URN failed to resolve and
  was dropped from the filtered graph with no error — so a project's own
  directives, tactics, and profiles vanished from governance the first time
  anyone activated a single artifact. Now the activation scan reads the same
  flat layout the loader does (plus the legacy nested layout additively, with
  the flat entry winning a same-name collision), so activating one artifact
  leaves the rest of the org pack intact.

- **The `researcher-robbie` agent profile no longer introduces itself under the
  wrong name (`#3377`).** Before, the profile's `purpose` and
  initialization-declaration prose still read "Researcher Rosa" — a leftover the
  profile rename missed — so any agent that loaded `researcher-robbie` and
  followed its initialization declaration announced itself as "Researcher Rosa",
  even though the profile's own `name` field, its docs page, and every sibling
  profile said "Researcher Robbie". Now the prose matches the profile's own
  `name`, and a parametrized test asserts every shipped profile's self-identity
  prose equals its `name` field, so this class of identity drift cannot silently
  recur.

- **`sync import-history` now imports legacy work packages that carry retired
  frontmatter fields, instead of skipping them (mission
  `first-sync-preflight-01KZZ9Q1` FR-011; `#3406`).** The import scan read WP
  frontmatter with the strict authoring model (`extra="forbid"`), so a
  historical WP carrying a field the current schema no longer knows (e.g.
  `estimated_lines`) raised a validation error, was logged "unreadable", and was
  degraded to a bare back-fill — losing its real title and dependencies. The
  import path now uses a lenient reader that drops unrecognised legacy keys
  while still validating known fields, so genuinely-malformed frontmatter is
  still skipped fail-loud. Authoring keeps the strict typo guard unchanged.

- **`sync status` now flags an unreachable sync server and how to repoint it,
  instead of reporting a bare "Unexpected status" (mission
  `first-sync-preflight-01KZZ9Q1` FR-003; `#3406`).** A configured server that
  answers with a gateway-class status (`502`/`503`/`504`) — the signature of a
  decommissioned platform env or a torn-down preview, which is exactly how a
  first sync against a stale `*.platformsh.site` URL stranded — was folded into
  the generic "Unexpected HTTP 502" branch, giving the operator no signal that
  the URL itself might be the fault. The health probe now reports these as
  **Server unavailable**, reassuring that queued events are retained and will
  drain on recovery (consistent with the offline queue's transient-retry
  handling), and — for the decommissioned case — naming the URL and the exact
  recovery (`spec-kitty sync server <url>` then `auth login --force`).

- **`auth login` now resolves the server the same way `sync` does — env over
  `[sync].server_url` over the documented default — instead of the env-only
  accessor that errored when only `spec-kitty sync server` had been set
  (`#3406`, FR-005).** Before, a user who set their server via `sync server`
  still hit "SPEC_KITTY_SAAS_URL environment variable is not set" on login, so a
  token could only be minted against one server while sync targeted another. It
  still refuses (with a remedy naming both `SPEC_KITTY_SAAS_URL` and
  `sync server`) when neither is set, rather than silently defaulting to the dev
  URL. One of the ten-gate first-sync gauntlet fixes.

- **`sync doctor` no longer reports "Sync is healthy" while the server probe
  says otherwise (mission `first-sync-preflight-01KZZ9Q1` FR-002; `#3406`).**
  The health summary only escalated a server verdict of `Unreachable`/`Error`;
  a `Permission denied` (403), gateway-down (5xx), or unexpected-status verdict
  printed a coloured row in the table but never entered the issue list, so the
  doctor still declared everything healthy while the live drain was blocked —
  the false-green that hid a broken first sync. Every non-healthy server verdict
  (anything but `Connected`/`Disabled`, excluding the auth states the
  auth/session block already owns) now reaches the summary with the probe's own
  remediation note.

- **Mission `create` and `next` now run correctly from a caller-owned linked
  git worktree, and each worktree's mission state stays isolated (mission
  `worktree-owned-root-3328-01KZRG01`; `#3346`, closes `#3328`).** Before,
  invoking `create` or `next` from an explicit linked checkout followed the
  worktree's `.git` pointer back to the primary checkout and tried to drive the
  mission there — failing with `START_BRANCH_FAILED` when that branch was
  already checked out, and risking one worktree reading or writing another
  worktree's mission state. Now the invoking checkout root is validated with
  fail-closed git-topology ownership checks and threaded through creation,
  resolution, `next`, runtime state, refs, and commits, so two linked worktrees
  can create and advance distinct missions concurrently with no
  cross-contamination while the primary checkout is left untouched. Managed
  Spec Kitty coordination and lane worktrees remain refused.

- **The ADR inventory freshener now targets the canonical `3.x` era index
  instead of the redirect README, so newly added ADRs are actually indexed
  (`#3346`, closes `#3345`).** Before, the freshener pointed at the redirect
  README and left the canonical era index stale, so a new ADR could pass docs
  freshness without appearing in the index maintainers browse. Now it writes the
  canonical era index directly.

- **Direct sync ingress no longer drifts to a shared/primary team when the
  session read transiently returns None (`#738`/spec-kitty-saas `#911`).** The
  fan-out handler resolved the producer scope as
  `read_queue_scope_from_session() or read_queue_scope_from_credentials()`. The
  session path is fail-closed to the user's Private Teamspace, but the credentials
  fallback returns whatever `team_slug` the credentials TOML last stored (often a
  shared/primary team, e.g. `stijn` rather than `stijn-private`). During a token
  refresh or a rehydrate miss the session read returns None and ingress silently
  rerouted to that team — forking the producer-scoped journal (`journal-<scope>.db`)
  and materializing the project under the wrong team server-side, so the
  private→shared share could never find it (the Kitty Prime "I can't see the
  team's work" symptom). Ingress is now session-only: it honours the fail-closed
  contract and skips queueing when the Private Teamspace can't be resolved, rather
  than attributing the event to the wrong scope. The credentials reader stays for
  the diagnostic call sites (e.g. `sync doctor`/preflight, which compare the two
  scopes to _detect_ exactly this drift).

- **Root README guide links point at the post-IA `tutorials/` and `how-to/`
  paths.** Fixes GitHub 404s from stale flat `docs/guides/*.md` hrefs after the
  guides subdivision (e.g. Your First Mission).

- **Four operator-visible read/write-consistency defects, where a step trusted a
  partial, pre-merge, or recomputed-from-scratch view of persisted state, are
  fixed (mission `mission-a-p0-consistency`; `#3320`, `#3231`, `#3334`, `#3311`).**
  Concretely: `retrospect create --update` reported and emitted the _pre-merge_
  record — the counts, JSON `findings_status`, and `RetrospectiveCaptured` event
  disagreed with what was written to disk; now they read the persisted record back
  (`#3320`). A leftover `finalize-tasks` scaffold placeholder blocked acceptance
  for a mission whose real criteria all passed; the verdict now exempts _only_ the
  empty placeholder row, so a real still-pending criterion still blocks as before
  (`#3231`). A failed `spec-kitty upgrade` stripped `schema_version` from
  `meta.json` and wedged the project as unrecoverable `LEGACY`; project metadata
  now round-trips the stamp so a failed migration stays recoverable (`#3334`).
  Re-running `finalize-tasks` after implementation had begun clobbered the recorded
  `planning_commit_sha`; it now preserves provenance once any work package has left
  `planned` (`#3311`).

- **Six upgrade-wedge failures, where a stuck migration left no self-service way
  out, are fixed (`#3383`; `#3335`, `#3336`, `#3337`, `#3338`, `#3339`,
  `#3372`).** Concretely: a failed `runtime_state_backfill` aborted mid-walk with
  no record of what it had already written, leaving the operator unable to tell
  how far the migration got; it now enumerates every mission and file already
  persisted before it stopped (`#3335`). `spec-kitty upgrade --dry-run` (and
  `--json`) could report nothing pending while the real run went on to apply many
  migrations, because the preview computed pending work through a different path
  than the real run; the preview now drives off the same migration selector, so it
  reports the true pending set (`#3336`). `agent mission create --json` returned a
  bare `CHARTER_PACK_CONFIG_INVALID` error code with no fix steps, discarding the
  human-readable remediation text a plain-text run would have shown; the `--json`
  envelope now carries the remediation body alongside the code (`#3337`). The
  `migrate backfill-runtime-state ... --dry-run` diagnostic a failed migration
  told operators to run was itself blocked behind that same failed migration — a
  catch-22 with no way out; the `--dry-run` form is now ungated (the mutating form
  stays blocked) (`#3338`). A failed `mission create` left the operator's checkout
  switched onto the coordination branch it had just minted, and left that orphan
  branch behind; it now restores the original checkout and deletes the branch it
  created (`#3339`). The review cycle could append a duplicate `review_feedback`
  frontmatter key, producing invalid YAML that later wedged upgrades trying to
  parse it; the writer that appended on a miss is retired (it now fails closed),
  duplicate-key artifacts are detected and can be repaired non-destructively, and
  the frontmatter reader names every offending key (`#3372`).

- **Coding agents — especially smaller models — no longer stall mid-implementation to demand human approval and build "prove every step was signed off" scaffolding; and the review/accept gates now capture real, bound evidence instead of unattributed notes.** (mission `governance-at-the-gate`; #3685, #3682) **Before:** the decision-documentation directive (`DIRECTIVE_003`, `required`) was delivered into the `implement` action bundle — directly, and transitively via an implement-scoped procedure whose `references` link the resolver promoted to an unconditional `requires` — so a literal reader composing the `required` directives landed on "author a durable decision artifact, alternatives, rationale, traceable" _during implementation_ and stopped to ask a human. Compounding it, the doctrine-delivery resolver was enforcement-flat and tension-blind: the `Enforcement` levels had no ordering, and the tension arbiter (`reconcile-change-scope-tensions`, itself the weakest `advisory`) never reached the agent _as_ an arbiter — so a weak model had no signal that a brake outranked a do-more rule. Separately, at the deciding gates the evidence was thin — an `in_review → approved` transition recorded an unattributed prose note (no `policy_metadata`, no `review_ref`), a first-pass approval wrote no `review-cycle` artifact at all, and `spec-kitty accept` left `acceptance-matrix.json` an unfilled `pending` scaffold. **After:** decision-documentation is delivered at the deciding gate (`review`) and removed from `implement`, with a class-level gate that fails if any `required` decision-documentation directive is ever scoped back onto implement (directly or transitively); the `Enforcement` levels carry an explicit rank and a structural gate forbids a `reconciles_tension` arbiter ranked below what it arbitrates (the arbiter is promoted to match its operands and is now delivered _as_ an arbiter, with co-delivered tensions annotated on the bundle); and the approve/accept gates capture real evidence — the approval event carries the reviewer's `policy_metadata` (tool/profile/model/shell-pid) and a `review_ref`, a first-pass approval auto-authors an `approved` `review-cycle` carrying a reproduction command, and `accept` populates `acceptance-matrix.json` criterion rows from the recorded review evidence (only from a genuine `approved` verdict — a stale rejection can never fabricate a pass). Follow-up #3805 tracks the durable resolver fix for the soft-`references`-as-`requires` modeling that made the transitive leak possible.

- **`spec-kitty next` no longer re-parses the whole charter on every invocation, and a slow shared runner can no longer red-block an unrelated PR on `next` latency.** (mission `next-latency-durable-fix`; #3787, #3595; relates #2749, #3783) **Before:** two problems compounded. (1) On any charter-bearing project, every `spec-kitty next` (the command the mission loop runs constantly) re-ran the charter freshness preflight from scratch — a full ruamel parse of the ~1600-line `charter.yaml` — costing ~0.5s per call. (2) The check meant to guard `next` latency was a single-shot absolute wall-clock ceiling (`scripts/check_nfr_003_latency.py`) still running on the **PR-blocking** `clean-install-verification` path; it false-redded on shared-runner variance and had been ratcheted up four times (1.00 → 1.05 → 1.60 → 2.20s), most recently during the #3783 landing. **After:** (1) `next` serves the charter freshness verdict from a per-repo content-hash cache — keyed on the charter bundle **plus** the synthesized-DRG graph and synthesis-manifest files, content-only (never mtime) and fail-closed, so it never serves a stale "fresh" governance verdict — skipping the parse on a hit. (2) The blocking wall-clock ceiling is retired: the `next` cold-start signal now runs statistically and off the PR path in `performance.yml` (the pipeline from ADR `2026-08-22-1`), and `clean-install-verification` keeps only the structural clean-wheel smoke check (that `next` runs at all). A `next`-path import-hygiene trim (deferring an import the no-op/startup path doesn't use) rides along; the deeper real-query import-floor reduction is tracked separately in #3789.

- **`spec-kitty accept` now tells you the honest way out of a path-convention mismatch instead of steering you into a fake green.** (#3730, #3085) **Before:** when a mission's layout did not match the active path convention, `accept` failed with _"These directories are required by the active mission. Create them before continuing."_ — which pushed operators to `mkdir` empty directories just to pass the gate (a fake green), and never mentioned the real escape hatch. Separately, a token declared under both `artifacts.optional` and `paths.deliverables` (e.g. `contracts/`) was reported **twice** — once as an optional warning and once as a blocking error — so the same missing path showed up at two severities. **After:** the failure surfaces the real option — _"Run `accept --lenient` to treat these as warnings instead of blocking errors for this mission run"_ — and keeps the `mkdir` suggestions only as an explicit opt-in "adopt the convention" path, not the prescribed remedy (`--lenient`'s help text now says it also downgrades missing path-convention checks). The double-report is deduped structurally (the blocking severity wins) via an artifact-token membership check rather than fragile string matching, and remediation now names the **resolved**, tested location rather than the bare declared token. Out of scope by design: the `src/`-hardcoded non-`src` repo portability (#3016) is unchanged.

- **`spec-kitty` no longer crashes on startup after installing typer 0.27.2 — every CLI command works again.** (#3782) **Before:** typer 0.27.2 (published 2026-08-28) removed `Abort` and `Exit` from its vendored `typer._click.exceptions` module. The orchestrator-API command layer resolved those exception classes with `getattr(_CLICK, name, _CLICK.exceptions.<name>)`, whose fallback argument is evaluated eagerly — so on the new typer it raised `AttributeError: module 'typer._click.exceptions' has no attribute 'Abort'` at import time, and since that module loads on every invocation, _every_ `spec-kitty` subprocess died with a traceback instead of running (`create`, `setup-plan`, `check-prerequisites`, `research`, …). **After:** a single `_resolve_click_exc()` helper resolves each click/typer exception class defensively across the vendored module, its `exceptions` submodule, the `typer` top level, and the standalone `click` package, so a symbol relocation in a future typer release degrades gracefully to click-only instead of breaking the CLI. Pinned by focused unit tests plus the existing `_JSONErrorGroup` typer-surface smoke test.

- **Auth and sync diagnostics no longer report success while the session is broken — every status line is now derived from evidence, and a probe that cannot verify says `unknown`, never `ok`.** (#3723) **Before:** `sync status` and `auth status` printed a green `Authenticated` banner directly above a contradicting `Access token: expired` detail, and `auth doctor` printed `No problems detected.` for an expired token whose refresh chain was failing — each surface _hand-rolled_ its own green claim alongside, never derived from, the detail it displayed, so there was no way to get from "broken" to a true statement about why without reading the source. **After:** a single typed authority `specify_cli.auth.verdict` (`HealthVerdict` — a tri-state `ok`/`unknown`/`fail` whose `headline` is a computed property derived from `state`, never a settable field, with mandatory evidence for every definite claim) owns the decision, and all three surfaces render `verdict.headline` + `verdict.evidence` instead of a bare word. An expired access token whose refresh chain cannot be proven offline now resolves to `unknown` ("Cannot verify"), never a false green; `auth doctor` prints "No problems detected." **only** when the verdict is a confirmed `ok` (an `unknown`/`fail` always raises a named finding), and its `--server` probe feeds the verdict so it can resolve `ok`/`fail`. A new AST architectural ratchet (`tests/architectural/test_status_line_honesty.py`) enforces the three honesty rules structurally: each surface must genuinely route through the authority, `HealthVerdict` must keep its 3-member Literal and property-derived headline, and no surface may hand-roll an authenticated-claim literal outside the one allowlisted verdict-gated render site.

- **A deliberately-canceled work package is now an honest mission ending, and the planner warns before authoring work that can never terminate** (mission `mission-completion-terminal-state-01M129MV`; #2945 #3590). **Before:** `spec-kitty accept` refused a work package that was canceled during a documented replan — even though `canceled` is a terminal lane — so a legitimate cancellation left the mission permanently non-terminal, forcing an operator to resurrect and falsely approve removed work; and `tasks` could author an "action" work package whose completion is only observable after integration, with no honest terminal state. Worse, the acceptance path kept its own accept-ready set (four parallel `{approved,done}`/canceled decisions across `acceptance/`, `dependency_graph.py`, and `policy/merge_gates.py`), and `move-task` auto-synthesized a non-empty cancellation `reason`, so "canceled with a reason" could not distinguish a documented replan from a bare `--force`. **After:** cancellation provenance is a first-class, operator-authored `reason_source` field on the status event (captured at emit, projected into the reduced snapshot), and a single `is_acceptable_ending(lane, *, has_provenance)` authority — consumed by `accept`, `merge`, both CLI claim gates (`implement.py` and the agent-action executor), and the dependency-readiness gate — admits a `canceled` work package **only** when it carries operator provenance. `accept` reports such work packages under a dedicated `canceled_wps` field, refuses a synthetic (undocumented) cancellation with a structured blocker, and still runs the acceptance-matrix and issue-matrix gates (canceled-terminal never short-circuits them). `merge` excludes canceled work packages from its per-work-package done/review assertions at both derivations (never driving `canceled → done`) and skips a lane's branch only when every work package in it is canceled. A canceled-with-provenance dependency no longer strands its dependent at claim or merge time. `tasks` gains an advisory `check-terminability` warning (never blocks) that flags a work package whose acceptance criteria can only be met after integration, so operators re-home that content at planning time. Backward-compatible: missions with no canceled work packages accept and merge identically, and legacy events with no `reason_source` are honored. The completion-contract redesign remains deferred to #3550.

- **The background sync daemon now resolves a `specify_cli`-capable interpreter before it spawns, instead of trusting a bare `sys.executable` that may die with `ModuleNotFoundError`.** (#3624) **Before:** `_spawn_sync_daemon_process` launched the daemon with `subprocess.Popen([sys.executable, "-c", …])`. On a host where the interpreter that launched the spawner cannot import `specify_cli` — a macOS framework-Python re-exec, a pyenv shim, or a Homebrew `python3` first on `PATH` — the auto-spawned child died immediately with `ModuleNotFoundError: No module named 'specify_cli'`, leaving only an opaque `<string>` line-3 traceback in `~/.spec-kitty/sync-daemon.log`. The failure was intermittent: a daemon started via the correctly-shimmed `spec-kitty` (or `spec-kitty doctor restart-daemon`) ran the right interpreter, so it depended on who spawned it. **After:** the spawn first probes the candidate interpreter (`python -c "import specify_cli"`); if it is incapable, it self-heals by prepending the running package's path to the child's `PYTHONPATH` and re-probes; if it is still incapable, it raises a loud, actionable `DaemonSpawnError` (telling the operator to restart via `spec-kitty` or `spec-kitty doctor restart-daemon`) rather than spawning a doomed child that scribbles into the log. The reaper's exec-identity argv marker is built from the resolved interpreter so cross-scope attribution stays accurate under self-heal.

- **`spec-kitty auth status` now shows each team's slug and `spec-kitty sync share` accepts a team name, closing the gap where the CLI could never tell a user the slug that `sync share` requires.** (#3731) **Before:** `auth status` printed team _names_ only, while `sync share` took a required _slug_ the CLI never displayed anywhere — a user had no way to learn their own team slug from the tool. **After:** the server-published `slug` (saas#986) is surfaced end-to-end. `Team` carries a `slug` field populated at both `/api/v1/me` ingress points (`Team.from_dict` and `parse_me_teams`), each falling back to the team `id` (the long-standing compatibility alias) for legacy sessions stored before the field existed. `auth status` prints `slug: <slug>` beside every team and marks the Private Teamspace _not shareable_ (the server refuses it as a destination). `sync share` now accepts either the slug or the display name and resolves it through the new fail-closed `resolve_team_slug` helper — an unknown or ambiguous handle, or one targeting the Private Teamspace, prints the shareable teams and exits 1 without calling the server, rather than silently picking the wrong team. New logic lives in the `auth.session` authority (`shareable_teams`, `resolve_team_slug`, `TeamSlugResolutionError`), not the command layer.

- **`spec-kitty sync share <team>` no longer fails first-run with an unhandled traceback while it self-heals; the recoverable race now reports an actionable line and teardown is deterministic.** (#3699) On a checkout that is opted in but whose project the server has not yet seen, the `share` command's 404 handler already materializes the project in Private Teamspace and retries — but the retry in `cli/commands/sync.py` sat **outside any `try`**, so the second, transient 404 (the newly emitted `BuildRegistered` is not yet visible server-side) propagated as a raw `RepositorySharingClientError` stack trace, trailed by a `Task was destroyed but it is pending!` warning from the WebSocket disconnect being skipped on the aborted path. **Before:** first-run `sync share` exited 1 with a Python traceback; the documented workaround was to run `sync now` and repeat the identical command. **After:** the retry is wrapped in its own `except RepositorySharingClientError` that prints `Registering this project in Private Teamspace. Run spec-kitty sync share <team> again in a moment.` and exits `1` cleanly (no traceback), and a `finally` drives `SyncRuntime.stop()` (idempotent; awaits the disconnect synchronously) on every exit path so orderly teardown runs on the error path too, removing the pending-task warning. The 404→materialize→retry policy is still inline in the command module; pushing it down into a typed `ShareOutcome` on `sync/sync_authority.py` is a deferred follow-up (the three interleaved command-layer render/exit paths make a clean extraction larger than the fix).

- **A custom mission family that ships its own `expected-artifacts.yaml` now genuinely blocks on unmet `blocking: true` requirements, instead of always silently passing.** (#3704) **Before:** `spec-kitty next`'s guard evaluation for a mission family outside the four built-in types (`research`/`documentation`/`software-dev`/`plan`) always returned `guard_failures == []` regardless of what artifacts existed on disk — a data-driven presence gate existed (`expected-artifacts.yaml`'s `path_pattern`s), but nothing consumed the resulting presence set into a real `guard_failures` list for a family outside the built-in guard-table dispatch, so a custom mission could advance silently past a step whose declared, `blocking: true` artifact was never produced. **After:** the same evaluation layer used by the built-ins now genuinely checks a custom family's declared manifest — present artifacts pass, a missing `blocking: true` artifact blocks with a real failure message and a `blocked` `Decision.kind`, at any of the three call sites (CLI pre-check, WP-iteration pre-check, composed-action guard) and at both the built-in and org-tier (`<org_root>/missions/<type>/expected-artifacts.yaml`) manifest locations. The four built-in families are unaffected — their `guard_failures` output is byte-identical before and after. An unregistered family with **no** manifest declared anywhere still runs to completion exactly as before (`UnregisteredMissionFamilyError` for strict dispatch, tolerant callers still degrade to `[]`). **Operator-visible behavior change:** an in-flight custom mission previously advancing silently past a step with an unmet `blocking: true` requirement may, on its next evaluation, correctly BLOCK where it previously would not — this is the intended fix. In-flight missions are not retroactively re-evaluated: past `status.events.jsonl` entries and `Decision`s are never rewritten; only the mission's next evaluation after deploy uses the corrected logic.

- **`spec-kitty charter activate mission-type <T>` now refuses a mission type that resolves an empty action sequence, instead of reporting success and leaving the project unable to plan anything.** (#3717; closes #3702) **Before:** the _first_ activation of such a type exited `0` with `Activated: <T>` and wrote it into `mission_type_activations`, so an operator who followed the documented order — declare the org pack, then activate — got a success message and a bricked project; every later governed entry point then failed, including `charter activate` itself on a second run (`exit 1: mission type ... has an empty action sequence`). The right validation already existed but only ran on the _read_ path (#3386), never on activation — the one operation whose whole job is deciding whether a type is usable. **After:** a fail-closed preflight at the CLI seam runs that same resolution _before_ any write, so the first run refuses with the same message the read path produces and **nothing is written**. The single-level `extends` fallback is honored (a type whose own sequence is empty but whose parent resolves a non-empty one still activates); the read-path `is_registered` short-circuit is unchanged.

- **A single project-local `charter.yaml` `directives:` entry is now additive instead of silently replacing the entire resolved directive set.** (#3728; mission `directives-additive-resolution`) **Before:** on a project that resolved its directives via the built-in catalog, adding even one directive under `charter.yaml`'s `directives:` section wiped the whole resolved set — `charter context --action plan --json` dropped from the catalog's full directive count to just the one local entry, with exit 0, nothing on stderr, and `charter status` still reporting FRESH/VALID. **After:** a project-local directive is unioned onto the base set the project already resolves (catalog default, charter activation, or an explicit `governance.doctrine.selected_directives` selection), so `N` base directives plus `K` **new** local ones resolve to `N+K` (a local id already in the base is de-duplicated, never a loss), with zero baseline lost.

- **Three release-blocking P0 workflow defects fixed as one mission (`p0-reliability-triad`; #3282, #3579, #3281).** Each left a project broken-but-"healthy"-reporting during a core workflow. **#3282 — upgrade:** `spec-kitty upgrade` wrote `mission_type_activations` into `.kittify/config.yaml` unconditionally, but a pointer-based charter project reads them from the pointed-at `charter.yaml`, so the seeded key was never read and mission creation kept failing closed after a "successful" upgrade; the provisioner now routes through the pointer-aware `charter.compiler.provision_mission_type_activations` writer (legacy projects still write `config.yaml`), and the dry-run pending predicate keys on key-presence in the resolved write target (preserving authored-empty-`[]` parity, non-crashing on a dangling pointer). No new migration. **#3579 — merge:** a stale-lane halt routed the operator to a raw `git` merge that conflicts on the derived `status.json`, naming neither of the tool's own remedies; `_stale_remediation` now names `spec-kitty agent status materialize` (rebuild from the event log) — no `status.json` merge driver is introduced (it stays intentionally driver-exempt). **#3281 — implement:** a retry after a recorded-planning-commit merge conflict skipped dependency propagation because `ensure_workspace_materialized` short-circuited on `workspace.exists`; the retry now re-enters an idempotent self-heal, fresh-path allocation is atomic (no orphaned worktree on conflict), and a **post-materialize** ancestry gate — enforced on both the CLI and `orchestrator_api` claim paths — refuses claiming a WP against a lane missing its dependencies **without** deadlocking a legitimately-approved same-mission dependency.

- **`specify_cli.dossier` no longer re-exports seven `spec_kitty_events` types — one canonical import path per type instead of two.** (#3677) `ArtifactIdentity`, `ContentHashRef`, `LocalNamespaceTuple`, and the four `MissionDossier*Payload` types (`MissionDossierArtifactIndexedPayload`, `MissionDossierArtifactMissingPayload`, `MissionDossierSnapshotComputedPayload`, `MissionDossierParityDriftDetectedPayload`) were re-exported from both `spec_kitty_events` (their canonical home) and `specify_cli.dossier`, violating the charter's single-canonical-authority principle for this surface; no `src/`/`tests/` caller used the second path. **After:** the seven names are removed from `dossier/__init__.py`'s `from .events import (...)` statement and `__all__`; the four `emit_*` function re-exports (`emit_artifact_indexed`, `emit_artifact_missing`, `emit_snapshot_computed`, `emit_parity_drift_detected`) are untouched, and `events.py` itself has zero diff. A regression test (`tests/dossier/test_reexport_trim.py`) pins both halves: the seven names are unreachable via `specify_cli.dossier`, and the four `emit_*` names remain reachable. **User-visible API change:** `from specify_cli.dossier import ArtifactIdentity` (and the other six) now raises `ImportError`; import these types directly from `spec_kitty_events` instead.

- **Concurrent review-verdict saves can no longer race each other into a silently-lost or silently-uncommitted commit — the actual `git add`/`git commit` for a review-cycle artifact now runs behind a checkout-wide serialization queue instead of unprotected.** (mission `durable-concurrent-review-cycle-records-01M0QRX7`; closes #3235) `_commit_review_cycle_artifact`'s git invocation lived deliberately outside `feature_status_lock` (per NFR-006), with no protection against two OS processes racing `git add`/`git commit` in the same working tree — `tests/integration/test_review_durability_matrix.py::test_sc004_two_concurrent_processes_never_clobber_a_verdict_over_50_iterations` reproduced the race under genuine multi-process concurrency, observing a `safe_commit` staging-area refusal or a reported-but-missing artifact. **After:** a new checkout-wide `FileLock`-backed queue (`src/specify_cli/review/verdict_commit_queue.py`, keyed on `git_common_dir()` so linked worktrees and missions converge on one lock while independent clones stay independent) wraps the whole allocate→write→commit→verify sequence; a save that can't complete within its bounded window fails the command explicitly (`verdict_durably_persisted: false`, a truthful busy result) rather than reporting success while the verdict silently disappears. `feature_status_lock` for event/status mutation remains a separate, narrower lock (distinct lock file, distinct re-entrancy, distinct timeout error): the two are only ever acquired queue-outer→status-inner and never in the reverse order, so there is no lock-ordering deadlock. The **whole** save is time-bounded, not just queue acquisition — while the queue is held the in-critical-section `feature_status_lock` wait is bounded too (a wedged holder can no longer hang every verdict save in the checkout); off the queue (the `--no-auto-commit` / local-only feedback paths) the historical unbounded wait is retained. Retained evidence and identical-adoption handling were hardened alongside so a commit-infra exception no longer unlinks a recoverable artifact, and a revert-compensator failure surfaces the same structured durability envelope instead of a bare error (mission `durable-concurrent-review-cycle-records-01M0QRX7`; #3773).

- **`spec-kitty agent mission setup-plan` no longer refuses to run when a host is unauthenticated, and its auth check now reads the real session state instead of a queue-scope proxy.** (#3621) Two defects, both fixed. **Before:** with `SPEC_KITTY_ENABLE_SAAS_SYNC=1`, setup-plan (a) decided the host was unauthenticated by checking `read_queue_scope_from_session()`/`read_queue_scope_from_credentials()` — a queue-scope file read, not an auth check — so a genuinely logged-in host with a valid refresh token but no materialized `queue_scope` (e.g. encrypted session storage, expired access token) was reported `SAAS_SYNC_UNAUTHENTICATED` and refused with **exit 2** before any local verification ran; and (b) even a correctly-detected logged-out host was refused the same way, blocking the read-only phase-completion check the caller actually wanted. **After:** authentication comes from the canonical `TokenManager.session_assessment` (a refresh-capable session reads as authenticated regardless of queue-scope materialization); local verification always runs and is authoritative — the command now **exits 0** whenever local verification succeeds, and hosted-sync unavailability (auth, structural boundary, or route) is reported as a nonfatal `warnings[]` diagnostic in `--json` (a `Warning:` line otherwise), matching the sibling mission commands' logged-out severity policy. Local dossier capture (`plan.md` mission-dossier sync) is unaffected by hosted-sync availability — it is project-isolated local capture and was never gated by the SaaS flag or auth state, matching every other mission command. **Breaking for automation:** a caller that branched on setup-plan's old exit code 2 / `SAAS_SYNC_UNAUTHENTICATED` error for an unauthenticated host must now read `warnings[].code` on exit 0 instead.

- **`spec-kitty init` now gitignores the `.worktrees/` execution-worktrees root, and `upgrade` backfills the entry into existing projects.** (#3689) **Before:** the only code that ever excluded `.worktrees/` was the 0.13.1 migration, which writes the local-only `.git/info/exclude` and never runs for projects stamped ≥ 0.13.1 — so on every project initialised since then, the first mission worktree made the main checkout's `git status` show `?? .worktrees/` permanently, and a stray `git add -A` staged an entire nested checkout; several code paths (`agent/workflow.py` FR-002(b), `workflow_executor.py`) already assumed the root was ignored. **After:** `.worktrees/` is a first-class `IGNORED` surface in the state contract (`worktrees_root`), so fresh `init` writes it to `.gitignore` through the existing `get_runtime_gitignore_entries()` path, and a new `3.2.6rc3_worktrees_gitignore_backfill` migration (sibling to the #3435 lint-report backfill, firing even on projects already stamped 3.2.6rc3) adds it to already-initialised projects — including via `.gitignore` rather than `info/exclude`, so the coverage travels with clones. A real-git regression test pins the observable: after the backfill, a checkout under `.worktrees/` is invisible to `git status`.

- **`spec-kitty upgrade --dry-run` on a project that is already up to date now reports the `mission_type_activations` seed it would still perform, instead of only saying "Project is already up to date!"** (mission `doctrine-drg-silent-drop-boundary`) A real upgrade seeds a missing `mission_type_activations` key on both the migration and the no-migrations path, but the dry-run preview only announced it when migrations were also pending. **Before:** an operator dry-running an already-current project that was missing the key saw "already up to date" and no hint of the pending seed — then a real upgrade silently changed the config. **After:** the dry-run previews the pending provisioning on the up-to-date path too, so the preview matches what a real upgrade does (the `--json` surface and non-dry runs are unaffected).

- **A malformed `drg/fragment.yaml` in one org pack of a multi-pack chain no longer drops the _other_ packs' fragments.** (mission `doctrine-drg-silent-drop-boundary`; #3629 second-opinion follow-up) The mission-step executor tolerated a malformed _optional_ org fragment by degrading it, but did so for the whole chain at once — one bad pack silently evicted its healthy siblings' fragments too. **After:** the degrade is **per-pack** — only the offending pack's fragment is skipped, with an operator-visible `WARNING` naming it, and the healthy siblings still compose. `strict` callers (the diagnostic APIs and the fail-loud composition path) are unchanged and still raise on any malformed pack.

- **`charter activate --cascade` no longer silently drops asset- and template-kind nodes from its cascade report — it now names every one it did not cascade, and says so identically in all three places a cascade is reported.** (#3705; ADR `2026-08-20-1`) **Before:** a cascade filtered out every node whose kind is not charter-activatable (`asset`, `template`) and then never mentioned them, so a pack whose executable check hung off an asset was both unreachable and unreported — the operator saw a successful cascade with no hint that anything had been left out, and nothing in the output distinguished "there was nothing to cascade" from "everything was dropped". **After:** each filtered node gets its own line — `Not cascaded: <kind>/<config-id> (kind not charter-activatable)` — resolved to the config-stem id, never capped or truncated; and when a cascade resolves _zero_ activatable targets because every referenced node was kind-filtered, that is stated explicitly rather than presented as a successful no-op. The same wording comes from one shared helper in all three consumers — the `--cascade` report, the no-cascade warning, and `charter deactivate --cascade` — so the three can't drift. Kind-filtering stays distinct from scope-narrowing: a node excluded by `--cascade-scope` still reports as `Skipped (out of scope)`, never as not-cascaded. **This is a visibility fix only.** Which kinds are charter-activatable is unchanged and deliberately not reopened: the exclusion of `template` and `asset` remains the recorded policy of ADR `2026-08-20-1`. Actually invoking a pack-shipped code asset as a gate handler stays tracked separately as #2599.

- **`spec-kitty init` now gitignores the `.worktrees/` execution-worktrees root, and `upgrade` backfills the entry into existing projects.** (#3689) **Before:** the only code that ever excluded `.worktrees/` was the 0.13.1 migration, which writes the local-only `.git/info/exclude` and never runs for projects stamped ≥ 0.13.1 — so on every project initialised since then, the first mission worktree made the main checkout's `git status` show `?? .worktrees/` permanently, and a stray `git add -A` staged an entire nested checkout; several code paths (`agent/workflow.py` FR-002(b), `workflow_executor.py`) already assumed the root was ignored. **After:** `.worktrees/` is a first-class `IGNORED` surface in the state contract (`worktrees_root`), so fresh `init` writes it to `.gitignore` through the existing `get_runtime_gitignore_entries()` path, and a new `3.2.6rc3_worktrees_gitignore_backfill` migration (sibling to the #3435 lint-report backfill, firing even on projects already stamped 3.2.6rc3) adds it to already-initialised projects — including via `.gitignore` rather than `info/exclude`, so the coverage travels with clones. A real-git regression test pins the observable: after the backfill, a checkout under `.worktrees/` is invisible to `git status`.

- **The off-PR `performance.yml` pipeline no longer red-fails every domain that has no perf tests yet (or no committed baseline) — a `set -e` footgun defeated its own tolerance guard (`#3669`; ADR `2026-08-22-1`).** The per-domain compare step ran `pytest … ; ec=$?; if …` under the Actions default shell (`bash -e -o pipefail`). Under `set -e`, a bare `pytest` line exiting non-zero **aborts the step before `ec=$?` runs**, so the intended allow-list for exit 5 (no `@pytest.mark.performance` tests under the domain's paths — expected during the ADR's incremental per-domain migration) and exit 4 (`pytest-benchmark` USAGE_ERROR when no baseline exists to compare against) never took effect. A first manual `workflow_dispatch` proved it: 5 of 17 legs (`lanes`, `missions`, `review`, `merge`, `dashboard`) — exactly the domains with zero perf-marked tests — failed on pytest exit 5. **Fix:** keep the pytest invocation in an AND-OR list (`… || ec=$?`, with `ec` pre-initialized to 0) so `set -e` can't abort it and the true exit code reaches the guard. Empty/no-baseline domains now pass as designed; a genuine statistical regression (exit 1) still fails its leg. The sibling `--benchmark-save` step was already correctly guarded with `|| test $? -eq 5`.

- **A custom mission family no longer crashes the work-package CLI guard, and a governance profile that selects an artifact that doesn't exist now fails loudly instead of silently vanishing.** (#3658, closes #3627, closes #3633, addresses #3629) Two doctrine-authoring footguns are closed. **Before:** (1) running a _custom_ mission family that named a step `implement` or `review` hit the WP-iteration guard, which raised an uncaught `UnregisteredMissionFamilyError` and aborted the command — an unregistered family has no guard table to enforce, so the crash was pure collateral; and (2) a `governance-profile.yaml` whose `selected_*` list named a nonexistent artifact was _silently_ projected into a phantom auto-minted graph node at generation time, so a typo in a governance selection disappeared without a word instead of being caught. **After:** the WP-iteration guard catches that one exception narrowly and degrades to "no guard failures" for unregistered families (registered families — `software-dev`, `plan`, … — keep byte-identical guard coverage); and DRG generation now fails loud with a `ValueError` naming any unresolved governance scope-edge target, before the phantom-mint step, mirroring the existing operating-procedure fail-loud precedent. Also documents the `Relation.SCOPE` two-grain overload as deliberate accepted debt (ADR amendment) rather than a bug to split. The remaining #3629 item (deprecating the dead `context-sources` profile fields) was subsequently completed in mission `doctrine-drg-silent-drop-boundary` — the block is now removed from the agent-profile schema (see the Breaking entry above).

- **The weekly flake-report workflow no longer crashes on its first live run — it requested two `gh run list` JSON fields that don't exist (mission `ci-flake-report-workflow-01M0M9D8`).** `scripts/ci/flake_report_cli.py` asked `gh run list --json` for `pullRequests` and `isDraft`, which are exposed by `gh run view` / `gh pr` but **not** by `gh run list`; `gh` exits non-zero with `Unknown JSON field: "pullRequests"`, aborting the whole report. The golden fixture tests never caught it because they read a recorded `runs.json` side-channel instead of shelling out to live `gh`. **Fix:** drop the two unsupported fields from the live request — `pr_number` stays `None` on the live path and `pr_identity` falls back to `headBranch` exactly as its push-event branch was already designed to, and `draft` was never read anywhere. The recorded fixture keeps both keys and `_run_from_entry` still reads them tolerantly via `.get()`, so all 111 golden tests stay green; only the live `gh run list` call changes.

- **Legacy PR-bound missions no longer try to finalize planning artifacts onto protected `main`.** (#2938) `finalize-tasks` now recognizes the legacy shape that conflated a protected final target with its planning branch and requires the operator to name the otherwise-unprovable planning ref with `--target-branch`. From the owning checkout it atomically persists that ref as `target_branch` while retaining the protected destination as `merge_target_branch`; foreign linked-worktree writes fail closed. Linked-worktree branch context is still read through the canonical checkout-identity seam, and `--validate-only` remains byte-, index-, HEAD-, status-, and ref-stable.

- **The pre-review gate can no longer pass a work package on an unverified or mis-captured test baseline — closing two false-green paths that let a real regression slip through review.** (#3657, closes #3611, closes #3612) The gate compares a work package's tests against a baseline before it can move to review; two defects made that comparison unsound. **Before:** (1) the baseline and the head side resolved `review.test_command` from _different_ checkouts — capture read it from the planning root while the head gate read it from the lane worktree, whose `.kittify/config.yaml` can lack the setting — so the two sides silently picked different scope sources and the `SOURCE_MISMATCH` safety check never fired; and (2) a declared-command baseline was captured without a shell and without substituting `{output_file}` (so `$VAR`/`~` and the artifact path never resolved), then stored a failure count as if it were the suite size — fabricating a plausible-but-wrong baseline that could read as a clean pass. **After:** scope-source _selection_ always resolves from the single planning root (tests still _run_ in the worktree), so both sides agree or the mismatch is caught; declared-command capture now runs through the same `sh -c` + `{output_file}` substitution the head runner uses, reaps the whole process group on timeout, and _refuses to store_ an ambiguous clean/no-artifact run — degrading to an honest `UNVERIFIED_BASELINE` instead of a false pass. A stored declared-command baseline's `total`/`passed` counts are still derived from failure identities rather than real JUnit suite sizes (documented in-code; it does not affect gate verdicts, which diff by failing-test identity) — worth a follow-up if a reporting consumer needs true counts.

- **`spec-kitty sync now` no longer strands the whole event journal when the server answers HTTP 412 (CLI/server sync-protocol skew) — it halts the pass, keeps every event retryable, and prints the server's own upgrade/pin guidance.** (#1553; supersedes the first cut in PR #3637) The SaaS batch endpoint's compatibility handshake (keyed on `X-SpecKitty-Protocol-Version`) returns 412 with `error_code` ∈ {`client-too-old`, `client-too-new`, `client-protocol-unparseable`}, an `error_description`, and a single `sync_protocol.upgrade_guidance` string. **Before:** a 412 fell into the generic transient bucket, so one `sync now` pass POSTed every batch in the journal and got the same 412 each time, with no operator-visible explanation; the first fix attempt (PR #3637) instead mapped 412 to `terminal_failed`, which _parked_ every event the pass touched — and because parked rows are excluded from selection forever and the delivery `target_id` does not change on upgrade, the journal would never have been redelivered after the operator upgraded, while the drain loop still counted the parking as progress and POSTed (and parked) the entire backlog in one pass. It also hardcoded "upgrade … pip install --upgrade spec-kitty-cli", which is the wrong instruction for a too-_new_ client (the server says pin), and mis-described the trigger header. **After:** each correlated 412 maps to `transient` / `known_no_effect` (retained, re-selected on the next run) carrying the server's `sync_protocol.upgrade_guidance` (then `error_description`, then a neutral fallback) as the error and its `error_code` as the error category; the batch driver halts the pass on the first 412 even when another selected row failed locally before transport, instead of advancing to the next batch; `sync now` prints the halt notice plus the server's guidance right after the counts, and the wholesale-transient exit message names the protocol skew instead of blaming auth or batch size. Parking (`terminal_failed`) stays reserved for per-event-permanent failures (oversized, refused). The CLI does not yet send `X-SpecKitty-Protocol-Version` (it sends the legacy `X-Spec-Kitty-Sync-Protocol`, which the handshake fails open on), so this change is the recovery path for when it does — advertising the new header is deliberately out of scope here.

- **Docs-freshness metadata gates are now diff-scoped on pull requests, so a docs PR is no longer failed by violations on pages it never touched.** (#3316) The `audience:`-reference resolver (`scripts/docs/audience_resolver.py`) and the `description` metadata gate (`scripts/docs/description_length_check.py`) both ran whole-tree in strict mode on every PR. **Before:** any pre-existing dangling persona reference or out-of-band/duplicate `description` anywhere under `docs/` redded an unrelated PR's docs-freshness job, and the only way through was to fix someone else's page. **After:** on `pull_request` both gates take `--changed-from <base-sha>` and report violations only for changed, published `docs/**/*.md` pages; the `push:main` run stays whole-tree (it is the backstop for persona deletions/renames that touch no referrer, the same accepted limitation as #3312). Description uniqueness stays corpus-aware — a changed page that duplicates an _unchanged_ peer still fails and names the peer — and the diff-scoped path re-asserts the published-corpus non-vacuity floor exactly as the whole-tree path does, so a collapsed `docfx.json` page set is still a gate malfunction (exit 2) on a PR. An unresolvable base ref fails closed (exit 2); a resolved diff touching no published docs is a clean pass.

- **`spec-kitty init` no longer gitignores all of `.cursor/` for teams that version-control their own Cursor rules.** (#2498) `GitignoreManager.protect_all_agents()` wrote a blanket `.cursor/` entry for every project, regardless of which agents were selected. **Before:** a repo that tracked `.cursor/rules/contributing.mdc` (or any other file under `.cursor/`) alongside Spec Kitty's own `.cursor/rules/spec-kitty.mdc` found the whole directory gitignored after `init`, making the team's own rules unstageable. **After:** the `cursor` entry in `AGENT_DIRECTORIES` is narrowed to only the paths Spec Kitty itself generates (`.cursor/rules/spec-kitty.mdc`, `.cursor/commands/`, `.cursor/skills/`), matching the existing `.github/copilot/` precedent; `spec-kitty upgrade` removes only the exact legacy `.cursor/` row proven to sit in Spec Kitty's auto-managed block and backfills the three narrow entries. Unmarked or otherwise unattributable blanket variants are preserved with manual-remediation guidance so an upgrade never deletes operator security policy by filename heuristic. The migration and manager also reject symlinked or non-UTF-8 `.gitignore` files without modifying them, including dangling links, so upgrade cannot write outside the project or silently discard bytes. `protect_selected_agents()` also had a latent bug where an agent name owning more than one registry entry silently kept only the last one — fixed alongside, since narrowing `cursor` to three rows would otherwise have surfaced it. `.cursor/skills/` stays ignored as a _declared_ Spec Kitty skill root (`AGENT_SKILL_CONFIG`, not yet populated by the installer); `.cursor/hooks.json` is intentionally **not** ignored (team-owned; only written on explicit `agent config set lint_on_edit`).

- **`spec-kitty upgrade` now backfills `.kittify/lint-report.json` into `.gitignore` on already-initialised projects.** (#3435) `spec-kitty charter lint` writes `.kittify/lint-report.json` as a side effect (the dashboard lint tile and `sync/lint_report_staging.py` read it back, so ignoring — not suppressing — the file is the right remedy). **Before:** fresh `init` projects got the entry via the gitignore contract, but projects initialised earlier were left with an untracked file that tripped `record-analysis`'s dirty-tree guard. **After:** the new `3.2.6rc3_lint_report_gitignore_backfill` migration (`m_3_2_6rc3_lint_report_gitignore_backfill`) adds the entry idempotently on `spec-kitty upgrade`, sibling to the 3.2.4/3.2.5 gitignore backfills.

- **`spec-kitty tracker sync push` and `sync run` now show which authority a SaaS-backed sync used, matching `sync pull`.** (#1221) **Before:** `sync pull`'s human-readable output already rendered the SaaS envelope's `identity_path` (`- provider: …` / `- type: …`) so a user could tell whether an operation ran under workspace installation authority or their own linked provider account, but `sync push` and `sync run` silently dropped the same field from their human output even though the SaaS client returns it identically for all three operations — a user debugging a permission failure on push/run had no CLI-visible way to see which authority was used, only readable by re-running with `--json`. **After:** `sync push` and `sync run` render `identity_path` the same way `sync pull` does; JSON output (`--json`) was already unaffected since it echoes the raw envelope.

- **`spec-kitty doctor command-files` no longer false-positives 15 "missing" errors on every globalized project.** (#1794) The check still resolved each agent's command files at the project-local `.claude/commands/`-style path, but the `3.1.2_globalize_commands` migration (and `3.2.0a4_safe_globalize_commands` after it) moved the canonical files to the user-global command dir and intentionally leaves the project-local files absent — `doctor skills`/`Slash Commands` was updated for this globalized layout, `doctor command-files` was not. **Before:** every configured agent's 15 consumer command files reported `"missing"`/`error` on a correctly globalized project, drowning out any real command-file regression signal. **After:** `check_command_file_health` resolves each agent's files via `get_global_command_dir` (the same helper the healthy `Slash Commands` audit already uses), so a globalized project with healthy global files reports zero issues; the `file` field in table/`--json` output now reports the absolute global path rather than a project-relative one.

- **Hosted event-sync delivers again for consented projects: `sync now` no longer self-blocks on an admission gate whose server endpoint isn't deployed, and `import-history --apply` no longer rejects the server's own preflight success.** (#3564, closes #3620) **Before:** #3293 shipped a hard, unconditional client-side admission gate whose writer (`AdmissionOperationService.perform`) has no production caller and whose server endpoint (`PUT …/sync-admission/`) returns 404 in production — so every consented project had `delivery_target = None`, `sync now` gated on `admission_not_current` (misreported as "not authenticated"), and `delivery_results` stayed 0 despite thousands of queued entries; separately, `import-history --apply` required a correlated per-event `results[]` the deployed preflight never sends, classifying a server success as a rejection and masking the real server diagnostic behind always-zero (non-mutating) reconciliation counters. **After:** the admission gate is conditioned on server capability — it defaults non-strict and mints a labeled local self-admission (`local-nonstrict:<origin>`) so a consented, authenticated project delivers via the existing local-consent-gated path, enforcing strict admission only on an explicit signal (a dormant hook for when the paired server half `spec-kitty-saas#795` lands); the misleading auth message is replaced by the real gate reason; and `import-history --apply` honors a `{accepted: true}` preflight with no `results[]` (staying fail-closed on any malformed or partial verdict) while surfacing the server's structured diagnostic. The self-admission it carries on the wire is honestly self-labeled (`local-nonstrict:…`) and never poses as a server-issued proof — a future strict server rejects it cleanly at ingest (degrade, not corruption) rather than being fooled — and the consent boundary is unchanged. Live end-to-end delivery may still be bounded by independent server-side event-shape validation (schema drift, historical transition semantics `#3017`/`#3001`), tracked separately.

- **`spec-kitty implement --base <ref>` now actually roots the lane on the ref you pass — and hard-errors instead of faking success when it can't — closing the P0 (#3571) that silently pulled unrelated work into a supposedly independent lane.** (#3616, closes #3571) **Before:** on a coordination-topology mission (the default), `--base` printed a green `→ Using explicit base ref` line while the lane descended from an entirely unrelated branch and did **not** contain your base as an ancestor — the override was smuggled through a field the dominant allocation path never read, so it was silently a no-op that also misreported success; unrelated pending work leaked into the lane, invalidating review scope. **After:** `--base` is threaded as an explicit parameter into the topology-aware allocator, so a fresh no-dependency lane descends from `<ref>` alone. On any route that cannot honor the base — reusing an existing lane worktree, re-attaching a crash-recovered lane branch, a dependency-bearing lane whose coord-descended tips would need re-parenting, or a base detached from the recorded planning commit — the command now **hard-errors** (typed `UnhonorableBaseError`, machine-readable in the orchestrator envelope) with a message naming the route, work package, and unhonored base, rather than printing a fabricated success line. The success line prints only after the lane has actually been parented on the ref. The `for_review` gate measures against the lane's real recorded base, and the legacy (`#1684`) `--base` route is preserved byte-for-byte. The broader two-route unification that prevents this class of drift from recurring is tracked as follow-up (#3460 / #3462 / #3536).

- **Charter/runtime gates now honor the mission entity you actually declared, so non-canonical actions and types stop being silently starved and typo'd types fail loud.** (#3596, #3598, #3599, #3597, #3407, #3615) Five charter/runtime surfaces were deciding delivery, tolerance, and gating by membership in a hardcoded 4-token set or a project-wide flag instead of the declared entity. **Before:** a declared non-bootstrap action (`tasks`, `retrospect`) short-circuited to an empty `compact` bundle even though it ships doctrine grain; a typo'd `mission_type` (`softwaer-dev`) resolved silently with fabricated provenance; a custom mission type could not gate on its own artifact filenames; a `plan` mission's `review` step aliased into software-dev's WP-iteration guard. **After:** an action delivers `bootstrap` iff the merged doctrine graph declares its `action:<type>/<step>` node (the 4-token fast path and single-graph-load budget preserved); an unregistered `mission_type` with no matching per-type `governance-profile.yaml` at the project or org layer raises `UnknownMissionTypeError` (your mission-type _activation_ restriction is unchanged — a canonical type you did not activate still hard-fails); artifact filenames resolve from the single per-type `expected-artifacts.yaml` `path_pattern` authority (the four built-ins byte-identical) and the stray empty `spec.md` that satisfied existence gates is gone; and the CLI-guard path routes to the mission's real guard family. **Program ordering:** requires the M0 `spec-kitty migrate backfill-mission-type` gate (above) to have run first. Governance and the four named red-by-design test reversals are recorded in ADR `2026-08-21-1-charter-gate-predicate-inversion`. (PR #3617)

- **A mission type's type-wide governance now reaches the agent, and a procedure's authored rationale is no longer silently dropped — closing the DRG projection gaps where authored doctrine validated, loaded, then vanished before delivery (#3604 / #3605 / #3488).** (#3628; mission rc3-drg-projection-completeness; closes #3604, #3605) **Before:** a mission type's `governance-profile.yaml` selections (its directives/tactics/paradigms/styleguides) were never projected into the doctrine reachability graph, so a **`plan`** mission — which authors _only_ type-wide governance — cascaded to **nothing**; separately, a procedure reference's authored `when`/`reason` rationale was dropped at the graph extractor while directive/tactic/paradigm references kept theirs. **After:** type-wide governance projects as `mission_type --scope--> <governance>` edges for every built-in mission type that declares type-wide selections — documentation, plan, and research (software-dev selects none at the type level and is unchanged) — so a `plan` mission now cascades to its directive, 9 tactics, 3 paradigms, and styleguide, procedure references carry their `when`/`reason` into the graph, and a new structural test **binds the projection (emit) and profile-rendering (delivery) seams** so a channel wired into one but not the other fails a test instead of silently diverging. The profile-delivery path itself needed no code change (verified already correct on `main` — the fix is the anti-divergence guard, not a re-fix). The canonical `scope` relation authority was updated in lockstep to reflect that scope edges now also originate from mission-type nodes. **Operator note:** because previously-dropped governance is now reachable, activating a mission type through the charter cascade surfaces a larger activation set than before (e.g. `plan` grows from an empty cascade to its full governance closure).

- **`implement --base <ref>` now records the correct base provenance even when `<ref>` diverges from the mission's coordination line — hardening the #3571 fix so the `for_review` gate can't silently fall back to the wrong base on exactly those lanes.** (#3571 follow-up) **Before:** a freshly-created lane rooted on a divergent `--base` was misdetected as a _reuse_ of an existing lane (the recorded planning-commit merge landing on top counted as "commits beyond base"), so its `base_commit` provenance was never written — and the `for_review` gate's recorded-honored-base lookup then found nothing and fell back to the topology guess, mis-scoping the review of that lane. **After:** lane reuse is detected structurally (the lane worktree or branch already exists), which is immune to base divergence — a fresh `--base` lane is correctly recorded with its honored base, a genuine second work package in the same lane still reuses it, and a crash-recovered lane still re-attaches.

- **Fail-loud sweep: six code paths that decided correctly but told the operator nothing now emit a legible signal.** (#3578, #3548, #3517, #3412, #2991; interim #3590) A recurring silent-drop defect class — the machine-readable half of a contract intact (correct `error_code`, byte-stable file, truthy return) while the human-readable half that tells an operator what happened is dropped — is closed at six ground-level sites. Each emits through an **existing** operator-visible surface (no new swallowable sink) and lands an issue-pinned red-first regression that asserts on the _signal_, not merely a code or shape:
  - **#3578** — a rollback to `planned` now surfaces `subtasks_reset_count` as **both** a human line **and** a `--json` field, and names the two co-applied siblings (runtime-claim release, review-override clear) that were previously silent. The subtask roster now distinguishes a subtask **completed in an earlier cycle** from one **never started**, so the flat reset no longer conflates work-state with review-state.
  - **#3548** — `orchestrator_api`'s `_fail()` no longer drops the human-readable `message` when structured `data` is passed (16 of 33 call sites had been silently losing their explanation, preferentially on the most actionable errors); both halves now reach the operator in the envelope.
  - **#3517** — the sync emitter no longer returns a durably-unqueued event as truthy and publication-eligible: `_emit` consumes `_route_event`'s durability bool, warns, and returns `None` so the `events.py` publish gates skip it. The never-raise contract is preserved; the bounded-retry redesign stays with #3549's sync owners.
  - **#3412** — a YAML-syntax-malformed `expected-artifacts.yaml` now fails loud (a typed `MalformedManifestError` naming the path) **distinct from "absent"**, instead of degrading to `None` and masquerading as "not found"; a genuinely missing/unreadable file still reads as absent.
  - **#2991** — `finalize-tasks` now warns when an `SC-###` success-criteria ref in a WP's `requirement_refs` is discarded by the `(?:FR|NFR|C)` graph scanner, so an author never believes traceability exists when the ref silently vanished. `SC` is **not** admitted as a first-class ref (the graph is unchanged) — the discard is merely signalled through the existing advisory-warning channel.
  - **#3590 (interim, warn-only)** — `finalize-tasks` now emits an authoring-time, non-blocking warning when a **code** work package's acceptance criteria are observable only **post-integration** (an action, not a diff) — so a WP that cannot be honestly reviewed while its lane is open is flagged at planning time. It **never** blocks finalize and touches no terminal state, gate, or lane exit; the deep terminal-state fix is Mission M6 (#3550 / #3432 / #3433 / #2745).

- **`spec-kitty upgrade` no longer disobeys the operator's own `auto_commit` opt-out, can no longer be blocked by its own generated files, and stops misreporting a successful or aborted run.** (mission `upgrade-command-hardening-01M0N5N4`; #3651, #3654, #3653, #3392, #3376, #3393, #3390, #2491) A cluster of confirmed defects in the ~1,300-line `cli/commands/upgrade.py` — two duplicated orchestration branches with no shared seams — made upgrade fail on its own re-run, ignore the operator's committed configuration, silently over-authorize a destructive repair, and misreport both success and failure. **Before:** a project with previously-written read-only generated command files hit ~30 `Errno 13 (Permission denied)` errors on the next upgrade with no in-product remedy; `auto_commit: false` was ignored — upgrade committed its churn on the main checkout and every worktree regardless, one of ~8 other command paths that honor the setting; `--yes`/`--force` also silently authorized `offer_teamspace_mission_state_migration`'s `doctor mission-state --fix` (`repair_repo`, a mutating repo rewrite) with no distinct prompt; a fully successful `upgrade --project --yes` could exit 1 and print no outcome (#3392); a worktree that failed mid-migration still stamped `schema_version`, misreporting readiness (#3376); the gitignore-backfill migration could gitignore paths it left tracked, leaving the tree permanently dirty (#3393); a `PlacementMismatchError` abort under-reported the mismatch and could leave phantom writes under `--dry-run` (#3390); and post-commit surface-repair writes could land after the single upgrade-churn commit, leaving dirty residue (#2491). **After:** every generated/rewritable-but-read-only file routes through one canonical restore→write→strip-permission-bit writer, so a re-run over its own prior output completes and re-applies the read-only bit instead of erroring; the commit decision for both the main checkout and every worktree defers to `get_auto_commit_default` (`core/agent_config.py`), and when the config disables it and real churn exists, the command now says so in human-mode output (`⚠ Changes were left uncommitted (auto_commit is disabled) — commit them yourself.`) instead of staying silent; `--yes`/`--force` authorizes only the invoked migrations — the mission-state repair is a separately-scoped, default-deny consent gate whose own failure can never sink an otherwise-completed upgrade; the two orchestration branches share a single post-migration finalizer that derives the exit code exactly once from one `UpgradeOutcome`, so a fully-successful run reliably exits 0 with a printed completion outcome and a worktree migration failure is surfaced honestly in the top-line result and exit code rather than downgraded to an invisible warning; and the placement-mismatch abort path and `--dry-run` report honestly with no phantom writes. A behavior-preserving characterization net (`tests/upgrade/test_upgrade_char_net.py`) pins the default (`auto_commit` unset/true) commit behavior byte-for-byte across the refactor.

- **`record-analysis` now emits a commitlint-compliant commit subject for the `analysis-report.md` commit.** (#3678) The prior subject, `"Add analysis report for mission {slug}"`, carried no `type(scope):` prefix and failed `commitlint.config.cjs`'s `type-empty`/`subject-empty` `type-enum` rules outright. **After:** `mission_record_analysis.py`'s `commit_for_mission` call now emits `docs(record-analysis): record analysis report for mission {slug}`, pinning `type` to `docs` per this repo's own convention for tool-authored analyze/review commits (fixing the emitted subject rather than widening commitlint's ignore regex).

- **`record-analysis`'s committed `analysis-report.md` frontmatter now records repo-relative `input_artifacts.*.path` values instead of absolute ones.** (ledger SK-63, FR-007/NFR-001/NFR-002) Hash-input paths (`spec.md`, `plan.md`, `tasks.md`, `charter.yaml`/`charter.md`) were recorded as absolute filesystem paths, leaking a contributor's local checkout layout (`/home/<user>/...`) into a file every mission commits to git history — a problem on a public repo. **After:** `analysis_report.py`'s `_relativize_or_raise` relativizes every hash-input path against its governing root (the repo root for spec/plan/tasks, the resolved canonical root for the charter) before it is written; a path that cannot be relativized against its governing root (e.g. a symlink escaping it) raises a typed `PathRelativizationError` instead of silently recording an absolute path. **Format change:** any tooling that parses `input_artifacts.*.path` from a committed `analysis-report.md` must now expect a repo-relative path, not an absolute one.

- **The dossier-emitter positional-call guard now catches attribute-chain and aliased-import call shapes it previously missed — test-only, no runtime behavior change.** (#3676) The guard's own docstring had framed the gap as an accepted design boundary ("this guard does simple Name-based matching only... widening the detector to handle aliasing is explicitly deferred until a real aliased call site exists"), but a gate a caller can silently route around by either call shape isn't evidence of anything for those shapes. **Before:** `tests/architectural/test_dossier_emitter_positional_guard.py`'s detector matched only bare-`Name` positional calls to the guarded `emit_*` functions, so `module.emit_artifact_indexed(...)` (attribute-chain) and `ei(...)` where `ei` came from `from ... import emit_artifact_indexed as ei` (aliased-import) both passed through unflagged. **After:** the detector resolves an attribute-chain call to its final attribute name, and resolves a same-file `ImportFrom` alias back to its original imported name via a syntactic alias map built once per file (attributing an aliased violation to the resolved original name, not the alias); two new positive-control fixtures — a planted attribute-chain call and a planted aliased-import call — fail (RED) against the pre-widening detector and pass (GREEN) against the post-widening one. No `src/` file is touched; the guard lives entirely in `tests/architectural/`.

- **Expected-artifacts loading now uses one cached charter authority.** (#3770,
  #3412) Runtime, resolver, dossier, and charter consumers share org-first
  precedence and schema validation. Present malformed or unreadable manifests
  fail loudly; only genuinely absent manifests degrade to `None`. An
  architectural gate forbids new direct model construction outside the
  authority. See ADR 2026-08-31-1.

## [3.2.6rc2] - 2026-08-20

_The 3.2.6rc2 candidate shipped 2026-08-20 (rc1 shipped 2026-08-12)._

### ✨ Added

- **Spec Kitty now ships a `spk-doctrine-show-me` skill that guides any agent to
  explain work with compact, checkable visuals — the smallest diagram,
  pseudocode, or tree that answers the question — recommended from the specify
  and plan surfaces (`#3528`).** Before, agents had no shared doctrine for _when_
  a visual earns its place or _which_ shape fits the point (call tree, sequence,
  state diagram, C4, or a `diff` over the matching tree), so visual explanations
  were ad-hoc and often missing. The skill routes to Spec Kitty's canonical
  Mermaid, PlantUML, C4, and diagram-review sources — bundling byte-pinned
  portable copies of the guides and themes so it keeps working once installed in
  a consumer project — and documents faithful `/spec-kitty.status` TUI rendering
  from `--json` (lifecycle lanes vs the five-group display, and done-progress vs
  weighted-readiness, so a custom board never mislabels weighted readiness as
  completed work). Adapted from HumanLayer's MIT-licensed `show-me` skill with
  full attribution and license notice preserved.

- **An organisation doctrine pack can now ship templates and mission-FSM
  content, and `spec-kitty` actually resolves them at runtime — before, an org
  pack could declare a template or mission that no resolution path would ever
  find (`#3524`; closes `#3523`).** The two forked template resolvers
  (`doctrine/resolver.py` and `specify_cli/runtime/resolver.py`) and the FSM
  mission-discovery walks consulted only the built-in, project-legacy, and
  user-global tiers — `resolve_org_roots()` existed but nothing on those paths
  called it, so a configured, validated, activated org pack stayed inert for
  templates and mission discovery. Now an `ORG` tier sits between the
  project-legacy and user-global tiers in the asset chain (6 tiers) and in FSM
  discovery (8 tiers); the two resolvers' tier-1 mission-scoped override probe is
  reconverged (they had silently drifted, so the same lookup behaved differently
  depending on which resolver ran); and `charter list` now reports org-sourced
  entries with the correct `ORG` origin instead of mislabelling them
  `GLOBAL_MISSION` and reading them from the wrong directory. Projects with no
  org pack are unaffected — `resolve_org_roots()` returns `[]` and every new
  lookup is a no-op.

- **`spec-kitty doctor mission-type` reports whether every mission's
  `mission_type` actually resolves, so a broken or unregistered type is visible
  before it misbehaves (mission `mission-type-guard-registry`; `#3402`,
  `#3386`).** Modelled on `doctor identity`, it walks every mission under
  `kitty-specs/` and classifies each into one of six distinguishable states —
  `resolved`, `activated-unresolvable`, `unknown`, `typeless`,
  `legacy-key-only`, or `error` — and supports `--json` for machine output and
  `--fail-on <state,...>` for CI gating (e.g.
  `--fail-on unknown,activated-unresolvable` exits non-zero when any mission
  sits in those states). Before, a mission whose type failed to resolve gave no
  signal until the runtime silently applied the wrong rules; now the condition
  is inspectable on demand.

- **A pack — built-in, org, fetched, or a charter bundle — now has one canonical
  `pack-manifest.yaml` schema instead of two divergent formats (mission
  `pack-metadata-manifest-unification-01M052PT`; closes `#3500`, `#3501`, `#3502`,
  `#3503`, slice of keystone `#2467`; ADR `2026-08-16-1`).** Before, org packs'
  `pack-manifest.yaml` stored per-kind `artifact_counts` (no lineage, and never
  written for the built-in pack every pack extends), while charter bundles'
  `synthesis-manifest.yaml` enumerated `constituents[]` in an unrelated shape —
  two formats that could drift, with neither covering the reference pack. Now the
  unified schema (enumerated `constituents:[{kind,id,path,content_hash}]`, stored
  `artifact_counts` retired for a derived `counts_by_kind` view, charter-only
  fields in an optional `charter:` profile block) is defined and the built-in pack
  emits it: a generated manifest (265 constituents, wired into `spec-kitty doctrine
  regenerate-graph`) plus new authored `packs/built-in/pack.yaml` + `pack.md`
  carrying a stable, immutable ULID `pack_id` and declared `parent_pack` /
  `accompanies_doctrine_pack` lineage edges, resolved exclusively through the
  existing `org_extends.resolve_extends_order` (no second lineage walker —
  enforced by a non-vacuous architectural ratchet). `pack_version` is
  derive-else-fallback: authored in `pack.yaml` when present, else generated, so
  fetched/org packs keep genuine fetch-time provenance. This slice lands the
  schema, models, and the built-in-pack writer; org/fetched/charter manifest
  writers and the `pack_id` resolver cutover are fast-follow, and the broader
  "compound packs" slice of `#2467` remains future work.
- **A new `spk-run-verdict-capture` skill so every agent harness records a WP
  review verdict the same way (`#3121`).** The sole authority for a verdict is the
  `review_result` event in `status.events.jsonl` (the `review-cycle-N.md` render
  is non-authoritative); the skill documents the deterministic CLI seam
  (`spec-kitty agent tasks move-task <WP> --to approved|planned
  --review-feedback-file`) and its verdict vocabulary, and `spk-run-review-wp`
  now references it.
- **Committed doctrine provenance is now portable across machines, checkouts,
  and wheels — no more baked-in absolute paths (mission
  `operator-config-ergonomics`, WP01/WP03/WP04; `#3494`;
  `FR-001`/`FR-002`/`FR-003`/`FR-006`/`FR-007`/`FR-008`).** Committed
  `charter.yaml` and `agent_profiles_manifest.json` used to record each
  built-in doctrine pack under the authoring machine's absolute filesystem
  path, so the same files broke on a teammate's checkout, an installed wheel,
  or CI. Both provenance carriers now emit a portable
  `${SPEC_KITTY_PACKS_ROOT}/built-in/...` token through one shared normalizer
  and **never** a resolved path — even when `SPEC_KITTY_PACKS_ROOT` is already
  exported to an absolute path at emit time (the re-bake case is
  regression-guarded). A single kernel expansion seam (`src/kernel/env_expand.py`,
  `expand_env_template`) backs both this token and the `.kitty.env` pointer
  below, and `SPEC_KITTY_PACKS_ROOT` is its canonical packs-root authority. An
  idempotent `spec-kitty upgrade` migration (`m_3_2_7_heal_provenance_paths`)
  rewrites any already-committed absolute built-in path back to the portable
  token with zero manual steps — this repo's own leaked paths in
  `.kittify/charter/charter.yaml` and `.kittify/agent_profiles_manifest.json`
  were healed the same way. A new `doctor provenance` facet reports any
  remaining leak with a heal hint.
- **Operator environment (SaaS tokens, org slugs, path overrides) now has one
  file to point at, loaded before anything else runs (mission
  `operator-config-ergonomics`, WP02; `#3495`; `FR-004`/`FR-004a`/`FR-005`).**
  Previously these values had to live in your real shell environment or be
  re-typed per project. A two-tier `.kitty.env` file — `${SPEC_KITTY_HOME}/.kitty.env`
  machine-wide, overridden by `<repo>/.kittify/.kitty.env` per-repo — is now
  loaded into `os.environ` **before** any other `spec-kitty` module is
  imported, so even import-time-gated behaviour picks it up. Precedence is
  **real-env > per-repo > home**: an explicit shell value always wins, and a
  per-repo file only arms the project it lives in (unlike a global `export`,
  which arms every project the shell later touches). `.kittify/config.yaml`
  gains a single `env_file` pointer (default `${SPEC_KITTY_HOME}/.kitty.env`).
  Fail policy is explicit: an absent file is skipped (the default for almost
  every project today); a present-but-unreadable `env_file` fails loud and
  names the file, because it gates auth; a malformed `KEY=VALUE` line is
  skipped; and a `SPEC_KITTY_HOME=` line inside the file is dropped with a
  warning to prevent locator recursion. An idempotent `spec-kitty upgrade`
  migration (`m_3_2_8_provision_kitty_env`) seeds the per-repo scaffold,
  registers the `env_file` pointer, and adds `.gitignore`/`.claudeignore`
  rules — seeding only values already present in the environment, never a live
  secret (secret-shaped vars are written as commented, blank templates). A new
  `doctor env-file` facet reports presence, tier, readability, pointer, and
  ignore-rule health with every value redacted through a fail-closed allowlist.
- **Opt-in release-candidate channel — catfood an rc without ever nagging
  operators who did not ask (mission `operator-config-ergonomics`, WP05;
  `#3496`; `FR-009`/`FR-010`).** A default-off `SPEC_KITTY_PRERELEASE`
  preference makes every "latest version" surface — `spec-kitty upgrade
  --agent-check` and the throttled startup nag — pre-release-aware only when
  explicitly opted in. Left unset (the default, unchanged for every existing
  project), only the latest **stable** release is ever surfaced, even when a
  newer rc exists on the index. Opted in, the newest PEP 440 pre-release is
  surfaced and the proposed upgrade is a **pinned** `spec-kitty-cli==<rc>`
  install, never a floating `--pre` flag. A new `doctor channel` facet reports
  the active channel. This ships the consumer half only; CI's rc build/publish
  cadence stays in `#3047`.
- **New architecture references tie the SaaS opt-in, `.kitty.env`, and rc-channel
  decisions together (mission `operator-config-ergonomics`, WP06; `FR-011`).**
  Two ADRs record the decisions:
  [`2026-08-16-5-operator-config-env-expansion-seam.md`](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
  (the kernel env-expansion seam, token provenance, and `.kitty.env` layering)
  and
  [`2026-08-16-4-rc-release-channel.md`](../adr/3.x/2026-08-16-4-rc-release-channel.md)
  (the default-off rc channel). A new
  [`team-kitty-saas.md`](../architecture/team-kitty-saas.md) architecture doc
  walks the full opt-in → project-store migration → admission/delivery-target →
  auth → history-disclosure → `sync now` flow with an end-to-end Mermaid
  interaction diagram. Consumption docs and the `spk-team-{sync,auth,tracker}`
  skills now point operators at the durable `.kitty.env` mechanism instead of a
  per-shell `export`.
- **An agent working the mission lifecycle — hitting a merge-gate rejection,
  an issue-matrix verdict, or an undrained SaaS sync — previously had to
  already know the mechanics, because they lived only in a maintainer's
  private notes (mission `self-documenting-repo` Bucket 2; `#3464`, follows
  `#3448`).** A second audit of that private memory routed the durable
  workflow / CI / git / status-&-sync mechanics into the repo's canonical
  homes: `docs/development/how-to/review-gates.md` now carries the
  (event-sourced) review-cycle + merge-gate mechanics and the issue-matrix
  discovery surface; a new `docs/operations/sync-drain.md` documents the real
  3-gate drain (`saas_disabled` → `missing_auth` → `missing_team`) and the
  `sync doctor` false-green trap; `coverage-signals.md` and
  `known-friction-points.md` gain the critical-path-move coverage remedy and
  the CI-label skip guard; `pr-landing.md` gains true-base/stale-stack
  diagnostics and a new `compress-mission-history.md` how-to; the
  architecture docs correct a **live stale-doc regression** (`AGENTS.md`
  claimed a `lanes.json`-absent `-WP##` fallback the resolver actually raises
  `MissingLanesError` for); three review-discipline heuristics enrich the
  doctrine tactics, and the `gh` "Closes #A,#B links only #A" trap lands in
  the tracker toolguide. A committed
  `agent-memory-workflow-migration-manifest.md` (with a completeness test)
  maps all 49 audited memories to a repo home, an already-home citation, a
  learned-fact note, or "keep-private". Dogfooding payoff: verifying against
  current code caught several _stale_ memories — the review-gate frontmatter
  mechanism was retired for an event-sourced one, and the drain's second gate
  was mis-remembered as `sync migrate` (retired).
- **An agent tripping a gate, hunting the right doctrine template source, or
  recovering a split-brain mission previously had to already know the
  answer — that knowledge lived only in a maintainer's private notes, not in
  the repo (mission `self-documenting-repo`; `#3448`).** A maintainer audit
  found this tribal knowledge nowhere in the shipped repo. Now it does:
  architectural/docs gate assertions (`write-side re-derivation`, `inert
  schema slots`, `relative-link fixer`) print a **content-anchored remedy
  derived from the gate's own logic**, so tripping a gate tells you how to
  satisfy it; `AGENTS.md` corrects the stale `src/doctrine/missions/…`
  template-source path to `packs/built-in/missions/…` (with a grep guard);
  six operator recovery runbooks for coord/lane split-brain scenarios are
  published under `docs/operations/`, each leading with the shipped
  `spec-kitty doctor … --fix` where one exists; and the docs-inventory
  freshen, mission wrap-up, and env/tracker conventions are now findable in
  `docs/development/`. A committed `agent-memory-migration-manifest.md`
  (with a completeness test) maps every audited gap-filler to its new repo
  home, its tracking issue, or an explicit "behaviour retired" — the audit
  surfaced five memories that were already stale (e.g. the shard-registration
  guidance retired by `#2671`'s auto-cover, and a `mission-gate-artifact`
  gate that never existed). Deleting the matching entries from a
  maintainer's live `MEMORY.md` stays a manual, per-operator checklist
  tracked in the manifest — this mission migrates the knowledge into the
  repo, it does not touch anyone's private memory file. Three behaviour
  quirks found along the way were filed, not fixed (`#3450`, `#3451`,
  `#3452`).
- **CI now builds each shippable module as its own reusable workflow, and a new
  `spec-kitty regen` lets contributors fix generated-asset drift themselves
  (mission `modular-per-package-ci-01M025GV`; `#3447`, closes `#3379`).** The
  monorepo already ships separately-packaged modules (`src/kernel`,
  `src/doctrine`, the `packs/built-in` data pack), but CI ran them as
  path-filtered jobs inside one monolithic `ci-quality` workflow, and the
  generated agent-command baselines + codex/vibe skill snapshots drifted
  silently when their source prompt templates changed — a contributor's
  one-line edit tripped a dozen parity gates a maintainer had to regenerate by
  hand (`#3379`). Now `kernel`, `doctrine` (fast + integration legs), and
  `packs` each build in an `on: workflow_call` module workflow invoked as a
  `uses:` job inside `ci-quality`, so a module has its own build boundary while
  its coverage still aggregates into the single run the Sonar reporter reads
  (reusable workflows, not `workflow_run` — coverage never fragments across
  runs). The architectural CI-model guards learned to resolve `uses:`
  delegation through one seam so a reusable-workflow caller is modeled as if it
  ran inline. `spec-kitty regen [--check]` regenerates the committed generated
  fixtures from source, byte-identical to a `PYTEST_UPDATE_SNAPSHOTS` run, from
  a single shared version pin; `--check` is the fork-safe freshness gate (it
  fails with the exact command + diff, since a fork PR's read-only token cannot
  commit back). A trust-tiered `regen-assets` workflow runs check-only on every
  PR, auto-commits on same-repo pushes, and offers a maintainer-label
  privileged path that ships disabled pending a security review. The 12-agent ×
  N byte grid that caused the churn is retired for structural invariants plus
  one canonical byte snapshot per render branch (markdown + TOML), so a
  source-prompt edit now regenerates at most one canonical fixture instead of
  ~14.

- **An org- or project-tier doctrine pack can now contribute a mission type
  that works end to end (mission `up-mission-type-seam-01KZY1JB`; `#3424`,
  closes `#3397`).** Before, a mission type shipped by an org or project pack
  could be declared and activated but not used: `mission create`, charter
  activation, and action-sequence projection all resolved against a
  built-in-only roster, so a custom type either hard-failed or — worse —
  silently resolved to an empty action sequence that planned nothing yet
  reported success. Now a layered, pack-aware lookup resolves built-in, org,
  and project mission types in that precedence order with a genuine action
  sequence and template set, and four operator-facing surfaces stop reporting
  falsehoods: `charter mission-type list` shows the real source layer,
  `mission-type show` succeeds for an activated non-built-in type, `doctrine
  mission-type list` actually layers, and `charter activate`'s step-removal
  warnings compare real sequences. Three previously silent degradations —
  malformed mission-type YAML, an unreadable roster directory, and an empty
  action sequence from a non-built-in layer — now fail loud, naming the
  offending file and layer. This is the availability slice only; mission-type
  is deliberately not promoted to a first-class doctrine artifact kind (ADR
  `2026-08-13-1`).

- **Hosted-sync consent is now per-project: one immutable `project_uuid` owns
  one physically separate sync store and one explicit consent decision
  (mission `per-project-sync-consent-ledgers-01KZKMQZ`; `#3262`, pairs with
  SaaS `#585`).** Before, a shared journal/ledger/queue mixed every project's
  rows and a filter defect could deliver another project's data (the #3030
  consent incident). Now each project's consent, consent epochs, journal,
  delivery results, body/offline queue, target binding, and migration state
  live in a UUID-owned `ProjectSyncStore` no other project's operation can
  open; `spec-kitty sync opt-in` records the only local grant authority
  (offline-capable, never inherited from login/URL/slug/path/env), opt-out is
  an immediate epoch-sealing barrier that never deletes captured rows, and
  `SPEC_KITTY_ENABLE_SAAS_SYNC` is strictly deny-only — arming it grants
  nothing. Local consent additionally pairs with an independent target-scoped
  SaaS admission generation, and `project_not_admitted` refusals park
  terminally instead of retrying. Operators migrate legacy shared state with
  the new copy-only, resumable project-store cutover commands
  (`spec-kitty sync project-store-preview` / `-migrate` / `-status` /
  `-quarantine` / `-history`); the retired shared-store `sync migrate`
  refuses with guidance.
  See [Per-Project Sync Consent](../guides/project-sync-consent.md).

- **The declarative transition-gate design is now documented as architecture,
  and two mission-doctrine docs point at the right paths again (`#3378`).**
  Before, the settled model for how transition gates work — the declarative
  `gate` artefact kind, where a gate executes, the trusted-publisher rule, and
  the typed-severity outcome — lived only in scattered discussion, and
  `mission-type-resolution.md` / `doctrine-kinds.md` still named the
  pre-relocation `src/doctrine/missions/` source of truth. Now six Proposed
  ADRs plus a `mission-gates.md` explanation page (with three render-verified
  diagrams) capture the design in one place, and those two docs are retargeted
  to the live `packs/built-in/missions/` paths.

- **Documentation can now be marked `durable` — a standing reference that is
  never flagged as stale draft (mission `docs-plans-closeout-01KZTK2J`;
  `#3368`).** Before, a long-lived throughline doc could only be `active`, so the
  freshness SLA eventually nagged it toward "review or retire" like any aging
  draft. Now `durable` is a reserved `doc_status` across the whole authority
  chain (the `042-common-docs` directive, the `DocStatus` enum, the common-docs
  styleguide and tactics, and the never-stale freshness rule), so a deliberate
  standing document is left alone. This closeout also retires ~60 shipped or
  superseded working notes in place (content preserved, evidence-cited) and
  gathers the domain plans under `docs/plans/domains/`.

- **`spec-kitty intake` now recognises an optional v1 handoff packet so upstream
  requirements tools can seed a mission without the agent re-inventing FR/AC
  ids.** A packet is ordinary Markdown; YAML frontmatter with `handoff_packet: 1`
  is additive. Unknown versions and malformed YAML degrade to today's prose
  intake. `intake --auto` also scans `.handoff/*.md`. Contract:
  `docs/contracts/handoff-packet-v1.md`.

- **The doctrine documentation site now shows rendered schema diagrams of the
  doctrine artefacts, drawn locally with no network egress (mission
  `doctrine-schema-diagrams-01KZTQTH`; `#3366`, `#3354`).** Before, the doctrine
  layer's shape — the relationship graph, the mission-step contract and action
  index, the cross-kind overview and the full agent-profile schema — lived only
  in prose, and the docsite had no way to render PlantUML at all. Now
  code-grounded `@startyaml` diagrams are authored for each and **drift-guarded
  against the live frozen models** (a diagram that falls out of sync with the
  code reds the build), then rendered offline by a version+sha256-pinned
  PlantUML running inside a network-isolated container — so building the docs
  sends nothing off-machine. Each rendered figure carries derived alt/aria text
  for accessibility.

- **A shrink-only census gate now guards the 40 test sites that pin
  `SPEC_KITTY_HOME`, so the collision can only get smaller from here (mission
  `isolated-home-pin-guard-r1a-01KZNMA3`; `#3121`).** Before, nothing stopped a
  41st ad-hoc home pin from landing, and a naive "converge them all" cleanup
  would silently delete the load-bearing isolation those fixtures carry. Now a
  content-addressed census — pinned as debt at a frozen SHA — plus a canonical
  `canonical_home` owner fixture, a falsifiability probe, and a halt gate red the
  build if the pinned set grows. Contributor-facing test infrastructure only (no
  `src/` change); this lands the _instrument_ ahead of the follow-on adoption
  (R1b), so `Refs #3121` rather than `Closes`.

### ♻️ Changed

- **The dead-symbol allowlist's provenance is now a machine-readable
  `source_module=` field instead of a parsed comment, so refreshing a still-dead
  allowlisted symbol no longer depends on comment hygiene (mission
  `symbolkey-source-module-01M0B0SF`; `#3552`).** Before, a content-tier entry's
  originating module lived only in its free-form `# module::Name` comment,
  which the refresh helper (`_refresh_dead_symbol_hashes.py`) had to
  tokenize-parse to recover — a fragile source of truth that had drifted into
  multiple comment formats, and same-name symbols from different modules
  couldn't be told apart structurally. Now every content-tier `SymbolKey`
  carries an optional, provenance-only `source_module=` keyword as the single
  canonical source; the `# module::Name` comment stays in place as
  human-readable audit trail, but the machine comment-parsing path is retired,
  and same-name entries disambiguate on the field rather than on comment
  convention. Test infrastructure only, no `src/` change (no version bump).

### 🐛 Fixed

- **`agent context resolve`'s error contract on an unresolvable/ambiguous `--mission` handle already changed in #167 without being recorded: exit code 2→1, and non-`--json` diagnostics moved from stderr to stdout (documentation follow-up, #174, controller-qa MINOR on #167).** Before #167, `resolve_context` called `resolve_mission_handle` directly, which — on `MissionNotFoundError`/`AmbiguousHandleError` — printed to `err_console` (stderr) and called `sys.exit(2)` in non-JSON mode, bypassing this command's own `--json` envelope entirely (the root cause of #160's quarantined strict-JSON test). #167 fixed that bypass by catching both exceptions and re-raising them as this command's own `ActionContextError`, which its existing handler renders through `console` (stdout) with `raise typer.Exit(1)` for both JSON and non-JSON output. Net effect for `agent context resolve` (only — no other `resolve_mission_handle` caller is affected): a not-found/ambiguous `--mission` handle now exits **1** (was 2) and, in non-JSON mode, prints its `[red]Error:[/red] ...` line to **stdout** (was stderr). Exit 1 is the correct, intended contract — this entry records the change for callers that depended on exit 2 or on scraping stderr.

- **Mission-handle JSON `error_code`/`error`/`outcome` values are now UPPER_SNAKE (`MISSION_NOT_FOUND`, `MISSION_AMBIGUOUS_SELECTOR`) across every emitter, matching the sibling convention already used elsewhere (`decisions/models.py`'s `MISSION_NOT_FOUND`, `_read_path_resolver.py`'s `MISSION_AMBIGUOUS_SELECTOR`) (#174, controller-qa MINOR follow-up on #167).** `resolve_mission_handle`'s `--json` envelope (`selector_resolution.py`), `AmbiguousHandleError.to_dict()` (`mission_resolver.py`), `agent context resolve`'s `ActionContextError` codes, and `agent retrospect synthesize --json`'s `outcome`/`error` fields previously emitted lowercase `mission_not_found`/`ambiguous_mission_handle` — inconsistent with every sibling code in the same functions. **This is a breaking JSON-contract change** for any caller that string-matched the old lowercase values (`spec-kitty agent tasks status --json`, `agent issue-verdict --json`, `implement --json`, `doctor review-cycle-reconcile --json`, `agent context resolve --json`, `agent retrospect synthesize --json`); the `success`/exit-code/stdout-vs-stderr shape is unchanged.

- **`ZeitgeistClient.offer()` now posts presence/focus/session control envelopes to a real relay's `/managed/control` endpoint with the headers it actually requires, instead of a route that always rejected them (`FIX-M2-10`).** Every `offer()` call — `presence()`, `focus_start/heartbeat/pause/end()` — was POSTing its `{op, request_id, args}` envelope to `<relay_url>/events`, the baseline Beacon-shaped route (`zeitgeist/server.py`), which has no `op` dispatch of any kind and structurally cannot process it; against a real, correctly-configured relay this was a 422 on every single call, discovered by `DQA-M2-02`'s Docker-local suite. `offer()` now targets `/managed/control` (`zeitgeist/managed.py`'s real presence/focus/session op dispatcher), includes the `schema_version` field `managed_control.schema.json`'s `ControlEnvelope` requires, and sends both gates a real relay enforces on that route: `Authorization: Bearer <token>` (the outer, unconditional `AuthenticationMiddleware` gate every route but `/health` sits behind) and `X-Zeitgeist-Capability: <token>` (`managed.py`'s own capability check, verified against a separate secret). Both headers carry the same single credential `credentials.py`'s `checkout` flow already stores per repo — the same value `subscription.py`/`operability.py`'s already-landed callers already forward as the capability header — rather than introducing a second stored secret. Covered by a new protocol-faithful local double (`tests/zeitgeist_client/conftest.py`'s `ManagedControlDouble`, mirroring `managed_auth.SharedSecretCapabilityVerifier`'s real HMAC wire shape and kind-scoped capability grants) in addition to the existing recording double.

- **Windows skill-content migrations no longer fail with `WinError 5` when replacing a managed read-only `SKILL.md` (#802; upstream #3771).** The shared bounded-directory writer clears the destination's write attribute before its atomic replace and restores the previous mode afterward, so migrations update read-only skill files without weakening their managed state. A POSIX unit regression simulates Windows' read-only-destination replacement failure, so the defect is covered without a Windows runner.

- **HTTPS doctrine bundle fetches now persist ETags separately from pack versions and safely resolve Artifactory `version` metadata.** Existing `source_type: https` URLs with a valid `/artifactory/<repository>/<item>` path are recognized automatically; `source_type: artifactory` is also available to enforce that intent. Successful downloads are buffered before one exact-item AQL response co-attests the `version` property and SHA-256, and the checksum must match those exact bytes before extraction or snapshot promotion. Conditional validators are reused only for the same query-free source and an intact local snapshot; query-bearing URLs always fetch unconditionally rather than collapsing distinct resources or persisting signed parameters. A 304 deliberately leaves the prior snapshot and sampled version byte-for-byte unchanged.

- **`safe-commit`/`spec-commit` and work-package prompts now print commands you
  can actually run — before, they named invocations that error out when
  copy-pasted (`#3577`).** The protected-branch commit refusals told operators to
  run `spec-kitty mission create --start-branch …` and the WP task-prompt
  templates showed `spec-kitty agent status`, but neither is real: `--start-branch`
  lives only on `agent mission create`, and the status board is `agent tasks
  status` (`agent status` is a command group with no board). Both are corrected
  at the source, so a printed command runs as-is.

- **A warn-mode commit-guard warning is no longer swallowed on a successful
  `safe-commit`/`spec-commit` — operators now see the guard's warning instead of
  it vanishing (`#3580`).** Before, a successful commit discarded the guard's
  warn-mode output, so a warning the guard emitted never reached the operator.
  Now the guard's stderr is surfaced on the success path, while git's routine
  stdout summary is routed to debug so an ordinary commit no longer emits a
  spurious warning on the same channel.
- **Activating a mission type now cascades to the governance its steps depend on,
  and the cascade proposes only kinds you can actually activate (`#2829`; M5 of
  the charter-resolution program).** Before, the charter cascade followed only
  `requires`/`suggests`/`refines`, so the forward closure from a `mission_type`
  dead-ended at the intermediate `action` node — every built-in mission type
  cascaded to **zero** artifacts, and the governance an operator switched on
  reached nobody. The followed set now also walks the action hop (`scope` +
  `instantiates`), so the three governance-bearing built-in mission types cascade
  to their directives/tactics/styleguides (measured 31/23/160, was 0). At the same
  time, cascade candidacy is filtered to the canonical `CHARTER_ACTIVATABLE_KINDS`
  authority, so it no longer proposes non-activatable `template`/`asset` targets
  (which surfaced as spurious "could not cascade-activate" warnings for 137
  existing sources). `mission_type:plan` correctly cascades empty — its step
  contracts scope no governance, so the traversal dead-end is closed for it too but
  there is nothing to reach (tracked as a follow-up to author plan-step
  governance). The relation-set decision is recorded in ADR `2026-08-20-1`.

- **The last five charter-activated doctrine artefacts that no consumer could reach
  are now wired to a single authority or honestly marked direct-activation-only
  (residual of `#3009`; M5).** Four had a defensible source expressed only as a
  hand-authored overlay edge; each is promoted to a real reference in its owning
  directive's frontmatter (DIRECTIVE_034 → `given-when-then-authoring` + `gherkin`,
  DIRECTIVE_030 → `sonar`, DIRECTIVE_041 → `quadruple-a-test-format`), so the pure
  doctrine graph explains their reachability without a secondary overlay patch and
  the shipped graph stays byte-identical. The fifth, `deployable-skill-authoring`,
  has no defensible source and is recorded direct-activation-only rather than given
  a guessed edge. Promoting the metadata surfaced — and fixed at root — a second
  validation authority: the catalog `DirectiveReference` model and
  `directive.schema.yaml` both rejected the `when`/`reason` keys under
  `extra="forbid"`, which would have silently dropped a promoted directive and
  degraded the profile renderer to a `CharterCatalogMissWarning`.

- **A procedure named in an agent profile's `operating-procedures` field now
  becomes a real, cascade-reachable dependency of that profile — and a fictional
  or wrong-kind entry fails the doctrine build loudly instead of drifting in
  silence (`#2994`, `#3352`, `#3488`; M3 of the operating-procedures program).**
  Before, those edges were hand-pinned one-by-one in the DRG extractor (drift-prone
  and easy to forget), while 44 dead references — 36 pointing at procedures that
  never existed and 8 pointing at the wrong kind — sat unresolved and invisible.
  Now the field is the single authority: `spec-kitty` harvests it into
  `agent_profile --requires--> procedure` graph edges, refuses to build when a
  built-in entry does not resolve to a real procedure node (naming the offender),
  and `spec-kitty doctor doctrine` surfaces any unresolved entries. The 44 dead
  references were triaged (delete / repoint / migrate) so the shipped population
  is 100% resolvable.
- **Charter preflight remediations can now actually clear the check they name,
  including for a legacy-bundle project, instead of sending the operator in a
  circle (`#2831`).** An operator on a project carrying the pre-consolidation
  legacy bundle (`governance.yaml`/`directives.yaml`/`metadata.yaml`/
  `references.yaml`, no `charter.yaml`) was told to run `spec-kitty charter
  sync` — a documented pure staleness reporter (`src/charter/sync.py`: "it
  always reports `synced=False` / `files_written=[]`") that clears nothing, so
  the gate refused identically with no way out. Three fixes: (1) the blocking
  `charter_source`/`synced_bundle` `missing`-state remediation now names
  `spec-kitty upgrade --yes` for a real legacy bundle — which reaches
  `ConsolidateCharterBundleMigration` and composes `charter.yaml` FROM the
  legacy content — instead of the content-discarding `spec-kitty charter
  generate --no-from-interview` both shapes previously shared; a project with
  no charter at all still gets the generate command, since there is nothing to
  preserve. (2) `spec-kitty charter preflight --auto-refresh`'s refresh
  sequence no longer opens with a hardcoded `charter sync` — step one now runs
  whichever of the above commands the freshness computer already derived,
  so auto-refresh can genuinely repair a missing/legacy charter source instead
  of failing on step one every time. (3) `charter status`/preflight now
  reports a `charter.yaml` that parses as YAML but is not a real charter
  bundle — an empty mapping, or a `schema_version` outside the supported
  `2.x.x` series — as `invalid` rather than `fresh`, so a downstream consumer
  that would reject the same file no longer sees preflight green it first.

- **A hand-authored project-tier agent profile now becomes a reference-graph node
  the charter cascade can reach — before, it loaded and validated but was
  silently invisible to cascade (`#3038`; M6 of the charter-resolution program;
  asset half deferred to `#3037`).** The project doctrine tier admitted only
  three kinds (directive / tactic / styleguide) as DRG nodes, so a profile
  authored under `.kittify/doctrine/agent_profiles/` reported healthy yet reached
  no dispatched agent. Spec Kitty now walks the authored project profiles and
  emits an `agent_profile:<id>` node into the project overlay `graph.yaml` the
  cascade reads — through the existing additive-only guards, and failing loud
  (naming the file) on a malformed, URN-unsafe, or duplicate `profile-id` rather
  than silently skipping it. The kind→node-kind admission map is now
  `ArtifactKind`-keyed and covered by the totality gate, so a future kind cannot
  silently escape project-tier node admission.

- **Loaded doctrine now actually reaches the dispatched agent — glossary packs,
  procedure/tactic step descriptions, project-overlay agent profiles, and
  `procedures` in `charter context --json` are no longer silently dropped
  (`#3489`, `#3176`, `#3389`, `#3488` render half; M4 of the charter-resolution
  program).** Before, four delivery/render paths validated clean yet delivered
  nothing: `GLOSSARY_PACK` had `slot=None` in the action-bundle delivery table
  (one of two `None` rows lacking the module's required stated reason) and no
  renderer, so glossary packs were structurally unreachable in every config;
  procedure/tactic step `description` was dead code (`title` is required, so
  `title or description` never reached it — ~63% of step content undeliverable);
  `build_activation_aware_doctrine_service` derived its project root from three
  fixed candidates, none of which was `.kittify/agent_profiles`, so a
  project-overlay profile silently vanished when resolved through the
  activation-aware service; and `charter context --json` omitted the
  `procedures[]` array the text render already shipped. Now `GLOSSARY_PACK` has a
  real `ACTIVATED` delivery slot with a term-name surface list plus a
  `--include glossary-pack:<id>` fetch pointer (names only — the full
  definitions stay behind the pointer so the NFR-001 token budget is respected),
  **every** remaining `None` delivery-table row carries a machine-checkable
  stated reason (closing the class, including `ANTI_PATTERN`), step
  `description` renders alongside `title` on both the action-bundle and profile
  channels, the styleguide/toolguide pointer-only choice is a documented
  deliberate budget decision rather than an unlabeled no-op, an optional
  `agent_profile_overlay_dir` threaded through the doctrine-service builders
  (default `None`, byte-identical unset) lets `default_profile_repository`
  resolve `.kittify/agent_profiles` through the sole sanctioned builder, and
  `context --json` ships a typed `procedures[]` array under a deliberately
  bumped `context_schema_version` (`1.0.0` → `1.1.0`) with `asset` documented as
  reference-only (its typed-array promotion deferred behind `#3037`). The
  `--include glossary-pack:<id>` fetch the pointer advertises inherits the same
  activation gate as the delivery slot (a de-activated pack is a structured miss,
  never a definition leak), and a delivered glossary pack is surfaced in the
  `--json` payload's `references[]` link set rather than being silently absent.

- **Doctrine authored in an org pack or project overlay now loads and activates
  with the same completeness as the built-in corpus — nested subdirectories are
  no longer silently dropped, and the charter kind vocabulary is derived from a
  single authority so drifted copies can't render the wrong token or blind kind
  inference (`#3490`, `#3426`, `#2981`; M1 of the charter-resolution program).**
  Before, org/project discovery scanned non-recursively while built-in used
  `rglob`, and the doctrine _loader_ and the charter-activation _resolver_ each
  decided recursion independently — so a tactic, styleguide, or agent profile
  authored one directory deep (e.g. `styleguides/writing/`) loaded at runtime and
  showed in `charter list`, yet the activation resolver silently skipped it
  (measured 71% tactic undercount; nested org styleguides un-activatable). Now a
  single doctrine-layer recursion authority (`doctrine.discovery_recursion`) is
  read by both the loader (`base._project_scan`, `agent_profiles._load` — the two
  redundant `rglob` overrides removed) and the resolver
  (`kind_vocabulary._org_scan_dirs` / `_layer_scan_dirs`), so org/project
  discovery is unconditionally recursive and the two agree by construction;
  kind-specific globs keep `.provenance/*.yaml` sidecars and `.md` files out, and
  the recursive flat-org scan excludes the reserved `built-in/` subtree so
  flat-wins-over-legacy precedence is preserved. The plural↔singular charter
  kind vocabulary is now derived from one `ArtifactKind`-backed authority
  (`CHARTER_ACTIVATABLE_*`, the 10 activatable kinds including `anti_pattern`),
  collapsing the hand-copied maps in `charter.activation.activations` and
  `charter.activation._activation_render` — the two drifted copies that had fallen two kinds
  behind, so `glossary_pack` rendered as its plural and `glossary_packs`
  inference was blind, are fixed. `charter context --include glossary_pack:<id>`
  now renders and `--include anti_pattern:<id>` resolves to a normal not-found
  instead of erroring on an "unsupported selector kind". A new falsifiable
  parity/totality gate binds loader↔resolver recursion agreement and covers the
  string-keyed kind authorities the previous enum-keyed guard could not see, so
  this class of silent drift fails loudly if reintroduced. No cascade-reach or
  golden-count change.
- **`charter activate --cascade` now follows a `requires`/`suggests` edge an org
  pack authors in its canonical `drg/fragment.yaml`, and `pack validate` no longer
  contradicts the runtime about whether that fragment is read (`#3572`, `#3573`).**
  Before, those fragment edges were parsed only by the diagnostic path (`doctor
  doctrine` / `charter list`) and were never bridged into the graph cascade walks —
  which read root-level `*.graph.yaml` only — so activating an artifact silently
  cascaded nothing for org-authored fragment dependencies, even though diagnostics
  showed the edge. The companion `drg_root_graph_missing` validator globbed
  `*.graph.yaml` and never flagged a `fragment.yaml`-only pack, so `pack validate`
  exited 0 on the same gap. Now `load_validated_graph` folds org fragments through
  the existing three-layer merge (reusing its endpoint-resolution and edge
  de-duplication — no second code path), so a fragment `requires` edge cascades;
  the graphless-pack warning fires only when a pack ships **neither** a root graph
  **nor** a `drg/fragment.yaml`; and the validator finding is reconciled in the
  same change, so `pack validate` and the runtime tell one story. The diagnostic
  path is unchanged (the bridge adds a consumer), and build-time callers that pass
  no org fragments are unaffected.

- **`charter activate --cascade` now follows an org-pack dependency edge no
  matter which pack in the chain declares it, and activating from an org pack
  that ships no dependency graph no longer crashes the command (`#3534`; closes
  `#3527`).** Before, cascade activation, `charter context --json`, and dossier
  rebaseline each saw only the first configured org pack — a `requires`/`suggests`
  edge into or out of any second-or-later pack was silently ignored, so
  `--cascade` under-activated whenever doctrine lived across more than one org
  pack. Now the full declaration-ordered org-pack chain is threaded through all
  three, so an edge cascades regardless of which pack authored it. As part of
  landing, activating a directive or profile from an org pack that carries
  doctrine artifacts but no root-level DRG graph now degrades that pack to "no
  DRG layer" and activates normally, instead of aborting with `DRGLoadError: No
  DRG graph files found` — each configured pack is handled on its own, so one
  graphless pack no longer takes a healthy sibling down with it.

- **A command run from a linked lane worktree no longer silently acts on the
  primary checkout: root/workspace resolution is now honest under worktrees and
  clones, and the review-verdict CLI path is unified across both surfaces
  (`#3129` umbrella; Epics `#2624`/`#3549`/`#3044`).** A family of commands keyed
  off the ambient invoking location (`find_repo_root`/`locate_project_root`) and
  re-anchored a foreign lane worktree to the primary — producing silent
  cross-checkout writes and false-green guards. A single checkout-identity guard
  (`core/checkout_identity.py`) now distinguishes an owned invocation from a
  foreign lane worktree (parsing `.git` directly, carrying read/write intent so
  the deliberate primary-read anchors from `#2320`/`#3328` are preserved), and
  in-scope commands adopt a fail-closed refusal (`#3128`) that names the target
  checkout instead of redirecting: `intake` (`#3540`), `doctor tool-surfaces
  --fix` (`#2613`), `doctor mission-state` (`#3051`/`#3541`), `migrate
  backfill-runtime-state` (`#3049`), `setup-plan` branch-match (`#3124`), and the
  `find_repo_root` nested-clone boundary (`#2610`). On the verdict seam,
  `_parse_review_result_json` and the `for_review` commit-gate are hoisted to a
  shared, topology-aware leaf that **both** `agent status emit` and
  `orchestrator-api transition` now enforce identically — on real lane commit
  state, not a topology guess — closing a gap where a work package with no
  commit on its lane could reach `for_review` (and onward to `done`) through
  `emit` alone (`#3547`/`#1734`); `agent status emit` gains `--review-result-json`
  so a work package can be walked to `done` through `emit` alone with a
  structured verdict, and its misleading `--help` example is corrected. `review_result` is registered in the `status_event_row` audit shape
  with a value-equality snapshot round-trip (`#3543`/`#3461`). The
  standalone-clone re-anchor described in the triggering issues was verified a
  phantom (clones already resolve to self); the real, decidable defect is the
  linked-worktree/nested-clone invoking location, and each slice ships an
  issue-pinned red-first regression.
- **Rejecting a work package no longer costs a wasted cycle: the feedback-file
  path `agent action review` prints in its rejection command is now one
  `move-task` will actually accept (`#3554`; closes `#3430`).** Before, the
  review prompt told the reviewer to write feedback to
  `tasks/<wp>/review-cycle-N.md` and then pass that same file to `move-task
  --review-feedback-file` — but inside the WP's own directory that exact
  filename is the tool-authored verdict artifact, which the provenance guard
  refuses as a feedback source. So the rejection command printed verbatim always
  failed, and the reviewer only discovered it after burning a cycle. The
  advertised path is now `tasks/<wp>/review-feedback-N.md` — still committed in
  the WP's own in-repo directory — and the name is owned in `review/cycle.py`
  beside the guard that decides what is acceptable, so the printed path and the
  accepted path cannot drift apart again.

- **The two `kitty-specs/` lane guards no longer disagree about a bulk-edit
  mission's own occurrence map, so it can be kept current from the implementing
  lane without a manual unwind (`#2980`).** The pre-commit ownership guard warned
  (and let the commit through) while `move-task` blocked the later transition,
  so `kitty-specs/<mission>/occurrence_map.yaml` — which DIRECTIVE_035 requires
  the lane to update as the sweep proceeds — tripped the gate after the work was
  committed. The exception is now expressed once (`is_occurrence_map_path` in
  `core.constants`) and honored by both guards: the map is permitted on the lane
  at both, while every other `kitty-specs/` path stays governed (a sibling
  `spec.md` on the lane is still blocked). The commit-guard `mode` semantics for
  non-exception paths are unchanged.

- **The lane "no kitty-specs on lane branches" `move-task` guard no longer
  false-positives on inherited planning artifacts in `coord` topology, so lane
  transitions stop demanding `--force` on every step (`#3271`; closes `#2274`).**
  The guard is a two-pass content delta (the shipped `#2274`/FR-007 fix), but
  both passes keyed off the lane's coordination/mission base ref, whose
  merge-base predates the `kitty-specs/**` a lane legitimately holds — prior
  missions' committed artifacts inherited from the base, plus this mission's own
  planning artifacts merged in via the recorded planning commit (ADR
  `2026-07-29-1` / `#2993`). Both are ancestors of the planning branch but not of
  the coord base, so they surfaced as lane-introduced contamination and the
  guard's own "clean the branch" remedy would have deleted other missions'
  artifacts — leaving `--force`, documented as "not recommended", as the only
  safe path. The delta is now measured against the planning branch
  (`planning_base_branch`, else the mission's `target_branch`), falling back to
  the lane base ref only for legacy/flat missions without `meta.json`. The
  sibling branch-currency and implementation-commit gates keep the coordination
  ref, which is correct for them.

- **Three architectural-gate tolls that only ever fired in CI, on legitimate
  additive change, are gone (mission `frozen-baseline-toll-reduction`; closes
  `#2853`).** For a developer working in this repo: editing the body of an
  allowlisted still-dead symbol no longer forces a hand-edited "rehashed WPxx"
  baseline — a new fail-closed helper
  (`tests/architectural/_refresh_dead_symbol_hashes.py`) refreshes the
  `body_hash` for you and is structurally incapable of admitting a _new_ dead
  symbol (it iterates the existing allowlist only and refuses on an
  unrecoverable or ambiguous `module_path`, proven by a non-fakeable
  regression). Adding a migration no longer needs a baseline bump: the
  `category_1_auto_discovered_migrations` count now derives from the frozenset
  authority in both loop arms, so the 105→107 file drift that a hard-pinned
  count would red on passes clean. And a legitimate new skip no longer
  hard-fails CI — `skip_marker_blocks` growth is now reviewable-with-teeth
  (asserted via `record_property`, with the mandatory co-located skip-reason
  line as the review signal) instead of a wall. Also drained the inert
  `test_no_dead_symbols` baseline key (closing a silent re-entry hole) and
  fast-marked the two sub-second gates for local pre-push runs. Every
  load-bearing gate is untouched — P0-security boundaries, still-shrinking
  burn-downs, zero-pins, and change-detectors all stay frozen behind the C-001
  do-not-touch fence; 108 gates green, ruff + mypy `--strict` clean. Test
  infrastructure only, no runtime or user-facing change (no version bump).
- **`finalize-tasks` no longer rejects a `planning_artifact` work package that
  owns its `kitty-specs/` deliverables, so a decision checkpoint, freeze/measurement
  snapshot, or bulk-edit occurrence map can be a first-class WP (mission
  `planning-artifact-kitty-specs-ownership`; closes `#3222` and its repro `#2643`).**
  The ownership model already blessed `kitty-specs/` ownership for
  `planning_artifact` (`ownership.validation._PLANNING_PREFIXES`,
  `validate_execution_mode_consistency`) and the lane layer already routes such
  WPs to the repo-root planning lane — only the `finalize-tasks` ban disagreed,
  rejecting any `kitty-specs/` owned file unconditionally (a later over-reach whose
  own rationale was scoped to `code_change` lane branches). The ban is now
  execution-mode-aware: it exempts a `planning_artifact` WP whose `owned_files`
  are **all** confined to the planning surfaces (`kitty-specs/`, `docs/`), and
  stays fail-closed for `code_change` and for any WP that also owns code — so a
  mislabelled planning WP cannot become a backdoor to owning `src/`. Planning-
  artifact WPs never reach a lane branch, so the lane commit-guard and move-task
  hygiene guards are unaffected.

- **A spec that writes some requirements as plain prose sentences no longer
  passes the coverage gate as if they were covered — `spec-kitty next` and
  `finalize-tasks` now block and name the uncounted ids (mission
  `bare-prose-requirements-uncounted`; closes `#3396`).** When a spec declared
  some requirements in a recognised shape (a table row, heading, bullet, or
  bold-led paragraph) and wrote others as bare sentences, the plain ones were
  silently mapped to nothing while both commands reported full coverage. Now
  `spec-kitty next` refuses to advance past the tasks boundary and
  `finalize-tasks` exits non-zero, each listing the bare-prose requirement ids;
  `map-requirements` surfaces them in its JSON (`bare_prose_requirement_ids`)
  without gating, since it registers mappings rather than advancing. The
  detector was measured against all 368 real `kitty-specs/*/spec.md` files — 1
  flagged (0.27%), zero true positives — and that figure is frozen into a
  shrink-only CI ratchet.
- **A mission whose `meta.json` recorded `target_branch: "main"` no longer
  wedges permanently at `finalize-tasks`, and the `--target-branch` escape
  hatch now actually rescues it (`#3482`; closes `#3466`).** `specify
  --topology single_branch` run from a checkout on `main` writes
  `target_branch: "main"`; finalize-tasks then resolved its WP-status
  bookkeeping destination from that literal field, tripped the protected-branch
  guard, and refused with `PROTECTED_BRANCH_REFUSED` — and passing
  `--target-branch <feature>` produced a byte-identical refusal still naming
  `main`, because the override never reached that consumer. There was no
  sanctioned way out (no retarget migration, hand-editing `meta.json` is
  prohibited). The override now persists into the canonical `target_branch`
  field before the commit pipeline, so every consumer converges on it and the
  mission finalizes; a failed persist is reported to `--json` callers instead
  of silently returning false.

- **`retrospect synthesize` now tells you the one thing that is actually
  wrong with a retrospective instead of burying it under ~100 errors about a
  schema the file was never meant to satisfy (`#3537`; closes `#3533`).** When
  a hand-edited retrospective had a single invalid finding category, the
  command printed a wall of Pydantic `extra_forbidden` / `Field required`
  errors describing the nested reader's schema — twice leading readers to
  believe the tool contradicted itself when one enum value was wrong. It now
  reports the generator reader's accurate one-line diagnosis (e.g.
  `not_helpful[0].category is invalid`) and appends the categories that field
  actually allows — findings and proposals draw from different sets — so the
  fix is obvious instead of a guess.

- **Writing an honest cardinality assertion in a test no longer costs you an
  annotation toll: the golden-count architectural gate
  (`tests/architectural/test_golden_count_ban.py`) stopped flagging
  dynamic-result `len(x) == N` checks (mission
  `test-friction-ratchet-remediation`; closes `#3458`).** Before, an ambiguous
  `len(result) == 3` over a runtime-computed collection defaulted to `convert`,
  so authors had to add `# golden-count: cardinality-is-contract` just to quiet
  the gate — on PR #3456 that toll fired twice for zero real catches. The
  classifier now treats an ambiguous dynamic-result count as `keep`, so genuine
  cardinality asserts pass untouched. The gate's real job is preserved:
  enumerable-domain golden counts like `len(Lane) == 10`, which silently drift
  when the domain grows, still convert. Companion guard added in the same slice:
  a new CT7 recurrence check (`test_ratchet_positional_anchor_ban.py`) bans
  reintroducing raw `("file.py", <int>)` 2-tuple ratchet keys in
  ratchet-substrate-importing seed containers, so the file:line-drift friction
  engine cannot regrow. Dev-facing only — no runtime or user-visible behaviour
  changes. (Also folds 12 dangling references to the retired
  `test_bridge_compat_surface.py` across 9 files — campsite cleanup of the
  already-landed #3285 deletion; refs `#2853`, `#3285`, `#2633`.)
- **A misspelled key in an `expected-artifacts.yaml` completeness manifest was
  silently discarded — the requirement simply vanished while the manifest still
  loaded "successfully" — and the shipped manifests disagreed with the guards
  that actually enforce completeness in eight places, while the `plan` mission
  type had no manifest at all (`#3413`; closes `#3388`).** Before, a typo'd or
  unrecognized key was dropped without a word, so a manifest could quietly
  describe a completeness contract different from the one the runtime enforced.
  Now `ExpectedArtifactSpec` and `ExpectedArtifactManifest` reject unknown keys
  (`extra="forbid"`) and the loader raises on a schema-invalid manifest instead
  of swallowing it; the three shipped `research`/`documentation`/`software-dev`
  manifests were reconciled to match their guards exactly; `plan` gained an
  (explicitly descriptive) manifest; and a cross-cutting parity test now catches
  the next manifest-vs-guard drift. The schema failure is also actionable and
  consistent: it raises a distinguishable `ManifestSchemaError` that names the
  offending manifest file, surfaced the same way across `spec-kitty reconcile`,
  the background dossier sync (a clear warning in the sync result, not a
  swallowed stack trace), and manifest-version resolution — and it now covers
  org-authored manifests too, not just the built-in ones (`#3542`). A genuine
  internal indexing error is no longer misreported as "fix your manifest". This
  covers _schema_ violations; a YAML-_syntax_-broken manifest still degrades
  silently upstream (tracked in `#3412`).

- **A mission running under a non–software-dev workflow no longer gets blocked
  by a guard about objects its workflow does not have — for example a `plan`
  mission's `review` step demanding "Not all work packages are approved or done"
  when a `plan` mission has no work packages at all (mission
  `mission-type-guard-registry`; `#3402`, `#3386`).** Before, runtime guard
  dispatch branched explicitly on the `research` and `documentation` mission
  families and then silently fell through to the software-dev guard table for
  everything else — including `plan` and any unregistered mission type — so a
  mission could be held back by a guard about artifacts it can never possess,
  with nothing explaining why. Now guard dispatch is an explicit registry keyed
  by mission family: `plan` has its own guard table authored from its real state
  machine, and an unregistered family fails loudly on the legacy path and
  degrades to an explicit, logged neutral result on the composed extension path
  — instead of inheriting the wrong rules by accident.

- **An organisation doctrine pack you registered, validated, and activated
  delivered none of its step contracts, artifact requirements, or graph nodes to
  `spec-kitty` at runtime — it does now (`#3520`; closes `#3516`).** Before, the
  runtime consumers (the step-contract executor and its review gate bindings, the
  mission-type governance profile, runtime dispatch, and mission-load validation)
  all resolved doctrine from the built-in pack plus the project tier only — they
  had the org-tier parameter but the callers never passed it, so an org pack was
  silently inert past activation. Now a shared `resolve_org_dirs` helper threads
  the org tier through each of them; an org `expected-artifacts.yaml` overrides the
  governance artifact slot **and** the dossier completeness index (so an
  org-mandated artifact is actually enforced by the missing-artifact detector); and
  a configured-but-broken org pack warns (a dropped path or a malformed manifest)
  instead of failing silently. **A chain of multiple org packs now works too**
  (`#3525`): before, the DRG graph merged only the first org pack, so a second
  pack's step contracts loaded but their `delegates_to`/graph edges silently did
  not resolve — the runtime now merges the full declared chain in order (later
  pack wins on collision, matching the doctrine overlay), and a malformed pack in
  the chain is dropped on its own without erasing the others. Projects with no org
  pack are unaffected — every path is byte-identical without one.

- **The `SPEC_KITTY_HOME` pin census (`arch-adversarial (arch_shard_3)`) was red
  on main because a legitimate new isolation pin (`#3497`) landed after the R1a
  freeze, and the "shrink-only" ratchet — as landed — could not actually shrink
  (`#3509`, `#3121`).** The acute red is fixed by the design-sanctioned owner
  adoption (the drifting test requests the exempt `canonical_home` fixture and
  drops its own `setenv`), with no edit to any frozen artefact. Beyond that, R1b's
  tombstone burn-down is now wired end to end: `t023` subtracts the tombstoned
  set from the anchor, and the production regeneration command
  (`_home_pin_scan.render_baseline`) emits tombstones from a new auditable
  manifest (`tests/architectural/census/spec_kitty_home_pin_tombstones.yaml`) and
  freezes the key-set hash over `census ∪ tombstones`. Regeneration fails closed
  if a tombstoned member's pin is still in the tree, and the ratchet still bites
  (a spurious pin reds; a tombstone over a live pin reds). On that seam the
  provable class was converged onto the canonical owner — census `40 → 26` — with
  the ~23 genuinely-different seams documented out of scope (`#3121`'s confirmed
  thesis: a name collision, not a duplicated seam). The subsystem is a no-op while
  the manifest is empty (committed artefacts byte-identical). The same convergence
  also greens a second, separate gate — limb (g) of the §0.9 `_home_pin_gate`
  verdict oracle (`arch-adversarial (arch_shard_2)`), which recomputes the
  published end-SHA sites against the tree — by teaching it the same tombstone
  term: a converged member's site is excused only when it is in the manifest, and
  the anti-vacuity floor now counts keys that recompute _live_ so the gate can't be
  bought off by tombstoning the population away.

- **Machines that never ran the layout migration silently captured zero sync
  events while reporting success — now they capture for real (`#3425`;
  `#3497`).** Before, an un-migrated machine defaulted to a legacy capture
  layout where live event/body writes were refused deep in the stack and
  swallowed — a **silent zero-capture** that never surfaced to the operator. A
  `#3293` regression compounded this by also refusing authenticated hosts
  entirely. Now a fresh root resolves to project-only capture _before_ any
  legacy persist; a legacy-with-data root auto-migrates through the canonical
  `migrate_journal`/`project_store_migration` engines under a deterministic,
  crash-safe migration id (re-entry never bricks the root); the live emit path
  completes its cutover via a resolve-before-unit-of-work seam so both emitter
  swallow sites are observable instead of silent (never-raises contract kept
  intact); and credential parsing is restored as a pure auth signal (never a
  physical-store selector), so an already-authenticated host stops being
  refused.
- **`spec-kitty next`/`implement` no longer block on a fully-absent or legacy
  `charter.md`-only charter — both are now advisory, matching `specify`/`plan`'s
  existing tolerance (`#3498`).** The shared preflight hook
  (`run_preflight_or_abort` in `charter_runtime/preflight/hook.py`) never
  forwarded `allow_missing_charter=True` to the runner, so a brand-new project
  with no `.kittify/charter/` contents at all, or a pre-inversion project
  carrying only `.kittify/charter/charter.md` (`charter.yaml` absent, #2831's
  shape), hard-blocked `next`/`implement` even though the dashboard already
  tolerated both states. `run_charter_preflight()`
  (`charter_runtime/preflight/runner.py`) gains a new `_is_legacy_charter_bundle`
  wording selector and a distinct, more detailed warning constant for the
  legacy-bundle case. Canonical layer state alone decides the exemption:
  source and synced bundle must be `missing`, and synthesized DRG must be
  `missing` or `built_in_only`; display-only `charter.md` only selects warning
  copy after that decision. Stale, invalid, or other partial residue therefore
  keeps blocking even when `charter.md` exists. Advancing/query and human/JSON
  `next` modes plus `implement` emit the advisory to stderr without polluting
  JSON stdout; dashboard persists/renders it. The canonical `CHARTER_MD` import
  stays lazy so `next` does not pull the heavyweight charter graph at startup.
  The legacy warning
  names the executable migration command explicitly:
  `spec-kitty charter generate --no-from-interview`.
- **A reviewer running a different agent profile than the implementer can now
  claim a completed work package for review — the false "WP already claimed for
  review by `<implementer>`" refusal is gone (`#3455`).** Before, claiming a WP
  for review (`for_review → in_review`) compared the claim holder's identity,
  which at `for_review` is structurally the _implementer_ — so any cross-profile
  reviewer (e.g. `reviewer-renata` reviewing `python-pedro`'s work) was rejected
  as a self-review collision, and the block surfaced on the status aggregate
  seam rather than the `move-task` command. Now the `for_review → in_review` edge
  is allow-only, and a genuine reviewer-vs-reviewer collision is decided by a
  single pure predicate at the `in_review` re-claim site (a real second reviewer
  is still blocked, and the message names the holder). Role is read from the
  reduced status slot, never by splitting the compact actor string (`#2861`).

- **Coord/primary partition-authority residuals: out-of-loop callers now resolve
  the correct partition surface, so coordination-topology missions stop deadlocking
  and mis-reporting (mission `partition-authority-residuals-01M021K9`; epics `#2160`
  / `#2720`).** Under coordination topology a cluster of out-of-loop and
  cross-function callers still read PRIMARY-partition artifacts off the `-coord`
  husk, or wrote lifecycle evidence to the wrong partition — degrading silently or
  **deadlocking `spec-kitty merge`**. Eleven fixes, each a caller reroute through
  the canonical `mission_runtime.artifacts` placement seam (STATUS reads stay on
  COORD): the coord **merge deadlock** is gone — the review-override write now lands
  on the surface the merge gate reads, and `spec-kitty merge` gains a
  `--skip-review-artifact-check`/`--note` escape hatch that records the bypass as
  durable override evidence (`#2959`); merge risk/dependency gates and the bulk-edit
  diff base stop silently SKIPping / seeing an empty graph on coord missions
  (`#3439`); the review handoff renders true per-WP lanes instead of a blanket stale
  `planned` (`#2698`); `move-task` commits its post-transition annotation atomically,
  leaving a clean status tree (`#2939`); the 4th safe-commit target resolves through
  the shared degrade helper with refusal-parity preserved (`#2966`); and
  `finalize-tasks` versions `wps.yaml` so a finalized checkpoint reproduces its own
  state (`#2937`). Diagnostic-output fidelity (`#2720`): `check-prerequisites`
  sources its inventory from canonical mission writer metadata (`#2692`); mission
  doctors validate `meta.json` against the writer schema — killing false
  `UNKNOWN_SHAPE` findings — and `doctor coordination` gains `--mission` scoping
  (`#2696`); `retrospect summary` discovers missions under the canonical
  `kitty-specs/*` root (`#2717`); `status doctor` no longer reports Healthy over
  blanked runtime attribution (`#2960`); and mission-state repair stops quarantining
  legacy `WPStatusChanged` lane transitions into a zero-WP `status.json` (`#3066`).

- **Review rejections now reach the hosted dashboard instead of being silently
  dropped by sync (`#3307` P0; `#3444`).** Before, when a reviewer sent a work
  package back for rework — any backward review-rejection move (`* → planned`,
  or `in_review → in_progress`) — the CLI stamped the status event `force=False`
  and, for `in_review → in_progress`, left off the `review_ref`. Those events
  were accepted on your machine but violated the shared `spec-kitty-events` wire
  contract the hosted ingestion endpoint enforces, so hosted sync silently
  rejected them: a rejection that looked applied locally never propagated to the
  team dashboard (in the reported case a whole batch surfaced 11+ days later as
  bulk sync failures). Root cause was two same-named `validate_transition`
  functions giving opposite answers — the emit path consulted only the
  CLI-local state machine, never the wire contract the server enforces. The
  emit-force decision now gates on **both**, so the review-rejection family
  emits `force=True` (still carrying the structured rewind rationale) and threads
  the `review_ref` on the wire, producing events the project's own vendored
  contract accepts. Reviewers are now told — at the `move-task` tool surface and
  in the review skills — that a rejection rationale (`--review-feedback-file` or
  `--note`) is mandatory, because it travels on the wire as that `review_ref`.
- **Coordination-topology missions no longer wedge lane allocation by
  committing PRIMARY planning artifacts onto the coordination branch (mission
  `write-path-integrity-01KZZD69`; `#3371` P0, `#2549`, `#3128`, `#3373`;
  advances `#2160`/`#1878`).** Before, `implement`'s planning auto-commit routed
  the whole batch verbatim to the coordination branch under coord topology, so a
  PRIMARY `lanes.json` landed on coord and the lane allocator's recorded-planning
  merge hit an add/add conflict — blocking every work-package claim on a
  PR-bound `--start-branch` + coord mission with no self-service recovery. Root
  cause was one layer deeper than the commit site: `BookkeepingTransaction.acquire`
  _unconditionally_ redirected writes to the coordination worktree, so this fix
  adds an opt-in `commit_to_primary_target` that PRIMARY planning commits use to
  land on the mission's own target branch (every status/coord caller keeps the
  default — zero regression to coord routing). A partition guard at the
  planning-commit seam now fails loud on any PRIMARY→coord / COORD→lane
  mis-route (excluding self-bookkeeping `meta.json` co-travel), closing the same
  class for `move-task --force` (`#2549`). `implement`'s lane-state **read** now
  resolves `lanes.json` from that same PRIMARY partition (via the kind-aware
  placement seam, matching its canonical `LANE_STATE` classification), so the
  read and write agree for coord-topology missions — previously the read still
  looked on the coordination surface, which broke `implement` end-to-end.
  Separately, mission-mutating
  `implement`/`review` now **fail closed** when invoked from a checkout the
  mission does not own (`#3128`): a `write_intent`-gated `CheckoutIdentityError`
  at the real workspace chokepoint (`workspace/context.py::resolve_workspace_for_wp`)
  refuses foreign-checkout writes without ever refusing reads or planning. The
  four re-implementations of the git-common-dir/toplevel probe are unified behind
  one primitive (`#3373`), and a static `tests/architectural/` gate plus a
  cross-partition repo scan keep the P0 class from silently regressing. The
  frontmatter/upgrade-wedge slice (`#3372`) and `#2702` were confirmed already
  closed (by mission `#3383` and prior work) and left out of scope.
- **Activating a charter directive no longer silently drops every org-pack
  artifact from the doctrine graph (mission `org-activation-scan-dirs-01KZY1PT`;
  `#3399`, closes `#3385`).** Before, the charter activation allow-list scanned
  org packs at a phantom `<root>/<plural>/built-in` layout that no org pack
  actually uses, while the live doctrine loader reads the flat `<root>/<plural>`
  layout. The two disagreed silently: the moment an operator ran
  `charter activate directive <stem>`, every org-pack URN failed to resolve and
  was dropped from the filtered graph with no error — so a project's own
  directives, tactics, and profiles vanished from governance the first time
  anyone activated a single artifact. Now the activation scan reads the same
  flat layout the loader does (plus the legacy nested layout additively, with
  the flat entry winning a same-name collision), so activating one artifact
  leaves the rest of the org pack intact.

- **The `researcher-robbie` agent profile no longer introduces itself under the
  wrong name (`#3377`).** Before, the profile's `purpose` and
  initialization-declaration prose still read "Researcher Rosa" — a leftover the
  profile rename missed — so any agent that loaded `researcher-robbie` and
  followed its initialization declaration announced itself as "Researcher Rosa",
  even though the profile's own `name` field, its docs page, and every sibling
  profile said "Researcher Robbie". Now the prose matches the profile's own
  `name`, and a parametrized test asserts every shipped profile's self-identity
  prose equals its `name` field, so this class of identity drift cannot silently
  recur.

- **`sync import-history` now imports legacy work packages that carry retired
  frontmatter fields, instead of skipping them (mission
  `first-sync-preflight-01KZZ9Q1` FR-011; `#3406`).** The import scan read WP
  frontmatter with the strict authoring model (`extra="forbid"`), so a
  historical WP carrying a field the current schema no longer knows (e.g.
  `estimated_lines`) raised a validation error, was logged "unreadable", and was
  degraded to a bare back-fill — losing its real title and dependencies. The
  import path now uses a lenient reader that drops unrecognised legacy keys
  while still validating known fields, so genuinely-malformed frontmatter is
  still skipped fail-loud. Authoring keeps the strict typo guard unchanged.

- **`sync status` now flags an unreachable sync server and how to repoint it,
  instead of reporting a bare "Unexpected status" (mission
  `first-sync-preflight-01KZZ9Q1` FR-003; `#3406`).** A configured server that
  answers with a gateway-class status (`502`/`503`/`504`) — the signature of a
  decommissioned platform env or a torn-down preview, which is exactly how a
  first sync against a stale `*.platformsh.site` URL stranded — was folded into
  the generic "Unexpected HTTP 502" branch, giving the operator no signal that
  the URL itself might be the fault. The health probe now reports these as
  **Server unavailable**, reassuring that queued events are retained and will
  drain on recovery (consistent with the offline queue's transient-retry
  handling), and — for the decommissioned case — naming the URL and the exact
  recovery (`spec-kitty sync server <url>` then `auth login --force`).
- **`auth login` now resolves the server the same way `sync` does — env over
  `[sync].server_url` over the documented default — instead of the env-only
  accessor that errored when only `spec-kitty sync server` had been set
  (`#3406`, FR-005).** Before, a user who set their server via `sync server`
  still hit "SPEC_KITTY_SAAS_URL environment variable is not set" on login, so a
  token could only be minted against one server while sync targeted another. It
  still refuses (with a remedy naming both `SPEC_KITTY_SAAS_URL` and
  `sync server`) when neither is set, rather than silently defaulting to the dev
  URL. One of the ten-gate first-sync gauntlet fixes.

- **`sync doctor` no longer reports "Sync is healthy" while the server probe
  says otherwise (mission `first-sync-preflight-01KZZ9Q1` FR-002; `#3406`).**
  The health summary only escalated a server verdict of `Unreachable`/`Error`;
  a `Permission denied` (403), gateway-down (5xx), or unexpected-status verdict
  printed a coloured row in the table but never entered the issue list, so the
  doctor still declared everything healthy while the live drain was blocked —
  the false-green that hid a broken first sync. Every non-healthy server verdict
  (anything but `Connected`/`Disabled`, excluding the auth states the
  auth/session block already owns) now reaches the summary with the probe's own
  remediation note.
- **Mission `create` and `next` now run correctly from a caller-owned linked
  git worktree, and each worktree's mission state stays isolated (mission
  `worktree-owned-root-3328-01KZRG01`; `#3346`, closes `#3328`).** Before,
  invoking `create` or `next` from an explicit linked checkout followed the
  worktree's `.git` pointer back to the primary checkout and tried to drive the
  mission there — failing with `START_BRANCH_FAILED` when that branch was
  already checked out, and risking one worktree reading or writing another
  worktree's mission state. Now the invoking checkout root is validated with
  fail-closed git-topology ownership checks and threaded through creation,
  resolution, `next`, runtime state, refs, and commits, so two linked worktrees
  can create and advance distinct missions concurrently with no
  cross-contamination while the primary checkout is left untouched. Managed
  Spec Kitty coordination and lane worktrees remain refused.

- **The ADR inventory freshener now targets the canonical `3.x` era index
  instead of the redirect README, so newly added ADRs are actually indexed
  (`#3346`, closes `#3345`).** Before, the freshener pointed at the redirect
  README and left the canonical era index stale, so a new ADR could pass docs
  freshness without appearing in the index maintainers browse. Now it writes the
  canonical era index directly.

- **Direct sync ingress no longer drifts to a shared/primary team when the
  session read transiently returns None (`#738`/spec-kitty-saas `#911`).** The
  fan-out handler resolved the producer scope as
  `read_queue_scope_from_session() or read_queue_scope_from_credentials()`. The
  session path is fail-closed to the user's Private Teamspace, but the credentials
  fallback returns whatever `team_slug` the credentials TOML last stored (often a
  shared/primary team, e.g. `stijn` rather than `stijn-private`). During a token
  refresh or a rehydrate miss the session read returns None and ingress silently
  rerouted to that team — forking the producer-scoped journal (`journal-<scope>.db`)
  and materializing the project under the wrong team server-side, so the
  private→shared share could never find it (the Kitty Prime "I can't see the
  team's work" symptom). Ingress is now session-only: it honours the fail-closed
  contract and skips queueing when the Private Teamspace can't be resolved, rather
  than attributing the event to the wrong scope. The credentials reader stays for
  the diagnostic call sites (e.g. `sync doctor`/preflight, which compare the two
  scopes to _detect_ exactly this drift).

- **Root README guide links point at the post-IA `tutorials/` and `how-to/`
  paths.** Fixes GitHub 404s from stale flat `docs/guides/*.md` hrefs after the
  guides subdivision (e.g. Your First Mission).

- **Four operator-visible read/write-consistency defects, where a step trusted a
  partial, pre-merge, or recomputed-from-scratch view of persisted state, are
  fixed (mission `mission-a-p0-consistency`; `#3320`, `#3231`, `#3334`, `#3311`).**
  Concretely: `retrospect create --update` reported and emitted the _pre-merge_
  record — the counts, JSON `findings_status`, and `RetrospectiveCaptured` event
  disagreed with what was written to disk; now they read the persisted record back
  (`#3320`). A leftover `finalize-tasks` scaffold placeholder blocked acceptance
  for a mission whose real criteria all passed; the verdict now exempts _only_ the
  empty placeholder row, so a real still-pending criterion still blocks as before
  (`#3231`). A failed `spec-kitty upgrade` stripped `schema_version` from
  `meta.json` and wedged the project as unrecoverable `LEGACY`; project metadata
  now round-trips the stamp so a failed migration stays recoverable (`#3334`).
  Re-running `finalize-tasks` after implementation had begun clobbered the recorded
  `planning_commit_sha`; it now preserves provenance once any work package has left
  `planned` (`#3311`).

- **Six upgrade-wedge failures, where a stuck migration left no self-service way
  out, are fixed (`#3383`; `#3335`, `#3336`, `#3337`, `#3338`, `#3339`,
  `#3372`).** Concretely: a failed `runtime_state_backfill` aborted mid-walk with
  no record of what it had already written, leaving the operator unable to tell
  how far the migration got; it now enumerates every mission and file already
  persisted before it stopped (`#3335`). `spec-kitty upgrade --dry-run` (and
  `--json`) could report nothing pending while the real run went on to apply many
  migrations, because the preview computed pending work through a different path
  than the real run; the preview now drives off the same migration selector, so it
  reports the true pending set (`#3336`). `agent mission create --json` returned a
  bare `CHARTER_PACK_CONFIG_INVALID` error code with no fix steps, discarding the
  human-readable remediation text a plain-text run would have shown; the `--json`
  envelope now carries the remediation body alongside the code (`#3337`). The
  `migrate backfill-runtime-state ... --dry-run` diagnostic a failed migration
  told operators to run was itself blocked behind that same failed migration — a
  catch-22 with no way out; the `--dry-run` form is now ungated (the mutating form
  stays blocked) (`#3338`). A failed `mission create` left the operator's checkout
  switched onto the coordination branch it had just minted, and left that orphan
  branch behind; it now restores the original checkout and deletes the branch it
  created (`#3339`). The review cycle could append a duplicate `review_feedback`
  frontmatter key, producing invalid YAML that later wedged upgrades trying to
  parse it; the writer that appended on a miss is retired (it now fails closed),
  duplicate-key artifacts are detected and can be repaired non-destructively, and
  the frontmatter reader names every offending key (`#3372`).

### 💥 Breaking Changes

- **`pack validate` (and `doctrine org validate`) now fails (exit code `1`) for
  three previously-passing org-pack shapes (mission
  `org-pack-authoring-diagnostics-01KZY463`; `#3387`).** All three close a
  silent-success authoring gap where a pack passed validation cleanly and only
  failed — or silently misbehaved — at runtime or on adoption. Concretely: a
  merge-time-skipped agent profile (a profile that individually passes schema
  validation but fails to field-merge onto a same-ID built-in profile) now
  surfaces as a `profile_skipped` error, sourced from
  `AgentProfileRepository.skipped_profiles()` rather than requiring a separate
  `spec-kitty doctor doctrine --json` invocation. A nested
  `assets/<pack>/x.asset.yaml` manifest with a schema violation is now scanned
  recursively, matching what `AssetRepository` loads at runtime (previously
  invisible to validation). DRG content living only under `drg/*.graph.yaml`
  fragments with no pack-root `*.graph.yaml` now produces a
  `drg_root_graph_missing` error — the runtime
  (`src/charter/_drg_helpers.py:load_validated_graph`) reads only the pack
  root, never `drg/` fragments, so this shape previously validated cleanly and
  then silently zeroed the pack's DRG content on adoption (per sibling mission
  `org-pack-drg-root-graph-guard-01KZY0QT`, `#3384`). `validate_pack()` gains a
  keyword-only `check_drg_root: bool = True` parameter for the new DRG check;
  `pack_assembler.py`'s internal round-trip validation of its own
  drg/-fragments-only output passes `check_drg_root=False` unconditionally (a
  structural carve-out — the assembler never writes a pack-root graph).

## [3.2.6rc1] - 2026-08-12

> [!WARNING]
> **`3.2.6rc1` is a Release Candidate — an internal, delta build published for validation, NOT an official `3.2.6` release.** It ships as a GitHub _prerelease_ and to PyPI as a PEP 440 prerelease, so ordinary installers skip it unless you explicitly opt in with `--pre`. Do **not** use it for production or general rollout. The last official release remains `v3.2.5`; when `3.2.6` is finalized its changelog section supersedes this one.

**Install for testing (opt-in only):**

```bash
pipx install --pre spec-kitty-cli==3.2.6rc1
# or, inside an existing environment:
pip install --pre spec-kitty-cli==3.2.6rc1
```

**Highlights since `v3.2.5`** — the operator-facing changes worth exercising in this candidate:

- **Breaking — built-in doctrine content relocated to `packs/built-in/` with no compatibility shim** (mission `relocate-builtin-doctrine-packs`). Repoint any reference that still targets the old `src/doctrine/<kind>/built-in/` path.
- **Breaking — local `beads`/`fp` tracker sync now requires a recorded egress decision** (mission `tracker-egress-refusal-3108`). A binding that never recorded hosted-sync consent stops syncing on upgrade until you record `tracker.egress: permitted` or `sync.enabled: true`.
- **Breaking — the `rtk-search-tooling` toolguide is removed**, and the `3.2.6_retire_rtk_search_tooling` upgrade migration strips it from projects that had it activated (it runs automatically on `spec-kitty upgrade` and is safe to re-run).
- **Breaking — org packs with an unrecognised agent-profile or DRG key now fail to load** (mission `doctrine-silence-guards`). Run `spec-kitty doctor doctrine --json` and check `skipped_profiles` before you upgrade.
- **`charter synthesize` is now non-destructive** — it preserves backed governance content by default, with `--prune` as the explicit opt-in and `--dry-run` to preview (mission `charter-synthesize-reconciliation`; `#3270` P0, folds `#2777` / `#3052`). The `implement` / `next` boundary no longer hard-blocks until you resynthesize.
- **Approving a work package after a rejection now sticks with no override flag required** (mission `review-verdict-write-integrity`; `#3044`) — the reject → fix → approve cycle no longer forces `--skip-review-artifact-check`.
- **Timestamps Spec Kitty writes into your project are now correct aware-UTC** instead of local time mislabelled as UTC (mission `kernel-clock-single-door`; `#3305`, closes `#3289`).
- **CLI UX: shell autocompletion, a `-h` short-help alias, and alphabetical command listing** (`#2232`, `#2234`, `#2235`) — additive, with no behavior change to existing commands.

The complete, factual list of changes for this candidate follows in the entries below.

### ✨ Added

- **Multi-Agent Parallel Development and Orchestrator Quickstart tutorials now open
  with illustrated Mission Kitty splashes (`#3331`).** Each page adds a decorative hero and
  a one-line caption that points to the authoritative workflow steps in the prose
  below, matching the pattern introduced in `#3276`.
- **Governed Charter Workflow, Claude Code Integration, and Claude Code Workflow
  tutorials now open with illustrated Mission Kitty splashes, plus TIP cross-links
  and hub `related:` edges (`#3333`).** Each page adds a decorative hero and a one-line
  caption; the Charter tour points at the governance how-tos, and the two Claude
  Code tutorials link each other for slash-command vs CLI/dashboard paths.
- **Three #3276 Mission Kitty heroes are regenerated as decorative-only splashes
  (missions overview, your first mission, when-to-use-modes alternate art) (`#3341`).**
  Replaces caption-mitigated board labels with abstract art; each PNG compressed
  to ≤500 KB. Memphis, four-paths, and corporate-comics assets on when-to-use-modes
  are unchanged.
- **The DRG now carries a whole-graph, action-only reachability companion guard, and six genuine residual
  orphans are wired into the graph (mission `drg-reachability-metric-wiring-01KZS5VR`; `#3009` point 3,
  `#1923`).** `TestReachabilityCompanionGuard` in `tests/doctrine/drg/test_reachability.py` asserts every
  activatable-kind node reachable from **neither** the action channel nor the profile channel's
  `{requires, specializes_from, suggests}` web is correctly partitioned into "both-channel dead" vs
  "profile-delivered" — live totality/disjointness assertions against the graph measured at test time, not
  an exact-membership pin (the ever-growing frozenset-literal pin was softened out during PR #3342 landing,
  consistent with mission `assertive-test-suite-sanitation-01KZME3P`'s "test plausible graph behavior, not
  exact ever-growing membership"). A fixed anti-gaming gate (`TestActionUnreachableShippedLedgerCoverage`)
  independently proves the thirteen URNs this mission wires are genuinely action-reachable and named in a
  wiring-table ledger row, so a node with outbound edges but no inbound path still cannot pass silently. Six
  traced inbound edges (`procedure:refactoring → DISCIPLINED_REFACTORING`, `DIRECTIVE_024`/`DIRECTIVE_025` →
  `RECONCILE_CHANGE_SCOPE_TENSIONS`, `DIRECTIVE_030` → `USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`,
  `researcher-robbie → spike-timebox-policy`, `lexical-larry → glossary-maintenance-workflow`,
  `minutes-maker-mahad → meeting-minutes-pipeline`) move the action-only whole-graph residual **88 → 75** and
  the both-channel-dead subset **38 → 34** (descriptive measurements at time of wiring, not pinned
  assertions). The `#1923` DRG orphan-residual record
  (`kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`) is truth-upped
  against the wired graph: every one of the 75 residual members now carries an individual or group
  disposition, `toolguide:rtk-search-tooling` is retired (already removed from disk), and only the genuinely
  action-reachable members of the prior "6 promoted" claim are recorded as promoted.
- **Documentation pages can now declare who they are for: a canonical `audience:`
  frontmatter field, plus a Common Docs styleguide and gates, ship in the built-in
  doctrine pack (mission `common-docs-convergence`).** Each page states its
  intended reader and Divio type, and projects that activate the pack inherit the
  same Common Docs conventions — the single-root structure and audience/type
  discipline — out of the box.
- **`charter synthesize` is now non-destructive — it preserves backed governance
  content by default (mission `charter-synthesize-reconciliation`; `#3270` P0,
  folds `#2777` / `#3052`).** Previously an authoring-only charter edit forced
  operators to run `charter synthesize`, which silently deleted doctrine graph
  nodes and edges whose backing artifacts still existed on disk — and `implement`
  / `next` hard-blocked until you ran it. Now synthesize **reconciles** against
  the on-disk graph: backed content is retained and the command reports what it
  kept (exit 0); `--prune` is the explicit opt-in that removes divergent content
  and lists every deletion; `--dry-run` previews exactly what `--prune` would
  remove and writes nothing; and a non-zero refusal is reserved for genuinely
  unpreservable states (orphaned removal without `--prune`, or an unparseable
  overlay). The `implement` / `next` boundary auto-refresh now self-heals
  non-destructively and clears the stale signal so you are never trapped, and
  `charter activate` / `deactivate` go through the same preserve path. Consumer-pack
  synthesis also emits charter-relevant edges from declared interview evidence
  (`#3052`) — no more orphaned just-generated directives, and no fabricated edges.
- **`spec-kitty accept --json` now surfaces stranded-verdict advisories in a
  top-level `advisories` array (mission `verdict-seam-boundary-hardening`;
  `#3255`).** When a mission carries a review verdict that no longer has a home
  (an SC-008 "stranded verdict"), `accept --json` reports it as a structured,
  non-error advisory alongside the normal payload instead of staying silent — so
  operators and automation can see and act on it without scraping human-readable
  output.
- **Spec Kitty's own charter now activates the writing-comms & diagramming
  doctrine set - this repository only; no downstream impact (builds on `#2918` /
  `#3225`).**
  Spec Kitty now dogfoods "The Magnificent 7" writing-comms doctrine in its own
  `.kittify/charter/`: audience-oriented writing (`DIRECTIVE_047` +
  `writing-audience-catalog` + the `plain-language` and
  `professional-communications` styleguides), the documentation-structure
  styleguides (`divio-type-discipline`, `docs-accessibility`, `docs-freshness-sla`,
  `publication-authority`), C4 diagramming (`USE_C4_MODEL_TECHNIQUES`, alongside the
  already-active Mermaid/PlantUML toolguides), the communication-governance
  directives (`048` version-governance, `049` agent self-introduction, `050`
  credential-handling), the `glossary-maintenance-workflow` procedure and
  `research-citation-discipline` styleguide, and the seven writing-comms agent
  profiles (`comms-cleo`, `diagram-daisy`, `analyst-annie`, `lexical-larry`,
  `minutes-maker-mahad`, `scribe-sally`, `synthesizer-sam`). It also activates
  `RECONCILE_CHANGE_SCOPE_TENSIONS` to bridge the smallest-viable-diff / Boy Scout /
  locality-of-change tension, explained in a new `charter.md` section.
  **Scope:** this changes Spec Kitty's _own_ project governance only. The doctrine
  artifacts already ship in `packs/built-in`; projects created or upgraded by the
  CLI are unaffected and keep their own charter activations.
- **A new "When to use Spec Kitty modes" guide helps you pick the lightest path
  for the work at hand (`#3238`).**
  [`docs/guides/when-to-use-modes.md`](../guides/when-to-use-modes.md) lays out
  four entry points - skip Spec Kitty for a trivial edit, dispatch an ad-hoc
  specialist for a short task, run a bounded adversarial squad at an SDD
  checkpoint, or drive a full mission when acceptance criteria and structured
  review matter - with an illustrated overview, so you match effort to the
  change instead of paying full-mission overhead on every edit.
- **`spec-kitty charter pack apply --compile` now applies a pack and compiles
  its bundle in one step (mission `charter-pack-usage-journey`; `#3105`).**
  Previously `apply` only merged activations into `config.yaml` and left you to
  discover that a separate `charter generate` was still needed; the default
  `apply` output now names that exact next command, and `--compile` does both at
  once (inheriting `generate`'s git-worktree requirement). `charter context
  --include section:terminology-canon` / `section:code-review-checklist` also no
  longer dead-end when the section is unauthored - they resolve to an honest
  placeholder pointing you at the file to edit (`#3095`, `#3094`, `#2552`).
- **Empty/unconfigured charter now dispatches to a warned generic agent instead
  of silently applying every built-in doctrine artefact (mission
  `charter-delivery-finish-context-degod`; `#3064`).** Previously, running a
  dispatch in a repository with no charter activated silently fell back to
  "all built-ins" - the entire shipped doctrine catalogue was applied in both
  routing and the governance context injected into the prompt. Now, when
  nothing is activated (a composite check across every charter-activatable
  dimension), auto-routing resolves to a **generic agent using no charter
  doctrine** - verified across both routing **and** the governance block, so no
  directive canon leaks into the prompt - and the user gets a **clear warning**
  to activate a charter first. The `software-dev` mission type stays
  always-available, and explicitly passing `--profile <name>` still resolves the
  specialist even under an empty charter (only the no-hint auto-route path
  changes; the shared activation gate is untouched).
- **A minimal starter charter now ships as a first-class, on-demand charter
  pack (mission `charter-delivery-finish-context-degod`; `#3064`).** It ships
  as `src/charter/packs/minimal.yaml`, alongside `default.yaml`. Run
  `spec-kitty charter pack list` to see the shipped built-in packs,
  `spec-kitty charter pack path minimal` to resolve the file, or
  `spec-kitty charter pack apply minimal` to merge its small, curated
  activation set into `.kittify/config.yaml` instead of authoring one from
  scratch - it is additive by default and never silently overwrites an
  existing activation (`--force` to overwrite explicitly).
- **Profile-channel `suggests`-edge delivery is now live - the inert `#3063`
  doctrine topology actually delivers (mission `doctrine-delivery-activation`,
  fast-follow to `doctrine-delivery-reachability`).** The profile-channel
  reachability walk now follows `suggests` edges (in addition to `requires` /
  `specializes_from`) and surfaces each edge's `when` clause as the delivered
  doctrine's applicability condition - as `when`-labelled links, not eager
  bodies (respecting the context-bloat budget). Architect and implementer
  profiles now receive their linked paradigms, tactics, techniques, and
  canvases: e.g. `architect-alphonso` reaches `domain-driven-design`, the C4
  model techniques, and the REASONS-canvas guidance; implementer profiles reach
  the `DISCIPLINED_REFACTORING` refactoring tactics. Companion authoring: a C4
  `template:instantiates` edge from `action:documentation/design`, and
  refactoring code-smell `anti_pattern` nodes wired via `REJECTS` (grounded in
  each tactic's attested `problem`/`when`). The reachability pins, the delivery
  wiring table, and the forward-API dead-symbol allowlist are reconciled to the
  now-live topology, each moved count carrying a composition-ledger entry. (#3063)
- **The `asset` doctrine kind is now reachable end to end - resolve, deliver,
  and author it (mission `doctrine-delivery-reachability`).** Previously a
  shipped asset (executable logic or any blob a pack hands to a downstream repo)
  had no operator surface and no followable how-to, so the documented remedy
  "ship it as an asset" was not actually followable (#3037). Now:
  - **`spec-kitty doctrine asset list`** enumerates every resolvable asset with
    its source tier (built-in / org / project), and **`spec-kitty doctrine asset
    path <id>`** resolves one identifier to a filesystem path - exit `0` on
    success, non-zero with the id named on an unknown id or a containment
    refusal. Nothing is installed into the consumer repo; assets resolve from
    packaged data plus the project/org overlays (no auto-install). The one
    built-in asset, `common-docs-structural-lint`, resolves from any
    installation.
  - **`spec-kitty doctrine new --kind asset <name>`** scaffolds an asset with
    the same parity as `validate`, writing into the directory the resolver reads
    (`.kittify/doctrine/assets/`).
  - **The action doctrine bundle now delivers every resolved kind**, including
    procedures and assets. The delivery gate is a total function over kinds:
    activation-gated kinds deliver `activated ∩ reachable`, while assets are
    **delivered-but-not-activation-gated** (`gate = ALL`) - a reachable source
    pulls them in without an activation list. This closes the defect where
    `asset_ids = []` was the silently-conforming outcome forever.
  - **Docs**: [Create a doctrine artifact](../development/how-to/create-a-doctrine-artifact.md)
    gains an executable asset how-to (author a manifest, place the blob, resolve
    it), and [Doctrine artifact kinds](../architecture/doctrine-kinds.md) documents
    the shipped built-in asset and the three delivery categories.
- **New checks that catch a change which looks like it worked and did nothing
  (mission `doctrine-silence-guards`).** Four additions, all aimed at the same
  failure mode - a declaration that loads, validates, reports success, and then
  has no effect:
  - A **zero-producer lint** fails the build when a schema field is declared but
    no code path ever writes it. Three such fields had shipped in this
    repository, one of them inert for months behind passing tests. The findings
    that already exist are frozen as a shrink-only baseline; the list can only
    get smaller, every entry names an owner and the fix it is waiting on, and a
    test refuses to let an entry outlive the work that was meant to remove it.
  - **`scripts/generate_schemas.py --check` now runs in CI**, in the always-on
    `lint` job rather than behind a path filter, so a model change that leaves
    its generated YAML schema behind fails immediately. Seven schemas were
    already stale and are reconciled here.
  - **`spec-kitty doctor doctrine` now reports org-pack edges that point at
    nothing** (see Breaking Changes).
  - **Occurrence maps can protect a single field inside a file that is otherwise
    migrating.** The `do_not_change` classification used to accept only
    whole-file path globs, so a file containing both governed keys and keys that
    should be renamed could not be described. It now accepts a YAML field path.

- **CLI UX: shell autocompletion, a `-h` short-help alias, and alphabetical
  command listing (#2232, #2234, #2235).** Three additive quality-of-life
  improvements to the `spec-kitty` command surface, with no behavior change to
  existing commands:
  - **Shell autocompletion** is now enabled (`--install-completion` /
    `--show-completion`), with a latency-safe fast path: every TAB press serves
    command/subcommand candidates from a small committed manifest
    (`_completion_manifest.json`) instead of importing the whole command tree,
    cutting completion invocation latency from roughly 812 ms to about 76 ms. A
    drift-guard test keeps the manifest in sync with the live command tree.
  - **`-h` is accepted as an alias for `--help`** across the root command and
    every subcommand.
  - **The root `--help` command list is now sorted alphabetically**, and a bare
    `spec-kitty` invocation renders the same ordered help.
- **`spec-kitty sync import-history` materializes existing local mission history
  into the SaaS projection (#2262).** A first sync registers a remote
  project/build but leaves it with zero materialized missions - the SaaS
  materializer refuses to fabricate a work package from a status event with no
  prior create. The new command synthesizes the missing
  `MissionCreated -> WPCreated[] -> WPStatusChanged[]` prefix (INV-3) from local
  history so historical work populates the projection. `--dry-run` (default)
  runs the whole read-only pipeline and previews the stream; `--apply` attaches
  a sha256 provenance manifest, runs the offline envelope contract gate, then
  server-preflights the entire stream before uploading anything (fail-closed -
  a rejection leaves the projection untouched) and uploads in chunks.
  Deterministic event ids make re-runs idempotent (the server dedups on
  `event_id`). Buildable slices Y1-Y5 ship here; Y6/Y7/Y8 remain gated.
- **Doctrine packs can now ship supporting files to consumer repos - the first
  is a docs structural-lint that keeps a project's documentation organized
  (#2302, #2864-#2867).** A doctrine pack can now carry an arbitrary
  addressable file (a script, a blob, a `.docx`) that travels with the pack and
  resolves in a consumer repo with no access to our source tree - the new
  built-in `asset` doctrine kind, shipping its first member. That inaugural
  asset, `common-docs-structural-lint`, checks that docs land in the right
  section, that redirect stubs and frontmatter follow the house contract, and
  that retired shadow doc-trees don't reappear; it is wired into the
  `docs-freshness` CI workflow as a blocking gate and is pulled in automatically
  whenever a common-docs artifact is activated. Alongside it, a one-time
  structural-sanity sweep redistributed nine misfiled `architecture/` notes,
  retired the `plans/notes/` 1.x shadow tree, and repointed every referrer with
  zero dead links; the common-docs styleguide gains a machine-parseable
  `structural_lint_config` block (with a `redirect_stub_description_prefix`
  exemption key) as the lint's single source of truth; and the docs
  reference-rewrite helper no longer doubles a destination path (`.../x.md/x.md`)
  on a file-level move. No CLI product code (`src/specify_cli`) changed.
- **Fork packaging hooks (entry-point plugins + `DistributionProfile`).**
  Renamed / private-index forks can customize CLI package identity, upgrade
  providers (including built-in PEP 503 `SimpleIndexProvider`), remediation
  index URLs, data-freshness TTL, and the public-PyPI notifier via
  `spec_kitty.cli_package`, `spec_kitty.upgrade_provider`, and
  `spec_kitty.distribution_profile` - without overlaying `src/specify_cli/**`.
  Stock public-PyPI / `spec-kitty-cli` installs with no hooks are unchanged.
  Packager guide: [`docs/guides/fork-packaging-hooks.md`](../guides/how-to/installation/fork-packaging-hooks.md).
- **Doctrine-controlled transition gates - the `for_review` pre-review gate is now
  declared by the repo's active doctrine, not hardcoded to Spec Kitty's own repo
  shape (#2595, #2596, #2598; epic #2535 half A).** Scope resolution moves behind a
  layout-agnostic `ScopeSource` port (`GateCoverageScopeSource` preserves the
  incumbent pytest/JUnit path byte-identically; `DeclaredCommandScopeSource` runs a
  consumer's declared `review.test_command` with baseline-relative verdicts). A
  named `GATE_REGISTRY` registers the pre-review engine as the first handler; a
  versioned `gates` binding on the `mission_step_contract` review contract (with an
  inert `handler_kind` seam for future executable-asset gates) is resolved through
  charter activation and dispatched by the inverted `_mt_run_transition_gates`
  hook with deterministic aggregation and per-handler fail-open (two hard-stops
  preserved). A new built-in `mission_step_contract.graph.yaml` DRG fragment makes
  the gate fire on the source repo. Behaviour parity is enforced by a golden
  captured from the pre-refactor base. **Closes the pre-review facet of #2534** (the
  always-on `tests.architectural._gate_coverage` consumer-repo import is removed -
  a consumer never reaches it, even under erroneous activation) **and #2330** (the
  pytest-layout papercut). Half B (executable gate assets, #2599) is out of scope.

- **The pre-review test gate now works correctly for projects that use a custom
  test command, not just pytest (#2873, follow-up to #2535 half A).** When a work
  package moves to `for_review`, Spec Kitty runs the project's tests and flags any
  failure the change _newly_ introduced - comparing against a baseline captured
  before the work started. Previously the baseline side and the review side could
  run those tests two different ways, so a project configured with its own
  `review.test_command` (anything other than pytest) got unreliable results: it
  could be wrongly blocked on failures that were already there, or - worse - a
  genuinely new test failure could slip through unflagged on a clean baseline. Now
  both sides run and interpret the tests through one shared path, so the
  comparison is apples-to-apples and a new failure is reliably caught. When the
  two sides genuinely _can't_ be compared (for example, the test command was
  changed in between), the gate now says so with a clear, non-blocking warning
  (shown as `SOURCE_MISMATCH`) instead of guessing - it never silently passes and
  never hard-blocks on that case. The captured baseline is now always saved, so
  review no longer gets stuck on an uncommitted baseline file. Internally, ~450
  lines of dead, duplicated test-scoping code left over from an earlier design
  were removed.

- **WP runtime-state evicted into the append-only event log (#2684, #2093).**
  Runtime-mutable work-package state - `shell_pid`, subtask completion,
  `## Activity Log` notes, `tracker_refs`, `agent`/`assignee`, and review-cycle
  fields - is folded through a single off-axis `InnerStateChanged` event and read
  from the reduced status snapshot, so `tasks/WP##.md` stops mutating on runtime
  events (byte-stable dossier content hash, AC-5). **Shipped as dual-write behind
  the phase-1 flag** (`_phase1_dual_write_enabled`, default off): the event log is
  the authority at `status_phase: 1`, while legacy frontmatter remains the default,
  sanctioned migration-window fallback. The corpus `backfill -> verify -> cutover`,
  the unconditional flag flip, and the legacy-fallback deletion are deferred to
  follow-up #2816.

- **Charter bundle consolidated into an authoritative `charter.yaml` (#2773).**
  The four compiled bundle files (`governance.yaml`, `directives.yaml`,
  `metadata.yaml`, `references.yaml`) plus `config.yaml`'s `activated_*` keys
  fold into a single git-tracked, authorable `charter.yaml` that becomes the
  project's authoritative structured charter; `charter.md` becomes a curated
  companion. The bundle manifest bumps to schema `2.0.0` (`charter.yaml` is the
  sole content-hash input), and `config.yaml` gains a one-line `charter:`
  pointer. A deterministic, idempotent, fail-loud `upgrade` migration performs
  the fold, sequenced strictly after the `3.2.6` activation-seed migrations
  (verbatim activation copy; the seeds' post-state - `config` carries
  `activated_*` - is the fold's pre-state).

- **`charter activate`/`deactivate --resynthesize` opt-in eager refresh (FR-007, #2761).**
  Since the config↔derived freshness seam (#2759) made `charter activate`/`deactivate`
  visible to the `synthesized_drg` freshness signal, a routine activation now reports
  `stale` until the operator reconciles it. The new `--resynthesize`/`--no-resynthesize`
  flag (default **off**) gives operators an escape hatch: passing it re-runs the existing
  `charter generate` + `charter synthesize` pipeline right after the config write, so the
  derived bundle/DRG - and the freshness signal - are fresh immediately, without building
  a second reconciliation pipeline. The default (no-flag) path is unchanged: a fast,
  config-only write that spawns **zero** synthesis calls, locked in by a call-count spy
  regression test (NFR-001); the `spec-kitty upgrade` migration and `org_charter`
  `promote_activations` paths are untouched and remain synthesis-free (NFR-003).
- **Development-assist test cleanup is now a standing wrap-up procedure (#2557).**
  A new built-in `development-assist-test-cleanup` procedure codifies a proactive,
  judge-the-test pass at mission close (identify -> judge -> execute -> scope-the-residue)
  that retires or splits the scaffolding tests a mission wrote to drive its own
  slices - characterization/parity oracles, before/after timing gates, per-WP
  shape / `__module__` / delegate assertions - before they land as permanent suite
  bloat. It applies `DIRECTIVE_041`'s keep-vs-delete axis and its
  duplicate-test-knowledge-has-one-source rule as the _proactive_ companion to that
  _reactive_ failing-test rubric, and is scoped distinct from `DIRECTIVE_025`
  (pre-existing debt in touched areas). It is wired into `mission-wrap-up-sequence`
  as a new "retire or split the mission's development-assist tests" step after
  acceptance (DRG: +1 node, +5 edges), and the wrap-up hand-off / notes summary now
  records which tests were retired / split / kept-and-renamed.
- **Relocation-hardened architectural dead-code scanners + content-addressed
  ratchet allow-lists (#2546, #2547, #2072, #2548, #2077).** The `tests/architectural/`
  ratchet allow-lists are re-keyed off _position_ anchors (line numbers, `module::Name`)
  onto **content descriptors**, and the 394-entry dead-symbol allow-list onto a
  **relocation-tolerant `SymbolKey`** - content-only by default, escalating a
  byte-identical same-name collision to a `module_path` tier (or fail-closing) via a
  **live, gate-time collision classifier** - so a behaviour-preserving relocation no
  longer forces a hand-edit **without re-blinding the T004 no-false-negative
  invariant**. Adds a standing int-to-line-sink meta-guard, a tier-specific
  dangling-entry ratchet, and the full production-path bite battery. The relocation
  promise is honestly downscoped: relocation-proof for simple single-definition
  entries; re-export/facade/fan-out entries stay `module_path`-keyed (documented, not
  a bug). Ships with a CaaCS change-coupling analysis of the test suite (epic #2071).
- **First-class TEMPLATE + loose-contract ASSET doctrine kinds (#2495, #2469).**
  Org-pack **templates** are now first-class, graph-addressable, edge-wireable
  DRG nodes, and a new loose-contract **`asset`** doctrine kind lets a pack ship
  and reference arbitrary addressable files (image, `.docx`, blob) via a sidecar
  `*.asset.yaml` manifest (`id`/`mime`/`path`, no blob schema). A single canonical
  `_NON_AUGMENTATION_ELIGIBLE_KINDS` set makes both kinds node-declarable but not
  augmentation-eligible or charter-activatable - closing the silent-leak defect
  class by construction. Safety is enforced from day one: **global URN-uniqueness**
  for `asset:`/`template:` (a single post-merge scan -> `duplicate_asset_id` /
  `duplicate_template_id`), **path-containment** (`asset_path_escape`), and **mime
  validation** (`asset_mime_invalid`). A new totality guard asserts every
  `ArtifactKind`/`NodeKind`-keyed mapping table stays exhaustive. The 9 existing
  kinds are unchanged.
- **External orchestrators can submit structured review outcomes without
  forcing lane transitions.** `orchestrator-api transition` now accepts
  `--review-result-json` with reviewer, verdict, and reference fields, allowing
  guarded `in_review` exits to remain fully host-enforced. The additive contract
  change bumps the orchestrator API to 1.3.0.
- **Dashboard WP cards show subtask progress (#2504).** Cards (and the WP
  detail view) previously showed a bare frontmatter count (`4 subtasks`);
  they now show `2/4 subtasks` (with a ✓ at n/n), counted from the canonical
  checkbox rows in the WP body - the same rows the lane-transition guard
  blocks on, via a new shared single definition
  (`core/subtask_rows.py`, now consumed by both the guard and the dashboard
  so the two can't drift). WPs that don't track completion via checkboxes
  keep the plain count badge (no false `0/N`). The kanban task payload gains
  additive `subtasks_done`/`subtasks_total` fields; the typed-contract
  baseline is regenerated accordingly.
- **Seven activated governance artefacts are now reachable from the doctrine
  graph, so `charter activate --cascade` pulls them in.** Each of these was
  shipped active in the default charter pack but had no inbound edge from
  anything, which meant no cascade, no traversal, and no way for an agent to
  arrive at it except by naming it directly. The authored edges are:
  `DIRECTIVE_035` -> occurrence-classification-workflow, `DIRECTIVE_003` ->
  decision-marker-capture, `DIRECTIVE_030` -> no-parallel-duplicate-test-runs,
  `DIRECTIVE_030` -> red-main-release-discipline, `python-conventions` ->
  python-review-checks, `atomic-design-review-checklist` -> atomic-design, and
  `structured-prompt-driven-development` -> reasons-canvas-writing. **This
  changes what a cascade brings in for your project:** activating one of the
  seven source artefacts with `--cascade` now also activates the target that
  was previously stranded. If you have been relying on a cascade to produce a
  specific, narrow set, re-check it after upgrading - the sets are now larger
  by design, because the targets were always meant to travel with their
  sources.

### 🐛 Fixed

- **A corrupt, truncated, or wrong-authority `meta.json` is now rejected loudly by
  every mission read path instead of being silently accepted (mission
  `meta-json-fail-closed-routing`; closes epic `#3259` — `#3228` / `#3229` /
  `#3230` / `#3240`).** A mission's `meta.json` is its canonical identity and
  VCS-lock record. Several internal read paths — git ref-advance, `implement`, and
  the acceptance-matrix merge-driver — still decoded it through hand-rolled parsers
  that would quietly accept a malformed or wrong-authority file, exactly the
  split-brain / wrong-authority failure the metadata-authority work exists to close.
  Before, a bad `meta.json` could let a mission proceed on corrupt identity state
  and surface later as a confusing, hard-to-trace failure; now every remaining read
  routes through one fail-closed decode seam and fails immediately with a clear,
  path-named error. The duplicated VCS-lock comparison — two copies that could
  return contradictory verdicts on the same file — is also unified into a single
  authority.

- **Two blocking CI gates now reflect what a PR actually changed (mission
  `ci-scoping-gate-reliability`; `#3008`, `#3147`).** _Corpus data no longer ships
  unguarded (`#3008`):_ a PR that changed only non-source corpus data — shipped
  doctrine under `packs/**`, a mission's planning artifacts under `kitty-specs/**`,
  or charter config under `.kittify/**` — never triggered the quality workflow at
  all, so every corpus-reading suite was silently skipped pre- and post-merge and a
  regression in shipped data shipped invisibly. Narrow, discrete trigger globs now
  start the workflow on such changes, and a new blocking `fast-tests-corpus` job
  runs the corpus-reading suites (selected by a `@pytest.mark.corpus` marker, so
  already-covered suites are not re-run) and gates the merge. The trigger
  deliberately excludes lifecycle churn (`status.events.jsonl`, notes, trace) so it
  does not fire on every mission PR. _Docs dead-link gate no longer over-fires
  (`#3147`):_ the blocking dead-link / related-edge check scanned the whole tree and
  failed a docs PR for pre-existing broken links in files it never touched. The
  blocking check is now scoped to the PR's own changed files (fail-closed on an
  unresolvable base ref — a shallow clone or unfetched base errors rather than
  passing trivially), while the unfiltered whole-tree scan is retained as the
  non-blocking `push: main` backstop so genuine repo-wide rot is still surfaced.
- **The `charter` and `sync` modules are cleared of their Sonar maintainability
  backlog, including a super-linear-backtracking regex (mission
  `charter-sync-sonar-remediation`; `#3232`-adjacent).** 80 SonarCloud findings
  across the two modules — 27 over-complex functions, 15 duplicate literals, 20
  malformed suppression comments, unused parameters, too-many-parameter
  signatures, and one ReDoS-class regex flagged `BLOCKER` — were resolved with
  **behavior-preserving** refactors and **no new suppressions**. Over-complex
  functions were brought to the ≤15 cognitive-complexity ceiling via tested
  helper extraction (each helper carries a focused test); duplicate literals
  became named constants; the `token_budget` heading regex was rewritten to
  remove its `.`/`\s` ambiguity (proven match-equivalent by a characterization
  test); and the two too-many-parameter event emitters (`emit_wp_status_changed`
  and `emit_token_usage_recorded`) were slimmed by bundling their optional tail
  fields into typed params objects (`WPStatusChangeMetadata` /
  `TokenUsageMetadata`), with every call site migrated to the params object so
  the tail stays fully type-checked rather than routed through an untyped
  `**kwargs` bag. Two findings are Sonar false-positives (a Pydantic
  `PrivateAttr` and an already-single-return method) with no clean code fix;
  they remain for a SonarCloud UI won't-fix. No runtime behavior changes.
- **Signature change for out-of-tree callers of two exported event emitters
  (mission `charter-sync-sonar-remediation`; `#3317`).** `emit_wp_status_changed`
  and `emit_token_usage_recorded` (re-exported from the `sync` facade) no longer
  accept their optional tail fields (`causation_id`, `force`, `evidence`,
  `run_id`, `provider`, `model`, …) as individual keyword arguments. Pass a
  `WPStatusChangeMetadata` / `TokenUsageMetadata` object via the keyword-only
  `metadata=` parameter instead. All in-tree callers are already migrated; only
  external plugins that called these helpers with the old keyword tail are
  affected.
- **Restored an honest red CI gate: `main`'s two standing reds now go green for
  the right reason, and `move-task`'s pre-review gate stops crying wolf
  (test-layer only; epic `#3260` — "a red gate must mean a real regression").**
  This is a CI/gate-correctness pass with **no runtime or behavior change** — no
  `src/` change, no `__init__.py` touch, no version bump — so nothing you install
  or run changes. What changes is that the project's own signal is trustworthy
  again:
  - **The blocking `regression tests` job goes green** because the last resident
    red-first reproduction (`#2782`) was retired. That repro asserted `agent
    mission create --json` synchronously emits a `direct ingress skipped`
    diagnostic on stderr — a contract the deferred/offline sync architecture
    cannot satisfy (mission-create queues its lifecycle event and dossier bodies
    to the offline outbox and returns without an in-process ingress attempt, so
    the diagnostic never fires there, even with consent recorded). It was
    redesigned into a green functional test of the architecturally-honest
    mission-create contract (`rc=0` + strict-JSON stdout + no diagnostic prose on
    stdout + the `#2254` drift guard), moved back beside its strict-JSON siblings,
    and un-marked `regression`. `-m regression` now collects nothing, so the
    blocking job passes. (The diagnostic's real firing is still proven at the
    resolver seam by a separate test.)
  - **The `integration-tests-cli` job goes green** because a drifted test was
    locking a since-corrected contract at the `commit_to_branch` seam. Following
    `#3269` / commit `793872a19`, only a genuine empty changeset maps to
    `unchanged`; a rejecting pre-commit hook is a real failure. The test was
    rewritten to assert the corrected contract (hook rejection re-raises and
    leaves the artifact dirty).
  - **`move-task`'s pre-review gate stops reporting phantom "new failures"** —
    two false reds that made the reliability gate untrustworthy (both children of
    epic `#3260`). `tests/doctrine/test_hatch_build.py` now guards its transitive
    import with `pytest.importorskip("hatchling")`, so the pre-review gate's
    ephemeral baseline venv (which lacks `hatchling` outside the `test` extra)
    skips it cleanly instead of hard-failing collection; the normal test job
    installs the extra and still runs every test (`#3224`). And
    `test_inline_meta_read_gate` now relativizes scanned paths against the scanned
    tree's own root rather than the gate file's location, so a cross-tree
    (git-worktree baseline) scan no longer produces absolute paths that silently
    over-count `mission_metadata.py` as a violation (`#3241`, PART 2).

- **The #2804 gate-artifact merge invariant is guarded again at the driver level,
  and the doctrine module's Sonar maintainability debt is cleared (mission
  `gate-artifact-merge-driver-unit-gate`; `#3232`).** A prior refactor (`b04da00e1`)
  deleted the unit test that pinned "a merge must never reset a filled acceptance/
  issue gate artifact back to a scaffold placeholder", and it was never restored
  because it had been written for a whole-file heuristic the row-union authority
  model (`#3076`) replaced. This restores that guard as a fast, in-memory unit gate
  over the shipped row-union reconcilers: a filled/accepted criterion is never reset
  to the scaffold marker, the accepted evidence handle survives a merge (including
  inside a structured conflict marker), and the merged verdict stays in its
  admissible domain — each with a falsifying control. Bundled opportunistically:
  the `src/doctrine/` Sonar backlog is cleared — 37 duplicate-literal findings hoisted
  to named constants, 7 over-complex functions reduced to the ≤15 cognitive-complexity
  ceiling via tested helper extraction, and 3 minor smells resolved — all
  behavior-preserving with no new suppressions. (One 183-complexity function is
  deferred to a dedicated mission.)
- **`spec-kitty auth login` (and any caller of the SaaS URL helper) now points
  you at the real hosted service when `SPEC_KITTY_SAAS_URL` is unset, not a fake
  placeholder (`#3297`, closes `#3296`).** Previously, running the command
  without that variable set told you to `Set it to your spec-kitty-saas instance
  URL (e.g. https://api.spec-kitty.example.com)` — a `.example.com` placeholder
  that does not resolve, so a first-time user who copied it got a dead URL. The
  guidance named the then-current hosted URL (now `https://team.spec-kitty.ai`), so the
  example is copy-paste-usable; self-hosted instances still override via the env
  var exactly as before.
- **Timestamps that Spec Kitty writes into your project no longer record local
  time while labelling it UTC (mission `kernel-clock-single-door`; `#3305`,
  closes `#3289`, owns the closed `#3288`).** Roughly twenty places across the
  tool — charter backup filenames, status-event stamps, auth-doctor report times,
  and other persisted "now" values — read the machine's _local_ clock and then
  tagged the result as UTC. On any machine not set to UTC the stored time was
  simply wrong: a backup taken at 09:00 CET was filed as `…T09-00-00` and read
  back as 09:00 UTC, an hour or two off. Every such value now comes from one
  canonical aware-UTC producer, so stamps are correct and consistent regardless
  of the host timezone. Under the hood all wall-clock reads now go through a
  single `kernel.clock` "door" that every package can import, and a repo-wide CI
  gate blocks any new raw `datetime.now()` / `time.time()` read from
  reintroducing the drift — but the change you can observe is simply: the
  timestamps are right now.
- **`spec-kitty doctor auth --fix` now reports a real disk failure instead of
  quietly claiming "nothing removed" (mission `sonar-bug-blocker-remediation`).**
  When breaking a stale auth lock hit a genuine I/O error — a full or failing
  disk — `force_release` mislabeled it as ordinary lock contention, so the
  command told you nothing was wrong while the real fault went unseen. It now
  lets genuine filesystem errors propagate while true lock contention still
  returns cleanly, matching the rest of the locking layer.
- **Activating a slug-named hub directive (e.g. `use-c4-model-techniques`) in a
  charter now resolves to the real doctrine node instead of a dangling
  identifier (`#3009`, `#3298`).** The directive-id normalizer folded numbered
  slugs (`024-...` → `DIRECTIVE_024`) but left slug-named directives hyphenated
  and uppercased (`use-c4-model-techniques` → `USE-C4-MODEL-TECHNIQUES`), which
  is not the artifact's canonical node id (`USE_C4_MODEL_TECHNIQUES`). So
  activating or referencing such a directive by its slug silently pointed at
  nothing. The normalizer now folds hyphens to underscores, matching the
  canonical node id — so slug-hub directives activate and cascade like any other.
- **`spec-kitty tracker sync publish` on a local (`beads`/`fp`) binding now
  prints a clear error instead of crashing with a Python traceback (`#3168`).**
  Local providers have no snapshot-publish transport, but the command delegated
  to the backend unconditionally and hit an uncaught `AttributeError`, which the
  CLI let escape as a raw traceback. It now exits with a clean
  "not supported for local providers — use `tracker sync push` instead" message.
- **`charter generate` is now idempotent — a second run no longer degrades the
  compiled catalog (`#3292`).** Two independent `active_languages` computations
  fed a feedback loop: `generate` stamped `catalog.languages: []` for a
  language-agnostic charter, and the language-scope gate then read that empty list
  back as an authoritative "admit no languages", degrading language-scoped
  styleguide/toolguide titles and summaries to a `"Definition unavailable in
  bundled doctrine"` placeholder on the next run. `active_languages` now has a
  single authority and an empty result means "no signal → admit all" (round-tripped
  as an absent field, not a persisted `[]`), so repeated generates are byte-stable.
- **The reason `spec-kitty sync doctor` gives for a refused tracker egress can
  no longer disagree with what the gate actually enforced (`#3287`, `#3291`).**
  The gate decided whether to refuse from one source but re-derived the _why_ —
  and the remedy shown to you — from a second, independent consent lookup that
  could drift from the enforced answer, and it repeated a full git-identity
  resolution on every gated sync. The reason now comes from the same evaluation
  that enforces the decision: a refusal's explanation always matches the
  refusal, a consent record that cannot be read is reported as its own state
  instead of masquerading as "no consent recorded", and a gated
  `tracker sync` resolves your project's consent once instead of twice.
- **A spec commit that genuinely FAILS is no longer silently reported as
  "unchanged" (`#3269`).** When a `git commit` failed for a real reason — a
  rejecting pre-commit hook, a lock error — `safe_commit` collapsed every
  non-zero exit onto the same "nothing to commit" path, so `spec-commit` printed
  _"Spec artifact(s) unchanged, no commit needed"_ and the spec silently never
  landed. Emptiness is now decided by the **staged tree** (`git diff --cached`),
  not by matching git's output text: a genuine no-op is still reported as
  unchanged, while a real failure surfaces as an error carrying git's own
  diagnostic — even when a failing hook prints its own "nothing to
  commit"-shaped message.
- **`spec-kitty` no longer crashes when an arbiter override lands on a
  conflict-marked review-cycle file (mission `verdict-seam-boundary-hardening`;
  `#3244`).** An arbiter override written against a `review-cycle-N.md` that
  still carried unresolved merge-conflict markers used to raise instead of
  resolving the latest cycle; the cycle number is now read from the filename
  alone, so the override applies cleanly.
- **SaaS tracker retry/poll tests no longer flake on CI, and a new gate keeps
  the whole bug class out (mission `sync-sleep-count-3136`; `#3136`).** These
  tests asserted on `time.sleep` call counts and failed non-deterministically
  with errors like `Expected 'sleep' to be called once. Called 179 times.` on
  test nodes a change never touched — because patching the shared stdlib
  `time.sleep` recorded sleeps from anything else running in the same test
  worker. Building on `#3187` (which gave `SaaSTrackerClient` its own
  `self._sleep` seam), the client now also binds `self._monotonic` /
  `self._randbelow`, so its retry/poll timing and jitter are fully isolated from
  process-global state. A new architectural gate
  (`tests/architectural/test_shared_module_object_patches.py`) refuses any future
  test that patches a shared module object read by a count/equality assertion, so
  this class of flake fails review instead of shipping.
- **Restored green CI on two suites that regressed after the single-`PACKS_ROOT`
  / charter-activation unification (mission `resolution-activation-foundation`).**
  `tests/review/test_pre_review_gate_integration.py` and
  `tests/merge/test_profile_charter_e2e.py` still built bare fixtures that never
  provisioned the default charter / mission-type activations, so once resolution
  moved to a single fail-closed `SPEC_KITTY_PACKS_ROOT` read the pre-review gate
  degraded to `no_coverage` (never blocking) and mission-template resolution
  raised `MissionsRootNotFound`. The fixtures now seed the default activations
  via the production provisioner and mirror the built-in `missions` leaf under
  the packs root. Test-harness only - no product behaviour changed; the
  fail-closed resolution the sibling mission introduced is intentional.
- **Commands run on a merged coordination mission no longer crash (`#3086`).**
  Once a coordination mission was merged, later commands against it - creating a
  retrospective, resuming implementation, or checking its status - failed
  outright, and this hit every merged coordination mission. Merging now
  finalizes the mission cleanly, so it stays usable afterward.
- **`decision widen` no longer lets one mission's decision travel under
  another mission's identity (mission `egress-refusal-consolidation-3110`;
  `#3111`).** Previously, ownership was resolved from whatever the decision
  ledger it was handed reported rather than from the mission you actually
  named, so a decision owned by mission A could be widened under a request
  naming mission B and have the egress consent gate treat it as consented -
  laundering A's identifying text out under B's team/token. Widening now
  refuses whenever the acting mission and the decision's recorded owner
  disagree. The governing rule: identity is a detector, never an actuator.
- **The consent-refusal gate deciding whether project-identifying text may
  leave your machine now has one definition site instead of two
  near-identical copies that could drift apart (`#3110`).**
  `saas_client/egress_consent.py` and `tracker/egress_consent.py` are
  replaced by `src/specify_cli/egress.py`.
- **Listing missions on Python 3.14 no longer reports a permission error as
  "no missions found" (`#3177`).** An unreadable mission directory was
  silently dropped instead of being recorded, so the CLI told you to `git
  pull` for what was actually an `EACCES`. It now reports the directory as
  unreadable; unaffected on the CLI's supported 3.11-3.13 interpreters.
- **Internal: a stale docstring in the saas-client/egress invocation adapters
  no longer claims re-registration only replaces a factory or resolver "when
  the qualified name matches" (`#3109`).** Both always replaced
  unconditionally; only the documentation was wrong, and only the control
  flow used to reach the same assignment differed. Behavior is unchanged.
- **`UnknownMissionTypeError` no longer labels an activated mission type both
  "unknown" and "registered" (mission
  `doctrine-consumer-surface-missions-extraction`; `#3183`).** When a mission
  type is activated but has no loadable profile, the error now states that
  distinctly, instead of the contradictory "Unknown mission type '<x>'.
  Registered types: <x>".
- **The built-in-doctrine dead-path architectural gates no longer silently lose
  coverage when a gate file is split, and the shipped `doctrine-daphne` profile
  no longer carries a repo-local `src/doctrine/graph.yaml` reference (mission
  `doctrine-consumer-surface-missions-extraction`; `#3036`, `#3182`).** The
  `src/`-wide gates and the doctrine-content gate are split by actual scope with
  their discriminator proofs driven from planted synthetic fixtures, and the
  relocated-tree cross-link scan now covers both shipped roots.
- **The dashboard's Charter page no longer misreports a compiled-only project
  as having no charter (mission `doctrine-charter-split-unification`;
  `#3150`).** Before this fix, a project with a compiled
  `.kittify/charter/charter.yaml` but no display-only `charter.md` companion
  showed "no charter" in the dashboard sidebar and its API - both the artifact
  scanner and the charter API endpoint still keyed presence on the legacy
  `charter.md` file. Presence resolution now prefers `charter.yaml` (the read
  authority) and falls back to `charter.md` when `charter.yaml` has not been
  compiled yet, across the dashboard, analysis-report, and
  retrospective-policy surfaces - so a `charter.md`-only project that never
  ran `charter sync`/compile still reports a charter, and a compiled project
  still survives `charter.md` deletion; the prose body the Charter page
  displays still comes from `charter.md` when one exists. Two exceptions are
  intentionally pinned, not
  residual gaps: `charter context`'s prose-presence gate (documented, C-003)
  and `charter status`'s legacy `charter.md`-only fallback for
  pre-consolidation bundles (`_status_collectors.py`, pinned by
  `test_status_collectors_legacy_md_shape.py`, FR-006).
- **A corrupt or malformed `meta.json` now always fails closed with a clear
  error, never a raw crash (mission `doctrine-charter-split-unification`;
  `#3140`).** Previously, dozens of call sites across mission-status,
  coordination, migration, and CLI commands could leak an unhandled
  `ValueError` when a mission's `meta.json` was corrupted or shaped
  unexpectedly, surfacing as an opaque traceback instead of an actionable
  error. Every one of those readers now routes through a single typed
  `MissionMetaReadError` (or a documented silent-empty fallback where that was
  always the contract), so a broken mission's metadata degrades predictably
  instead of crashing the command you ran.
- **Internal: `doctrine-charter-tests.yml` CI now actually covers the charter
  CLI command layer, and the CLI-reference parity check runs instead of
  silently skipping (`#3149`, `#3107`, `#3102`).** A change under
  `src/specify_cli/cli/commands/charter/**` previously wouldn't trigger the
  workflow named for it; the docs-parity gate had pointed at a reference file
  that no longer existed, so it never actually ran.
- **Approving a work package after a rejection now actually sticks - no
  override flag required (mission `review-verdict-write-integrity`; `#3044`,
  `#2275`, `#2996`, `#990`, `#2697`, `#2646`).** Before this fix,
  `move-task --to approved` on a previously-rejected WP advanced the lane but
  wrote no record of the approval - the stale `rejected` verdict stayed
  authoritative, so `move-task --to done` and `spec-kitty merge` kept blocking
  on it, forcing `--skip-review-artifact-check` (an arbiter-override flag) on
  every ordinary reject -> fix -> approve cycle. Separately, the rejection
  writer accepted any file as "feedback" without checking it wasn't itself a
  prior cycle's own review artifact (by path or by a renamed copy), so a
  mistaken re-submission (a reviewer accidentally re-pasting the same feedback
  text) could silently duplicate an old review under fresh, fabricated
  frontmatter. Neither writer ever git-committed its output under any
  topology, so even a successful write could land untracked. Now: approving a
  rejected WP through the normal path persists and commits a real
  `verdict: approved` review-cycle artifact with a genuine reviewer identity;
  the override flag still works for actual arbiter decisions but is no longer
  _needed_ for an ordinary approval; a rejection's feedback source is refused
  if it's the same or a duplicate of a prior cycle's own artifact (a check
  that a deliberate one-character edit still defeats - it targets accidental
  duplication, not a determined actor); and both `move-task` write paths now
  commit their review-cycle artifact when auto-commit is resolved on
  (`--auto-commit`, or `auto_commit: true`/default in `.kittify/config.yaml`),
  surfacing a clear error if the commit itself fails rather than silently
  discarding it. Under `--no-auto-commit`, or with `auto_commit: false`
  configured, the write still lands but is not committed. A third writer,
  `_persist_review_feedback`, does not yet thread a commit router at all.
  `agent tasks status`'s stale-verdict display (`#2646`) is confirmed to close
  as a side effect of the durable writer, with no separate code change needed.
- **A work package's current verdict now has a single authority that wins on
  disagreement - the status event log, not a review artifact's frontmatter
  (mission `review-cycle-verdict-seam-rebuild-01KZ2W7W`; ADR
  `2026-08-03-1`).** Before this fix, "is this WP approved?" had no single
  answer: some readers (the kanban board, `move-task`'s review-readiness
  check) parsed a `review-cycle-N.md` artifact's `verdict:` frontmatter field
  directly, so a reader could disagree with the event log about which verdict
  was current if the two ever drifted. Now the event-sourced verdict wins on
  any such disagreement; frontmatter reads remain in place as a fallback for
  the case where the event log carries no opinion (for example, legacy
  coord-topology missions that predate this seam), and no new
  frontmatter-reading path was added - the merge gate still drives its
  readiness loop off a frontmatter reader for that no-opinion case, by design.
  The review-cycle artifact remains authoritative for _what the reviewer
  said_ - the reviewer's prose, affected files, reproduction command - never
  for _which verdict is current_ once the event log has an opinion to give.
- **An arbiter's override decision now durably persists and clears the merge
  gate on its own - no separate flag or manual step required afterward
  (mission `review-cycle-verdict-seam-rebuild-01KZ2W7W`; ADR
  `2026-08-03-1`).** Before this fix, the arbiter override writer never
  git-committed its output under any topology, so an override could be
  present in a working tree and still vanish from a fresh clone or a
  branch switch - the exact gap that made `--skip-review-artifact-check`
  feel unreliable even when it had "worked." Now the override is committed
  through the same seam every other verdict-relevant write uses, so it
  survives a fresh clone and the merge gate accepts it without repeating the
  override flag.
- **An arbiter override can no longer be mistaken for, or silently absorbed
  into, a genuine reviewer approval (mission
  `review-cycle-verdict-seam-rebuild-01KZ2W7W`; ADR `2026-08-03-1`).** Before
  this fix, nothing distinguished a knowingly-overridden standing rejection
  from an approval a reviewer actually performed - both could present the
  same way to a consumer reading only the latest verdict. Now the override is
  recorded and read back as its own first-class outcome (a stated actor and
  reason, event-sourced on the same partition as the record it annotates),
  never fabricated as an approval review nobody performed.
- **Applying a charter pack no longer leaves your project worse off than doing
  nothing (mission `charter-pack-usage-journey`; `#3104`, `#3105`).** Before
  this fix, `spec-kitty charter pack apply <pack>` on an unconfigured project
  disabled the safe generic-agent dispatch fallback - so the next unmatched
  `spec-kitty dispatch` hard-failed with `ROUTER_NO_MATCH` - and `charter
  context` / `charter status` still reported the charter as "not found" because
  they gated on the display-only `charter.md` that `apply` never writes. Now:
  applying a pack **without** compiling keeps the warned generic-agent net
  engaged (an unmatched request still falls back, never `ROUTER_NO_MATCH`), and
  checking that adds no extra doctrine-catalog load to the dispatch hot path
  (`#3118`); `apply --compile` does the apply and compile in one step; after you
  compile, `charter context` / `charter status` reflect the pack's activated
  governance and keep working even if `charter.md` is deleted (the read
  authority is the compiled `charter.yaml`); and the governance resolver reports
  the _activated_ directive set rather than silently falling back to all
  built-in directives. The documented `spec-kitty analyze` surface and the CLI
  are now guarded to stay in agreement (`#3096`). **Deliberate behaviour
  change:** the dispatch net now keys purely on whether a compiled bundle or a
  routable profile/org pack exists, not on every activated doctrine dimension -
  so a project that has activated only glossary packs, directives, or other
  non-routing doctrine (no bundle, no routable profile) now falls back to the
  generic-agent net too. This narrows the broader composite-dimension check the
  `#3064` fix introduced above; it is a tested, recorded change, not a silent
  regression.
- **Contract note - `charter context --json` (`project_charter.present`).** The
  read authority for the JSON charter-presence surface moved from the
  display-only `charter.md` to the compiled `charter.yaml`: a project that has a
  `charter.md` but never compiled now reports `project_charter.present: false`
  (the new `charter_md_present` / `charter_md_path` keys expose the display file
  separately, so the information is additive, not lost). The payload also now
  carries a top-level **`context_schema_version`** stamp (a versioned _tracking_
  contract; a full shape freeze + deprecation policy stays deferred to the
  `#2519` activation-surface work) so an external consumer can detect a shape
  change instead of breaking silently. External `--json` consumers should read
  `charter.yaml` as the authority-of-record and pin `context_schema_version`
  (`#2787`).
- **A non-terminating test now fails loudly instead of hanging the CI job
  (mission `verification-trust-3115`; `#3115`, `#3113`).** `pytest.ini`
  registered a `timeout` marker but set no timeout, so a test that never
  returned stalled its whole shard rather than failing - a mechanism reporting
  nothing where it should report a failure. The fast-test CI jobs now carry a
  default per-test timeout (`--timeout` with the signal method), and a new
  architectural gate (`test_ci_fast_jobs_have_timeout.py`) keeps the flag from
  being silently dropped, with two documented exemptions (the real-wheel docs
  build and the `-n0` real-port orphan-sweep, where a signal mid-teardown is
  unsafe). Also hardens the terminal-render width fold, the egress-consent
  boundary, and the `tests/sync` leak-guard so each is provable rather than
  asserted. **No product code (`src/specify_cli`) changed** - this is a
  test-trust and CI change; Windows and local runs still get no per-test
  timeout (tracked by `#3143`). (`#3130`, `#3136` referenced.)
- **Fixed: `sync` could deliver one project's events to another project's
  workspace, including projects that never opted in (#3030).** A machine
  keeps one shared local event journal across every Spec Kitty checkout on
  it. Sync's consent check only asked "is sync enabled for _this_ checkout?"
  - once yes, it delivered the _entire_ journal, so a single opted-in
  project could ship another, unrelated project's events and metadata to the
  hosted server. Every path that reads from the journal for delivery is now
  gated per-project, consent is checked before events leave the machine
  rather than only at the checkout level, and an unresolvable consent check
  now fails closed (refuses to send) instead of failing open. If you use
  hosted sync for more than one local project, only the project(s) you
  explicitly opted in now have their data sent.
- **Generated agent guidance reads grammatically again (mission
  `charter-delivery-finish-context-degod`; `#3082`).** The "verbatim-or-fetch"
  disclosure lines every agent receives in charter context were frequently
  ungrammatical - e.g. `When you designing or reviewing significant code
  changes, run this command`. The authored `when` clause is now normalized into
  the closed contract lead-in set (`When you are about to ...`) for every clause
  shape, and the prompt-governance contract is asserted **per stanza** so a
  regression can't hide behind another matching line. (A second, independent
  render surface in `section_bodies.py` is tracked separately as `#3093`.)
- **DRG document-writer blind spot closed (mission `doctrine-delivery-activation`;
  `#3075`, `#2977`).** All three `DRGGraph` document-emit sites
  (`rewrite_opposed_by`, `charter.synthesizer.project_drg`, and the
  `pack_assembler` force-dedup path) now route through the canonical
  `graph_document_to_dict` and are registered `DocumentWriter` members, guarded
  by a new non-vacuous writer-discovery gate that fails on either an
  unregistered dict-literal or a `.model_dump()`-shaped emitter. The
  `pack_assembler` path was additionally crashing `yaml.safe_dump` on the
  `Relation` enum (and leaking withheld fields). The repository surfaces are
  typed via a new `ArtifactRepository` `Protocol`, removing 12
  `# type: ignore[attr-defined]`.
- **`DRGGraphSchemaError` now surfaces as a structured `doctrine validate`
  issue instead of an uncaught traceback**, and `AssetRepository.source_path`
  no longer disagrees with `get` for a manifest that failed validation (a base
  `_post_validate` success-path hook records the source path only after
  validation) (`#3062`).
- **The `test_every_load_delivery` fixture is now hermetic** to an ambient
  gitignored `.kittify/charter/context-state.json`, eliminating a local-only
  false-red on the `first_load`/bootstrap assertions.
- **Read-side placement seam: mission reads route through the kind-aware seam and
  new bypasses are structurally impossible (#2922, #1878; also #2921, #2966
  part-1).** The write side already failed loud when an artifact's coordination
  partition was gone, but ~50 modules still read mission artifacts through the
  low-level kind-blind resolvers, so a read could silently substitute the primary
  checkout for a deleted coord branch:
  - Every fail-loud-appropriate caller (72 sites, per a per-site classification
    ledger) now reads via `PlacementSeam.read_dir(<kind>)` with the correct
    artifact kind. Coord-partition reads - a lane-based merge's event log, the
    decision-log companion read, the doctrine synthesizer - now fail loud instead
    of treating a deleted coordination branch as healthy.
  - 16 diagnostic/audit/SaaS-facing readers (dashboard scan, dossier API,
    retrospective summary, status aggregation, and friends) stay **lenient by
    design** and are recorded as justified allow-list entries - reporting surfaces
    must not start raising.
  - A new whole-tree AST gate reds on any future direct kind-blind read in a
    non-sanctioned module, reusing the same scanner as the write-side gate. The
    allow-list is shrink-only: a staleness twin-guard reds until an entry that is
    no longer needed is deleted.
  - Behavior is unchanged for the healthy case; `repair_lane_mismatch` no longer
    duplicates frontmatter into the document body (#2921), and
    `backfill_runtime_state`'s mission-id read is anchored on the PRIMARY leg.
  - Fail-loud does **not** mean crash on the paths that exist to recover from a
    broken coordination branch. `spec-kitty implement --recover` now reports a
    `COORDINATION` finding carrying the `doctor coordination --fix` remediation
    instead of tracebacking, `spec-kitty merge` aborts with a readable message
    before any state change rather than mid-merge, and `agent workflow review`
    degrades to an advisory warning instead of aborting while computing one.
  - `spec-kitty verify`'s mission-directory probe is now CWD-invariant: invoked
    from a lane worktree it resolves the main repository's `kitty-specs/` rather
    than reporting the mission as absent. Both production callers already
    anchored on the main repo, so this is observationally a no-op for them.
  - **`spec-kitty accept` no longer rewinds finished work packages to
    `claimed` (#3013, #2985).** The birth-cutover seed anchored its
    `planned -> claimed` carrier on a work package's _earliest_ transition,
    which for a force-jumped or pruned WP is its **terminal** one. The seed
    then collided on timestamp, and because the reducer sorts by
    `(at, event_id)` the hash-derived seed id outranked the real ULID - folding
    a `done` WP back to `claimed`, so a second `accept` on an unchanged tree
    did not converge. (This corrects the mechanism recorded on #2985: it is the
    sort key, not append order.) `accept` is also now event-count neutral on
    missions whose runtime state is already canonical. **Already-corrupted logs
    do not self-heal** - they still need the #3003 corpus regenerate, which
    this unblocks.
  - **`doctor mission-state --fix` no longer destroys `review_result`, log
    order, or dropped duplicates (#3003).** `_build_canonical_row` is a closed
    allowlist that omitted `review_result` - a first-class `StatusEvent` field
    _and_ a hard FSM guard, since every transition out of `in_review` is
    rejected without it. Repairing a corpus therefore converted valid history
    into events the reducer could no longer validate: 268 transitions across 44
    missions, with none failing beforehand. The loss was worst-shaped, because
    `DoneEvidence.review` mirrors the payload only on approval - so the
    `changes_requested` rows were the irrecoverable ones. The allowlist is now
    gated against `StatusEvent.__dataclass_fields__` so a newly added model
    field cannot be dropped the same way. Two further fixes: rows now sort on
    `at` **or** `timestamp` (lifecycle and retrospective rows date themselves
    with the latter, so 839 of them were collapsing to `""` and being hoisted to
    the head of an append-only log), and a dropped duplicate `event_id` row is
    quarantined rather than only hashed.
  - The classification ledger is now the _mechanical_ authority for the
    stay-lenient allow-list - the gate parses it, so the doc and the gate cannot
    drift apart silently. The gate additionally resolves import aliases, and its
    coverage bounds (including the unpoliced `primary_feature_dir_for_mission`)
    are stated explicitly rather than implied.
- **Almost the entire test suite was being skipped on pushes to `main` (#2957).**
  CI decides which test jobs to start by looking at which paths a change
  touched. That is a sensible optimisation for a pull request, but it was
  applied to pushes to the protected branch as well - so a merge whose diff
  happened to match none of the path filters started **10 of 50** test jobs and
  left **31,547 of 33,822** test cases (93.3%) running nowhere. This was not
  theoretical: four test files that pin frozen contracts were failing on `main`
  while `main` CI reported green, because the only jobs that would have run them
  were filtered out. Path filtering is now a pull-request optimisation only. A
  push to a protected branch starts 49 of the 50 suite jobs and leaves no test
  uncollected; pull requests are unchanged. A new check
  (`tests/architectural/test_ci_collection_completeness.py`) fails if any
  collected test is left with no job that would run it on a push to `main`. It
  has no baseline and no allowlist - the only way to satisfy it is to make a job
  actually run the test.

- **Doctrine packs could declare things that quietly had no effect (mission
  `doctrine-silence-guards`; ADRs [2026-07-26-1](../adr/3.x/2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md),
  [2026-07-26-2](../adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md),
  [2026-07-26-3](../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md)).**
  The doctrine layer's characteristic failure was silence rather than error: a
  declaration was accepted, validated, reported as loaded, and then dropped. Every
  case below now either works or fails with a message naming what was wrong.
  - **Five of the sixteen artifact kinds were missing from the doctrine-graph
    extractor** - `anti_pattern`, `asset`, `glossary`, `glossary_pack` and
    `glossary_scope` were dropped whenever the graph was rebuilt. All sixteen are
    handled, and the mapping is now checked for completeness instead of being
    maintained by hand.
  - **Two of the twelve org-pack directory names crashed the merge outright**
    with a bare `KeyError` (`mission_types/`, `glossary_packs/`). One consequence
    worth naming: the shipped test fixture called `augment-all-kinds-pack` could
    not be merged at all, so the "all kinds" fixture never exercised all kinds.
  - **Edges derived automatically from an org pack's agent-profile fields never
    reached the graph.** The producer emitted fully-qualified `<kind>:<id>`
    endpoints; the code that consumed them looked up bare ids. Nothing matched,
    so 100% of that path's output was discarded, silently.
  - **An edge from a built-in artifact to a pack artifact was dropped** with
    neither a warning nor an error. It now resolves, or reports a typed error
    naming the endpoint it could not resolve.
  - **A bare name that referred to a styleguide was turned into a made-up
    `directive:<name>` node** rather than the `styleguide:<name>` the author
    meant.
  - **Unrecognised keys in agent profiles and in graph nodes and edges were
    silently ignored**, so a typo or a retired key left an artifact that read
    one way and behaved another (see Breaking Changes).
  - **Activating the `doctrine-daphne` agent profile pulled in 76 related
    artifacts but not the one procedure the profile itself says it runs.** The
    edge to that procedure used a relation type (`applies`) that nothing
    traverses, and it was the procedure's only inbound edge, so the profile's own
    operating procedure was unreachable. The edge is retyped to `requires`, and
    authoring an `applies` edge into the shipped tree is now rejected.
  - **Error messages sent operators to files that do not exist** - an inline
    reference rejection pointed at `src/doctrine/graph.yaml`, split into per-kind
    fragments long ago, and two operator-facing skill documents told authors to
    read a `src/doctrine/<kind>/shipped/` layer that has never existed on disk.
    Both are corrected and both are now guarded.
  - **The generated schema for the docs structural lint had widened to "any
    object"**, so a malformed lint configuration validated cleanly and the lint
    ran on settings nobody had checked. The generator now emits the real
    ten-key contract.
  - **The documented example for declaring agent-profile lineage used a syntax
    that exists nowhere in the vocabulary** (`urn:profile:...`). Anyone who copied
    it got a declaration that merged without complaint and produced no edge. The
    example is corrected in `AGENTS.md` / `CLAUDE.md` and in
    [the org-pack authoring guide](../guides/how-to/governance/create-an-org-doctrine-pack.md), and
    the accepted forms are now enforced at merge time.

- **`spec-kitty agent tasks mark-status` could not find subtask ids written the
  way the shipped template tells you to write them (#2962).** The command
  resolved a subtask id by matching a row shape in `tasks.md` - a checkbox, a
  pipe-table row, or an inline `Subtasks: T001, T002` list. The shipped
  `software-dev` template instructs authors that subtask rows are reference
  rows and explicitly _not_ checkboxes, so a `tasks.md` that follows the
  template matched none of those shapes and every id came back `NOT_FOUND`.
  That blocked the review workflow on every work package of every mission using
  that template. The command now falls back to the authored `subtasks:` roster
  in work-package frontmatter - the same list the lane-transition guard already
  treats as canonical, so the two surfaces agree on what a work package's
  subtasks are. The fallback runs last, so every row shape that worked before
  resolves exactly as before.

- **Placement-port residuals: partition routing is now enforced by the port, not
  by caller discipline (#2923, #2924, #2926, #2932; epic #2931).** Closes the
  residuals deferred from the coord-write-placement-closure merge (PR #2920):
  - The sole `status_phase` writer (`_flip_phase`) resolves its write target
    through the placement port and **fails closed** with a typed
    `PlacementMismatchError` (writing nothing) if the resolved PRIMARY home
    disagrees with the caller's directory - coincidental correctness becomes an
    enforced invariant.
  - The two-target legacy cutover reads `tasks/` frontmatter from the PRIMARY leg
    while the status event write stays on COORD.
  - Three hand-rolled "resolve write target, else degrade" copies collapse into
    one `resolve_write_target_or_degrade` helper (each caller keeps its own
    fail-open / fail-closed policy), and the retrospective trace loader degrades
    to `[]` on a deleted coordination branch. A latent bug is fixed along the way:
    a caller-supplied coordination branch that was silently discarded in the
    pre-`meta.json` bootstrap window is now honored.
  - The write-side placement scan no longer blanket-exempts the `migration/`
    subtree, restoring whole-tree precision. The remaining deferred gate/contract
    reds were already green on the current base and are verified in-mission.

- **The merge review-readiness check no longer writes a stray `status.json`
  during a merge (#2934).** The check that looks for a rejected review before
  merge was reducing mission status through the _writing_ materializer, so it
  left a `status.json` snapshot on disk as a side effect. On a mission with no
  status events yet, that snapshot had no matching `status.events.jsonl` (the
  append-only event log that is the real source of truth), and the merge could
  commit the orphaned snapshot on its own - the invalid "snapshot without its
  event log" state the status doctor flags. The check now reads status without
  writing anything; a gate reads, it does not persist. Includes the regression
  test and a de-mocked planning-only merge test that exposed the shape.

- **Running Spec Kitty non-interactively (agents, CI, piped input) no longer
  hangs waiting for a prompt that will never be answered (#2876; extended in
  #2912; landed by #2910).** Under `SPEC_KITTY_NON_INTERACTIVE=1`, `spec-kitty plan` and
  `specify` reached their discovery interviews and called a blocking prompt with
  no non-interactive gate anywhere in the call graph, so an open-but-silent
  stdin pipe made them wait forever. The interviews now honor the contract: they
  still open every Decision Moment and write the decision index, but take
  defaults and record each question as deferred instead of prompting - no prompt
  is ever emitted non-interactively. A single authority, `core/env.is_interactive()`
  (precedence `SPEC_KITTY_FORCE_INTERACTIVE` > `SPEC_KITTY_NON_INTERACTIVE` > a
  real TTY), now backs that decision, and #2912 routed the four other divergent
  prompt-gates - `init`, the `merge` hollow-review confirm, the `intake`
  candidate picker, and `doctor` - through it too, so every prompt obeys the
  same rule (with `doctor` keeping its CI-environment veto layered on top). Also
  fixes the garbled interview hint menu where Rich was eating `[enter]`/`[text]`/`[d]`
  as style tags.

- **Merging an accepted mission no longer discards the acceptance and
  issue-matrix evidence recorded when it was accepted (#2804; scorer hardening
  #2912; landed by #2910).** `acceptance-matrix.json` and `issue-matrix.md` are filled on the
  target at accept time while the mission branch keeps empty scaffolds; the
  squash integration ran `git merge --squash -X theirs`, so the empty scaffold
  won the add/add conflict and the merged history kept blank gate artifacts -
  losing the audit trail exactly when a reviewer needs it. Two new custom merge
  drivers (`merge-driver-acceptance-matrix` / `merge-driver-issue-matrix`) now
  keep whichever side actually carries evidence - scored, not fixed-side, so it
  is correct whether the fill happened on the target or in a lane, with ties
  going to the target where accept ran. The scorers were then hardened (#2912) to
  read the scaffold marker from the field the scaffolder actually writes, and to
  resolve verdict/title columns by canonical header rather than fixed position,
  so a reordered or minimal matrix scores correctly. Seeded into `.gitattributes`,
  the `init` seed, and an upgrade migration for already-initialized repos -
  following the same pattern as the #2709 meta/traces drivers.

- **Lifecycle gates no longer emit a confident-but-wrong verdict when run from
  the wrong worktree, and a misclassified lock write no longer blocks a claim or
  merge (#1834, #2885, #2882, #2795).** Every lifecycle gate now receives an
  explicit execution context - which tree, which ref, which phase - and refuses,
  recording a clear cannot-evaluate diagnostic instead of a pass/fail, when that
  context is missing or inconsistent, rather than silently inheriting the
  caller's working directory and judging a fact about one worktree against
  another. Separately, `spec-kitty implement`/`merge` no longer wrongly report a
  work package as blocked because Spec Kitty mistook its own planning-partition
  lock write for a dirty tree (the #2795 claim-blocker, now topology-agnostic).
  Internally, eleven scattered gate-exemption predicates are retired onto one
  owner guarded by an exemption-registry ratchet, and the accept gate now
  asserts ref-agreement before it judges the acceptance matrix.

- **The `issue-matrix.md` and `acceptance-matrix.json` missing-file errors now name the regenerate command.**
  Both files are already scaffolded automatically during `spec-kitty tasks` (finalize-tasks); the failure messages an operator actually sees when one is missing (at `move-task --to approved` and at `spec-kitty accept`) previously said nothing about that, so a missing file read as "no tooling exists for this" rather than "re-run finalize-tasks." Both messages now name `spec-kitty agent mission finalize-tasks --mission <slug>`, and the issue-matrix message also points at its schema/worked-example doc (`src/specify_cli/cli/commands/review/ERROR_CODES.md`). The `spec-kitty-mission-review` skill's Gate 4 section gained the same pointer.

- **Windows backslash in git tree-path misreported committed specs as uncommitted (#2836).**
  `_git_commit_check_context` built the git tree path with `str(Path(...))`, which
  renders using the OS-native separator - a backslash (`\`) on Windows. Git's
  `HEAD:<path>` object syntax and `ls-files` pathspec require forward slashes, so
  both subprocess checks failed and `is_committed()` reported genuinely-committed
  spec files as uncommitted, blocking the setup-plan workflow (e.g.
  `/spec-kitty.plan` refusing to proceed). Both return sites now resolve through a
  single worktree-aware kernel seam (`kernel.paths.repo_tree_path`) that renders
  forward slashes on every host via `PurePosixPath`. Invisible on POSIX
  (macOS/Linux/CI) where `os.sep` is already `/`.

- **Posix path-separator normalization consolidated into one kernel seam.**
  The `str(x).replace("\\", "/")` idiom behind #2836 was scattered across ~17
  sites in `charter`, `mission_runtime`, and `specify_cli` (review, upgrade +
  migrations, merge, git, skills, status, paths, bulk_edit) - each an independent
  chance to reintroduce the Windows backslash defect. All now route through the
  behaviour-agnostic `kernel.paths.to_posix(path: Path | str)` seam (kernel being
  the zero-dependency root every layer can import downward), leaving the seam
  definition as the only `replace("\\", "/")` in `src/`.

- **`merge`'s hollow-review warning no longer flags a WP with a genuinely independent reviewer.**
  `force_count >= 2` alone can't distinguish "the reviewer used `--force` to bypass an unrelated gate false-positive" from "no independent review happened" - both increment the same counter. When the event log positively confirms a different actor logged the approving transition than the one that most recently implemented the WP, the warning no longer fires; absence of that evidence still warns as before (fail-safe default, never suppressed on uncertain data).

- **Honest force-provenance on evidence-gated backward edges (#2684, #2736, #2810).**
  Persisted `StatusEvent.force` is now truthful - falsy on the evidence-gated
  review-rejection edges (`build_transition_plan` asks the FSM instead of
  auto-promoting `force`) and truthful on genuine guard-bypasses (leaving a
  terminal `done`). Fixes the false-force stamp found during #2736 / PR #2810.

- **Off-axis emit sites resolve their write target from stored topology, never `Path.cwd()` (#2647).**
  Runtime-state events can no longer be written against the wrong feature
  directory when the CLI runs from a foreign working directory.

- **Rollback to `planned` releases the prior claim (#2512).**
  A rolled-back work package no longer retains a stale `shell_pid`/`agent` in the
  reduced snapshot, so the next resume/re-claim is not blocked by a dead claim.

- **Runtime-state backfill verify is now genuinely fail-closed on value tampering (#2684).**
  The parity check could silently pass a tampered value when a correcting seed annotation
  happened to sort last in a same-timestamp reduce fold (a content-hash-ULID coin-flip); it
  now flags any two annotations assigning different values to one slot as corruption,
  regardless of fold order. (The backfill CLI wiring itself remains deferred to #2816.)
  The runtime-state eviction also hardens the dual-write end-state: bypass frontmatter reads
  routed onto the gated snapshot seam, the phase-1 authority predicate split from the legacy
  lane-mirror, and the #2093 authority invariant asserted by imported-symbol identity.

- **Fresh-project `charter synthesize` no longer crashes after the `charter.yaml` inversion (#2800, #2773).**
  Post-#2773, `charter generate` stopped writing `charter.md`, but the fresh-project
  synthesize intercept still gated on `charter.md` being present - so on a real fresh
  project the intercept never fired and `charter synthesize` fell through to the production
  adapter, exiting 1 with `'str' object has no attribute 'get'`. The intercept now gates on
  the authoritative `charter.yaml` (what `generate` writes), restoring the fresh-project seed
  path and aligning with the inversion invariant that `charter.md` is display-only, never a
  resolving signal.
- **Pre-review regression gate no longer silently skipped by a leaked sync toggle in the parallel suite (#2800, #2794).**
  The gate reuses the sync layer's process-wide `SPEC_KITTY_SYNC_MINIMAL_IMPORT` /
  `SPEC_KITTY_SYNC_DISABLE` opt-outs; in a whole-tree `-n auto` run one could leak into an
  xdist worker and skip the gate, reding the gate-observability tests. An autouse fixture now
  unsets both toggles before every agent test, making them worker- and order-independent. No
  production behaviour change; the deliberate gate↔sync coupling is tracked for a dedicated
  opt-out in #2801.
- **CI test-suite remediation: stale fixtures from two recent merges brought back to green (#2800).**
  The `charter.yaml` consolidation (#2773) and the coord-rollback transactionality mission
  (#2786) merged with un-flagged test-fixture debt a CI path-filter hid until #2800 surfaced
  it: charter selection/bundle/synthesize/freshness fixtures still seeding the retired
  `governance.yaml`/`metadata.yaml` triad; arch-gate remainders (golden-count, tmp-literal,
  marker drift); a #2709 regression fixture missing the canonical `force` event field; and 89
  mechanical `mypy --strict` errors in the agent test package. Fixtures re-pointed onto
  `charter.yaml`, gates re-based, and tests whose premise encoded a retired flow removed
  outright per the standing-order §4 remediation framework (now amended to codify
  _superseded-design -> remove_). The legacy-topology bootstrap CWD gap a strict-xfail guards
  is now tracked in #2802.
- **Sync batch-400 poison isolation - one invalid event no longer strands its whole batch (#2736; closes #2755).**
  A whole-batch HTTP 400 with no per-event `details` made the CLI fan the batch-level error onto **every**
  event as `rejected` (non-terminal), so the culprit re-poisoned every subsequent drain and the innocents
  never delivered - the upstream cause of the `wp_status_event_without_create` projection anomaly. The
  receiver now recursively **bisects** a poison batch (`delivery/receivers.py`): split -> re-POST both halves
  -> recurse to singletons, isolating the culprit (kept `rejected`/retryable, never force-parked) and
  delivering every innocent, with create-before-status ordering preserved by sequential left-before-right
  recursion (and a split-point clamp so a same-`wp_id` create+status pair still terminates). The live
  offline-queue path (`sync/batch.py` `_parse_error_response` no-`details` branch) now dispositions a
  batch-level 400 as `failed_transient` (no `retry_count` bump) instead of poisoning innocents. A single
  shared `core/batch_partition.py` primitive (`split_in_half` + `create_aware_midpoint`) de-duplicates the
  batch-splitting math and **closes #2755** by retrofitting the 413 byte-shrink onto it, guarded by a
  behavioral + AST single-authority test. CLI-side only, no server-contract change; the SaaS
  transition-matrix and reducer alignment are tracked cross-repo (spec-kitty-saas#509 / #510).
- **Mission squash merge no longer clobbers target-newer acceptance provenance or traces (#2709).**
  The supported squash merge ran `git merge --squash -X theirs` on every conflicting file,
  silently reverting target-newer `meta.json` acceptance/VCS fields (and `traces/*.md`
  sections) to the older mission-branch copies, and the coord->target projection
  blind-overwrote the durable event log and `status.json`. Merges now reconcile **per
  artifact class**: planning artifacts stay mission-authoritative (`-X theirs` intent from
  #1732 preserved), while `meta.json` acceptance/VCS keys field-merge target-authoritative
  with `acceptance_history` unioned and `traces/*.md` do a line-level union - via new
  `spec-kitty merge-driver-meta` / `merge-driver-traces` git drivers whose activation is
  scoped to the ephemeral squash merge (they no longer leak into a later `auto_rebase`). The
  projection unions the event log via `merge_event_payloads` and rematerializes `status.json`
  from the reduced log instead of a blind copy. Seeded by migration `m_3_2_6`. Ships with a
  red-first reproduction and two class-closing architectural lints (no-blind-copy over the
  projection path + driver-registry completeness sourced from the canonical artifact-kind
  registry).
- **Merge rollback and `--resume` stay coherent after a failed target advance (#2711).**
  When target advancement failed after `approved -> done` events were committed to the
  coordination branch, rollback reverted only working-tree bytes - leaving a committed `done`
  opposed to a reverted working `approved` - and `spec-kitty merge --resume` re-emitted a
  fresh `done` (non-idempotent). Rollback now reverts the coordination `done` commit
  (coord-worktree `git revert`, sourced from the canonical write-target ref; never a raw
  `update-ref`), and `--resume` derives progress from the durable committed event log with
  `MergeState.completed_wps` demoted to an advisory hint - so committed and working status
  stay coherent and resume is `event_id`-stable. INV-5 (#1827) merge-phase ordering is
  preserved. Ships with a red-first reproduction and a resume non-reemission property guard.
  Tracked follow-ups: **#2786** (write a durable reconcile marker when the rollback revert
  itself fails) and **#2794** (a `SPEC_KITTY_SYNC_MINIMAL_IMPORT` test-isolation leak that
  skips the pre-review gate under the parallel CI suite).
- **A failed coordination-`done` revert during rollback no longer silently re-opens the
  #2711 split-brain (#2786), and the coordination write-set rolls back transactionally
  (#2367 Mechanism B).** When the rollback's coord-`done` `git revert` itself _failed_ (#2786),
  or when a merge aborted mid-way through `_record_merged_wps_done_for_merge` before any revert
  ran (#2367-B), rollback restored only working-tree bytes and left a committed `done` opposed to
  a reverted working `approved` - a silently-stranded split-brain. Rollback now **marks-not-raises**:
  a durable `MergeState.pending_coord_reconcile` marker records the stranded WP(s) - derived from
  the **committed** coordination ref (the reliable authority; a working-tree diff is empty at the
  revert-failure point) over _this merge's own_ pre-target `done` write-set, so a legitimately
  pre-existing-`done` WP is never re-stranded. `spec-kitty merge --resume` heals via a strand-gated,
  idempotent `git revert` (byte-stable on re-run), and `spec-kitty doctor coordination` detects the
  strand (re-verifying incoherence from the committed ref, not marker-presence) with a `--fix`. A
  behavioral class-closing guard reds if any of the seven `_restore_final_bookkeeping_snapshots`
  rollback sites (incl. the previously-unenumerated coord-reachable site) strands without marking.
  INV-5 (#1827) ordering preserved; happy-path merge byte-identical. Ships red-first repros for both
  mechanisms. Deferred with follow-ups: **#2797** (unify the two `git revert` transport legs into
  one shared helper). (**#2795**, #2367 Mechanism A - claim-time VCS-lock resync, was deferred here
  and has since landed in #2906, above.)
- **`--json` output is now plain regardless of terminal colour; CLI tests are colour-deterministic (#2632).**
  Under a colour-forcing harness (e.g. `FORCE_COLOR=3`) Rich syntax-highlighted `--json`
  output - splicing ANSI escapes into the payload so `json.loads` and `| jq` choked - and
  split literal substrings in styled human output, red-ing ~81 pre-existing tests. All CLI
  output now routes through a single canonical `CliConsole` seam
  (`specify_cli.cli.console`) whose machine-output methods (`emit_json`/`print_json`) are
  plain by construction, so `--json` is safe under any colour environment. Test determinism
  comes from toggling colour on that one shared object (`set_plain`), never from mutating
  `os.environ`. The whole CLI layer (~77 ad-hoc `Console()` constructions) was moved onto the
  seam - no shim - and an architectural guard forbids a raw `Console()` under
  `src/specify_cli/cli/`. Deferred non-CLI consoles (including an active `retrospective/cli.py`
  `--json` corruption vector) are tracked in #2634. ADR: `2026-07-14-1-canonical-cli-console-seam`.
- **Implement-loop friction quick-wins II (#2570, #2493, #2555, #2566, #2589, #2533, #2580).**
  Eight fixes that make lifecycle guards no-op-stable against their own runtime writes and the
  pre-review gate return real verdicts, each preserving the guard's true-positive:
  the lane allocator ignores the `shell_pid`/`base_*` WP frontmatter it just wrote (batch lane
  allocation needs no inter-commit); the analysis-report freshness check ignores pipe-table
  `[D]`/`[P]` status-marker churn from `mark-status`; the pre-review gate resolves `pytest` via
  `uv run` (a real verdict instead of a spurious `--force` on a green tree) and serializes
  concurrent runs behind a machine-wide lock whose acquire-timeout is decoupled from the run
  timeout; the `agent_profiles` manifest stores `output_path` repo-relative so `spec-kitty
  upgrade` is cross-machine deterministic; the issue-matrix approval error names the offending
  schema-drift column instead of a misleading "Missing rows"; bulk-edit inference no longer
  trips on ordinary refactor verbs while genuine bulk edits still trip; `setup-plan`'s first
  scaffold write returns `success` + `scaffold_only` (mirroring the specify twin) instead of
  reading as `blocked`; `move-task` routes coord-lane planning-artifact staging through the
  commit-router authority path (no lane `kitty-specs/` commit, STATUS_STATE placement
  byte-unchanged) and closes the 4th divergent `shell_pid` writer; and a solo PR-bound coord
  mission routes its empty-coord status surface cleanly to primary instead of tripping a
  split-brain warning. Successor to the loop-friction fast-follow; follow-ups filed for the
  topology-derivation revisit (#2602), de-god debt (#2603, #2604), the `implement --json`
  output contract (#2605), and worktree-aware `doctor tool-surfaces --fix` (#2613).
- **Implement-loop friction quick-wins (#2581, #2573, #2549, #2577).** Four independent
  loop-friction fixes: `mission create` / `spec-kitty specify` now derive the create-time
  topology from context - a non-primary feature branch without `--pr-bound` defaults to
  `single_branch` instead of minting a coordination branch the operator must manually flatten
  (primary branch, `--pr-bound`, and explicit `--topology` still default to `coord`);
  `move-task --to for_review` gains a `--skip-pre-review-gate` flag, honors the
  `SPEC_KITTY_SYNC_DISABLE` / `SPEC_KITTY_SYNC_MINIMAL_IMPORT` disable env, and surfaces a
  progress notice so the scoped-test gate no longer reads as a hang (the full async redesign
  stays deferred on #2573); `finalize-tasks --json` reports per-branch commit hashes
  (`commit_hashes`) for the two-branch coord-topology commit set instead of a single
  `commit_hash` that omitted the coordination-branch commit (#2549 facet B; facet A deferred);
  and `charter synthesize` no longer fails closed on an empty/first-run config demanding a
  companion tactic for every built-in directive - first-run parity restored (#2526 regression).

- **Coord-shadows follow-ups: canonical-source consolidation + gate/liveness robustness
  (#2574, #2575, #2576, #2567, #2568).** The triplicated subtask-gate-dir resolver is unified
  onto one `resolve_subtasks_gate_dir` seam with the strong git-ancestry fallback (the weak
  `status_transition` site no longer reads a stale coordination husk); `core/process_liveness`
  guards against PID reuse via a persisted creation-time baseline co-written at every claim site
  (a recycled PID no longer reads as a live claim); the rollback-uncheck write routes through the
  house path-guard and surfaces failures instead of silently leaving checked rows; the acceptance
  gate's stray checkbox parser is migrated onto the canonical `core/subtask_rows`; and the review
  lock folds onto the canonical `is_process_alive` (last stray `os.kill` liveness probe removed).

- **Coord-shadows-primary read/gate arm closed (#2502, #2504, #2510, #2512, #2513, #1231).**
  The `for_review` subtask gate no longer fails open: `_infer_subtasks_complete` reads the
  PRIMARY planning surface at every emit-layer caller and blocks on unchecked rows on both the
  native `agent status` and orchestrator-api paths (the redundant #2511 per-door pre-derivation
  is retired). A single canonical `core/subtask_rows._walk_wp_section` now defines a WP subtask
  row for the guard, the dashboard count, and rollback-uncheck (the writer no longer re-enters a
  re-appearing `## WPnn` heading). A recovered coordination-topology lane re-registers its
  sparse-checkout and leaks no `status.events.jsonl`/`status.json`. Process liveness is promoted
  to `core/process_liveness.is_process_alive` (with a `sync/daemon` re-export alias) so the
  stale-WP indicator suppresses false-stale for a live claim. Freshness-hash checkbox-insensitivity
  (#1764) is pinned by a regression guard; #1862 is verified-already-fixed.

- **Arch-suite warnings remediated at root (#2553, #2554).** Report-only diagnostics
  (migration patch-skips, duplicate-gate selection, ratchet shrinkage, legacy-contract
  backfill) are routed off the `warnings` channel via `record_property` (signal
  preserved, no blanket `filterwarnings=ignore`); a Toolguide model-vs-schema drift is
  fixed so `terminology-guard.toolguide.yaml` validates (clearing the `base.py` skip
  warning); and three agent profiles now cite `bdd-scenario-lifecycle` as a _procedure_
  rather than a tactic (clearing `CharterCatalogMissWarning`).
- **Coord-authority `safe_commit` misfired on a coordination-husk identity read
  (#2508).** Identity-meta was read off the coordination husk rather than the primary
  checkout, so `safe_commit` could target the wrong tree; the read now anchors on the
  primary checkout (`_load_coord_branch_meta` / `_commit_workflow_change`). Pinned
  red-first by a dedicated regression that fails against the pre-fix code.
- **orchestrator-api `transition` no longer lets WPs into `for_review` with
  unchecked subtasks (#2510).** The command trusted a caller-asserted
  `--subtasks-complete`; left unset, emit-time inference read `tasks.md` off
  the STATUS feature dir - the coordination worktree husk mid-mission, where
  the PRIMARY-partition `tasks.md` never exists - and **failed open**,
  silently bypassing the subtask guard native `move-task` enforces (field
  evidence: four WPs reached `done` with 0/16 rows ticked, `force=false`).
  Mirroring the command's own commit-gate precedent, the API now derives the
  value server-side from the PRIMARY planning surface when the caller doesn't
  assert it; explicit assertions keep working and `--force` keeps its bypass.
  Fifth member of the coord-shadows-primary class
  (#2331/#2430/#2502/#2508).

- **Dashboard artifact viewers no longer render empty for in-flight
  coordination missions (#2502).** #2431 re-anchored the mission _list_ and
  _kanban_ to read planning artifacts primary-first, but the viewer endpoint
  family (`/api/research`, contracts/checklists listings, the spec/plan file
  server) still resolved the feature dir through the coord-first resolver -
  landing on the status-only coord husk, so clicking spec/plan/research on a
  running mission showed nothing while the board showed the work. A new
  `resolve_feature_planning_dir()` composes the coord-first resolver with the
  primary-first planning re-anchor; all viewer endpoints use it, and
  `handle_kanban`'s split reads are made explicit (legacy-format check =
  planning surface; weighted-progress read stays on the coord-first status
  surface). Finished missions were unaffected (their coord worktrees are
  gone), which is why the gap only showed mid-run - the same "broken precisely
  while running" shape as #2430.

- **Agent context payloads no longer lose their `Profile-Cited Directives`
  and `Tactics` anchors when the token budget trims a section (mission
  `charter-sole-door-bypass-closure`).** When the token-budget algorithm
  substituted a section for a shorter fetch-command stanza, it deleted the
  section's own header line along with its body - so a governance payload
  that ran over budget could silently lose the
  `Profile-Cited Directives (<profile>):` and `Tactics:` anchors an agent
  reading the payload needs to find the section it wants. The budget
  algorithm now keeps each populated kind's header intact and swaps out only
  its body.
- **`spec-kitty agent tasks status` no longer silently degrades the board on
  a malformed `.kittify/config.yaml` (mission
  `charter-sole-door-bypass-closure`).** Previously, a broken activation
  config (for example, `activated_agent_profiles` set to something other
  than a list) was swallowed by a blanket exception handler, and the
  command rendered a status board with no human-in-charge marker and no
  indication anything was wrong. It now surfaces the underlying
  `CharterPackConfigError` as a structured error instead of degrading
  silently - you'll notice this as a new, explicit failure where the
  command previously ran quietly with missing markers.
- **Bump `cryptography` floor to `>=50.0.0`, fixing CVE-2026-69247 (`#3181`).**
  `cryptography` is the dependency behind AES-256-GCM + scrypt KDF encrypted
  auth session storage; the previously locked `49.0.0` was affected. There is
  no user-facing behavior change - encrypted session storage keeps working
  exactly as before, just on a patched dependency version. Run
  `spec-kitty auth status` after upgrading if you want to confirm your stored
  session is still recognized; _no re-login is required_.

### ♻️ Changed

- **The test suite is leaner and its CI ownership is explicit (mission
  `assertive-test-suite-sanitation`).** Removed permanently inert tests,
  dominated duplicates, historical shape/count pins, stale scaffolds, and
  non-causal structural scanners while preserving reviewed live-path and
  planted-fault guards. The shared pytest environment now publishes a validated
  staged build with lease heartbeats, eliminating the `#3283` sibling timeout
  cascade. Regression remains a generic blocking marker route with honest
  empty-set handling; quarantine remains an empty Tier-3 visibility route whose
  owner manifest is checked against repository-wide marker discovery. The
  original `doctor restart-daemon` NFR-002 ≤10-second shared-runner wall-clock
  claim is explicitly retired; its controlled Linux lane now enforces
  distinct-PID restart and healthy-control-plane behavior under bounded
  operation timeouts. Hosted-macOS performance evidence is deferred to a
  controlled developer/canary harness rather than shared-runner wall clock.
  The integrated census records 36,013 nodes / 2,667 Python test files versus
  the frozen 37,444 / 2,731 baseline, with every frozen candidate terminally
  owned.

- **The `doctrine` module now has a curated, enforced public API surface, so
  runtime code imports it through stable doors instead of reaching into its
  internals (mission `doctrine-public-api-surface`; `#3179`, closes the
  runtime→doctrine half of `#2986`).** A new `doctrine.api` manifest names the
  symbols the future `spec-kitty-doctrine` wheel will export, the `charter.*`
  facades re-export them by object identity, and ~34 `specify_cli` modules move
  off direct `doctrine.*` imports onto those facades. A lazy-import ratchet plus a
  source-side laundering guard keep new reach-through from creeping back in. This
  is an internal architecture boundary only — no CLI command, output, or runtime
  behavior changes — and it unblocks the `#3101` doctrine wheel cutover.
- **The contributor planning surface (`docs/plans/`) gains durable, version-spanning
  _domain plans_ and a curated index (`#3324`).** Two domain throughlines — SaaS & hosted sync,
  and doctrine & charter — now hold the standing strategy and invariants for their
  surface across releases, distinct from the release-scoped `3.2.x` plans that retire
  once distilled. The plans index is reorganized into domain throughlines, portfolio &
  milestone planning, and a single working-collections list; loose top-level notes are
  filed into their subject subdirectories; and subdirectory landing files are
  standardized on `index.md`. This is an internal contributor-facing change — the CLI
  and templates are unaffected.
- **The beginner guides now open with illustrated Mission Kitty splashes, and the
  Spec-Driven Development page carries a real diagram instead of ASCII art
  (`#3276`).** Getting Started, Understanding Missions, Your First Mission, and
  When to use Spec Kitty modes each gain a hero illustration; When to use modes
  adds a four-path comparison board; and the SDD workflow — previously a plain
  ASCII box diagram — is now a styled SVG flowchart that renders cleanly in light
  and dark mode. The guide prose also switches to native DocFX alerts
  (`> [!NOTE]` / `> [!TIP]`) so callouts stand out on the published site. Where a
  stylized splash shows a workflow-like board, a one-line caption points to the
  authoritative steps, modes, or mission types on the same page, so the artwork
  reads as illustration and the page text stays the source of truth. The written
  content and structure are unchanged; the pages are just easier to scan.
- **Spec Kitty's documentation now lives under one predictable `docs/` root with
  canonical sections, so you can find a page by where it logically belongs
  (mission `common-docs-convergence`; `#2215`, `#2887`, `#3273`).** The scattered
  root folders (`research/`, `examples/`, `glossary/`, `media/`) and the duplicate
  `reference/` vs `api/` split are gone. How-tos are now organised by audience —
  user how-tos under `guides/`, contributor how-tos under `development/` — each
  subdivided by concern behind a single landing page, so you reach what you need
  in fewer clicks. Old documentation URLs redirect to their new homes, so existing
  links and bookmarks keep working. Every page now declares its intended reader
  and Divio type, and the architecture docs present one living design with prior
  versions filed as ADRs.
- **Dead queue-backed event-drain code removed from `sync/batch.py`, closing a
  latent consent-bypass path (mission `chain-b-consent-bypass-3167`; `#3167`,
  `#3190`, `#3187`, `#3220`).** `batch_sync` and `sync_all_queued_events` had no
  production caller - the journal dispatcher remains the only event drain Spec
  Kitty actually uses - but if either were ever reconnected, they could send a
  project's events without checking that project's consent first. Both are
  deleted, along with 31 supporting symbols and 91 test nodes that existed only
  to serve them, and the now-inert `E15` egress-allowlist entry is removed. A
  `tests/sync` autouse fixture that had been silently granting "consent" to
  almost every test in the folder - which is why this gate went uncovered for
  as long as it did - no longer patches the removed seam. No behaviour changes
  for existing projects.
- **Doctrine-pack resolution and charter activation now run through a single
  authority (mission `resolution-activation-foundation`; `#2657`, `#3210`).**
  One kernel primitive resolves the packs root and honours
  `SPEC_KITTY_PACKS_ROOT` for every reader - the duplicate runtime `home.py`
  resolver is collapsed onto it - so resolution can no longer diverge between
  call sites. Fresh `spec-kitty init` provisions the default charter by
  deterministic copy instead of re-scanning, so a freshly initialised project
  and a migrated one start from an identical charter. The provisioned charter
  is the sole authority for what is activated, and an unresolved mission-type
  now fails closed at the create/use boundary instead of resolving implicitly.
  Existing projects need no action.
- **The event log is now the single authority for a work package's review
  verdict; the review-cycle `.md` no longer carries one (mission
  `verdict-seam-write-unification-01KZ9Q35`).** Every verdict reader and merge/
  review gate resolves the event-sourced `review_result` slot in
  `status.events.jsonl`; the `review-cycle-N.md` frontmatter `verdict` field is
  retired, and durability moved to the event log (the `.md` write is now
  best-effort). To keep existing projects safe across this reader collapse, a
  new auto-discovered upgrade migration (`verdict_provenance_backfill`) runs on
  `spec-kitty upgrade` and backfills each mission's stranded terminal `.md`
  verdict into the event log (FR-012/SC-008); it is idempotent (keyed on a
  deterministic ULID) so re-running `upgrade` is safe. `spec-kitty accept`
  carries a non-blocking diagnostic that names any still-stranded WP and points
  at `upgrade`. Runbook:
  [`docs/migrations/verdict-provenance-backfill.md`](../migrations/verdict-provenance-backfill.md).
  _No `pyproject.toml`/`__init__.py` version bump accompanies this entry: the
  mission changed only the `status/__init__.py` facade, not the CLI entry
  point, so a CHANGELOG entry without a version bump is correct here._

- **Built-in mission data now ships under `packs/built-in/missions/`, alongside
  every other built-in doctrine kind (mission
  `doctrine-consumer-surface-missions-extraction`; `#3091`).** The mission-type
  profiles, step prompts, step contracts, and per-type content that previously
  lived embedded in the `doctrine` Python package at `src/doctrine/missions/`
  now resolve from the shippable `packs/built-in/missions/` location; the 11
  `.py` logic modules stay in place as an ordinary package. Every reader -
  across kernel, doctrine, charter, `specify_cli`, and the upgrade migrations -
  was repointed in one atomic change, and mission-asset resolution now targets
  the pack location explicitly so it can no longer silently fall back to the
  (now data-less) package directory in a built/wheel layout. No user action is
  required: `spec-kitty init` and mission resolution behave exactly as before,
  and the regenerated DRG graph fragments are byte-identical.
- **Mission-asset resolution is now a single doctrine-agnostic kernel primitive
  (mission `doctrine-consumer-surface-missions-extraction`; `#3091`).** The
  kernel's built-in-content lookup no longer hard-codes the `doctrine` package
  name or mission-type vocabulary; `doctrine/pack_paths.py` and
  `MissionTemplateRepository.default_missions_root()` converge onto that one
  primitive, guarded by a kernel-scoped architectural test that fails on any
  reintroduced `kernel -> doctrine` edge.
- **Retrospective policy set in `charter.yaml` now takes precedence over
  `charter.md` frontmatter (mission `doctrine-charter-split-unification`).**
  If both files configure retrospective behaviour and they disagree, the
  compiled `charter.yaml` value now wins - matching how every other
  charter-governed decision already resolves. Projects that configure
  retrospective policy only via `charter.md` frontmatter (no `charter.yaml`
  retrospective block) are unaffected and keep resolving from the markdown as
  before.
- **Internal: doctrine/charter changes now get a dedicated, path-filtered CI
  workflow (mission `charter-pack-usage-journey`; `#3102`).** A PR that touches
  only `src/doctrine/**` / `src/charter/**` (or touches neither) now runs the
  DRG-freshness, charter-context-resolution, and architectural/adversarial
  checks for that layer in an isolated workflow instead of paying for the full
  suite - faster, more targeted feedback for doctrine/charter work, no change
  for unrelated PRs. The `charter pack apply` -> `charter generate` two-step and
  the empty-charter dispatch-safety-net behaviour are also now documented in
  the charter journey guides (`#3107`).
- **The `charter/context.py` god-module was decomposed 3243 -> 570 lines (mission
  `charter-delivery-finish-context-degod`; `#2532`).** The charter-context
  engine - previously a single 3243-line module - is now a thin orchestration
  surface delegating to 16 focused sibling modules under `src/charter/`
  (catalog diagnosis, token budget, artifact bodies, selection rendering,
  activation, bootstrap text, compact governance, JSON builder, profile
  resolution, doctrine-service builder, ...), and a long-standing internal import
  cycle is dissolved. This is a pure maintainability change: a byte-for-byte
  parity fixture over the three public entry points (`build_charter_context` /
  `_include` / `_json`) is green before and after, and a completion gate asserts
  each seam is really used. No behaviour or output changes.
- **Glossary-term casing gate is prose-only; the baseline ratchet is retired (#2830, #2823).**
  All pre-existing non-canonical glossary-term casing across `docs/` prose was paid down and the
  frozen baseline (`tests/architectural/glossary_canonical_terms_baseline.txt`) deleted, so
  `test_glossary_canonical_terms.py` now enforces **zero** non-canonical occurrences in scanned
  prose instead of freezing an escape hatch. The gate skips fenced code blocks and inline-code
  spans (captured CLI `--help` output and emitted-string literals keep their real casing) and
  exempts the historical `docs/adr/` and `docs/changelog/` trees. Also refreshes the `AGENTS.md`
  Canonical Kind Vocabulary table: charter-activatable tokens now list `procedure` (not
  `template`) and add `glossary-pack`; `template`, `asset`, and `anti_pattern` remain
  `ArtifactKind` members but are **not** charter-activatable (excluded via
  `_NON_AUGMENTATION_ELIGIBLE_KINDS` - this is a governance clarification, not a kind
  rename). Retires the Contextive generated-file staleness test.
- **The docs anti-sprawl structure ratchet (R1) is retired (#2851 follow-up).** The per-PR
  blocking `anti_sprawl_ratchet.py --strict` step is removed from `docs-freshness.yml`, and
  the script plus its orphaned `doctrine.directives.common_docs` constant (its only consumer)
  and self-test are deleted. `DIRECTIVE_042`'s single-root / 13-section / no-shadow-tree policy
  is unchanged - it remains a red-line integrity rule - but is now maintained by periodic bulk
  curation rather than a per-PR CI gate, matching the operator's bulk-remediation ops intent and
  trimming a blocking CI step. The other docs rulers (R2 related-edge validator, R3 lockfile
  freshness, description-length and body-link gates) are unaffected and stay blocking.
- **Runtime-state corpus cutover completed; the phase-1 dual-write flag is deleted (#2816, #2848).**
  Completes the #2684 / #2093 eviction. WP runtime state - lane, claim, `agent`/`assignee`,
  `shell_pid`, subtask completion, `tracker_refs`, review-cycle fields, and resolved
  role/profile/model bindings - is now **unconditionally** reconstructed from the append-only
  event log through a single reader (`reconstruct_wp_view`); the `_phase1_dual_write_enabled`
  flag and the legacy frontmatter-runtime fallback are removed, so `tasks/WP##.md` frontmatter
  is no longer a runtime authority. The existing corpus was migrated (per-mission `backfill ->
  verify -> status_phase` flip). Adds **`spec-kitty migrate backfill-runtime-state`**, which
  seeds a mission's legacy runtime as events, verifies the reduced snapshot against the old
  reader by count + value (fail-closed - never flips a mission that fails verify; per-mission
  best-effort), and flips `meta.json` `status_phase` to snapshot-authority only for verified
  missions; the same seed->verify->flip path ships as an auto-discovered upgrade migration for
  consumer repos.
- **Skill projection delivers copies, never absolute symlinks (#2412, ADR 2026-07-19-1).**
  Projected skill files under `.claude/skills/`, `.agents/skills/`, etc. used to be
  absolute symlinks into the user-global canonical root - which dangle when the repo
  is mounted into a dev-container or synced to a remote box, are unreadable to agent
  harnesses sandboxed to the repo root, and all break at once if the global root
  moves. `_project_skill_file` now always delivers a real copy (the pre-existing
  Windows fallback path, promoted): hash-equal destinations are left untouched
  (idempotent re-runs), legacy symlinks are replaced with copies organically on each
  project's next init/upgrade/repair run (no migration needed), and `repair_skills`
  always repairs to a copy, healing pre-existing `delivery_mode: symlink` manifest
  entries as it goes. Freshness is preserved because every install run re-projects
  the full skill set; copies inherit the canonical root's read-only mode. Supersedes
  the per-project-symlink half of ADR 2026-04-08-3 (the global canonical root is
  unchanged).
- **`charter generate` seeds a starter `charter.md` companion when absent (#2800).**
  After the #2773 inversion `charter generate` produced no `charter.md` at all, leaving a
  fresh project without the display-only rationale companion and no signal one should exist.
  `generate` now writes a minimal starter `charter.md` **only when the file is absent**
  (create-if-absent); an existing curated companion is left byte-for-byte untouched,
  preserving the #2772 never-clobber invariant. `charter.md` remains display-only, never a
  resolving input. ADR 2026-07-18-1 amended.
- **Internal: the `specify_cli` aware-UTC clock contract is now enforced structurally
  (#2496).** Follow-up to #2494's clock-consolidation sweep. Routes the remaining
  byte-identical `datetime.now(UTC).isoformat()` "now"-stamp call sites in `specify_cli`
  onto the single canonical `now_utc_iso()` helper, the canonical producer of that form.
  Behaviour-preserving: the `UTC` / `timezone.utc` spellings serialize byte-identically
  under `requires-python >=3.11`. Adds an **AST negative gate** over the whole
  `src/specify_cli` tree (`tests/specify_cli/test_clock_consolidation.py`), alongside
  the pre-existing owned-file inventory, so a module added later is covered the moment it
  lands rather than silently regressing while the suite stays green; the gate ships a
  self-mutant non-vacuity test and a stale-exemption check. It targets the fluent
  single-expression `<x>.now(<aware-UTC>).isoformat()` idiom (import aliases resolved);
  distinct contracts are deliberately out of scope and not flagged: the second-precision
  `%Y-%m-%dT%H:%M:%SZ` stamp family, `isoformat(timespec=...)`, naive `now()`, the
  datetime-returning family, and non-fluent forms (a variable-split or a space-separated
  `str()` of an aware instant).
- **Internal: the coord-authority trio is decomposed into ports + pure cores
  (#2464, #2465).** The three coord-authority god-modules are restructured
  behaviour-preservingly into the shipped Typer-shell + request-dataclass + pure-cores
  (ports injected) + executor pattern - following `MissionResolver` (#2494) and
  `tasks.py` (#2308): `workflow.py` -> `workflow_cores.py` + `workflow_executor.py`,
  `implement.py` -> `implement_cores.py` (a `GitPort` injected and two `# noqa: C901`
  suppressions removed), and `acceptance/` -> `summary_core.py` + `gates_core.py`. The
  trio's leaf resolvers now consume the kind-aware placement seam, preserving all three
  (lenient) read contracts (#2465). No user-facing behaviour change; pinned by
  seam-only + cores-no-I/O architectural tests and a characterization safety net over
  implement / review / accept / next.
- **Read-side placement seam closure: the last unpoliced primitive is gone
  (#2886, #3014; closes the read-side placement-seam migration opened by
  #2922/#2921).** The #2922 migration above left one gap on purpose - its own
  gate coverage bounds named `primary_feature_dir_for_mission` as unpoliced,
  because the wrapper itself, and the ~34 call sites still composing a
  mission's primary directory by calling it directly, hadn't been routed
  through the seam yet. They are now: every one of those call sites asks
  `placement_seam(root, slug).read_dir(<kind>)` for the artifact kind it
  actually wants, instead of asking a topology-blind wrapper to guess a path
  from a slug. The terminal `KITTY_SPECS_DIR` assembler survives as the
  seam's own module-private leaf - the one place still allowed to compose a
  path, because something has to. One behavioural nuance was accepted rather
  than papered over: on a backfilled mission where the old blind composition
  returned a directory that does not exist, the seam now recovers the real
  bare-`<slug>` directory instead of repeating the miss (identity-confirmed,
  not just path-shaped). A new architecture reference,
  [`docs/architecture/artifact-placement-seam.md`](../architecture/artifact-placement-seam.md),
  documents the L0-L4 read-placement layering end to end; `branch-target-routing.md`
  is narrowed to the branch-target sense now that placement has its own home.
  Governed by ADR
  [2026-06-24-1](../adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
  and ADR
  [2026-07-23-1](../adr/3.x/2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md);
  no new architectural decision was needed.
- **Activating a subset of directives, tactics, styleguides, toolguides,
  mission-step contracts, or glossary packs now actually narrows what your
  project sees - it didn't before (mission `charter-sole-door-bypass-closure`).**
  If your `charter.yaml`/pack config selects only some of a pack's
  directives (or tactics, styleguides, toolguides, mission-step contracts,
  glossary packs), the runtime, CLI, and rendered context now consistently
  show only the selected set for those 6 kinds. Previously this filtering
  only worked for `paradigm`, `procedure`, and `agent_profile` - the other 6
  kinds fell through unfiltered, so a deactivated pack could still show up.
  Mission-type selection was already honoured before this mission; it is
  now covered by regression tests confirming that. **If you haven't
  configured any activation selection, nothing changes** - a
  bare/unconfigured project's result set is unaffected. One deliberate
  exception: `.kittify/profiles` (a local-override directory outside the
  doctrine activation model) is explicitly still unfiltered by this
  change - a scope call, not a missed site; that area is slated for
  separate future rework.

  Under the hood, this closes every **enumerated direct-construction and
  `._inner` bypass** around the charter's `DoctrineService` factory and
  extends activation gating from 3 kinds to all 9 charter-activatable kinds
  plus the `mission-type` token. It does **not** close the full ~20-door
  list: `doctrine.template_catalog.resolve_template_by_id` (5 importers),
  `specify_cli/runtime/resolver.py`'s tier-1-4 reimplementation,
  `runtime/home.py`'s `importlib.resources` root lookup, three
  root-relative missions-root duplicates, and one escalated
  `AgentProfileRepository` site (`tool_surface/profiles/projection.py`)
  remain - each named in the mission spec and tracked as its own follow-on
  (#3176 for the last). This mission also promotes
  `MissionTemplateRepository.default_missions_root()` as the single shared
  missions-root authority and retargets two duplicate hardcoded path
  constructions onto it, but that consolidation does **not** claim
  convergence with `doctrine.pack_paths.built_in_dir` - full convergence
  remains `#3091`'s to deliver.

  **One more consumer-visible narrowing, for projects that declare
  languages.** If your project's compiled `charter.yaml` records a
  `catalog.languages` answer (i.e. you already went through the charter
  interview or `charter sync`), language-scoped agent profiles now filter
  consistently through the factory - previously, one of the two
  divergent builder paths this mission unifies did not apply that filter
  at all, so a language-scoped profile could show up even for a language
  your project doesn't use. Measured on this repository's own root
  (`catalog.languages: [python]`): the built-in agent-profile catalog
  narrows from 18 profiles to 15 - `frontend-freddy`, `java-jenny`, and
  `node-norris` no longer resolve, because they're scoped to languages
  this project doesn't declare. `python-pedro` still resolves. This is
  intended, not a regression (FR-008's "fuller behaviour on each axis"):
  if you relied on an off-language profile resolving anyway, activate it
  explicitly rather than depending on the prior inconsistency. Projects
  with no compiled `languages` answer are unaffected - see above.

### 💥 Breaking Changes

- **Built-in doctrine content moved out of `src/doctrine/` into a top-level
  `packs/built-in/` pack root (mission `relocate-builtin-doctrine-packs`).**
  The shipped built-in artefact _data_ (directives, tactics, procedures,
  paradigms, styleguides, toolguides, agent profiles, glossary packs, assets,
  and the per-kind `*.graph.yaml` DRG fragments) no longer lives inside the
  `doctrine` Python package. The layout is **flattened**: the old
  `src/doctrine/<kind>/built-in/<file>` home loses its inner `built-in/` segment
  and becomes `packs/built-in/<kind>/<file>`; the sharded fragments move from
  `src/doctrine/<kind>.graph.yaml` to `packs/built-in/<kind>.graph.yaml`. All
  three tiers now resolve the built-in root through a single fail-closed seam,
  `resolve_pack_root("built-in")` (`src/doctrine/pack_paths.py`); the DRG seam
  `built_in_graph_source()` yields the `packs/built-in/` directory. Doctrine
  `.py` code, `schemas/`, `templates/`, `skills/`, and the `missions/` tree do
  **not** move and remain under `src/doctrine/`. There is **no compatibility
  shim** - repoint any reference to the new path (drop the inner `built-in/`).
  The wheel/sdist ship `packs/` as a site-packages sibling of `doctrine`.
  Follow-ons are tracked: Phase 1b relocates `missions/` (#3091); Phase 2
  converges the built-in loader/schema onto the org-pack contract. See
  [docs/migrations/relocate-builtin-doctrine-packs.md](https://github.com/Priivacy-ai/spec-kitty/blob/main/docs/migrations/relocate-builtin-doctrine-packs.md).
- **`primary_feature_dir_for_mission` is removed; importing it now raises
  `ImportError` (#2886, #3014).** It was the last kind-blind wrapper left over
  from before the read-side placement seam (#2922): callers passed it a slug
  and it guessed a mission's primary directory by path composition, with no
  artifact-kind awareness and no way to fail loud when the guess was wrong. The
  invariant "reads go through the seam" is now structural rather than
  counted - there is no bypass left to police, so the gate that used to name it
  as an accepted gap has nothing left to accept. If you imported this function
  directly (an internal API, but importable), replace the call with
  `placement_seam(root, slug).read_dir(<kind>)` for the artifact kind you
  actually need; see the Changed entry above and
  [`docs/architecture/artifact-placement-seam.md`](../architecture/artifact-placement-seam.md)
  for the read-placement layering it now goes through.
- **An org doctrine pack whose agent profile carries an unrecognised key now
  fails to load (mission `doctrine-silence-guards`).** Agent profiles and DRG
  nodes and edges used to accept keys the code did not know about and drop them,
  so a typo or a key retired in an earlier release produced an artifact that
  looked complete and behaved differently from how it read. Those keys are now
  rejected outright. Silently dropping them is the defect being closed, so this
  is deliberate - but **if you maintain an org pack, check it before you
  upgrade**: run `spec-kitty doctor doctrine --json` and read the
  `skipped_profiles` list. A pack containing an invalid profile is reported
  unhealthy rather than crashing the command or passing as healthy. The
  blast-radius check for this change covered this repository only; packs outside
  it were not surveyed.
- **Cross-pack references in an org pack must now be written in full.** An edge
  endpoint in a pack's `drg/` fragment is either `<kind>:<id>` - for example
  `styleguide:acme-sty-001` - or a bare id declared in that same fragment's own
  `nodes:` block. A bare id no longer resolves against a _different_ pack in the
  same merge. That old behaviour made the resulting graph depend on the order
  packs happen to be listed in `organisation_packs:`: the same two packs in two
  orders produced two different graphs, and nothing was reported either way. An
  endpoint that cannot be resolved is now refused at merge time with an
  `unresolved_edge_endpoint` conflict naming the token, instead of being dropped
  or silently re-pointed at an invented node. See
  [the org-pack authoring guide](../guides/how-to/governance/create-an-org-doctrine-pack.md).
- **A push to a protected branch now starts 49 of 50 test jobs instead of about
  10.** Pull requests are unaffected - path filtering still narrows a PR to the
  suites its diff touches. This is a deliberate trade of CI minutes for
  coverage: filtering is a pull-request optimisation, and the protected branch
  is precisely where the frozen contracts have to actually run. See the #2957
  entry under Fixed.
- **`spec-kitty doctor doctrine` now fails when an org pack declares an edge
  endpoint that resolves to nothing.** The dangling endpoints are listed in the
  report and the command exits non-zero. `charter status` reports the same
  problems in its `errors` array but deliberately keeps exit code 0 - it is a
  reporting surface, not a gate, and scripts that treat its exit code as a pass
  or fail signal are unaffected.
- **The `rtk-search-tooling` toolguide is removed, including from the default
  charter pack - an upgrade migration cleans up projects that already have it
  activated.** RTK is fiddly to set up correctly and can materially change how
  a project's tests execute, so shipping it as an artefact every new project
  activates by default was a liability rather than a service. The toolguide,
  its guide document, and its node in the doctrine graph are gone, and it no
  longer appears in `src/charter/packs/default.yaml`.

  This is a breaking removal for existing projects because of how the entry got
  there. The 3.2.0rc35 default-pack migration copied the pack's
  `activated_toolguides` list verbatim into each project's
  `.kittify/config.yaml`, and by design only ever writes keys that are
  _absent_ - so no later upgrade would have taken a retired member back out.
  Charter compilation is deliberately fail-closed and refuses to quietly skip a
  reference it cannot resolve, so a project left holding the stale entry would
  hard-fail on the next compile with `UnknownArtifactIdError: No toolguide
  artifact with config ID 'rtk-search-tooling' found`.

  The new `3.2.6_retire_rtk_search_tooling` migration removes the entry from
  `.kittify/config.yaml` and strips the matching compiled blocks from
  `.kittify/charter/charter.yaml` and `.kittify/charter/references.yaml`, which
  would otherwise still name a source file that no longer exists. It runs
  automatically on `spec-kitty upgrade`, does nothing on a project that never
  had the entry, and is safe to run more than once. If you deliberately want
  RTK guidance, keep it in your own org doctrine pack.
- **Local tracker providers (`beads`/`fp`) now require a recorded egress
  decision, and absence of both channels denies (mission
  `tracker-egress-refusal-3108`).** Every `spec-kitty tracker sync
  pull`/`push`/`run` on a local binding used to ship issue titles, bodies,
  labels, and assignees as `argv` of an operator-named executable
  (`tracker/factory.py`'s `command` key, defaulting to `bd`/`fp`) with no
  consent check at all — a committed `sync.enabled: false` did not stop it.
  It is now gated by a join of two independently-recorded consent channels:
  **Channel 1**, the existing hosted-sync consent chain (`sync.enabled` /
  `spec-kitty sync opt-in`), and **Channel 2**, a new `tracker.egress` key
  (`refused` / `permitted`) in the project's own committed
  `.kittify/config.yaml`. At this destination Channel 2 is two-way: a
  recorded `permitted` grants local sync independently of Channel 1, because
  the subprocess involved is the operator's own machine, never spec-kitty's
  hosted service; a recorded `refused`, or absence at _both_ channels,
  denies. **This is the breaking change:** an existing `beads`/`fp` binding
  that has never recorded hosted-sync consent and has no `tracker.egress` key
  stops syncing on upgrade until one of the two is recorded — record
  `tracker.egress: permitted` to keep syncing without consenting to hosted
  sync at all, or run `spec-kitty sync opt-in` / record `sync.enabled: true`
  to consent to hosted sync instead. Absence denies by design, but the
  two-way local grant is the deliberate escape from a coercion the old,
  ungated behaviour otherwise implied: without it, "consent to hosted sync or
  lose your local tracker" would be the only way to keep a `beads`/`fp`
  binding working, and recording `tracker.egress: permitted` is never a
  de facto opt-in to hosted sync — it grants the local subprocess path only.
  Only `sync pull`/`push`/`run` are gated: `tracker bind`, `status`, `unbind`,
  and `map add` stay available on a refusing project, and a local `beads`/`fp`
  `bind` no longer needs hosted authentication to run — an unauthenticated
  project can still bind and use a local tracker. The refusal is also raised
  before any network probe, so a refused hosted sync makes no HTTP request to
  the tracker host at all. See
  [the upgrade note](../migrations/tracker-egress-refusal.md) for the full
  remediation paths.

  <!-- WP04 review, HIGH-1 (named, both-ends window — same pattern as the
       WP02→WP04 A1 window): the link above is deliberately forward. It
       resolves once WP08 lands `docs/migrations/tracker-egress-refusal.md`,
       not before, and until then it reds `tests/docs/test_relative_link_fixer.py`:
       `TestLiveTreeGate::test_assembled_tree_has_no_unexpected_dead_links` and
       `TestLiveTreeGate::test_full_tree_no_exclude_is_green`. Do not
       allowlist it in `_KNOWN_GAPS` (that gate is deliberately reserved for
       links that will never resolve) and do not drop the sentence -- WP08
       does not own this file. Re-measure `tests/docs/test_relative_link_fixer.py`
       green after WP08 lands, before the PR opens. -->

## [3.2.5] - 2026-07-08

### ✨ Added

- **Coord/primary placement-partition lock - one topology-aware seam owns where
  every mission artifact is stored and read (#1716, #1878/G2).** Formalizes
  `PlacementSeam.write_target(kind)` / `read_dir(kind)` as the single thin
  authority over the existing `resolve_action_context` SSOT and routes every
  remaining write site through it - **fail-closed** via `PlacementResolutionRequired`
  (a real resolution failure raises rather than silently committing to the
  operator's checkout). An architectural ratchet forbids the
  `CommitTarget(ref=<checkout>)` grammar (a self-test proves it bites), and an
  end-to-end characterization test locks the behaviour. Canonical partition:
  coord branch = lifecycle (status/notes/trace/issue-matrix/move-task); primary
  = stable planning (spec/plan/WP outlines); no-coordination topology → all
  primary. RETROSPECTIVE delegates to the existing `resolve_retrospective_home`
  (no second authority). Also **fixes #2091** (an empty `mid8` no longer builds a
  malformed `kitty/mission-<slug>-` coordination branch → `git worktree add`
  exit-128; the `CoordinationWorkspace` composition seam fail-loud-guards it) and
  **#2250** (a never-coordinated mission no longer reports
  `COORDINATION_BRANCH_DELETED`). **The read side is now locked too (#1716
  closeout):** every remaining coordination-surface _read_ - the kind-blind
  `resolve_feature_dir_for_mission` sweep (#2453) and the inline `meta.json`
  reads (#2100) - routes through the same topology-aware seam kind-correctly, so
  `spec-kitty accept` no longer reads a stale `-coord` acceptance matrix (#2404)
  and planning artifacts always resolve to their canonical surface regardless of
  the working directory. A non-vacuous architectural ratchet keeps the routed
  read classes from silently regrowing. Closes epic **#1716** and #2453 / #2100
  / #2088 / #2404.
- **Doctrine/charter pack paths support environment-variable indirection
  (#2437).** Pack-location fields (e.g. an org-pack's `local_path`) previously
  had to be hardcoded absolute paths, so a shared, committed `.kittify` config
  resolved only on the machine of the developer who wrote it and broke for every
  teammate and CI runner. Pack-path templates now expand `${VAR}`/`$VAR` and `~`
  at read time (via `os.path.expandvars` + `expanduser`), so a portable form
  like `${SPEC_KITTY_PACK_HOME}/acme-doctrine` can be committed once and each
  environment resolves it against its own base. Expansion is **fail-closed**: an
  unset/empty env token raises rather than silently collapsing to a wrong path
  (e.g. `${UNSET}/acme` → repo root). Purely additive - literal absolute paths
  keep working.
- **Review-time regression gate at `move-task --to for_review` (#572).** When a
  work package moves to `for_review`, Spec Kitty now auto-scopes the CI shards
  that cover the WP's changed files and re-runs them, so a WP that broke a
  shared contract pinned by a test _outside_ its `owned_files` is caught at
  review time instead of only at merge. Warn-only by default; opt in to a hard
  block with `review.fail_on_pre_review_regression` (enforced only when
  `review.test_command` is set; `move-task --force` overrides), and override the
  scope per-WP via frontmatter `pre_review_test_scope`. See
  [review-gates.md](../development/how-to/review-gates.md).
- **`spec-kitty review --check-residual` + environment-parity preflight
  (#2283).** The new `--check-residual` flag runs CI's always-on
  `unit-contract-residual` `-m` selection over `tests/` locally - the `-m`
  expression is read **live** from `.github/workflows/ci-quality.yml`, so a
  previously CI-only marker-orphan failure can be reproduced before pushing. The
  `spec-kitty review` preflight also detects local-vs-CI environment skew
  (installed package versions diverging from `uv.lock`, plus typer/click
  lock-parity), warning by default and failing closed under
  `SPEC_KITTY_ENV_SKEW_FAIL_CLOSED`.

### 🐛 Fixed

- **Post-merge stale-assertion analyzer stops false-positive storms on
  behavior-preserving refactors (#2031, #2343).** A relocation/re-export (a
  WP05 extraction produced 180 false findings and tripped the drift ceiling)
  and generic-literal noise both flagged as stale assertions. The analyzer now
  (a) suppresses a removed identifier only when the origin file's **module-level
  head** still re-exports/imports it (keyed on head-importability - not
  bare-name-anywhere, so a genuine deletion of a common name like `run`/`main`
  is still flagged; a nested `import parse` does not mask a real `def parse()`
  deletion), and (b) suppresses literal-only noise by **genuineness** (a pinned
  generic-token set / all-punctuation), never by length (a short literal like
  `"E001"` can be assert-critical). Both paths suppress rather than
  info-downgrade, so render surfaces and the FP ceiling are unchanged.
- **Review-prompt files no longer accumulate unbounded; coverage-allowlist
  repointed off a removed module (#2439, #2443).**
  `write_review_prompt_with_metadata()` now prunes review-prompt files to a
  newest-preserving cap after each write - fail-safe, and never pruning the
  current invocation's own file - closing the LC-7 retention residual of #1842.
  Separately, the `diff-coverage` critical-path `--include` allowlist still
  referenced the stale `src/specify_cli/core/mission_detection.py` (removed in a
  rename); it is repointed to `src/specify_cli/lanes/branch_naming.py` in **both**
  the CI workflow and its test authority in lockstep, with a glob-aware existence
  guard so a phantom allowlist entry reds instead of silently covering nothing.
- **`spec-kitty agent mission finalize-tasks` accepts glob-only `owned_files`
  (#2446).** A work package whose `owned_files` used a filename glob (e.g.
  `src/foo/*.py`) with no explicit `authoritative_surface` was rejected because
  `infer_authoritative_surface` produced an invalid `src/foo/*.py/` path. It now
  reduces a glob-bearing final path segment to its directory, so glob-only
  ownership infers a valid authoritative surface. (Fix landing via PR #2454.)
- **A retired skill's projected files are now drained by surface repair instead
  of orphaned forever (#2409).** When a skill was retired from the registry,
  `spec-kitty upgrade --project` could not reconcile its leftover projections:
  the repair path warned `Cannot repair … skill not found in registry` on every
  subsequent upgrade and left the files in place (committed, where the repo
  tracks skill surfaces; a dangling symlink, where the global root had dropped
  the skill). Repair now reconciles retirements **manifest-driven**: entries in
  `.kittify/skills-manifest.json` whose skill no longer exists in a _live_
  registry have their projected files removed - symlinks unlinked, hash-clean
  copies deleted, user-**modified** copies archived to
  `.kittify/.migration-backup/agent-skills/` instead of deleted - emptied skill
  dirs pruned, and the manifest entries dropped, silencing the repeat warning.
  Only ledger-recorded paths are ever touched (a user-authored skill sharing
  the projection root is never scanned), and an **empty** registry never
  retires anything (a broken canonical source must not mass-drain the
  manifest).
- **Test-session state leaks closed: per-mission prompt-tmp namespace +
  workspace-context tombstone (#1842, #2032).** Runtime prompt files are now
  written under a per-repo/per-mission namespaced temp directory
  (`<tmp>/spec-kitty-prompts/<repo-id>/…`) instead of a shared flat `/tmp`
  path, and a lane's workspace-context sidecar is now tombstoned when its
  worktree is torn down at merge (or when the lane is canceled) - clearing the
  stale-context and prompt-litter residue flagged by the #1931 `/tmp`-hygiene
  audit. A session-scoped pytest reaper (controller-gated, run-uid-scoped, and
  never touching the real `~/.spec-kitty`) now fails the suite if a test leaks
  repo-root residue, so new leaks are caught at their source.
- **Dashboard: PR-bound missions planned on a feature branch are visible again
  (#2430).** The dashboard scanner resolved ONE directory per mission,
  coord-worktree-first - but under coordination topology the two partitions
  live on different surfaces: `spec-commit` lands planning artifacts
  (`spec.md`/`plan.md`/`tasks.md`/`tasks/`/`meta.json`) on the **primary**
  surface, while the live event log lives on the **coordination** branch. The
  scanned `-coord` copy therefore held only status writes, so the legacy
  existence filter (numeric prefix or `tasks/` present) silently dropped any
  in-flight post-083 mission from `/api/features`, and artifact viewers/kanban
  read the wrong surface. The scanner now splits the read per partition —
  planning artifacts primary-first through the same kind-aware read seam the
  #2331 identity fix uses (`resolve_planning_read_dir`), live lane state from
  the gather-resolved coord surface - so an in-flight coordination mission
  lists with its real spec/plan/tasks AND live kanban lanes. Same
  coord-shadows-primary class as #2331; the accept-side sibling is #2404.
- **Session banner no longer recommends a downgrade (#2413).** The
  session-presence health check decided "upgrade-available" with a bare
  inequality (`avail != current`), so any machine whose installed CLI was
  _newer_ than the cached PyPI latest - a fresh release not yet in the 1-hour
  cache, or an rc/dev install - got "⚠ Upgrade available: 3.2.2" while running
  3.2.4. Both health branches now use `packaging.Version` ordering
  (`avail > current`); unparseable versions are treated as no-upgrade so
  session start never breaks on a weird cache value.
- **The shared Agent-Skills projection root and the per-machine skill install
  ledger are now gitignored (#2412).** The skills installer projects global
  canonical skills into `.agents/skills/` (codex/vibe/pi/letta) preferring
  **absolute symlinks** into the user-global root - machine-local content by
  construction - but unlike `.claude/` and the other agent dirs (gitignored
  wholesale at init), bare `.agents/` was never covered by any init path,
  registry entry, or migration, so the `/Users/<name>/...` symlink blobs were
  committable (and the upgrade auto-commit would land them automatically).
  `.kittify/skills-manifest.json` (per-machine timestamps/hashes/delivery
  modes) had the same gap. Both are now registered `IGNORED` state surfaces
  (fresh `spec-kitty init` gitignores them, and `spec-kitty doctor`'s
  present-but-not-gitignored warning covers them), and a sibling backfill
  migration (`3.2.5_agents_skills_gitignore_backfill`) adds the entries on
  `spec-kitty upgrade` for already-initialised projects. The symlink-vs-copy
  delivery question (ask 3 of #2412) is tracked separately on the issue.
- **`spec-kitty upgrade` now commits worktree churn on every checkout, not just
  main (#2392, closes #2385/#1873, pins #2105).** The upgrade auto-commit
  captured a porcelain baseline for the main checkout only, so migration writes
  it made in sibling worktrees were left uncommitted - dirtying them and
  blocking coordination-topology merges (NFR-002). The porcelain-baseline commit
  routine is extracted into a canonical per-checkout seam
  (`upgrade/autocommit.py::commit_touched_checkout`); the migration runner now
  snapshots each worktree _before_ its writes and commits only that new churn on
  the worktree's own branch (in-flight WP edits are never swept in;
  `manual_review_required` migrations skip the commit with a warning;
  detached-HEAD skips instead of guessing a ref; `--dry-run` stays a strict
  no-op). #1873's self-healing path is restored (metadata synthesized from
  `None` is marked dirty so it's saved even when detected version == target).
- **Legacy-topology warning no longer over-fires on intentional
  coordination-less missions (#2351).** The once-per-mission warning keyed on
  `coordination_branch` absence, so it fired for genuinely deliberate
  `single_branch`/`lanes` shapes (#2218) as well as truly pre-SSOT missions. A
  new warning-only classifier gates just the emit on the canonical stored
  `MissionTopology` + flattened flag (warn iff coordination branch absent AND
  stored topology null AND not flattened; malformed still warns); the shared
  `_is_legacy_mission` predicate that drives worktree routing and write-contract
  selection is left byte-for-byte unchanged.
- **`.kittify/migrations/` and `.kittify/logs/` are gitignored and backfilled
  (#2384, completes the #2369 sweep).** Two more generated `.kittify/` subtrees
  (mission-state repair manifests + quarantine backups; orchestrator per-WP
  logs) were neither IGNORED state surfaces nor backfilled, so they dirtied the
  tree and failed `accept`'s git-dirty check. Both are now registered IGNORED
  local-runtime surfaces (fresh `init` gitignores them) with a sibling
  backfill migration for already-initialised projects on upgrade.
- **`saas_client` no longer defaults to a hardcoded `api.spec-kitty.io`; it
  fails closed (#2248).** `load_auth_context` fell back to a baked-in SaaS URL
  when neither `SPEC_KITTY_SAAS_URL` nor `.kittify/saas-auth.json` supplied one,
  risking silently pointing the client at the wrong server. With the #2146
  target-authority decision in place, the default is removed and a no-URL
  resolution now raises `SaasAuthError` (caught where the no-token path already
  was).
- **Sync runtime callers route through the canonical resolved target authority
  (#2146).** The tracker client, sharing client, and background sync read the
  raw `SyncConfig.get_server_url()` (config-only, hardcoded default) instead of
  `resolve_runtime_target().resolved_server_url`, so with `SPEC_KITTY_SAAS_URL`
  set, auth/readiness hit the env target while these surfaces silently posted to
  the config target (the SC-008 split-brain). All three now resolve the same
  target as auth/readiness, and `sync status`/`sync doctor` report the resolved
  URL. Separately, `sync server <url>` now accepts loopback HTTP
  (`http://localhost`/`127.0.0.1`/`::1`) for the documented local-Docker-SaaS
  dev workflow while still requiring HTTPS for remote hosts.
- **compat-planner contract checks are revived (#2419).** Two test surfaces
  validated `upgrade`/`render_json` payloads against the committed
  `compat-planner.json` contract but silently no-op'd in CI since 2026-04-27
  (each resolved the contract via a maintainer-worktree-only path, so it was
  `None` and validation was skipped). Both now anchor on the repo root, load
  unconditionally, and fail hard on a missing/unreadable contract - which caught
  one real drift (a migration description trimmed to satisfy `maxLength`).
- **migration_id contract pattern widened to admit the dotted convention
  (#2339).** The `compat-planner.json` `migration_id` pattern
  (`^[a-z0-9_]{1,128}$`) rejected 83 of 89 real dotted ids (e.g.
  `3.2.0rc45_...`) - a contract-authoring bug that let #2339-class drift slip
  through unnoticed. Widened to `^[a-z0-9_.]{1,128}$` (a backward-compatible
  widening; no shipped `migration_id` renamed, so persisted per-project ledgers
  keep validating).

### ♻️ Changed

- **Internal: version-comparison primitives consolidated into one canonical module (#2417, landing via PR #2414).**
  Landing the #2413 fix surfaced three independent "is version A newer than
  version B" implementations that had drifted apart in edge-case handling:
  `cli/commands/upgrade.py::_version_is_newer` (caught the broad `Exception`
  instead of the specific parse failure), `core/upgrade_probe.py::_classify`'s
  inline comparison, and the `_upgrade_is_available` helper #2413 had just
  added to `session_presence/manager.py`. All three now delegate to a new
  pure module, `specify_cli.core.version_compare`
  (`try_parse_version` / `is_version_newer`), with no CLI/click/typer
  imports so it is safe to import from any layer; the two duplicate boolean
  helpers are deleted outright, no aliases left behind. No user-facing
  behavior change.
- **Internal: CI-topology census freshness gate is now LOC-insensitive
  (#2416).** The gate compared each worklist entry's exact line count and an
  LOC-derived sort order, so any PR that shifted the line count of a worklist
  directory went red regardless of touching CI routing - a maintenance tax two
  PRs paid inside 24h. It now checks membership + committed routing plan only
  (an order/LOC-insensitive index at the shared derivation), fixing both the
  pytest gate and the `--verify-census` CLI by construction. Zero `src` changes.
- **Internal: test-suite `/tmp` hygiene sweep (#1842, epic #1931).** 97
  grandfathered test files were converted off literal `/tmp` paths to
  `tmp_path`/sentinels, and the empty-`/tmp` ratchet was flipped to a
  self-consistent hard gate so new literal-`/tmp` leaks fail fast. Also fixed a
  test-only `--output=` parser leak that could write an invalid Windows filename
  (breaking the Windows critical CI job), with a new arch guard blocking
  Windows-illegal names and shell-expansion-leak telltales across tracked files
  (#2169).

### 💥 Breaking Changes

- **Pre-3.2.x legacy (meta-less) missions are no longer supported for
  coordination operations (#2091 / #2462).** A mission with no resolvable
  mission identity - no `mission_id`/`mid8` in `meta.json`, the pre-3.2.x
  mission-identity model - can no longer drive coordination operations (status
  transitions, `move-task`, review/merge coordination writes). Such a mission
  now **fails loud** with a customer-actionable error instead of silently
  composing a malformed `kitty/mission-<slug>-` ref (the old #2091 defect that
  surfaced only as an opaque `git worktree add` exit-128). This intentionally
  drops the dual-era legacy-bridge fallback: legacy missions are dwindling and
  the dual-support path was a persistent source of split-brain routing bugs.
  **Migration:** run `spec-kitty migrate backfill-identity` to mint a ULID
  `mission_id` (and derive its `mid8`) for any affected mission - audit first
  with `spec-kitty doctor identity`. See
  [mission-id-canonical-identity.md](../migrations/mission-id-canonical-identity.md).

## [3.2.4] - 2026-07-05

Spec Kitty 3.2.4 is a reliability-and-trust release. It fixes a batch of
everyday mission-lifecycle friction points, closes a real gap in the bulk-edit
safety net, makes SaaS sync reporting honest, and - behind the scenes —
reshapes the CI pipeline and decomposes a large internal command module for
faster feedback and lower regression risk going forward.

- **Smoother day-to-day mission lifecycle.** A batch of guard/gate fixes
  removes friction from the implement-review-accept loop: a subtask guard no
  longer misattributes a later work package's unchecked boxes to an earlier
  one, a mission fully implemented by `spec-kitty-orchestrator` can now pass
  `spec-kitty accept` (two false-positive blockers removed), `move-task --to
  for_review` recovers a killed implementer's uncommitted work instead of
  dead-ending, closing a mission now reliably commits its auto-captured
  retrospective, the dashboard no longer hides an in-flight coordination
  mission behind a synthetic "orphan" entry, and a stale `.kittify/derived/`
  view or Op-index cache file can no longer dirty `git status` or block
  `accept`. `map-requirements` also now explains exactly _why_ a requirement
  reference is stale instead of looking like data corruption.
- **Mission-state repair no longer risks data loss.** `doctor mission-state
  --fix` (and the automatic repair `spec-kitty upgrade` runs) previously could
  empty a healthy mission's event log of its canonical lifecycle history; it
  now preserves every reader-canonical event class and anchors on the primary
  checkout so repairs actually take effect.
- **Bulk-edit safety net closed.** The `occurrence_map.yaml` gate that blocks
  an incomplete bulk-edit classification at finalize-tasks now covers _both_
  finalize-tasks command surfaces, not just one - closing a path where a
  bulk-edit mission could slip through with an inadmissible occurrence map.
- **Honest SaaS sync reporting.** `sync opt-in` no longer implies remote
  enablement it didn't perform, and `sync status --check --json` reports real
  (or honestly `unknown`) remote/import state instead of staying silent.
- **New `orchestrator-api` capability.** A read-only `resolve-workspace`
  command lets an external orchestrator recover a work package's lane
  workspace without accidentally re-triggering a lifecycle transition.

_Behind the scenes:_ the CI pipeline was reshaped - path-filtered job groups, a
split core-misc shard, and an always-on, de-serialized architectural-adversarial
pole - so most PRs get faster, more targeted feedback without losing any
coverage; and the sprawling `agent tasks` command module was decomposed into
small, independently-tested, behavior-preserving pieces. Neither changes any
user-visible behavior, but both reduce the odds of the next regression and
speed up how fast we catch one.

### 💥 Breaking Changes

- **Deprecated compatibility shim packages removed (mission `unshim-wave2-01KWMCAX`, #2291 / #2290 / #2326 under #1797).** The following re-export shim import paths are **deleted** - code that imported them must switch to the canonical path:
  - `specify_cli.next` → **`runtime.next`** (the canonical `spec-kitty next` runtime/control-loop package; antecedent #612)
  - `specify_cli.glossary` → **`glossary`** (antecedent #613)
  - `specify_cli.charter_lint` → **`specify_cli.charter_runtime.lint`**
  - `specify_cli.charter_freshness` → **`specify_cli.charter_runtime.freshness`**
  - `specify_cli.charter_preflight` → **`specify_cli.charter_runtime.preflight`**

  All in-tree callers were re-pointed to the canonical modules before deletion. The shim registry (`docs/migrations/shim-registry.yaml`, the file read by `spec-kitty doctor shim-registry`) is drained to `shims: []`, and the ownership manifest (`docs/architecture/05_ownership_manifest.yaml`) mirrors the drain for these slices. The user-facing CLI surface is unchanged - `spec-kitty next` and `spec-kitty charter lint/preflight/freshness` behave identically. **No version bump accompanies this entry:** `src/specify_cli/__init__.py` is untouched by the mission (verified against the mission lane history), so the public CLI package version is unaffected; only internal deprecated import paths are removed.

### ♻️ Changed

- **CI health: charter-path doc hotfix + arch-adversarial matrix shard (mission `ci-health-charter-path-and-arch-shard-01KWRTB2`, closes #2397).** Two independent CI-health fixes bundled by operator decision: (a) `docs/guides/contributing.md` still published the retired legacy charter path `memory/charter.md`, redding `fast-tests-docs` on every open PR - replaced with the canonical `.kittify/charter/charter.md`; (b) the `arch-adversarial` job (already de-serialized from the core-misc critical path by the CI-topology-shrink mission above) remained a single unsharded ~14.4-min bottleneck - matrix-sharded into always-on, group-less shards (same pattern as `fast-tests-core-misc`), still running on 100% of source changes with no test dropped or double-counted across shards, dropping the slowest shard below the ~13.6-min sub-target.
- **One canonical `MissionCreated` payload builder (#2270, PR #2398).** Three independent code paths derived `MissionCreated` defaults and had drifted apart: `core/mission_creation.py`, a verbatim-duplicate helper in `sync/emitter.py`, and a third, divergent inline fallback in `status/lifecycle_events.py` (raw slug vs. titleized `friendly_name`, absent vs. now `created_at`, differing None-field wire shape). A new pure CORE module, `core/mission_payload.py::build_mission_created_payload`, is now the single source; both the local lifecycle-event path and the SaaS `EventEmitter` route through it, preserving the CORE↛INTEGRATION boundary (no sync import in core). **Behavioral note:** the local mission log's default `friendly_name` (when not passed explicitly) now titleizes the slug instead of using it raw, matching what the SaaS emitter already produced.
- **CI topology shrink + shard split + always-on architectural pole (mission `ci-topology-shrink-01KWQAVX`, #2378 / #1933 / #2383 under #1931).** The `ci-quality.yml` PR pipeline is reshaped so a single-area PR runs only its focused shard(s) plus the always-on gates, not a full-matrix run:
  - **Group-side shrink (#1933).** The previously-unmapped `src/specify_cli/*` directories are folded into six named composite `dorny/paths-filter` groups (`auth_audit_git`, `lifecycle`, `agent_surface`, `closeout`, `governance`, `platform`), each registered atomically across all five surfaces (filters block, `changes.outputs.*`, the `unmatched` enumeration, and the `JOB_GROUPS` needs-lists). All 32 worklist dirs are now routed. This is the **shrink** interpretation of #1933 (fast, targeted PR CI), not the literal nightly-scheduled full suite (deferred per C-006); the escape hatches (`workflow_dispatch` `run_all`/`run_extended`, the nightly `schedule` cron, the `unmatched` fail-closed catch-all) and the nightly `run_all` over-cover of every worklist dir remain intact - no new blind spot (FR-009).
  - **Shard-side split (#2378).** `fast-tests-core-misc` is subdivided into two disjoint, non-empty matrix shards (ignore-mirror kept consistent), so a core-misc change no longer drags the whole misc bucket.
  - **Architectural un-blind, de-serialized (#2383, NFR-002).** The architectural + adversarial guard job (`arch-adversarial`) runs always-on (`if: always()`, group-less) over 100% of `src/`, and is **de-serialized** from `fast-tests-core-misc` (its `needs` edge is dropped) so it no longer sits on the core-misc critical path - the path collapses from `sum` to `max`, structurally under the ≤13.6-min next-lane ceiling (NFR-001; live `measured_source_run_id` backfilled by the operator from the PR's first post-shrink CI run).
  - **Coverage-consumer integrity by construction (C-005).** New architectural invariants assert coverage-emitting jobs ⊆ `sonarcloud.needs` and critical-path emitters ⊆ `diff-coverage.needs`; in the process the pre-existing production **`mission-loader-coverage` coverage-drop is fixed** - it emits `--cov=src/specify_cli/mission_loader` yet was absent from `sonarcloud.needs`, so its coverage XML was silently dropped from the Sonar gate. The full 8-invariant #2368 substrate suite plus the new NFR-002/003/005 and C-005 relations stay green (NFR-007), and the gate-coverage ratchet baseline is refreshed (`orphan_test_count` 0; `total_tests` rises with the added invariants; `duplicate_test_count` falls with the same-tier consolidation).
- **Root `CHANGELOG.md` is now a symlink to the canonical `docs/changelog/CHANGELOG.md` - the generated mirror is retired.** The two-file model (canonical + frontmatter-stripped root copy kept in sync by `scripts/docs/sync_changelog.py`) made contributors edit the root copy and trip docs-freshness on every external PR. There is now exactly one changelog file; `sync_changelog.py --check` guards the symlink (and `--write` restores it), and release tooling (`extract_changelog.py`, `validate_release.py`) reads the canonical text through the link - both scan `## [...]` headings and tolerate the YAML frontmatter.
- **`orchestrator-api` contract 1.1.0 → 1.2.0: new read-only `resolve-workspace` command (#2337).** `resolve-workspace --mission --wp` returns a work package's lane `workspace_path` / `prompt_path` / `lane_branch` for its **existing** lane, resolved via the canonical naming seams **without** allocating, creating, validating-clean, or transitioning. It's the read-only companion of `start-implementation` (which does a `planned→claimed→in_progress` composite transition): an external orchestrator resuming a WP already past implementation (e.g. one parked in `for_review` after an interrupted run) can obtain its workspace to dispatch a reviewer without mis-transitioning it. Purely additive - existing commands and payloads are unchanged.
- **Internal: the `agent tasks` god-command is decomposed into pure decision cores behind injected ports (mission `tasks-py-degod-01KWF08S`, #2116 under #2173).** Behavior-preserving - the full `agent tasks` CLI contract (all subcommands, flags, exit codes, `--json` envelopes, including the coord skip-exit-0 arm and the refuse-exit-1 arms) is **byte-identical**, frozen by a golden characterization harness. The decision/aggregation logic of the five fat command bodies (`move_task`, `map_requirements`, `status`, `mark_status`, `finalize_tasks`) now lives in pure, independently-tested sibling modules (`tasks_transition_core`, `tasks_mapping_core`, `tasks_status_view`) behind an injected `TasksPorts` seam (`FsReader` coord-READ authority + a two-capability `CoordCommitRouter` coord-WRITE authority); each command body is a ≤150-LOC thin orchestrator. Also folds the pre-3.0 coord read-authority split-brain onto the kind-aware authority (guard-only sites) and drains the resolution-authority census (shrink-only). **No user-facing behavior change.** The Render-seam unification and the whole-file `tasks.py` shim relocation are deferred to a follow-up mission (see `docs/plans/tasks-py-degod-followup-mission-debrief.md`).

### 🐛 Fixed

- **Bulk-edit occurrence-map gate now also enforced on the legacy `agent tasks finalize-tasks` command (#2345, PR #2386).** The PR that gates `occurrence_map.yaml` at finalize-tasks (rather than at first `implement WP##`) only wired the check into `agent mission finalize-tasks`; the older, still-live `agent tasks finalize-tasks` command family could complete finalize-tasks for a bulk-edit mission with a missing, schema-invalid, or inadmissible occurrence map with zero gate friction - found by the pre-merge adversarial squad during landing. `_ft_validate_occurrence_map_ready` mirrors the mission-command gate and runs first in `_ft_validate` (fail-fast, before dependency parsing); the shared error message and JSON payload are de-duplicated into `bulk_edit/gate.py` (`finalize_tasks_gate_error_payload`) so the two command surfaces can't drift apart again.
- **Honest SaaS sync opt-in reporting + typed `remote_sync` status fields (#2264 slice, PR #2396).** `sync opt-in` printed `✓ Enabled SaaS sync for this checkout` even though it only writes local routing flags - implying remote enablement that never happened; the message now states only that a local preference was recorded. `sync status --check --json` gains a typed `remote_sync` block (`remote_project_state` / `materialized_at` / `historical_import_state` / `last_blocker_sample`), honestly `unknown`/null until the import engine (#2262) populates it - `ok` semantics are unchanged, so existing consumers are unaffected and new consumers read remote state from `remote_sync`, not `ok`. Also folded in: `opt-in` now exits non-zero (was a dim exit-0 message) when the SaaS-sync rollout flag is disabled, since opt-in cannot take effect with the flag off.
- **`.kittify/migrations/` and `.kittify/logs/` are now gitignored - completing
  the #2369 derived-views fix (#2384).** Two more generated `.kittify/` subtrees
  of the same class as `.kittify/derived/` were neither registered `IGNORED`
  state surfaces nor added by any backfill, so they showed up untracked and
  failed `spec-kitty accept`'s `git_dirty` check: `.kittify/migrations/`
  (mission-state repair manifests + quarantine backups) and `.kittify/logs/`
  (orchestrator per-WP implementation/review logs). Both are now registered
  `IGNORED` surfaces (fresh `spec-kitty init` gitignores them), and a sibling
  backfill migration (`3.2.4_runtime_dirs_gitignore_backfill`) adds them on
  `spec-kitty upgrade` for already-initialised projects.
- **Upgrade-worktree coherence: one canonical per-checkout auto-commit seam
  (epic #2392 spine - closes #2385, #1873; regression-pins #2105).** The
  `spec-kitty upgrade` commit routine (porcelain-baseline-derived commit-set,
  directory expansion, eligibility filter) is extracted from the CLI into
  `specify_cli.upgrade.autocommit.commit_touched_checkout()` and applied
  symmetrically to **every checkout the run touches** over the runner's single
  worktree enumeration:
  - **#2385** - worktree migration churn was never committed (auto-commit ran on
    the main checkout only), so each coord/lane worktree was left dirty and a
    later `spec-kitty merge` tripped the #1826/NFR-002 guard. The runner now
    captures a per-worktree porcelain baseline before that worktree's writes and
    commits its _new_ churn on its own branch; pre-existing uncommitted work
    (e.g. in-flight WP edits) is never swept in, and per-worktree
    `manual_review_required` migrations skip that worktree's commit with a
    warning. Root `.gitignore` churn - exactly what the gitignore-backfill
    migrations write - is now commit-eligible instead of being dropped by the
    root-level-file filter.
  - **#1873** - freshly synthesized worktree metadata is persisted (and
    committed) even when the detected version already equals the target,
    restoring the #1857 self-healing path.
  - **#2105** - already porcelain-derived in this tree; now regression-pinned by
    a test asserting manifest updates and newly-installed skills land in the
    commit-set (guards against regressing to a hardcoded file list).
  - A detached-HEAD checkout skips the auto-commit with a warning instead of
    guessing a ref. `--dry-run` remains a strict no-op per checkout. An
    invariant test asserts that after `upgrade`, no touched checkout carries
    porcelain dirt beyond what pre-existed. **#2367's two mechanisms are
    deliberately NOT routed through this seam** (per the #2392 architect
    design): the implement-claim VCS-lock policy (#2222/C-003 race decision)
    and the merge-rollback snapshot capture set are separate seams sharing the
    same invariant.
- **Guard/gate friction hotfixes (#2346 / #2324, #1834).**
  - **Subtask guard no longer misattributes a later WP's checkboxes (#2346, also closes #2324).** `_check_unchecked_subtasks` entered a WP's section on _any_ heading that merely mentioned its id, so a dependent heading like `### WP03 - … (depends: WP01, WP02)` re-entered WP01/WP02's section and harvested WP03's unchecked `- [ ] T0xx` rows as the earlier WP's blockers - spuriously blocking that WP's lane transition. A heading now belongs to the WP named by its **first** `WPxx` token, not any mention.
  - **`grep_absence` negative invariants accept an optional path-scope (#1834).** The acceptance gate ran `grep -r <pattern> .` over the whole repo, so a negative-invariant pattern that a mission's own spec/plan/WP prose mentioned false-positived as `still_present`. `NegativeInvariant` now carries an optional `scope` (whitespace-separated repo-relative search roots); when set, the grep runs only under those paths. Default (unscoped) preserves the whole-repo search, and `scope` is omitted from serialization when unset so existing matrices are untouched.
  - **Documented merge-before-accept for merged-post-state invariants (#1834).** The accept runbook (`docs/guides/accept-and-merge.md`) now records that the accept gate re-runs each negative-invariant `verification_command` **live** (so a hand-set `overall_verdict` does not stick), and that a mission whose invariants assert the _merged_ post-state must run `spec-kitty merge` (local) before `spec-kitty accept`.
- **A mission fully implemented by `spec-kitty-orchestrator` can now pass
  `spec-kitty accept` - two mechanical false-positives removed (#2369).** The
  accept gate is the mission-level readiness check (all-done, subtasks,
  clarifications, artifacts, clean tree, paths), but two checks always failed on
  orchestrator-completed missions, forcing operators to bypass accept entirely:
  (a) the strict-metadata check required `shell_pid` on **every** WP, including
  terminal ones - but `shell_pid` is an interactive-`spec-kitty next` artifact the
  orchestrator never stamps; it is now **lane-gated to active lanes exactly like
  `assignee`**, so a done/approved WP no longer needs it (an active WP still does).
  (b) `spec-kitty materialize` writes regenerable views to `.kittify/derived/`,
  which was **not** in the runtime gitignore set (unlike sibling `.kittify/`
  paths), so it dirtied the tree and failed accept's `git_dirty` check - the
  `derived/` views are now a registered `IGNORED` state surface (so fresh
  `spec-kitty init` gitignores it), and a dedicated backfill migration
  (`3.2.4_derived_mission_views_gitignore_backfill`) adds `.kittify/derived/`
  to `.gitignore` on `spec-kitty upgrade` for already-initialised projects
  (the runtime-hygiene migrations previously only knew a hardcoded subset of
  entries). The six meaningful accept checks still gate.
- **Mission-state repair no longer empties `status.events.jsonl` of a healthy
  mission (#2376).** The repair (run by `spec-kitty upgrade` via the TeamSpace
  mission-state gate, and by `doctor mission-state --fix`) quarantined _every_
  `event_type` row except retrospective ones - including the canonical lifecycle
  events (`MissionCreated`, `SpecifyStarted`, `WPCreated`, …) that
  `status/lifecycle_events.py` writes and whose **only** per-mission home is
  `status.events.jsonl`. A completed mission whose log was all lifecycle events
  was emptied to 0 bytes. Repair now **preserves every reader-canonical non-lane
  class** in place - canonical lifecycle events (those in
  `LIFECYCLE_EVENT_TYPES`), retrospective lifecycle rows (the `type` envelope),
  **and the `retrospective.*` (`event_name` envelope) stream written by
  `emit_retrospective_event`** - so the repair predicate matches the durable
  reader (`status/store.py::is_non_lane_event`) exactly. Before this, a mixed log
  containing a `retrospective.completed` row still silently stripped it (the same
  #2376 data-loss class in a different event format). A backstop also refuses to
  write a 0-byte log when the source was non-empty. Decision-Moment
  (`DecisionPoint*`) rows are still pruned: their canonical store is
  `decisions/index.json` / `DM-*.md`, so the copy here is a mirror (unchanged,
  tested behavior). Rows preserved verbatim in the quarantine dir remain
  recoverable.
  - **Repair now anchors on the primary checkout so `SNAPSHOT_DRIFT` actually
    converges and stale coordination worktrees are left untouched (#2320).**
    `doctor mission-state --fix` already re-materializes `status.json` from
    `status.events.jsonl`, but when invoked from inside a worktree the
    invocation root pointed at that worktree, so the materialize landed there:
    the **primary** `status.json` stayed frozen (a re-`--audit` reported the
    same `SNAPSHOT_DRIFT` blocker) and uncommitted repairs were written into a
    possibly-stale coordination worktree. Repair now re-anchors to the canonical
    primary main-checkout via the single worktree-pointer parser
    (`resolve_canonical_root`), so it always targets the primary
    `kitty-specs/<slug>` (drift converges) and never dirties `.worktrees/`. The
    read-only `--audit` path is now anchored on the **same** authority at the
    `run_mission_state` dispatch seam, so audit and fix resolve to the identical
    canonical root from any cwd (a worktree-invoked `--audit` reads the primary,
    matching `--fix`) instead of diverging onto a stale worktree.
- **The Op-index performance cache is now gitignored (#2341).**
  `kitty-ops/ops-index.jsonl` - the machine-local reverse-scan cache that powers
  `spec-kitty invocations list` - was never added to `.gitignore`, so a
  freshly-generated index showed up in `git status` indefinitely (and could be
  accidentally committed). It is now registered as an `IGNORED` `LOCAL_RUNTIME`
  surface in the state contract (`op_invocation_index`), which flows into fresh
  `spec-kitty init` protection automatically. Existing projects are repaired by
  the runtime git-hygiene migration, which also `git rm --cached`s a
  previously-committed index. Durable per-Op audit records
  (`kitty-ops/<op_id>.jsonl`, the new `op_invocation_record` surface) stay
  **tracked** - only the index is ignored.
- **The dashboard no longer orphans a valid in-flight (mid-orchestration)
  mission (#2331).** While a coordination-topology mission had live worktrees
  checked out, `spec-kitty dashboard` registered it under a synthetic
  `orphan:<slug>` key - hiding it from the mission dropdown - because the
  registry read mission identity (`meta.json`) from the coordination worktree,
  which lacks it (`meta.json` is a PRIMARY-partition artifact that lives on the
  primary checkout). Identity now resolves through the kind-aware
  `resolve_planning_read_dir(..., PRIMARY_METADATA)` seam, so a mission mid-run
  shows under its real title and canonical ULID; status/board display still uses
  the coordination surface. `lifecycle.json` now also carries `mission_id`. No
  change for merged/idle missions.

- **`move-task --to for_review` recovers a killed implementer's uncommitted lane
  deliverables instead of dead-ending (#2335).** When an implementer finished its
  files but was interrupted before committing, moving the work package to
  `for_review` failed with a message demanding a manual `git add`/`git commit`
  _inside the lane worktree_ - violating the "spec-kitty drives commits" rule. On
  the `for_review` transition, when the auto-commit policy is enabled (the
  default), spec-kitty now commits the finished lane deliverables via the tool
  (`safe_commit` on the lane branch) before the readiness guard runs, so recovery
  completes without touching lane git by hand. Scoped to `for_review` only
  (`approved`/`done` deliverables are already committed); `--force` still
  bypasses, and `--no-auto-commit` defers to the existing guard.

- **`mission close` / `spec-kitty merge` now commit the retrospective they
  auto-generate, instead of leaving the durable event log dirty.** Closing a
  mission that was merged via the legacy plain-git/GitHub path (so merge-time
  teardown never ran) auto-captured `retrospective.yaml` and appended a
  `RetrospectiveCaptured` event to `status.events.jsonl`, but left both
  uncommitted with no notice - violating the atomic-event-log discipline
  (FR-016), since an uncommitted append can be lost. The shared post-merge
  retrospective postcondition now commits the captured record + its event-log
  append via the merge-bookkeeping commit path, so `merge` and `mission close`
  behave identically and the working tree is left clean. If the commit cannot be
  made (detached HEAD / not a worktree), it fails open but reports the
  uncommitted artifacts and the exact command to commit them. `mission close
  --help` no longer describes the non-`--discard` path as a pure "no-op".
- **`map-requirements` now explains _why_ a WP `requirement_refs` entry is stale
  instead of looking like data corruption (#2066).** When the stale/invalid-refs
  gate trips, the `--json` payload (and console output) now surface the FR-ID set
  parsed from `spec.md` (`parsed_spec_ids`), classify each offending ref per WP into
  `malformed` (violates the `FR-NNN` / `NFR-NNN` / `C-NNN` format - e.g. a
  letter-suffixed `FR-003a` or an unfilled `<FR-XXX>` placeholder) vs
  `unknown_spec_id` (well-formed but not declared in the spec), and the hint names
  the format rule. A one-character ID-format mismatch is now obvious rather than
  reading like invented/orphaned IDs.

## [3.2.3] - 2026-06-29

Spec Kitty 3.2.3 is a stabilization-and-foundations release. It hardens how the
toolkit behaves under non-trivial branch topologies, smooths the day-to-day
planning and implementation loop, and lands a governed documentation and doctrine
foundation for the upcoming 3.3.x developer-experience focus.

- **Improved branch topology support.** Coordination-topology missions now read
  and write every artifact from the correct surface - planning artifacts
  (`lanes.json`, work-package `tasks/`, `meta.json` identity) on the primary
  branch, status on the coordination worktree - through a single kind-aware
  resolution seam, backed by single-authority resolution gates. The orchestrator,
  the accept gate, merge/lane logic, and `spec-kitty next` no longer stall,
  mis-route, or report phantom early state on coordination missions.
- **Usability upgrades.** A batch of mission-lifecycle tooling-loop friction
  fixes, clearer global-install guidance, and safer everyday operation:
  `SPEC_KITTY_HOME` now isolates _all_ local state, `--json` output is safe to
  capture with `2>&1`, worktree discard can no longer delete a sibling mission,
  and a stale tool environment can no longer brick the CLI.
- **Doctrine additions.** The Common Docs consolidation lands a governed
  documentation foundation - a documentation directive, a styleguide, and
  curation / scaffold / write / find tactics wired into the doctrine graph —
  alongside the structural move to a 13-section Divio `docs/` tree: 117
  architecture decision records converted to metadata-in-file records under
  `docs/adr/`, redirect coverage for every moved page, and documentation rulers
  promoted to blocking gates.
- **Doctrine/charter extension improvements.** Charter activation now gates
  org-pack agent availability across dispatch, context, and projection; the
  generated charter interpolates the project documentation policy; and
  `spec-kitty doctor` reports unsanctioned built-in doctrine-graph overrides.

### ✨ Added

- **Retrospectives now have a durable home and survive coordination teardown (#2119).**
  A new `RETROSPECTIVE` primary-artifact kind routes `retrospective.yaml` to the
  tracked `kitty-specs/<slug>/` mission folder for every topology, instead of the
  ephemeral coordination worktree that is deleted on teardown.
- **Governed documentation foundation - the Common Docs doctrine (#2210, #2165).**
  A built-in documentation directive (`DIRECTIVE_042`), a documentation styleguide,
  and `curation` / `scaffold` / `write` / `find` tactics are now wired into the
  doctrine graph, plus three documentation rulers (a `related:` link validator, a
  page-inventory lockfile generator, and an anti-sprawl ratchet), each shipped with
  its own self-test.
- **Common Docs structural move - a 13-section Divio `docs/` tree (#2165, #2054).**
  The split-brain `architecture/` + `docs/` trees are consolidated into one Divio
  layout. 117 unique architecture decision records are converted from the legacy
  table/bold/dash formats into metadata-in-file (MADR) records under
  `docs/adr/<era>/` with byte-invariant decision bodies; redirect stubs preserve
  every moved published URL; page frontmatter is the single source of truth for the
  page-inventory lockfile; and the documentation rulers are promoted to blocking
  gates. The canonical changelog now lives at `docs/changelog/CHANGELOG.md` with
  root `CHANGELOG.md` retained for release tooling.
- **Charter-activation-gated org-pack agents (#2211, #2156, #2166).** Agents
  contributed by an organization doctrine pack are surfaced in dispatch, context,
  and projection only when their charter artifact is active - org overlays are
  applied through the charter, never raw `org_dirs`.
- **Single-Authority Resolution Gates - Phase 1 (#2181, #2173).** New architectural
  gates enforce a single resolution authority for surface placement, preventing
  kind-blind or primary-anchored resolvers from re-introducing split-brain reads.

### 💥 Breaking Changes

- **Removed**: Hidden `--feature` alias hard-removed from 8 user-facing CLI commands
  (`implement`, `merge`, `next`, `research`, `context`, `accept`,
  `lifecycle plan`, `lifecycle tasks`, `mission-type current`).
  Passing `--feature` on any of these commands now yields exit code 2 with
  "No such option: --feature". Use `--mission` instead. (#1060)
- **Fixed**: No-selector guard on all 8 commands now exits with code 2 and a readable
  error message instead of a potential `TypeError` traceback.

### 🐛 Fixed

- **`SPEC_KITTY_HOME` now isolates _all_ local Spec Kitty state, not just runtime
  assets (fixes #2171).** Previously the variable governed runtime/Mission assets
  while global sync state - sync `config.toml`, hosted-auth session and refresh
  lock, event queues and the active queue scope, the Lamport clock, the sync
  daemon (state/log/lock), and tracker credentials/cache - still resolved to the
  shared default home (`~/.spec-kitty` on POSIX). An operator who exported
  `SPEC_KITTY_HOME` to target a separate hosted environment would silently read
  and write their everyday dev session. Every global-state surface now derives
  from a single authoritative root (`specify_cli.paths.get_runtime_root`) that
  honors `SPEC_KITTY_HOME` on Linux, macOS, and Windows. When the variable is
  unset the POSIX default (`~/.spec-kitty`) is byte-identical to prior releases;
  on Windows the surfaces that previously leaked to `~/.spec-kitty` are
  normalized onto the platformdirs app-data base. No automatic migration of
  existing `~/.spec-kitty` data is performed - setting the variable selects a
  (possibly fresh) separate root and leaves existing default-home data in place.
- **`--json` output is now safe to capture with `2>&1`.** The CLI correctly puts
  the JSON object on stdout and diagnostics on stderr, but agents commonly invoke
  `spec-kitty … --json 2>&1` and parse the _merged_ stream - so any warning/log line
  on stderr (e.g. `CharterCatalogMissWarning`, deprecation notices) corrupted the
  JSON. In `--json` mode the logging bootstrap now runs in a silent mode: every root
  log handler is raised above real records and a `NullHandler` is installed when none
  exist, so Python's `lastResort` WARNING→stderr fallback never fires and
  `captureWarnings`-routed warnings are dropped too. A successful `--json` run emits
  only the JSON object on both stdout and the merged `2>&1` stream; genuine command
  errors are still emitted as JSON on stdout by the commands themselves. (Typer
  _usage_ errors for genuinely malformed invocations still print to stderr - a
  separate, pre-dispatch surface.)
- **`spec-kitty accept` no longer false-positives on a mission's `contracts/` path
  convention.** The accept gate's path-convention check (`validate_mission_paths`)
  resolved every mission-declared path against the repo root, so a mission-artifact
  path like software-dev's `deliverables: contracts/` (also an `artifacts.optional`
  entry) was sought at `<repo_root>/contracts/` and reported missing - telling the
  operator to `mkdir -p contracts/` even though `contracts/` existed and was committed
  at `kitty-specs/<mission>/contracts/`. A declared path that is a mission artifact
  (member of `mission.config.artifacts`) is now resolved against the mission's primary
  feature dir via the canonical `planning_read_dir` surface (the same one
  `_missing_artifacts` uses) - no repo-root fallback; build paths (`src/`/`tests/`/
  `docs/`) stay repo-root. A residual of the #1716 / #2113 "no resolution to the repo
  primary for mission artifacts" cluster.
- Retired the unsupported `specify_cli.mission_read_path` backcompat import path (#2048),
  after its last production caller had moved to `specify_cli.missions._read_path_resolver`.
  Supported callers should use `resolve_handle_to_read_path` /
  `resolve_feature_dir_for_mission`; white-box tests that need the 3-argument worker may
  import `_resolve_mission_read_path` directly.
- **Retrospectives are persisted before any coordination teardown (#2119, #1771).**
  The merge and `close --discard` paths now write the retrospective to its durable
  home _before_ destroying the coordination worktree (persist-before-destroy, run
  outside the best-effort swallow), via one shared `coordination/teardown.py` seam
  that consolidates the previously-duplicated teardown call sites. The 6 retrospective
  home-resolution sites are unified onto a single primary-anchored authority.
- **Handle-blind PRIMARY reads are canonicalized at the seam entry (#2136).**
  `resolve_planning_read_dir` now canonicalizes a bare `mid8`/`slug` handle on the
  caller side (keeping the `primary_feature_dir_for_mission` primitive blind to avoid
  recursion), so a bare handle no longer resolves to a different directory than a
  pre-resolved `<slug>-<mid8>` one; ambiguous handles raise rather than silently pick.
- **Phantom `spec-kitty agent worktree repair` recovery guidance replaced with the
  real `spec-kitty doctor workspaces --fix` (#1890)**, enforced by a `src/`-scoped,
  count-agnostic grep-guard.
- **Coordination-topology missions read and write every artifact from the correct
  surface (#2160, #2226, #2212, #2194).** Identity reads (`meta.json`), merge/lane
  reads (`lanes.json`, work-package `tasks/`), and the implement / review / merge
  loop now resolve coordination-topology planning artifacts on the primary surface
  through the kind-aware resolution seam, while status stays on the coordination
  worktree (closes #2185, #2186, #2187, #2115, #2140, #2183). Gate-authority
  hardening stops a coordination mission from reading early/empty state and routing
  an agent to the wrong next step (closes #2197, #2198, #2199, #2214).
- **`mission close --discard` now actually tears down coordination-topology
  missions (#2121)** instead of leaving the coordination worktree and branch behind.
- **`mission close --discard` targets worktrees by exact name, not a `<slug>-*`
  prefix (#2129)** - a sibling mission whose slug shared a prefix could previously be
  discarded too (data loss).
- **The accept gate resolves `mid8` / ULID mission handles for its primary-partition
  reads (#2126)** instead of only the fully-qualified `<slug>-<mid8>` form.
- **The generated charter now interpolates the project documentation policy into its
  directive (#2153)** rather than emitting an unresolved placeholder.
- **`spec-kitty doctor` reports unsanctioned built-in doctrine-graph overrides
  (#2082)** and the dead override-policy symbol debt is retired.
- **Tooling robustness:** `uv tool upgrade` is no longer pinned to a stale rc release
  (#2143); `tomli_w` is imported lazily so a stale environment can no longer brick the
  CLI (#2132); `run_tests` detects the host Python interpreter (#2137); and lane
  auto-rebase restores managed-artifact (`lanes.json` / `tasks/` / `WP*`) take-theirs
  classification (#2147).

### ♻️ Changed

- **Extracted a shared atomic-YAML writer in `retrospective/writer.py` (#2125)**,
  de-duplicating the write-temp-then-rename logic across the record-write sites, and
  hoisted the `retrospective.yaml` filename to a single named constant.

- **Orchestrator no longer stalls on a coord/`pr_bound` mission rooted on a writable
  target branch (#2118).** Continuing the split-brain remediation: the `#2090`
  write-surface change routes planning artifacts (`lanes.json` → `LANE_STATE`, WP
  `tasks/` → `WORK_PACKAGE_TASK`) to the primary `target_branch`, but the
  `orchestrator-api` read path still read them off the coordination worktree (which
  carries only status). Under coordination topology the dependency graph came back
  empty, so `list-ready`/`mission-state` saw no schedulable work and the orchestrator
  stalled with every WP stuck at `lane=planned`. The orchestrator's PRIMARY-partition
  reads (`require_lanes_json`, `read_lanes_json`, `build_dependency_graph`, WP
  `tasks/` lookup) now resolve through the kind-aware `resolve_planning_read_dir`
  seam (primary surface for all topologies), mirroring the existing `meta.json`
  treatment in `_resolve_merge_target_branch`; STATUS reads (`read_events` /
  `materialize`) stay on the coordination worktree. Related: #2115 (the
  implement/review/merge read-surface twin), #1716 / #1878 (coordination-topology
  coherence).

- **Mission-lifecycle tooling friction batch (#2224, #2217–#2223).** A set of
  fixes to the planning and implementation loop's tooling surfaces, sliced from the
  Doctrine-Fidelity retrospective follow-ups.
- **Clearer global CLI install guidance (#2231)** for installing `spec-kitty` as a
  global tool.
- **Internal maintainability.** Several god-modules were decomposed into focused
  seams - `cli/commands/doctor.py` (#2059), `agent/mission.py` (#2056),
  `cli/commands/merge.py` (#2057), and `agent/tasks.py` (#2058); the dead-symbol
  architectural gate was hardened with a parser fix, detectors, and a teeth
  self-test (#2158); and the pre-3.0 read-path shims were retired (#1057, #2048).

## [3.2.2] - 2026-06-24

Patch release continuing the post-3.2.0 stabilization, focused on the
**coordination/primary surface-resolution ("split-brain" / file-location)
remediation**. Remediation of these recent file-location issues is **ongoing**, but
progress is significant enough to warrant a new release - we will continue stabilizing
the functionality. This release also adopts a coherent test-flakiness policy, hardens
CI test coverage, and decomposes the `agent/tasks.py` god-module.

### ✨ Added

- **Single, kind- and topology-aware artifact-surface authority (split-brain remediation).**
  Mission planning artifacts and reads/writes now resolve through one canonical surface
  authority instead of drifting between the coordination worktree and the primary checkout:
  - `MissionTopology` SSOT + `routes_through_coordination` route every decision site through
    one classifier; a single read-surface resolver and a single **write-surface** authority
    replace the parallel derivations (#2070, single-authority topology cleanup).
  - Planning + identity artifacts are placed by a kind-aware `MissionArtifactKind` partition —
    planning/identity kinds land on the primary `target_branch` for all topologies; status/
    bookkeeping stays on coordination (#2090 write-surface coherence; ADR for kind- and
    topology-aware placement, #2101).
  - The planning-lifecycle **gate/verify commands** (`setup-plan`, `accept`, `map-requirements`,
    `record-analysis`, `research`, and the `finalize-tasks` commit) now read/commit planning
    artifacts via that seam - closing the case where a coord-topology mission authored on
    primary but verified from coordination (#2113; closes #2107, #2085, #2102). A default-deny
    architectural literal-ban ratchet prevents the class from regrowing.
- **CI test-coverage hardening.** A static gate-coverage checker + orphan ratchet flags tests
  selected by zero CI gates and ratchets the backlog down (#2067, folds #1933); hot
  churn-magnet orphans and `tests/runtime/` are now gated and run on every PR (#2108, #2109, #2111).
- **Maintainability:** the 4633-LOC `agent/tasks.py` god-module is decomposed into five cohesive,
  one-way-import seam modules with a byte-identical CLI surface; the three planning-commit tails
  are centralized through `commit_for_mission` (#2058 / #2114; follow-up body-thinning + FR-007
  consolidation tracked in #2116).
- **Test-flakiness handling policy (#2038):** a suite-wide policy (`docs/guides/testing-flakiness.md`)
  - never retry-to-green; three tiers (budget / correctness / environmental), each with one sanctioned
  response - plus an env-gated, **non-blocking** `quarantine` pytest marker (held out of every normal/
  blocking run unless `SPEC_KITTY_RUN_QUARANTINE=1`), distinct from the mutmut-deselection `flaky` marker.

### 🐛 Fixed

- **Surface-resolution "split-brain" / file-location fixes (coordination vs primary).**
  - Mission-identity reads (mid8 / `mission_id`) are anchored on the **primary** surface, so a
    coord-topology mission no longer builds a malformed coordination branch from an empty mid8 (#2091).
  - `finalize-tasks` aligns on the primary planning surface and the ownership-overlap validator is
    **lane/dependency-aware** - dependency-ordered WPs that legitimately share `owned_files` are no
    longer falsely rejected (#2087, #2088).
  - The read path no longer returns a stale coordination "husk" for a flattened/single-branch mission:
    the stored topology gates the husk short-circuit (#2062); `map-requirements` and `finalize-tasks`
    share one WP-frontmatter read surface (#2064).
  - Write-branch resolvers (`get_feature_target_branch`, `resolve_target_branch`, the `finalize-tasks`
    commit) read `meta.json` on the **primary** surface, so commits no longer silently fall back to the
    repo default `main` under coordination topology.
- **Coord-topology orchestration: WPs reached `done` with nothing committed or integrated.** Three fixes,
  all on the external `orchestrator-api` path for coordination-topology missions:
  - `start-implementation` no longer crashed with `TypeError: transactional status batch only supports one
    feature/mission/wp` - the transactional batch guard now anchors the per-request consistency check on the
    first request's canonicalized dir (matching the non-transactional sibling) instead of the resolved primary
    anchor, which legitimately differs from the coord-worktree request surface.
  - `append-history` now commits the WP prompt file from the coordination worktree (via the canonical
    `resolve_placement_only` target) instead of the primary checkout, fixing a `SAFE_COMMIT_PATH_POLICY`
    refusal that stalled the orchestrate loop.
  - `start-implementation` now allocates the **real lane worktree** (lane branch on the coordination branch,
    with dependency-lane tips merged) instead of returning a bare legacy path, so `merge-mission` has a lane
    branch to integrate and dependent WPs see their dependencies' code. Its response now carries `lane_id`,
    `lane_branch`, and `lane_base_ref`, and `workspace_path` now means that lane worktree. The `for_review`
    transition is gated on a real commit existing beyond the lane base (shared with the native `move-task`
    gate), so "done without a commit" is impossible via the API too.
  - Both `spec-kitty merge` and `orchestrator-api merge-mission` now resolve the target branch from the
    **primary-checkout** meta.json (`merge_target_branch` then `target_branch`) via one shared resolver
    (`core.paths.resolve_merge_target_branch`), instead of the coord-aware read surface - which under
    coordination topology has no meta.json and made the resolver silently fall back to the repo default
    (`main`), merging the mission into the wrong branch (and tripping a downstream `SafeCommitHeadMismatch`).
    Explicit `--target` still wins; the repo default is only used when no mission target is set.
- **Non-deterministic xdist collection in `tests/specify_cli/shims/test_registry.py` (#2038):** the
  frozenset-derived parametrize sets are now `sorted()`, so workers collect an identical order
  (root-cause fix - no retry).

### ⚠️ Contract

- `orchestrator-api` `CONTRACT_VERSION` bumped to **1.1.0**: additive `start-implementation` response fields
  (`lane_id`, `lane_branch`, `lane_base_ref`) and a changed meaning for `workspace_path` (now the lane
  worktree). New error code `LANE_ALLOCATION_FAILED`.

## [3.2.1] - 2026-06-18

Patch release stabilizing the scaffolds around the functionality introduced in 3.2.0. Remediates
blocking issues witnessed after 3.2.0; not every discovered issue is remediated here, and further
patch releases are expected in quick succession.

### 🐛 Fixed

- **Orchestrator coord-read of coord-only missions (#2016):** `orchestrator_api` now resolves a mission that
  exists only as a coordination worktree (no primary `meta.json`) by adopting the canonical mid8 cascade
  (`meta.mid8` → declared `mission_id` → `<slug>-<mid8>` tail) instead of a strict-only reimplementation that
  returned `None`. Legacy non-coord missions keep their primary-read path; genuinely unresolvable handles still
  fail closed.
- **Charter status/sync/preflight coherence (#2009, epic #2007/C2):** `charter status --json` no longer crashes on
  a non-JSON-safe `datetime` in the bundle metadata; the DRG "`built_in_only` + stale `graph.yaml` residue" state
  is now a non-blocking read-time diagnostic instead of a preflight-blocking `invalid`; and a BOM/CRLF hash
  divergence between `sync` and `status`/freshness (which produced a `noop`-despite-stale `charter sync`) is fixed
  by canonicalizing line endings/BOM in the single `charter.hasher.hash_content` seam. Regression tests pin the
  already-landed status side-effect-free and hash-unification fixes.
- **Green the architectural CI gate (#2025):** corrected pytest markers on a subprocess/git test, removed a
  mission-diff-scoped test that did not belong on `main`, and made the architectural ratchet composite keys
  interpreter-stable (Python 3.11 ↔ 3.12 f-string tokenization), re-greening the `tests/architectural/**` shard
  that went red when 3.2.0's gate-un-mask first ran on `main`.

### 🔧 Changed

- **merge.py decomposition, slice 1 (#2027, epic #2026):** extracted the `baseline_merge_commit` record/verify
  cluster from the oversized `cli/commands/merge.py` into a dedicated `specify_cli/merge/baseline.py`,
  behavior-preserving with back-compat re-exports (public + legacy private names).
- **Charter constant single-sourced:** the `_GRAPH_FILENAME` value, previously duplicated across three modules,
  now resolves from one leaf `charter.synthesizer._constants`.

### 🐛 Fixed (security follow-up)

- **SonarCloud + Dependabot:** re-exported the charter package helper named in `__all__`, hardened merge
  bookkeeping projection so status-surface paths cannot resolve outside trusted repo roots, and refreshed locked
  crypto/tooling dependencies to patched releases (`cryptography 49.0.0`, `pip 26.1.2`) so the security gates stay
  clean.

## [3.2.0] - 2026-06-16

### ✨ Added / 🔧 Changed

- Stable 3.2.0 release of the mission-runtime, profile-invocation, tool-surface,
  branch-authority, and coordination-worktree line after the rc45 validation cycle.
  This promotes the accumulated 3.2.0 release-candidate fixes to the default PyPI
  channel.

## [3.2.0rc45] - 2026-06-15

### 🐛 Fixed

- **Agent profile projection plugin production follow-through (PR #1975):** Claude Code plugin bundles now emit
  strict-validator-compatible `skills`/`agents` component paths and a valid empty hooks record; init/upgrade
  auto-repair no longer builds optional disabled plugin bundle artifacts or silently writes Amazon Q user-global
  agent profiles; docs inventory, lockfile, and Roo-deprecation test expectations are refreshed for the CI gates.

## [3.2.0rc44] - 2026-06-14

### ✨ Added

- **ToolSurfaceContract unified registry (mission `tool-surface-contract-01KV2K2P`, PR #1948):**
  `src/specify_cli/tool_surface/` is now the bounded context for configured tool surface policy.
  `spec-kitty doctor tool-surfaces --json` reports stable findings and repair commands across command
  skills, doctrine skills, session/context surfaces, native agent profile projections, and plugin
  bundle surfaces. `doctor skills --json` remains backward-compatible, legacy `agent config` flows
  still work through the new contract, and fresh clones now get actionable generated-surface repair
  plans instead of silent missing `.agents/skills/` drift.
- **Branch-strategy recommendation in `/specify` (issue #765):** `spec-kitty agent mission branch-context`
  now resolves the repository's primary branch and emits a recommendation payload (`primary_branch`,
  `current_is_primary`, `recommended_strategy`, `reason`). The software-dev specify prompt consumes it to
  **proactively** recommend starting on a dedicated feature branch; `mission create --start-branch` now
  creates/switches before any mission artifacts are written when the operator is on the primary branch and
  expects a later PR; staying on the current branch remains an explicit, supported choice (wiring `--pr-bound`
  branch-strategy gate into the operator flow). The recommendation fields are additive and opt-in: callers
  that do not resolve a primary branch receive the byte-identical legacy branch contract.

### 🐛 Fixed

- **Docs: corrected the retired `spec-kitty agent workflow implement` command (issue #1874):** the
  `agent workflow` command group no longer exists (the canonical form is `spec-kitty agent action
  implement` / `… review`). Updated the user-facing `docs/how-to/implement-work-package.md` and the
  `AGENTS.md` testing note. (The same stale command also appears in the PowerShell toolguide and the
  documentation/research per-WP task-prompt templates; those are rendered into the twelve-agent command
  snapshots, whose baselines are already drifted on `main`, so that replacement is left to the
  cli-reference-audit sweep which can regenerate the baselines in one pass.)
- **`spec-kitty upgrade` no longer churns `metadata.yaml` on a no-op (issue #1871):** the "stamp
  `last_upgraded_at` only on material change" rule lived in three divergent idioms, and the migrations-applied
  root path plus `_stamp_schema_version` rewrote `metadata.yaml` (and advanced the timestamp / mtime) even when
  every migration was already recorded. `ProjectMetadata.save()` now does a **masked compare-before-write**
  (skipping the write when only the volatile `last_upgraded_at`/`schema_version` would change) and
  `_stamp_schema_version` skips its re-dump when the rendered bytes already match disk. A genuine
  version/migration/environment change still writes with a fresh timestamp; a no-op upgrade - including across a
  fully-recorded version range, on both the root and worktree paths - is now zero writes. This closes the class
  at the write boundary for upgrade/doctor/regeneration instead of adding a fourth per-path guard.
- **`agent tasks map-requirements --json` no longer crashes on auto-commit (issue #1891, Finding 1):** the
  command stored the `CommitResult` returned by `safe_commit()` directly in the `--json` payload, so on the
  auto-commit success path `json.dumps` failed with _"Object of type CommitResult is not JSON serializable"_ —
  the mapping succeeded but agents got an unparseable error instead of the result. `committed` is now a bool
  and the resulting `commit_sha` (or `null`) is exposed alongside it. (Findings 2 and 3 - `agent action
  implement --json` and `setup-plan`/`finalize-tasks` JSON preamble - are tracked separately.)
- **`accept --lenient` now relaxes mission path conventions (issue #1892):** `spec-kitty accept` / `agent
  mission accept` validated a mission's declared `paths` (`src/`, `tests/`, `contracts/` for software-dev)
  unconditionally, so repos with a non-default layout (e.g. a Go service using `internal/` with no top-level
  `tests/`) failed acceptance even with `--lenient` - the only workaround was creating throwaway empty
  directories. Path conventions now block only in strict mode; under `--lenient` an unmet convention is
  surfaced as a non-blocking warning. (A per-project `paths` override remains a possible follow-up.)
- **Name-vs-authority remediation (mission #133; closes #1889, #1860, #1865, #1866, #1867, #1863, #1896, #1898, #1904, #1684, #1906):** (#1884/#1883/#1885 were independently fixed by PR #1910 and are verified-already-fixed here, not re-closed)
  binds the two remaining "a name/string shape is trusted as authority without cross-checking the declared authority"
  seams and ratchets them closed, and clears the live 3.2.0 release-blocker P0s rooted in that class. Topology
  authority seam (`WorktreeTopology` + `classify_worktree_topology` + `is_registered_coord_worktree` in
  `coordination/surface_resolver.py`, wrapping the `git worktree list --porcelain` registry) and branch-identity
  authority seam (`mission_branch_name_required` + structured `BranchIdentityUnresolved` in `lanes/branch_naming.py`,
  dual-era: legacy `\d{3}-` AND mid8 names both resolve) replace the convention predicates at their consumer sites;
  the `(slug.replace('-','')+"00000000")[:8]` mid8-fabrication idiom is eradicated (routed through
  `resolve_transaction_mid8`, fail-closed). **P0s fixed:** `setup-plan`'s committed-spec gate verifies against the
  placement authority's ref not primary HEAD (#1884); the accept gate is idempotent across all modes via
  accept-owned-path exclusion (#1883); unresolvable mission handles raise a structured `MissionNotFoundError`
  (code + next_step, #1911) instead of a silent `mission=unknown` stub (#1885 residual). #1889's coordination-branch-deleted
  case becomes a distinct loud `CoordinationBranchDeleted` (decision-table row R3). An architectural ratchet
  (`test_topology_resolution_boundary.py`) keeps coord predicates, unbackstopped `kitty/mission-{slug}` composes, and
  the fabrication idiom from regrowing outside the blessed seam modules. Doctrine refinements (#1865/#1866/#1867) and
  the DRG extractor styleguide/toolguide `references` walk (#1863) ride along; the authority-path default flips
  `architecture/2.x/adr` → `3.x/adr`. **Cross-lane dependency code propagation (#1684):** `allocate_lane_worktree`
  now merges approved dependency-lane tips (fresh creation + lane re-entry) so a dependent WP in a sibling lane sees
  its approved dependency's code, instead of branching from the bare mission branch.
- **`_branch_exists`/`ref_exists` consolidation (#1904):** the duplicated `git rev-parse --verify` branch/ref
  existence idiom across `coordination/status_transition.py`, `missions/_create.py`, `lanes/worktree_allocator.py`,
  and `lanes/merge.py` is unified into `lanes/_git.py` (env-parameterized so the merge path's environment composes).

### 🧹 Maintenance

- **SonarCloud hygiene on mission #133 surfaces:** raised new-code coverage on the authored seam/allocator/query
  files; reduced cognitive-complexity (extract-method) and duplicate-literal smells across `doctrine.py`,
  `sync/daemon.py`, `sync/owner.py`, `drg/validator.py`, `org_charter.py`, `_read_path_resolver.py`, `core/worktree.py`,
  `agent/workflow.py`, and `upgrade.py` (all behavior-preserving); regenerated stale codex/vibe command-skill
  snapshots to match the advanced templates (PR #1897 finding).

- **Upgrade no longer re-records not-applicable migrations (issue #1872):** a migration whose `detect()`
  is `False` was re-appended as a `skipped` / "Not applicable" `MigrationRecord` on every `spec-kitty upgrade`
  run over the same version range, growing `applied_migrations` without bound and - for worktrees, after
  #1857 - bumping `last_upgraded_at` on no-op runs. `ProjectMetadata.record_migration()` is now idempotent
  (an identical `(id, result)` record is not re-appended) and the worktree upgrade path only marks metadata
  dirty when a new record was actually written, restoring stable `last_upgraded_at` for no-op re-runs. A
  genuine `failed → success` transition still records the new result.
- **Coordination & Merge stabilization (mission 131; closes #1826, #1861 Part 1, residuals of #1833/#1814/#1736/#1735):**
  merge-pipeline ref advances now resync any worktree checked out on the advanced branch (shared
  `git/ref_advance.py` helper with a no-raw-`update-ref` architectural ratchet), refusing loudly - never
  resetting - when the worktree holds uncommitted state; the safe-commit backstop message names the diverged
  worktree/ref/state; `finalize-tasks --validate-only` no longer switches the git checkout; task finalization
  cleans its own primary-checkout residue (operator files untouched); workspace resolution treats non-worktree
  "husk" directories under `.worktrees/` as structured failures instead of silently running git against the
  primary repo, with a new `spec-kitty doctor workspaces [--fix]` check for self-serve recovery - **note:**
  pre-existing husks that previously failed silently now produce explicit errors; run
  `spec-kitty doctor workspaces --fix` once to clean them; retrospective gating reads route through the
  canonical status surface (AC10 ratchet); `upgrade --dry-run` no longer prints a success line implying
  changes were applied; merge-driver hardening (single `_make_merge_env()` authority, narrowed exception
  mask, deterministic mixed-timestamp event-log sort).
- **Protected-branch guard capability honesty (PR #1850 review):** the bool→capability conversion had
  re-opened protected-ref commits from production flows - three sites asserted `GuardCapability.TEST_MODE`
  (legacy workflow commit, baseline-artifact commit, finalize-tasks bootstrap) and six non-merge flows
  borrowed `MERGE_BOOKKEEPING` (move-task, mark-status, map-requirements, decision-log, op-record). All
  now assert `STANDARD`; protected destinations refuse, and refusals degrade gracefully (decision events
  and Op records are preserved on disk, nothing lands on the protected ref). `SPEC_KITTY_TEST_MODE` no
  longer waives the command-level protected-branch prechecks - only the documented operator hatch
  `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` does - and the coordination gate now computes the same
  hatch-aware `ProtectionState` as `safe_commit`, so the two can no longer disagree. Ratcheted by
  `tests/architectural/test_guard_capability_call_sites.py` (capability→flow allowlist; `TEST_MODE` has
  zero `src/` callers) and `tests/git/test_guard_capability_regression.py`.
- **Mission handle canonicalization completes at every CLI write boundary (PR #1850 review):** bare mid8,
  numeric-prefix, and full-ULID handles now resolve to the identical canonical `mission_slug`,
  `mission_id`, status surfaces, and placement (ref and kind) as the full slug - across
  `resolve_status_surface_with_anchor`, `resolve_placement_only`, `MissionStatus.load`,
  `_find_mission_slug` (agent tasks/status/workflow), `agent decision open`, `merge --mission`,
  `spec-kitty next --mission`, `plan --mission`, `mission run/close --mission`,
  `research --mission`, and `context resolve` (persisted `authoritative_ref`). No more
  wrong-but-plausible `kitty-specs/<mid8>/` paths, `legacy-<mid8>` identities, split-brain runtime
  runs or SaaS sync namespaces keyed by the raw handle, or `close --discard` silently leaving lane
  branches/worktrees behind. Pinned by
  `tests/specify_cli/missions/test_handle_equivalence_matrix.py` (78 parity tests).
- **Sync daemon reaper is scoped to its daemon root, not just the interpreter (PR #1850 review):** the
  spawner embeds the resolved daemon state root and spawn-time interpreter identity as inert argv markers;
  the reaper kills only on marker + spawn-signature + interpreter-identity match and conservatively skips
  unmarked or unidentifiable processes. Fixes both the cross-`$HOME` over-kill and the macOS
  framework-Python inertness (where the re-exec rewrites `exe()` and `argv[0]` to the `Python.app` stub).
- **CI `next` filter covers the canonical runtime:** `src/runtime/next/**` and `src/mission_runtime/**`
  now trigger the next suites and count toward diff-coverage critical paths (previously only the
  deprecated `src/specify_cli/next/` shim was mapped, so `integration-tests-next` skipped on
  canonical-runtime changes).
- **`StatusReadPathNotFound` no longer escapes `mission_runtime`'s single-error contract:** the fail-closed
  refusal is translated to `ActionContextError` (error code and message preserved) at all three resolution
  boundaries and handled in the transactional status path; `MissionStatus.load` keeps its established
  `CoordAuthorityUnavailable` shape for every handle form in the fail-closed coordination window.
- **Repo hygiene:** per-machine `.kittify/legacy-warning-shown-*` marker files untracked and gitignored.

## [3.2.0rc43] - 2026-06-11

### ✨ Added / 🔧 Changed

- **Tooling stability & guard coherence (mission 01KTRC04, slice of #1619, closes the #1796 cluster):**
  the safe-commit / protected-branch guard is ONE mechanism - a pure Shared-Kernel policy module
  (`core/commit_guard.evaluate(target, protection_state, capability) -> GuardVerdict`) behind the single
  `git/commit_helpers.safe_commit` facade. The five legacy privilege channels (message-prefix allowlist,
  `allow_protected_branch_in_test_mode`, `allow_completed_op_on_protected_branch`, op-record file-content
  exception, env hatches) are DELETED; protected flows assert an explicit `GuardCapability` at the call
  site (never derived from message/file/env). Operator escape hatch `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`
  retained. Permanently ratcheted by `tests/architectural/test_safe_commit_import_boundary.py` (#1355).
- **Planning placement single authority (#1777/#1784/#1631/#1334):** `mission_runtime.resolve_placement_only`
  is the one commit-destination authority for planning paths; `_resolve_planning_branch` destination
  authority retired. Legit spec/plan commits on protected branches route to the resolved destination with
  ZERO guard relaxation; the finalize-tasks branch catch-22 is gone (idempotent re-runs).
- **safe-commit ergonomics (#1820/#1330):** directory arguments expand to contained dirty files with a
  per-file report; explicit `--to-branch` honored; `SPEC_KITTY_INFER_DESTINATION_REF` retired.
- `record-analysis` verdict derived from the structured `analysis-findings/v1` frontmatter table - prose
  substring counting removed (#1819); severity vocabulary reuses `SEVERITY_ORDER` (no parallel model).
- Carried `StatusSurfaceFragment` threaded through `MissionStatus.load` + `status_transition` (#1821).
- `doctor.py` doctrine profile-health rendering extracted to `_profile_health_render.py` (#1623 slice).
- DRG provenance is a declared typed field on `DRGNode`/`DRGEdge`; the `object.__setattr__` sidecar is
  deleted; `graph.yaml` byte-stable (#1624).
- ADR 2026-06-03-2 addendum: Strangler **Step 7 delivered** (CommitTarget consumed by safe_commit).

## [3.2.0rc42] - 2026-06-11

### 💥 Changed

- **Op record schema v2 (WP01, do-dispatch-open-op-lifecycle)**: the dual-purpose
  `InvocationRecord` model is split into frozen `OpStartedEvent` /
  `OpCompletedEvent` Pydantic v2 models. Completed events now require `outcome`
  and `closed_by` and carry no started-only fields; blank-default records are
  unrepresentable. Readers of `kitty-ops/*.jsonl` warn-and-skip legacy (pre-v2)
  lines, pointing at `spec-kitty upgrade`; `parse_op_event` raises a catchable
  `LegacyRecordError` for them. `spec-kitty invocations list` now shows
  `outcome` and `closed_by` for closed Ops. `artifact_link`, `commit_link`, and
  `glossary_checked` event shapes are unchanged.
- **Breaking - standalone dispatch no longer auto-closes its Op as `done`
  (dispatch-open-op-lifecycle)**: `spec-kitty dispatch` opens the Op and loads
  governance context; the working agent closes it via
  `spec-kitty profile-invocation complete --invocation-id <id>
  --outcome <done|failed|abandoned>` (completed-event schema v2: `outcome`
  required, new `closed_by` field). New `spec-kitty doctor ops --close-stale`
  sweeps stale open Ops closed as `abandoned` (`closed_by: doctor_sweep`).
  Legacy `kitty-ops` records are migrated (rewrite-or-delete) by
  `spec-kitty upgrade`. Claude Code session presence now lists open Ops at
  session start, a new `Stop` hook (`spec-kitty session-stop`) reminds at
  session end, and the doctrine skill pack / standalone command templates
  document the open→work→close contract.

### 🐛 Fixed

- Hardened the v2 Op migration and readers: `spec-kitty invocations list` skips
  dangling `ops-index.jsonl` rows after unsalvageable Op files are deleted, and
  migration idempotency now treats only v2-parseable `mode_of_work` / `closed_by`
  values as already migrated.
- Preserved machine-readable output for standalone dispatch `--json` by
  suppressing post-payload inline glossary notices on JSON paths; rich output
  still shows the notices.
- Updated the rich standalone-dispatch close hint to include the now-required
  `--outcome <done|failed|abandoned>` flag.
- Replaced stale short profile aliases in shipped mission-runtime templates
  (`researcher`, `architect`, `planner`, `implementer`, `reviewer`) with the
  canonical shipped profile IDs, preventing fresh `software-dev` runs from
  blocking on missing invocation profiles.
- `spec-kitty merge` now skips empty post-merge bookkeeping commits after a
  successful lane merge instead of failing the command after the target branch
  has already been updated.

### ✨ Added / 🔧 Changed

- **Execution-context unification (mission 01KTPKST, slice of #1619/#1666):** structurally drained the
  coord-vs-primary split-brain class. One `MissionExecutionContext` (doc-09 fragment/op-composite +
  `CommitTarget`) resolved once and threaded through all command surfaces; status owned by the
  Mission-Management OHS facade. Collapsed the duplicate read-path resolver, the two worktree-pointer
  parsers, and the three sync-daemon orphan-reapers; `materialize_if_stale` now skips during git ops
  (no status clobber on rebase); dashboard reads are write-free (`materialize_snapshot`); sync-daemon
  singleton enforced one-per-host/auth-scope; occurrence-map gained multi-path `moves:` (backward-compatible);
  retrospect record relocated to a tracked home (committable). Adds a dual-CWD + flattened-topology parity
  ratchet (`tests/architectural/test_execution_context_parity.py`).
- Drains #1814, #1816, #1789, #1071, #1062, #1572, #1737, #1357, #1735, #1771, #1736, #1770, #1764, #1815,
  #1622 (partial); follow-ups #1819/#1820/#1821 filed.

## [3.2.0rc41] - 2026-06-08

### ✨ Added

- Introduced canonical `mission_runtime` umbrella package (`src/mission_runtime/`) as the sole
  sanctioned execution-state resolver; `resolve_action_context` is now the single entry point
  for all mission/WP context resolution (epic #1666 slice 2, ADR `2026-06-07-1-execution-state-canonical-surface.md`).
- Added `_branch_trees_equal` predicate in merge command for content-based squash-resume
  idempotency (FR-037); replaces ancestry-based `rev-list` check that failed after squash merges.
- Added `path_is_under_worktrees` guard to `_stage_finalize_artifacts_in_coord_worktree`
  (FR-035); finalize/implement can no longer stage sources already under `.worktrees/`, preventing
  nested-worktree path pollution on coord-topology missions (#1772 Bug 0).
- Added `rebuild_mission_event_log` canonical rebuild entry point for migration paths (#1754).
- New ADR `2026-06-07-1-execution-state-canonical-surface.md` documenting the sole-resolver
  boundary and migration contract.

### 🔧 Changed

- `status/` facade now enforced repo-wide: ~219 deep `specify_cli.status.<sub>` imports
  collapsed to 21 across `src/specify_cli` and `src/runtime` (724 files covered by boundary test).
- `mission_read_path.py` converted to a thin compatibility shim over the canonical
  `specify_cli.missions._read_path_resolver`; duplicate resolver implementation eliminated.
- `mission_runtime.__all__` trimmed to the 4-symbol public contract; historical first-party
  names (`ActionContext`, `ActionName`, `ACTION_NAMES`, `_resolve_mission_slug`) served via
  `__getattr__` without appearing in the public surface.
- `resolve_action_context` top-level imports moved to deferred (inside function bodies),
  breaking the `mission_runtime → dependency_graph → status → uninitialized_hint → dependency_graph`
  circular import; cold `import mission_runtime` now works without prior status initialization.
- `FrontmatterSource` and `resolve_wp_manifests` routed through single ownership ports (#1757).
- Mission-identity snapshot carry-through added to `runtime_bridge.py` (#1663).
- Full-sequence parity ratchet (`test_execution_context_parity.py`) extended to cover
  `next → implement → move-task → review → status` across three execution modes plus a
  negative control (#1672).

### 🐛 Fixed

- Coord-topology merge hardening (#1772): `path_is_under_worktrees` predicate applied at
  staging; `_lane_already_integrated` tree-diff gate (fail-loud on zero-diff squash); in-branch
  status validation; `doctor` check for tracked `.worktrees/` content.
- Cold import of `mission_runtime` no longer raises `ImportError: cannot import name
  'detect_cycles' from partially initialized module` (circular import via status facade).
- `mission_runtime_api.md` contract corrected to match actual `resolve_action_context` signature
  (`action`/`feature` keyword args, not positional `mission`).
- `status_boundary.md` updated to document `workspace/context.py` as a permanent third
  exemption (import-time cycle breaker); contract and test allow-list now in sync.
- Raw `kitty-specs/` path construction eliminated from call sites; all paths go through the
  single resolver (FR-009).
- Closed: #1673, #1664, #1672, #1663, #1757, #1754, #1772.

## [3.2.0rc40] - 2026-06-07

### ✨ Added

- Introduced `Lane.GENESIS` pseudo-state and a canonical `WPState` State-pattern FSM in
  `specify_cli.status.wp_state`, making the FSM the single source of truth for WP lanes,
  edges, and transitions (mission `wp-lane-state-machine-fsm-01KTGZAZ`).
- Added ADR `2026-06-07-1-wp-lane-fsm-genesis-and-finalize-clobber.md` documenting the
  genesis-lane bootstrap and the finalize event-log clobber fix.

### 🔧 Changed

- Routed all WP lane validation and mutation through the single FSM transition primitive;
  callers no longer reconstruct transition authority from derived constants (#1666).

### 🐛 Fixed

- `implement` and `finalize` no longer overwrite the coordination branch's canonical
  status event log (`status.events.jsonl`/`status.json`) with the primary checkout's
  stale copies, preserving seeded lane state on coordination-topology missions (#1589).
- Reconciled the genesis gate and `spec_kitty_events` 6.0.0 expectations for CI.

## [3.2.0rc39] - 2026-06-07

### ✨ Added

- Added `session_presence` package with `SessionPresenceManager`, `InstallResult`,
  `ClaudeCodeWriter`, `MarkdownRulesWriter`, `ClaudeCodeHookRegistrar`, `UpgradeChecker`,
  `SessionPresenceContent`, and supporting writer/hook infrastructure.
- Added `spec-kitty session-start` CLI command (invoked by the Claude Code `SessionStart`
  hook) that emits an orientation block to stdout when run inside a spec-kitty project.
  The command always exits 0 and never blocks a Claude Code session start.
- `spec-kitty init` now calls `SessionPresenceManager.install()` after saving agent
  configuration, writing the orientation block and registering the `SessionStart` hook for
  Claude Code projects automatically.
- Added Phase 1 upgrade migration (`3_3_0_session_presence_claude_code`) that detects
  existing Claude Code projects missing the orientation section or `SessionStart` hook and
  backfills both artefacts on `spec-kitty upgrade`.

### 🐛 Fixed

- Work packages can now declare `scope: codebase-wide` so cross-cutting/refactor
  WPs are exempt from `owned_files` overlap validation, end-to-end through
  `finalize-tasks` (#1753). Two coupled defects were fixed: (1) the strict
  (`extra="forbid"`) `WPMetadata` parser rejected the `scope` key at parse time,
  and (2) `OwnershipManifest.from_frontmatter` hard-coded `scope = None` on its
  `WPMetadata` branch - the exact path `finalize-tasks` uses - silently dropping
  the exemption even when the key parsed. The adapter now propagates `scope`, and
  acceptance tests assert that narrow WPs claiming the same files still fail
  regardless of lane/dependency structure, while a codebase-wide WP is exempt.
  Also removed redundant `@overload` stubs on `from_frontmatter` that tripped
  strict mypy (`overload-cannot-match`).

### 📝 Docs

- AGENTS.md: added "Use Canonical Sources, Never Improvise" guidance and a
  ruff/mypy-clean (no disabled checks) code-style rule.
- `tasks-finalize` doctrine prompt: documented ownership-overlap handling for
  domain/refactor missions (linearize shared surfaces; declare codebase-wide).

## [3.2.0rc38] - 2026-06-06

### ✨ Added

- Added implementation concern Map terminology and work-package traceability
  across planning artifacts, generated task prompts, validation checks, docs,
  ADRs, glossary context, and agent snapshots.
- Added tracked Op record storage under `kitty-ops/`, including
  `ops-index.jsonl`, `lifecycle.jsonl`, propagation-error records, best-effort
  `op(...)` auto-commit support, and `spec-kitty doctor ops` orphan reporting.
- Added DocFX publishing polish, all-contributors normalization, and updated
  CLI/reference documentation for the 3.2 release candidate line.

### 🔧 Improved

- Moved Op record storage from its previous gitignored event directory to
  git-tracked `kitty-ops/`, including `ops-index.jsonl`, `lifecycle.jsonl`, and
  propagation errors. Pre-existing records in the retired location are
  abandoned and not migrated.
- Consolidated software-dev template source resolution and rejected stale
  template-root environment overrides so runtime fixtures and package defaults
  cannot silently diverge.
- Tightened release workflow ownership around downstream consumer validation,
  release metadata, path filters, and GitHub Pages publishing support.

### 🐛 Fixed

- **Merge done-marking surface divergence** (`merge.py`, `coordination/surface_resolver.py`):
  After `spec-kitty merge`, WPs that were `approved` would show as `Completed: 0 (80.0%)`
  instead of `Completed: 1 (100%)` when the mission carried a `coordination_branch` in
  `meta.json`. Root cause: `_mark_wp_merged_done` wrote done events to the coordination
  branch surface via `BookkeepingTransaction` (coord-branch-aware), while
  `_assert_merged_wps_reached_done` read back from the primary checkout via
  `resolve_feature_dir_for_mission` (topology-unaware). The two functions resolved to
  different filesytem paths - write never landed where read looked. Fix: introduced
  `coordination.surface_resolver.resolve_status_surface(repo_root, mission_slug)` as the
  single canonical surface resolver; `_assert_merged_wps_reached_done` now calls it instead
  of the topology-unaware resolver, eliminating the divergence. A full merge-path audit
  (inline comment in `merge.py`) confirms no other DIVERGENT sites. Parity ratchet added
  (four regression tests). Class recurrence of issue
  [#1589](https://github.com/Priivacy-ai/spec-kitty/issues/1589) facet 3.
  Closes [#1726](https://github.com/Priivacy-ai/spec-kitty/issues/1726).
  ([#1672](https://github.com/Priivacy-ai/spec-kitty/issues/1672) parity ratchet)

- Completed Op records are now best-effort auto-committed with `op(...)`
  commit messages, and `spec-kitty doctor ops` reports started-only orphan
  records.

- `spec-kitty merge` (without `--push`) no longer checks or requires origin
  sync before performing local lane integration. A local target branch that
  is ahead of, behind, or diverged from its remote tracking branch does not
  block a local-only merge. This resolves issue #1706 where users with
  accumulated orchestration commits on local `main` could not run
  `spec-kitty merge` until they pushed to origin first.

- Push-safety checks now fire only when `--push` is requested. The
  `"behind"` and `"diverged"` states block before local merge mutation with
  remediation guidance, while `"ahead"` remains push-safe.

- `MergeState` now persists `push_requested` for correct resume semantics:
  a resumed merge respects the original invocation's push intent without
  requiring re-specification of `--push`.
- `spec-kitty next` now preserves query startup latency behavior while runtime
  template-source cleanup is in effect.

## [3.2.0rc37] - 2026-06-04

### Added

- Added execution-state domain remediation artifacts, ADRs, and glossary
  context covering ExecutionContext ownership, command targets, effector
  actors, mission/MissionRun boundaries, and status aggregate behavior.
- Added architectural ratchets for execution-context parity, status module
  boundaries, and raw `kitty-specs/<mission>` path construction.

### Changed

- Routed command and runtime path handling through shared execution-context and
  feature-directory resolution so raw mission spec paths consistently resolve
  through the active action context.
- Refreshed Contextive execution glossary and doctrine skill metadata while
  removing the retired `spk-integrate-ci` skill from the bundled doctrine pack.
- Hardened release-candidate CI ownership and release workflow checks around
  path filters, candidate metadata, and downstream compatibility validation.

### Fixed

- Fixed 3.1.10 acceptance and move-task regressions across transactional
  coordination, protected branch bypass handling, and clean-tree acceptance
  fixtures.
- Suppressed SaaS ingress warnings when SaaS sync is disabled.
- Addressed low-risk Sonar cleanup findings and mission-review follow-up
  issues from execution-state domain remediation.

## [3.2.0rc36] - 2026-06-03

### Changed

- Polished 3.2 CLI UX around init next steps, scaffold state, widen guidance,
  and charter preflight output.
- Updated agent harness installation guidance and snapshots for Codex, Kiro,
  Antigravity, and public harness docs.
- Added execution-state/runtime architecture notes covering mission vs.
  MissionRun boundaries and context decomposition.
- Hardened release-candidate CI around charter checks, workflow status
  coordination, and Next runtime task parsing.

## [3.2.0rc35] - 2026-06-02

### Added

- Added agent upgrade prompts and slash-command repair diagnostics so project
  upgrades can detect and repair stale agent command surfaces.
- Added doctrine/profile activation closure work, including canonical kind
  resolution, DRG-backed profile lineage, layered charter listing, template
  discovery, and single-source doctrine health reporting.

### Changed

- Reworked parent-mission acceptance docs and charter boundary documentation
  around status-commit terminology and profile integrity closeout.
- Tightened coordination topology handling across runtime prompts, decision
  logs, dependency gates, move-task transitions, and orchestrator API paths.

### Fixed

- Fixed slash-command install and audit gaps that left generated command files
  stale after upgrades.
- Fixed coordination-topology edge cases that could read stale checkout state,
  miss decision logs, or proceed across topology gaps without failing closed.
- Fixed charter activation and closeout CI instability, including layer-aware
  activation and clean-install latency recalibration.

## [3.2.0rc34] - 2026-06-02

### Changed

- Clarified that live canary and cross-repo end-to-end runs remain required
  release-candidate hygiene under the charter, but are run locally before
  tagging instead of as tag-time PyPI publish workflow blockers.
- Transactional mission status reads now resolve the coordination worktree
  without creating or mutating checkout state, keeping lane views aligned with
  the coordination branch.

### Fixed

- Planning-artifact commits now preserve append-only coordination event logs
  instead of clobbering lane history with stale primary-checkout copies.
- Planning-artifact claim commits now parse git porcelain status structurally,
  fail closed on unrelated structural changes, and skip idempotent
  already-on-coordination content.
- Move-task transitions now derive source and target lanes from transactional
  coordination status so review handoffs do not fail after coordination/feature
  branch desync.
- `.kittify/sync-state.json` is treated as local relay state, while charter
  synthesis provenance can be tracked with the required commit reminder.

## [3.2.0rc33] - 2026-06-01

### Changed

- Tag-time PyPI publishing now stays focused on release-local checks. Live
  canary evidence and the cross-repo end-to-end consumer scenario are no longer
  blocking jobs in `.github/workflows/release.yml`; they remain required local
  release-candidate hygiene before tagging.
- Release metadata now aligns `.kittify/metadata.yaml` with `pyproject.toml`
  for `3.2.0rc33`.

## [3.2.0rc32] - 2026-06-01

### Added

- Charter governance references: `governance_references` declarations in `charter.md`
  now surface supporting public governance docs in `charter context` text/JSON and
  `charter status` diagnostics, with repo-root-scoped path safety.
- Release authority now has a machine-readable shared-package compatibility
  manifest, plus gates that validate CLI ranges, `uv.lock`, SaaS consumer
  contracts, and exact PyPI installability for published artifacts.

### Changed

- Release metadata now aligns `.kittify/metadata.yaml` with `pyproject.toml`
  for `3.2.0rc32`.
- Glossary runtime modules are packaged under canonical top-level `glossary`
  while `specify_cli.glossary` remains a registered compatibility shim.

### Fixed

- `spec-kitty agent decision open --json` now emits exactly one parseable JSON
  object on stdout. The response includes a retry-safe idempotency key so callers
  can rerun the same logical open by mission slug and recover the same
  `decision_id` after wrapper parse/process failures. Idempotent retries repair
  a missing opened event when local decision files were persisted before event
  emission failed, and dry-run output no longer advertises persisted recovery.
- `charter generate --force` now refuses to overwrite symlinked `charter.md` paths,
  preventing silent writes through symlink targets.
- Sync WebSocket connections now send ephemeral `ws_token` credentials in the
  `Authorization: Bearer` upgrade header instead of an ignored `?token=` query
  parameter, restoring authenticated live event delivery.
- Prerelease PyPI publishing no longer waives downstream consumer evidence; the
  release workflow now requires the private consumer suite before any PyPI
  promotion.
- A circular work-package dependency in `tasks.md` no longer leaves the canonical
  status uninitialized with a misleading, looping error (#1589). `finalize-tasks`
  aborts on the cycle before bootstrapping status; `spec-kitty next`/`move-task`
  and lane reads now name the dependency cycle as the root cause instead of an
  infinite "run finalize-tasks to bootstrap the event log" hint.
- `spec-kitty agent status doctor` no longer reports a mission as "Healthy" when
  it has work-package definitions but no canonical status (e.g. after a
  cycle-aborted `finalize-tasks`); it now emits an `uninitialized_status` warning
  naming the cycle when present (#1589).
- CI: the shared-package drift check now skips gracefully when
  `SPEC_KITTY_SAAS_READ_TOKEN` is unavailable (fork PRs) instead of hard-failing;
  the cross-repo drift is still enforced by the push-to-main CI that holds the
  secret.

### Documentation

- Clarified that `.kittify/charter/charter.md` is the Spec Kitty runtime governance
  center, while public docs such as `spec/constitution.md` are supporting context
  rather than alternate authoritative charter paths.
- Added migration guidance for constitution-era `.kittify/memory/constitution.md`
  and `.kittify/constitution/*` layouts.

## [3.2.0rc31] (rolled into rc32)

### Fixed

- Legacy `specify_cli.charter_lint.checks.*` shim imports now preserve canonical
  `specify_cli.charter_runtime.lint.checks.*` module identity and fail loudly if a
  nested alias is missing, preventing duplicate checker module instances.

## [3.2.0rc30] - 2026-05-29

### Added

- **ADR 2026-05-28-1**: Documents CI dependency resolution and test surface consistency —
  five structural gaps identified from CI run 26558837157, chosen remediations, and
  confirmation criteria.
  (`architecture/adrs/2026-05-28-1-ci-dependency-resolution-and-test-surface-consistency.md`)
- Typer-surface smoke test (`tests/agent/test_json_group_typer_surface.py`) that exercises
  the `_JSONErrorGroup` / JSON-envelope contract end-to-end using `typer.Exit` (not
  `click.exceptions.Exit`). Acts as a canary for the typer 0.26+ vendored-click regression.
- `agent` pytest marker for orchestrator-api / agent-facing contract surface tests.

### Changed

- **CI: all test and lint jobs now use `uv sync --frozen --all-extras`** instead of
  `pip install -e .[test]`. The lockfile is the single environment contract for both
  local and CI, eliminating resolver drift between `uv.lock` and `pyproject.toml` bounds.
  Three infrastructure jobs (`uv-lock-check`, `build-wheel`, `clean-install-verification`)
  are unaffected.
- Python version pinned to `3.11.15` in `.python-version` for reproducibility.

### Fixed

- `_JSONErrorGroup` exception handlers now use `_CLICK_USAGE_ERRORS` / `_CLICK_ABORTS`
  tuples that include both `click.exceptions.*` and `typer._click.exceptions.*` variants,
  fixing silent miss of all exceptions raised by typer 0.26+ which vendors click
  internally as `typer._click`.
- Charter-preflight test fixtures (`tests/specify_cli/charter_preflight/_fixtures.py`)
  now use `charter.hasher.hash_content()` instead of raw `hashlib.sha256(bytes)`,
  aligning with the production algorithm and eliminating hash-format divergence.
- E2e conftest synthesises `.kittify/charter/metadata.yaml` after `copytree` using
  the production `charter.hasher.hash_content()` helper, making fixtures self-contained
  and reproducible on clean clones without gitignored runtime state.
- Missing `import click` in `orchestrator_api/commands.py` that caused `NameError` in the
  `except ImportError` fallback when importing the module on typer < 0.26.
- Restored `doctrine` CLI group registration (incorrectly removed when a stale regression
  test was treated as a contract); narrowed the curation-excision guard to `curate`/`promote`
  only; restored `spec-kitty doctrine` sections in `docs/reference/cli-commands.md`.

### Security / Lint

- `TID251` (`flake8-tidy-imports` banned-api) added to ruff: `hashlib.sha256` usage in
  `tests/` must go through `charter.hasher.hash_content()`; `click.exceptions.Exit`,
  `UsageError`, and `Abort` in tests must use `typer.*` equivalents instead.
- `TID251` is now **enforced**, not advisory: a dedicated `[ENFORCED] banned-API lint
  gate (TID251)` step in `ci-quality.yml` runs `ruff check src tests --select TID251`
  without `continue-on-error`, so an unannotated banned call fails the build. The
  previous whole-directory `per-file-ignores` (which silently exempted 10 test trees and
  defeated the "new sha256 still needs a `# noqa`" policy) were removed; every legitimate
  raw `hashlib.sha256` now carries an inline `# noqa: TID251 - <justification>`. A guard
  test (`tests/architectural/test_tid251_enforcement.py`) pins the enforcement so it
  cannot silently regress to advisory. (Closes the adversarial review block on #1395.)

## [3.2.0rc29] - 2026-05-29

3.2.0rc29 rerolls the coordination branch atomic event-log candidate after
PR review and publishes the launch-readiness hardening merged after the yanked
3.2.0rc28 candidate.

### Added

- Added mission coordination branches, sparse coordination worktrees,
  `BookkeepingTransaction`, and `WorkflowMutationPolicy` so mission status
  mutations are staged, audited, and committed away from protected target
  branches.
- Added regression, integration, stress, and architectural coverage for
  coordination worktree creation, safe-commit branch assertions, legacy mission
  fallback, workflow rollback, post-merge indexing, and concurrent status
  emission.
- Added `mission close --discard` and doctor diagnostics for coordination
  workspace health, restart-daemon timing, command/skill manifest drift, and
  upgrade remediation provenance.
- Added external-orchestrator install and compatibility documentation, including
  PyPI installation paths, orchestrator API JSON-error guidance, host-surface
  governance docs, and environment-variable references.

### Changed

- **BREAKING (CLI)**: `spec-kitty safe-commit` now requires
  `--to-branch <ref>`. The temporary `SPEC_KITTY_INFER_DESTINATION_REF=1`
  compatibility path lets the CLI resolve and pass the destination explicitly
  during rollout; the helper itself never infers it.
- **BREAKING (internal)**: `safe_commit()` now requires keyword-only
  `worktree_root`, `destination_ref`, and `paths`, and structurally verifies
  that the worktree HEAD matches the declared destination before staging.
- Removed Spec Kitty internal protected-branch commit exceptions for planning
  artifacts and merged-WP done records. Remaining exceptions are limited to
  documented non-Spec-Kitty upgrade/release workflows.
- Hardened release CI ownership by deduplicating release-readiness checks,
  adding installed-entrypoint smoke coverage, and preserving clean-install
  latency evidence.
- Documented the host-surface parity matrix and Mode of Work governance layer
  so standalone dispatch behavior has a visible README entry point.
- Clarified correlation link and projection policy / read-model policy coverage
  for the 3.2.0 trail-model tranche, including deferred Tier 2 items.

### Fixed

- Migrated remaining production `safe_commit()` call sites to the
  destination-ref-aware API so agent task, mission, merge, upgrade, and
  orchestrator paths no longer crash on the removed legacy signature.
- Fixed protected-branch leakage from `agent action implement` by routing
  planning artifacts and workflow status writes through coordination-owned
  commit paths instead of target-branch bypasses.
- Serialized first-time coordination worktree creation under the feature
  status lock to prevent concurrent emitters from racing on `git worktree add`.
- Fixed idempotent squash-merge retry behavior, finalize-tasks dependency
  source precedence, safe-commit recovery reporting, workflow path mirroring,
  configured command execution on Windows, charter JSON error envelopes, and
  command/skill manifest repair drift.
- Restored upgrade-readiness preference preservation and compatibility hints,
  including uv-tool pytest remediation provenance fallbacks.
- Restored compatibility for older unit-test fakes that do not expose the new
  coordination branch or commit-result fields.

### Deferred

- Continued tracking deferred follow-up work such as
  [#534](https://github.com/Priivacy-ai/spec-kitty/issues/534) outside the
  3.2.0 readiness tranche.

## [3.2.0rc28] - 2026-05-27

3.2.0rc28 fixes acceptance lane ownership and a clean-install dependency gap.

### Changed

- `accept` and orchestrator-api `accept-mission` now keep `approved` and
  `done` distinct: acceptance reports accepted-ready, approved,
  merge-pending, and already-merged WPs without closing approved WPs. Merge
  remains the owner of the `approved -> done` integration transition.
- Software-dev mission guards now treat `approved` and `done` as
  accepted-ready for mission advancement.

### Fixed

- Declared `click` as a direct runtime dependency because CLI modules import it
  directly. This fixes pipx/Windows clean-install import failures.

## [3.2.0rc27] - 2026-05-26

3.2.0rc27 fixes a charter freshness/preflight false positive found in the
post-rc26 mainline checks.

### Fixed

- Charter freshness now uses the same canonical hash semantics as
  `charter sync`, so whitespace-normalized stored hashes do not falsely mark a
  project stale.
- Fresh built-in doctrine seeds now produce the charter synthesis manifest
  expected by preflight, preventing new projects from failing with
  `charter_source stale` before any local charter exists.
- Synced charter bundles no longer become stale from source mtime drift when
  metadata hashes and required bundle files already prove the source is fresh.

## [3.2.0rc26] - 2026-05-26

Rolls up the charter preflight, built-in vocabulary, and CI stabilization
guardrails merged after rc25.

### Breaking changes

- **`shipped` → `built-in` vocabulary rename.** Public CLI JSON surfaces that
  previously emitted `"shipped"` as a doctrine layer label now emit `"built-in"`.
  This aligns user-facing terminology with the on-disk `built-in/` directory
  layout that already existed. Affected commands:
  - `spec-kitty charter status --json`
  - `spec-kitty charter lint --json`
  - `spec-kitty charter preflight --json` (new in this release)
  - `spec-kitty agent profile list --json`
  - `spec-kitty doctrine pack validate --json`

  External tooling that pattern-matched the string `"shipped"` MUST be updated.
  No deprecation period: the rename is mechanical and the architectural test
  `tests/architectural/test_no_shipped_layer_label.py` prevents regression.

  Related: ADR `architecture/3.x/adr/2026-05-24-3-shipped-to-built-in-cutover.md`.

### Changed

- **Deprecated paths:** `specify_cli.charter_lint`, `specify_cli.charter_freshness`,
  and `specify_cli.charter_preflight` now re-export from
  `specify_cli.charter_runtime.{lint,freshness,preflight}` under a shared
  charter-runtime umbrella (LD-5 / FR-014). The old paths emit no
  `DeprecationWarning` yet; they will in the next minor release. External
  importers should update to the new paths during this deprecation window
  (spec C-008). The `charter_runtime.facade` slot is reserved for a future
  charter-facade consolidation.

### Added

- **`spec-kitty charter preflight` command.** Caller-facing preflight contract
  for governance freshness (FR-006, FR-007, FR-008). Returns a structured JSON
  report that `next`, `implement`, and the dashboard consume to decide whether
  to proceed, prompt for `charter synthesize`, or block. See
  `docs/reference/charter-commands.md` and ADR
  `architecture/3.x/adr/2026-05-24-1-charter-freshness-ux-contract.md`.

- Pre-launch and launch-readiness operator docs for hosted SaaS
  sync (#1095). Public docs remain local-first; hosted readiness
  stays opt-in via `SPEC_KITTY_ENABLE_SAAS_SYNC=1`. The new
  `docs/how-to/internal-hosted-readiness.md` covers the dogfooding
  workflow for internal / pre-launch operators, and the new
  `docs/explanation/launch-readiness-future.md` stages the launch-day
  behavior shift behind an explicit "Status: pre-launch" banner.

## [3.2.0rc25] - 2026-05-23

Rolls up the post-rc24 static-analysis and upgrade UX type-boundary fixes.

- Tightens acceptance package imports, compatibility cache typing, and
  readiness upgrade UX helper boundaries after the overnight Sonar sweep.
- Keeps the 3.2.0 stable release candidate line current with `main`
  after `#1293`.

## [3.2.0rc24] - 2026-05-22

Ships the canonical SaaS-bound producer refactor for CLI lifecycle,
sync, decision, glossary, and migration emitters.

- Routes known SaaS-bound CLI payloads through the `spec-kitty-events`
  5.2 canonical models where those contracts exist, while preserving
  transitional legacy wire payloads required by current SaaS consumers.
- Preserves local `artifact_path` metadata on artifact-phase Started
  events and projects those payloads to the strict canonical SaaS wire
  shape before queueing.
- Adds producer conformance coverage, strict lifecycle validation,
  handler-reset isolation, and a documented canonical-producer lint
  baseline for remaining local-only/test producers.

## [3.2.0rc23] - 2026-05-21

Rolls up the autonomous-runtime safety sweep needed before the 3.2.0
stable cut, plus the documentation and CI guardrails merged after rc22.
The candidate focuses on removing operator-required workarounds from
fully autonomous local missions.

- Closes `#1255`: retrospective files written by `retrospect create`
  are now accepted by `retrospect synthesize`, with regression coverage
  for both dry-run and apply flows.
- Closes `#1256`: decisions deferred during planning can be resolved
  cleanly at terminus, and `decision verify` no longer reports resolved
  clarification markers as drift.
- Closes `#1235` and `#1257`: task finalization rejects
  `kitty-specs/` paths in WP `owned_files` with a clear WP/path error,
  while bulk-edit preflight treats WPs that author planning artifacts
  such as `occurrence_map.yaml` as informational.
- Closes `#1236`: lane computation now preserves parallel lanes for
  upstream WPs with disjoint `owned_files`; fan-in WPs remain the
  synchronization point.
- Closes `#1258`: autonomous local mission docs now include the
  focused-PR fallback for `TARGET_BRANCH_NOT_SYNCHRONIZED` when local
  `main` contains orchestration commits.
- Adds the 3.2 documentation refresh, harness/install lifecycle pages,
  docs freshness checks, drift-detector CI, canonical-producer linting,
  acceptance-matrix extension preservation, and charter-context envelope
  repair merged after rc22.

## [3.2.0rc22] - 2026-05-21

Ships the `sync diagnose` canonical-allowlist fix so canary diagnostic
output stops flagging known event types (`TasksCompleted`,
`PlanCompleted`, `GatePassed`, etc.) as unknown. The `sync diagnose`
allowlist is replaced with delegation to
`spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL` - the
canonical registry shared with the SaaS strict validator. A
drift-detector regression test asserts the union remains in sync, so
future events releases self-validate. The CLI's outbound emission
gate (`emitter.VALID_EVENT_TYPES`) is intentionally untouched.

- Fixes `spec-kitty sync diagnose` false-positive "unknown event"
  warnings by sourcing recognised types from the canonical events
  registry (`Priivacy-ai/spec-kitty#1222`).
- Adds a drift-detector regression test that fails when the events
  package adds or removes an event type without the registry being
  re-imported.

## [3.2.0rc21] - 2026-05-20

Rolls up the minor issue-queue cleanup selected before the 3.2.0
stable release, plus the post-merge test hardening needed to keep
`main` green after those fixes landed.

- Fixes tasking help assertions to validate Typer option metadata
  instead of Rich-rendered, platform-truncated help text, restoring
  the full main test sweep after the task command cleanup.
- Refreshes the rc20 lockfile metadata so branch and release
  validation agree on the packaged dependency graph.
- Improves task finalization and review-state behavior: rejected
  review overrides are described with the canonical tasking language,
  finalize-tasks dependency prose no longer produces false positives,
  and the main test sweep covers those edge cases.
- Tightens CI and repository hygiene by requiring PR suffixes in the
  protect-main check and tracking research evidence logs.
- Hardens sync, acceptance, retrospective, and dashboard edges found
  during the pre-3.2.0 issue sweep: doctor daemon health checks are
  isolated, acceptance clarification markers match the canonical
  contract, retrospective event emission is materialized, and the
  dashboard exposes the glossary shell.

## [3.2.0rc20] - 2026-05-20

Closes the next dormant mask from epic `#1198`, surfaced by the
rc19 canary now that the `#1202` observability fix is in place.

- Closes `#1203` mask 1: `EventEmitter.emit_wp_created` in
  `src/specify_cli/sync/emitter.py` now constructs the payload
  matching the canonical events 5.1.0 `wp_created_payload` schema.
  Four simultaneous violations are closed in a single change:
  `title` renamed to `wp_title` at the payload boundary,
  `dependencies` renamed to `depends_on`, required `actor`
  parameter added (default `"cli"`) and placed in the payload,
  and `mission_id` removed from the payload (the parameter is
  still accepted for backward compatibility but is no longer
  written to the wire - it isn't in the schema's allowed set).
  The local emitter's per-event-type validator table is updated
  to match the canonical required-fields contract; the
  singleton-level `emit_wp_created` mirror in
  `src/specify_cli/sync/events.py` gains an `actor` parameter and
  passes it through; and the production caller in
  `src/specify_cli/cli/commands/agent/mission.py:2448` passes
  `actor="spec-kitty agent mission finalize-tasks"`.

This was the four-violation drift P4 predicted in the differential
matrix and that the rc19 canary surfaced in full detail thanks to
the per-event-violation observability restored in `#1202`. The
structural follow-up `#1200` (construct payloads via pydantic
models across every `emit_*` site) still pending; this surgical
close prevents the immediate canary blocker while that work
proceeds.

## [3.2.0rc19] - 2026-05-20

Ships the combined `#1199` + `#1202` surgical fix from epic `#1198`:
the immediate Phase 4 canary blocker plus the observability fix that
restores the SaaS's per-event violation diversity to operators.

- Closes `#1199`: `emit_mission_created_local` in
  `src/specify_cli/status/lifecycle_events.py` now accepts
  `mission_type` (required) and `wp_count` (default 0) and places
  both in the payload. The canonical events 5.1.0 schema for
  `mission_created_payload` lists both as required; the deployed
  SaaS jsonschema gate rejects payloads without them with
  `'mission_type' is a required property`. The sibling call site in
  `src/specify_cli/core/mission_creation.py:412` now passes both
  fields, matching the sync-events path at `:468-470`.
- `_validate_lifecycle_payload` widened from `extra_forbidden`-only
  to fail on ALL model violations (extras + missing-required +
  every other `violation_type`). The historical comment block that
  rationalised the narrow scope as matching SaaS tolerance was
  based on the SaaS-side `_should_validate_strict_envelope` hole
  (`Priivacy-ai/spec-kitty-saas#217`) and is no longer true. The
  widened validator catches MissionCreated, WPStatusChanged,
  MissionDossierArtifactIndexed, and every other event type the
  events package recognises, preventing the next analogous drift
  from reaching the offline queue.
- Closes `#1202`: `_parse_error_response` in
  `src/specify_cli/sync/batch.py` now reads `details[*].detail`
  (the key the SaaS actually ships) before falling back to
  `.error` / `.reason`. Without this fix, every per-event line
  in a SaaS rejection collapsed to the outer `error_msg` —
  hiding the SaaS's full per-event violation diversity for the
  entire `rc12 → rc18` drift-chain investigation. With the fix,
  the next failed batch surfaces every distinct violation per
  event, dramatically compressing any remaining mask-peeling.

Sequenced first per epic `#1198`. The structural follow-up
`#1200` (pydantic-construct payloads across all `emit_*` sites +
CI conformance gate) and `#1203` (dormant masks sweep) are next,
with `spec-kitty-saas#217` (close the strict-envelope hole)
sequenced after.

## [3.2.0rc18] - 2026-05-20

Ships the final observed Phase 4 launch-gate payload drift fix after the
rc17 `WPStatusChanged` envelope cleanup.

- Closes `#1190` via `#1191`: `emit_mission_created_local` no longer writes
  `actor` into the `MissionCreated` payload. The canonical
  `spec-kitty-events` 5.1.0 schema declares `additionalProperties: false` for
  `mission_created_payload` and does not allow `actor`, so deployed SaaS batch
  ingest rejected every batch containing one of these events.
- Refactors `_validate_lifecycle_payload` to delegate to
  `spec_kitty_events.conformance.validate_event`, replacing the previous
  hand-maintained lifecycle payload map that missed `MissionCreated` and other
  known event types. The local guard now catches extra-property drift before
  queue fan-out while still tolerating currently accepted missing-field
  violations.
- Adds regression coverage for the cleaned `MissionCreated` payload, the
  conformance guard's extra-field rejection, valid-payload pass-through, and
  graceful fallback for event types not recognised by the installed events
  package.

## [3.2.0rc17] - 2026-05-20

Ships the third Phase 4 launch-gate fix: the actual SaaS-side schema
violation that was hiding behind the parser and canary issues fixed in
rc16.

- Closes `#1188`: `emit_wp_status_changed` in
  `src/specify_cli/sync/emitter.py` no longer passes
  `envelope_fields=` to `_emit`. The payload-only keys (`from_lane`,
  `to_lane`, `actor`, `force`, `reason`, `review_ref`,
  `execution_mode`, `evidence`) were being duplicated at the envelope
  level alongside the canonical envelope keys, and the SaaS schema at
  `/api/v1/events/batch/` rejected every batch containing a
  `WPStatusChanged` event with
  `Additional properties are not allowed ('actor' was unexpected)`
  (HTTP 400). On rc16 this surfaced as scenarios 1, 2, and 4 of the
  deployed-dev identity-boundary canary failing with
  `Synced: 0 Duplicates: 0 Errors: N (unknown: N)`; scenario 3 passed
  because it never emits events through the batch endpoint.
- Extends `envelope.forbidden_fields` in
  `src/specify_cli/core/upstream_contract.json` to include the
  payload-only keys, so the existing
  `test_no_forbidden_fields_in_envelope` contract test now guards
  against regressions.
- Updates the unit tests in `tests/sync/test_events.py` that
  previously asserted the top-level duplicates; the new assertions
  pin the contract that those keys live in `payload` only.

The bug has been on `main` since commit `533e47d2` (2026-04-14,
"Harden SaaS auth and restore build sync emission"). It was masked on
earlier RCs by the audit-predicate gap fixed in rc15
(`#1142`), the parser misclassification fixed in rc16 (`#1182`), and
the canary-command shape fixed in
`spec-kitty-end-to-end-testing#45` (`#1141`). With those three out of
the way, the underlying envelope drift was finally visible end-to-end
and could be fixed.

## [3.2.0rc16] - 2026-05-20

Ships the Phase 4 canary launch-gate unblock: the actual root-cause fix for
`#1141` and the parser/classification fix for `#1182`.

- Closes `#1182`: `_parse_event_results` in `src/specify_cli/sync/batch.py`
  now routes per-event `status="queued"` / `status="pending"` responses to a
  new `pending_count` bucket on `BatchSyncResult` instead of folding them
  into the rejected catch-all with `category=unknown`. `sync now` previously
  reported durably-queued events as `Errors: N (unknown: N)` and exited
  non-zero when the in-process final-sync hit its 5s timeout; pending-only
  drains now exit 0 and surface as `Pending: N` in the summary. Queue
  mutation policy unchanged (pending rows are left for the next daemon tick,
  same disposition as `failed_transient`).
- Closes `#1141` (companion fix in `spec-kitty-end-to-end-testing#45`): the
  canary scenario 4 `move-task --to planned` invocation was omitting
  `--review-feedback-file`, so the CLI hard-rejected the command at the
  argument-validation layer before reaching `emit_status_transition`. The
  rc15 diagnostic breadcrumb in `fire_saas_fanout` could never fire because
  the codepath never reached fan-out. The e2e fix passes a structured
  feedback markdown so the backward emit actually lands. No CLI change is
  required; the events #32 force-required contract and the CLI's
  review-feedback hardening are both intentional and remain in force.
- New unit coverage in `tests/sync/test_batch_error_surfacing.py` pins the
  contract: per-event `queued` / `pending` are not errors, never count
  toward `success_count` (they are durable in-flight, not terminal), but
  do count toward sync activity so the "no progress" guard does not fire
  on a pending-only drain.

## [3.2.0rc15] - 2026-05-19

Ships the Phase 4 canary unblock work landed via PR `#1180`:

- Closes `#1142`: broadens `is_mission_lifecycle_row` in
  `src/specify_cli/audit/shape_registry.py` to accept all four canonical
  aggregate types (`Project`, `Mission`, `WorkPackage`, `MissionDossier`)
  rather than `Mission` alone. Fresh missions no longer trip the
  `FORBIDDEN_KEY` TeamSpace gate when `sync now` runs.
- Closes `#1141`: adds a diagnostic breadcrumb at `fire_saas_fanout` entry in
  `src/specify_cli/status/adapters.py` plus regression coverage that the
  backward `in_review → planned` rollback reaches fanout with the expected
  shape. **Note**: this is a diagnostic landing, not the full root-cause fix
  - the silent replacement that the canary scenario 4 peek catches likely
  lives downstream in `OfflineQueue.queue_event` and is expected to be
  chased on a follow-up RC if it reproduces.
- Bundles the +30 targeted audit / status-emit-sequence tests from `#1180`.

## [3.2.0rc14] - 2026-05-19

Ships the next 3.2 release candidate after the doctrine/charter and
sync-boundary follow-up window:

- Adds the three-layer doctrine and charter DRG work: org-pack loading across
  every configured pack, project/org/built-in precedence diagnostics,
  org-charter interview pre-fill, collision warnings, and the related
  workflow/governance payload hardening.
- Closes the org-pack and charter-scope safety follow-ups by blocking archive
  traversal, unsafe server-provided filenames, symlink/hardlink extraction, and
  scope roots that escape the repository.
- Documents recovery from partially installed command namespace packages for
  `spec-kitty-events`, including the concrete import error signature and
  reinstall path.
- Keeps local workflow test suites honest under the hosted sync preflight:
  e2e workflow tests now opt out of `SPEC_KITTY_ENABLE_SAAS_SYNC` the same way
  integration and tasks suites do, while sync/auth suites retain hosted-sync
  coverage.
- Restores strict mission-step-contract type checking by making ambiguous DRG
  URN matches explicitly typed.
- Carries review and release hygiene fixes for unsafe target-branch merge
  guidance, retrospective workflow wording, doctrine language-bias lint, fresh
  sync Sonar findings, and Windows/main CI health.
- Aligns the release checklist with the main-branch protection workflow:
  release PRs should be squash-merged so the resulting commit retains the PR
  marker that `Protect Main Branch` recognizes.

## [3.2.0rc13] - 2026-05-19

Ships a focused sync-boundary hotfix for pipx-style CLI installs:

- Fixes `#1120`: daemon owner records now canonicalize
  `executable_path` at the `DaemonOwnerRecord` boundary, and foreground
  sync identity uses the same canonicalization helper. Pipx-installed CLIs
  whose `sys.executable` flows through a symlink no longer report a spurious
  `daemon_executable_path` mismatch during `sync status --check` or
  sync-producing command preflight.
- Adds adversarial coverage for owner-record dataclass canonicalization,
  resolve-failure fallback behavior, and the asymmetric one-sided resolve
  failure class that could reintroduce false split-brain detection.

## [3.2.0rc12] - 2026-05-18

Ships the MVP CLI sync-boundary preflight surface required by the Teamspace
auth-boundary hardening launch gate:

- Includes `#1115`: `specify_cli.sync.owner` daemon owner record with
  mismatch / orphan detection, `specify_cli.sync.preflight` read-only
  auth/daemon/queue boundary preflight, and the new identity-boundary rows
  exposed by `sync status --check` / `sync doctor`.
- Closes `#1087` (sync status/doctor expose auth/queue/daemon split brain),
  `#1088` (sync daemon coherent machine-global owner), `#1089` (setup-plan
  evidence enqueued in one sync scope), and `#1090` (scoped queue migration
  does not strand authenticated work).
- Unblocks the deployed-dev sync identity-boundary canary
  (`spec-kitty-end-to-end-testing#42` / `#41`) by providing a packaged CLI
  whose `sync status --check` output is parseable by the canary harness.

## [3.2.0rc11] - 2026-05-17

Closes the planning#16 backward-transition follow-up across the CLI release
surface:

- `spec-kitty backwards --note ...` now preserves the canonical
  `backward rewind:` transition-reason prefix when callers supply a note,
  keeping emitted `WPStatusChanged` events accepted by the shared contract and
  SaaS ingestion.
- The resolved lockfile moves to `spec-kitty-events==5.1.0`, which ships the
  review-rejection replay conformance fixture used to verify forced backward
  transition handling.

## [3.2.0rc10] - 2026-05-17

Rolls forward `3.2.0rc9` (never tagged) and adds the Teamspace MVP
canonical-lifecycle / sync-daemon launch-gate followups:

- **#1067 follow-up.** `core/mission_creation.py:create_mission_core`
  now emits the canonical `SpecifyStarted` event immediately after
  `MissionCreated`, referencing the freshly scaffolded `spec.md`
  artifact path. Previously the constant was defined but never emitted,
  so the canonical lifecycle stream skipped straight from
  `MissionCreated` to `SpecifyCompleted` at setup-plan time - leaving
  TeamSpace replay and the local dashboard blind to in-progress
  specifying. Regression coverage in
  `tests/specify_cli/core/test_mission_creation_specify_started.py`.
- **#1071 follow-up.** `sync status --check` and `sync doctor` now
  surface the daemon PID/port and any orphan `run_sync_daemon`
  processes (via the existing `scan_sync_daemons` helper), so operators
  see cross-checkout daemon divergence without grepping `ps`.
  `_kill_and_cleanup` now waits for the killed PID to actually exit
  before clearing `DAEMON_STATE_FILE` - closing the AC bullet that
  required version-mismatch replacement not leave older daemons live.
  Module docstring updated to be honest about state-file-scoped
  singleton semantics. Regression coverage in
  `tests/cli/commands/test_sync_status_singleton_diagnostics.py` and
  `tests/sync/test_daemon_replace_on_version_mismatch.py`.

Everything previously slated for rc9 (below) is included in rc10.

## [3.2.0rc9] (rolled into rc10)

The `quality-devex-hardening-3-2-01KRJGKH` mission closes six epic-#822
tickets and lands the doctrine tactics, canonical-terminology glossary,
and code-patterns catalog that underpin the 3.2.0 stable release. Push-time
Sonar restoration (#825) is the only remaining operator-action gate.

### Added

- **Stale-lane auto-rebase with conflict classification** (#771). New
  `specify_cli.merge.conflict_classifier` rule pipeline (Validator-flavor;
  5 conflict shapes - pyproject deps union, `__init__.py` import-block
  union, urls.py URL list union, `uv.lock` regenerate, default manual)
  and `specify_cli.lanes.auto_rebase` orchestrator. `spec-kitty merge`
  now attempts `git merge <mission-branch>` inside a stale lane worktree
  before halting, auto-resolves additive-only conflicts via a union-merge
  driver, regenerates `uv.lock` under a global file lock, runs
  `ruff --fix --select I001` on touched `__init__.py` files, and reports
  auto-resolved vs manual lanes. Semantic conflicts still halt with the
  current actionable error. ADR
  `architecture/2.x/adr/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md`
  documents the fail-safe-default policy.
- **No-upgrade UX notification** (#740). New `core/upgrade_probe.py`
  (PyPI probe + 2 s timeout-bounded channel classification:
  ALREADY_CURRENT / AHEAD_OF_PYPI / NO_UPGRADE_PATH / UNKNOWN) and
  `core/upgrade_notifier.py` (cache-aware emitter). Distinguishes
  "already on the latest supported version" from "build/channel with no
  upgrade path"; never blocks the CLI on network failure; rate-limited
  to once per 24 h with `SPEC_KITTY_NO_UPGRADE_CHECK=1` opt-out; reuses
  `should_check_version()` rather than introducing a parallel gate.
  Cache-warm budget < 100 ms.
- **`secure-regex-catastrophic-backtracking` doctrine tactic** codifying
  the four dangerous regex shapes, the rewrite ladder, and the escape
  hatches. Every regex change now requires a wall-clock regression test
  asserting linear runtime on adversarial input (default budget: < 100 ms
  for 100 000 chars) per FR-008.
- **`chain-of-responsibility-rule-pipeline` doctrine tactic** with three
  flavors (Validator / Transformer / Scorer) and the typed
  `CanonicalRule` Protocol at
  `src/specify_cli/migration/canonicalization.py` as the canonical
  Transformer-flavor implementation.
- **Core code-patterns catalog** at
  `architecture/2.x/04_implementation_mapping/code-patterns.md` listing
  the recurring shapes used across the codebase (Rule-Based Pipeline,
  Append-Only Event Log + Reducer, etc.) with doctrine cross-references.
- **Canonical-terminology glossary entries** for `characterization test`,
  `pipeline-shape`, `rule pipeline`, `catastrophic backtracking`,
  `structural debt`, `deliberate linearity`, and `sonar quality gate`
  in `.kittify/glossaries/spec_kitty_core.yaml`, each cross-referencing
  the doctrine tactic or architectural document that codifies it
  (FR-013).
- **Targeted symlink-fallback test** for the
  `m_0_8_0_worktree_agents_symlink` migration's `OSError -> shutil.copy2`
  fallback (#629). Runs on every CI pass via `monkeypatch`, not gated
  by `windows_ci`. Covers both happy-fallback and dual-failure arms.
- **Behavior-driven coverage tests** for `cli/commands/charter.py`,
  `cli/commands/charter_bundle.py`, `cli/commands/agent/config.py`,
  `next/_internal_runtime/engine.py`, and `core/file_lock.py`
  (Bucket A/B/C split; `CliRunner` + `tmp_path` real I/O; no
  `mock.patch` on Path methods) per the `function-over-form-testing`
  tactic (#595 workstream A).
- **Wall-clock regression guard** at
  `tests/regressions/test_changelog_regex_redos.py` (20 tests; < 100 ms
  on 100 000-line adversarial input) against future re-introduction of
  the three Sonar-flagged patterns in `release/changelog.py` (pre-fixed
  in PR #592) (#595 workstream B / FR-008).
- **`dev` dependency-group type stubs** (`types-jsonschema`,
  `types-psutil`, `types-PyYAML`, `types-requests`, `types-toml`) in
  `[dependency-groups] dev` so `uv run --with mypy mypy --strict`
  resolves stubs from the default env.

### Changed

- **mypy strict baseline** is now green for `src/specify_cli`,
  `src/charter`, `src/doctrine` per decision moment
  `DM-01KRJHT7QD7XQMY33Y5TDTQ80V` (option A - fix the existing target;
  #971). Includes `doctor.py::_print_overdue_details` annotation fix
  (typed `ShimRegistryReport` under `TYPE_CHECKING`) and
  `_resolve_fail_on` return-type tightening to
  `tuple[Severity | None, bool]`.
- **`_canonicalize_status_row` and `rebuild_state.py`** refactored onto
  the typed `CanonicalRule` Protocol with characterization-test coverage
  preceding the refactor commits (NFR-003 / `tdd-red-green-refactor`).
- **`doctor.py::mission_state`** refactored from cognitive complexity 57
  to a CC 3 thin orchestrator plus per-mode runners
  (`_validate_modes`, `_resolve_fail_on`, `_resolve_audit_root`,
  `_emit_mission_state`, `_run_audit_mode`, `_run_mission_repair`,
  `_run_teamspace_dry_run_mode`), with 17 characterization tests
  guarding behavior across all three dispatch arms (`--audit`, `--fix`,
  `--teamspace-dry-run`) (#595 workstream C).
- **`review.py` split into `cli/commands/review/` package** with sibling
  files for cleaner ownership boundaries.

### Fixed

- **`doctor.py:1092` `MissionRepairResult.findings` real-branch bug**:
  `report` variable was dual-typed as `RepairReport` /
  `RepoAuditReport` across mutually exclusive branches; runtime correct
  but typing broken. Now closes mypy strict on `doctor.py`.
- **Pre-existing YAML scanner error** in
  `.kittify/glossaries/spec_kitty_core.yaml` line 484: the `unsafe bypass`
  definition contained an unquoted backtick-wrapped `bypass_used: true`
  literal that `yaml.safe_load` interpreted as a nested mapping. The
  definition value is now double-quoted; semantic content unchanged.
  File now parses cleanly under `yaml.safe_load` and `ruamel.yaml`.

### Documentation

- **Mission-review report** at
  `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/mission-review.md`
  citing every doctrine tactic applied per WP and linking the
  code-patterns catalog (NFR-006 / FR-012).
- **Post-merge audit report** at
  `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/post-merge-review.md` —
  independent adversarial review confirming PASS WITH NOTES (no code
  defects; release-readiness gated on three operator-action items:
  Sonar hotspot rationale application, NFR-001 smoke execution, and the
  push-time Sonar workflow flip). Documents FR coverage matrix, drift
  findings, silent-failure scan, and security notes. All four
  post-merge stale-assertion findings classified as false alarms.
- **NFR-001 release-stability smoke recipe** at
  `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/nfr-001-smoke-recipe.md`
  for operator execution post-merge.
- **SonarCloud hotspot rationales** at
  `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/sonar-hotspot-rationales.md`
  documenting the 4 encrypt-data hotspots for operator application in the
  Sonar UI before push-time CI restoration (#825).
- **ADR `2026-05-14-1-stale-lane-auto-rebase-classifier-policy`** for #771.

### Deferred

- **Push-time SonarCloud restoration** (#825 / FR-004): gated on the
  operator applying the four hotspot rationales in the Sonar UI and the
  sonar quality gate flipping to `OK` (at audit time: ERROR —
  `new_coverage` 58.9% vs threshold 80%; `new_security_hotspots_reviewed`
  0% vs threshold 100%). The
  `.github/workflows/ci-quality.yml::sonarcloud` conditional remains on
  `schedule || workflow_dispatch` until gate is OK. See
  `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/sonar-pre-flip-verification.txt`.

### Removed

## [3.2.0rc8] - 2026-05-14

3.2.0rc8 rolls up the post-rc7 TeamSpace launch fixes and compatibility
cleanup needed before the final 3.2.0 cut. It includes defensive sync batching
for real edge-proxy limits, the Mission Dossier event-envelope migration for
`spec-kitty-events>=5.0.0`, and the small compatibility/quality fixes that
landed after rc7.

### Changed

- Reduced the CLI's default sync batch decompressed byte budget to 256 KiB and
  added a 512 KiB hard ceiling for over-generous server-advertised limits, so
  large TeamSpace queue drains split into safe requests instead of relying on
  HTTP 413 retry shrinkage.
- Migrated all four Mission Dossier event emitters to the namespaced envelope
  required by `spec-kitty-events>=5.0.0`, including `namespace`,
  `artifact_id`/`expected_identity`, content refs, and schema-compatible
  diagnostics.
- Preserved legacy queued Mission Dossier events by migrating flat queued
  payloads on drain when namespace data is available, and kept queue coalescing
  scoped correctly across both legacy and namespaced payload shapes.

### Fixed

- Restored agent profile list compatibility after the rc7 candidate.
- Reduced SonarCloud noise in path helper and charter synthesizer code without
  changing runtime behavior.
- Fixed the deployed-dev TeamSpace sync canary failure where a 1200-event
  backlog could cascade into 1000 HTTP 413 failures.
- Fixed SaaS ingestion rejection of CLI-emitted Mission Dossier artifact events
  caused by the old flat payload shape being rejected with
  `Additional properties are not allowed`.

## [3.2.0rc7] - 2026-05-12

3.2.0rc7 lands the `review-merge-gate-hardening-3-2-x-01KRC57C` mission
covering the remaining 3.2.x P1 release blockers plus a narrowed slice of the
charter encoding chokepoint, with post-merge remediation, SonarCloud
new-code gate cleanup, and CI portability fixes folded in.

### Added

- New canonical `KittyInternalConsistencyError` base under
  `src/kernel/errors.py`, with `CharterEncodingError` now inheriting from it
  so any UI/CLI/TUI surface can render structured remediation uniformly.
- Reusable SonarCloud branch-review snippet at
  `work/snippets/sonarcloud_branch_review.sh` (qualitygates/project_status +
  measures/component_tree + issues/search via REST API).
- Architectural decision record
  `architecture/adrs/2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md`
  deferring still-open `#391` sub-tickets (`#612` / `#613` / `#614`) from
  3.2.x scope, on top of the shared-package-boundary cutover precedent.

### Changed

- Refactored `_bake_mission_number_into_mission_branch` in
  `src/specify_cli/cli/commands/merge.py` from cognitive complexity 22 down
  to a flat coordinator backed by six named predicate / effect helpers, with
  no behavior change.
- Narrowed broad `except` clauses in `src/charter/_io.py`,
  `src/charter/compiler.py`, and `src/charter/interview.py` so charter
  encoding errors propagate to the canonical handler instead of being
  swallowed.
- Wired `assert_pytest_available()` into the production review preflight in
  `src/specify_cli/cli/commands/review/__init__.py`.

### Fixed

- Pre-merge mission-review remediation of findings `D1`, `D2`, `D3`, `S1`,
  and `S2` against the canonical issue matrix at
  `kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/issue-matrix.md`.
- Repaired 18 pre-existing test failures by extracting a shared
  `setup_mocked_env()` context manager to `tests/mocked_env.py` and rewiring
  the affected sites onto it.
- CI portability: `tests/integration/test_pytest_venv_concurrency.py` now
  invokes pytest through `sys.executable` instead of relying on a bare `uv`
  on `$PATH`, which is not guaranteed inside slow-test CI shards.
- Cleared the SonarCloud new-code coverage gate for the branch by adding 26
  focused coverage tests under `tests/kernel/`, `tests/charter/`, and
  `tests/core/test_paths_coverage_supplements.py`.
- Repaired dead links to the deleted `kitty-specs/_drafts/` directory in the
  3.2.x deferral ADR and the mission spec after the pre-PR cleanup pass.

## [3.2.0rc6] - 2026-05-11

3.2.0rc6 includes the post-rc5 TeamSpace migration enforcement and dry-run
compatibility fixes needed before publishing the next TeamSpace-ready CLI
candidate.

### Changed

- Surface pending TeamSpace mission-state migration during `spec-kitty upgrade`
  and require a clean migration before hosted TeamSpace connection flows.
- Allow the release compatibility gate to prove SaaS-supported dependency
  versions when the candidate CLI declares a compatible range instead of an
  exact pin.

### Fixed

- Render user-friendly TeamSpace migration gate failures when mission-state
  repair raises unexpected payload or filesystem errors.
- Preserve SaaS-disabled sync opt-in behavior while still enforcing
  mission-state readiness for hosted sync paths.
- Synthesize historical approval evidence during TeamSpace dry-run conversion
  so approved/done mission-state rows can validate against the canonical event
  contract.

## [3.2.0rc5] - 2026-05-11

3.2.0rc5 closes the remaining CLI-side TeamSpace migration readiness gaps found
while rechecking the historical mission-state migration parent issue.

### Changed

- Documented the deterministic historical mission-state repair contract and
  safe release sequencing used before any repository-wide repair is required.

### Fixed

- Block TeamSpace dry-run/import envelope synthesis when audit findings still
  contain TeamSpace blockers, so legacy mission-state rows cannot bypass the
  readiness audit.
- Reject historical mission-state sync batches with legacy status fields before
  network submission, preserving the local queue and returning remediation.

## [3.2.0rc4] - 2026-05-11

3.2.0rc4 tightens the TeamSpace release candidate against the published
`spec-kitty-events` 5.0.0 contract and includes the latest migration rehearsal
diagnostics.

### Changed

- Tightened the CLI `spec-kitty-events` dependency to `>=5.0.0,<6.0.0` now
  that the 5.0.0 TeamSpace canonical event contract is published to PyPI
  (#978).
- Included the TeamSpace dry-run row mapping diagnostics merged after rc3 so
  migration rehearsals can trace source rows to synthesized TeamSpace envelopes
  (#1014).

## [3.2.0rc3] - 2026-05-06

3.2.0rc3 fixes a TeamSpace dry-run compatibility gap found during the
historical mission-state migration rehearsal.

### Fixed

- Synthesized minimal repo evidence for historical done rows that only
  preserved review evidence, allowing `doctor mission-state --teamspace-dry-run`
  to validate those rows against the `spec-kitty-events` 5.0.0 payload contract
  (#997).

## [3.2.0rc2] - 2026-05-05

3.2.0rc2 adds the TeamSpace mission-state repair and validation surface needed
before public TeamSpace import. The repair command is available now; the
TeamSpace dry-run path requires `spec-kitty-events>=5.0.0` once that contract
package is published.

### Added

- Added deterministic `doctor mission-state --fix` repair for historical
  `kitty-specs/` state, including Git safety checks, migration manifests, legacy
  key cleanup, typed-row quarantine, lane normalization, and production
  `status.json` rematerialization (#980).
- Added `doctor mission-state --teamspace-dry-run` to synthesize canonical
  TeamSpace envelopes in memory and validate them with the 5.0.0 event contract
  when available (#980).
- Documented the distributed Git repair workflow for coordinated repository
  migration before TeamSpace launch (#980).
- Added `doctor mission-state --include-fixtures` and the packaged
  mission-state survey fixture pack used by the TeamSpace readiness audit
  contract (#920, #922, #929).
- Added an opt-in `TeamSpace Mission-State Readiness` GitHub Actions workflow
  that runs `doctor mission-state --audit --fail-on teamspace-blocker` and
  uploads the JSON audit artifact (#920, #934).

### Changed

- Aligned CLI sync emission for `WPStatusChanged` and `MissionClosed` with the
  canonical TeamSpace event payload shape while keeping launch dry-run gated on
  the published events contract (#980).
- `doctor mission-state --audit` JSON reports now expose TeamSpace blocker
  counts, and `--fail-on teamspace-blocker` gates import/sync readiness
  without requiring network access (#920, #934).

## [3.2.0rc1] - 2026-05-05

3.2.0rc1 is the first release candidate for the 3.2.0 line. It rolls up the
workflow stabilization work from the alpha series and the final release
confidence missions.

### Fixed

- Hardened the mission status, review, and merge surfaces that block reliable
  implement-review-retrospect loops, including stale review verdict handling,
  finalized-board routing, canonical review feedback pointers, and first-class
  retrospective synthesis paths.
- Fixed task-board progress semantics so done-only counts are no longer paired
  with unlabeled weighted readiness percentages; JSON status output now exposes
  explicit progress semantics and weighted readiness fields (#966).
- Added an installed dependency drift guard for shared packages so release and
  review evidence fail when the active environment disagrees with `uv.lock` for
  `spec-kitty-events` or `spec-kitty-tracker` (#848).
- Addressed final mission-review regressions around machine-facing contract
  output, sync-control side effects, and the charter golden-path E2E assertion.

### Release Validation

- Closed the stale ruff blocker after `uv run ruff check src tests` passed on
  current `main` (#869).
- Re-ran final local release gates from fresh `origin/main`: dependency sync,
  lock validation, installed shared-package drift guard, ruff, and the
  contract/architectural/release pytest batch all passed.
- GitHub Actions on the release candidate base commit passed `CI Quality`,
  `ci-windows`, and `Protect Main Branch`.

### Known Limitations

- The broad strict mypy gate remains tracked for follow-up in #971 and is not a
  blocking gate for this release candidate.
- Hosted sync drain reliability has a known SaaS-sync limitation tracked in
  #889; do not treat this release candidate as proof of full hosted drain
  reliability until that issue is fixed.

## [3.2.0a10] - 2026-05-04

3.2.0a10 is a prerelease that stabilizes the implement-review-retrospect
control loop after the 3.2.0 release-blocker triage.

### Fixed

- Rejection transitions from `in_review` now derive or require structured
  rejected review results before mutating task state, closing the gap where
  reviewer feedback could fail without a durable review result (#960).
- Review feedback pointers are canonicalized to `review-cycle://...` URIs and
  legacy `feedback://` references are normalized or resolved with a warning,
  preserving focused fix-mode context across rejection cycles (#962).
- Written `review-cycle-N.md` artifacts now include required YAML frontmatter
  before they can be referenced, and invalid review artifacts fail closed
  instead of leaving dangling status pointers (#963).
- `spec-kitty next` now treats finalized task boards and work-package lane
  state as authoritative in query mode without bypassing mutating runtime
  composition or retrospective terminus handling (#961).
- Completed missions now have a usable `agent retrospect synthesize` path when
  `retrospective.yaml` is missing, with JSON output that distinguishes created,
  synthesized, insufficient-artifacts, and mission-not-found outcomes (#965).

### Internal

- Added targeted regression coverage for the shared review-cycle domain,
  rejection transitions, canonical feedback resolution, finalized routing,
  retrospective synthesis, and the focused implement-review-retrospect smoke
  path.

## [3.2.0a9] - 2026-05-03

3.2.0a9 is a prerelease that adds mission-state audit diagnostics and hardens
the 3.2.0 workflow reliability path for implementation, review, merge, and
release-blocker triage.

### Added

- Added a read-only mission-state audit engine for inspecting mission status,
  work package state, review artifacts, and lifecycle consistency without
  mutating project state.
- Added reliability fixture coverage for branch, mission, review prompt, and
  sync workflows used by the 3.2.0 release-blocker tranche.

### Fixed

- Implementation start is now idempotent across planned, claimed, and
  in-progress task states, preventing duplicate or inconsistent lifecycle
  transitions (#946).
- Merge preflight now refreshes the target branch tracking ref before enforcing
  target-branch synchronization, so stale local `origin/main` state cannot
  allow an unsafe merge (#959).
- Merge, review prompt, worktree ownership, sync finalization, and review
  artifact consistency checks now have tighter diagnostics and regression
  coverage for the 3.2.0 workflow reliability tranche (#959).
- Command JSON output now avoids leaking non-serializable status event mocks in
  covered move-task paths, preserving strict JSON command contracts.

### Internal

- Recorded the atomic work-package start lifecycle ADR and expanded regression
  coverage around status persistence, bootstrap seeding, merge preflight, and
  test sync isolation.
- Restored CI release confidence by covering the previously failing
  `fast-tests-core-misc`, `integration-tests-merge`, `integration-tests-cli`,
  and `diff-coverage` gates.

## [3.2.0a8] - 2026-05-01

3.2.0a8 is a prerelease that hardens direct SaaS sync ingress around the
Private Teamspace boundary. CLI sync side effects now resolve a canonical
Private Teamspace target, rehydrate session membership once when needed, and
skip direct ingress with a diagnostic instead of falling back to a shared team.

### Fixed

- Direct sync ingress for `/api/v1/events/batch/` and `/api/v1/ws-token` now
  uses a strict Private Teamspace resolver and refuses shared-team fallbacks
  from stale `default_team_id`, `teams[0]`, or websocket state (#943).
- Auth refresh and session rehydration now update team membership from
  `/api/v1/me`, recomputing `default_team_id` from the refreshed private team
  list instead of preserving stale shared defaults (#943).
- `--json` command stdout remains parseable when SaaS sync cannot connect or
  cannot resolve a Private Teamspace; sync diagnostics route to stderr or
  structured logs rather than contaminating stdout (#943).

### Internal

- Added strict resolver, sync call-site, websocket, offline queue, and
  strict-JSON regression coverage for the Private Teamspace ingress boundary.
- Added mission review evidence for
  `private-teamspace-ingress-safeguards-01KQH03Y`.

## [3.2.0a7] - 2026-05-01

3.2.0a7 is a focused prerelease that bounds WebSocket sync startup and
shutdown behavior. Short-lived agent commands now fail over to batch sync
instead of hanging indefinitely when a local sync socket accepts the
connection but never emits the initial snapshot.

### Fixed

- WebSocket sync startup now has bounded open, initial snapshot, and close
  deadlines so `spec-kitty agent mission setup-plan` and other short-lived
  commands degrade to batch sync instead of blocking forever on a stalled
  sync socket (#936).

### Internal

- Added regression coverage for a WebSocket connection that never sends the
  initial snapshot and for shutdown paths where the close handshake stalls.
- Aligned existing Bandit suppressions in touched sync/readiness callsites so
  local and CI security scans recognize the intended safe dynamic SQL and
  localhost URL patterns.

## [3.2.0a6] - 2026-04-30

3.2.0a6 is a prerelease hardening sweep that restores the documented
fresh-project golden path (`init` → charter `setup`/`generate`/
`synthesize` → `next`), locks in strict JSON for covered `--json` commands
under any SaaS state, fixes agent identity parsing and review-cycle
accounting, adds paired profile-invocation lifecycle observability for
`spec-kitty next`, and tightens merge/review/status recovery paths. The
release introduces the new top-level `spec-kitty review` mission-review
command and no new top-level runtime dependencies.

### Fixed

- `charter bundle validate --json` now fail-closes on incomplete Charter
  synthesis state while preserving strict JSON stdout. Sidecar-only bundles,
  manifest-only bundles, incompatible bundle versions, missing provenance
  sidecars, dangling sidecar references, and synthesis manifest integrity
  failures all produce parseable failure envelopes with actionable
  `synthesis_state` details (#914, closes the final Phase 7 release gap for
  #469/#515).
- Stamp `schema_version` and a `schema_capabilities` block in
  `.kittify/metadata.yaml` on `spec-kitty init` so a fresh project no
  longer requires hand-edits before subsequent CLI commands; existing
  schema fields are preserved (additive, idempotent) (#840, WP01).
- Strict JSON envelope contract for covered `--json` commands: stdout is
  parseable by `json.loads` regardless of SaaS sync state (disabled,
  unauthorized, network-failed, success); sync/auth diagnostics route to
  stderr or nest inside the envelope (#842, WP02).
- `WPMetadata.resolved_agent()` parses 4-segment colon-delimited agent
  strings (`tool:model:profile:role`) and preserves every supplied field
  through implement and review prompt rendering, with deterministic
  fallback for partial strings (#833, WP03).
- Review-cycle counter advances exactly once per genuine reviewer
  rejection; reclaim/regenerate of an `implement` prompt no longer
  inflates the counter or writes a spurious `review-cycle-N.md`
  artifact (#676, WP04).
- `spec-kitty next` writes paired `started`/`completed` profile-invocation
  lifecycle records keyed to the canonical mission step + action it
  issued, observable via `spec-kitty doctor invocation-pairing` (#843,
  WP05).
- `charter generate` auto-tracks the produced `charter.md` and ensures
  the required `.gitignore` entries exist; `charter bundle validate`
  succeeds immediately afterwards with no operator `git add` between
  the two commands. Outside a git working tree, `generate` fails fast
  with an actionable error that names `git init` as the remediation
  (#841, WP06).
- `charter synthesize` succeeds on a fresh project via the public CLI
  with no hand-seeded `.kittify/doctrine/`; the bounded fresh-project
  path materialises a minimal doctrine tree (`PROVENANCE.md`) so the
  shipped doctrine layer can supply content (#839, WP06).
- `spec-kitty merge --abort` now clears the global merge lock, removes
  legacy merge-state files, aborts an in-progress Git merge when present,
  and remains idempotent when no merge is active (#903).
- Approved/done work packages with stale `verdict: rejected` review
  artifacts are now surfaced across status views, including
  `spec-kitty agent tasks status` and `show_kanban_status()`. Review
  artifact lookup follows the real `tasks/<WP-slug>/review-cycle-N.md`
  layout, and `in_review` work packages now warn when reviewer movement
  stalls beyond the configured threshold (#904, #909).
- Review lane-guard failures now name the planning branch and include a
  concrete `git show <planning-branch>:<path>` command for the first
  contaminated path, instead of a placeholder path (#905).
- Work-package review definition-of-done coverage now includes real error
  path and artifact-deletion regressions, not only happy-path review
  behavior (#906).
- Broad `except Exception` / BLE001 suppressions in touched runtime paths
  were audited and now carry inline justification where fail-open behavior
  is intentional (#907).
- `spec-kitty review <mission>` is now a first-class mission-review CLI
  command with structured status/exit behavior for post-merge mission
  fidelity checks (#908).

### Internal

- Consolidated golden-path E2E (`tests/e2e/test_charter_epic_golden_path.py`)
  rewritten to drive the fresh-project chain through the public CLI
  only - no hand seeding of `.kittify/doctrine/`, no edits to
  `.kittify/metadata.yaml`, no manual `git add` of charter artifacts
  between `generate` and `bundle validate`. Runs in well under the
  120-second NFR-007 budget. Also exercises strict JSON parsability of
  `mission branch-context --json` (WP02 spot-check) and the `started`
  lifecycle record (WP05 spot-check) (WP07).
- Governance setup docs (`docs/how-to/setup-governance.md`) note that
  `charter generate` now auto-tracks `charter.md`, removing any
  expectation that operators run `git add` between `generate` and
  `bundle validate` (WP07).
- Added regression coverage for merge abort cleanup, stale rejected review
  artifacts, stalled in-review work packages, lane-guard remediation text,
  mission-review command behavior, review DoD deletion/error cases, and
  agent-shard coverage for status warning paths (#903-#909).

### Tranche-2 acceptance pass (SC-001..SC-008)

- **SC-001 (Fresh-path completion)** - `tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path` walks `init → charter interview → generate → bundle validate → synthesize → mission create → setup-plan → finalize-tasks → next` against a fresh project with no `.kittify/` hand-edits and no `git add` of charter artifacts. Passes locally in <20s.
- **SC-002 (JSON parsability)** - `tests/integration/test_json_envelope_strict.py` (WP02) covers the SaaS state matrix; the consolidated E2E spot-checks `mission branch-context --json` via `json.loads(stdout)`.
- **SC-003 (Identity preservation rate)** - WP03 unit + integration tests cover colon arities 1–4 and assert `model`/`profile_id`/`role` in rendered prompts.
- **SC-004 (Review-cycle precision)** - WP04 tests assert the counter is unchanged across ≥3 reclaim/regenerate runs and advances by exactly 1 on a real rejection.
- **SC-005 (Lifecycle observability)** - `tests/integration/test_next_lifecycle_records.py` (WP05) covers ≥5 issuances with mid-cycle orphan; the consolidated E2E asserts at least one `started` record after `next` issues an action and that the `canonical_action_id` matches the issued step id.
- **SC-006 (Charter parity rate)** - `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` (WP06) covers the auto-track + non-git fail-fast contract; the consolidated E2E exercises `generate → bundle validate` with no intervening git ops.
- **SC-007 (Documentation/CLI agreement)** - `docs/how-to/setup-governance.md` updated; no documented governance-setup flow contains a `git add charter.md` step between `charter generate` and `charter bundle validate`.
- **SC-008 (Release-surface discipline)** - Diff inventory: one new top-level public CLI command, `spec-kitty review`, added for mission-review fidelity checks (#908); one new `spec-kitty doctor invocation-pairing` subcommand under the existing `doctor` group for lifecycle observability; zero new top-level runtime dependencies in `pyproject.toml` `[project.dependencies]`.

## [3.2.0a5] - 2026-04-27

### Fixed

- CLI auth now consumes the server Tranche 2 contract end to end: logout posts refresh tokens to `/oauth/revoke`, local credential cleanup failures are reported truthfully, refresh handles benign 409 replay without resubmitting a spent token, and `auth doctor --server` checks `/api/v1/session-status` with safe re-authentication guidance (#902).
- Fix `spec-kitty upgrade` silently leaving projects in PROJECT_MIGRATION_NEEDED state by stamping `schema_version` after metadata save (#705, WP01).
- `spec-kitty init` in a non-git directory now prints an actionable "run `git init`" message (#636, WP05).
- Suppress misleading "shutdown / final-sync" red error lines after a successful `spec-kitty agent mission create --json` payload (#735, WP06).
- Deduplicate "Not authenticated, skipping sync" / "token refresh failed" diagnostics to at most once per CLI invocation (#717, WP06).
- Fix `read_events()` raising `KeyError('wp_id')` on `DecisionPointOpened` / `DecisionPointResolved` events that share `status.events.jsonl` with lane-transition events. Restores `finalize-tasks` / `materialize` / dashboard for any mission that uses the decision moment Protocol (#830, WP08).

### Changed

- Loosen `.python-version` from a hard `3.13` pin to `3.11` (the floor declared by `pyproject.toml`) and restore `mypy --strict` cleanliness on `mission_step_contracts/executor.py` (#805, WP03).

### Removed

- Retire the deprecated `/spec-kitty.checklist` command surface from every supported agent's rendered output. The canonical requirements checklist at `kitty-specs/<mission>/checklists/requirements.md` is unaffected (#815, supersedes #635, WP04).

### Internal

- Add regression tests confirming `--feature` aliases stay hidden from `--help` while remaining accepted (#790, WP07).
- Add regression test confirming `spec-kitty agent decision` command shape stays consistent across docs / help / skill snapshots (#774, WP07).

### Added

- **Frontend Freddy agent profile** - browser-side implementer specialising in HTML/CSS/JavaScript/TypeScript, component frameworks (React, Vue, Svelte), WCAG 2.1 accessibility, Core Web Vitals performance, and frontend testing (vitest, Playwright). Specialises from `implementer-ivan`. Self-review protocol enforces lint, type-check, unit/component tests, e2e smoke, axe accessibility gate, and bundle budget. Avoidance boundary explicitly names Node Norris's server-side domain.
- **Node Norris agent profile** - server-side Node.js implementer specialising in HTTP APIs (Express/Fastify/NestJS), async/Promise discipline, streaming, npm security (`npm audit`), and integration testing (supertest). Specialises from `implementer-ivan`. Avoidance boundary explicitly names Frontend Freddy's browser-rendering domain. The two profiles are mutually exclusive by design.
- **BDD paradigm** (`behaviour-driven-development`) - encodes BDD as a three-phase collaboration practice: Discovery (Three Amigos conversations), Formulation (Given/When/Then specifications), and Automation (executable living documentation). References `DIRECTIVE_034` and `DIRECTIVE_037`.
- **BDD Scenario Lifecycle procedure** (`bdd-scenario-lifecycle`) - covers the Formulation → Automation → Maintenance phases that follow an Example Mapping Workshop. Toolchain-agnostic (Cucumber-JVM, Cucumber-JS, Behave, SpecFlow). Encodes four anti-patterns: imperative Gherkin, rubber-stamp scenarios, shared mutable state, and orphaned step definitions.
- **New tactics:**
  - `reference-architectural-patterns` - structured selection of named reference patterns (Layered, Hexagonal, Event-Driven, CQRS, Microservices, Modular Monolith) scored against coupling, scalability, and operational complexity constraints.
  - `development-bdd` - architecture-level BDD tactic for expressing observable behavioral contracts at system boundaries before implementation; distinct from the existing `behavior-driven-development` technique tactic.
  - `bug-fixing-checklist` - language-agnostic test-first defect resolution: write a reproduction test before touching production code.
  - `test-readability-clarity-check` - dual-perspective reconstruction check: read only tests, reconstruct system understanding, compare against spec to surface documentation gaps.
  - `code-documentation-analysis` - brownfield boundary discovery by extracting and clustering domain terminology from code and documentation artifacts. Contributes foundational analysis tactics toward the brownfield investigation skill described in [#666](https://github.com/Priivacy-ai/spec-kitty/issues/666).
  - `terminology-extraction-mapping` - systematic extraction and relationship mapping of domain terms across multiple sources to produce a maintainable glossary. Complementary artifact to the bounded-context linguistic discovery approach targeted by [#666](https://github.com/Priivacy-ai/spec-kitty/issues/666).
- **Tactic directory normalization** - shipped tactics reorganised into four category subdirectories: `testing/` (15 tactics), `analysis/` (14), `communication/` (7), `architecture/` (14). Cross-cutting tactics remain in the `shipped/` root. The existing `rglob` loader requires no changes.
- **`tasks-finalize` command skill** - added to `CANONICAL_COMMANDS` in the agent skills pipeline and deployed to `.agents/skills/spec-kitty.tasks-finalize/`. Closes the gap where this command was missing from Codex/Vibe skill packages. <!-- tool-surface: ignore -->

### Changed

- **Profile enrichment** - four existing profiles updated with additive tactic and paradigm references:
  - `implementer-ivan`: `bug-fixing-checklist` tactic reference (propagates to all specialist profiles via `resolve_profile()` union merge).
  - `reviewer-renata`: `test-readability-clarity-check` and `bdd-scenario-lifecycle` tactic references; `behaviour-driven-development` paradigm in context sources.
  - `architect-alphonso`: `development-bdd` tactic reference; BDD paradigm, example-mapping-workshop, and bdd-scenario-lifecycle in additional context sources.
  - `java-jenny`: `behavior-driven-development` and `bdd-scenario-lifecycle` tactic references; `bdd-scenarios` self-review step (Cucumber-JVM + Serenity BDD gate).
- **`behavior-driven-development` tactic enriched** - extended `notes` with a toolchain landscape section (Cucumber family, Playwright, Selenium, Serenity BDD, custom DSLs; source: `patterns.sddevelopment.be/primers/toolchain-and-automation/bdd`); three new `failure_modes` (rubber-stamp scenarios, shared mutable state between scenarios, orphaned step definitions); cross-references to the new BDD paradigm and procedure.
- **`tactic-references` union-merged in `resolve_profile()`** - `tactic-references` added to `_LIST_FIELDS` in `src/doctrine/agent_profiles/repository.py`. Specialist profiles now inherit base-profile tactic references via `_union_merge` at resolution time rather than overriding them.
- **Tactic compliance test extended** - `test_tactic_compliance.py` `ARTIFACT_DIRS` now includes `procedure` and `paradigm` types, enabling cross-type reference validation for tactics that reference procedures or paradigms.
- **Shared package boundary cutover** (mission `shared-package-boundary-cutover-01KQ22DS`) - `spec-kitty-runtime` is no longer a dependency of `spec-kitty-cli`. The CLI now owns its own runtime internally under `src/specify_cli/next/_internal_runtime/`; `spec-kitty next` works from a clean install of `spec-kitty-cli` alone. `spec-kitty-events` and `spec-kitty-tracker` are external PyPI dependencies consumed via their public import surfaces (`spec_kitty_events`, `spec_kitty_tracker`). The vendored events tree under `src/specify_cli/spec_kitty_events/` has been removed (~23 kLoC). Developers who relied on editable cross-package overrides should consult [`docs/development/local-overrides.md`](../development/how-to/local-overrides.md); operators upgrading from a pre-cutover release should consult [`docs/migration/shared-package-boundary-cutover.md`](../migrations/shared-package-boundary-cutover.md). Decision rationale recorded in [ADR 2026-04-25-1](../adr/3.x/2026-04-25-1-shared-package-boundary.md).

### Removed

- **`constraints.txt`** - the file existed solely to paper over a transitive pin conflict with the retired `spec-kitty-runtime` package and is no longer needed.

### Fixed

- `spec-kitty agent config list/status` now checks global command roots for slash-command agents instead of reporting missing project-local command directories after `init`.
- `spec-kitty agent config add/sync --create-missing` no longer recreates retired project-local command directories for globally managed slash-command agents.
- `spec-kitty agent config remove/sync` now removes only the managed command surface for project-local agent directories, preserving unrelated files such as `.github/workflows/`.

### Added - Documentation mission composition rewrite (#502, #461, Phase 6 WP6.4)

- Documentation mission now runs on the StepContractExecutor composition substrate, mirroring research (#504) and software-dev (#503). The runtime resolves the new composed step contracts ahead of the legacy `mission.yaml` workflow via the existing `_resolve_runtime_template_in_root` precedence - no loader changes were required.
- New runtime sidecar templates: `src/specify_cli/missions/documentation/mission-runtime.yaml` and `src/doctrine/missions/documentation/mission-runtime.yaml`.
- Six shipped step contracts under `src/doctrine/mission_step_contracts/shipped/documentation-{discover,audit,design,generate,validate,publish}.step-contract.yaml`.
- Six action doctrine bundles under `src/doctrine/missions/documentation/actions/{discover,audit,design,generate,validate,publish}/` (governance guidelines + directive/tactic indices).
- DRG action nodes and edges for `action:documentation/{discover,audit,design,generate,validate,publish}` in `src/doctrine/graph.yaml`.
- Composition wiring in `src/specify_cli/next/runtime_bridge.py`: `_COMPOSED_ACTIONS_BY_MISSION["documentation"]` and a fail-closed guard branch in `_check_composed_action_guard()` raising a structured error for unknown documentation actions. `src/specify_cli/mission_step_contracts/executor.py` adds six `_ACTION_PROFILE_DEFAULTS` entries (`researcher-robbie` for discover/audit, `architect-alphonso` for design, `implementer-ivan` for generate, `reviewer-renata` for validate/publish).
- Real-runtime integration walk at `tests/integration/test_documentation_runtime_walk.py` proving SC-001 / SC-003 / SC-004 from a freshly initialized temp repo.

#### Backward compatibility

- The legacy `src/specify_cli/missions/documentation/mission.yaml` and `src/doctrine/missions/documentation/mission.yaml` files remain on disk for backward reference. Existing documentation-mission projects that authored against the legacy workflow continue to work; runtime template resolution prefers the new `mission-runtime.yaml` ahead of the legacy file via the existing precedence in `_resolve_runtime_template_in_root` (no loader changes in this PR).

### Added

- **Upgrade compatibility planner** - `spec-kitty upgrade` now separates CLI
  update guidance from current-project schema compatibility. New flags
  `--cli`, `--project`, `--yes`, and `--no-nag` support CLI-only guidance,
  project-only migrations, non-interactive confirmation, and explicit nag
  suppression. `spec-kitty upgrade --dry-run --json` emits the stable
  compatibility-plan contract for automation.
- **Host-surface parity matrix** at `docs/host-surface-parity.md` - authoritative record of how each of the 15 supported host surfaces teaches the standalone dispatch governance-injection contract. Closes the remaining `#496` host-surface breadth rollout.
- **Mode of work runtime derivation** - every standalone dispatch invocation records its `mode_of_work` (`task_execution`, `mission_step`, or `query`) on the `started` event. Derivation is from the CLI entry command.
- **Correlation links** - `spec-kitty profile-invocation complete` accepts `--artifact <path>` (repeatable) and `--commit <sha>` (singular); each appends an additive event to the invocation JSONL for single-file request→artifact/commit correlation.
- **SaaS read-model policy** at `src/specify_cli/invocation/projection_policy.py` - typed module mapping `(mode, event)` to projection rules. Documented in `docs/trail-model.md`.
- **Tier 2 SaaS projection decision** - decisively documented as deferred in `docs/trail-model.md`. Tier 2 evidence stays local-only in 3.2.x.
- **README Governance layer subsection** - entry point for operators discovering standalone dispatch.
- **decision moment Ledger (V1)** - new `spec-kitty agent decision` subgroup with five
  subcommands: `open`, `resolve`, `defer`, `cancel`, `verify`. Mints ULID `decision_id`s
  at interview ask-time, writes paper trail under `kitty-specs/<mission>/decisions/`
  (`index.json` + `DM-<id>.md`), and appends `DecisionPointOpened(interview)` /
  `DecisionPointResolved(interview)` events to `status.events.jsonl`. Local-only;
  no SaaS sync required.
- **Charter integration** - `spec-kitty charter interview` now calls `decision open`
  before each question and the appropriate terminal command after each answer.
  `answers.yaml` behavior is unchanged.
- **Specify + Plan template updates** - `specify.md` and `plan.md` source templates
  gain a decision moment Protocol section instructing the LLM to call decision
  subcommands at ask/resolution time and write `<!-- decision_id: <id> -->` anchors
  for deferred decisions.
- **`decision verify` gate** - scans `spec.md` / `plan.md` for
  `[NEEDS CLARIFICATION: ...] <!-- decision_id: <id> -->` sentinels and
  cross-checks against the decisions index. Exits non-zero on drift
  (`DEFERRED_WITHOUT_MARKER`, `MARKER_WITHOUT_DECISION`, `STALE_MARKER`).
- **widen mode (#758)** - `spec-kitty agent decision widen` + `resolve --from-widen`
  lifecycle. Writes `widen-pending.jsonl`, emits `DecisionPointWidened` events,
  integrates with charter/specify/plan widen affordances. Surfaces decision
  write-back errors explicitly instead of silently suppressing them.

### Changed

- Project schema compatibility is now enforced by the centralized compat
  planner. Out-of-date CLI notices are passive and throttled; incompatible
  project schemas block unsafe commands with exit codes 4, 5, or 6 and exact
  remediation guidance.
- `spec-kitty profile-invocation complete --evidence` is now mode-gated: rejected on non-evidence-eligible invocations with `InvalidModeForEvidenceError`. Rejection occurs before any write; the invocation stays open.
- `_propagate_one` consults the new projection policy after the sync-gate and authentication lookup. Existing `task_execution` / `mission_step` projection behaviour is preserved exactly.
- Dashboard user-visible wording: the mission selector, current-mission header, overview heading, analysis heading, and empty-state prompt now read "Mission Run" / "mission" instead of "Feature". Backend identifiers (CSS classes, HTML IDs, cookie keys, API route segments, JSON field names) are unchanged.
- **`spec-kitty-events` bumped to `==4.0.0`** - vendored copy at
  `src/specify_cli/spec_kitty_events/` refreshed. Introduces
  `DecisionPointOpenedInterviewPayload`, `DecisionPointResolvedInterviewPayload`,
  `OriginSurface.PLANNING_INTERVIEW` (`origin_surface: planning_interview`),
  `OriginFlow` enum (values `specify`, `plan`), `DecisionPointWidened`, and
  `TerminalOutcome` enum.
- **`[tool.uv.sources]`** redirects `spec-kitty-events` to `../spec-kitty-events/`
  in editable mode for monorepo development. Dev-only; ignored by pip / PyPI.

### Deferred

- `spec-kitty explain` (issue #534) remains deferred to Phase 5 pending DRG glossary addressability (#499, #759).

### Out of scope (tracked separately)

- SaaS sync projection for widened decisions - tracked in spec-kitty-saas#110, #111.
- Tasks-phase interview support - future mission.

### Migration notes

**No operator action required for routine upgrade.** The trail model is additive:

- Pre-mission invocation records (no `mode_of_work`) continue to accept `--evidence` and project under legacy `task_execution` rules.
- Existing SaaS dashboards see no change for `task_execution` / `mission_step` traffic.
- New standalone dispatch events now appear in the SaaS timeline as minimal entries without body - this is a deliberate behaviour change documented in the SaaS Read-Model Policy table.

### Added (Phase 4 trail follow-on)

- `docs/trail-model.md`: Formal operator documentation for the Phase 4 trail contract,
  mode-of-work taxonomy, tier promotion rules, SaaS projection policy, intake positioning,
  and explain deferral (WP04).
- "Governance context injection" section in `.agents/skills/spec-kitty/SKILL.md` <!-- tool-surface: ignore -->
  for Codex/Vibe hosts, enabling Tier 1 trail recording without host-side SaaS auth (WP03).
- "Standalone invocations (outside missions)" section in
  `src/doctrine/skills/spec-kitty-runtime-next/SKILL.md` for Claude Code and gstack hosts,
  covering when to open an invocation record outside the mission workflow (WP04).
- End-to-end invocation integration tests in
  `tests/specify_cli/invocation/test_invocation_e2e.py` covering Tier 1 JSONL write,
  complete-event append, local-only list read, and sync-gate suppression (WP05).

### Fixed

- `propagator.py` (`_propagate_one`): Invocation events are now suppressed when
  `effective_sync_enabled = False`, even when the user is authenticated. Previously,
  sync-disabled checkouts could still emit SaaS events if a WebSocket client was
  connected (WP01).
- `executor.complete_invocation` now calls `promote_to_evidence()` when the
  `--evidence` flag is supplied, enabling correct Tier 2 artifact promotion (WP03).

### Changed

- Issue #496: Priority-surface slice complete in 3.2.x (Claude Code via
  `spec-kitty-runtime-next` doctrine skill, Codex CLI via SKILL.md governance context
  injection). Remaining 9 surfaces tracked in #496 for a follow-on patch or Phase 5.
- Issue #534: `spec-kitty explain` explicitly deferred to Phase 5 (requires DRG
  glossary addressability, issue #499). A partial implementation without glossary
  citations would be misleading.

## [3.2.0a4] - 2026-04-21

### Added

- **Mutation-aware test suites** - kill-the-survivor passes for `doctrine.resolver`, `doctrine.agent_profiles`, `doctrine.missions`, `doctrine.shared`, and `specify_cli.compat.registry`. Achieves 75–85 % kill rates per module; residuals documented as trampoline-equivalent, unloadable, or functionally equivalent in `docs/development/mutation-testing-findings.md`.
- `_OPTIONAL_KEYS` / `_ALL_KNOWN_KEYS` constants in `specify_cli.compat.registry._validate_entry` - unknown YAML keys now raise `RegistrySchemaError` before `ShimEntry(**entry)` can raise `TypeError`.
- `model_dump(mode="json")` on WP frontmatter serialization in `finalize_tasks` - prevents `Path` objects from reaching YAML serialization.

### Added

## [3.2.0a3] - 2026-04-21

### Fixed

- Release publish no longer hard-fails when the private `SPEC_KITTY_SAAS_READ_TOKEN` secret is absent. The pipeline still enforces runtime drift and exact wheel installability, and it runs the SaaS consumer-contract check whenever the private compatibility reference can actually be fetched.

## [3.2.0a2] - 2026-04-21

### Changed

- `spec-kitty-runtime` is now pinned to `0.4.4`, matching the corrected published runtime line rather than the broken `0.4.3` metadata.
- Release readiness and tag-time publish pipelines now verify shared-package drift, candidate-wheel installability with plain `pip`, and candidate compatibility against the SaaS consumer contract before publish.

### Removed

- Temporary `tool.uv.override-dependencies` masking for `spec-kitty-events`. Release validation now requires the published runtime metadata to resolve cleanly without local overrides.

## [3.2.0a1] - 2026-04-20

### Added

- **Mutation testing** - `mutmut` 3.5.0 added to `[project.optional-dependencies.test]` and configured in `[tool.mutmut]` as a **local-only** quality gate. Includes a curated doctrine set: `tactic:mutation-testing-workflow`, `styleguide:mutation-aware-test-design`, and language-specific toolguides for Python (`mutmut`) and TypeScript (`stryker`), all anchored to `DIRECTIVE_034` in the DRG graph. ADR `2026-04-20-1-mutation-testing-as-local-only-quality-gate.md` records the decision, the sandbox constraints, and the two-marker exclusion taxonomy.
- **`non_sandbox` / `flaky` pytest markers** - registered in `pytest.ini` and `pyproject.toml[tool.pytest.ini_options].markers`. Per-file `--ignore=` entries for sandbox-incompatible tests have been migrated to module-level `pytestmark` declarations; `[tool.mutmut].pytest_add_cli_args` now deselects via `-m "not non_sandbox and not flaky ..."`. Directory-level ignores remain only where tests fail during pytest _collection_ (import errors that markers cannot intercept). 1 test is currently marked `flaky` as debt to be root-caused.
- **`docs/how-to/run-mutation-tests.md`** - Contributor how-to covering local `mutmut run` invocation, the kill-the-survivor workflow, equivalent-mutant suppression, and the `non_sandbox` / `flaky` marker taxonomy.
- Charter synthesizer now has a real harness-owned operator path: the new generated-artifact adapter reads agent-authored YAML from `.kittify/charter/generated/` and promotes validated doctrine into the live `.kittify/doctrine/` tree.
- `spec-kitty charter resynthesize --list-topics` now lists valid project-artifact selectors, DRG URNs, and interview-section selectors, including hyphenated aliases for section names.
- `spec-kitty charter status --provenance` now reports synthesis generation state, evidence summary, manifest health, and per-artifact provenance visibility alongside the older charter sync surface.
- ADR `2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md` now records the host-side charter handoff contract: exact file layout, identity rules, and CLI sequence.
- **`architecture/2.x/06_migration_and_shim_rules.md`** - Authoritative compatibility shim lifecycle
  rulebook covering 4 rule families: schema/version gating, bundle/runtime migration authoring contract,
  shim lifecycle (with copy-paste template), and removal plans/registry contract. Required reading for
  all future extraction missions (#615).
- **`architecture/2.x/shim-registry.yaml`** - Machine-readable registry of all known compatibility
  shims. Starts empty (zero-shim baseline confirmed at mission-615 start). Future shims must be
  registered here before merging. Validated by `spec-kitty doctor shim-registry` (#615).
- **`spec-kitty doctor shim-registry`** - New CI enforcement subcommand that classifies each
  registered shim as `pending`, `overdue`, `grandfathered`, or `removed`. Exits 1 when any shim
  is overdue; exits 2 on configuration error. Supports `--json` for machine-readable CI output (#615).

### Changed

- `spec-kitty charter synthesize` and `spec-kitty charter resynthesize` now default to the generated-artifact adapter. `--adapter fixture` remains available only for deterministic offline regression runs.
- `spec-kitty charter synthesize --dry-run` is now a real stage-and-validate pass: it writes the staged artifact set, runs project DRG validation and neutrality gating, and only skips the final promote step.
- Shared contract-library pins now align with the current released pair consumed across the CLI and SaaS surfaces: `spec-kitty-events==3.2.0` and `spec-kitty-tracker==0.4.2`.
- Release pipeline now generates and attaches a CycloneDX SBOM (`sbom.cdx.json`) to every GitHub Release. The SBOM is an environment-snapshot of the fully resolved dependency tree at build time, making it straightforward for enterprise users to ingest the inventory into tools like Dependency-Track for continuous CVE monitoring without rescanning the package themselves.

### Fixed

- Directive provenance now records canonical URNs (`directive:PROJECT_<NNN>`) instead of slug-based placeholders, which restores correct directive filenames, provenance reload, and `directive:PROJECT_<NNN>` resynthesis.
- Bounded resynthesis now preserves evidence inputs end-to-end, so regenerated provenance entries keep the correct `evidence_bundle_hash` and `corpus_snapshot_id`.
- Generated-artifact synthesis errors now point to the exact expected file path and exact expected artifact id, which makes harness handoff mistakes easier to diagnose.
- Charter neutrality lint now scans mission `templates/` directories in addition to `command-templates/`, so banned terms in generic mission prompt files are caught by the default repo scan (#653 tripwire).
- Bump `requests` floor to `>=2.33.0` (CVE-2026-25645).
- Bump `pytest` floor to `>=9.0.3` (CVE-2025-71176).
- Pin `pygments>=2.20.0` explicitly to resolve CVE-2026-4539 in the transitive dependency pulled in via `rich`.
- `auth refresh` now treats `HTTP 401` responses with `invalid_grant` or `session_invalid` error codes identically to `HTTP 400`, and clears the locally stored session on server-side refresh rejection so `auth status` no longer reports stale credentials as authenticated.

### Removed

- **`specify_cli.charter` compatibility shim** - The re-export shim at `src/specify_cli/charter/` has been
  removed. External code importing `specify_cli.charter.*` must migrate to the canonical package:
  `from charter import <name>`. See
  [docs/architecture/05_ownership_map.md](../architecture/05_ownership_map.md) for the full
  charter slice entry and the reference exemplar pattern. Closes #611.

## [3.1.8] - 2026-04-29

### Fixed

- Dashboard feature polling now tolerates `/api/features` error responses and
  malformed payloads without crashing on an undefined `features` array, so the
  UI no longer gets stuck loading when feature scanning fails.
- OpenCode global command installation now targets OpenCode's config command
  directory, honoring `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME` before
  falling back to `~/.config/opencode/commands`.

## [3.1.7] - 2026-04-28

### Fixed

- Compact charter context now preserves charter section anchors, directive IDs,
  and tactic IDs so follow-on agent prompts keep project charter rules in LLM
  context after bootstrap load.
- Review claims now enter the canonical `in_review` lane while still
  recognizing legacy review-claim events, avoiding review-loop false blocks.
- Merge completion now keeps post-merge status transitions stable and avoids
  duplicate done/approved emissions.
- `spec-kitty intake` now caps oversized plan files, ignores out-of-repo and
  symlinked auto-detected plans, and writes mission brief/provenance files
  atomically.
- `auth refresh` now treats `HTTP 401` responses with `invalid_grant` or
  `session_invalid` error codes like `HTTP 400`, and clears locally stored
  sessions after server-side refresh rejection.
- Local dashboard mission selectors now sort by mission recency instead of
  lexical slug order.
- `agent config list/status/add/sync/remove` now respects global command roots
  for slash-command agents and avoids recreating retired project-local command
  directories.
- Status event readers now ignore non-lane mission events in
  `status.events.jsonl` while still failing loudly for malformed lane events.
- Sync shutdown diagnostics are deduplicated within a process and suppressed
  after successful JSON mission creation.

### Changed

- `spec-kitty-tracker` is pinned to `0.4.3` for the latest tracker-side
  stability fixes.
- The local `.python-version` pin now uses `3.13` instead of a patch-specific
  interpreter version.

## [3.1.6] - 2026-04-20

### Fixed

- `spec-kitty agent action implement` now exposes and forwards
  `--acknowledge-not-bulk-edit` to the underlying workspace-allocation command,
  allowing non-bulk-edit missions to suppress false-positive bulk-edit inference
  warnings during workspace creation.

### Docs

- Spec Kitty's internal maintainer charter now records the ownership boundary
  for user-authored custom commands, custom skills, and project overrides, with
  an explicit proof trail showing that package-owned mutation flows must preserve
  files whose ownership is not proven by managed-path or manifest data.

## [3.1.5] - 2026-04-16

### Changed

- Keep `main` on the stable `3.x` release line. Release docs, install guidance,
  and README messaging now point new users at `3.1.x` on GitHub Releases and PyPI,
  while keeping `1.x-maintenance` explicitly maintenance-only.

### Fixed

- Make `spec-kitty upgrade` auto-commit safely through the charter rename migration.
  The `safe_commit` backstop now disables rename collapsing during its staged-path
  probe, and upgrade auto-commit expands changed directories into concrete paths
  before validating the staging area. This closes the false-positive abort reported
  in [#643](https://github.com/Priivacy-ai/spec-kitty/issues/643).
- Remove pytest/junit prompt bias from charter defaults, plan templates, and doctrine
  guidance. Packaged defaults now start from neutral selections, language inference
  flows through explicit repo signals, and language-scoped doctrine artifacts remain
  available when no active language filter is provided.

### Docs

- Align README and user-facing release docs around swim-lane terminology and the
  `3.1.x` stable release line.

## [3.1.4] - 2026-04-15

### Fixed

- Make `/spec-kitty.plan` stop instructing agents to update imaginary
  agent-specific context files or hunt for non-existent `agent context update`
  commands. Planning now stays focused on the actual mission artifacts it owns.
- Clarify `/spec-kitty.specify` mission-handle timing and non-blocking charter
  behavior so creation-time flows do not assume a mission already exists or stop
  on missing charter state.
- Tighten generated `/spec-kitty.implement`, `/spec-kitty.review`, and
  `/spec-kitty.merge` wrappers so they use the canonical `--mission <handle>`
  language and explicitly avoid redundant context rediscovery, including
  separate charter loads.

## [3.1.3] - 2026-04-15

### Fixed

- Make `/spec-kitty.charter` use an LLM-led interview by default, with better
  repo-scan guidance for greenfield/bootstrap repos, explicit doctrine-gap
  handling, natural-language questioning, depth scaling, and commit-after-generate
  behavior.
- Preserve explicit empty `selected_paradigms`, `selected_directives`, and
  `available_tools` during charter compilation instead of broadening them to
  packaged defaults.

### Docs

- Add ADR recording that explicit empty charter selections must remain empty and
  must not silently expand to shipped defaults.

## [3.1.2] - 2026-04-15

### Fixed - CI recovery & release readiness

- **`release-readiness` workflow now filters `windows_ci` tests** on the Linux runner. The job was running the full suite with no marker filter, failing 10 Windows-only tests (auth file-fallback, kernel paths, sync daemon paths, tracker credentials, migrate messaging, keyring packaging, lock contention, Windows home path). Those tests continue to run on the native `ci-windows.yml` job.
- **Kiro agent registration completed**: added `.kiro/` to `gitignore_manager.AGENT_DIRECTORIES`, regenerated 11 canonical command baselines under `tests/specify_cli/regression/_twelve_agent_baseline/kiro/`, and updated the four count constants that had drifted after PR #626 (13 slash-command agents, 15 `AGENT_DIRECTORIES` entries).
- **Auth test fixtures aligned with the hardened HTTP transport** introduced in `Harden SaaS auth and restore build sync emission`. Tests for `AuthorizationCodeFlow`, `TokenRefreshFlow`, `WebSocketTokenProvisioner`, and the browser-login/refresh-transport integration paths now patch `PublicHttpClient` in each flow module's own namespace (matching the production call graph) instead of raw `httpx.AsyncClient`. Network-error paths raise `NetworkError` from the client mock rather than `httpx.ConnectError` to match the new `except NetworkError` contract.
- **`ResolutionTier` unified across `doctrine.resolver` and `specify_cli.runtime.resolver`**. `specify_cli.runtime.resolver` is now a thin re-export shim, as its own docstring had claimed. Tests assert tier equivalence via `.name` to stay robust against `pytestarch`'s filesystem-walk loader, which can load the same source file under alternate module names during `pytest --import-mode=importlib`.
- **Post-`unified-charter-bundle-chokepoint` test fixture hardening**: three pre-existing tests (`test_local_support_declarations_end_to_end`, `test_template_prompt_bootstrap_context_first_load`, `test_all_pass_with_healthy_setup`) now `git init` their tmp directories to satisfy the new `resolve_canonical_repo_root` precondition that calls `git rev-parse --git-common-dir`.
- **Codex / Vibe agent skills migration test alignment**: five tests that pre-dated mission 083 were updated to assert the new `.agents/skills/spec-kitty.<cmd>/SKILL.md` layout rather than the retired `.codex/prompts/` layout. Invariants preserved (direct `spec-kitty agent action` CLI calls, per-agent argument handling, agent assets generation); only the probe path changed to match the post-083 architecture.
- **Contract handoff fixture** updated to include `BuildRegistered` and `BuildHeartbeat` event types added on the emitter side by the SaaS-auth hardening.
- **Miscellaneous tails**: redacted a dev-machine path literal in an architecture review doc (caught by `test_command_template_cleanliness`); fixed `test_rewrite_shims.py::test_result_counts` to use two slash-command agents since codex is no longer one; marked `test_home_unit.py::TestGetKittifyHomeWindows::test_windows_default_path` `windows_ci` since DRIFT-3 of the Windows Compatibility Hardening mission made `get_kittify_home()` delegate to `specify_cli.paths.get_runtime_root().base`, which the monkeypatch-based simulation no longer drives reliably on non-Windows runners.
- **Kiro regenerated baselines** for all 12 canonical commands, closing the `tests/specify_cli/regression/test_twelve_agent_parity.py` baseline-missing cluster introduced by PR #626.

### Added

- **Unified charter bundle manifest v1.0.0** at `src/charter/bundle.py` declaring the three `sync()`-produced derivatives (`governance.yaml`, `directives.yaml`, `metadata.yaml`) as the authoritative bundle contract. `references.yaml` and `context-state.json` are explicitly out of v1.0.0 scope; they are produced by other pipelines.
- **Canonical-root resolver** at `src/charter/resolution.py` (`resolve_canonical_repo_root()`). Readers running inside a git worktree now transparently observe the main-checkout charter bundle without per-worktree materialisation. Closes Priivacy-ai/spec-kitty#339.
- **`spec-kitty charter bundle validate [--json]`** CLI surface for operator and CI bundle-health checks.
- **Migration `m_3_2_3_unified_bundle`** advances 3.x projects to the unified bundle layout. On a populated project it validates the bundle against the v1.0.0 manifest, invokes `ensure_charter_bundle_fresh()` to regenerate any missing derivatives, and emits a structured JSON report (see `kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/migration-report.schema.json`). Idempotent - the second apply against an already-upgraded project is a clean no-op. Refs Priivacy-ai/spec-kitty#464, #479.

### Changed

- **`SyncResult` extended with `canonical_root: Path`** - `files_written` remains a list of file names relative to `canonical_root / .kittify/charter/`. Existing readers were rewired in lockstep; no compatibility shim.
- **`ensure_charter_bundle_fresh()` is now the sole chokepoint** for readers of `governance.yaml`, `directives.yaml`, and `metadata.yaml`. Direct reads of those files are forbidden and are enforced by an AST-walk coverage test (`tests/charter/test_chokepoint_coverage.py`). Refs Priivacy-ai/spec-kitty#461, #464.

### Unchanged (explicitly)

- **`.kittify/memory/` and `.kittify/AGENTS.md` symlinks in worktrees** remain as-is - they provide project-memory and agent-instructions sharing, documented-intentional per `src/specify_cli/templates/AGENTS.md:168-179`. They are NOT part of the charter bundle; the canonical-root resolver fixes the worktree charter-visibility story without touching `src/specify_cli/core/worktree.py` (C-011).
- **Files under `.kittify/charter/` that are not v1.0.0 manifest files** (`references.yaml`, `context-state.json`, `interview/answers.yaml`, `library/*.md`) are unchanged. The migration lists them under `bundle_validation.unexpected` for operator visibility but does not delete, move, or rewrite them (C-012).
- **Project `.gitignore` is not reconciled** by the migration. The v1.0.0 manifest's required entries already match the repository `.gitignore` verbatim; the migration performs no read or write against `.gitignore` (D-12).

### Refs

- EPIC: Priivacy-ai/spec-kitty#461 (Charter as Synthesis & doctrine reference graph).
- Phase 2 tracking: Priivacy-ai/spec-kitty#464.
- Closes on merge: Priivacy-ai/spec-kitty#339, #451.

### Fixed

- **`mission merge` no longer silently loses content when the repository carries legacy sparse-checkout state** - the stash/merge/stash-pop cascade used by the merge driver previously recorded phantom deletions for paths filtered out by a sparse-checkout pattern, and the subsequent housekeeping commit silently reverted content the preceding merge had introduced. Merge and `agent action implement` now run a sparse-checkout preflight and fail closed unless the operator passes `--allow-sparse-checkout`, `safe_commit` now aborts commits whose staging area contains paths outside the intended scope, and `mission merge` performs a post-merge refresh and invariant check before leaving the integration branch. Closes Priivacy-ai/spec-kitty#588.
- **`move-task --to approved` and `--to planned` on a lane-worktree review no longer require `--force` when the only untracked content is `.spec-kitty/`** - the review-lock uncommitted-changes guard now treats the execution lane's own `.spec-kitty/` scratch directory as expected content rather than an unexplained untracked path, so operators stop being trained to pass `--force` reflexively. Closes Priivacy-ai/spec-kitty#589.
- **Retry guidance emitted by the uncommitted-changes guard now names the actual target lane** rather than hardcoded `for_review`, so operators see the transition they were attempting instead of a misleading default.

### Added

- **`spec-kitty doctor sparse-checkout --fix`** - detection and one-command migration for repositories upgraded from pre-3.0 spec-kitty that still carry `core.sparseCheckout=true` and a `.git/info/sparse-checkout` pattern file. The fix removes the git-config entry, clears the pattern file, and verifies post-fix state.
- **`--allow-sparse-checkout` flag on `mission merge` and `agent action implement`** - explicit escape hatch for users with intentional sparse configurations. Use of the flag emits a `WARNING`-level structured log record (`spec_kitty.override.sparse_checkout`) at the CLI layer. Durable cross-repo audit event support is tracked as Priivacy-ai/spec-kitty#617.
- **Commit-time backstop inside `safe_commit`** - fail-closed check that aborts commits whose staging area contains paths outside the intended scope, independent of the preflight. This is the universal defence that catches sparse-stash-pop phantom-deletion cascades regardless of which command initiated them.
- **Per-worktree `.spec-kitty/` exclude entry** - every lane worktree now receives a local git exclude entry for `.spec-kitty/` at worktree creation, so lane scratch content stays invisible to the working-tree guard even in worktrees initialised before the fix.
- **Session-scoped sparse-checkout warning** at review-lock and task-command entry points - surfaces detected legacy sparse-checkout state once per process before an operator wastes a commit cycle, without blocking.
- **ADR `2026-04-14-1-sparse-checkout-defense-in-depth`** - documents the four-layer hybrid defence (merge/implement preflight, `safe_commit` backstop, session warning, `doctor --fix`) and the alternatives considered.

### Recovery for users already affected

If a prior `mission merge` landed on your target branch with a silent content
reversion (symptoms: a follow-up `chore: record done transitions` commit that
deleted content merged in the preceding commit), restore the content from the
merge commit that introduced it:

```bash
# Identify the merge commit
git log --merges --oneline -- <affected-file>

# Restore content from that merge
git checkout <merge-sha> -- <affected-file> [...]

# Commit the restoration
git add <affected-file> [...]
git commit -m "fix: restore content reverted by phantom-deletion bug"
```

Then run the migration to prevent recurrence:

```bash
spec-kitty doctor sparse-checkout --fix
```

Root-cause diagnostic trail: [Priivacy-ai/spec-kitty#588 (comment)](https://github.com/Priivacy-ai/spec-kitty/issues/588#issuecomment-4242179946).

## [3.1.2a4] - 2026-04-14

### Added

- **Kiro CLI as first-class agent** - `spec-kitty init --ai kiro` registers the Kiro CLI (Amazon Q Developer CLI's rebrand) with its own `.kiro/prompts/` directory and `kiro-cli` binary check. Legacy `--ai q` (→ `.amazonq/prompts/`) remains supported for backwards compatibility. README and `docs/reference/supported-agents.md` now document the shell-quoting requirement for `$ARGUMENTS` pass-through (see kirodotdev/Kiro#4141). Closes #246.

### Fixed

- **`diff-coverage` CI job no longer fails with "no merge base"** - the base-branch fetch was passing `--depth=1` after `actions/checkout@v6` had already fetched full history, which truncated `origin/<base>` back to a single commit and broke `diff-cover`'s merge-base computation. Dropped `--depth=1`.
- **`test_mission_v1_guards_unit.py::test_registry_keys` now matches the guard registry** - synchronised the `EXPECTED_GUARDS` set with the `occurrence_map_complete` guard added in #616.

## [3.1.2a3] - 2026-04-12

### Fixed

- **Merge-time numbering lock and retry safety** - `mission_number` assignment now acquires a file lock before scanning existing prefixes, MergeState uses `mission_id` as its canonical key, and interrupted merges no longer risk duplicate or skipped numbers on retry. Closes #601.
- **CLI no longer hangs 15–20 min when offline queue is full and session expired** - the offline queue drain path now respects a bounded timeout instead of blocking indefinitely on expired-session retries. Closes #598, #602.
- **Sonar readiness and parser findings addressed** - actionable maintenance issues flagged by SonarCloud (code smells, complexity, minor bugs) are resolved. Closes #599, #600.

## [3.1.2a2] - 2026-04-11

### Added

- **Hosted readiness control surfaces** - the CLI now exposes the canonical SaaS rollout/readiness module, a six-state hosted readiness evaluator, and a background-daemon policy/intent model that keeps stealth rollout behavior explicit while making enabled-mode failures actionable.

### Changed

- **Tracker command classification is corrected for first-run flows** - `tracker discover` no longer requires an existing mission binding, `tracker providers` remains available as static output without hosted prerequisites, and hosted/manual-daemon checks are applied according to command intent rather than indiscriminately.
- **Tracker dependency advances to the hardened hosted-discovery release line** - the CLI now targets `spec-kitty-tracker==0.4.1`, aligning the prerelease with the published runtime validation and canonical discovery contract shipped in the tracker SDK.

### Fixed

- **Background-daemon policy no longer blocks local-provider sync flows** - local tracker providers continue to execute direct sync operations even when hosted SaaS daemon startup is set to manual.

## [3.1.2a1] - 2026-04-10

### Added

- **Browser-mediated CLI auth preview** - `spec-kitty auth login` now supports browser-based OAuth with Device Authorization Flow fallback, centralized token management, secure storage, and WebSocket token provisioning against the SaaS contract.

### Changed

- **Human CLI auth now flows through the new auth subsystem** - HTTP transport, sync runtime, and tracker SaaS callers now refresh through the shared token manager instead of the legacy password/JWT credential path.

### Fixed

- **Browser auth CI coverage gaps** - test dependencies and stale tracker refresh patch targets were corrected so the new auth stack passes the core and integration suites reliably in CI.

## [3.1.1] - 2026-04-09

### Added

- **Semantic status-event merge driver** - `kitty-specs/**/status.events.jsonl` now uses a Spec Kitty merge driver that unions append-only event logs by `event_id`, rejects conflicting payloads, and fails closed when merged WPs do not reach `done` in the canonical event log.
- **Forward-safe mission identity** - newly created missions now mint a ULID `mission_id` at creation time, persist it to `meta.json`, and emit it through mission-created event payloads.
- **Release hygiene guardrail** - release validation now enforces `pyproject.toml` and `.kittify/metadata.yaml` version sync before a cut can proceed.

### Changed

- **`spec-kitty init` now produces a minimal file scaffold** - init no longer initializes git, creates bootstrap commits, or seeds `.agents/skills/`. The generated next steps now point users at `spec-kitty next` plus `spec-kitty agent action implement/review` as the canonical workflow.
- **Planning-artifact WPs are first-class lane-owned items** - the canonical planning lane is now `lane-planning`, and it resolves to the main repository checkout instead of an ad hoc special-case path.
- **Top-level `implement` is de-emphasized** - onboarding and command docs now treat `spec-kitty implement` as internal infrastructure rather than the primary user-facing flow.

### Fixed

- **Merge conflict recovery for `status.events.jsonl`** - append-only status events are no longer silently dropped during merge conflict resolution, and fresh repositories now self-heal the local git merge-driver config when running merge flows. Closes #574.
- **Planning/query consistency after PR #555** - mixed planning/code review-context resolution no longer crashes when a dependency resolves to the repo-root workspace, and fresh-run query mode now returns `run_id: null` instead of leaking a deleted temporary run id.
- **Dependency parser trailing-prose bleed** - the final WP section is now bounded at non-WP `##` headings so trailing prose does not get misread as dependency declarations.
- **Concurrent auth refresh race** - stale 401 responses during token rotation no longer wipe valid shared credentials from active CLI sessions.

## [3.1.1a3] - 2026-04-07

### Added

- **Global slash command installation** - all 16 spec-kitty slash commands are now installed globally to `~/.<agent-dir>/` (e.g. `~/.claude/commands/`, `~/.gemini/commands/`, `~/.codex/prompts/`, etc.) at every CLI startup, for all 13 supported agents. No `spec-kitty init` or per-project `spec-kitty upgrade` is required for commands to be available. Commands update automatically when the CLI is upgraded.
- **Migration `3.1.2_globalize_commands`** - removes existing per-project `spec-kitty.*` command files from `.claude/commands/`, `.gemini/commands/`, and equivalent directories in all configured agents. Runs automatically on `spec-kitty upgrade`.
- **ADR `2026-04-07-1-global-slash-command-installation`** - documents the decision to install commands globally, the full 13-agent table with global roots, and the rationale.

### Changed

- `spec-kitty init` no longer writes per-project command files. Commands are managed exclusively by the global startup hook.

## [3.1.1a2] - 2026-04-07

### Fixed

- **`spec-kitty init` / any CLI command no longer dirties the git repo** - every CLI invocation that touched status was unconditionally rewriting `kitty-specs/*/status.json`, even when nothing had changed, leaving ~60 files modified in `git status`. Root cause: `materialize()` stamped a fresh `datetime.now(UTC)` into `materialized_at` on every call. Fixed in `reducer.py` (3.1.1a1): `materialized_at` is now derived deterministically from the last event's `at` timestamp (or `""` for features with no events), and a content-equality guard skips the write when the file is already up to date. Closes #524.

### Added

- **Migration `3.1.1_normalize_status_json`** - one-shot upgrade migration that normalises all existing `kitty-specs/*/status.json` files to the new deterministic format. Runs automatically on `spec-kitty upgrade` for any project where the committed files still carry old wall-clock timestamps or the legacy `feature_slug` field. After the migration the skip-write guard in `materialize()` keeps all status snapshots stable indefinitely.

### Changed

- **`StatusSnapshot` and `ProgressResult` serialisation no longer emits `feature_slug`** - `with_tracked_mission_slug_aliases` previously injected a redundant `feature_slug` alias into every serialised snapshot. Now only `mission_slug` is written. Reading still accepts both keys for backward compat with existing files.

## [3.1.1a1] - 2026-04-07

### Added

- **Typed `WPMetadata` Pydantic model** (`src/specify_cli/status/wp_metadata.py`) - immutable, validated work package metadata with `update()` builder API; replaces all raw `frontmatter.get()` dict access across consumer files. Closes #410.
- **`Lane` enum state machine** - valid lane transitions enforced at the type level; all runtime consumers migrated from string comparisons to `Lane` enum values.
- **Typed dashboard API contracts** (`src/specify_cli/dashboard/handlers/api.py`) - Pydantic response models replace untyped dicts.
- **RE2 shim** (`src/kernel/_safe_re.py`) - `types.ModuleType`-based shim backed by `google-re2`; exposes the full `re` API and mitigates Sonar DOS hotspot findings. `google-re2>=1.1` added as a core runtime dependency.
- **CI status-layer test stages** - new `fast-tests-status` and `integration-tests-status` jobs run the `tests/status/` and `tests/specify_cli/status/` suites in parallel with existing core/doctrine jobs; their coverage outputs feed the `diff-coverage` gate.
- **`WPMetadata.display_title` property** - safe fallback for missing or empty WP titles.

### Changed

- All `frontmatter.get()` calls outside `frontmatter.py` migrated to typed `WPMetadata` access. Migration scripts retain raw dict access annotated `# MIGRATION-ONLY`.
- `WPMetadata.title` is now optional; WP read errors propagate gracefully via `read_wp_frontmatter()`.
- `OwnershipManifest.from_frontmatter()` accepts `WPMetadata` directly.
- `diff-coverage` job wired to consume `coverage-kernel.xml`, `coverage-fast-status.xml`, and `coverage-integration-status.xml` in both enforced (critical-path 90%) and advisory (full-diff) steps.
- GitHub Actions upgraded to Node.js 24 compatible versions (`actions/checkout@v6`, `actions/setup-python@v6`, `actions/setup-node@v6`, `actions/upload-artifact@v7`, `actions/download-artifact@v8`) across all workflow files.

### Fixed

- `ValidationError` caught in phase-1 status mirror (`status/emit.py`) - prevents NoneType crashes on malformed WP files.
- Ruff and mypy violations cleaned up in all files touched by the migration.
- Sonar false-positive NOSONAR suppressions added in `arbiter.py` and `dashboard/handlers/api.py`.
- WP03 validation report (mission 068) decision corrected from `close_with_evidence` to `tighten_workflow` to reflect the CI logic additions; `test_tighten_workflow_passes_large_pr_sample` implemented to verify the advisory-only contract.

## [3.1.0] - 2026-04-07

### Added

- **Planning pipeline integrity (mission 069)** - four structural fixes eliminating fragilities discovered during mission 068:
  - **Dirty-git reads fix (WP01)** - `materialize()` now derives `materialized_at` from the last event timestamp (deterministic) and skips the write when content is byte-identical. `materialize_if_stale()` returns a read-only `reduce()` call. All read-only commands leave zero modified files in `git status`. Fixes #524.
  - **Structured WP manifest - `wps.yaml` (WP02, WP03, WP04)** - new `src/specify_cli/core/wps_manifest.py` with Pydantic model, YAML loader, and `generate_tasks_md_from_manifest()`. JSON Schema at `src/specify_cli/schemas/wps.schema.json`. When `wps.yaml` is present, `finalize-tasks` derives dependencies exclusively from the manifest; `tasks.md` is regenerated as a derived artifact. `/spec-kitty.tasks-outline` and `/spec-kitty.tasks-packages` templates updated to produce/consume `wps.yaml`. Migration `m_3_2_0_update_planning_templates` propagates changes to existing installations. Fixes #525.
  - **`spec-kitty next` query mode (WP05)** - bare `spec-kitty next` (no `--result`) enters query mode: returns current step with `[QUERY - no result provided, state not advanced]` prefix without advancing the state machine. Prevents ghost completions when agents call `next` while disoriented. Fixes #526.
  - **Slug validator digit-prefix support (WP06)** - `KEBAB_CASE_PATTERN` updated to accept `NNN-*` slugs following spec-kitty's own naming convention. Fixes #527.

## [3.1.0a8] - 2026-04-07

### Added

- **Post-merge reliability and release hardening (mission 068)** - 5 work packages closing the workflow-stabilization track:
  - **Stale-assertion analyzer (WP01)** - new `src/specify_cli/post_merge/` package: stdlib `ast`-based tool that detects test assertions likely invalidated by merged source changes. CLI: `spec-kitty agent tests stale-check --base <ref> --head <ref> [--json]`. Integrated into the merge runner. No new dependencies, no network calls.
  - **Merge strategy + safe-commit + linear-history hint (WP02)** - `MergeStrategy` enum (MERGE/SQUASH/REBASE) in new `src/specify_cli/merge/config.py` with `--strategy` CLI flag (resolves: flag → `.kittify/config.yaml` → squash default). `safe_commit()` called after `_mark_wp_merged_done` before worktree removal (FR-019). Linear-history rejection hint guides users past protected-branch push failures. Closes #456.
  - **Diff-coverage policy validation (WP03)** - validation report confirms the enforce/advisory split already satisfies the policy intent. CI step names tightened to `diff-coverage (critical-path, enforced)` and `diff-coverage (full-diff, advisory)`. Closes #455.
  - **Release-prep CLI (WP04)** - new `src/specify_cli/release/` package: `propose_version()`, `build_changelog_block()`, `ReleasePrepPayload`. CLI: `spec-kitty agent release prep --channel {alpha,beta,stable} [--json]`. Zero network calls. Closes #457.
  - **Recovery extension + mission close (WP05)** - `scan_recovery_state()` extended with `consult_status_events=True` to detect merged-and-deleted WPs via event log; new `RecoveryState.ready_to_start_from_target` field. `spec-kitty implement` gains `--base <ref>` flag for explicit worktree branching. Closes #415.

### Fixed

- **`implement --base` Typer pattern** - changed to Annotated pattern, fixing test isolation failures where direct Python calls received `OptionInfo` objects instead of `None`
- **`implement` console capsys isolation** - `_json_safe_output` wrapper now resets `console._file = None` in `finally` to prevent "I/O operation on closed file" when tests run in sequence with pytest capsys
- **Replay parity test** - corrected `reduced.mission_key == "replay-mission"` (was wrong field name and wrong value)

## [3.1.0a7] - 2026-04-06

### Added

- **Runtime recovery and audit safety (mission 067)** -- 6 work packages delivering resilience and audit infrastructure:
  - **Merge resume recovery (WP01)** -- `spec-kitty merge --resume` recovers from interrupted merges with persistent state tracking in `.kittify/merge-state.json`
  - **Implementation crash recovery (WP02)** -- `spec-kitty implement --recover` restores execution context after agent crashes, rebuilding worktree state and resuming from last known checkpoint
  - **Stale-claim doctor checks (WP03)** -- `spec-kitty doctor` detects orphaned claims, stale locks, and zombie worktrees with structured diagnostic output
  - **Audit-mode scope relaxation (WP04)** -- ownership validation supports `scope: codebase-wide` for audit/cutover WPs; new `validate_audit_coverage()` warns on uncovered audit targets
  - **Shim-to-canonical migration (WP05)** -- all `spec-kitty agent shim <action>` calls replaced with direct `spec-kitty agent action <action>` across 48 agent command files
  - **Finalize-tasks audit wiring (WP06)** -- `validate_audit_coverage()` integrated into finalize-tasks ownership validation pipeline as a soft warning check

### Fixed

- **Agent command files** -- regenerated all 48 agent command files to use canonical `spec-kitty agent action` instead of deprecated `spec-kitty agent shim`
- **Post-merge test regressions** -- fixed 4 stale test assertions after mission 067 merge (implement template content, merge resume behavior, --recover flag default)

## [3.1.0a6] - 2026-04-06

### Added

- **Review loop stabilization (mission 066)** - new `src/specify_cli/review/` module with 6 submodules:
  - `artifacts.py` - persisted review-cycle artifacts at `kitty-specs/<mission>/tasks/<WP-slug>/review-cycle-{N}.md` with YAML frontmatter. Replaces ephemeral `.git/spec-kitty/feedback/` storage. Backward-compatible `feedback://` pointer resolution retained (#432, #433).
  - `fix_prompt.py` - focused fix-mode prompt generation from review-cycle artifacts. Rejected WPs get ~40-line targeted prompts instead of replaying 400-500 line full WP prompts (#430).
  - `dirty_classifier.py` - dirty-state classification for review handoff. Partitions `git status --porcelain` output into blocking (WP-owned files) vs benign (status artifacts, other WP files, metadata). External reviewers no longer need `--force` for unrelated dirtiness (#439).
  - `baseline.py` - baseline test capture at implement time via `pytest --junitxml` + JUnit XML parsing. Review prompts include "Baseline Context" section distinguishing pre-existing failures from regressions. Configurable `review.test_command` for non-pytest projects (#444).
  - `lock.py` - concurrent review serialization via `.spec-kitty/review-lock.json`. Stale lock detection via PID check. Opt-in env-var isolation for projects that configure `review.concurrent_isolation` in config.yaml (#440).
  - `arbiter.py` - structured arbiter checklist with 5 standard rationale categories (pre-existing failure, wrong context, cross-scope, infra/environmental, custom). Override detection on forward `--force` from planned after rejection event. Decisions persisted in review-cycle artifact frontmatter (#441).
- **147 new tests** across the review module (avg 93% coverage, range 91-99%)
- **Implement-review skill update** - parallel sprint pattern, merge/conflict resolution guide, dead-code detection warning, post-merge validation steps
- **Tasks template handoff** - `/spec-kitty.tasks` now offers to invoke `/spec-kitty-implement-review` skill at completion for automated full-sprint execution

### Fixed

- **ReviewLock wired into live command path** - `ReviewLock.acquire()` called in `workflow.py review()` after workspace resolution; `ReviewLock.release()` called in `tasks.py move-task` on review completion
- **Removed dead `wp_prompt_path` parameter** from `generate_fix_prompt()` and all callers

## [3.1.0a5] - 2026-04-06

### Fixed

- **Dependency parsing in finalize-tasks** - new shared parser (`core/dependency_parser.py`) recognizes inline, colon-header, and bullet-list dependency formats. Both `agent mission finalize-tasks` and `agent tasks finalize-tasks` use the same parser. Non-empty disagreement between tasks.md and WP frontmatter triggers a diagnostic error instead of silently overwriting (#406).
- **validate-only is genuinely non-mutating** - all file writes gated behind `if not validate_only`. JSON output reports `would_modify`/`unchanged`/`preserved` without touching disk (#417).
- **Lane computation completeness** - every executable WP must appear in `lanes.json` or lane computation fails with a diagnostic error. Missing ownership manifests are a hard failure. Planning-artifact WPs surfaced in diagnostic summary. Zero-match globs and `src/**` fallback emit warnings (#422).
- **Parallelism collapse reporting** - new `CollapseReport` records every union-find merge with rule name and evidence. Rule 3 (surface heuristics) now gated on `_are_disjoint()` - WPs with provably disjoint owned files are not collapsed by keyword matches alone (#423).
- **Pipe-table mark-status support** - column-aware parser recognizes `[P]` in Parallel column (not corrupted), updates Status column or appends one. Checkbox format remains canonical for new generation (#438).
- **Agent command guidance** - all error messages, shim templates, and command-template examples now use `--mission` consistently. Five `require_explicit_feature()` callers fixed from `--feature` to `--mission`. Error messages include complete copy-pasteable example commands (#434).
- **Full --feature → --mission sweep** - 12 typer.Option declarations, 4 argparse declarations, 11 error messages, and 5 docstrings updated. `--mission` is the primary displayed flag name; `--feature` retained as hidden backward-compatibility alias (#448).

### Added

- `src/specify_cli/core/dependency_parser.py` - canonical shared dependency parser
- `CollapseEvent` and `CollapseReport` data models in `lanes/models.py`
- `LaneComputationError` exception for diagnostic lane failures
- `validate_glob_matches()` in ownership validation
- `planning_artifact_wps` field on `LanesManifest`
- Charter regression vigilance rules for `--mission` terminology canon

## [3.1.0a4] - 2026-04-06

### Fixed

- **Mission-era host surface cleanup** - removed remaining feature-era host command references from shipped templates, agent-facing prompts, and smoke-test scaffolding so new missions no longer regenerate `create-feature`, `feature_slug`, or `--feature` guidance on canonical paths.
- **Runtime mission metadata normalization** - mission resolution now prefers canonical `mission_type` metadata and rehydrates mission identity consistently in diagnostics, verification, and rebuild-state migrations.
- **Release-readiness regressions after host cutover** - updated cross-cutting, orchestrator, parity, body-sync, gitignore-isolation, and e2e smoke coverage to validate the mission-era CLI and contract instead of the removed feature-era host surface.

## [3.1.0a3] - 2026-04-05

### Fixed

- **Doctrine artifact discovery in subdirectories** - all 7 doctrine repositories now use `rglob()` instead of `glob()`, so artifacts in subdirectories of `shipped/` are no longer silently skipped (#396).
- **Dashboard `/api/features` empty response** - `StatusEvent.from_dict()` now accepts both `feature_slug` and `mission_slug` field names and normalizes the legacy `in_review` lane to `for_review`.
- **Stale `patch()` targets caught at lint time** - new `scripts/check_patch_targets.py` validates every `@patch()` target string resolves, added as an `[ENFORCED]` CI lint step (#394).
- **Architectural layer coverage guards** - meta-tests fail when a `src/` package has no layer assignment or a defined layer matches no module (#395).
- **Sonar reliability bugs** - resolved 7 findings: unreachable code (S1763), identical branches (S3923), premature async task GC (S7502), always-true condition (S2583), tautological assertion (S3981), CSS shorthand override (S4657), parameter shadowing (S1226).
- **Async task GC in event emitter** - `asyncio.ensure_future()` results held in `_pending_tasks` set with done-callback cleanup, preventing premature garbage collection.
- **`check-readiness` CI gate unblocked** - post-release version bump missed after tagging v3.1.0a2 (#408).

### Changed

- **CI test parallelization** - `fast-tests` and `integration-tests` split into `doctrine` + `core` phases running in parallel (#397).
- **`--mission-run` as canonical CLI flag** - added as alias for `--feature` across all CLI commands. `--feature` remains accepted as legacy alias.
- **Node.js 20 → 22** in CI workflows (current LTS).
- **Mutation testing CI job disabled** - too slow to run reliably.
- **Ruff max line length** increased from 120 to 164.
- **Defunct `tests/legacy` references removed**.

### Added

- **RTK search tooling toolguide** - new shipped doctrine artifact documenting RTK interception patterns and correct search tooling for worktree sessions.
- **`last_updated` field** on Toolguide model and schema.
- **Integration tests for nested artifact discovery** - 281-line test suite covering all 8 doctrine repository types.
- **`integration` pytest marker** registered in `pyproject.toml`.

## [3.1.0a2] - 2026-04-05

### Changed

- **Prerelease publishing is now first-class** - tag-mode release validation accepts matching prerelease tags such as `v3.1.0a0`, GitHub Releases are marked as prereleases automatically for those tags, and maintainer docs now document the end-to-end prerelease PyPI/GitHub publish path.
- **Rebased doctrine-stack work onto `main`'s execution architecture** - carry forward the doctrine, constitution, and template-repository work from PR #305 into PR #348 while preserving `main`'s context, ownership, event-log, merge-engine, and shim foundations instead of reviving deleted subsystems.
- **Kernel established as the shared dependency floor** - `src/kernel/` now owns shared path, atomic-write, and glossary-boundary primitives; doctrine no longer reaches back into `specify_cli`, and the package boundary is documented by ADRs and enforced by architectural tests.
- **Constitution now acts as the local routing layer for governance assets** - project-local mission path construction flows through `ProjectMissionPaths`, while doctrine-backed mission/template access is routed through `MissionTemplateRepository` and constitution-facing resolvers instead of scattered path assembly.
- **Mission terminology split clarified as the architectural answer to issue #241** - a direct `--feature` → `--mission` rename would have collided with the existing mission-type concept, so the branch now separates `mission type` (`--mission-type`) from `mission run` (`--mission-run`) and keeps legacy `--feature` compatibility where required during the deprecation window.
- **CI flows extended for the new package layout** - quality workflows now cover doctrine and kernel explicitly, including dedicated kernel coverage enforcement and updated readiness/release paths.
- **Fork-safe SonarCloud targeting via repository variables** - CI now resolves SonarCloud settings from `SONAR_ORGANIZATION`, `SONAR_PROJECT_KEY`, and optional `SONAR_HOST_URL`, with upstream-safe defaults and a fallback project-key convention of `<organization>_<repo-name>` when `SONAR_PROJECT_KEY` is unset.

### Fixed

- **Dashboard loading regressions on shared mission installs** - repaired the shared dashboard JavaScript syntax error, made feature scanning tolerate unreadable legacy event logs, hardened `/api/features` error handling, and marked the scanner regressions as part of the `fast` suite so CI/Sonar coverage reflects the new branches.
- **Narrow exception handlers in doctrine repositories** - Replace 21 bare `except Exception` handlers across `src/doctrine/` with specific exception tuples (`YAMLError`, `ValidationError`, `OSError`, `ModuleNotFoundError`, `TypeError`, `UnicodeDecodeError`) matching actual failure modes. Addresses PR #305 review finding M1.
- **Fix `spec-kitty --help` crash** - Add missing `Optional` import to `workflow.py` and `tasks.py`. `from __future__ import annotations` defers annotation evaluation; Typer's `eval()` of `Optional[str]` annotations raised `NameError` at app construction time.
- **Address PR #305 architectural review gaps in the rebased branch** - resolve the core review findings by removing doctrine→`specify_cli` dependency leakage, bringing doctrine into CI coverage, lifting shared glossary/path primitives into kernel, and documenting the resulting boundary in the architecture corpus.

### Documentation

- **Doctrine inclusion assessment** - `docs/development/doctrine-inclusion-assessment.md` evaluates the current state of the three Doctrine+Kitty merger pillars (agent profiles ~80%, mission type customization ~45%, ad-hoc experimentation ~25%) with gap analysis, dependency violation status, and phased recommendations.
- **Doctrine skills README** - `src/doctrine/skills/README.md` documents the skills-vs-mission-composition boundary, the iterative context loading pattern, and the skill inventory. Captures the architectural distinction from the PR #305 review.
- **Updated skill: spec-kitty-runtime-next** - new "Doctrine-Aware Step Execution" section teaches agents to load agent profiles at init, apply action-scoped constitution context at step boundaries, and pull specific tactics/directives on demand instead of dumping all doctrine upfront.
- **Updated skill: spec-kitty-constitution-doctrine** - new "Programmatic Doctrine Access", "Doctrine Artifact Kinds", and "Iterative Context Loading Pattern" sections document `DoctrineService` entry points, explain all 8 artifact kinds (directives, tactics, paradigms, styleguides, toolguides, procedures, agent profiles, step contracts) with access patterns, and teach the anti-pattern of upfront context dumps.
- **Updated skill: spec-kitty-mission-system** - new "Doctrine Composition Layer" section documents `MissionStepContract`, `Procedure`, and action index artifacts as the structured primitives backing mission behavior.
- **New skill: ad-hoc-profile-load** - teaches agents how to load a profile on demand for interactive sessions outside the mission loop: resolve by ID or task context, adopt identity/boundaries/governance scope, maintain role throughout the session, and persist to tool context.
- **Recorded the remaining follow-on work after the PR #305 -> PR #348 transition** - the compiler-backed mission-bundle follow-up remains relevant, the skills-vs-mission-composition boundary still needs to stay explicit, constitution-local routing should expand beyond mission-path centralization, issue #241 still has compatibility/documentation cleanup left on older `--feature`-based surfaces, and residual runtime/test debt remains outside this rebase-focused integration.

## [3.0.3] - 2026-04-01

### Added

- **Ticket-first mission origin binding** (feature 061): Service-layer workflow for starting a mission from an existing Jira or Linear ticket. Adds `search_origin_candidates()`, `bind_mission_origin()`, and `start_mission_from_ticket()` in `tracker/origin.py`. Persists durable `origin_ticket` provenance in `meta.json` with 7-field validation. Emits `MissionOriginBound` observational telemetry event. SaaS-first write ordering ensures local metadata never runs ahead of the authoritative control plane.
- **Reusable feature-creation API**: Extracted `create_feature_core()` from the CLI command into `core/feature_creation.py` - a stable, programmatic API returning `FeatureCreationResult` with domain exceptions instead of `typer.Exit()`.
- **SaaS tracker client extensions**: `search_issues()` and `bind_mission_origin()` transport methods on `SaaSTrackerClient` with full retry, auth refresh, and error handling.

## [3.0.2] - 2026-04-01

### Fixed

- **Missing prompt-driven slash commands**: `rewrite_agent_shims()` (3.0.0 migration step 6) deleted 9 prompt-driven template files (specify, plan, tasks, etc.) leaving only 7 CLI shims. Now regenerates all 16 command files per the hybrid architecture (feature 058). Added `m_3_0_2` migration to restore prompt files for already-affected projects.
- **Event log not created at feature birth**: `status.events.jsonl` was only bootstrapped during `finalize-tasks`, causing `CanonicalStatusNotFoundError` when the dashboard scanned features in the specify/plan phase. Now initialized when `create-feature` runs.
- **Dashboard scanner crash on pre-finalization features**: `_count_wps_by_lane()` and `_process_wp_file()` propagate `CanonicalStatusNotFoundError` (hard-fail contract); callers `scan_all_features()` and `scan_feature_kanban()` catch at feature level with actionable error messages.
- **Stale `/spec-kitty.clarify` references**: Removed 14 remaining references to the deleted clarify command across kitty-specs checklists, coverage tables, and `pyproject.toml`.
- **Missing `.gitignore` entries**: Added `.kittify/workspaces/` and `.kittify/merge-state.json` to match `state_contract.py` expectations.

## [3.0.1] - 2026-03-31

### Fixed

- **Canonical status hard cutover completed.** Work-package lane state is now consistently sourced from `status.events.jsonl` across active CLI commands, packaged task tooling, templates, docs, and standalone helpers. Frontmatter lane fallbacks and `lane=` body-log writes are removed from active 3.0 flows.
- **Canonical bootstrap and hard-fail behavior hardened.** `finalize-tasks` now seeds canonical `planned` state for generated WPs, while runtime commands fail explicitly when canonical status is missing instead of silently reconstructing it from abandoned frontmatter state.
- **Release automation updated for 3.x.** GitHub release validation, maintainer docs, and workflow tag handling now use semantic `vX.Y.Z` tags generically, so `v3.0.1` publishes correctly to GitHub Releases and PyPI.

## [3.0.0] - 2026-03-30

### Breaking Changes

- **Event log is sole authority for mutable WP state.** Frontmatter `lane`, `review_status`, `reviewed_by`, and `progress` fields are no longer written or read at runtime. Status is read from `status.events.jsonl` via the reducer.
- **`feature_detection.py` deleted.** All commands require explicit `--feature <slug>` in multi-feature repos. No branch scanning, no env var detection, no cwd walking.
- **Legacy worktree file filtering removed.** `planning_artifact` WPs work in-repo; `code_change` WPs use standard full worktrees.
- **Command templates restored as hybrid.** Planning commands (specify, plan, tasks, etc.) install as full prompts; execution commands (implement, review, merge, etc.) install as thin CLI-dispatch shims.

### Added

- **MissionContext** - opaque token-based bound identity for all workflow commands (`src/specify_cli/context/`)
- **WP Ownership Manifest** - `execution_mode`, `owned_files`, `authoritative_surface` per WP (`src/specify_cli/ownership/`)
- **Lane-weighted progress** - `planned=0.0`, `in_progress=0.3`, `for_review=0.6`, `done=1.0` (`src/specify_cli/status/progress.py`)
- **`spec-kitty materialize`** command for CI/debugging regeneration of derived views
- **Dedicated merge workspace** at `.kittify/runtime/merge/` with per-mission state and atomic lock
- **Merge conflict auto-resolution** for event logs (append-merge) and metadata (take-theirs)
- **Thin agent shims** for CLI-driven commands with `spec-kitty agent shim <command>` entrypoints
- **Schema version gate** (disabled until 3.0.0 migration ships to consumers)
- **One-shot migration framework** - `backfill_identity`, `backfill_ownership`, `rebuild_state`, `strip_frontmatter`
- **`--validate-only`** flag on `finalize-tasks`
- **`spec-kitty next`** hint in `tasks status` output
- **Integration Verification** section in WP prompt template
- **Doctor `command-files`** check - detects stale/missing/wrong-type agent command files
- **Version markers** in generated command files (`<!-- spec-kitty-command-version: X.Y.Z -->`)
- **Migration `m_2_1_4`** - unconditionally enforces correct hybrid command file state

### Removed

- `feature_detection.py` (668 lines) - replaced by MissionContext tokens
- `status/legacy_bridge.py`, `status/phase.py`, `status/reconcile.py`, `status/migrate.py`
- `merge/executor.py`, `merge/forecast.py`, `merge/status_resolver.py`
- `core/agent_context.py` - tech-stack parsing no longer needed
- ~56 command template files (replaced by 9 canonical prompts + 7 thin shims)
- Sparse checkout policy enforcement
- Frontmatter lane/review_status read/write throughout codebase
- Dual-write (event log + frontmatter) behavior

### Fixed

- "planning repository" → "project root checkout" terminology (migration included)
- Template path references removed from agent prompts (agents no longer search for `.kittify/missions/` files)
- Workflow `implement`/`review` now emit status events (was silently failing)
- Merge reconciliation marks ALL ancestor WPs as done (not just effective tips)
- `require_explicit_feature()` lists available features in error message
- YAML parse errors in frontmatter now logged as warnings (not silently swallowed)
- Merge engine uses `git reset --hard` on detached HEAD (not `git checkout` which fails when branch is checked out elsewhere)
- Migration backup covers `kitty-specs/` and `.gitignore` (not just `.kittify/`)
- `rebuild_state.py` uses max timestamp (not last file line) for terminal state
- Merge lock uses atomic `open('x')` (not TOCTOU `exists()` + `write_text()`)
- `merge --resume` errors when multiple paused merges exist (not silently picks first)

## [2.1.4] - 2026-03-27

### Added

**Enforce correct command file state**: Version markers and migration to guarantee all agent command files are always in the correct state.

- `<!-- spec-kitty-command-version: X.Y.Z -->` marker added as the first line of every generated command file (both full prompts and thin shims)
- Migration `m_2_1_4_enforce_command_file_state` unconditionally writes all 16 command files per configured agent; idempotent on subsequent runs when version markers match
- `spec-kitty doctor command-files` subcommand checks all agent command files for missing files, stale version markers, and wrong file type (full prompt vs thin shim)

## [2.1.3] - 2026-03-27

### 🐛 Fixed

**Preserve explicit WP args in workflow prompts**: Slash-command arguments passed to `/spec-kitty.implement` and `/spec-kitty.review` are now forwarded into the resolver-first flow instead of being silently dropped. Agents receiving explicit WP selectors (e.g., `WP03`, `--base WP01`) will correctly pass them to `spec-kitty agent context resolve` via `--wp-id` and `--base` flags.

- `implement.md` and `review.md` mission templates now include an `{ARGS}` placeholder with conditional forwarding instructions
- Public slash-command docs updated: `/spec-kitty.implement` documents `[--base WP_ID]` support; `/spec-kitty.review` is now WP-only (removed stale "or prompt path" syntax)
- Regression tests added across Markdown and TOML agent formats to ensure argument placeholders survive rendering

## [2.1.2] - 2026-03-23

### 🔧 Improved

**Skills audit and expansion**: All 6 distributed skills audited, command-verified, and expanded with full architecture documentation. Skills now document internal systems (glossary pipeline, constitution extraction, runtime DAG, git workflow boundary) so agents can operate effectively.

- setup-doctor: Fixed wrong CLI commands (`verify` → `verify-setup`, `status` → `agent tasks status`), added `--remove-orphaned` safety warning
- runtime-review: Added discovery step, `--feature` flags, empty-lane guidance
- glossary-context: Added 5-layer middleware pipeline, extraction methods, checkpoint/resume, step config
- constitution-doctrine: Added extraction rules, governance.yaml schema, interview profiles, answers.yaml schema
- runtime-next: Added decision algorithm, WP iteration logic, 6 guard primitives, agent loop pattern
- orchestrator-api: Added JSON output examples, error code catalog, idempotency behavior, preflight details

### ✨ Added

**2 new skills**: `spec-kitty-mission-system` (explains missions, 4 types, template resolution, guards) and `spec-kitty-git-workflow` (documents Python vs agent git operation boundary).

**Reusable skill update utility**: `src/specify_cli/upgrade/skill_update.py` for finding and patching skill files across all 13 agent skill roots.

**10 upgrade migrations** for consumer projects: 6 skill fixes, 1 release skill removal, 2 new skill installations, 1 glossary skill expansion.

**Documentation parity sprint (Feature 056)**: DocFX build now includes all 4 Divio categories (was only building 1x/ and 2x/). 5 new user guides distilled from skills, 4 existing docs expanded, 22 fact-check corrections across 20 files.

### 🐛 Fixed

**DocFX build gap**: 56 docs files (tutorials, how-to, reference, explanation) were in the repo but excluded from the docs.spec-kitty.ai build. Now included via updated `docfx.json`.

**8-lane state machine documentation**: All docs updated from outdated 4-lane model (planned/doing/for_review/done) to correct 8-lane model (planned/claimed/in_progress/for_review/approved/done/blocked/canceled) with 24 allowed transitions.

**CLI reference completeness**: Added 12 missing commands to cli-commands.md, 7 missing subcommands to agent-subcommands.md. Fixed `spec-kitty sync` (documented as flat command, actually a group with 6 subcommands).

### 🧹 Maintenance

- Removed `release` skill from distribution (spec-kitty development only, not for consumers)
- Removed obsolete `docs/how-to/upgrade-to-0-11-0.md`
- Fixed all cross-reference links in new docs (0 new DocFX build warnings)

## [2.1.1] - 2026-03-21

### 🐛 Fixed

- **Bundled doctrine payload in wheels**: the PyPI wheel now includes the full `doctrine/` package tree, including the canonical skill pack under `doctrine/skills/`, so `spec-kitty init` and `spec-kitty upgrade` can install managed skills for shipped builds.
- **2.1.0 repair migration**: added `2.1.1_repair_skill_pack` so projects that already upgraded on broken `2.1.0` wheels reinstall the canonical managed skill pack on `spec-kitty upgrade`.
- **Release verification guard**: the release workflow now fails if the built wheel omits doctrine files or bundled skills, and distribution tests now assert that a wheel-installed `spec-kitty init` produces the managed skill manifest and installed skill files.

## [2.1.0] - 2026-03-21

### ✅ Added

- **agent skills Pack (`#330`)**: added canonical bundled skills, registry/installer/verification flow, manifest support, and upgrade migration `m_2_0_11_install_skills`.
- **Structured requirement mapping (`#329`)**: added requirement-to-work-package mapping support with CLI integration for tracing delivery intent into execution planning.

### 🔧 Changed

- **Deterministic planning branch intent (`#328`)**: `specify` and `plan` commands now inject explicit target-branch metadata into templates to reduce ambiguity in downstream execution.
- **Primary release line promotion**: `2.x` becomes the stable `main` line, with GitHub Releases and PyPI publication starting at `2.1.0`.

### ⚠️ Deprecated

- **`1.x` overall**: the former `1.x` line is now deprecated and moves to `1.x-maintenance` for critical fixes only. No new `1.x` PyPI releases are planned.

### 🗑️ Removed

- **Public `/spec-kitty.clarify` slash command (`#322`)**: removed the legacy clarify command, template, and migration path in favor of the current planning/discovery flow.

## [2.0.11] - 2026-03-20

### 📄 Documentation

- **2.x release metadata refresh**: updated the README's current-release banner so the branch advertises the active GitHub-only 2.x release line instead of the initial `v2.0.0` placeholder.

## [2.0.10] - 2026-03-20

### ✅ Added

- **Project-level `auto_commit` setting (`#321`)**: repos can now configure automatic commit behavior directly in project config.
- **Sync queue resilience and diagnostics (`#320`)**: offline queue now supports FIFO eviction, coalescing, configurable caps, and sync doctor coverage for failure recovery.

### 🐛 Fixed

- **Merge target resolution (`#272`)**: merge target branch is now resolved from feature `meta.json`, preventing merges from targeting the wrong branch.
- **Acceptance and state persistence hardening (`#319`)**: state writes are now centralized around canonical metadata/state handling to reduce drift across acceptance, mission, and status flows.
- **Feature context fallback restored**: ambiguous agent/task resolution now falls back to the latest incomplete feature instead of stopping on a stale explicit-selection error.
- **Upgrade downgrade protection**: `spec-kitty upgrade` now refuses older targets instead of silently rewriting project metadata backwards.
- **Migration discovery fail-fast**: broken `m_*.py` modules now fail discovery immediately instead of being skipped with a stderr warning.
- **Upgrade metadata durability**: successful and failed migration records are now persisted immediately so retries can resume from an accurate state after mid-run failures.
- **Safe auto-commit stash isolation**: `safe_commit()` now restores only the stash entry it created, preventing unrelated user stashes from being popped during upgrade/status auto-commits.
- **Embedded task script compatibility**: copied `.kittify/scripts/tasks` helpers now fall back cleanly when the host `specify_cli` install is older than the copied templates.

### 🔧 Changed

- **State architecture cleanup phase 2 (`#319`)**: consolidated atomic-write and state-contract handling across runtime, acceptance, and feature metadata paths.
- **Test and quality isolation follow-ups**: retained the refactors that separated policy/test churn from release-critical behavior on the 2.x line.

## [2.0.9] - 2026-03-15

### ✅ Added

- **Mutation testing CI integration (feat #047)**: mutmut toolchain setup, CI integration, and targeted kill sessions for `status/` reducer and transitions.
- **Agentic mutation testing remediation workflow**: GitHub Agentic Workflow (gh-aw) replaces the legacy Claude workflow for mutation testing remediation.
- **SonarCloud integration**: added SonarCloud config; `develop` branch recognized as 2.x-equivalent in CI quality gates.
- **Architecture corpus restructure**: versioned architecture docs under `architecture/1.x/` and `architecture/2.x/`, 45 ADRs, glossary contexts across 10 bounded domains, Contextive integration, and stakeholder persona definitions.
- **`meta.json` schema example in specify template**: documents `"target_branch"` and `"vcs"` as required explicit fields.

### 🐛 Fixed

- **Post-rebase quality fixes**: resolved unmatched `)` syntax error, `gap_analysis_path` undefined name (F821), `timezone` → `UTC` reference, unused `type: ignore` comments, and `toml` import-untyped mypy errors.
- **Test isolation**: moved misplaced test package; fixed 3 test failures and Pydantic V1 deprecation warnings.
- **Sync offline queue**: redirect offline queue warning to stderr instead of stdout.
- **CI branch detection**: `develop` now recognized as a 2.x branch for branch-contract guards.

### 🔧 Changed

- **Ruff lint compliance**: full ruff clean pass across `src/` and `tests/`; added ruff lint config to `pyproject.toml`.
- **Documentation site updates**: 2.x docs site refresh with Contextive IDE integration guide.
- **Test suite restructuring**: migrated to vertical-slice layout; redesigned CI quality workflow; annotated suite with fast/slow/git_repo markers; deleted tests/legacy/ after extracting unique behaviours.

## [2.0.8] - 2026-03-11

### 🐛 Fixed

- **Dashboard approved lane**: WPs with `lane: "approved"` no longer silently fall back to the "planned" column. Added "Approved" as a 5th kanban column between For Review and Done, with `claimed`→planned and `in_progress`→doing lane normalization in the scanner.
- **Slim FEATURE_CONTEXT_UNRESOLVED payload**: reduced error payload size for LLM consumption to stay within agent context budgets.

## [2.0.7] - 2026-03-11

### ✅ Added

- **Mutation testing CI integration (feat #047)**: mutmut toolchain setup, CI integration, and targeted kill sessions for `status/` reducer and transitions (#275).
- **Agentic mutation testing remediation workflow**: GitHub Agentic Workflow (gh-aw) replaces the legacy Claude workflow for mutation testing remediation.
- **SonarCloud integration**: added SonarCloud config; `develop` branch recognized as 2.x-equivalent in CI quality gates.
- **Architecture corpus restructure**: versioned architecture docs under `architecture/1.x/` and `architecture/2.x/`, 45 ADRs, glossary contexts across 10 bounded domains, Contextive integration, and stakeholder persona definitions.
- **Google Antigravity as first-class agent (#266)**: added Google Antigravity to the supported agent roster with directory, templates, and migration coverage.
- **Commands own workflow context (#261)**: commands now carry their own workflow context rather than relying on ambient state.
- **Tracker snapshot publish payload (feat #048)**: resource routing in publish path (WP01) and batch API contract for tracker snapshot publish (WP02).

### 🐛 Fixed

- **Stale overrides from upgrade version-skew (#285)**: `classify_asset()` now compares project `.kittify/` files against immutable package-bundled defaults (`get_package_asset_root()`) instead of the mutable `~/.kittify/` directory. This prevents old managed templates from being misclassified as user customizations and permanently shadowing newer templates in `.kittify/overrides/` during upgrades.
- **New `SUPERSEDED` disposition**: managed files that differ from the current package default are now correctly classified as `SUPERSEDED` (removed) rather than `CUSTOMIZED` (moved to overrides). Only files with no package counterpart are treated as genuine user customizations.
- **Repair migration for already-affected users**: new `2.0.7_fix_stale_overrides` migration scans `.kittify/overrides/` for files byte-identical to current package defaults and removes them. Genuine user customizations are preserved.
- **Constitution: resolve_doctrine_root fallback for pip-installed users (#278)**: `resolve_doctrine_root()` no longer crashes when the `doctrine` package directory is missing from pip wheels; falls back to `specify_cli` package root.
- **Merge: worktree/branch cleanup when feature is already integrated (#271)**: `spec-kitty merge` now runs worktree removal and branch deletion when all WP branches are already merged, instead of exiting with "Nothing to merge" and leaving cleanup to the user.
- **Post-rebase quality fixes (#273)**: resolved unmatched `)` syntax error, `gap_analysis_path` undefined name (F821), `timezone` → `UTC` reference, unused `type: ignore` comments, and `toml` import-untyped mypy errors.
- **Test isolation**: moved misplaced test package; fixed 3 test failures and Pydantic V1 deprecation warnings.
- **Sync offline queue**: redirect offline queue warning to stderr instead of stdout.
- **CI branch detection**: `develop` now recognized as a 2.x branch for branch-contract guards.
- **Tracker publish path normalization (feat #048)**: normalize provider in publish path and document auth token resolution.

### 🔧 Changed

- **Ruff lint compliance**: full ruff clean pass across `src/` and `tests/`; added ruff lint config to `pyproject.toml`.
- **Documentation site updates**: 2.x docs site refresh with Contextive IDE integration guide.

## [2.0.6] - 2026-03-10

### 🐛 Fixed

- **Upgrade consistency sweep**: added a new `2.0.6_consistency_sweep` migration that backfills missing or blank feature `meta.json`, infers `target_branch` from feature docs or the repo primary branch, reconstructs missing `status.events.jsonl`, regenerates `status.json` and generated `tasks.md` status blocks, normalizes legacy WP frontmatter lane aliases/quoting, rewrites stale prompt paths, and archives orphan empty `status.json` snapshots before rebuilding canonical state.
- **Worktree upgrade coverage**: `spec-kitty upgrade` now upgrades worktrees that have `kitty-specs/` or legacy `.specify/` state even when `.kittify/` has not been created yet.
- **Detector false positives**: runtime-managed 2.x installs no longer trip legacy project-local mission migrations, and the constitution migration only flags the legacy `.kittify/memory/constitution.md` path.
- **Target-branch backfill correctness**: the `0.13.8_target_branch` migration now uses repo-aware branch inference instead of the obsolete hardcoded Feature 025 exception.

## [2.0.5] - 2026-03-10

### ✅ Added

- **Namespace-aware artifact body sync (Feature 047)**: Full offline-first pipeline for pushing spec artifact bodies (markdown content) to the SaaS backend, including `NamespaceRef` typed identifiers, `OfflineBodyUploadQueue` SQLite persistence, body upload preparation and filtering, HTTP transport with response classification, dossier pipeline orchestration with partial failure handling, background sync queue drain, and end-to-end diagnostics/logging.

### 🐛 Fixed

- **Init default directory (`#258`)**: `spec-kitty init` now defaults to the current directory when project name is omitted on the 2.x line.
- **Sync integration**: Completed namespace artifact body sync wiring for end-to-end operation.

### 📄 Documentation

- **Connector auth binding ADR**: Added architectural decision record for connector authentication binding and installation model gap analysis.
- **Command-owned action context ADR**: Defined command-owned action context pattern.

## [2.0.4] - 2026-03-06

### 🐛 Fixed

- **Upgrade JSON machine-parseability hardening (`#254`)**: `spec-kitty upgrade --json` now emits raw JSON output without Rich console wrapping.
- **Upgrade migration status consistency (`#256`)**: non-applicable migrations are reported as `skipped` instead of incorrectly marked as applied.

### 🔧 Changed

- **Contract hardening closeout (`#213`-`#218`)**: merged deterministic branch/runtime contracts, typed artifact-path payloads, merge/preflight JSON enrichment, and banner suppression in agent contexts.
- **Codex/Copilot slash-flow reliability (`#128`)**: integrated slash-command output stability improvements via deterministic JSON/banners/template alignment.
- **Worktree/preflight stability (`#226`)**: released preflight and command-contract hardening on the 2.x line for end-to-end spec→implement→review runs.

## [2.0.2] - 2026-02-27

### ✅ Added

- **Flag-gated tracker command group**: added `spec-kitty tracker ...` commands behind `SPEC_KITTY_ENABLE_SAAS_SYNC`, including provider listing, bind/unbind, mapping, local sync pull/push/run, and snapshot publish.
- **Tracker host-local persistence + credentials support**: added CLI-owned tracker SQLite cache/checkpoints and provider credential handling consistent with existing Spec Kitty host persistence patterns.

### 🔧 Changed

- **Dependency floor hardening for 2.x installs**: added explicit lower bounds for previously unbounded core CLI direct dependencies to reduce resolver drift in fresh environments.
- **Workflow review lane guard**: review start now requires a valid `for_review` lane state before progressing.

## [2.0.1] - 2026-02-26

### 🐛 Fixed

- **Main bias fix**: `resolve_primary_branch()` now checks the current branch before the hardcoded `[main, master, develop]` list. Repos on non-standard primary branches (e.g., `2.x`) no longer get blocked by `spec-kitty specify`.
- `create_feature()` records the current branch as `target_branch` in `meta.json` instead of guessing via heuristics. Added `--target-branch` CLI option for explicit override.
- `guards.py` uses `resolve_primary_branch()` instead of hardcoded `{"main", "master"}` set.
- `merge-feature --target` auto-detects from `meta.json` when not specified.
- Template references to "main" replaced with "target branch" throughout command templates.

### 🔧 Changed

- **Dashboard `--open` flag**: Browser auto-open is now disabled by default. Pass `--open` to open the dashboard URL in your browser. Prevents browser windows from spawning during tests or CI.
- Consolidated 3 ad-hoc branch-check functions into `_show_branch_context()` for consistent branch banners across all planning commands.

## [2.0.0] - 2026-02-22

### 🔧 Changed

- Start semantic versioning for `2.x` GitHub-only releases using `v2.<minor>.<patch>` tags.
- `2.x` release automation now publishes GitHub Releases only (no PyPI publish step).

### 🐛 Fixed

- `spec-kitty next` no longer short-circuits `--result failed|blocked` in the CLI bridge; both now flow through `spec-kitty-runtime` `next_step(...)`, preserving canonical runtime lifecycle behavior and run metadata.
- Runtime mission template selection for `next` now follows deterministic precedence tiers (`explicit`, `env`, `project override`, `project legacy`, `user global`, `project config`, `builtin`) when resolving `mission-runtime.yaml`.
- `--answer --json` integration coverage now exercises a real pending-decision success path (runtime `requires_inputs`) instead of fake decision IDs.
- Added replay-parity integration coverage in `spec-kitty` against `spec-kitty-events` canonical fixture stream (`mission-next-replay-full-lifecycle`).
- **WP prompt tracking reliability**: removed stale `kitty-specs/**/tasks/*.md` from tracked `.gitignore`, migrated existing projects away from that rule, and hardened workflow status commits to fail loudly if claim commits cannot be written.

## [2.0.0a5] - 2026-02-14

### 🐛 Fixed

**Backported orchestrator deadlock fixes from v0.15.3**:

- **Orchestrator deadlock**: Fixed false "No progress possible" detection when WP tasks raise exceptions or complete but leave WPs in intermediate states (IMPLEMENTATION/REVIEW). The orchestrator now properly marks failed WPs as FAILED and restarts orphaned WPs, preventing deadlock cascades. (Backport of #137 by @tannn)
- **Exception handling**: Task exceptions now properly mark WPs as FAILED with error details, allowing dependent WPs to recognize failure instead of blocking indefinitely
- **WP restart logic**: Added restart counter to prevent infinite restart loops if WP repeatedly fails to advance state. Restarts are now capped at `max_retries` (default: 3)
- **State recovery**: Improved detection of interrupted implementations (IMPLEMENTATION status without `implementation_completed` timestamp) to automatically reset and retry

### 🧹 Maintenance

- **Test coverage**: Added 8 new orchestrator tests covering exception handling, restart scenarios, deadlock detection, and state persistence
- **Test quality**: Reorganized test suite with proper markers (`@pytest.mark.orchestrator_exception_handling`, `@pytest.mark.orchestrator_deadlock_detection`) and class grouping following project conventions

## [2.0.0a4] - 2026-02-13

### 🐛 Fixed

**Backported v0.15.2 hotfix from main branch**:

- **Branch detection**: Replaced single `rev-parse --abbrev-ref HEAD` with dual-strategy
  approach (`git branch --show-current` primary, `rev-parse` fallback). Fixes unborn branch
  detection and detached HEAD handling. Updated all inline callers in tasks.py, workflow.py,
  and vcs/git.py.

- **Subprocess encoding safety**: Added `encoding="utf-8", errors="replace"` to all ~135
  `subprocess.run(text=True)` calls across 36 files. Prevents crashes on non-UTF-8 git output (Windows, locale mismatches).

- **Pre-commit hook safety**: Removed `set -e` from encoding check hook, expanded Python
  interpreter detection (loops through python3/python/py with smoke test), fixed exit code
  handling to distinguish encoding errors (exit 2) from execution failures.

- **Init fail-fast**: `spec-kitty init` now raises RuntimeError immediately after git init
  failure instead of falling through to "project ready" success message.

- **PowerShell templates**: Added PowerShell equivalent blocks to implement.md templates
  for software-dev, research, and documentation missions.

## [2.0.0a3] - 2026-02-11

### 🐛 Fixed

**Complete Bug #119 cherry-pick**:
- Fixed missing update to `scripts/tasks/acceptance_support.py` (root-level test helper)
- This file was missed in the original Bug #119 cherry-pick, causing test failures
- Now all acceptance_support.py copies correctly exclude 'done' lane from assignee requirement

## [2.0.0a2] - 2026-02-11

### 🐛 Fixed

**Cherry-picked 7 critical bug fixes from v0.15.0 (main branch)**:

- **Bug #95**: Enforce kebab-case validation for feature slugs
  - Rejects slugs with spaces, underscores, uppercase, or leading numbers
  - Prevents invalid directory structures and broken workflow commands
  - Added 8 comprehensive validation tests

- **Bug #120**: Use local git exclude for worktree ignores
  - Worktree-specific ignores now written to `.git/info/exclude` instead of `.gitignore`
  - Prevents `.gitignore` pollution when merging worktrees
  - VCS abstraction layer handles legacy worktree filtering consistently

- **Bug #117**: Improve dashboard lifecycle and error diagnostics
  - Dashboard process detection no longer reports false failures
  - Distinguishes between health check timeout (process running) vs actual failure
  - Provides specific error messages for missing metadata, port conflicts, permission errors

- **Bug #124**: Unify branch resolution, stop implicit master fallback
  - Respects user's current branch instead of auto-checkout
  - Shows notification when current branch differs from feature target
  - No more surprise checkouts during `spec-kitty implement` or `move-task`
  - Consistent branch resolution across all commands

- **Bug #119**: Relax strict assignee gate in acceptance validation
  - Assignee now optional for completed work packages in 'done' lane
  - Strict validation still enforces assignee for 'doing' and 'for_review'
  - Required fields (lane, agent, shell_pid) still mandatory

- **Bug #122**: Prevent staged files from leaking into status commits
  - New `safe_commit()` helper explicitly stages only intended files
  - Status commits no longer capture unrelated staged changes
  - Preserves user's staging area across workflow operations

- **Bug #123**: Call lane transition before status update (atomic state)
  - Lane transitions now happen BEFORE internal state updates
  - Prevents inconsistent state when operations fail mid-transition
  - Applies to orchestrator implementation and review phases

All fixes include comprehensive test coverage (54+ new tests) and maintain backward compatibility.

## [0.13.26] - 2026-02-04

### 🛠️ Refactored

**Consolidated workflow implement workspace creation**:
- `spec-kitty agent workflow implement` now delegates workspace creation to `spec-kitty implement` when needed
- Removes duplicated worktree setup in the agent command
- Prevents agents from creating worktrees from inside another worktree

### 🐛 Fixed

**Clearer recovery guidance for multi-parent merge failures**:
- When auto-merge fails, instructions now show concrete recovery steps
- Explicitly warns there is no `spec-kitty agent workflow merge` command
- Points agents to the correct `spec-kitty agent feature merge` command

## [0.13.25] - 2026-02-04

### 🐛 Fixed

**`spec-kitty upgrade` not bumping version when no migrations needed**:
- When `spec-kitty upgrade` found no applicable migrations, it returned early without updating the version in `.kittify/metadata.yaml`
- This left the project stuck at its old version (e.g., 0.13.21) even though the CLI was newer (0.13.24)
- The dashboard then blocked with a version mismatch error
- Fixed both `upgrade.py` (CLI command path) and `runner.py` (programmatic path) to stamp the version even when no migrations are needed

## [0.13.24] - 2026-02-04

### 🔧 Improved

**Review workflow shows git context for reviewers**:
- `spec-kitty agent workflow review` now displays the WP's branch name, base branch, and commit count
- Reviewers see exactly which commits belong to the WP vs inherited history
- Provides ready-to-use `git log <base>..HEAD` and `git diff <base>..HEAD` commands
- base branch auto-detected from WP dependencies (tries dependency branches first, then main/2.x)
- Prevents reviewers from accidentally diffing against the wrong base (e.g., `main` instead of `2.x`)

## [0.13.20] - 2026-01-30

### 🐛 Fixed

**Merged Single-Parent Dependency Workflow Gap** (ADR-18):
- Fixed `spec-kitty implement` failing when single-parent dependency has been merged to target branch
- Issue: WP01 merged to 2.x → WP02 can't implement (looks for non-existent WP01 workspace branch)
- Root cause: Implement command didn't distinguish between in-progress vs merged dependencies
- Solution: Auto-detect when dependency lane is "done" and branch from target branch instead
- Behavior:
  - If `base_wp.lane == "done"`: Branch from target branch (e.g., 2.x) - merged work already there
  - If `base_wp.lane != "done"`: Branch from workspace branch (e.g., 025-feature-WP01) - work in progress
- Eliminates need for manual frontmatter editing (remove dependencies, update base_branch)
- Complements ADR-15 (multi-parent all-done suggestion) for single-parent case
- **Impact**: Critical fix for normal workspace-per-WP workflow where dependencies complete before dependents start
- **Technical Story**: Feature 025-cli-event-log-integration WP02/WP08 blocked on merged WP01

## [0.13.7] - 2026-01-27

### 🐛 Fixed

**Activity Log Parser Failing on Hyphenated Agent Names** ([#111](https://github.com/Priivacy-ai/spec-kitty/pull/111)):
- Fixed `activity_entries()` regex in `tasks_support.py` to handle hyphenated agent names
- Parser was using `[^–-]+?` pattern which treated hyphens as field separators
- Agent names like `cursor-agent`, `claude-reviewer`, `cursor-reviewer` now parse correctly
- Acceptance validation no longer fails with "Activity Log missing entry for lane=done" for hyphenated agents
- Changed pattern to `\S+(?:\s+\S+)*?` (matches non-whitespace), aligning with `task_helpers.py`
- Added comprehensive test suite with 11 test cases covering hyphenated names, backward compatibility, and edge cases
- **Contributors**: Rodrigo D. L. (bruj0)

**Workflow Completion Instructions Missing Git Commit Step** ([#104](https://github.com/Priivacy-ai/spec-kitty/pull/104)):
- Fixed agents not committing implementation files before marking tasks done
- Issue caused cascading failures where dependent work packages started from empty branches
  - WP02 worktree had HTML + CSS ✅
  - WP03 worktree had HTML only (missing WP02's CSS) ❌
  - WP04 worktree had HTML only (missing CSS and JS from WP02 and WP03) ❌
- Root cause: "WHEN YOU'RE DONE" instructions in `workflow implement` command didn't include git commit step
- Fix: Added explicit git commit instruction as step 1 in completion checklist
- Updated both in-prompt instructions (shown twice) and terminal output summary
- Added warning: "The move-task command will FAIL if you have uncommitted changes! Commit all implementation files BEFORE moving to for_review. Dependent work packages need your committed changes."
- **Impact**: Critical fix for multi-agent parallel development workflows using workspace-per-WP model (v0.11.0+)
- **Contributors**: Jerome Lacube

**Dashboard Command Template Generating Python Code Instead of Running CLI** ([#94](https://github.com/Priivacy-ai/spec-kitty/issues/94), [#99](https://github.com/Priivacy-ai/spec-kitty/pull/99)):
- Fixed `/spec-kitty.dashboard` command template to use `spec-kitty dashboard` CLI command
- Removed outdated Python code that manually checked dashboard status and opened browsers
- Dashboard now properly:
  - Starts automatically if not running
  - Opens in default browser
  - Handles worktree detection automatically
- Updated all three dashboard template files:
  - `.kittify/missions/software-dev/command-templates/dashboard.md`
  - `src/specify_cli/missions/software-dev/command-templates/dashboard.md`
  - `src/specify_cli/templates/command-templates/dashboard.md`
- Reduced template code from ~264 lines to ~47 lines
- **Contributors**: Jerome Lacube

## [0.13.6] - 2026-01-27

### 🐛 Fixed

**Critical JSON Mode Corruption Fix** (Release Blocker):
- Fixed JSON output corruption in `spec-kitty implement --json` mode (GitHub Issue #72 follow-up)
  - **Bug**: Warning messages from empty branch detection were written to stdout, corrupting JSON output
  - **Impact**: Automated workflows using `--json` flag would fail with JSON parse errors
  - **Fix**: Changed warning messages to use `file=sys.stderr` to separate warnings from JSON output
  - **File**: `src/specify_cli/core/multi_parent_merge.py:142-144`
  - **Tests**: Updated 5 tests in `test_multi_parent_merge_empty_branches.py` to check stderr instead of stdout

**Missing Migration Fix** (Existing Users Affected):
- Fixed missing migration for commit workflow section (GitHub Issue #72 follow-up)
  - **Bug**: New projects got commit workflow section in implement.md, but existing projects didn't after upgrade
  - **Impact**: Existing users remained vulnerable to agents forgetting to commit work
  - **Fix**: Created migration `m_0_13_5_add_commit_workflow_to_templates.py` to update all agent templates
  - **Coverage**: Updates both software-dev and documentation mission templates for all 12 agents
  - **Migration**: Automatically runs on `spec-kitty upgrade` for projects missing commit workflow

**Subprocess Error Handling** (Defensive Programming):
- Added timeout and error handling to multi-parent merge git commands
  - **Bug**: Git commands in empty branch detection lacked timeout parameters and try/except blocks
  - **Impact**: Function could hang forever or crash on git errors (corrupted repo, permission issues)
  - **Fix**: Added 10-second timeouts and exception handling to all git subprocess calls
  - **File**: `src/specify_cli/core/multi_parent_merge.py:117-144`
  - **Errors handled**: TimeoutExpired (>10s git commands), general exceptions with warning

### Added

- Git commit validation for "done" status transitions - prevents completing WPs with uncommitted changes
- Empty branch detection in merge-base creation - warns when dependencies have no commits
- Git commit workflow section in documentation mission template (consistency with software-dev/research)
- Comprehensive troubleshooting guide for empty branch recovery in the legacy workspace-model documentation
- Migration to add commit workflow section to existing projects (`m_0_13_5_add_commit_workflow_to_templates.py`)

### Changed

- `move-task --to done` now validates git status (same checks as "for_review")
- Use `--force` flag to bypass validation (not recommended)
- Warning messages in multi-parent merge now output to stderr instead of stdout (preserves JSON output integrity)

### Fixed (Non-Critical)

- WP agents can no longer mark tasks as "done" without committing implementation files
- Multi-parent merge-bases no longer silently accept empty dependency branches
- Documentation mission now instructs agents to commit work before review
- Stale WP detection now correctly detects default branch name (main/master/develop) instead of hardcoding "main"
  - **Bug**: Fresh worktrees incorrectly flagged as stale when repository used non-standard default branch
  - **Root Cause**: Code hardcoded "main" as default branch; when `git merge-base HEAD main` failed, it fell through to using parent branch's old commit timestamp
  - **Fix**: Added `get_default_branch()` helper to dynamically detect default branch via origin HEAD or local branch existence
  - **Impact**: Prevents false staleness warnings for fresh worktrees in repos using "master", "develop", or other default branches

## [0.13.5] - 2026-01-26

### 🐛 Fixed

**Fixed /spec-kitty.clarify Command Template**:
- Fixed broken placeholder in clarify template that prevented agents from running clarification workflow
  - **Bug**: Template contained `(Missing script command for sh)` placeholder instead of actual command
  - **Impact**: Agents couldn't get feature context, invented non-existent commands like `spec-kitty agent feature get-active --json`
  - **Fix**: Replaced manual detection logic with `spec-kitty agent feature check-prerequisites --json --paths-only`
  - **Consistency**: Now matches pattern used in specify.md, plan.md, and tasks.md templates
  - Migration `m_0_13_5_fix_clarify_template.py` automatically updates all 12 agent directories on upgrade
  - Source template: `src/specify_cli/missions/software-dev/command-templates/clarify.md`

**Testing**:
- Added comprehensive test suite with 34 tests covering all scenarios
  - Parametrized tests for all 12 agents (claude, copilot, gemini, cursor, qwen, opencode, windsurf, codex, kilocode, auggie, roo, q)
  - Tests for detection, application, agent config respect, idempotency, dry-run
  - Template content validation (ensures no broken placeholders, matches tasks.md pattern)
  - End-to-end integration test verifying migration actually runs and fixes templates

## [0.13.4] - 2026-01-26

### 🐛 Fixed

**Critical Dependency Validation Fix**:
- Fixed `spec-kitty agent workflow implement` not validating WP dependencies before creating workspaces
  - **Bug**: WP with single dependency could create workspace without `--base` flag
  - **Impact**: Workspace branched from main instead of dependency branch (silent correctness bug)
  - **Fix**: Added shared validation utility that errors when single dependency but no `--base` provided
  - **Example**: `WP06` depends on `WP04` → command now errors and suggests `--base WP04`
  - Created `src/specify_cli/core/implement_validation.py` with `validate_and_resolve_base()`
  - Agent commands now delegate to top-level commands (no more legacy script calls)

**Fixed Broken Agent Commands**:
- Fixed `spec-kitty agent feature accept` calling non-existent `scripts/tasks/tasks_cli.py`
  - Now delegates to top-level `accept()` command
- Fixed `spec-kitty agent feature merge` calling non-existent `scripts/tasks/tasks_cli.py`
  - Now delegates to top-level `merge()` command
  - Parameter mapping: `keep_branch` → `delete_branch` (inverted logic)

**Critical Merge Workflow Fix**:
- Fixed merge failing when main branch lacks upstream tracking (Issue reported post-0.13.2 release)
  - 0.13.2 only checked if remote EXISTS, but not if branch TRACKS it
  - Added `has_tracking_branch()` function to check upstream tracking
  - Merge now skips pull if: (1) no remote OR (2) no upstream tracking
  - Affects users with local-only repos or repos where main doesn't track origin/main

**Testing & Prevention**:
- Added 22 new tests for dependency validation and agent command wrappers
  - Unit tests: `test_implement_validation.py` (11 tests)
  - Integration tests: `test_agent_command_wrappers.py` (11 tests)
- Added `TestMigrationRegistryCompleteness` test (prevents 0.13.2-style release blocker)
  - Verifies all `m_*.py` migration files are imported in `__init__.py`
  - Prevents silent bugs where migrations exist but never run
- Added integration tests for merge with untracked branches
- Added unit tests for `has_tracking_branch()` function

**Documentation**:
- Added `src/specify_cli/cli/commands/agent/README.md` (wrapper pattern documentation)
  - Dependency validation best practices
  - Parameter mapping guidelines
  - Common pitfalls and examples
- Updated RELEASE_CHECKLIST.md with mandatory migration registry verification

## [0.13.2] - 2026-01-26

### 🐛 Fixed

**Critical Windows Compatibility Issues**:
- Fixed UTF-8 encoding errors causing Windows crashes (Issue #101)
  - Added `encoding='utf-8'` to all `write_text()` and `read_text()` calls
  - Affected files: feature.py, worktree.py, agent_context.py, doc_generators.py, gap_analysis.py
  - Completes PR #100 which missed several locations
- Fixed hardcoded `python3` breaking Windows installations (Issue #105)
  - Replaced with `sys.executable` in Python code (feature.py)
  - Added dynamic Python detection in git hooks (tries python3, falls back to python)
  - Windows users no longer need to create python3 hardlinks/aliases

**Workflow Improvements**:
- Added `--base` parameter to `spec-kitty agent workflow implement` (Issue #96)
  - Enables agents to create dependent WP worktrees via workflow command
  - Provides feature parity with top-level `spec-kitty implement` command
  - Example: `spec-kitty agent workflow implement WP02 --base WP01 --agent claude`

**Template and Documentation Fixes**:
- Fixed broken `/spec-kitty.clarify` skill (Issue #106)
  - Removed unresolved `{SCRIPT}` and `{ARGS}` placeholders
  - Replaced with auto-detection instructions for feature paths
- Fixed outdated template path references (Issue #102)
  - Updated 6 references from `.kittify/templates/` to `src/specify_cli/missions/`
  - Templates now reference correct bundled locations
- Fixed upgrade version detection for modern projects (Issue #108)
  - Added detection for versions 0.7.0-0.13.0
  - Prevents unnecessary migrations on modern projects
- Regenerated all 12 agent constitution templates (Issue #97)
  - All agents now correctly suggest `/spec-kitty.specify` as next step (not `/spec-kitty.plan`)

### 📚 Documentation

- Added GitHub CLI authentication troubleshooting to CLAUDE.md
  - Documents `unset GITHUB_TOKEN` technique for organization repos

**Issues Closed**: #96, #97, #101, #102, #105, #106, #108, #103 (not a bug), #107 (not a bug)

## [0.13.1] - 2026-01-25

### ✨ Added

**Adversarial Test Suite for 0.13.0 Release**:
- **Distribution tests**: Validate PyPI user experience without SPEC_KITTY_TEMPLATE_ROOT bypass (prevents 0.10.8-style packaging failures)
- **Path validation security tests**: Test directory traversal, symlink attacks, case-sensitivity bypasses, and path injection prevention
- **CSV schema attack tests**: Validate handling of formula injection, encoding errors, duplicate columns, and empty files
- **Git state detection tests**: Verify accuracy of uncommitted work, merge state, and branch divergence detection
- **Migration robustness tests**: Test UTF-8 encoding, idempotency, and partial/corrupted file handling
- **Multi-parent merge tests**: Validate dependency-order merging and conflict resolution
- **Context & config tests**: Test non-interactive modes, agent configuration, and workspace validation

**Test Infrastructure**:
- New `tests/adversarial/` directory with shared fixtures and attack vectors
- `@pytest.mark.distribution` and `@pytest.mark.slow` markers for CI optimization
- Session-scoped `wheel_install` fixture for efficient testing
- Platform-specific skip conditions for cross-platform compatibility

### 📚 Documentation

**Testing**:
- Comprehensive adversarial test documentation in feature 024 spec
- Attack vector catalog with prevention strategies
- CI integration guidance for slow/distribution tests

## [0.13.0] - 2026-01-25

### ✨ Added

**Deterministic CSV Schema Enforcement for Research Missions**:
- **Canonical schema documentation**: Research CSV schemas now documented in all 12 agent implement.md templates
- **Two schemas enforced**:
  - `evidence-log.csv`: `timestamp,source_type,citation,key_finding,confidence,notes`
  - `source-register.csv`: `source_id,citation,url,accessed_date,relevance,status`
- **Schema visibility**: Agents see schemas before editing (in "Research CSV Schemas" section with examples)
- **Detection migration**: `m_0_13_0_research_csv_schema_check.py` scans existing features for schema mismatches (informational only, no auto-fix)
- **Template propagation**: `m_0_13_0_update_research_implement_templates.py` updates all agent templates with schema documentation
- **Reusable validator**: `src/specify_cli/validators/csv_schema.py` provides `CSVSchemaValidation` dataclass for exact schema matching
- **Exported constants**: `EVIDENCE_REQUIRED_COLUMNS` and `SOURCE_REGISTER_REQUIRED_COLUMNS` now importable from `research.py`
- **ADR #8**: Documents architecture decision for documentation-based enforcement vs runtime enforcement/auto-migration

**Problem Solved**: Agents were modifying CSV schemas during implementation, creating different schemas in parallel WPs, causing merge conflicts and validation failures at review time.

**Solution Approach**: Document schemas where agents can see them (prevention) rather than runtime enforcement or auto-migration (data loss risk).

**Fully Non-Interactive Init Support**:
- Added `--non-interactive` / `--yes` and `SPEC_KITTY_NON_INTERACTIVE` to disable prompts
- Added `--agent-strategy`, `--preferred-implementer`, and `--preferred-reviewer` to expose all selection options via CLI
- Non-interactive mode now avoids arrow-key menus and requires `--force` for non-empty `--here` directories
- Updated documentation for automation and CI usage

### 🐛 Fixed

**Windows UTF-8 Encoding Crashes**:
- Fixed all `write_text()` calls to include `encoding='utf-8'` parameter
- Affects feature creation, worktree setup, gap analysis, doc generators, agent context, and test fixtures
- Windows users can now create features without charmap encoding errors
- Fixes #101, incorporates PR #100

**Constitution Template Workflow**:
- Fixed incorrect next-step suggestion after creating constitution
- Now correctly suggests `/spec-kitty.specify` instead of `/spec-kitty.plan`
- Propagated fix to all 12 agent directories via migration
- Fixes #97 (inspired by PR #98)

**Research Mission Detection**:
- Fixed `spec-kitty mission current` to show feature-level missions
- Now auto-detects feature from current directory (kitty-specs or worktree)
- Added `--feature` flag for explicit feature specification
- No longer always defaults to software-dev for research features
- Fixes #93

### 🎉 Closed

**Agent Configuration Feature**:
- Closed #51 as completed (already implemented in v0.12.0)
- Feature: `spec-kitty agent config add/remove/list`

### 📚 Documentation

**Release Management**:
- Added `RELEASE_CHECKLIST.md` - Comprehensive release preparation checklist with version-specific sections for research missions, agent management, and workspace-per-WP changes

### Migration Notes

**For users with existing research features**:
1. Run `spec-kitty upgrade` to trigger detection migration
2. See informational report with schema diffs and migration tips
3. Use LLM agent to help migrate data:
   - Read canonical schema in `.claude/commands/spec-kitty.implement.md`
   - Create new CSV with correct headers
   - Map old columns → new columns
   - Replace old file and commit to main

**For new research features (0.13.0+)**:
- Templates already have correct schemas
- Agents see schema documentation before editing
- Follow append-only pattern to avoid overwrites
- Validation passes at review

## [0.12.1] - 2026-01-24

### 🐛 Fixed

**kitty-specs/ in .gitignore Blocking Feature Creation**:
- Fixed issue where users with `kitty-specs/` in their `.gitignore` couldn't create features
- Error manifested as: "Issue Detected: The spec-kitty agent feature create-feature command failed to commit because .gitignore contains kitty-specs/"
- New migration `m_0_12_1_remove_kitty_specs_from_gitignore` automatically removes blocking entries
- Only removes patterns that block the entire `kitty-specs/` directory
- Preserves worktree-specific patterns like `kitty-specs/**/tasks/*.md` (used to prevent merge conflicts)

### Migration Notes

**For users experiencing this bug:**
1. Run `spec-kitty upgrade` to apply the fix automatically
2. Or manually remove `kitty-specs/` from your `.gitignore`

The migration will detect and remove entries like:
- `kitty-specs`
- `kitty-specs/`
- `/kitty-specs`
- `/kitty-specs/`

It will NOT remove specific subpath patterns that are intentionally used in worktrees.

## [0.12.0] - 2026-01-23

### ✨ Added

**Config-Driven Agent Management** (Feature 022):
- **Single source of truth**: `.kittify/config.yaml` now controls which agents are configured
- **New CLI commands**: `spec-kitty agent config list|add|remove|status|sync`
  - `list`: Show configured agents
  - `add <agents...>`: Add agents to configuration
  - `remove <agents...>`: Remove agents from configuration
  - `status`: Show configured vs orphaned agents
  - `sync`: Synchronize filesystem with configuration
- **Migrations respect config**: `get_agent_dirs_for_project()` helper only processes configured agents
- **Orphan detection**: Identifies agent directories not in config (from manual deletions)
- **ADR #6**: Documents architectural decision for config-driven approach

**Smarter Feature Merge with Pre-flight** (Feature 017):
- **Pre-flight validation**: Checks all WP worktrees for uncommitted changes, missing worktrees, and target branch divergence before any merge starts
- **Conflict forecasting**: `--dry-run` predicts which files will conflict and classifies them as auto-resolvable (status files) or manual
- **Smart merge order**: WPs merged in dependency order based on frontmatter `dependencies` field
- **Status file auto-resolution**: Conflicts in WP prompt files (`kitty-specs/*/tasks/*.md`) automatically resolved by taking advanced lane status
- **merge state persistence**: Progress saved to `.kittify/merge-state.json` for recovery
- **Resume/abort flags**: `--resume` continues interrupted merges, `--abort` clears state and starts fresh
- **Auto-cleanup**: Worktrees and branches removed after successful merge (configurable with `--keep-worktree`, `--keep-branch`)

### 📚 Documentation

**Merge Preflight Documentation** (Feature 018):
- Added `docs/how-to/merge-feature.md` - Complete merge workflow guide with pre-flight, dry-run, strategies, and cleanup options
- Added `docs/how-to/troubleshoot-merge.md` - Comprehensive troubleshooting guide with error reference table
- Updated CLAUDE.md with Merge & Preflight Patterns section documenting MergeState dataclass and public API

**Agent Management Documentation Sprint** (Feature 023):
- Added `docs/how-to/manage-agents.md` - Complete guide to adding, removing, and managing AI agent integrations
- Added `docs/how-to/upgrade-to-0-12-0.md` - Migration guide for config-driven agent management
- Updated `docs/reference/cli-commands.md` with comprehensive `agent config` subcommand documentation
- Updated `docs/reference/agent-subcommands.md`, `docs/reference/configuration.md`, `docs/reference/supported-agents.md` with accurate cross-references
- Updated `docs/how-to/install-spec-kitty.md` with agent configuration guidance

### 🐛 Fixed

**Merge Resume Bug**:
- Fixed `merge_workspace_per_wp()` missing `resume_state` parameter causing `TypeError` when using `--resume`

**Agent Workflow Output Truncation** (GitHub Codex compatibility):
- Fixed workflow commands (`implement`, `review`) outputting 300+ lines which got truncated by agents like GitHub Codex
- Prompts now written to temp file with concise 15-line summary to stdout
- Added directive language (`▶▶▶ NEXT STEP: Read the full prompt file now:`) so agents automatically read the file
- Agents no longer miss work package requirements due to output truncation

**False Staleness for Newly-Created Worktrees**:
- Fixed stale detection flagging new worktrees as stale immediately
- Previously, `git log -1` returned parent branch's commit time (could be hours old)
- Now checks if branch has commits since diverging from main
- Worktrees with no new commits are NOT flagged as stale (agent just started)

## [0.11.1] - 2026-01-16

### 🐛 Fixed

**Merge Template Improvements**:
- Added explicit preflight validation code using `python3 -c` with `validate_worktree_location()`
- Added clear visual "⛔ Location Pre-flight Check (CRITICAL)" section to prevent agents running merge from wrong location
- Fixed contradictory instructions in software-dev mission merge template (was incorrectly saying "run from main")
- Fixed empty Python code block in research mission merge template that confused agents
- Added workspace-per-WP model (0.11.0+) documentation vs legacy pattern in worktree strategy section

**Documentation Accuracy** (Feature 014):
- Rewrote `multi-agent-orchestration.md` for the 0.11.0+ isolated-WP worktree model:
  - Planning happens in main repo (not worktrees)
  - Each WP gets its own worktree (not shared)
  - Removed references to non-existent scripts
  - Updated lane tracking to frontmatter (not directories)
  - Added parallelization patterns and status monitoring
- Fixed the legacy isolated-worktree guide merge command syntax (runs from worktree without feature argument)
- Fixed `documentation-mission.md` broken source links
- Fixed `reference/README.md` - replaced outdated "Planned Content" with actual content links
- Fixed `kanban-workflow.md` - clarified `/spec-kitty.accept` works on features, not individual WPs

### 📚 Added

**Comprehensive End-User Documentation** (Feature 014):
- Complete Divio 4-type documentation suite:
  - **Tutorials**: Getting Started, Your First Feature, Claude Code Integration, Claude Code Workflow, Multi-Agent Workflow, Missions Overview
  - **How-To Guides**: 14 task-oriented guides covering installation, specifications, planning, implementation, review, dependencies, parallel development, dashboard usage, and migration
  - **Reference**: CLI Commands, Slash Commands, Agent Subcommands, Configuration, Environment Variables, File Structure, Missions, Supported Agents
  - **Explanations**: Spec-Driven Development, Divio Documentation, legacy isolated worktree model, Git Worktrees, Mission System, Kanban Workflow, AI Agent Architecture, Documentation Mission, Multi-Agent Orchestration
- Cross-references between all documentation types
- DocFX-compatible structure with `toc.yml` navigation

## [0.11.0] - 2026-01-12

### 🚨 BREAKING CHANGES - Workspace Model Changed (Feature 010)

**Old (0.10.x)**: One worktree per feature
- `/spec-kitty.specify` created `.worktrees/###-feature/`
- All WPs worked in same worktree
- Sequential development (one agent at a time)

**New (0.11.0)**: One worktree per work package
- Planning commands (specify, plan, tasks) work in main repository (NO worktree created)
- `spec-kitty implement WP##` creates `.worktrees/###-feature-WP##/`
- Each WP has isolated worktree with dedicated branch
- Enables parallel multi-agent development

### ⚠️ Migration Required

**You MUST complete or delete all in-progress features before upgrading to 0.11.0.**

See docs/upgrading-to-0-11-0.md for complete migration guide.

### 🔒 Security (IMPORTANT) - Feature 011

- **Comprehensive adversarial review framework**
  - Expanded review template from 3 bullets (109 lines) to 12 scrutiny categories (505 lines)
  - **Security scrutiny now mandatory**: 10 detailed security subsections
  - **Mandatory verification**: 7 security grep commands must be run on EVERY review
  - **Automatic rejection** if any security check fails
  - **Impact**: All future features will have security-first reviews

### ✨ Added

**Legacy isolated-WP worktree features (010)**:
- **New command**: `spec-kitty implement WP## [--base WPXX]` - Create workspace for work package
  - `--base` flag branches from another WP's branch (for dependencies)
  - Automatically moves WP from `planned` → `doing` lane
- **New command**: `spec-kitty agent feature finalize-tasks` - Finalize WP generation
  - Parses dependencies from tasks.md
  - Generates `dependencies: []` field in WP frontmatter
  - Validates dependency graph (cycle detection, invalid references)
- **Dependency tracking**: WP frontmatter includes `dependencies: []` field
- **Dependency graph utilities**: `src/specify_cli/core/dependency_graph.py`
- **Review warnings**: Alert when dependent WPs need rebase

**Constitution Features (011)**:
- **Interactive constitution command** (Phase-based discovery)
  - 4-phase discovery workflow (Technical, Quality, Tribal Knowledge, Governance)
  - Two paths: Minimal (Phase 1 only) or Comprehensive (all phases)
  - Skip options for each phase
  - Truly optional - all commands work without constitution

### ♻️ Refactored - Feature 011

- **Template source relocation** (Safe dogfooding - Critical)
  - Moved ALL template sources from `.kittify/` to `src/specify_cli/`
  - Updated template manager to load from package resources
  - Removed `.kittify/*` force-includes from `pyproject.toml`
  - **Impact**: Developers can now safely dogfood without packaging risk

- **Mission-specific constitutions removed**
  - Single project-level constitution model (`.kittify/memory/constitution.md`)
  - Migration removes mission constitutions from user projects

### 🐛 Fixed - Feature 011

- **Windows dashboard ERR_EMPTY_RESPONSE** (#71)
  - Replaced POSIX-only signal handling with cross-platform psutil
  - Added `psutil>=5.9.0` dependency
  - Dashboard now works on Windows 10/11

- **Upgrade migration failures** (#70)
  - Fixed multiple migrations to handle missing files gracefully
  - All migrations now idempotent
  - Upgrade path from 0.6.4 → 0.10.12 completes without intervention

### 🐛 Fixed - Feature 012

- **`/spec-kitty.status` template instructed agents to run Python code**
  - AI agents cannot execute arbitrary Python - they use CLI tools
  - Updated template to use CLI command as primary method
  - Python API now documented as alternative for Jupyter/scripts

### 📖 Documentation - Feature 010

- **New docs**: legacy isolated-worktree workflow guide with examples
- **New docs**: `docs/upgrading-to-0-11-0.md` - Migration instructions

### 🎯 Why These Changes?

**Feature 010 (Workspace-per-WP)**:
- Enables parallel multi-agent development
- Better isolation per work package
- Explicit dependencies with validation
- Scalability for large features (10+ WPs)

**Feature 011 (Constitution & Packaging Safety)**:
- Safe dogfooding (no packaging contamination)
- Cross-platform dashboard support
- Optional, interactive constitution setup
- Smooth upgrade migrations

## [0.10.13] - 2026-01-12

### 🐛 Fixed

- **CRITICAL: Missing migration in PyPI v0.10.12 package**
  - Migration `m_0_10_12_constitution_cleanup.py` was missing from PyPI package uploaded on 2026-01-07
  - File existed in source repository but was not included in distributed wheel
  - Caused constitution cleanup to not run during upgrades from v0.10.11
  - v0.10.13 includes the missing migration file
  - Users who installed v0.10.12 should run `spec-kitty upgrade` again after upgrading to v0.10.13
  - **Root cause**: PyPI package was built before migration file was committed to repository
  - **Prevention**: Added migration file count verification to release workflow

### ♻️ Improved

- **Release workflow hardening**
  - Added verification step to count migration files in built wheel
  - Release now fails if migration count doesn't match source repository
  - Prevents future packaging bugs where files are missing from distribution

### 📋 Migration for v0.10.12 Users

If you installed v0.10.12 from PyPI and upgraded from v0.10.11:
```bash
pip install --upgrade spec-kitty-cli
spec-kitty upgrade  # Run again to apply missing migration 0.10.12
```

The migration will remove mission-specific constitution directories:
- `.kittify/missions/software-dev/constitution/` → removed
- `.kittify/missions/research/constitution/` → removed
- Single project-level constitution: `.kittify/memory/constitution.md` (kept)

## [0.10.12] - 2026-01-12

### 🔒 Security (IMPORTANT)

- **Comprehensive adversarial review framework**
  - Expanded review template from 3 bullets (109 lines) to 12 scrutiny categories (505 lines)
  - **Security scrutiny now mandatory**: 10 detailed security subsections
  - **Mandatory verification**: 7 security grep commands must be run on EVERY review
  - **Automatic rejection** if any security check fails
  - **Impact**: All future features will have security-first reviews
  - **Rationale**: Prevents systematic quality issues (TODOs in prod, mocked implementations, security vulnerabilities)
  - See spec footnote and commit `61d7d01` for complete rationale

### 🐛 Fixed

- **Windows dashboard ERR_EMPTY_RESPONSE** (#71)
  - Replaced POSIX-only signal handling with cross-platform psutil library
  - `signal.SIGKILL` and `signal.SIGTERM` don't exist on Windows
  - Added `psutil>=5.9.0` dependency for cross-platform process management
  - Refactored `src/specify_cli/dashboard/lifecycle.py`:
    - `os.kill(pid, 0)` → `psutil.Process(pid).is_running()`
    - `signal.SIGKILL` → `psutil.Process(pid).kill()` (6 locations)
    - `signal.SIGTERM` → `psutil.Process(pid).terminate()` with timeout
  - Added proper exception handling (NoSuchProcess, AccessDenied, TimeoutExpired)
  - Dashboard now starts, serves HTML, and stops cleanly on Windows 10/11
  - All 41 dashboard tests passing

- **Upgrade migration failures** (#70)
  - Fixed `m_0_7_3_update_scripts.py` to handle missing bash scripts gracefully
  - Fixed `m_0_10_6_workflow_simplification.py` to copy templates before validation
  - Fixed `m_0_10_2_update_slash_commands.py` to explicitly remove legacy .toml files
  - Fixed `m_0_10_0_python_only.py` to explicitly remove `.kittify/scripts/tasks/`
  - Created `m_0_10_12_constitution_cleanup.py` to remove mission constitutions
  - All migrations now idempotent (safe to run multiple times)
  - Upgrade path from 0.6.4 → 0.10.12 now completes without manual intervention

- **Upgrade migration parameter mismatch** (#68 follow-up)
  - Fixed `m_0_10_9_repair_templates.py` migration calling `generate_agent_assets()` with wrong parameter name
  - Changed `ai=ai_config` to `agent_key=ai_config` to match function signature

### ♻️ Refactored

- **Template source relocation** (Safe dogfooding - Critical)
  - Moved ALL template sources from `.kittify/` to `src/specify_cli/`
  - Templates: `.kittify/templates/` → `src/specify_cli/templates/`
  - Missions: `.kittify/missions/` → `src/specify_cli/missions/`
  - Scripts: `.kittify/scripts/` → `src/specify_cli/scripts/`
  - Updated `src/specify_cli/template/manager.py` to load from `src/` not `.kittify/`
  - Removed ALL `.kittify/*` force-includes from `pyproject.toml`
  - **Impact**: Spec-kitty developers can now safely dogfood spec-kitty without risk of packaging their filled-in constitutions
  - **Verification**: Building wheel produces ZERO `.kittify/` or `memory/constitution.md` entries
  - Package now only contains `src/specify_cli/` (proper Python packaging)

- **Mission-specific constitutions removed**
  - Removed `mission.constitution_dir` property from `src/specify_cli/mission.py`
  - Removed constitution scanning from `src/specify_cli/manifest.py`
  - Deleted all `missions/*/constitution/` directories
  - **Impact**: Single project-level constitution model (`.kittify/memory/constitution.md`)
  - **Migration**: `m_0_10_12_constitution_cleanup.py` removes mission constitutions from user projects
  - Eliminates confusion about which constitution applies

## [0.10.11] - 2026-01-07

### 🐛 Fixed

- **Upgrade migration parameter mismatch** (#68 follow-up)
  - Fixed `m_0_10_9_repair_templates.py` migration calling `generate_agent_assets()` with wrong parameter name
  - Changed `ai=ai_config` to `agent_key=ai_config` to match function signature
  - Corrected parameter order to match function definition
  - **Root cause**: Migration was using deprecated parameter name, blocking users from upgrading to 0.10.11
  - **Impact**: Users unable to run `spec-kitty upgrade` to get template fixes from 0.10.11

## [0.10.11] - 2026-01-07

### 🐛 Fixed

- **Deprecated script references in mission templates** (#68)
  - Fixed `.kittify/missions/software-dev/templates/task-prompt-template.md` to use workflow commands instead of deprecated `python3 .kittify/scripts/tasks/tasks_cli.py`
  - Fixed `.kittify/templates/task-prompt-template.md` with same update
  - Fixed `.kittify/missions/software-dev/command-templates/tasks.md` to reference workflow commands
  - Updated `.kittify/templates/POWERSHELL_SYNTAX.md` to document spec-kitty CLI instead of obsolete PowerShell scripts
  - **Root cause**: Migration 0.10.9 fixed agent command templates but missed mission-specific templates
  - **Impact**: Agents were executing users' local `cli.py` files instead of spec-kitty CLI on Windows

### ✨ Added

- **Template compliance tests** - Prevent deprecated script references
  - `test_no_deprecated_script_references()` - Detects old `.kittify/scripts/` paths in templates
  - `test_templates_use_spec_kitty_cli()` - Ensures templates reference spec-kitty CLI commands
  - Tests run on all mission templates and global templates
  - Prevents regression of issue #68

## [0.10.10] - 2026-01-06

### 🐛 Fixed

- **Windows UTF-8 encoding error in agent commands** (#66)
  - Fixed `'charmap' codec can't encode characters` error on Windows
  - `spec-kitty agent feature create-feature` now works correctly on Windows
  - Added UTF-8 stdout/stderr reconfiguration in main() entry point
  - Handles Unicode characters in git output and error messages
  - Gracefully falls back for Python < 3.7

## [0.10.9] - 2026-01-06

### 🐛 Fixed

- **CRITICAL: Wrong templates bundled in PyPI packages** (#62, #63, #64)
  - Fixed pyproject.toml to bundle .kittify/templates/ instead of outdated /templates/
  - Removed outdated /templates/ directory entirely to prevent confusion
  - All PyPI installations now receive correct Python CLI templates
  - No more bash script references in command templates
  - Migration 0.10.0 now handles missing templates gracefully
  - Added package bundling validation tests to prevent regression

- **Template divergence eliminated**
  - 10 of 13 command templates were outdated in /templates/
  - implement.md was 199 lines longer in old location (277 vs 78 lines)
  - Git hooks were missing (1 vs 3)
  - claudeignore-template was missing

- **All 12 AI agent integrations fixed**
  - Claude Code, GitHub Copilot, Cursor, Gemini, Qwen Code, OpenCode, Windsurf,
    GitHub Codex, Kilocode, Augment Code, Roo Cline, Amazon Q
  - All agents now receive correct Python CLI slash commands

### ✨ Added

- **Repair migration (0.10.9_repair_templates)** - Automatically fixes broken installations
  - Detects projects with broken template references
  - Regenerates all agent slash commands from correct templates
  - Runs automatically during `spec-kitty upgrade`
  - Verifies repair was successful

- **Package bundling validation tests** - Prevents future regressions
  - Validates correct templates are bundled in sdist and wheel
  - Checks for bash script references before release
  - Tests importlib.resources accessibility

### 📚 Migration & Upgrade Path

**For users with broken installations (issues #62, #63, #64):**

1. **Upgrade spec-kitty package:**
   ```bash
   pip install --upgrade spec-kitty-cli
   spec-kitty --version  # Should show 0.10.9
   ```

2. **Run upgrade to apply repair migration:**
   ```bash
   cd /path/to/your/project
   spec-kitty upgrade
   ```
   This will automatically detect and fix broken templates.

3. **Verify repair:**
   ```bash
   # Check for bash script references (should return nothing)
   grep -r "scripts/bash" .claude/commands/
   ```

**For new projects:**
- Automatically get correct templates from package
- No action needed

**For existing healthy projects:**
- Run `spec-kitty upgrade` to stay current
- No breaking changes

### 🔒 Breaking Changes

None - Fully backwards compatible. Existing projects will upgrade smoothly.

## [0.10.8] - 2025-12-30

### 🐛 Fixed

- **Critical: Constitution not copied to worktrees** (#46)
  - Moved `memory/` directory from root to `.kittify/memory/` where code expects it
  - Removed broken circular symlinks (`.kittify/memory` → `../../../.kittify/memory`)
  - Fixed `.kittify/AGENTS.md` to be real file instead of broken symlink
  - Fixed worktree.py symlink handling (check for symlink before trying rmtree)
  - Added migration to automatically fix existing projects
  - Worktrees now correctly access constitution from main repo

- **Migration system** (v0.10.8_fix_memory_structure)
  - Automatically moves `memory/` to `.kittify/memory/` in existing projects
  - Removes broken symlinks and creates proper structure
  - Updates worktrees to use correct paths
  - Handles both Unix symlinks and Windows file copies

### 🔧 Changed

- **Directory structure standardization**
  - `memory/` → `.kittify/memory/` (matches `.kittify/scripts/`, `.kittify/templates/`)
  - `.kittify/AGENTS.md` is now a real file (not symlink)
  - All `.kittify/` resources now follow consistent pattern

## [0.10.7] - 2025-12-30

### 🐛 Fixed

- **Critical: Copilot initialization bug** (#53, fixes #61, #50)
  - Fixed NameError when running `spec-kitty init --ai copilot`
  - Changed `commands_dir` to `command_templates_dir` in asset_generator.py
  - Unblocks all users trying to initialize projects with Copilot

- **Critical: Dashboard contracts and checklists missing** (#59, fixes #52)
  - Restored contracts and checklists handlers that were lost in Nov 11 dashboard refactoring
  - Added generic `_handle_artifact_directory()` helper method
  - Both contracts and checklists now display correctly in dashboard
  - Fixed frontend to use full filepath instead of filename only

- **Critical: Windows UTF-8 encoding errors** (#56)
  - Added explicit `encoding='utf-8'` to read_text() calls
  - Fixes dashboard diagnostics showing "undefined" on Windows
  - Affects manifest.py and migration files
  - Windows defaults to cp1252, causing UnicodeDecodeError with UTF-8 content

- **Plan.md location validation** (#60)
  - Improved validation messaging in plan.md template
  - Added prominent ⚠️ STOP header for AI agents
  - Clearer examples of correct vs wrong worktree locations
  - Template-only change (no code modifications)

### 🔄 Closed

- PR #58 - Obsolete (PowerShell scripts deleted in v0.10.0)
- PR #57 - Obsolete (PowerShell scripts deleted in v0.10.0)
- PR #49 - Superseded by #59 (better architecture)
- PR #43 - Obsolete (PowerShell scripts deleted in v0.10.0)

## [0.10.6] - 2025-12-18

### ✨ Added

- **Workflow commands for simplified agent experience**
  - New `spec-kitty agent workflow implement [WP_ID]` command
  - New `spec-kitty agent workflow review [WP_ID]` command
  - Commands display full WP prompt directly to agents (no file navigation)
  - Auto-detect first planned/for_review WP when no ID provided
  - Auto-move WP to "doing" lane before displaying prompt
  - Show "WHEN YOU'RE DONE" instructions at top of output
  - Display source file path for easy re-reading
  - Prevents race conditions (two agents picking same WP)

### 🔧 Changed

- **Slash command template simplification**
  - implement.md: 78 lines → 11 lines (calls workflow command)
  - review.md: 72 lines → 11 lines (calls workflow command)
  - Templates now just run workflow commands instead of complex instructions
  - Agents see prompts immediately without navigation confusion

- **Consistent lane management**
  - Both implement and review workflows move WP to "doing" at start
  - Prevents ambiguity about which lane means "actively working"
  - Review workflow now supports auto-detect (no argument needed)

### 🐛 Fixed

- **Worktree path resolution**
  - Fixed `_find_first_planned_wp()` to work correctly in worktrees
  - Fixed `_find_first_for_review_wp()` to work correctly in worktrees
  - Auto-detect now finds WPs in worktree's kitty-specs/, not main repo

- **Legacy subdirectory cleanup**
  - Migrated features 007 and 010 from old subdirectory structure to flat structure
  - Moved 15 WP files from `tasks/done/phase-*/` to flat `tasks/`
  - All features now use proper flat structure with frontmatter-only lanes

## [0.9.4] - 2025-12-17

### 📚 Documentation & Validation

- **Prevent agent-created subdirectories in tasks/**
  - Added explicit warnings to tasks/README.md
  - Updated AGENTS.md with flat structure requirements
  - Updated /spec-kitty.tasks template to forbid subdirectories
  - Added runtime validation in check-prerequisites.sh
  - Blocks execution if phase-_, component-_, or any subdirectories found
  - Clear error messages with examples of correct vs wrong paths

This prevents Claude agents from creating organizational subdirectories like `tasks/phase-1/`, `tasks/backend/`, etc.

## [0.9.3] - 2025-12-17

### 🐛 Fixed

- **Critical symlink detection fix**
  - Now checks `is_symlink()` BEFORE `exists()` (exists() returns False for broken symlinks!)
  - Properly removes both working and broken symlinks from worktrees
  - Fixes remaining test failures in worktree cleanup migration
  - Handles all symlink scenarios correctly

This completes the fix for symlink removal in worktree cleanup.

## [0.9.2] - 2025-12-17

### 🐛 Fixed

- **Symlink handling in worktree cleanup**
  - Migration now properly detects and removes symlinks to command directories
  - Uses `unlink()` for symlinks instead of `shutil.rmtree()`
  - Fixes "Cannot call rmtree on a symbolic link" error during upgrade
  - Handles both symlinks and regular directories correctly

This fixes the upgrade failure when worktrees have symlinked agent command directories.

## [0.9.1] - 2025-12-17

### 🔧 Bug Fixes & Improvements

This release fixes critical issues found in v0.9.0 and adds version checking to prevent compatibility problems.

### 🆕 Added

- **Version compatibility checking**
  - CLI now checks for version mismatches between installed spec-kitty-cli and project version
  - Hard error with explicit instructions when versions don't match
  - Special critical warning for v0.9.0+ upgrade explaining breaking changes
  - Shows detailed before/after directory structure comparison
  - Version checks in all CLI commands and bash scripts
  - Graceful handling of legacy projects without metadata

- **Programmatic frontmatter management**
  - New `specify_cli.frontmatter` module for consistent YAML operations
  - Uses ruamel.yaml for absolute formatting consistency
  - No more manual YAML editing by LLMs or scripts
  - Prevents quoted vs unquoted value inconsistencies

### 🐛 Fixed

- **Migration improvements**
  - v0.9.0 migration now finds ALL markdown files (not just WP*.md)
  - Detects and removes empty lane subdirectories
  - Uses shutil.rmtree() for robust directory removal
  - Better detection of legacy format

- **Complete lane migration (v0.9.1)**
  - Migrates files missed by v0.9.0 (phase-_.md, task-_.md, etc.)
  - Removes ALL agent command directories from worktrees (.codex/prompts/, .gemini/commands/, etc.)
  - Removes .kittify/scripts/ from worktrees (inherit from main repo)
  - Normalizes all frontmatter to consistent YAML format
  - Fixes issue where worktrees had old command templates referencing deprecated scripts

- **Flat structure in new features**
  - Fixed create-new-feature.sh to create flat tasks/ directory (not subdirectories)
  - Updated README.md documentation to reflect v0.9.0+ structure
  - New features now work correctly with frontmatter-only lanes from day one

- **Lane validation**
  - tasks_cli.py update command now validates lane values
  - Rejects invalid lanes before processing
  - Clear error messages for invalid input

### 🔧 Changed

- Added `ruamel.yaml>=0.18.0` dependency for consistent YAML handling
- Updated success messages to reflect flat structure

### 🚀 Migration

If you upgraded to v0.9.0 and still have issues, run `spec-kitty upgrade` again to apply v0.9.1 fixes:
- Completes any remaining lane migrations
- Cleans up worktree command directories
- Normalizes all frontmatter for consistency

## [0.9.0] - 2025-12-17

### 🎯 Major Release: Frontmatter-Only Lane Management

This release fundamentally changes how Spec Kitty manages work package lanes, eliminating directory-based lane tracking in favor of a simpler, conflict-free frontmatter-only system.

### ⚠️ Breaking Changes

- **Lane system completely redesigned**
  - Work packages now live in a flat `kitty-specs/<feature>/tasks/` directory
  - Lane status determined **solely by `lane:` frontmatter field** (no more subdirectories)
  - Old system: `tasks/planned/WP01.md`, `tasks/doing/WP02.md` ❌
  - New system: `tasks/WP01.md` with `lane: "planned"` ✅

- **Command renamed: `move` → `update`**
  - Legacy `tasks_cli.py move` command removed
  - Use `tasks_cli.py update <feature> <WP> <lane>` instead
  - Semantic clarity: command updates metadata, doesn't move files
  - Legacy format detection: `update` command refuses to work on old directory-based structure

- **Direct frontmatter editing now supported**
  - You can now directly edit the `lane:` field in WP frontmatter
  - Previous "DO NOT EDIT" warnings removed from all templates
  - System recognizes manual lane changes immediately
  - No file movement required for lane transitions

### 🆕 Added

- **Migration command: `spec-kitty upgrade`**
  - Automatically migrates features from directory-based to frontmatter-only format
  - Preserves all lane assignments during migration
  - Idempotent: safe to run multiple times
  - Cleans up empty lane subdirectories after migration
  - Migrates both main repo and worktree features

- **Legacy format detection**
  - `is_legacy_format()` function detects old directory-based structure
  - CLI commands display helpful warnings when legacy format detected
  - Dashboard shows migration prompt for legacy features
  - Non-blocking: legacy features remain functional until migrated

- **Enhanced status command**
  - Better formatted output with lane grouping
  - Auto-detects feature from branch/worktree when not specified
  - Shows work packages organized by current lane
  - Works with both legacy and new formats

### 🔧 Changed

- **work package location logic**
  - `locate_work_package()` now searches flat `tasks/` directory first
  - Falls back to legacy subdirectory search for backwards compatibility
  - Exact WP ID matching (WP04 won't match WP04b)

- **Lane extraction utilities**
  - New `get_lane_from_frontmatter()` function extracts lane from YAML
  - Defaults to "planned" when `lane:` field missing
  - Validates lane values against allowed set
  - Available in both `task_helpers.py` and `tasks_support.py`

- **Dashboard scanner updates**
  - Reads lane from frontmatter instead of directory location
  - Displays legacy format warnings
  - Works seamlessly with both formats during transition

- **Activity log behavior**
  - Lane transitions still append activity log entries
  - Captures agent, shell PID, and timestamp
  - No file movement logged (because no movement occurs)

### 📚 Documentation

- **Updated all templates**
  - `.kittify/templates/task-prompt-template.md` - Removed "DO NOT EDIT" warnings
  - `.kittify/templates/tasks-template.md` - Updated for flat structure
  - `.kittify/templates/AGENTS.md` - New lane management instructions
  - `tasks/README.md` - Rewritten for flat directory layout

- **Updated mission templates**
  - All mission-specific templates updated (software-dev, research)
  - Command templates updated (`implement.md`, `review.md`, `merge.md`)
  - Examples updated to show new workflow

- **Updated main documentation**
  - `README.md` - Updated quick start examples
  - `docs/quickstart.md` - New lane management workflow
  - `docs/multi-agent-orchestration.md` - Updated collaboration examples
  - All `examples/` updated with new commands

### 🧪 Testing

- 286 tests passing (0 failures)
- New tests for frontmatter-only lane system
- Legacy format detection tests
- Migration command tests
- Dual-format compatibility tests

### 🚀 Migration Guide

**For existing projects:**

1. **Back up your work** (commit changes, push to remote)
2. **Run migration**: `spec-kitty upgrade`
3. **Verify**: `spec-kitty status --feature <your-feature>`
4. **Update workflows**: Replace `move` with `update` in scripts/docs

**Key benefits of upgrading:**

- ✅ No file conflicts during lane changes (especially in worktrees)
- ✅ Direct editing of `lane:` field supported
- ✅ Better multi-agent compatibility
- ✅ Simpler mental model (one directory, not four)
- ✅ Fewer git operations per lane change

**Legacy format still works** - You can continue using old directory structure until ready to migrate. All commands detect format automatically.

### 🐛 Fixed

- File conflicts during simultaneous lane changes by multiple agents
- Git staging issues with lane transitions
- Race conditions in worktree-based parallel development
- Lane mismatch validation errors (no longer possible with frontmatter-only)

### 🔗 Related

- Feature implementation: `007-frontmatter-only-lane`
- All 6 work packages completed and reviewed
- Comprehensive test coverage added

---

## [0.8.2] - 2025-12-17

### Added

- **Task lane management documentation** - Added clear instructions to AGENTS.md and task templates warning agents never to manually edit the `lane:` YAML field
  - Lane is determined by directory location, not YAML field
  - Editing `lane:` without moving the file creates a mismatch that breaks the system
  - All templates now include YAML comment: `# DO NOT EDIT - use: workflow commands` (legacy note)
  - Added "Task Lane Management Rule" section to project AGENTS.md

## [0.8.1] - 2025-12-17

### Fixed

- **work package move race conditions** - Multiple agents can now work on different WPs simultaneously without blocking each other
  - Conflict detection now only blocks on changes to the same WP, not unrelated WP files
  - Agents working on WP05 no longer block moves of WP04

- **Exact WP ID matching** - `WP04` no longer incorrectly matches `WP04b`
  - Changed from prefix matching to exact boundary matching
  - Pattern now requires WP ID to be followed by `-`, `_`, `.`, or end of filename

- **Cleanup no longer leaves staged deletions** - Stale copy cleanup uses filesystem delete instead of `git rm`
  - Prevents orphaned staged deletions from blocking subsequent operations
  - Automatically unstages any previously staged changes to cleaned files

## [0.8.0] - 2025-12-15

### Breaking Changes

- **Mission system refactored to per-feature model**
  - Missions are now selected during `/spec-kitty.specify` instead of `spec-kitty init`
  - Each feature stores its mission in `meta.json` (field: `"mission": "software-dev"`)
  - `.kittify/active-mission` symlink/file is no longer used
  - Run `spec-kitty upgrade` to clean up existing projects

- **Removed commands**
  - `spec-kitty mission switch` - Missions are now per-feature, not per-project
  - Running this command now shows a helpful error message explaining the new workflow

- **Removed flags**
  - `--mission` flag from `spec-kitty init` - Use `/spec-kitty.specify` instead
  - Flag is hidden but shows deprecation warning if used

### Added

- **Mission inference during `/spec-kitty.specify`** - LLM analyzes feature description and suggests appropriate mission:
  - "Build a REST API" → suggests `software-dev`
  - "Research best practices" → suggests `research`
  - User confirms or overrides the suggestion
  - Explicit `--mission` flag bypasses inference

- **Per-feature mission storage** - Selected mission stored in feature's `meta.json`:
  - All downstream commands read mission from feature context
  - Legacy features without mission field default to `software-dev`

- **Mission discovery** - New `discover_missions()` function returns all available missions with source indicators

- **Updated `spec-kitty mission list`** - Shows source column (project/built-in) for each mission

- **Migration for v0.8.0** - `spec-kitty upgrade` removes obsolete `.kittify/active-mission` file

- **AGENTS.md worktree fix** - New worktrees get AGENTS.md symlink, and `spec-kitty upgrade` fixes existing worktrees

### Changed

- All downstream commands (`/spec-kitty.plan`, `/spec-kitty.tasks`, `/spec-kitty.implement`, `/spec-kitty.review`, `/spec-kitty.accept`) now read mission from feature's `meta.json`
- `create-new-feature.sh` accepts `--mission <key>` parameter to set mission in meta.json
- Common bash/PowerShell scripts updated to resolve mission from feature directory
- `spec-kitty mission current` shows current default mission (for informational purposes)
- Dashboard template now includes dynamic AGENTS.md path discovery instructions

### Deprecated

- `set_active_mission()` function - Shows deprecation warning, will be removed in future version

### Migration Guide

1. Run `spec-kitty upgrade` to remove `.kittify/active-mission`
2. Existing features without `mission` field will use `software-dev` by default
3. New features will have mission set during `/spec-kitty.specify`

## [0.7.4] - 2025-12-14

### Added

- **Script Update Migration** – `spec-kitty upgrade` now updates project scripts:
  - Copies latest `create-new-feature.sh` from package to project
  - Fixes worktree feature numbering bug in existing projects
  - Previously, projects kept old scripts from when they were initialized

## [0.7.3] - 2025-12-14

### Fixed

- **Duplicate Feature Numbers with Worktrees** – Script now scans both `kitty-specs/` AND `.worktrees/` for existing feature numbers:
  - Previously only scanned `kitty-specs/` which was empty when using worktrees
  - This caused new features to get `001` even when `001-*` worktree already existed
  - Now correctly finds highest number across both locations

## [0.7.2] - 2025-12-14

### Fixed

- **Duplicate Slash Commands in Worktrees (Corrected)** – Fixed the fix from v0.7.1:
  - v0.7.1 incorrectly removed commands from main repo (broke `/` commands there)
  - v0.7.2 removes commands from **worktrees** instead (they inherit from main repo)
  - Claude Code traverses UP, so worktrees find main repo's `.claude/commands/`
  - main repo keeps commands, worktrees don't need their own copy

## [0.7.1] - 2025-12-14 [YANKED]

### Fixed

- ~~Duplicate Slash Commands in Worktrees~~ – **Incorrect fix, replaced by v0.7.2**

## [0.7.0] - 2025-12-14

### Added

- **`spec-kitty upgrade` Command** – Automatically migrate existing projects to current version:
  - Detects project version via metadata or directory structure heuristics
  - Applies all necessary migrations in order (0.2.0 → 0.6.7)
  - Auto-upgrades worktrees alongside main project
  - Supports `--dry-run`, `--verbose`, `--json`, `--target`, `--no-worktrees` options
  - Tracks applied migrations in `.kittify/metadata.yaml`
  - Idempotent - safe to run multiple times

- **Migration System** – Five automatic migrations for project structure updates:
  - `0.2.0`: `.specify/` → `.kittify/` directory rename
  - `0.4.8`: Add all 12 agent directories to `.gitignore`
  - `0.5.0`: Install encoding validation git hooks
  - `0.6.5`: `commands/` → `command-templates/` rename
  - `0.6.7`: Ensure software-dev and research missions are present

- **Broken Mission Detection** – `VersionDetector.detect_broken_mission_system()` identifies corrupted mission.yaml files

- **Migration Registry Validation** – Duplicate migration IDs and missing required fields now raise `ValueError`

### Fixed

- **Test Timeout in Dashboard CLI Tests** – Reduced port cleanup from 763 ports to 8 specific test ports
- **Playwright Window Handling** – Tests now open new windows (not tabs) and close properly on exit

## [0.6.7] - 2025-12-13

### Fixed

- **Missing software-dev Mission in PyPI Package** – Fixed build configuration to include all missions:
  - Added explicit sdist include patterns to pyproject.toml
  - The `software-dev` mission was missing from v0.6.5 and v0.6.6 wheel builds
  - Root cause: `force-include` only applied to wheel target, not sdist (wheel was built from sdist)
  - Now both `software-dev` and `research` missions are correctly packaged

## [0.6.6] - 2025-12-13

### Fixed

- **Test Suite Updated for 12 Agent Directories** – All tests now expect 12 agents (added `.github/copilot/`):
  - Updated `test_init_flow.py`, `test_gitignore_management.py`, `test_gitignore_manager_simple.py`
  - Updated `tests/unit/test_gitignore_manager.py` to expect 12 agents
  - Fixed template manager tests to use new `.kittify/` source paths

### Changed

- **Template Source Paths** – Tests now use correct `.kittify/templates/command-templates/` paths

## [0.6.5] - 2025-12-13

### Added

- **Pre-commit Git Hooks** – Automatic protection against committing agent directories:
  - Blocks commits containing `.claude/`, `.codex/`, `.gemini/`, etc.
  - Warns about `.github/copilot/` (nested in `.github/` which is usually committed)
  - Installed automatically during `spec-kitty init`

- **GitHub Copilot Directory Protection** – Added `.github/copilot/` as 12th protected agent directory

- **.claudeignore Generation** – Optimizes Claude Code token usage by excluding templates

### Fixed

- **Worktree Constitution Symlinks** – Feature worktrees now share constitution via symlink
- **Git Hooks Installation Timing** – Hooks now install after `.git/` is created

## [0.6.4] - 2025-11-26

### Fixed

- **Agent Commands Missing in Worktrees** – Slash commands now work in all feature worktrees for all AI agents:
  - `create-new-feature.sh` now symlinks agent command directories from main repo to worktrees
  - Supports all 12 agent types: Claude, Gemini, Copilot, Cursor, Qwen, OpenCode, Windsurf, Codex, KiloCode, Auggie, Roo, Amazon Q
  - Fixes `/spec-kitty.research`, `/spec-kitty.plan`, and all other slash commands in worktrees
  - Existing worktrees get symlinks added when reused (backward compatible)
  - Root cause: worktrees are separate working directories that don't share `.claude/commands/` etc.

## [0.6.3] - 2025-11-25

### Fixed

- **Mission Directory Not Copied During Init** – Projects initialized with `spec-kitty init` now correctly receive mission templates:
  - Fixed `copy_specify_base_from_package()` to look at correct path `specify_cli/missions` (matching pyproject.toml)
  - Previously looked at wrong paths: `.kittify/missions` and `template_data/missions`
  - `software-dev` mission was missing from initialized projects, breaking `/spec-kitty.plan` and other commands
  - Root cause: pyproject.toml packages missions to `specify_cli/missions` but code looked elsewhere

## [0.6.2] - 2025-11-18

### Fixed

- **PowerShell Wrapper Parameter Handling** – Windows lane transitions now work correctly:
  - Fixed legacy `tasks-move-to-lane.ps1` to properly parse named PowerShell parameters
  - Translates Spec Kitty's named params (`-FeatureName`, `-TaskId`, `-TargetLane`) to `tasks_cli.py` positional args
  - Resolves `unrecognized arguments` error that broke `/spec-kitty.review` on Windows
  - Maintains backward compatibility with positional argument usage
  - Fixes #34

## [0.6.1] - 2025-11-18

### Fixed

- **Untracked Task File Moves** – Task move workflow now handles untracked files:
  - Added `is_file_tracked()` helper to detect if file is in git index
  - Move command automatically stages untracked source files before moving
  - Fixes `/spec-kitty.implement` failures when `/spec-kitty.tasks` doesn't commit
  - Provides clear feedback: `[spec-kitty] Added untracked file: ...`
  - Defensive fix works with both existing untracked files and future workflows

## [0.6.0] - 2025-11-16

### Fixed

- **Dashboard Constitution Tracking** – Feature-level constitution.md files now tracked and displayed:
  - Added constitution to scanner artifact list
  - Constitution appears in overview with ⚖️ icon
  - Frontend properly detects constitution.exists property

- **Dashboard Modification Detection** – Dashboard now detects file modifications, not just existence:
  - Scanner returns {exists, mtime, size} for each artifact instead of boolean
  - Frontend updated to use .exists property with optional chaining
  - Overview auto-reloads when artifacts change during polling
  - No manual refresh required to see new/modified files

- **Dashboard Project Constitution Endpoint** – Project constitution now loads in dashboard:
  - Added /api/constitution endpoint to serve .kittify/memory/constitution.md
  - Sidebar Constitution link now displays file content instead of "not found"
  - Separate from feature-level constitution tracking

- **work package Conflict Detection Too Strict** – Moving WP no longer blocked by unrelated WP changes:
  - Conflict detection now scoped to same work package ID only
  - Moving WP04 no longer fails if WP06/WP08 have uncommitted changes
  - Reduces false positives from ~90% to ~5%
  - Agents don't need --force for unrelated work packages
  - Still catches real conflicts (same WP in multiple lanes)

- **Accept Command Over-Questioning** – Acceptance workflow now auto-detects instead of asking:
  - feature slug auto-detected from git branch
  - Mode defaults to 'local' (most common)
  - Validation commands searched in git log
  - Only asks user if auto-detection fails
  - Reduces user questions from 3-4 to 0 in typical case

- **Init Command Blocking on Optional Tools** – Project init no longer fails on missing agent tools:
  - Changed from red error + exit(1) to yellow warning + continue
  - Gemini CLI and other tools are optional
  - Users can install tools later without re-init
  - --ignore-agent-tools flag still available but rarely needed

- **Encoding Normalization Incomplete** – Unicode smart quotes now properly normalized to ASCII:
  - Added character mapping for 12 common Unicode characters
  - Smart quotes (U+2018/U+2019) → ASCII apostrophe
  - Em/en dashes → hyphens
  - Ellipsis, bullets, nbsp → ASCII equivalents
  - --normalize-encoding now produces true ASCII output

### Changed

- **Mission Display Simplified** – Reduced verbose mission card to single line:
  - Removed domain label, version number, path display
  - Removed redundant refresh button (auto-updates every second)
  - Changed from card layout to inline text: "Mission: {name}"
  - Cleaner, less cluttered header

### Added

- **Mission System Architecture** – Complete mission-based workflow system (feature 005):
  - Guards module for pre-flight validation
  - Pydantic mission schema validation
  - Mission CLI commands (list, current, switch, info)
  - Research mission templates and citation validators
  - Path convention validation
  - Dashboard mission display
  - Comprehensive integration tests

## [0.5.3] - 2025-11-15

### Fixed

- **Dashboard Orphaned Process Cleanup** – Fixed dashboard startup failures caused by orphaned test processes:
  - Dashboard now detects and cleans up orphaned processes when health check fails due to project path mismatch
  - Added retry logic after successful orphan cleanup
  - Orphan cleanup triggers on health check failure (not just port exhaustion)
  - Eliminates false "Unable to start dashboard" errors when orphaned test dashboards occupy ports

- **Dashboard Subprocess Import Failure** – Fixed ModuleNotFoundError in complex Python environments:
  - Dashboard subprocess now always inserts spec-kitty path at sys.path[0]
  - Fixes import failures when user's PYTHONPATH or .pth files contain spec-kitty path at lower priority
  - Ensures correct spec-kitty installation takes precedence over environment paths
  - Resolves "ModuleNotFoundError: No module named 'specify_cli.dashboard'" in subprocesses

### Changed

- **Test Suite Cleanup Improvements** – Enhanced dashboard test cleanup to prevent orphaned processes:
  - Module-level cleanup fixture kills all orphaned dashboards before and after test runs
  - Expanded cleanup port range from 9992-9999 to 9237-10000 (covers default and test ranges)
  - Added `kill_all_spec_kitty_dashboards()` helper using pgrep/pkill
  - Two-tier cleanup strategy: module-level (all processes) + function-level (specific ports)

### Added

- **Testing Guidelines for Agents** (`docs/testing-guidelines.md`) – Comprehensive testing best practices:
  - Required cleanup patterns for dashboard tests (pytest fixtures, autouse fixtures)
  - Anti-patterns to avoid (cleanup in test body, shared directories, no exception handling)
  - Impact analysis of orphaned processes on local development and CI/CD
  - Examples of proper test isolation and resource management

### Changed

- **Command Consolidation** – Merged `spec-kitty check` and `spec-kitty diagnostics` into `spec-kitty verify-setup`:
  - Removed redundant `spec-kitty check` and `spec-kitty diagnostics` commands
  - Tool checking now integrated into `verify-setup` with `--check-tools` flag (default: enabled)
  - Diagnostics mode with dashboard health available via `--diagnostics` flag
  - Removed ASCII banner from verify-setup for cleaner output
  - Simplifies CLI interface - single command for all environment verification
  - JSON output includes tool availability when `--check-tools` is enabled

### Removed

- **`spec-kitty check` command** – Functionality moved to `verify-setup --check-tools`
  - Migration: Use `spec-kitty verify-setup` instead of `spec-kitty check`
  - Tool checking enabled by default, disable with `--check-tools=false`
- **`spec-kitty diagnostics` command** – Functionality moved to `verify-setup --diagnostics`
  - Migration: Use `spec-kitty verify-setup --diagnostics` instead of `spec-kitty diagnostics`
  - Shows Rich panel-based output with dashboard health, observations, and issues

## [0.5.2] - 2025-11-14

### Fixed

- **Dashboard Startup Race Condition** – Fixed root cause of dashboard health check timing out prematurely:
  - Increased health check timeout from 10 to 20 seconds with exponential backoff
  - Retry pattern: 10×100ms, 40×250ms, 20×500ms for adaptive performance
  - Removed workaround fallback check that was masking the real issue
  - Eliminated false "Unable to start dashboard" errors on slower systems

### Changed

- **Dashboard Health Check Strategy** – Improved reliability with exponential backoff:
  - Quick initial checks (100ms) for fast systems
  - Gradual slowdown (250ms then 500ms) for slower systems
  - Total timeout increased to ~20 seconds for adequate startup time
  - Cleaner error handling without port-scanning fallback

### Added

- **Symlinked kitty-specs Test Coverage** – New test validates dashboard works with worktree structure:
  - Tests scenario from bug report (symlinked `kitty-specs/` to `.worktrees/`)
  - Ensures dashboard starts correctly with symlinked directories
  - Prevents regression of false error reporting

## [0.5.1] - 2025-11-14

### Added

- **Task Metadata Validation Guardrail** – Prevents workflow failures when file locations don't match frontmatter:
  - Auto-detects lane mismatches (file in `for_review/` but `lane: "planned"`)
  - CLI command: `spec-kitty validate-tasks --fix`
  - Integrated into `/spec-kitty.review` workflow (auto-runs before review)
  - Adds activity log entries documenting all repairs
  - Validates required fields (work_package_id, lane) and formats
- **Task Metadata Validation Module** (`src/specify_cli/task_metadata_validation.py`) – Core validation:
  - `detect_lane_mismatch()` - Finds directory/frontmatter inconsistencies
  - `repair_lane_mismatch()` - Auto-fixes with audit trail
  - `validate_task_metadata()` - Comprehensive field validation
  - `scan_all_tasks_for_mismatches()` - Feature-wide scanning

### Changed

- **Version Reading** – Now reads dynamically from package metadata instead of hardcoded value:
  - Uses `importlib.metadata.version()` to get actual installed version
  - `spec-kitty --version` always shows correct version
  - No manual updates needed in `__init__.py`
- **Review Workflow** – Added automatic task metadata validation before review:
  - Runs `spec-kitty validate-tasks --fix` automatically
  - Prevents agents getting stuck on lane mismatches
  - Documented in `.claude/commands/spec-kitty.review.md`

### Fixed

- **Dashboard CLI False Error** – CLI no longer reports "Unable to start dashboard" when dashboard actually started successfully. Added fallback verification to check if dashboard is accessible before reporting failure. Handles race condition where health check times out but server is functional.
- **Review Workflow Blocking** – Review command no longer fails when file locations don't match frontmatter metadata. Auto-validation repairs inconsistencies before review.
- **Hardcoded Version** – `spec-kitty --version` now reads from package metadata, always shows correct installed version.

### Documentation

- **task-metadata-validation.md** (350 lines) – Auto-repair workflow:
  - Lane mismatch detection and repair
  - CLI usage examples
  - Python API reference
  - Integration with review workflow

### Testing

- Added version detection tests to prevent future hardcoded version bugs
- Task metadata validation tested with real frontmatter/directory mismatches
- All tests passing (13/13)

## [0.5.0] - 2025-11-13

### Added

- **Encoding Validation Guardrail** – Comprehensive 5-layer defense system to prevent Windows-1252 characters from crashing the dashboard:
  - **Layer 1**: Dashboard auto-fixes encoding errors on read (server-side resilience)
  - **Layer 2**: Character sanitization module with 15+ problematic character mappings
  - **Layer 3**: CLI command `spec-kitty validate-encoding` with `--fix` flag
  - **Layer 4**: Pre-commit hook that blocks commits with encoding errors
  - **Layer 5**: Enhanced AGENTS.md with real crash examples and character blacklist
- **Plan Validation Guardrail** – Prevents agents from skipping the planning phase:
  - Detects 11 template markers in plan.md (threshold: 5+ markers = unfilled)
  - Blocks `/spec-kitty.research` command when plan is unfilled
  - Blocks `/spec-kitty.tasks` via check-prerequisites.sh
  - Clear error messages with remediation steps
- **Character Sanitization Module** (`src/specify_cli/text_sanitization.py`) – Core module for encoding fixes:
  - Maps smart quotes (`' ' " "`) → ASCII (`' "`)
  - Maps plus-minus (`±`) → `+/-`, multiplication (`×`) → `x`, degree (`°`) → `degrees`
  - Supports dry-run mode and automatic backup creation
  - Directory-wide sanitization with glob patterns
- **Plan Validation Module** (`src/specify_cli/plan_validation.py`) – Template detection:
  - Configurable threshold (default: 5 markers)
  - Line-precise error reporting
  - Strict and lenient validation modes

### Changed

- **Version Reading** – Now reads dynamically from package metadata instead of hardcoded value:
  - Uses `importlib.metadata.version()` to get actual installed version
  - `spec-kitty --version` always shows correct version
  - No manual updates needed in `__init__.py`
- **Review Workflow** – Added automatic task metadata validation before review:
  - Runs `spec-kitty validate-tasks --fix` automatically
  - Prevents agents getting stuck on lane mismatches
  - Documented in `.claude/commands/spec-kitty.review.md`
- **Dashboard Scanner** – Now resilient to encoding errors:
  - Auto-fixes files on read with backup creation
  - Creates error cards instead of crashing on bad files
  - Logs encoding issues with clear error messages
- **Research Command** – Added plan validation gate before allowing research artifact creation
- **Prerequisites Check Script** – Added bash-based plan validation (35 lines)
- **AGENTS.md Template** – Enhanced with encoding warnings:
  - Real crash examples from production
  - Explicit character blacklist with Unicode codepoints
  - Auto-fix workflow documentation

### Fixed

- **Dashboard Blank Page Issue** – Dashboard no longer crashes when markdown files contain Windows-1252 smart quotes, ±, ×, ° symbols. Auto-fix sanitizes files on first read.
- **Agents Skipping Planning** – Research and tasks commands now blocked until plan.md is properly filled out (not just template).
- **Review Workflow Blocking** – Review command no longer fails when file locations don't match frontmatter metadata. Auto-validation repairs inconsistencies before review.
- **Hardcoded Version** – `spec-kitty --version` now reads from package metadata, always shows correct installed version.

### Documentation

- **encoding-validation.md** (554 lines) – Complete guide covering:
  - Problem description with real examples
  - 5-layer architecture explanation
  - Testing procedures and troubleshooting
  - Migration guide for existing projects
  - API reference and performance considerations
- **plan-validation-guardrail.md** (202 lines) – Implementation details:
  - Problem and solution overview
  - Configuration instructions
  - Testing procedures
  - Benefits and future enhancements
- **task-metadata-validation.md** (350 lines) – Auto-repair workflow:
  - Lane mismatch detection and repair
  - CLI usage examples
  - Python API reference
  - Integration with review workflow
- **TESTING_REQUIREMENTS_ENCODING_AND_PLAN_VALIDATION.md** (1056 lines) – Functional test specifications:
  - 35+ test cases across 6 test suites
  - Coverage targets (85-95%)
  - Performance requirements
  - Edge case testing requirements

### Testing

- Added 7 unit tests for plan validation (all passing)
- Verified on real project (battleship): fixed 9 files with encoding issues
- Dashboard now loads successfully after encoding fixes
- Character mapping tests: smart quotes, ±, ×, ° all converted correctly

## [0.4.13] - 2025-11-13

### Fixed

- **CRITICAL: verify-setup ImportError (Issue #28)** – Fixed ImportError in `verify-setup` command caused by incorrect import statement in `verify_enhanced.py`. Changed `from . import detect_feature_slug, AcceptanceError` to `from .acceptance import detect_feature_slug, AcceptanceError`. This was a blocking bug that prevented users from running the diagnostic command.

## [0.4.12] - 2025-11-13

### Added

- **Version Flag** – Added `--version` and `-v` flags to display installed spec-kitty-cli version.
- **Dashboard Health Diagnostics** – Enhanced `spec-kitty diagnostics` to detect dashboard startup failures, test if dashboard can start, and report specific errors. Now catches issues like corrupted files, health check timeouts, and background process failures.

### Changed

- **Diagnostics Output** – Added Dashboard Health panel showing startup test results, PID tracking status, and specific failure reasons.

## [0.4.11] - 2025-11-13

### Fixed

- **PowerShell Python Quoting Bug (Issue #26)** – Fixed SyntaxError in PowerShell scripts caused by double-quote conflicts in embedded Python code. Changed all Python strings in `common.ps1` to use single quotes to avoid PowerShell string parsing conflicts.

### Added

- **PowerShell Syntax Guide** – Created comprehensive `templates/POWERSHELL_SYNTAX.md` with bash vs PowerShell syntax comparison table, common mistakes, and debugging tips for AI agents.
- **Conditional PowerShell Reference** – Enhanced `agent-file-template.md` to conditionally include PowerShell syntax reminders only for PowerShell projects, keeping bash contexts clean.

### Changed

- **AI Agent Context** – PowerShell-specific guidance now provided via separate reference document instead of cluttering bash-focused templates.

Fixes #26
Addresses #27

## [0.4.10] - 2025-11-13

### Fixed

- **CRITICAL: Missing missions directory in PyPI package** – Added `.kittify/missions/` to `pyproject.toml` force-include list. Previous release (0.4.9) was missing this directory, causing "Active mission directory not found" errors for all fresh installations.

## [0.4.9] - 2025-11-13

### Added

- **Diagnostics CLI Command** – New `spec-kitty diagnostics` command with human-readable and JSON output for comprehensive project health checks.
- **Dashboard Process Tracking** – Dashboard now stores process PID in `.dashboard` metadata file for reliable cleanup and monitoring.
- **Feature Collision Detection** – Added explicit warnings when creating features with duplicate names that would overwrite existing work.
- **LLM Context Documentation** – Enhanced all 13 command templates with location pre-flight checks, file discovery sections, and workflow context to prevent agents from getting lost.

### Changed

- **Dashboard Lifecycle** – Enhanced `ensure_dashboard_running()` to automatically clean up orphaned dashboard processes on initialization, preventing port exhaustion.
- **Feature Creation Warnings** – `create-new-feature.sh` now warns when git is disabled or features already exist, with clear JSON indicators for LLM agents.
- **Import Safety** – Fixed `detect_feature_slug` import path in diagnostics module to use correct module location.
- **Worktree Documentation** – Updated WORKTREE_MODEL.md to accurately describe `.kittify/` as a complete copy (not symlink) with disk space implications documented.

### Fixed

- **CRITICAL: Dashboard Process Orphan Leak** – Fixed critical bug where background dashboard processes were orphaned and accumulated until all ports were exhausted. Complete fix includes:
  - PIDs are captured and stored in `.dashboard` file (commit b8c7394)
  - Orphaned processes with .dashboard files are automatically cleaned up on next init
  - HTTP shutdown failures fall back to SIGTERM/SIGKILL with PID tracking
  - Port range cleanup scans for orphaned dashboards without .dashboard files (commit 11340a4)
  - Safe fingerprinting via health check API prevents killing unrelated services
  - Automatic retry with cleanup when port exhaustion detected
  - Failed startup processes are cleaned up (no orphans from Ctrl+C during health check)
  - Multi-project scenarios remain fully isolated (per-project PIDs, safe port sweeps)
  - Handles all orphan types: with metadata, without metadata, deleted temp projects
  - Prevents "Could not find free port" errors after repeated uses

- **Import Path Bug** – Fixed `detect_feature_slug` import in `src/specify_cli/dashboard/diagnostics.py` to import from `specify_cli.acceptance` instead of package root.

- **Worktree Documentation Accuracy** – Corrected WORKTREE_MODEL.md which incorrectly stated `.kittify/` was symlinked; it's actually a complete copy due to git worktree behavior.

### LLM Context Improvements

All command templates enhanced with consistent context patterns:
- **Location Pre-flight Checks**: pwd/git branch verification with expected outputs and correction steps
- **File Discovery**: Lists what files {SCRIPT} provides, output locations, and available context
- **Workflow Context**: Documents before/after commands and feature lifecycle integration

Templates updated:
- merge.md: CRITICAL safety check preventing merges from wrong location
- clarify.md, research.md, analyze.md: HIGH priority core workflow commands
- specify.md, checklist.md: Entry point and utility commands
- constitution.md, dashboard.md: Project-level and monitoring commands

### Testing

- ✅ Dashboard comprehensive test suite (34 tests, 100% coverage)
- ✅ All CLI commands validated
- ✅ Import paths verified
- ✅ Worktree behavior confirmed across test scenarios
- ✅ LLM context patterns applied consistently

### Security

- Dashboard process cleanup prevents resource exhaustion attacks
- Explicit warnings when creating duplicate features prevent silent data overwrite
- Git disabled warnings ensure users know when version control is unavailable

### Backward Compatibility

All changes are fully backward compatible:
- PID storage is optional (old `.dashboard` files still work)
- Feature collision detection is advisory (doesn't block creation)
- LLM context additions don't change command behavior
- Dashboard cleanup is automatic (users don't need to do anything)

## [0.4.12] - 2025-11-11

### Added

- **Core Service Modules** – Introduced `specify_cli.core.git_ops`, `project_resolver`, and `tool_checker` packages to host git utilities, project discovery, and tool validation logic with clean public APIs.
- **Test Coverage** – Added dedicated suites (`tests/specify_cli/test_core/test_git_ops.py`, `test_project_resolver.py`, `test_tool_checker.py`) covering subprocess helpers, path resolution, and tool validation flows.

### Changed

- **CLI Import Surface** – `src/specify_cli/__init__.py` now imports git, resolver, and tool helpers from the new core modules, slimming the monolith and sharing the implementations across commands.
- **Versioning Compliance** – `pyproject.toml` bumped to v0.4.12 to capture the core-service extraction and accompanying behavior changes.

## [0.4.11] - 2025-11-11

### Added

- **Template Test Suite** – New `tests/test_template/` coverage exercises template manager, renderer, and agent asset generator flows to guard the init experience.

### Changed

- **Template System Extraction** – Moved template discovery, rendering, and asset generation logic out of `src/specify_cli/__init__.py` into dedicated `specify_cli.template` modules with shared frontmatter parsing.
- **Dashboard Reuse** – Updated the dashboard scanner to consume the shared frontmatter parser so Kanban metadata stays in sync with CLI-generated commands.

## [0.4.10] - 2025-11-11

### Added

- **Core Modules** – Introduced `specify_cli.core.config` and `specify_cli.core.utils` to centralize constants, shared helpers, and exports for downstream packages.
- **CLI UI Package** – Moved `StepTracker`, arrow-key selection, and related utilities into `specify_cli.cli.ui`, enabling reuse across commands.
- **Test Coverage** – Added dedicated unit suites for the new core modules and CLI UI interactions (12 new tests).

### Changed

- **Package Structure** – Created foundational package directories for `core/`, `cli/`, `template/`, and `dashboard/`, including structured `__init__.py` exports.
- **Init Command Dependencies** – Updated `src/specify_cli/__init__.py` to consume the extracted modules, reducing monolith size and improving readability.
- **File Utilities** – Replaced ad-hoc directory creation/removal with safe helper functions to prevent duplication across commands.

## [0.4.8] - 2025-11-10

### Added

- **GitignoreManager Module** – New centralized system for managing .gitignore entries for AI agent directories, replacing fragmented approach.
- **Comprehensive Agent Protection** – Auto-protect ALL 12 AI agent directories (.claude/, .codex/, .opencode/, etc.) in .gitignore during init, not just selected ones.
- **Duplicate Detection** – Smart duplicate detection prevents .gitignore pollution when running init multiple times.
- **Cross-Platform Support** – Line ending preservation ensures .gitignore works correctly on Windows, macOS, and Linux.

### Changed

- **init Command Behavior** – Now automatically protects all AI agent directories instead of just selected ones, ensuring no sensitive data is accidentally committed.
- **Error Messages** – Improved error messages for permission issues with clear remediation steps (e.g., "Run: chmod u+w .gitignore").

### Fixed

- **Dashboard Markdown Rendering** – Fixed issue where .md files in Research and Contracts tabs were not rendered, now properly displays formatted markdown content.
- **Dashboard CSV Display** – Fixed CSV files not rendering in dashboard, now displays as formatted tables with proper styling and hover effects.

### Security

- **Agent Directory Protection** – All 12 known AI agent directories are now automatically added to .gitignore during init, preventing accidental commit of API keys, auth tokens, and other sensitive data.
- **Special .github/ Handling** – Added warning for .github/ directory which is used both by GitHub Copilot and GitHub Actions, reminding users to review before committing.

### Removed

- **Legacy Functions** – Removed `handle_codex_security()` and `ensure_gitignore_entries()` functions, replaced by comprehensive GitignoreManager class.

## [0.4.7] - 2025-11-07

### Added

- **Dashboard Diagnostics Page** – New diagnostics page showing real-time environment analysis, artifact location mismatches, and actionable recommendations.
- **CLI verify-setup Command** – New `spec-kitty verify-setup` command for comprehensive environment diagnostics in the terminal.
- **Worktree-Aware Resolution** – Added `resolve_worktree_aware_feature_dir()` function that intelligently detects and prefers worktree locations.
- **Agent Location Checks** – Standardized "CRITICAL: Location Requirement" sections in command templates with bash verification scripts.
- **Test Coverage** – Added comprehensive test suite for gitignore management and Codex security features with 9 test cases covering all edge cases.

### Changed

- **Command Templates** – Enhanced plan.md and tasks.md with explicit worktree location requirements and verification scripts.
- **Error Messages** – Improved bash script errors with visual indicators (❌ ERROR, 🔧 TO FIX, 💡 TIP) and exact fix commands.
- **Research Command** – Updated to use worktree-aware feature directory resolution.
- **Refactored Codex Security** – Extracted Codex credential protection logic into a dedicated `handle_codex_security()` function for better maintainability and testability.

### Fixed

- **Artifact Location Mismatch** – Fixed issue where agents create artifacts in wrong location, preventing them from appearing in dashboard.

## [0.4.5] - 2025-11-06

### Added

- **Agent Guidance** – Bundled a shared `AGENTS.md` ruleset that is copied into `.kittify/` so every generated command has a canonical place to point agents for path/encoding/git expectations.
- **Encoding Toolkit** – Introduced `scripts/validate_encoding.py` and new documentation to scan/fix Windows-1252 artifacts, plus a non-interactive init guide in `docs/non-interactive-init.md`.
- **Dashboard Assets** – Split the inline dashboard UI into static CSS/JS files and committed them with the release.

### Changed

- **CLI Help & Docs** – Expanded `spec-kitty init`, `research`, `check`, `accept`, and `merge` help text and refreshed README/index links to render correctly on PyPI.
- **Dashboard Runtime** – Hardened the dashboard server/CLI handshake with health checks, token-gated shutdown, and more resilient worktree detection.
- **Mission Handling** – Improved mission activation to fall back gracefully when symlinks are unavailable (e.g., Windows w/out dev mode) and aligned shell helpers with the new logic.

### Security

- **Codex Guardrails** – Automatically append `.codex/` to `.gitignore`, warn if `auth.json` is tracked, and reiterate the `CODEX_HOME` workflow to keep API credentials out of source control.

## [0.4.6] - 2025-11-06

### Fixed

- **PyYAML Dependency** – Added `pyyaml` to the core dependency list so mission loading works in clean environments (CI no longer fails installing the package).
- **PyPI README Links** – Restored absolute documentation links to keep images and references working on PyPI.

## [0.4.4] - 2025-11-06

### Security

- **Credential Cleanup** – Removed the committed `.codex` directory (OpenAI credentials) from the entire Git history and regenerated sanitized release assets.
- **Token Rotation** – Documented that all compromised keys were revoked and environments refreshed before reissuing packages.

### Changed

- **Release Artifacts** – Rebuilt GitHub release bundles and PyPI distributions from the cleaned history to ensure no secrets are present in published archives.

## [0.3.2] - 2025-11-03

### Added

- **Automated PyPI Release Pipeline** – Tag-triggered GitHub Actions workflow automatically builds, validates, and publishes releases to PyPI using `PYPI_API_TOKEN` secret, eliminating manual publish steps.
- **Release Validation Tooling** – `scripts/release/validate_release.py` CLI enforces semantic version progression, changelog completeness, and version/tag alignment in both branch and tag modes with actionable error messages.
- **Release Readiness Guardrails** – Pull request workflow validates version bumps, changelog entries, and test passage before merge; nightly scheduled checks monitor drift.
- **Comprehensive Release Documentation** – Complete maintainer guides covering secret management, branch protection, troubleshooting, and step-by-step release workflows.
- **Changelog Extraction** – `scripts/release/extract_changelog.py` automatically extracts version-specific release notes for GitHub Releases.
- **Release Test Suite** – 4 pytest tests validate branch mode, tag mode, changelog parsing, and version regression detection.

### Changed

- **GitHub Actions Workflows** – Updated `release.yml` with pinned dependency versions, proper workflow ordering (PyPI publish before GitHub Release), and checksums stored in `dist/SHA256SUMS.txt`.
- **Workflow Reliability** – Fixed heredoc syntax error in `protect-main.yml` that was causing exit code 127 failures.

### Security

- **Secret Hygiene** – PyPI credentials exclusively stored in GitHub Actions secrets with rotation guidance; no tokens in repository or logs; workflows sanitize outputs.
- **Workflow Permissions** – Explicit least-privilege permissions in all workflows (contents:write, id-token:write for releases; contents:read for guards).

## [0.3.1] - 2025-11-03

### Changed

- **Worktree-Aware Merge Flow** – `/spec-kitty merge` now detects when it is invoked from a Git worktree, runs the actual merge steps from the primary repository checkout, and surfaces clearer guidance when the target checkout is dirty.

### Documentation

- **Merge Workflow Guidance** – Updated templates and Claude workflow docs to describe the primary-repo hand-off during merges and reinforce the feature-worktree best practice.

## [0.3.0] - 2025-11-02

### Added

- **pip Installation Instructions** – All documentation now includes pip installation commands alongside uv, making Spec Kitty accessible to users who prefer traditional Python package management.
- **Multiple Installation Methods** – Documented three installation paths: PyPI (stable), GitHub (development), and one-time usage (pipx/uvx).

### Changed

- **Documentation Consistency** – Updated README.md, docs/index.md, docs/installation.md, and docs/quickstart.md to provide both pip and uv commands throughout.
- **Installation Recommendations** – PyPI installation now marked as recommended for stable releases, with GitHub source for development versions.

### Fixed

- **Packaging Issues** – Removed duplicate `.kittify` force-include that caused "Duplicate filename in local headers" errors on PyPI.
- **Test Dependencies** – Added `pip install -e .[test]` to workflows to ensure all project dependencies available for tests.

## [0.2.20] - 2025-11-02

### Added

- **Automated PyPI Release Pipeline** – Tag-triggered GitHub Actions workflow automatically builds, validates, and publishes releases to PyPI using `PYPI_API_TOKEN` secret, eliminating manual publish steps.
- **Release Validation Tooling** – `scripts/release/validate_release.py` CLI enforces semantic version progression, changelog completeness, and version/tag alignment in both branch and tag modes with actionable error messages.
- **Release Readiness Guardrails** – Pull request workflow validates version bumps, changelog entries, and test passage before merge; protect-main workflow blocks direct pushes to main branch.
- **Comprehensive Release Documentation** – Complete maintainer guides covering secret management, branch protection, troubleshooting, and step-by-step release workflows in README, docs, and inline help.
- **Enhanced PyPI Metadata** – Added project URLs (repository, issues, docs, changelog), keywords, classifiers, and license information to improve PyPI discoverability and presentation.
- **Changelog Extraction** – `scripts/release/extract_changelog.py` automatically extracts version-specific release notes for GitHub Releases.
- **Release Test Suite** – 4 pytest tests validate branch mode, tag mode, changelog parsing, and version regression detection.

### Changed

- **GitHub Actions Workflows** – Replaced legacy release workflow with modern PyPI automation supporting validation, building, checksums, GitHub Releases, and secure publishing.
- **Documentation Structure** – Added dedicated releases section to docs with readiness checklist, workflow references, and troubleshooting guides; updated table of contents.

### Security

- **Secret Hygiene** – PyPI credentials exclusively stored in GitHub Actions secrets with rotation guidance; no tokens in repository or logs; workflows sanitize outputs.
- **Workflow Permissions** – Explicit least-privilege permissions in all workflows (contents:write, id-token:write for releases; contents:read for guards).

## [0.2.3] - 2025-10-29

### Added

- **Mission system assets** – Bundled Software Dev Kitty and Deep Research Kitty mission definitions (commands, templates, constitutions) directly in the CLI package so `spec-kitty init` can hydrate missions without a network call.

### Changed

- Synced mission templates between the repository and packaged wheel to keep `/spec-kitty.*` commands consistent across `--ai` choices.

## [0.2.2] - 2025-10-29

### Added

- **Phase 0 Research command** – `spec-kitty research` (and `/spec-kitty.research`) scaffolds `research.md`, `data-model.md`, and CSV evidence logs using mission-aware templates so Deep Research Kitty teams can execute discovery workflows without leaving the guided process.
- **Mission templates for research** – Deep Research Kitty now ships reusable templates for research decisions, data models, and evidence capture packaged inside the Python wheel.

### Changed

- Updated `spec-kitty init` guidance, plan command instructions, and README workflow to include the new research phase between planning and task generation.

## [0.2.1] - 2025-10-29

### Added

- **Mission picker in init** - `spec-kitty init` now prompts for a mission (or accepts `--mission`) so projects start with Software Dev Kitty, Deep Research Kitty, or another bundled mission and record the choice in `.kittify/active-mission`.

### Changed

- Highlight the active mission in the post-init guidance while keeping the Codex export step as the final instruction.

## [0.2.0] - 2025-10-28

### Added

- **New `/spec-kitty.merge` command** - Completes the workflow by merging features into main branch and cleaning up worktrees automatically. Supports multiple merge strategies (merge, squash, rebase), optional push to origin, and configurable cleanup of worktrees and branches.
- **Worktree Strategy documentation** - Added comprehensive guide to the opinionated worktree approach for parallel feature development.
- **Dashboard screenshots** - Added dashboard-kanban.png and dashboard-overview.png showcasing the real-time kanban board.
- **Real-Time Dashboard section** - Added prominent dashboard documentation "above the fold" in README with screenshots and feature highlights.
- **Mission management CLI** - `spec-kitty mission list|current|switch|info` for inspecting and activating domain-specific missions inside a project.
- **Deep Research Kitty mission** - Research-focused templates (spec, plan, tasks, findings, prompts) and command guardrails for evidence-driven work.
- **Mission packaging** - Missions are now bundled in release archives and Python wheels so project initialization copies `.kittify/missions` automatically.

### Changed

- Updated command list in init output to show workflow order and include merge command.
- Updated `/spec-kitty.accept` description to clarify it verifies (not merges) features.
- Reordered slash commands documentation to reflect actual execution workflow.
- Updated maintainers to reflect fork ownership.
- Updated all repository references from `spec-kitty/spec-kitty` to `Priivacy-ai/spec-kitty`.
- Updated installation instructions to use GitHub repository URL instead of local directory.

### Fixed

- Removed invalid `multiple=True` parameter from `typer.Option()` in accept command that caused TypeError on CLI startup.
- Fixed "nine articles" claim in spec-driven.md to "core articles" (only 6 are documented).

### Removed

- Removed SECURITY.md (GitHub-specific security policies).
- Removed CODE_OF_CONDUCT.md (GitHub-specific contact information).
- Removed video overview section from README (outdated content).
- Removed plant emoji (🌱) branding from all documentation and code.
- Replaced logo_small.webp and logo_large.webp with actual spec-kitty cat logo.

## [0.1.3] - 2025-10-28

### Fixed

- Removed invalid `multiple=True` parameter from `typer.Option()` in accept command that caused TypeError on CLI startup.

## [0.1.2] - 2025-10-28

### Changed

- Rebranded the CLI command prefix from `speckitty` to `spec-kitty`, including package metadata and documentation references.
- Migrated template directories from `.specify` to `.kittify` and feature storage from `/specs` to `/kitty-specs` to avoid namespace conflicts with Spec Kit.
- Updated environment variables, helper scripts, and dashboards to align with the new `.kittify` and `kitty-specs` conventions.

## [0.1.1] - 2025-10-07

### Added

- New `/spec-kitty.accept` command (and `spec-kitty accept`) for feature-level acceptance: validates kanban state, frontmatter metadata, and artifacts; records acceptance metadata in `meta.json`; prints merge/cleanup instructions; and supports PR or local workflows across every agent.
- Acceptance helper scripts (`accept-feature.sh` / `.ps1`) and expanded `tasks_cli` utilities (`status`, `verify`, `accept`) for automation and integration with AI agents.
- Worktree-aware bootstrap workflow now defaults to creating per-feature worktrees, enabling parallel feature development with isolated sandboxes.
- Implementation prompts now require operating inside the feature’s worktree and rely on the lane helper scripts for moves/metadata, eliminating `git mv` conflicts; the dashboard also surfaces active/expected worktree paths.

### Changed

- `/spec-kitty.specify`, `/spec-kitty.plan`, and `/spec-kitty.clarify` now run fully conversational interviews—asking one question at a time, tracking internal coverage without rendering markdown tables, and only proceeding once summaries are confirmed—while continuing to resolve helper scripts via the `.kittify/scripts/...` paths.
- Added proportionality guidance so discovery, planning, and clarification depth scales with feature complexity (e.g., lightweight tic-tac-toe flows vs. an operating system build).
- `/spec-kitty.tasks` now produces both `tasks.md` and the kanban prompt files in one pass; the separate `/spec-kitty.task-prompts` command has been removed.
- Tasks are grouped into at most ten work packages with bundled prompts, reducing file churn and making prompt generation LLM-friendly.
- Both shell and PowerShell feature bootstrap scripts now stop with guidance to return `WAITING_FOR_DISCOVERY_INPUT` when invoked without a confirmed feature description, aligning with the new discovery workflow.

## [0.1.0] - 2025-10-07

### Changed

- `/spec-kitty.specify` and `/spec-kitty.plan` now enforce mandatory discovery interviews, pausing until you answer their question sets before any files are written.
- `/spec-kitty.implement` now enforces the kanban workflow (planned → doing → for_review) with blocking validation, new helper scripts, and a task workflow quick reference.
- Removed the legacy `specify` entrypoint; the CLI is now invoked exclusively via `spec-kitty`.
- Updated installation instructions and scripts to use the new `spec-kitty-cli` package name and command.
- Simplified local template overrides to use the `SPEC_KITTY_TEMPLATE_ROOT` environment variable only.

## [0.0.20] - 2025-10-07

### Changed

- Renamed the primary CLI entrypoint to `spec-kitty` and temporarily exposed a legacy `specify` alias for backwards compatibility.
- Refreshed documentation, scripts, and examples to use the `spec-kitty` command by default.

## [0.0.19] - 2025-10-07

### Changed

- Rebranded the project as Spec Kitty, updating CLI defaults, docs, and scripts while acknowledging the original GitHub Spec Kit lineage.
- Renamed all slash-command prefixes and generated artifact names from `/speckit.*` to `/spec-kitty.*` to match the new branding.

### Added

- Refreshed CLI banner text and tagline to reflect spec-kitty branding.

## [0.0.18] - 2025-10-06

### Added

- Support for using `.` as a shorthand for current directory in `spec-kitty init .` command, equivalent to `--here` flag but more intuitive for users.
- Use the `/spec-kitty.` command prefix to easily discover Spec Kitty-related commands.
- Refactor the prompts and templates to simplify their capabilities and how they are tracked. No more polluting things with tests when they are not needed.
- Ensure that tasks are created per user story (simplifies testing and validation).
- Add support for Visual Studio Code prompt shortcuts and automatic script execution.
- Allow `spec-kitty init` to bootstrap multiple AI assistants in one run (interactive multi-select or comma-separated `--ai` value).
- When running from a local checkout, `spec-kitty init` now copies templates directly instead of downloading release archives, so new commands are immediately available.

### Changed

- All command files now prefixed with `spec-kitty.` (e.g., `spec-kitty.specify.md`, `spec-kitty.plan.md`) for better discoverability and differentiation in IDE/CLI command palettes and file explorers
