---
title: 3.2.x Goal Corroboration — Planning / Tracking POV (planner-priti)
description: "Planner Priti's corroboration of the 3.2.x goals from the planning/tracking lens: the git-meta and tracker record of missions, PRs, issues, and commit counts."
doc_status: deprecated
updated: '2026-06-16'
---
# 3.2.x Goal Corroboration — Planning / Tracking POV (planner-priti)

> **Author:** Planner Priti (work-decomposition & delivery-sequencing specialist).
> **Lens:** git-meta + tracker record (missions, PRs, issues, commit counts), NOT code-design.
> **Range:** `v3.1.10` (6975ee2, 2026-06-04) .. `v3.2.0` (40e5209, 2026-06-16) — 2317 raw commits.
> **Claim under test:** the operator's 3.2.x goals (G1 doctrine→runtime depth; G2 core-domain
> strangler onto SSOTs; G3 DevEx & enablers, per `docs/release-goals/3.2.x.md`) are
> **evidence-grounded continuations** of a 3.2.0 trajectory, not net-new pivots.

## Directives Applied (planner-priti)

- **Directive 003 — Decision Documentation Requirement:** every goal→evidence mapping and every
  verdict below carries its cited git/tracker rationale (commit ranges, path counts, mission slugs,
  PR/issue numbers). No verdict is asserted without a traceable count.
- **Modes engaged:** *decomposition* (the in-range mission inventory broken to goal buckets),
  *sequencing* (trajectory-into-tag analysis), *prioritisation* (strongest/weakest evidence ranking),
  *risk-analysis* (where evidence is thin / classification is soft).
- **Avoidance boundary honoured:** I do NOT adjudicate code-design correctness of the SSOTs (that is
  architect-alphonso / randy-reducer territory — see `naming-identity-ssot-strangler/`). I corroborate
  the *delivery record* only.

## Method & Caveats (so the numbers are honest)

- **Mission inventory** = `kitty-specs/*/spec.md` files **added** in-range (`git log --diff-filter=A`):
  **129 missions** landed (excludes `test-feature-*` E2E leak dirs + 1 empty stub).
- **Goal classification of missions** is slug-keyword-based with a fixed precedence
  (G2-strangler > G1-doctrine > G3-devex > other/enabler). This is a *planning heuristic*, not a
  semantic read of each spec.md; soft edges are flagged in Risks. Counts are directional, not exact.
- **Commit counts** are path-scoped to real `src/specify_cli/<domain>` modules (agent-dir copies
  `.claude/.codex/.amazonq/…`, vendored, locks **excluded** per scope). `op(<profile>): …` governance
  commits (43) are workflow audit-trail, not feature delta.
- **PRs**: 119 merged in `merged:2026-06-04..2026-06-17` (gh, authoritative). **~63** of those are
  release/rc/tranche plumbing (`3.2.0aN..rc42..3.2.0`) — i.e. *the entire range is the 3.2.0 push*,
  which is itself the corroboration that the goals describe the 3.2.0 line of work.
- **Authorship**: 1858/2317 commits Robert Douglass, 421 Stijn Dejongh — a concentrated, intentional
  release drive, not scattered drive-by.

## Goal × Evidence Table

| Goal | In-range missions (slug-classified) | Path-scoped commit signal (`src/specify_cli/…`) | Merged-PR signal | Guard/ratchet test surface | Verdict |
|------|-------------------------------------|--------------------------------------------------|------------------|----------------------------|---------|
| **G1** Doctrine/Charter/DRG → runtime | **26** (charter ×9 tranche/p7/pack-activation, doctrine/glossary ×8, DRG ×3, profile ×3, spdd/reasons ×1, lifecycle-dispatch-DRG-closeout) | `doctrine+charter+drg` paths **157**; `mission_step_contracts` **17**; `charter_runtime` **8**; `charter_activate` **6**; doctrine-test suite **204** files | ~14 (charter/doctrine/glossary/profile-projection) | `mission_step_contracts/test_executor.py`, DRG node-kind + step-contract-runtime-input fixes (#1518/#1523) | **SUPPORTED (depth qualifier)** |
| **G2** Core-domain strangler → SSOT | **28** (execution-state ×3, coordination/topology ×3, merge ×4, status/lane ×5, identity/naming ×4, ownership ×3, canonical-producer ×2, event-arch, mission-state-migration) | `status` **77**, `core` **61**, `missions` **58**, `lanes` **35**, `coordination` **42**, `merge` **14**, `mission_runtime`(src/) **8**, `identity` **4**, `context` **3** | **21** | `test_execution_context_parity.py`, `test_merge_pipeline_ratchets.py`, `test_ratchet_baselines.py`, `test_shared_package_boundary.py` — all extended in-range | **SUPPORTED (strongest)** |
| **G3** DevEx & enablers | **19** (test-suite-acceleration, mutant-slaying, complexity/code-smell, tool-surface-contract ×2, tooling-stability-guard-coherence, stabilization/blocker-cleanup ×4, p0/p1 fixes) | `tests/**` **760** (architectural ratchets **81**), `.github/workflows/**` **72** | **37** (releng/sonar/ci/lint/hooks/parallel) | `HOW_TO_MAINTAIN.md` + `docs/release-goals/` convention landed; `test_no_legacy_terminology.py`, parity ratchets in active use | **SUPPORTED** |

## Mission Inventory Mapped to Goals (in-range, 129 total)

**G2 — Strangler / SSOT (28) — the spine of the release:**
execution-state-domain-remediation-01KT6HVH · execution-state-canonical-surface-01KTG6P9 ·
execution-context-unification-01KTPKST · coordination-merge-stabilization-01KTXRVR ·
coordination-topology-stabilization-01KTZVQ2 · mission-coordination-branch-atomic-event-log-01KSPTVW ·
wp-lane-state-machine-fsm-01KTGZAZ · status-writepath-profile-surface-remediation-01KTB6AN ·
mission-state-migration-determinism-cleanup-01KRC7JG · name-vs-authority-remediation-01KTYGTE ·
mission-identity-seam-and-1908-panel-01KV6510 · identity-boundary-ci-gate-rerun-01KS51YK ·
unblock-sync-identity-boundary-canary-01KRZJ07 · functional-ownership-map-01KPDY72 ·
charter-ownership-consolidation-and-neutrality-hardening-01KPD880 · migration-shim-ownership-rules-01KPDYDW ·
canonical-producer-lint-01KS4XX4 · canonical-producer-refactor-01KS7PEK ·
merge-done-surface-resolver-01KTDVHZ · merge-preflight-remote-state-boundary-separation-01KTBE5M ·
merge-review-status-hardening-sprint-01KQFF35 · review-merge-gate-hardening-3-2-x-01KRC57C ·
event-architecture-cli-git-truth-01KT119Y · backward-transition-cli-emit-01KRV8GC ·
status-commit-rename-01KSPN6C · sync-diagnose-canonical-allowlist-01KS4F8H ·
runtime-mission-execution-extraction-01KPDYGW · locate-project-root-consolidation-01KV5SX1.

**G1 — Doctrine/Charter/DRG (26):**
charter-* (828-sprint, contract-cleanup, e2e-followups, end-user-docs, golden-path-e2e,
mediated-doctrine-selection, p7-release-closure, p7-schema-versioning, pack-activation-layer,
ux-and-org-pack-vocabulary) · doctrine-enrichment-frontend-brownfield-normalization ·
doctrine-glossary-architecture-consolidation-01KTNWFC · glossary-drg-chokepoint ·
glossary-drg-surfaces-and-charter-lint · glossary-functional-module-extraction ·
glossary-seed-file-schema-validation · layered-doctrine-org-layer-01KRNPEE ·
mission-lifecycle-dispatch-drg-closeout-01KV0S99 · org-doctrine-profile-integrity-{activation-closure,closeout} ·
phase-3-charter-synthesizer-pipeline · profile-invocation-runtime-audit-trail ·
profile-roles-as-value-object · spdd-reasons-doctrine-pack · agent-profile-projection-plugin-production ·
pre-doctrine-test-stabilization.

**G3 — DevEx / enablers (19):**
test-suite-acceleration-01KV3H59 · mutant-slaying-core-packages · complexity-code-smell-remediation ·
p0-test-failure-resolution-1298-1305 · p1-dependency-cycle-cleanup · phase6-composition-stabilization ·
quality-devex-hardening-3-2-01KRJGKH · stability-and-hygiene-hardening-2026-04 ·
stabilization-release-core-bug-fixes · stable-320-{p0-cli-stabilization,release-blocker-cleanup} ·
tool-surface-contract-01KV2K2P · tool-surface-contract-residuals-01KV4S5B ·
tooling-stability-guard-coherence-01KTRC04 · test-stabilization-{and-debt-pass,pre-existing-cluster-fix} ·
sync-rejection-classification-and-queue-retry-hygiene · task-workflow-bug-fixes ·
cli-bug-sweep-tool-surface-self-registration · private-teamspace-ingress-safeguards.

**other/enabler (~56):** auth/sync/teamspace/SaaS hardening, docs/install/upgrade UX, mission-composition
rewrites, session-presence, pi-and-letta agent support, codebase-sanitization, do-dispatch lifecycle,
release tranches. These are *non-goal-or-adjacent* delivery (the operator's own §Non-goals defers UX/SaaS
to 3.3.x); their volume is the noise floor against which the three goals stand out, not counter-evidence.

## Per-Goal Corroboration Verdict

### G1 — SUPPORTED, with a depth qualifier

Quantitatively undeniable as a **direction**: 26 in-range missions and 157 doctrine/charter/DRG
path-commits, plus a 204-file doctrine test corpus and concrete *runtime-wiring* commits
(`mission_step_contracts/test_executor.py`; step-contract-runtime-input #1523; DRG node-kind #1518;
charter/missions paired-invariant gaps #1717/#1718). The trajectory is real and continuous.
**Qualifier (Directive-003 honesty):** the operator's *own* G1 success criterion is the strict one —
"doctrine/DRG **demonstrably gates** a runtime decision path, with a test proving the directive/contract
changes behaviour, not just resolves." The git record shows the *plumbing and breadth* are there; from
the planning POV I can corroborate **the trajectory exists and accelerated**, but the binary "gates not
just resolves" proof is an architect/test-level assertion (`naming-identity-ssot-strangler` already flags
G1 as the *next* slice, not yet closed). So: **continuation confirmed; success-criterion closure pending.**

### G2 — SUPPORTED (strongest-evidenced)

This is the spine of the release. 28 in-range missions, and the heaviest path-commit concentration in the
whole codebase: status **77**, core **61**, missions **58**, coordination **42**, lanes **35**. The
strangler vocabulary is explicit in subjects ("canonical mission_runtime surface + status-facade
strangle … epic #1666 slice 2", #1793; "Canonicalize WP lane state machine", #1775; "execution-context
unification" #1850). Critically, the **last substantive commits before the tag are G2** (#2001
mission-identity naming seam; #1991 coord-topology lanes.json; coordination artifact-home unification) —
proving the trajectory runs *into* 3.2.0, not stopping short of it. The ratchet surface
(`test_execution_context_parity`, `test_merge_pipeline_ratchets`, `test_ratchet_baselines`,
`test_shared_package_boundary`) was extended in-range, evidencing the "extract→route→**enforce**" pattern
the goal claims. Net-new pivot? No — these are #1619/#1666/#1868/#1878 epic slices, multi-mission chains.

### G3 — SUPPORTED

19 in-range missions plus the largest PR-bucket (37, releng/sonar/ci/lint/hooks/parallel) and 72
workflow-file commits, 760 test-file commits. The two named devex governance artifacts —
`HOW_TO_MAINTAIN.md` and the `docs/release-goals/` convention — **exist and landed in-range**, directly
matching the goal text. The seam-extraction-for-testability and ratchet-to-stay-strangled claims are
corroborated by the same parity/baseline ratchet files G2 leans on (shared enabler) plus
test-suite-acceleration-01KV3H59 (parallelize CI/local, per-worker HOME isolation, #1957). This is a
genuine, measurable enabler stream, not a label retrofitted onto incidental cleanup.

## Risks / Thin Spots (planner-priti risk register)

- **R1 (classification softness):** slug-keyword bucketing has soft edges — `merge-*` missions could be
  read as G3-stabilization rather than G2-SSOT; `charter-end-user-docs` is G1-adjacent but doc-shaped.
  Counts are **directional**; the *ordinal* result (G2 > G1 ≈ G3 ≫ pivot-risk) is robust to reasonable
  re-bucketing. Mitigation: precedence rule is documented and reproducible.
- **R2 (G1 depth gap):** the *only* place evidence is genuinely thin against the operator's wording is
  G1's "gates not just resolves" criterion — breadth is proven, the behaviour-gating *proof-test* is the
  declared next slice. This is a known-open, not a contradiction.
- **R3 (release noise):** ~63 of 119 PRs are release/rc plumbing; if one counts PRs naively, DevEx looks
  inflated. The mission-level inventory (129 specs) is the cleaner planning signal and is what the
  verdicts rest on.
- **R4 (corpus vs range):** the *total* kitty-specs corpus (G1 32 / G2 43 / G3 29) shows the same shape
  as the in-range slice (G1 26 / G2 28 / G3 19), confirming 3.2.x continues a pre-existing trajectory —
  the goals are continuations, **claim VALIDATED**.

## Bottom Line

The operator's claim — *"3.2.0 already moved in these directions; the goals are evidence-grounded
continuations, not net-new pivots"* — is **corroborated from the planning/tracking POV**. All three
goals map to substantial, dated, multi-mission delivery that runs continuously into the 3.2.0 tag, with
G2 as the demonstrable spine. The single honest caveat is G1's strict success-criterion (behaviour-gating
proof), which the trajectory approaches but has not yet closed — consistent with the operator's own
"cycle stays open" framing.
