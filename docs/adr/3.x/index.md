---
title: '3.x Architectural Decision Records'
description: 'Index and era history for every Spec Kitty 3.x architectural decision record, with the dated naming convention, the status vocabulary, and how to register a new entry.'
doc_status: active
updated: '2026-08-10'
type: explanation
audience: docs/context/audience/internal/system-architect.md
---

# 3.x ADRs

Architectural Decision Records for the 3.x track (starting 3.0.0, released 2026-03-30).

## Era history

The 3.x track formally began with the **3.0.0 release on 2026-03-30**. ADRs dated on or
after that release live here; older decisions remain in [`docs/adr/2.x/`](../2.x/index.md)
and [`docs/adr/1.x/`](../1.x/index.md). A handful of ADRs landed just before the era
restructuring but thematically belong to 3.x — the shared-package-boundary cutover,
mission-identity-uses-ULID, and the retrospective-gate work — and were moved here with
their git history preserved.

The 3.x era is where Spec Kitty's runtime became a **doctrine-governed, charter-activated**
system with a hardened execution model. The through-lines of this era's decisions:

- **Execution lanes, worktrees, and mission branches** — lanes own their worktrees and
  branches; review approval, integration completion, and mission acceptance became
  distinct, and acceptance runs on the integrated mission branch.
- **Mission identity and topology** — ULID-based canonical identity (not a sequential
  prefix), MissionTopology as a single source of truth, and kind-/topology-aware artifact
  placement with read/write surface symmetry.
- **Doctrine offers, charter activates, runtime consumes** — the doctrine → charter → core
  resolution unification, DRG edges as the canonical artefact-relationship authority,
  progressive disclosure of doctrine context, and the glossary promoted to a first-order
  doctrine artefact.
- **Shared package and integration boundaries** — the shared-package-boundary cutover, the
  CORE/INTEGRATION boundary model, single-authority seams, and the consolidated
  write-surface wiring with `consolidate` as the canonical lane-consolidation term.
- **Governance honesty** — red main is honest signal and CI is the release authority;
  charter.yaml is the authoritative structured source with the prose extractor retired.

This is the **current** track. The prior architecture is [2.x](../2.x/index.md); the
foundational decisions are [1.x](../1.x/index.md).

## Naming

- `YYYY-MM-DD-N-descriptive-title-with-dashes.md` where `N` is `1, 2, 3, …` per ADR landed on a given date.

After adding an ADR file, run (from the repository root, so `scripts` resolves as a
package — #3227) `python -m scripts.docs.freshen_adr_inventory docs/adr/3.x/<your-adr>.md`
to update the page-inventory lockfile and add the row to the index table below. Invoking
the script by file path (`python scripts/docs/freshen_adr_inventory.py ...`) fails with
`ModuleNotFoundError: No module named 'scripts'`; use the `python -m` module form.

## Source of Truth

This folder is canonical for 3.x decisions. The `architecture/` tree was removed
by the Common Docs structural move (PR #2225); existing references using the old
`architecture/2.x/adr/<filename>` paths will need updating to `docs/adr/3.x/`.

## Status Conventions

- `Accepted` means the decision remains current policy.
- `Superseded` means a newer ADR replaced the decision; keep the file for history, but do not implement from it.
- `Deprecated` means the direction is in active retirement and should not receive new work.

## Template

Use the shared template at [`docs/architecture/adr-template.md`](../../architecture/adr-template.md).

## Index

| Date | Title |
| --- | --- |
| 2026-03-09 | [Prompts Do Not Discover Context, Commands Do](2026-03-09-1-prompts-do-not-discover-context-commands-do.md) |
| 2026-04-03 | [Execution lanes own worktrees and mission branches](2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md) |
| 2026-04-03 | [Review approval and integration completion are distinct](2026-04-03-2-review-approval-and-integration-completion-are-distinct.md) |
| 2026-04-03 | [Feature acceptance runs on the integrated mission branch](2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md) |
| 2026-04-04 | [Tracker binding context is discovered, not user-supplied](2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md) |
| 2026-04-04 | [Mission type, mission, and mission run terminology boundary](2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md) |
| 2026-04-06 | [WP state pattern for lane behavior](2026-04-06-1-wp-state-pattern-for-lane-behavior.md) |
| 2026-04-06 | [Connector Installation, User Link, and Resource Mapping Separation](2026-04-06-2-connector-auth-binding-separation.md) |
| 2026-04-06 | [GitHub App Installation Identity Is Provider-Authoritative; Nango Is Secondary](2026-04-06-3-github-app-installation-authority.md) |
| 2026-04-07 | [Global slash command installation](2026-04-07-1-global-slash-command-installation.md) |
| 2026-04-08 | [ADR 1 (2026-04-08): Global `~/.kittify/` as Machine-Level Runtime](2026-04-08-1-global-kittify-machine-level-runtime.md) |
| 2026-04-08 | [ADR 2 (2026-04-08): Package-Bundled Templates as Sole Source](2026-04-08-2-package-bundled-templates-sole-source.md) |
| 2026-04-08 | [ADR 3 (2026-04-08): Global Skill Installation with Per-Project Symlinks](2026-04-08-3-global-skill-installation-per-project-symlinks.md) |
| 2026-04-08 | [ADR 4 (2026-04-08): Charter and Doctrine Are Not Init-Time Concerns](2026-04-08-4-charter-doctrine-not-init-time.md) |
| 2026-04-08 | [ADR 5 (2026-04-08): Shim Generation Supersedes Script-Type Dispatch](2026-04-08-5-shim-generation-supersedes-script-dispatch.md) |
| 2026-04-08 | [ADR 6 (2026-04-08): Global Agent Commands Supersede Per-Project Copies](2026-04-08-6-global-agent-commands-supersede-project-copies.md) |
| 2026-04-08 | [ADR 7 (2026-04-08): Preferred Agent Roles Removed as Unused Concept](2026-04-08-7-preferred-agent-roles-removed-unused.md) |
| 2026-04-09 | [Mission identity uses ULID, not sequential prefix](2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md) |
| 2026-04-09 | [CLI SaaS auth is browser-mediated OAuth, not password](2026-04-09-2-cli-saas-auth-is-browser-mediated-oauth-not-password.md) |
| 2026-04-11 | [SaaS rollout and readiness](2026-04-11-1-saas-rollout-and-readiness.md) |
| 2026-04-14 | [ADR 1 (2026-04-14): Bulk-Edit Occurrence Classification Guardrail](2026-04-14-1-bulk-edit-occurrence-classification-guardrail.md) |
| 2026-04-14 | [ADR 2 (2026-04-14): Agent Skills Renderer for Codex and Vibe](2026-04-14-2-agent-skills-renderer-for-codex-and-vibe.md) |
| 2026-04-15 | [Explicit empty charter selections remain empty](2026-04-15-2-explicit-empty-charter-selections-remain-empty.md) |
| 2026-04-17 | [Charter Synthesizer — Adapter Seam and Provenance Identity](2026-04-17-1-charter-synthesizer-adapter-seam.md) |
| 2026-04-17 | [Charter Synthesizer — Atomicity via Stage + Ordered Promote + Manifest-Last Commit](2026-04-17-2-charter-synthesizer-atomicity.md) |
| 2026-04-19 | [CLI auth uses encrypted file-only session storage](2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md) |
| 2026-04-19 | [Ticket delivery is CLI plumbing; specification is LLM content](2026-04-19-2-ticket-delivery-is-cli-plumbing-specification-is-llm-content.md) |
| 2026-04-19 | [Harness-Owned Generated-Artifact Charter Handoff Contract](2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md) |
| 2026-04-20 | [Mutation testing as a local-only quality gate](2026-04-20-1-mutation-testing-as-local-only-quality-gate.md) |
| 2026-04-21 | [Private teamspace and repository sharing boundary](2026-04-21-1-private-teamspace-and-repository-sharing-boundary.md) |
| 2026-04-22 | [Glossary Chokepoint p95 Latency Measurement](2026-04-22-5-glossary-chokepoint-p95-measurement.md) |
| 2026-04-25 | [Shared package boundary cutover](2026-04-25-1-shared-package-boundary.md) |
| 2026-04-26 | [Contract pinning resolved version](2026-04-26-1-contract-pinning-resolved-version.md) |
| 2026-04-26 | [Auth transport boundary](2026-04-26-2-auth-transport-boundary.md) |
| 2026-04-26 | [E2E hard gate](2026-04-26-3-e2e-hard-gate.md) |
| 2026-04-27 | [Retrospective gate shared module](2026-04-27-1-retrospective-gate-shared-module.md) |
| 2026-05-01 | [Atomic work-package start lifecycle](2026-05-01-1-atomic-work-package-start-lifecycle.md) |
| 2026-05-10 | [Deterministic historical mission-state repair](2026-05-10-1-deterministic-historical-mission-state-repair.md) |
| 2026-05-11 | [Defer #391 still-open structural extraction sub-tickets from the 3.2.x stabilization scope](2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md) |
| 2026-05-12 | [PROPOSAL: `spec-kitty review` lightweight vs post-merge mode contract (WP03)](2026-05-12-1-wp03-review-mode-contract-PROPOSED.md) |
| 2026-05-12 | [PROPOSAL: Charter-content encoding chokepoint location (WP06)](2026-05-12-2-wp06-charter-encoding-chokepoint-PROPOSED.md) |
| 2026-05-14 | [Stale-lane auto-rebase classifier policy](2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md) |
| 2026-05-16 | [Doctrine layer merge semantics](2026-05-16-1-doctrine-layer-merge-semantics.md) |
| 2026-05-18 | [ADR-8: Monorepo charter scope via `CharterScope` abstraction](2026-05-18-1-monorepo-charter-scope.md) |
| 2026-05-18 | [ADR 2026-05-18-2 — DELETE specify_cli.auth.transport (deferred to Robert)](2026-05-18-2-delete-specify-cli-auth-transport.md) |
| 2026-05-19 | [Retrospective default-on policy architecture](2026-05-19-1-retrospective-default-policy-architecture.md) |
| 2026-05-24 | [Charter freshness UX contract](2026-05-24-1-charter-freshness-ux-contract.md) |
| 2026-05-24 | [Pack augmentation vocabulary — `overrides` and `enhances` as declarative fields](2026-05-24-2-pack-augmentation-vocabulary.md) |
| 2026-05-24 | [`shipped` → `built-in` vocabulary cutover for doctrine layer label](2026-05-24-3-shipped-to-built-in-cutover.md) |
| 2026-05-28 | [ADR 2026-05-28-1: CI Dependency Resolution and Test Surface Consistency](2026-05-28-1-ci-dependency-resolution-and-test-surface-consistency.md) |
| 2026-06-02 | [Pi agent is skill-only: no prompt templates, invoker deferred](2026-06-02-1-pi-agent-skill-only-support.md) |
| 2026-06-02 | [Letta agent is skill-only: no slash-command templates, invoker and session model deferred](2026-06-02-2-letta-agent-skill-only-support.md) |
| 2026-06-03 | [Execution-state domain model](2026-06-03-1-execution-state-domain-model.md) |
| 2026-06-03 | [ExecutionContext owner and CommitTarget atomicity](2026-06-03-2-executioncontext-owner-and-committarget.md) |
| 2026-06-03 | [Effector/Actor model](2026-06-03-3-effector-actor-model.md) |
| 2026-06-05 | [Merge publish-layer boundary](2026-06-05-1-merge-publish-layer-boundary.md) |
| 2026-06-06 | [Plan concerns to work package traceability](2026-06-06-1-plan-concerns-to-work-package-traceability.md) |
| 2026-06-07 | [Execution-state canonical surface (`mission_runtime`)](2026-06-07-1-execution-state-canonical-surface.md) |
| 2026-06-07 | [Session presence: multi-harness architecture](2026-06-07-2-session-presence-multi-harness-architecture.md) |
| 2026-06-07 | [WP lane FSM, the `genesis` lane, and the finalize event-log clobber fix](2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md) |
| 2026-06-11 | [Op as a first-class execution artifact (Mission ⟷ Op ⟷ ad-hoc)](2026-06-11-1-op-as-first-class-execution-artifact.md) |
| 2026-06-15 | [Marketplace descriptor vs publish](2026-06-15-1-marketplace-descriptor-vs-publish.md) |
| 2026-06-19 | [A materialized-but-empty coordination worktree hard-fails — no silent primary fallback](2026-06-19-1-coord-empty-surface-fallback.md) |
| 2026-06-21 | [Protected-branch configuration is a standalone boundary-resolved value, not a nested context sub-object](2026-06-21-1-protected-branch-config-boundary-resolved-value.md) |
| 2026-06-22 | [MissionTopology SSOT — store the mission shape, resolve it once](2026-06-22-1-mission-topology-ssot.md) |
| 2026-06-24 | [Kind- and topology-aware artifact placement — one partition, read/write symmetry](2026-06-24-1-kind-and-topology-aware-artifact-placement.md) |
| 2026-06-24 | [Write-branch resolution anchors `meta.json` on the PRIMARY surface (write-surface twin)](2026-06-24-2-write-branch-resolution-primary-anchor.md) |
| 2026-06-25 | [Terminal-artifact durable home + topology-aware teardown contract](2026-06-25-1-terminal-artifact-durable-home-teardown.md) |
| 2026-06-26 | [Single-authority seam + call-site gate for resolution boundaries (Phase 1)](2026-06-26-1-single-authority-seam-and-call-site-gate.md) |
| 2026-06-26 | [CORE / INTEGRATION Boundary Model](2026-06-26-2-core-integration-boundary.md) |
| 2026-06-27 | [Common Docs Consolidation — Reconciliation of Metadata, Structure, Redirects, Glossary Read-Path, ADR Migration, and Curation](2026-06-27-1-common-docs-reconciliation.md) |
| 2026-06-30 | [Sync Daemon Identity Contract and Cleanup Classification](2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md) |
| 2026-07-01 | [No legacy-compat branches in resolvers — require canonical identity, migrate legacy](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md) |
| 2026-07-07 | [IGNORED-Surface Backfill Migration Pattern](2026-07-07-1-ignored-surface-backfill-migration-pattern.md) |
| 2026-07-08 | [MissionResolver Port — One Walk Trunk, Shell-Side DI, No Shared Container](2026-07-08-1-mission-resolver-port.md) |
| 2026-07-14 | [Canonical CliConsole seam — one CLI output object, plain --json, object-not-env determinism](2026-07-14-1-canonical-cli-console-seam.md) |
| 2026-07-14 | [Doctrine → Charter → Core Mission-Type Resolution Unification (governance first)](2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md) |
| 2026-07-15 | [Doctrine Offers, Charter Activates, Runtime Consumes Only Activated (default-charter provisioning)](2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md) |
| 2026-07-16 | [WP runtime-state authority — evict runtime-mutable state from tasks/WP##.md into the canonical event log](2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md) |
| 2026-07-16 | [Steps are the mission-type building block; "template" is a doctrine artefact kind](2026-07-16-2-mission-type-step-authority-and-template-vocabulary.md) |
| 2026-07-17 | [Red main is honest signal; CI status is the release authority](2026-07-17-1-red-main-is-honest-ci-is-release-authority.md) |
| 2026-07-18 | [charter.yaml is the authoritative structured source; charter.md is a curated companion; retire the prose→triad extractor](2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md) |
| 2026-07-19 | [Evict runtime-mutable WP state into the event log via a single generic InnerStateChanged annotation event](2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md) |
| 2026-07-19 | [Skill projection delivers copies, not symlinks](2026-07-19-2-skill-projection-copies-not-symlinks.md) |
| 2026-07-21 | [in_tension_with and reconciles_tension DRG edges (retiring opposed_by)](2026-07-21-1-in-tension-with-drg-edge.md) |
| 2026-07-21 | [promote the glossary to a first-order doctrine artefact (GLOSSARY_PACK kind), retire the runtime glossary, and deliver terminology enforcement as an executable ASSET gate](2026-07-21-2-glossary-first-order-doctrine-artefact.md) |
| 2026-07-22 | [gate bindings reuse `mission_step_contract` — the content-vs-relationship principle](2026-07-22-1-gate-binding-content-vs-relationship.md) |
| 2026-07-23 | [`surface` names two unrelated domains — split the vocabulary, rename to `ToolSurfaceKind` and `TopologySurface`](2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md) |
| 2026-07-23 | [Post-Consolidation Deferral and External Enforcement of Negative Invariants](2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md) |
| 2026-07-26 | [DRG edges are the canonical artefact-relationship authority; inline `references:` blocks are pre-DRG residue to be migrated and retired](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md) |
| 2026-07-26 | [doctrine artefacts live at `<type>/<pack>/[<category>/]<name>` — misplacement is an error, not invisibility](2026-07-26-2-doctrine-artefact-pack-layout-convention.md) |
| 2026-07-26 | [a signed `impacts` edge subsumes `in_tension_with` — one relation, sign carries the direction of effect](2026-07-26-3-impacts-edge-subsumes-in-tension-with.md) |
| 2026-07-28 | [doctrine context is delivered as navigable links, not inlined bodies — `when`/`reason` carry the fetch guidance](2026-07-28-1-progressive-disclosure-of-doctrine-context.md) |
| 2026-07-29 | [Lane Base Merges the Recorded Planning-Artifact Commit (FR-009)](2026-07-29-1-lane-base-recorded-planning-commit.md) |
| 2026-07-30 | [CONSOLIDATED Write-Surface Wiring and `consolidate` as Canonical Lane-Consolidation Terminology](2026-07-30-1-consolidated-write-surface-and-consolidate-terminology.md) |
| 2026-08-02 | [Charter-Wheel Assessment — Extractable in Principle, Cut Over Kernel→Doctrine→Charter as One No-Partial Follow-On](2026-08-02-1-charter-wheel-assessment.md) |
| 2026-08-03 | [Review-Cycle Artifacts Are COORD-Partition Per-WP Bookkeeping](2026-08-03-1-review-cycle-artifacts-are-coord-partition.md) |
| 2026-08-04 | [The Egress-Consent Boundary — Consent Is Keyed on the Record Being Sent, Never on Ambient Context](2026-08-04-1-egress-consent-boundary.md) |
| 2026-08-05 | [Sequence Charter-Activation-Driven Mission-Type Availability Ahead of Mission-Type-as-ArtifactKind; Land It With Mission-Tree Resolution Unification as One Slice](2026-08-05-1-mission-type-availability-before-kind-promotion.md) |
| 2026-08-07 | [A Mission-Halting Instrument Is Worth Its Cost — It Runs Before the Mission, and Its Verdict Is Acted On](2026-08-07-1-a-mission-halting-instrument-is-worth-its-cost.md) |
| 2026-08-09 | [One Project UUID Owns One Sync Store and One Consent Decision](2026-08-09-1-project-sync-store-boundary.md) |
| 2026-08-12 | [Local, No-Egress PlantUML Rendering for Code-Grounded Doctrine Schema Diagrams](2026-08-12-1-plantuml-schema-diagram-rendering.md) |
| 2026-08-12 | [Explicit Checkout Ownership for Mission Create and Next](2026-08-12-1-checkout-ownership-for-mission-create-and-next.md) |
| 2026-08-13 | [The built-in mission subtree stays nested and self-contained; retire the legacy step-contract surface](2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md) |
| 2026-08-13 | [Transition gates are declarative, asset-backed, first-class doctrine artefacts](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md) |
| 2026-08-13 | [Gate execution targets a surface through a kernel selector and the topology placement seam](2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md) |
| 2026-08-13 | [Executable doctrine runs only from trusted publishers (signed built-in; TOFU for the rest)](2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md) |
| 2026-08-13 | [A local loopback daemon amortizes doctrine parse and caches deterministic gate verdicts (direction)](2026-08-13-5-local-daemon-amortizes-doctrine-parse-and-caches-gate-verdicts.md) |
| 2026-08-13 | [Gate outcomes carry a typed severity; an operator-configured error-handling strategy decides the CLI effect](2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md) |
| 2026-08-13 | [Mission-Type Roster Layering Is the Availability Slice, Not the Kind-Promotion Slice](2026-08-13-1-mission-type-roster-layering-seam.md) |
| 2026-08-15 | [Own a Tool-Agnostic, Versioned, Optional Handoff-Packet Intake Contract](2026-08-15-1-handoff-packet-intake-contract.md) |
| 2026-08-16 | [Unify Pack Metadata on a Single Manifest — Enumerated Constituents + Delegated Lineage](2026-08-16-1-pack-metadata-manifest-unification.md) |
| 2026-08-16 | [Open-packs Is the Source of Truth for Built-in Doctrine; CI Re-vendors It Into the Core Release](2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md) |
| 2026-08-16 | [spec-kitty-internal Is One Public Org Pack, Consumed via the Org Tier, Never Force-Shipped](2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md) |
| 2026-08-16 | [Default-off pre-release (rc) consumer channel, gated by SPEC_KITTY_PRERELEASE](2026-08-16-4-rc-release-channel.md) |
| 2026-08-16 | [Operator configuration resolves through one kernel env-expansion seam; committed provenance stores tokens](2026-08-16-5-operator-config-env-expansion-seam.md) |
| 2026-08-27 | [Install-agnostic pre-commit hook fallback + spec-kitty migrate repin-hooks](2026-08-27-1-precommit-hook-stable-entrypoint-and-repin-migration.md) |
| 2026-08-28 | [A project path_conventions override precedes the doctrine default, without changing the blocking policy](2026-08-28-1-project-path-convention-override-precedes-doctrine.md) |
| 2026-08-31 | [Relocate the expected-artifacts.yaml loader authority into charter, sibling error model](2026-08-31-1-expected-artifacts-loader-relocation.md) |
| 2026-09-03 | [Explicit Owned-Checkout Extends to the Single-Branch Mission Lifecycle](2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md) |
| 2026-09-06 | [Convergence Retirement and Client-Repo Inversion](2026-09-06-1-convergence-retirement-and-client-repo-inversion.md) |
| 2026-09-06 | [RuntimeEventEmitter Seam Disposition — Rewire-Ready Consolidation, Not Retirement](2026-09-06-2-runtime-event-emitter-disposition.md) |
| 2026-09-14 | [Census-Floor Ratchets — Per-Ratchet Adjudication (Tripwire, Retire, Retire, Keep-Property)](2026-09-14-1-census-floor-ratchet-adjudication.md) |
| 2026-09-15 | [Main-Tip Verdict Topology — Adjudicating the #4347/#4371/#4360-A/#4430 Coupled Cluster](2026-09-15-1-ci-main-verdict-topology.md) |
| 2026-09-19 | [Terminus-Safety Invariant — gate-then-mutate-with-rollback across merge, accept, and mission close](2026-09-19-1-terminus-safety-invariant.md) |
| 2026-09-20 | [`not-applicable` issue-matrix verdict — non-gating, terminal, classifier-narrowed approval gate](2026-09-20-1-issue-matrix-not-applicable-verdict.md) |
| 2026-09-20 | [Org-aware mission-type loader + path_conventions doctrine slot (full charter convergence deferred to #2652)](2026-09-20-1-canonical-mission-type-source.md) |
