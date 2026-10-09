---
work_package_id: WP01
title: Canonical fragment endpoint validation
dependencies: []
requirement_refs:
- FR-001
- FR-012
- NFR-001
- NFR-004
- C-001
- C-009
- SC-001
- SC-004
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- NFR-002
- NFR-003
- C-002
- C-003
- C-004
- C-005
- C-006
- C-007
- C-008
- SC-002
- SC-003
planning_base_branch: issue-5833-pack-fragment-validation
merge_target_branch: issue-5833-pack-fragment-validation
branch_strategy: Planning artifacts for this mission were generated on issue-5833-pack-fragment-validation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5833-pack-fragment-validation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Delivery - one focused validator fix
history:
- at: '2026-10-09T13:50:25Z'
  actor: pi/gpt-6.1-sol
  action: Prompt generated via canonical tasks workflow from parent-adjudicated design
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/doctrine/pack_validator.py
create_intent:
- tests/specify_cli/doctrine/test_pack_validator_org_endpoints.py
- tests/charter/test_drg_endpoint_facade.py
execution_mode: code_change
model: gpt-6.1-sol
owned_files:
- src/specify_cli/doctrine/pack_validator.py
- src/charter/offering/drg/org_pack_loader.py
- src/charter/offering/drg/merge.py
- src/charter/offering/drg/validator.py
- src/charter/offering/drg/__init__.py
- src/charter/drg.py
- tests/specify_cli/doctrine/test_pack_validator.py
- tests/specify_cli/doctrine/test_pack_validator_fragment_finding.py
- tests/specify_cli/doctrine/test_pack_validator_org_endpoints.py
- tests/doctrine/drg/test_org_fragment_validation.py
- tests/doctrine/drg/test_org_pack_node_inference.py
- tests/doctrine/drg/test_org_pack_auto_emit.py
- tests/doctrine/drg/test_org_pack_merge.py
- tests/doctrine/drg/test_validator.py
- tests/doctrine/test_org_pack_augmentation.py
- tests/charter/test_drg_endpoint_facade.py
- tests/cli/test_doctrine_org_commands.py
- tests/specify_cli/cli/commands/test_doctrine_validate.py
- tests/architectural/test_charter_facades_reexport_doctrine.py
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/changelog/CHANGELOG.md
role: implementer
agent: pi
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 — Canonical fragment endpoint validation

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` to load the frontmatter profile and apply its boundaries before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `pi`
- Actually resolve with the clone's `.venv/bin/spec-kitty agent profile show implementer-ivan --json`; load implement action context and fully read charter before AGENTS.
- Do not treat the profile name as proof it was loaded. Parent owns dispatch; use openai-codex/gpt-6.1-sol without silent fallback.

## IMPORTANT: Review Feedback

Read status/review_ref and address every independent reviewer finding before handoff. No approval is present merely because this WP was authored.

## Objectives & Success Criteria

Deliver #5833 through the two existing validation commands; satisfy FR-001–FR-012 and SC-001–SC-004.
A dangling authored requires edge must produce drg_dangling_edge with file/token/role, not merely nonzero exit.
Valid explicit/file-backed/built-in controls remain valid; schema-invalid discovered identities do not count as file trust.
Preserve graph-document, augmentation and runtime semantics, deterministic order and truthful loader-fault attribution.

## Context & Constraints

Read ../spec.md, ../plan.md, ../research.md, ../data-model.md, ../contracts/pack-validation.md, ../quickstart.md and ../reasons-canvas.md.
The parent adjudicated architect-alphonso's static recommendation; it is a technical handoff, not human discovery or Mission acceptance.
Original specify Decision Moments retain operator-delegated/issue attribution. No unreviewed diagnostic prototype is implementation authority.
One focused WP owns the related adapter/charter/test/doc seams; code-change ownership contains no kitty-specs paths.
Charter extensions are necessary to expose existing authority and loader provenance without a duplicate parser or resolver.
No dependency/version bump, #5962 migration, schema-table expansion, sibling resolver or unknown-relation policy.
No QA/global configuration access, main checkout/push, merge/consolidate or new Mission. Remain in the exclusive topic checkout.

## Branch Strategy

- **Strategy**: single_branch; canonical implement resolves direct owned checkout, not a lane worktree.
- **Planning base** and **merge target**: issue-5833-pack-fragment-validation.
- Invoke `.venv/bin/spec-kitty agent action implement WP01 --agent pi --mission 01M4GC4BTDJS52Z3B1YKQ0GK4F` only after finalized tasks and analysis prerequisites succeed.
- Consume the actual returned workspace. Do not create a worktree or guess lane paths.
- Parent rechecks OPEN/DRAFT PR #5962 before implementation/rebase. If merged, re-ground paths and adapt, never restore retired paths.

## Subtasks & Detailed Guidance

### T001 — Pre-RED inspection and scope reconciliation ONLY

**Purpose**: inspect touched seams and reconcile scope without any production-code edit or commit before witnessed RED.
**Steps**:
1. Read current pack_validator, loader, resolver, dangling authority and facade, including scanner shortcuts and intent consumers.
2. Inspect touched-area complexity/Sonar/lint issues; propose only bounded behavior-preserving enablers for T003 AFTER T002 RED.
3. Smallest viable file set first; Boy Scout within it; locality brakes scope growth. Record folded/deferred rationale.
4. Do not sweep god-files, add an architectural allowlist or expand schema coverage for unrelated kinds.
**Files**: read-only owned source seams; no pre-RED production edits, tidy implementation or production-code commits.
**Validation**: record static observations/scope rationale only; scout evidence is not new test proof.
**Parallel?** No. T002 must witness and separately commit acceptance RED before ANY production-code commit, including tidy/provenance/enabler changes.

### T002 — Commit outside-in issue-pinned RED

**Purpose**: expose the missing check through existing public entry points without a false augmentation RED.
**Steps**:
1. Add realistic temporary org-pack fixtures with requires edges for missing qualified/bare sources and targets, malformed known prefix, ambiguous built-in bare id.
2. Through doctrine pack validate --json, assert error/category/file/token/role. Through charter org validate assert rendered finding and exit; it has no JSON flag.
3. A base failure must be missing requested findings, not schema failure or unknown_target from enhances.
4. Witness RED through the existing entry points on the recorded planning base, then commit RED tests/evidence separately before ANY production-code commit, including T003 tidy/provenance/enabler changes; record exact command/count and planning-base comparison.
5. Preserve valid controls and meaningful isolated built-in fixtures for ambiguity; no mock of validate_pack or fake resolver.
**Files**: new test_pack_validator_org_endpoints.py and existing command tests as proportionate.
**Validation**: six broken cases × two commands; JSON assertions pin the actual contract.
**Parallel?** No. No retry-to-green or regression-marker residue after fix.

### T003 — Behavior-preserving provenance/public typed seams

**Purpose**: AFTER T002 witnessed/separately committed RED, perform bounded tidy/provenance/public-seam enablers in distinct behavior-preserving commits before T004/T005 functional code.
**Steps**:
1. Loader adds private discovered-node subtype and authored_nodes accessor; authored_edges filters existing projected subtype internally.
2. Preserve node/edge serialized fields, authored duplicates/order, deduplication and authored metadata precedence; authors cannot spoof provenance markers. Mint the discovered subtype only at loader discovery; accessors inspect private subtype identity, never serialized dictionaries, reason/title/body_path/token heuristics or a dump/reload round trip. Extend existing dump/metadata/duplicate oracles, do not replace them.
3. Promote existing resolver/error to resolve_edge_endpoint/EndpointResolutionError; update actual callers and __all__, not duplicate algorithms.
4. Expose resolver/error/dangling predicate and only externally consumed types through charter.drg; extend the existing architectural facade identity table for those actual objects, no wrapper/private adapter imports. Real src owner→facade→adapter callers must justify every __all__ export; avoid redundant aggregate exports or import them through the aggregate. Keep conflict-kind alias private unless external typing needs it; no dead-symbol allowlist growth.
5. Generalize dangling_endpoints to minimal generic read-only properties/Sequence protocols; DRGGraph result typing stays list[DRGEdge], preserving original edge identity/order and one returned edge even when both sides are missing. Explicitly retain src/charter/activation/synthesizer/reconcile.py consumer typing for _edge_conflict; no reconciliation algorithm edit is indicated.
6. Clarify runtime completeness versus standalone authoring closure docstrings additively; runtime severity/behavior stays unchanged.
**Files**: loader/merge/validator/facade/necessary aggregate; focused loader/resolver/facade tests.
**Validation**: serialized/order compatibility, facade consumer typing and existing runtime tests. Separate enabler commit; endpoint fix remains RED.
**Parallel?** No. No model_construct, invented relation or extra persistent provenance state.

### T004 — Same-scan schema trust and single-load threading

**Purpose**: avoid discovery-as-validation false greens and profile identity false reds.
**Steps**:
1. Existing artifact scan produces separate schema-trusted URN projection only after owning schema validation succeeds.
2. Extract schema-trusted profile identity from the validated profile contract (profile-id and accepted field-name alias), ordinary artifact identity from its validated contract. Do NOT globally change legacy artifact_id/id extraction: legacy profile duplicates/intent/registry behavior and both-intent shortcut stay unchanged. Pin at least the profile-id valid/invalid file-only fixture and existing profile skip/dedup checks.
3. Shortcut rows supply no success proof. Do not add another scan or schema mapping.
4. Return successful loaded org fragment alongside existing findings; thread explicit successful/failed/absent outcomes through ALL THREE main adapter consumers: endpoint, intent and sanction. Sanctions retain ALL loaded nodes, not only authored/trusted identities.
5. Distinguish an omitted helper argument from explicitly supplied failed/absent outcomes with an explicit sentinel/default contract: existing one-argument _collect_fragment_edge_intent(drg_dir) still performs its default load, but validate_pack never reloads an explicit failed/absent result in intent or sanctions. Preserve projected intent edges/#5494 fallback; no alternate YAML parser.
6. Governance-profile selection failure skips whole endpoint pass; individual schema failure only removes file trust. Pin one successful load with realistic endpoint+intent+replaceable-builtins sanction consumers and one failed load attempt with unchanged attributed finding/no derived noise; retain direct one-argument helper coverage.
**Files**: pack_validator and focused twin fixtures.
**Validation**: valid/invalid asset/directive/profile file-only twins, both-intent intent_conflict without false trust, explicit declaration+invalid file retaining schema error but no trust-only dangling, and endpoint/intent/sanction one-load/failed-load/direct-helper oracles.
**Parallel?** No. Built-in endpoint index is shared once between layout checks, not rebuilt per edge.

### T005 — Authored endpoint-only adapter

**Purpose**: close the fragment gap through existing binding and dangling authorities.
**Steps**:
1. Run canonical authored-edge pass independently of graph-document early return.
2. Universe: built-ins + schema-trusted identities + authored explicit nodes. Never use unfiltered discovery or legacy registry as trust.
3. Build local map in existing fragment order filtered by declaration/trust, then remaining trusted identities deterministically; local last-assignment/nearest-scope behavior stays.
4. Resolve source and target independently through public resolver; retain raw token, role, normalized binding and cause.
5. Pass minimal typed endpoint view to dangling_endpoints; format missing sides source then target. No second membership policy.
6. Unknown labels still get existence checks; no label validation or enum coercion. Built-ins unavailable uses existing empty fallback, not skip.
7. Replace graph-document inline membership loop with shared authority using CURRENT snapshot; no precollection/forward-reference change.
8. Use drg_dangling_edge for every unbindable side with runtime cause; update existing category descriptions, no new fields/category.
**Files**: adapter and focused endpoint tests.
**Validation**: both ends broken, unknown prefix, malformed/ambiguous causes, local precedence, declaration-without-file, unknown-label valid/invalid pairs.
**Parallel?** No. No short circuit after source refusal; generated edges cannot acquire fragment-attributed findings.

### T006 — Compatibility, controls and focused coverage

**Purpose**: prove the new check is non-vacuous without broad/heavy sweeps.
**Steps**:
1. Pin valid declared/bare/qualified local/built-in controls and invalid schema twins; include explicit skill/asset declarations.
2. Pin generated-edge exclusion, parse/schema/I/O and governance-failure twins, empty/no fragment and missing built-in fallback.
3. Pin coexisting-shape non-cross-rescue and unchanged order-sensitive sharded duplicate/kind-drift/root/category/text behavior.
4. Pin authored missing augmentation plus existing unknown_target where current intent emits it; preserve #5494 source-kind fallback and skips.
5. Repeat same fixture JSON validation to prove deterministic output/order.
6. Every new branch/helper has focused tests in its change; measure >=90% changed-line coverage, not only total suite percentage. Explicitly run test_validator_structured_detection.py for original edge identity/order/return-once/formatting and strictly type-check the reconciliation sibling.
7. Pin qualified intentional sibling pair: standalone without a local declaration fails, while configured complete assembled runtime graph resolves the real sibling node. Record runtime/doctor results separately; do not add cross-pack resolution to standalone validation.
**Files**: focused owned loader/merge/validator/augmentation/command tests.
**Validation**: tests distinguish artifact-schema fault from no-return loader fault; no vacuous paired passes.
**Parallel?** No. Do not delete valid existing tests, weaken checks or tune host timing gates.

### T007 — Author docs, bounded validation and review handoff

**Purpose**: explain newly red packs and deliver independently reviewable evidence.
**Steps**:
1. Update guide endpoint/bare-id paragraph, error table and troubleshooting in place; impact-first changelog cites #5833.
2. Explain single-pack scope; intentional sibling declaration asserts graph identity, not installed content/schema success. Correct plural kind, qualified edge, no copied content/misleading body_path.
3. doctor doctrine checks configured assembled runtime graph but does not bypass failing standalone validation.
4. Run both real commands on packs/internal and all targeted/owning fast-tier/static checks below; record exact commands/counts.
5. Remove transitional regression markers, self-review diff for unrelated changes/PII/local paths and append existing tracers through CLI.
6. Parent dispatches an independent reviewer. Never self-approve or synthesize acceptance/next outcomes; honor mandatory unchanged pre-review gate.
**Files**: canonical guide/changelog; no product pack or config changes.
**Validation**: real packs/internal zero-error results, separate witnessed/committed RED before ANY production-code commit, unchanged bounded doctor severity/health assertions plus intentional sibling pair, no source/test omissions, truthful Agent: pi/gpt-6.1-sol and Issue: #5833 trailers.
**Parallel?** No.

## Test Strategy — future commands, not planning results

Only clone venv; one targeted command at a time; <=2 workers. Run every written/changed test plus blast radius.
1. `.venv/bin/python -m pytest tests/specify_cli/doctrine/test_pack_validator_org_endpoints.py tests/specify_cli/doctrine/test_pack_validator.py tests/specify_cli/doctrine/test_pack_validator_fragment_finding.py -n 2 --dist loadfile -q`
2. `.venv/bin/python -m pytest tests/doctrine/drg/test_org_fragment_validation.py tests/doctrine/drg/test_org_pack_node_inference.py tests/doctrine/drg/test_org_pack_auto_emit.py tests/doctrine/drg/test_org_pack_merge.py tests/doctrine/drg/test_validator.py tests/doctrine/drg/test_validator_structured_detection.py tests/doctrine/test_org_pack_augmentation.py tests/charter/test_drg_endpoint_facade.py -n 2 --dist loadfile -q`
3. `.venv/bin/python -m pytest tests/cli/test_doctrine_org_commands.py tests/specify_cli/cli/commands/test_doctrine_validate.py tests/specify_cli/cli/commands/test_doctor_doctrine_org_layer.py tests/specify_cli/cli/commands/test_doctrine_hard_fail_surfacing.py tests/specify_cli/doctrine/test_pack_assembler.py -n 2 --dist loadfile -q`
4. Owning subsystem fast tiers in separate serial commands: `.venv/bin/python -m pytest tests/charter -m '(fast or unit) and not slow and not e2e and not stress and not timing and not performance' -n 2 --dist loadfile -q`; same command for tests/doctrine, then tests/specify_cli/doctrine.
5. Named gates only: `.venv/bin/python -m pytest tests/architectural/test_charter_facades_reexport_doctrine.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_no_dead_symbols.py -n 2 --dist loadfile -q`.
6. Each changed Python source/test file: `.venv/bin/ruff check <changed-files>`, `.venv/bin/ruff format --check --force-exclude <changed-files>`, `.venv/bin/mypy --strict <changed-files>` using existing pyproject settings. Resolve real typing errors, no new suppression. Additional exact sibling oracle: `.venv/bin/mypy --strict src/charter/offering/drg/validator.py src/charter/activation/synthesizer/reconcile.py`; checking this caller does not authorize editing its algorithm. The named no_dead_symbols gate is required by promoted __all__ exports and real production-call chains, not a broad sweep.
7. Both public commands on packs/internal as quickstart specifies. Targeted coverage invocation measures changed-line coverage; no whole-repo sweep.
8. Mandatory existing baseline/pre-review gate: `PATH="$PWD/.venv/bin:$PATH" UV_NO_SYNC=1 PYTEST_XDIST_AUTO_NUM_WORKERS=2 make test-fast`. Keep these env values for canonical review transition, which runs unchanged configured gate.
No make test-full, bare architectural/e2e/performance/stress/timing sweep, gate-skip flag, Makefile/config edit or global environment mutation. Specific implicated additional gates require recorded rationale, never bare directories.

## Risks & Mitigations

Schema shortcuts, discovered nodes and profile aliases: separate trust/provenance plus twins.
Relation enum mismatch and source failures: minimal structural view and independent two-side binding.
Sharded order and augmentation parity: keep legacy consumers/snapshots unchanged; compatibility fixtures.
Unavailable built-ins: no silent clean skip; use local universe and preserve existing load-failure policy.
PR #5962 content overlap: recheck before implementation/rebase, not a draft migration here.
Pre-existing failures: follow charter reporting/attribution, diagnose stale install/venv truthfully; no retry-to-green or baseline green-washing.

## Review Guidance / Definition of Done

Independent reviewer verifies RED on planning-base and GREEN on final commit; category/file/token/role checks cannot pass through unrelated augmentation errors.
Review source for one scan/load, provenance accessors, public facade, generic typed predicate reuse and no duplicate endpoint policy.
Verify compatibility matrix, deterministic findings, changed-line coverage >=90%, complexity <=15 and strict compiler/lint/format results.
Verify docs/remediation, packs/internal both commands, truthful command/count evidence, no global/local path leaks or scope creep.
No acceptance is implied by green local tests; canonical review/verdict and parent workflow own approval.
Existing structured-detection and doctor files are validation oracles, not automatically owned edit targets. Grant narrow test_validator_structured_detection.py ownership only if extending those tests becomes necessary; record rationale and canonical ownership refresh before editing. Doctor assertions remain unchanged unless an agreed contract correction warrants a separately documented change. The facade identity-table file is explicitly owned for required new identity rows.

## Activity Log

- 2026-10-09T13:50:25Z — pi/gpt-6.1-sol — Prompt generated from canonical template and parent-adjudicated architect recommendation; no implementation or tests performed.

Progress is event-sourced through status.events.jsonl. Mark subtasks via canonical `agent tasks mark-status`; never add lane frontmatter or task checkboxes. Keep activity entries chronological and append review feedback without erasing history.
