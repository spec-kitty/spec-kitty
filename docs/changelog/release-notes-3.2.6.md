---
title: Release notes — 3.2.6
description: 'Consolidated 3.2.6 release notes: the stabilization release hardening fail-loud honesty across the workflow, plus orchestrator-api 1.4.0 for external-host design pipelines.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-09-03'
related:
- docs/changelog/CHANGELOG.md
- docs/changelog/index.md
- docs/changelog/release-goals.md
---
# Release notes — `3.2.6`

_For the Spec Kitty operator or maintainer upgrading an existing project from `v3.2.5`._

**3.2.6 is the stabilization release that makes Spec Kitty tell the truth.** It closes a long list of "reported success while the thing was actually broken" defects — silent status greens, phantom mission restarts, retention policies quietly ignored, timestamps mislabelled, a startup-crashing dependency — and pairs that reliability push with one substantial new capability: **`orchestrator-api` contract 1.4.0**, which lets an external host (a CI pipeline, a custom dashboard, a native driver) run a Mission's entire design pipeline — `specify → plan → tasks → analyze → decision resolution` — without ever crossing into host-CLI territory. Alongside those, `charter` becomes the canonical governing term, sync ships **off by default** on a bare install, and the CLI gains explicit worktree-owned lifecycle commands, shell autocompletion, and a durable operator-config file.

The previous stable release was **v3.2.5** (2026-07-08). This is the finalized `3.2.6`; it supersedes the per-candidate notes for `3.2.6rc1` and `3.2.6rc2`.

## Install / upgrade

```bash
# New install:
pipx install spec-kitty-cli        # or: pip install spec-kitty-cli

# Existing project:
spec-kitty upgrade
```

`spec-kitty upgrade` runs every 3.2.6 migration automatically; each is idempotent and safe to re-run. Read the **Breaking changes** section below before upgrading — several items need a one-time action, and a few need one command run _before_ the upgrade reaches the project.

---

## 💥 Breaking changes

This section is exhaustive. Each item states what breaks and the exact action to take. Read it in full before you upgrade.

### Governance, charter & doctrine packs

- **Built-in doctrine content moved to `packs/built-in/` with no compatibility shim** (mission `relocate-builtin-doctrine-packs`). _What breaks:_ any reference to the old `src/doctrine/<kind>/built-in/<file>` path. _Action:_ repoint each reference to `packs/built-in/<kind>/<file>` — drop the inner `built-in/` segment. Doctrine `.py` code, `schemas/`, `templates/`, `skills/`, and `missions/` did **not** move.

- **An org pack with an unrecognised agent-profile or DRG key now fails to load** (mission `doctrine-silence-guards`). _What breaks:_ a pack carrying a typo'd or retired key that earlier releases silently dropped. _Action:_ before upgrading, run `spec-kitty doctor doctrine --json` and check the `skipped_profiles` list; fix any invalid profile. A pack with an invalid profile is reported unhealthy rather than passing as healthy.

- **The redundant `context-sources.*` agent-profile block is removed from the schema** (`#3629`; mission `doctrine-drg-silent-drop-boundary`). _What breaks:_ a custom profile that still authors `context-sources` (`directives`/`tactics`/`toolguides`/`styleguides`/`doctrine-layers`/`additional`) now fails to load loudly instead of dropping the block in silence. _Action:_ run `spec-kitty upgrade` — the `3_3_1_context_sources_consolidation` migration set-merges every reference id onto the canonical `*-references` fields. Author references solely on `directive-references` / `tactic-references` / `toolguide-references` / `styleguide-references`.

- **Cross-pack references in an org pack must now be written in full** (mission `doctrine-silence-guards`). _What breaks:_ a bare id in a `drg/` fragment no longer resolves against a _different_ pack in the same merge — it now raises an `unresolved_edge_endpoint` conflict at merge time. _Action:_ write each edge endpoint as `<kind>:<id>` (for example `styleguide:acme-sty-001`), or as a bare id declared in that same fragment's own `nodes:` block.

- **`pack validate` (and `doctrine org validate`) now fail (exit 1) for three previously-passing org-pack shapes** (`#3387`; mission `org-pack-authoring-diagnostics`). _What breaks:_ a merge-time-skipped agent profile (now `profile_skipped`), a nested `assets/<pack>/x.asset.yaml` with a schema violation (now scanned recursively), and DRG content living only under `drg/*.graph.yaml` fragments with no pack-root `*.graph.yaml` (now `drg_root_graph_missing`). _Action:_ if you maintain an org pack, run `pack validate` and fix all three shapes before adopting the pack.

- **`spec-kitty doctor doctrine` now exits non-zero when an org pack declares an edge endpoint that resolves to nothing** (mission `doctrine-silence-guards`). _What breaks:_ CI that treated `doctor doctrine` as a green gate over a pack with dangling endpoints. _Action:_ resolve the dangling endpoints the report names. `charter status` reports the same problems in its `errors` array but deliberately keeps exit code 0, so scripts keying on `charter status`'s exit code are unaffected.

- **The `rtk-search-tooling` toolguide is removed**, including from the default charter pack (`3.2.6_retire_rtk_search_tooling` migration). _What breaks:_ a project still holding the stale `activated_toolguides` entry would hard-fail its next charter compile with `UnknownArtifactIdError`. _Action:_ run `spec-kitty upgrade` — the migration strips the entry from `.kittify/config.yaml`, `charter.yaml`, and `references.yaml`, does nothing on a project that never had it, and is safe to re-run. If you want RTK guidance, keep it in your own org pack.

### Sync, tracker & auth

- **The legacy local-sync surface is now deactivated by default; opt in with `SPEC_KITTY_ENABLE_SAAS_SYNC=1`** (`#3799`; mission `sync-deactivate-by-default`; folds `#3470`/`#2801`/`#2809`). _What breaks:_ a bare install now spawns **no** sync daemon and emits **no** events — zero background processes and zero network egress on the default path. _Action:_ existing sync users must set `SPEC_KITTY_ENABLE_SAAS_SYNC=1` (a per-shell `export`, a per-repo `.kittify/.kitty.env` entry, or per-invocation) to retain the daemon and event emission. Deactivation does not kill a daemon a prior opted-in session left running — `spec-kitty sync doctor` surfaces an advisory and `spec-kitty doctor restart-daemon` retires it. Arming stays strictly upstream of the per-project egress _consent_ gate; it never replaces or weakens consent. The pre-review regression gate is cut off the shared sync toggles onto its own `SPEC_KITTY_PRE_REVIEW_GATE_DISABLE`.

- **Local tracker providers (`beads`/`fp`) now require a recorded egress decision** (mission `tracker-egress-refusal-3108`). _What breaks:_ a `beads`/`fp` binding that never recorded hosted-sync consent and has no `tracker.egress` key stops syncing on upgrade (only `sync pull`/`push`/`run` are gated; `bind`/`status`/`unbind`/`map add` stay available). _Action:_ record `tracker.egress: permitted` in `.kittify/config.yaml` to keep local sync without consenting to hosted sync at all, **or** run `spec-kitty sync opt-in` / set `sync.enabled: true` to consent to hosted sync. Absence at both channels denies by design.

- **Hosted-sync consent is now per-project, and the shared-store `sync migrate` is retired** (`#3262`; mission `per-project-sync-consent-ledgers`). _What breaks:_ the old shared-store `sync migrate` now refuses with guidance, and `SPEC_KITTY_ENABLE_SAAS_SYNC` is strictly deny-only as a consent signal (arming it grants nothing on its own). _Action:_ each project keeps its own isolated consent ledger; `spec-kitty sync opt-in` is the sole local grant. Use the copy-only, resumable cutover commands (`sync project-store-preview` / `-migrate` / `-status` / `-quarantine` / `-history`) to move existing history. See `docs/guides/project-sync-consent.md`.

### Missions, gates & lifecycle

- **A legacy `{"mission": …}`-only Mission now stops resolving its type** and goes neutral/typeless (`#3598`; epic `#3410`). _What breaks:_ the canonical reader drops the legacy `mission` field and the silent `software-dev` default, and this **compounds** with the per-type hard-fail — a legacy Mission that used to mask as `software-dev` can go type-unresolvable. _Action (program-ordered):_ run `spec-kitty migrate backfill-mission-type` against the project **before** this change reaches it (it mints a profile-resolving `mission_type` into every legacy Mission and never fabricates an unresolvable type), then gate with `spec-kitty doctor mission-type --fail-on legacy-key-only,typeless,error`.

- **`spec-kitty next` and `finalize-tasks` now block on requirements written as bare prose** (`#3396`; mission `bare-prose-requirements-uncounted`). _What breaks:_ a spec whose requirements are bare sentences (no `FR/NFR/C` id) used to pass the coverage gate as covered. _Action:_ `next` now refuses to advance past the tasks boundary and `finalize-tasks` exits non-zero, listing the uncounted requirement ids — give each requirement a first-class id.

- **A custom mission family that ships its own `expected-artifacts.yaml` now genuinely blocks on unmet `blocking: true` requirements** (`#3704`). _What breaks:_ an in-flight custom Mission previously advancing silently past a step whose declared, `blocking: true` artifact was never produced may now correctly **block** on its next evaluation. _Action:_ produce the declared artifact (or fix the manifest). The four built-in families are byte-identical; an unregistered family with no manifest still runs to completion as before. In-flight Missions are not retroactively re-evaluated.

- **An `expected-artifacts.yaml` with an unknown or typo'd key now fails loud** (`#3413`; `#3542`). _What breaks:_ a misspelled key used to be silently discarded, so the requirement vanished. _Action:_ the loader now raises `ManifestSchemaError` naming the file (across `reconcile`, background dossier sync, and version resolution, including org-authored manifests) — fix the key to the schema.

- **Review rejections now require a rationale** (`#3307`, `#3444`). _What breaks:_ a rejection travels to the hosted dashboard as `review_ref`, so an empty rationale is refused. _Action:_ pass `--review-feedback-file` or `--note` when rejecting a work package; the backward review move now correctly carries `force=True` and the rationale on the wire.

- **The event log is the single authority for a work package's review verdict** (`#3121`; mission `verdict-seam-write-unification`). _What breaks:_ automation that read the `review-cycle-N.md` `verdict` field as truth. _Action:_ read the `review_result` event in `status.events.jsonl`; the Markdown render is now best-effort and non-authoritative. An `upgrade` migration backfills stranded terminal `.md` verdicts.

- **Mission-mutating `implement`/`review` now fail closed when run from a foreign checkout** (`#3128`, `#3129`). _What breaks:_ a command run from a linked lane worktree that used to silently act on the primary checkout. _Action:_ run mission-mutating commands from the owned checkout (reads and planning are unaffected); a foreign checkout now raises a `CheckoutIdentityError` naming the target checkout.

### Internal APIs & automation contracts

These affect only callers scripting against Spec Kitty internals, parsing its JSON, or importing its modules.

- **`primary_feature_dir_for_mission` is removed; importing it raises `ImportError`** (`#2886`, `#3014`). _Action:_ replace the call with `placement_seam(root, slug).read_dir(<kind>)` for the artifact kind you need.

- **Seven `spec_kitty_events` types are no longer re-exported from `specify_cli.dossier`** (`#3677`). _What breaks:_ `from specify_cli.dossier import ArtifactIdentity` (and the six other moved types) now raises `ImportError`. _Action:_ import these types directly from `spec_kitty_events`. The four `emit_*` re-exports are unchanged.

- **The two exported event emitters take a metadata object, not tail kwargs** (`#3317`). _What breaks:_ out-of-tree callers of `emit_wp_status_changed` / `emit_token_usage_recorded` (re-exported from the `sync` facade) that passed `causation_id`/`force`/`evidence`/`run_id`/`provider`/`model` as individual kwargs. _Action:_ pass a `WPStatusChangeMetadata` / `TokenUsageMetadata` object via the keyword-only `metadata=` parameter.

- **`spec-kitty agent mission setup-plan` changes its unauthenticated-host contract** (`#3621`). _What breaks:_ automation that branched on the old exit code `2` / `SAAS_SYNC_UNAUTHENTICATED` error for an unauthenticated host. _Action:_ the command now exits `0` whenever local verification succeeds and reports hosted-sync unavailability as a nonfatal `warnings[].code` diagnostic — read that instead.

- **`charter context --json` bumps its schema and moves its charter-presence authority** (`#2787`, `#3489`). _What breaks:_ consumers parsing the payload. _Action:_ pin the new top-level `context_schema_version` (now `1.1.0`, adding a typed `procedures[]` array); read `charter.yaml` as the authority of record for `project_charter.present` (a project with only an uncompiled `charter.md` now reports `present: false`, with new additive `charter_md_present` / `charter_md_path` keys).

- **`record-analysis`'s committed `analysis-report.md` now records repo-relative `input_artifacts.*.path` values** (ledger SK-63). _What breaks:_ tooling that parsed those paths expecting absolute filesystem paths. _Action:_ expect a repo-relative path.

- **The printed rejection feedback-file path changed** (`#3554`). _What breaks:_ automation hardcoding `tasks/<wp>/review-cycle-N.md` as the feedback target (which the provenance guard always refused). _Action:_ write feedback to `tasks/<wp>/review-feedback-N.md`.

### Spec Kitty's own CI (contributors only)

- **A push to a protected branch now starts 49 of 50 test jobs instead of about 10** (`#2957`). Pull requests are unaffected — path filtering still narrows a PR to the suites its diff touches. This is a deliberate trade of CI minutes for coverage on the branch where frozen contracts must actually run. No action for consumer projects.

---

## ✨ Added

### orchestrator-api & external hosts

- **`orchestrator-api` contract 1.3.0 → 1.4.0 adds 11 design-phase verbs** so an external host can drive `specify → plan → tasks → check-prerequisites/record-analysis → decision resolution` without any host-CLI crossing (`#3837`; mission `design-phase-orchestrator-api`). `specify`, `plan`, `tasks`, `check-prerequisites`, and `record-analysis` scaffold and validate a Mission's design artifacts; `open-decision`/`resolve-decision`/`defer-decision`/`cancel-decision` operate the decision ledger (each rejecting an empty rationale/final-answer, which also hardens `spec-kitty next` decision resolution); `design-status` is a read-only fail-closed query; and `answer-decision` resolves a `next` `decision_required` moment with full host-CLI event/lifecycle parity. Purely additive — all 21 commands and 51 error codes coexist and no existing verb changed. The 1.3.0 groundwork also added `--review-result-json` to `orchestrator-api transition` so a host can submit a structured review outcome without forcing a lane transition. See [Orchestrator API Reference § Design-Phase Commands](../api/orchestrator-api.md#design-phase-commands).

### Explicit worktree-owned lifecycle

- **`--owned-checkout` now works across the whole single-branch Mission lifecycle** (`#3843`; extends `#3346`/`#3787`; ADR `2026-09-03-1`). `check-prerequisites`, `finalize-tasks`, `spec-commit`, `accept`, `agent tasks move-task`, and `agent tasks mark-status` all accept `--owned-checkout PATH` and route reads, writes, status events, and commits through one validated owned root, so an agent operating from a task-owned worktree can run a Mission end-to-end. Owned mode is `single_branch`-only for now (a `lanes`/`coord` Mission is refused with a structured error rather than mis-routed); flagless behavior is byte-for-byte unchanged.

### Charter, doctrine & packs

- **`charter` is now the canonical governing term** (`#3664`, `#3732`; mission arc `retire-doctrine-term`). The glossary authorities and `docs/context/charter.md` (renamed from `doctrine.md`) speak `charter`; the internal `doctrine` code package is relocated to `charter.offering` with a real `charter.offering` / `charter.activation` module split; and every operator-facing `doctrine` surface keeps working through a one-time deprecation warning — `import doctrine`, the `spec-kitty doctrine` CLI group (now an alias of `spec-kitty charter`), the `governance.doctrine` selection key (mapped forward), the `doctrine.org.packs` path, and the `doctrine:` synthesizer URN prefix (event logs keep parsing both). `spec-kitty upgrade` migrates `interview/answers.yaml` preserving every answer.
- **`charter synthesize` is now non-destructive by default** (`#3270`; folds `#2777`/`#3052`). It preserves backed governance content and reconciles against the on-disk graph; `--prune` is the explicit opt-in for removal and `--dry-run` previews. The `implement`/`next` boundary self-heals instead of hard-blocking until you resynthesize.
- **Org and project doctrine packs are now genuinely usable end-to-end** — a new `ORG` resolution tier ships templates and mission-FSM content, layered packs contribute end-to-end mission types with real action sequences, a chain of multiple org packs merges correctly, and cascade follows `requires`/`suggests` edges an org pack authors in `drg/fragment.yaml` (`#3524`, `#3424`, `#3520`, `#3572`, `#3534`, `#2829`). A unified `pack-manifest.yaml` schema now spans built-in/org/fetched/charter packs (`#3500`–`#3503`; ADR `2026-08-16-1`).
- **New doctrine surfaces reach the agent that earlier releases silently dropped**: `asset` and `template` become first-class doctrine kinds (`#2495`, `#2469`, `#3037`); glossary packs, procedure/tactic step descriptions, and `suggests`-edge paradigms/tactics now render in delivery (`#3489`, `#3063`); `charter context --json` ships a typed `procedures[]` array; and the four consolidated charter-bundle files fold into one authoritative `charter.yaml` (schema `2.0.0`) with a deterministic upgrade migration (`#2773`).
- **`spec-kitty doctor mission-type` and `charter context --json` gain honesty surfaces**: `doctor mission-type` classifies whether every Mission's type resolves (six states, `--json`, `--fail-on` for CI); `charter context --json` exposes a top-level `directives_source` provenance field and fail-loud directive-resolution diagnostics (`#3402`, `#3728`).
- **The `spk-doctrine-show-me` and `spk-run-verdict-capture` skills** ship shared doctrine for choosing an explanatory diagram and for recording a review verdict identically across every agent harness (`#3528`, `#3121`).

### Missions & lifecycle

- **A deliberately-canceled work package is now an honest Mission ending** (`#2945`, `#3590`). Cancellation provenance is a first-class, operator-authored `reason_source` on the status event, and a single `is_acceptable_ending` authority lets `accept` and `merge` admit a `canceled` WP only when it carries operator provenance; a synthetic (undocumented) cancellation is refused. `tasks` also gains an advisory `check-terminability` warning that flags, at planning time, a work package whose acceptance can only be observed after integration.
- **Runtime work-package state now lives in the append-only event log** (`#2684`, `#2816`) — `tasks/WP##.md` frontmatter is no longer a runtime authority; `spec-kitty migrate backfill-runtime-state` seeds and verifies the cutover.
- **`spec-kitty intake` recognises an optional v1 handoff packet** so an upstream requirements tool can seed a Mission's FR/AC ids (`docs/contracts/handoff-packet-v1.md`); `intake --auto` scans `.handoff/*.md`.
- **Dashboard work-package cards** now show subtask progress (`2/4 subtasks`) and a deterministic colored avatar for the assigned agent profile (`#2504`, `#647`).

### Sync, tracker & operator config

- **`spec-kitty sync import-history`** materializes existing local Mission history into the hosted projection with deterministic, idempotent event ids and fail-closed server preflight (`#2262`).
- **A two-tier `.kitty.env` operator-config file** (`${SPEC_KITTY_HOME}/.kitty.env` machine-wide, overridden per-repo) loads before any `spec-kitty` module imports, so operator environment is durable instead of per-shell (`#3495`); committed doctrine provenance is now portable across machines and wheels via a `${SPEC_KITTY_PACKS_ROOT}` token (`#3494`); and an opt-in `SPEC_KITTY_PRERELEASE` channel surfaces pinned release candidates (`#3496`). New `doctor` facets: `provenance`, `env-file`, `channel`.

### CLI UX

- **Shell autocompletion, a `-h` short-help alias, and alphabetical command listing** (`#2232`, `#2234`, `#2235`) — additive, with a committed completion-manifest fast path and no behavior change to existing commands.

---

## 🐛 Fixed

### Startup & correctness

- **`spec-kitty` no longer crashes on startup after installing typer 0.27.2** (`#3782`). typer 0.27.2 removed `Abort`/`Exit` from a vendored module whose eager `getattr` fallback broke every `spec-kitty` subprocess at import; a defensive resolver now degrades gracefully across the vendored module, its submodule, `typer`, and standalone `click`.
- **Every CLI command's cold-import boundary is restored** — commands no longer eagerly load the status-orchestration and workspace machinery, a regression the explicit-owned-checkout work had introduced (restores the `#1461` boundary; new architectural gate enforces it).
- **Timestamps Spec Kitty writes into your project are now correct aware-UTC** instead of local time mislabelled as UTC — ~20 sites (charter backup filenames, status-event stamps, auth-doctor report times) now flow through one `kernel.clock` producer (`#3305`, closes `#3289`).

### Status honesty — "success" that was actually broken

- **Auth and sync diagnostics are now derived from evidence** (`#3723`). `sync status` / `auth status` / `auth doctor` route through one typed `HealthVerdict` authority (tri-state `ok`/`unknown`/`fail`, headline computed from state, mandatory evidence for a definite claim); an expired token whose refresh chain can't be verified resolves to `unknown`, never a false green. `sync doctor` no longer reports "healthy" while the server probe disagrees, and `sync status` names an unreachable/decommissioned server with the exact recovery command (`#3406`).
- **`spec-kitty next` no longer restarts a merged Mission or stalls on a canceled work package** (`#2947`, `#3780`). The loop now decides from the committed status authority — a merged Mission returns `terminal`/`done` instead of fabricating a fresh run against a stale coordination worktree, and an operator-canceled-with-provenance WP advances instead of stalling. `next` also serves the charter-freshness verdict from a per-repo content-hash cache instead of re-parsing the whole charter on every call (`#3787`).
- **A fail-loud sweep closed silent-drop defects at a dozen ground-level sites** (`#3578`, `#3548`, `#3517`, `#3412`, `#2991`, `#3624`, and others). Each now emits the human-readable half of its contract through an existing operator-visible surface: `orchestrator_api`'s `_fail()` keeps its `message` when structured `data` is passed; the sync emitter no longer returns a durably-unqueued event as publishable; a malformed manifest fails loud distinct from "absent"; and the background sync daemon resolves a `specify_cli`-capable interpreter before spawning instead of trusting a bare `sys.executable`.
- **Review verdicts, arbiter overrides, and approvals are durable and single-authority** (`#3044`, `#3235`, ADR `2026-08-03-1`). Approving a work package after a rejection sticks with no `--skip-review-artifact-check` flag; a concurrent review-cycle commit can no longer race into a silently-lost verdict (a checkout-wide serialization queue wraps the whole write); and an arbiter override persists across a fresh clone and clears the merge gate on its own, recorded as its own first-class outcome rather than posing as a reviewer approval.

### Merge & retention

- **`spec-kitty merge` now honors a Mission's declared retention policy** (`#3131`). A Mission's `meta.json` can carry `retain_branches`/`retain_worktrees`; merge resolves cleanup via `resolve_merge_retention` with precedence explicit-CLI-flag > meta.json > default, failing closed toward retention on ambiguity, and tears down (or keeps) the coordination branch/worktree/marker as one coupled decision. An explicit delete override still works but prints a notice naming the contradicted policy. Mint with `spec-kitty agent mission create --retain-branches --retain-worktrees`.
- **Merge no longer discards acceptance/issue-matrix evidence or resets a filled gate artifact to a scaffold** (`#2804`, `#2709`, `#3232`). Custom merge drivers keep whichever side carries evidence; squash merges reconcile per artifact class; and rollback/`--resume` stay coherent after a failed target advance (`#2711`, `#2786`).

### Commit-boundary & workspace integrity

- **Lifecycle commands on a protected-primary / coordination-topology Mission no longer leave a dirty tree, report false success, or refuse with un-followable guidance** (mission `commit-boundary-router-integrity`; epic `#2739`; fixes `#3784`, `#2693`, `#3716`). The commit-router, the protected-primary refusal, and coordination-topology routing now agree on where planning artifacts land — `implement`'s claim commit excludes any `.worktrees/`-nested path, `mission create` commits its scaffold transactionally and discloses `spec.md` as uncommitted, and `mission close --discard` leaves a clean tree.
- **`spec-kitty implement --base <ref>` actually roots the lane on the ref, and hard-errors instead of faking success when it can't** (`#3616`, `#3571`, plus follow-ups). The override is threaded into the topology-aware allocator; an unhonorable route raises a typed `UnhonorableBaseError` naming the route, work package, and base rather than printing a fabricated success line. A shared allocation seam plus a CI anti-bypass guard prevent the class recurring (`#3460`/`#3462`/`#3536`).
- **A command run from a linked lane worktree no longer silently acts on the primary checkout** (`#3129`, `#3346`) — a checkout-identity guard distinguishes owned from foreign worktrees and fails closed, and `mission create`/`next` run correctly from a caller-owned worktree with isolated state.

### Charter, doctrine & gates

- **`spec-kitty charter context --include directive:<id>` resolves the exact ids the `--json` surface advertises** (`#3816`) — the directive selector now normalizes slug, numeric, and `DIRECTIVE_NNN` forms through one canonical authority, closing a divergence that also silently dropped every directive from the gated `DoctrineService.directives` property.
- **`charter generate --from-interview` reports a present-but-corrupt `answers.yaml` honestly** instead of claiming no answers exist (`#2940`); **`charter activate mission-type <T>` refuses a type that resolves an empty action sequence** before writing (`#3717`); and **a single project-local `directives:` entry is now additive** instead of silently replacing the whole resolved set (`#3728`).
- **`charter activate --cascade` names every asset/template node it did not cascade** instead of silently dropping them (`#3705`), and **a malformed `drg/fragment.yaml` in one pack no longer drops the other packs' fragments** — the degrade is now per-pack with an operator-visible warning (`#3629`).
- **Governance now reaches the deciding gate, not the implementer** (mission `governance-at-the-gate`; `#3685`, `#3682`) — decision-documentation is delivered at `review` (removed from `implement`, so smaller models stop stalling mid-implementation to demand sign-off), enforcement levels carry an explicit rank, and the review/accept gates capture real bound evidence.

### Sync, tracker & auth

- **Review rejections reach the hosted dashboard again** (`#3307`, `#3444`) — the backward review move now emits `force=True` and threads `review_ref`, satisfying the wire contract the hosted endpoint enforces.
- **Machines that never ran the layout migration now capture sync events for real** instead of silently capturing zero while reporting success (`#3425`, `#3497`); **`auth login` resolves the then-current hosted URL** when unset (the current endpoint is `https://team.spec-kitty.ai`) (`#3297`); and a batch-400 poison event no longer strands its whole batch (`#2736`, `#2755`).
- **Hosted event-sync delivers again for consented projects** (`#3564`, `#3620`) — `sync now` no longer self-blocks on an admission gate whose server endpoint isn't deployed, and `import-history --apply` honors the server's own preflight success.
- **`sync share <team>` no longer crashes first-run while it self-heals**, and **`auth status` now shows each team's slug** that `sync share` requires (`#3699`, `#3731`).

### Upgrade & migrations

- **`spec-kitty upgrade` obeys your `auto_commit` opt-out, survives its own re-run, and stops misreporting success or failure** (mission `upgrade-command-hardening`; `#3651` and cluster). Read-only generated files route through one restore→write→re-protect writer (no more ~30 `Permission denied` errors on re-run); the commit decision defers to `get_auto_commit_default` and says so when it leaves changes uncommitted; a destructive mission-state repair is a separately-scoped consent gate; and a single finalizer derives the exit code once.
- **`upgrade` no longer silently drops skill-content migrations on Windows** when the managed `SKILL.md` is read-only (`#3771`), and **refreshes a stale `.claude/CLAUDE.md` orientation surface** rather than leaving an outdated version string (`#2265`).
- **`init` gitignores the `.worktrees/` root** (with an `upgrade` backfill) so a mission worktree no longer shows in `git status` (`#3689`), and **no longer blanket-gitignores all of `.cursor/`** for teams versioning their own Cursor rules (`#2498`). Several upgrade-wedge failures that left a stuck migration with no self-service exit are fixed (`#3383`).

---

## ♻️ Changed

- **`spec-kitty --version` / `-v` is now a single copyable line** — no ASCII-art banner before the version string (community contribution by @zohar).
- **One canonical mission-type reader** replaces ~10–12 hand-rolled `meta.json` readers that disagreed on field order and default; the dashboard, retrospectives, and identity now show a Mission's _true_ type instead of masking everything as `software-dev` (`#3598`; ADR `2026-08-22-1`). See the Breaking-changes note on the `spec-kitty migrate backfill-mission-type` program ordering.
- **`--json` output is plain regardless of terminal colour** — ~77 ad-hoc `Console()` sites moved onto one `CliConsole` seam with an architectural guard (`#2632`; ADR `2026-07-14-1`).
- **Wall-clock performance tests moved off the PR path** to a dedicated statistical `performance.yml` pipeline (`pytest-benchmark`, per-domain baselines), after a false-red audit found 58.6% of CI failures were inactionable flake; a weekly `ci-flake-report.yml` now measures the false-red rate, and `CI Quality` fails a draft PR fast while running a ready PR to completion (ADR `2026-08-22-1`; `#3595`, `#3669`).
- **Skill projection delivers real copies, never absolute symlinks**, healing dangling links in dev containers and sandboxes (`#2412`; ADR `2026-07-19-1`).
- **The `ExecutionMode` three-way name collision is untangled** — the ownership enum is renamed `WorkProductKind` (member string values unchanged, so WP frontmatter stays wire-compatible), the dead runtime duplicate is retired, and a re-drift guard prevents recurrence (`#3416`).
- **Docs consolidated under one predictable `docs/` root** with user (`guides/`) vs contributor (`development/`) split and old-URL redirects, and docs can now be marked `durable` so a standing reference is never flagged as a stale draft (`#2215`, `#3368`).

---

For the complete, line-by-line list of every change — every Added, Fixed, Changed, and Breaking entry with its full before→after detail — see the `[3.2.6rc1]`, `[3.2.6rc2]`, and `[Unreleased]` (3.2.6rc4) sections of the [canonical CHANGELOG](CHANGELOG.md).
