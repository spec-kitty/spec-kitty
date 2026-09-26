---
doc_status: active
updated: '2026-09-26'
---

# Planner Priti — Group D issue-coverage check

Themes: arch-gate-allowlists (63), dead-code-legacy-residue (43), docs-drift (39), doctrine-drg-packs (26), charter-context-activation (20), duplicate-authorities (4) = **195 tracer items from 61 missions**.

**Profile applied:** planner-priti (builtin) — decomposition, sequencing, risk analysis, prioritisation (Eisenhower); avoidance boundary respected (no implementation, no architectural decisions; drafts propose scope only). Directive 003 (decision documentation) applied: every verdict cites the issue read or the code probe it rests on. Charter plan context loaded (bootstrap); DIRECTIVE_044 canonical sources and DIRECTIVE_010 specification fidelity guided the "verify against live code, not the tracer" checks. Read-only: nothing filed, commented or edited on GitHub or in the repo.

**Verdicts (34 clusters, 171 items; 24 informational items unclustered):** COVERED 9 · PARTIAL 12 · CLOSED-ONLY 8 · UNCOVERED 5


## Clusters → verdict → issues

| ID | Kind | Cluster | Missions / items | Max sev | Verdict | Issues (state, fit) |
|---|---|---|---|---|---|---|
| D-01 | both | Architectural-gate allowlists/census rows pinned by file:line (or stored LOC) go red on unrelated line drift; the standing positional-anchor ban (#2077) only scans files that import the ratchet substrate, so line-pinned allowli... | 8 / 10 | high | **CLOSED-ONLY** | #2077 (closed, exact); #2547 (closed, partial); #2564 (closed, partial); #3206 (open, adjacent) |
| D-02 | both | Dead-symbol/dead-module gates impose sequencing tax: seam-first WPs red until a consumer lands, body-hash keys invalidate on any class-body edit, bidirectional ratchet forces detector+row co-landing, and facade re-export livene... | 9 / 11 | high | **PARTIAL** | #2913 (open, partial); #2546 (closed, partial); #3552 (closed, partial); #2559 (closed, partial) |
| D-03 | cause | Per-WP/per-lane targeted test runs never execute the full tests/architectural/ suite, so mission-introduced arch-gate reds accumulate and only surface at closure, pre-merge squads, or CI. | 4 / 4 | high | **COVERED** | #3943 (open, exact); #3260 (open, adjacent) |
| D-04 | improvement | Planning does not enumerate which architectural gates, allowlists, layer ledgers, facade tables and CI shard roots a planned edit will trip; plans assert 'deletions only help gates' or predict empty allowlists from the mission'... | 8 / 9 | high | **UNCOVERED** | #3487 (open, adjacent); #4227 (open, adjacent) |
| D-05 | cause | Gate registration toil: new tests/modules need manual rows in census/registry/baseline files, floor constants are duplicated across gate files, and set-equality pins need multiple synchronized edits. | 5 / 6 | high | **CLOSED-ONLY** | #4315 (closed, exact); #2616 (closed, partial); #2621 (closed, partial); #2913 (open, adjacent) |
| D-06 | cause | The ruff-format-exclude ratchet reds when a WP incidentally reformats an excluded file whose pyproject.toml exclude row is not in that WP's owned_files. | 1 / 1 | medium | **COVERED** | #4506 (open, exact) |
| D-07 | both | The archive byte-freeze gate blocks corrections to archived mission dossiers, yet live contracts are stored in (and cited from) completed mission folders; there is no canonical home for durable cross-mission contracts, and the ... | 6 / 7 | medium | **PARTIAL** | #4956 (open, adjacent); #3100 (open, partial); #3911 (closed, adjacent) |
| D-08 | cause | Several guards are text/name-shaped and can pass while the protected behaviour is gone (substring seam-allowance test, literal RETIRED names, --feature literal token, keyword-only AST predicates, per-directory count ceilings, t... | 7 / 10 | high | **PARTIAL** | #3663 (open, partial); #3195 (open, partial); #2986 (open, partial); #5015 (open, adjacent); #3113 (closed, exact); #3676 (closed, partial) |
| D-09 | improvement | Allowlist hygiene: hand-written allowlists had missing sites and phantom entries, exemption paths went stale after relocations, emptied allowlists are not tightened to ==0, and audit inventories have no overcount/stale-entry tr... | 4 / 5 | medium | **PARTIAL** | #3088 (open, partial) |
| D-10 | cause | Retired sync/event plumbing emitted 'project sync store is locked' / 'layout cutover did not publish' warnings, slowed plan/record-analysis past 120s, and hung the dossier body-upload path. | 7 / 7 | high | **CLOSED-ONLY** | #3475 (closed, exact); #3625 (closed, exact) |
| D-11 | cause | Sync-era egress/consent residue: one key answered hosted vs local tracker consent, Chain B repo_defaults, inert batch.py reads, dead register_saas_client_factory seam, decision-widen unvalidated ids, sync doctor mis-rendering, ... | 3 / 16 | high | **CLOSED-ONLY** | #3108 (closed, exact); #3030 (closed, exact); #3111 (closed, exact); #3109 (closed, exact) |
| D-12 | cause | Three incompatible mission-type schemas/resolvers (legacy MissionConfig/specify_cli/mission.py, MissionTypeProfile, mission-runtime.yaml), an unpopulated path_conventions slot, and the typeless->software-dev default. | 3 / 4 | high | **COVERED** | #2652 (open, exact); #2660 (open, exact); #2721 (open, partial); #3831 (closed, partial) |
| D-13 | cause | runtime_bridge compat delegates cannot be deleted because the frozen #2531 compat-surface guard asserts identity via name lists that grep-based deadness classification cannot see. | 1 / 2 | medium | **COVERED** | #2561 (open, exact) |
| D-14 | improvement | Identified dead code left in place: core/vcs/git.py + protocol remove_workspace (zero callers, documented as dead in git/destructive_guard.py), doctrine/snapshot.py _ARTIFACT_BUCKETS (unreferenced), and the core/no_follow.py re... | 3 / 3 | medium | **UNCOVERED** | #2499 (open, adjacent) |
| D-15 | cause | Remaining duplicated primitives: requirement-mapping missing/unmapped classification and its NFR-002 fail-loud wrapper exist in runtime + two CLI sites; env truthy parsing and path-containment helpers are forked. | 2 / 2 | medium | **PARTIAL** | #3555 (open, exact) |
| D-16 | cause | Coord/primary partition residue: coord copy of lanes.json as legacy residue on 3.2.0-era missions, deferred resolve_feature_dir_for_mission read-site sweep, and skip-vs-refuse divergence across move-task/mark-status/map-require... | 3 / 3 | medium | **COVERED** | #2160 (open, partial); #1878 (open, partial); #2453 (closed, exact); #2300 (closed, exact) |
| D-17 | both | Planning artifacts, issue bodies and briefs carry file:line citations, counts, command names and root-cause pins that drift or were never verified (wrong gate cited, undercounted forks, mis-pinned root cause, nonexistent comman... | 13 / 18 | high | **PARTIAL** | #2897 (open, partial); #4067 (open, adjacent) |
| D-18 | cause | record-analysis bakes absolute machine-local paths into committed analysis-report.md input_artifacts, forcing hand rewrites and reviewer rejections. | 2 / 2 | medium | **COVERED** | #3398 (open, exact) |
| D-19 | cause | docs/configuration/linting-cutoff-policy.md lists bandit and pip-audit as blocking checks, but no workflow in .github/workflows/ runs either (they are only dev dependencies in pyproject.toml). | 1 / 1 | medium | **UNCOVERED** | #3181 (closed, adjacent) |
| D-20 | cause | Agent-facing docs/help drift: CLAUDE.md once pointed at a nonexistent SPEC-KITTY-LEDGER.md (src/tests comments still cite it), CLAUDE.md's shared-package boundary line is too coarse for src/runtime/next/, stale -WP## fallback n... | 5 / 5 | medium | **PARTIAL** | #3448 (open, partial) |
| D-21 | both | Derived artifacts (CLI reference, docs index, ADR inventory, .contextive glossary, packs graph/manifest) each need their own regeneration script with environment quirks (PYTHONPATH, SPEC_KITTY_PACKS_ROOT, stale installed binary... | 5 / 5 | medium | **PARTIAL** | #2440 (open, partial); #2887 (closed, partial); #4343 (closed, adjacent) |
| D-22 | cause | Tracer-file location never converged: the mission-tracer-files procedure says traces/, missions use traces/ (53), tracers/ (18), tracer/ (1) and root tracer-*.md (48); an older safe-commit guard warned on tracer writes from lan... | 3 / 3 | medium | **UNCOVERED** | #4959 (closed, adjacent); #2217 (closed, adjacent) |
| D-23 | cause | Adding a DRG ArtifactKind/NodeKind silently misses switch/mapping sites, mirrored kind sets must move in lockstep, fixed-field result dataclasses drop new kinds, asset paths lacked containment, and org/built-in URN collisions w... | 1 / 7 | high | **CLOSED-ONLY** | #3608 (closed, exact); #2469 (closed, partial); #2495 (closed, partial) |
| D-24 | cause | Org-pack/mission-type layout parity: the activation scanner assumed a layout the loader does not use, a unit test pinned the bug, nested-vs-flat built-in mission-type layout is undecided, and layered roster lookups need per-id ... | 2 / 5 | high | **COVERED** | #2468 (open, partial); #2467 (open, partial); #3385 (closed, exact) |
| D-25 | cause | Doctrine validation surfaces are not trustworthy proof: doctor doctrine does not schema-validate new artifacts, a built-in toolguide fails extra_forbidden and is silently skipped, and SkippedProfile has no severity. | 3 / 3 | medium | **PARTIAL** | #2701 (open, exact); #4836 (open, adjacent) |
| D-26 | cause | The glossary-pack generator lived in a scratchpad and was never committed, so the shipped glossary pack is hand-edited with test_glossary_pack_parity as the only net. | 1 / 1 | medium | **PARTIAL** | #4835 (open, partial) |
| D-27 | cause | Charter synthesis-manifest churn: CLI invocations restamp adapter/synthesizer version and hashes (including downgrades from a stale PATH CLI and dropped bundle_content_hash), dirtying tracked charter files and tripping move-tas... | 3 / 3 | medium | **CLOSED-ONLY** | #1912 (closed, exact); #2681 (closed, adjacent); #1838 (open, adjacent) |
| D-28 | cause | implement preflight still surfaces stale-state gates one at a time (charter_source -> charter sync -> synthesized_drg -> synthesize), gates docs-only WPs on charter/DRG freshness, and its fresh-project detector (SK-14) misfires... | 2 / 3 | high | **CLOSED-ONLY** | #2157 (closed, exact); #2831 (closed, adjacent); #3897 (open, adjacent) |
| D-29 | cause | Analyze-freshness false positives: check_analysis_report_current byte-hashes charter.yaml (which carries generated_at) and spec/plan/tasks, so a routine charter sync or a citation-only edit forces a mission-wide re-analyze. | 2 / 2 | high | **PARTIAL** | #2493 (open, partial); #2157 (closed, adjacent) |
| D-30 | cause | synthesized_drg freshness compared a frozen manifest created_at against bundle mtime (permanently stale), and activate/deactivate mutated config without recompiling the bundle. | 1 / 2 | high | **CLOSED-ONLY** | #2681 (closed, exact); #4908 (closed, adjacent); #2780 (open, adjacent) |
| D-31 | cause | Charter write commands fail closed from linked worktrees (DD-05), so charter JSON contract tests red inside worktrees and charter repros need separate clones. | 2 / 3 | medium | **COVERED** | #4873 (open, exact); #4250 (open, partial) |
| D-32 | cause | charter context emits noise on every call: LegacyOrgPackDoctrineKeyWarning, CharterCatalogMissWarning for language-filtered artifacts, and 'unresolved configured directive IDs' while still returning the charter. | 3 / 3 | medium | **COVERED** | #4573 (open, exact); #4000 (open, adjacent) |
| D-33 | cause | Layer-chain widening landed in shared primitives without sweeping callers (org chain not threaded; charter list --all-layers shows one path per layer; promote_activations is a second inert write chokepoint onto commit_plan). | 2 / 4 | medium | **PARTIAL** | #4100 (open, partial); #4101 (open, partial); #4400 (open, adjacent); #3527 (closed, exact) |
| D-34 | improvement | Fail-open patterns recur as a class (`is False` tri-state checks, truthiness on falsy values, match without default, dict.get(key, PERMISSIVE) on policy tables) and are found only by hand review. | 1 / 1 | medium | **UNCOVERED** | #2992 (open, adjacent) |

### Gaps and notes per non-COVERED cluster

- **D-01 (CLOSED-ONLY)** — The ban's context scoping (only files importing composite_key/ContentDescriptor) leaves raw (Path,int) allowlists in non-substrate gates unguarded; _KNOWN_JOIN_ALLOWLIST is live on main and bit a mission on 2026-08-13.
- **D-02 (PARTIAL)** — No open issue for dead-symbol gate sequencing friction (seam-first WPs, body-hash invalidation on legitimate class edits after 2026-08-24).
- **D-04 (UNCOVERED)** — Searched open/closed titles (arch gate, allowlist, plan, gate impact) and 2 semantic queries; no issue asks plan/tasks to produce a gate-impact census.
- **D-05 (CLOSED-ONLY)** — Residual: duplicated floor constants (CANONICALIZER_FLOOR twins), set-equality pins needing three edits, and the ci-nightly wallclock registry left 20/21 modules allowlisted with no follow-up (#4864 closed).
- **D-07 (PARTIAL)** — No issue defines (a) a canonical root for durable cross-mission contracts (e.g. docs/contracts/) and migration of live contracts out of kitty-specs/*, or (b) a sanctioned errata/supersession mechanism for archived dossiers.
- **D-08 (PARTIAL)** — Per-gate issues exist, but no standing audit/directive requires behaviour-anchored non-vacuity (mutation-proven teeth) for guards; test_seam_allowances_name_a_live_seam (substring) is still present.
- **D-09 (PARTIAL)** — No generic rule that every allowlist is census-derived with per-row rationale, has a stale-entry reverse check, and asserts its exemption paths exist (the glossary_packs stale path was fixed in place).
- **D-10 (CLOSED-ONLY)** — None live: the warning strings, _await_publish_or_loud and src/specify_cli/sync/ are gone from main; the completion manifest's saas_gated field also retired. Tracer evidence (2026-08-22..24) predates retirement.
- **D-11 (CLOSED-ONLY)** — Resolved on main: tracker/egress_verdict.py is a single local-consent verdict (Channel 1 retired with sync, issue #5); ADR docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md exists; 'engagement' is in docs/context/identity.md.
- **D-14 (UNCOVERED)** — Title greps (dead, remove_workspace, _ARTIFACT_BUCKETS, shim) + 1 semantic search found nothing. Dead-symbol gates miss them because one is a Protocol method and one is module-private.
- **D-15 (PARTIAL)** — Path-containment helpers still exist in >=5 copies (core/utils._is_relative_to, charter governance_references._is_relative_to, mission_runtime.checkout_identity._is_within, status/store._is_contained, dashboard handlers); one stray truthy parse remains in git/protection_policy.py despite core/env.is_truthy.
- **D-17 (PARTIAL)** — No doctrine/tooling asks for symbol-anchored citations in spec/plan/research or a citation-verification step in /spec-kitty.analyze.
- **D-19 (UNCOVERED)** — Verified on main 2026-09-26: grep of .github/workflows, Makefile, scripts finds no bandit/pip-audit invocation; doc line 51 still claims blocking. Title greps and a semantic search found no issue.
- **D-20 (PARTIAL)** — Several items fixed on main (CLAUDE.md no longer cites the ledger; spec-commit help is primary-partition; -WP## note corrected). Residual: invocation/router.py and two tests cite SPEC-KITTY-LEDGER.md:2727 which is not in the repo; runtime/next layering guidance unrefined.
- **D-21 (PARTIAL)** — No `make regen` (or equivalent) that runs every derived-artifact generator from a worktree with the right env; Makefile has no such target.
- **D-22 (UNCOVERED)** — No issue on reconciling legacy tracer layouts (tracers/, root tracer-*.md) with the procedure/tracer-append convention, or making retrospective/recon tooling read all variants.
- **D-23 (CLOSED-ONLY)** — Resolved on main: drg/merge.py::_check_node_urn_unique, pack_validator asset_path_escape, tests/charter/test_kind_cascade_exhaustive.py. #2467 pack-split remains open (tracked in D-24).
- **D-25 (PARTIAL)** — No issue for doctor doctrine schema-validating every shipped artifact (test_shipped_graph_valid.py is the only net).
- **D-26 (PARTIAL)** — Verified: no glossary-pack generator script in the repo. #4835 does not ask for committing the docs/context -> pack generator.
- **D-27 (CLOSED-ONLY)** — Committed .kittify/charter/synthesis-manifest.yaml stamps adapter_version/synthesizer_version 3.2.6 while the repo is 3.2.7rc1, so any governed run from the current CLI rewrites it; stale PATH binaries downgrade it.
- **D-28 (CLOSED-ONLY)** — No open issue for the post-#2157 recurrence or the SK-14 fresh-project detector misfire / shared-state mutation under concurrent implement.
- **D-29 (PARTIAL)** — Charter input is hashed as raw bytes of charter.yaml (verified: generated_at present; analysis_report.py _sha256_file). No issue for normalizing charter metadata or semantically inert spec/plan edits.
- **D-30 (CLOSED-ONLY)** — Resolved on main; no action.
- **D-33 (PARTIAL)** — charter list --all-layers multi-org-pack display (deferred by cascade-org-inert) has no issue.
- **D-34 (UNCOVERED)** — Two semantic searches plus title greps (fail-open, permissive default, tri-state) found no class-level lint/audit issue.

## Draft issues (not filed)

Ordered by priority, then by leverage. Dependencies name other clusters or issues.

### D-04 · P2 · Plan phase: generate a gate-impact census (arch gates, allowlists, layer ledgers, CI shard roots) for the files a mission will touch
- **Scope:** Add a deterministic helper (e.g. spec-kitty agent mission gate-impact) that, given planned touched files/symbols, lists the tests/architectural gates and allowlist rows that reference them, the layer-rule ledger entries, and the CI module/shard owning each test path; surface it in the plan template's Charter Check.
- **Labels:** enhancement, workflow, priority:P2
- **Depends on / relates:** Complements #3943 (post-hoc) — this is the shift-left half; benefits from D-01 content-addressed keys.
- **Evidence:** `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-design-decisions.md:93`, `kitty-specs/cross-os-primitive-unification-01M2T1CM/tracer-design-decisions.md:84`, `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-design-decisions.md:115`

### D-07 · P2 · Canonical home for durable cross-mission contracts + errata protocol for frozen archived dossiers
- **Scope:** Create docs/contracts/ (or similar) as the citable home for contracts that outlive a mission; migrate round-trip-tested live contracts out of kitty-specs/<done-mission>/; define an errata/supersession file convention that test_archive_root_byte_identical accepts, and mention it in the plan template.
- **Labels:** documentation, tech-debt, priority:P2
- **Depends on / relates:** Coordinate with #3100 (archive relocation) and #4956.
- **Evidence:** `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:7`, `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:7`, `kitty-specs/dispatch-dry-run-route-only-01M1HKV2/tracer-design-decisions.md:54`

### D-17 · P2 · Citation discipline for mission artifacts: symbol-anchored references + analyze-time citation check
- **Scope:** Extend the #2897 stable-identifier guideline to file:line citations (prefer path::qualname) and add an analyze check that resolves cited paths/symbols/commands against the tree and flags stale line ranges and nonexistent CLI commands.
- **Labels:** documentation, workflow, priority:P2
- **Depends on / relates:** Extends #2897; pairs with D-04.
- **Evidence:** `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-design-decisions.md:6`, `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-design-decisions.md:7`, `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-design-decisions.md:552`

### D-19 · P2 · Security scans: linting-cutoff-policy claims bandit + pip-audit are blocking, but no workflow runs them
- **Scope:** Either wire bandit and pip-audit into the lean modular CI (ci-router/ci-aggregate) as required or advisory jobs, or correct docs/configuration/linting-cutoff-policy.md to the real gate set. Decide explicitly — the doc currently gives false assurance.
- **Labels:** domain:ci, documentation, priority:P2
- **Depends on / relates:** None.
- **Evidence:** `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:95`

### D-27 · P2 · Charter synthesis-manifest still churns on CLI version: stop restamping adapter/synthesizer_version on content-identical runs (regression of #1912)
- **Scope:** Treat the manifest version stamps as content-only (update only when synthesized content changes) and refuse to write an older synthesizer_version than recorded; add a regression test that two governed runs across a version bump leave the tree clean.
- **Labels:** domain:charter, reliability, priority:P2
- **Depends on / relates:** Related to D-28 (SK-14 preflight mutating shared governance state).
- **Evidence:** `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:7`, `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:363`, `kitty-specs/relocate-saas-sync-flag-to-core-01KWQ3RV/tracers/tooling-friction.md:16`

### D-28 · P2 · implement preflight: aggregate all charter/DRG prerequisite gaps in one pass (post-#2157 recurrence) and stop the fresh-project detector mutating shared charter state
- **Scope:** Reproduce the chained bounce seen 2026-08-13; make preflight report every stale prerequisite at once (or auto-run deterministic refresh); make the SK-14 fresh-project detector read-only on a populated repo and never rewrite .kittify/charter from a lane implement.
- **Labels:** workflow, reliability, domain:charter, priority:P2
- **Depends on / relates:** Under #3897; interacts with D-27.
- **Evidence:** `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-tooling-friction.md:493`, `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:357`

### D-29 · P2 · Analysis-report freshness: hash normalized charter content (ignore generated_at/extracted_at) so charter sync does not stale the analysis
- **Scope:** Normalize charter.yaml (strip timestamp/provenance metadata) before hashing in collect_input_artifact_hashes, mirroring the tasks.md normalization; optionally offer a lightweight re-record for citation-only spec/plan edits.
- **Labels:** workflow, reliability, priority:P2
- **Depends on / relates:** Sibling of #2493 item 1.
- **Evidence:** `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-tooling-friction.md:290`, `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:233`

### D-01 · P3 · Positional-anchor ban: close the scope hole for (Path, int) allowlists in gates that do not import the ratchet substrate
- **Scope:** Extend test_ratchet_positional_anchor_ban to every module-level allowlist seed under tests/architectural/ (not only substrate-importing files), with an explicit enumerated exemption list; migrate test_built_in_location_authority._KNOWN_JOIN_ALLOWLIST (and any other hits) to composite_key/ContentDescriptor.
- **Labels:** tech-debt, domain:ci, priority:P3
- **Depends on / relates:** Independent; touches the same files as #3206 (coordinate).
- **Evidence:** `kitty-specs/org-activation-scan-dirs-01KZY1PT/tracer-tooling-friction.md:392`, `kitty-specs/content-address-ratchet-allowlists-01KX8M4D/tracers/standing-metaguard.md:5`, `kitty-specs/refactor-stable-gate-substrate-01KWK3FY/tracers/design-decisions.md:25`

### D-02 · P3 · Dead-symbol gate: first-class 'pending consumer' marker for seam-first WPs and name-keyed entries for __all__ symbols
- **Scope:** Let a WP declare a new public seam as pending-consumer (with owning follow-up WP id) so test_no_dead_symbols does not red mid-mission; evaluate replacing body_hash keys with name+source_module keys (#3552 follow-through) so adding a dataclass field does not invalidate the allowlist row.
- **Labels:** tech-debt, domain:ci, priority:P3
- **Depends on / relates:** Fold into #2913 decision if the maintainer prefers one gate-friction ruling.
- **Evidence:** `kitty-specs/relocation-hardened-dead-code-scanners-01KX958P/tracers/live-collision-classifier.md:8`, `kitty-specs/charter-catalog-coherence-01M2XQQF/tracer-approach.md:26`, `kitty-specs/cascade-asset-silent-drop-01M0RME0/tracer-tooling-friction.md:51`

### D-05 · P3 · Gate registration residue after #4315: single-source floor constants and auto-derived registries
- **Scope:** Hoist duplicated ratchet floor constants into one module; replace set-equality pins (e.g. _ROUTED_MODULES) with derived sets; file the wallclock-registry recapture of the 13 stale modules that ci-nightly-wallclock-budget left allowlisted.
- **Labels:** tech-debt, domain:ci, priority:P3
- **Depends on / relates:** Follows #4315 rulings.
- **Evidence:** `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:7`, `kitty-specs/user-content-preservation-01M3549Q/tracer/design-decisions.md:14`, `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-approach.md:57`

### D-08 · P3 · Guard non-vacuity audit: census substring/name-shaped architectural guards and add mutation-proven teeth
- **Scope:** Inventory tests/architectural guards whose predicate is a substring, literal name list, or keyword-only AST match; for each, add a planted-regression (mutation) test proving it fails when the behaviour is removed, or rewrite it behaviourally. Start with test_seam_allowances_name_a_live_seam and the --feature literal guard.
- **Labels:** tech-debt, reliability, priority:P3
- **Depends on / relates:** Umbrella over #3663, #3195, #2986; pairs with D-09.
- **Evidence:** `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-evidence-base.md:247`, `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-design-decisions.md:308`, `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-design-decisions.md:36`

### D-14 · P3 · Delete confirmed dead code: VCS remove_workspace (protocol+git), snapshot._ARTIFACT_BUCKETS; evaluate inlining core/no_follow.py shim
- **Scope:** Remove the zero-caller remove_workspace protocol method and git implementation (guarded_worktree_remove is the live path) and the unreferenced _ARTIFACT_BUCKETS table; decide whether core/no_follow.py stays a re-export shim. Note in the PR why the dead-symbol gate missed each (method-level, private name).
- **Labels:** tech-debt, tidy-up, good first issue, priority:P3
- **Depends on / relates:** None.
- **Evidence:** `kitty-specs/merge-destructive-op-safety-01M2XQF8/tracer-design-decisions.md:33`, `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-approach.md:32`, `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/tracer-tooling-friction.md:9`

### D-15 · P3 · Unify path-containment helpers (>=5 copies) onto one kernel primitive; route the stray env truthy parse through core.env.is_truthy
- **Scope:** Introduce/choose one containment primitive (kernel.paths) and migrate the five private copies; replace protection_policy's inline ('1','true','yes') check with is_truthy. Pure de-duplication, no semantic change.
- **Labels:** tech-debt, tidy-up, priority:P3
- **Depends on / relates:** Independent of #3555.
- **Evidence:** `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-approach.md:28`, `kitty-specs/relocate-saas-sync-flag-to-core-01KWQ3RV/tracers/design-decisions.md:24`

### D-20 · P3 · Remove dangling SPEC-KITTY-LEDGER.md citations from src/tests and refine CLAUDE.md runtime/next layering guidance
- **Scope:** Replace SPEC-KITTY-LEDGER.md:2727 references (invocation/router.py, test_router.py, test_dispatch.py) with the tracker issue they summarize (#3840); add one line to CLAUDE.md distinguishing _internal_runtime/ (closed DAG re-exports) from top-level runtime/next orchestration.
- **Labels:** documentation, tidy-up, priority:P3
- **Depends on / relates:** Under #3448.
- **Evidence:** `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:38`, `kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/tracer-tooling-friction.md:8`, `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:14`

### D-21 · P3 · Add one `make regen-derived` target that refreshes every byte-exact derived artifact from any worktree
- **Scope:** Chain build_cli_reference, docs index/ADR inventory freshen, generate_contextive_glossaries and doctrine regenerate-graph with PYTHONPATH/SPEC_KITTY_PACKS_ROOT set for the current checkout; document it next to the freshness gates it satisfies.
- **Labels:** tooling, tech-debt, priority:P3
- **Depends on / relates:** Subsumes #2440's chaining ask.
- **Evidence:** `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:9`, `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/tooling-friction.md:60`, `kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/tracer-tooling-friction.md:7`

### D-22 · P3 · Converge mission tracer file layout on traces/<category>.md (procedure, tooling, legacy readers)
- **Scope:** Make the procedure, charter standing order and agent tracer-append agree on one layout; teach retrospective/recon readers to accept legacy tracers/ and root tracer-*.md read-only, without editing frozen archives.
- **Labels:** workflow, tidy-up, priority:P3
- **Depends on / relates:** Respects the archive freeze (D-07).
- **Evidence:** `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-tooling-friction.md:211`, `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/tooling-friction.md:48`, `kitty-specs/doctrine-catfooding-2196-01KWE16N/tasks/WP04-mission-tracer-files.md:140`

### D-25 · P3 · doctor doctrine: schema-validate every artifact it counts, and report silently-skipped artifacts as errors
- **Scope:** Run the same pydantic validation as test_shipped_graph_valid in doctor doctrine; surface artifacts dropped by base.py loaders as findings with severity.
- **Labels:** domain:charter, reliability, priority:P3
- **Depends on / relates:** After #2701.
- **Evidence:** `kitty-specs/relocation-hardened-dead-code-scanners-01KX958P/tracers/warning-remediation.md:17`, `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-design-decisions.md:56`, `kitty-specs/doctrine-catfooding-2196-01KWE16N/tasks/WP04-mission-tracer-files.md:93`

### D-33 · P3 · charter list --all-layers: show every org pack in the chain (consume resolve_layer_roots org_chain)
- **Scope:** Render pack-2+ availability from the additive org_chain key instead of the single roots['org'] path; add a two-pack fixture test.
- **Labels:** domain:charter, enhancement, priority:P3
- **Depends on / relates:** None.
- **Evidence:** `kitty-specs/charter-activate-empty-action-sequence-01M0STSX/tracer-design-decisions.md:33`, `kitty-specs/cascade-org-inert-01M07E9P/tracer-approach.md:46`

### D-34 · P3 · Class-level fail-open audit: lint for permissive-default policy lookups and tri-state `is False` checks
- **Scope:** Add a ruff-custom or AST arch check flagging dict.get(key, <permissive literal>) on policy/consent tables, `x is False` on tri-state values, and match statements without a default in gate/guard modules; seed with a live census and per-site rationale.
- **Labels:** reliability, tech-debt, priority:P3
- **Depends on / relates:** Pairs with D-08.
- **Evidence:** `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-design-decisions.md:472`

## Sequencing suggestion (planner lens)

1. **Do first (P2, independent, cheap):** D-19 (security-scan doc vs CI: a false assurance), D-29 (analysis freshness normalization), D-27 (synthesis-manifest churn). Each is small and removes recurring friction on every mission.
2. **Then (P2, shift-left):** D-04 gate-impact census at plan time, paired with the open #3943 (post-hoc gates on the merged branch). D-17 citation discipline rides the same analyze surface.
3. **P2 structural:** D-28 preflight aggregation (post-#2157 recurrence); D-07 contracts home + errata protocol (coordinate with #3100).
4. **P3 hygiene batch (parallel, good-first-issue grade):** D-14 dead code, D-15 containment helpers, D-20 dangling ledger refs, D-22 tracer layout, D-33 charter list --all-layers, D-21 regen target.
5. **P3 gate-quality track (one owner):** D-01 ban scope hole → D-02 dead-symbol sequencing (or fold into #2913) → D-05 registration residue → D-08/D-09 non-vacuity + hygiene audit → D-34 fail-open lint.

## Informational items not clustered (24)

Design notes recording a choice already made or a defect already unified in-mission, with no residual action: accept-path-remediation-honesty-01M0TWZP, census-freshness-loc-insensitive-01KWVD6Y, charter-authority-flip-01M14RB3, coordination-doctor-branch-safety-01M35EN8, cross-os-primitive-unification-01M2T1CM, custom-mission-guard-failure-blocking-inert-01M0STY0, doctrine-catfooding-2196-01KWE16N, doctrine-delivery-activation-01KYQVQK, dossier-guard-reexport-analyze-cleanup-01M0NHRT, journal-project-consent-3030-01KYKWQS, legacy-cleanup-split-dossier-queue-migration-01M0MGHB, merge-destructive-op-safety-01M2XQF8, mission-resolver-port-01KX1C05, mission-type-guard-registry-01KZY2FG, move-task-approval-ergonomics-01M302R0, org-pack-authoring-diagnostics-01KZY463, spdd-reasons-activation-split-brain-01M1K6VN, sync-strict-json-auth-01KWA6KN, tasks-py-degod-wave2-01KWH9EQ, user-content-preservation-01M3549Q, windows-upgrade-mode-fidelity-01M35C25, write-side-seam-matrix-tracer-01KYP3MH. Examples: the resolved duplicate-authority unifications (dirty-check predicate, backup naming, gating-reference helper, branch-identity authority), walk_edges single-relation walks, resolver no-cache rationale, and the WP09 not_applicable intent superseded by an ADR.

## Honest limits

- **Semantic search was heavily rate-limited** (a shared quota across sibling delegates). About 12 semantic queries succeeded. Most matching used title greps over `open_issues.tsv` and a sibling delegate's complete closed-issue title index (`closed_issues_E.tsv`, 2,367 rows), plus full reads of 12 issue bodies (#2077, #2546, #3943, #4956, #4873, #4000, #2561, #3088, #2493, #3555, #4315, #2913, and the #2157 comments). An UNCOVERED verdict means no match by title grep plus at least one semantic query. An issue whose title does not use the tracer's vocabulary could still be missed.
- **Live-code checks were spot checks** on main at the time of the run (grep/ls, one `charter context` run, one script invocation). They were not full reproductions. Clusters marked "resolved on main" (D-10, D-11, D-23, D-30) rest on the absence of the cited symbols or strings and the presence of the fix artifacts.
- **Regression calls:** CLOSED-ONLY clusters D-01, D-05, D-27 and D-28 are called residual or regression because a mission's creation date comes after the issue's close date. Tracer text was not re-run against HEAD for D-28; its recurrence evidence is dated 2026-08-13.
- **Clustering choices:** 34 clusters is above the 8-20 guideline because this group spans 6 themes and 195 items. Sync-era items (D-10, D-11) were kept as separate clusters so they can be dismissed explicitly rather than hidden.
- The `groupD_items.jsonl` file in the shared scratchpad was re-extracted into `D_work/items.jsonl` for deterministic indexing; the cluster→item mapping is in `D_work/assign.py`.
