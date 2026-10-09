# Implementation Plan: Canonical org-fragment reference validation

**Branch**: `issue-5833-pack-fragment-validation` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)
**Audience**: software-engineer (implementer and independent reviewer)
**Input**: Existing Mission #5833; parent-adjudicated architect-alphonso recommendation, condensed with source citations in [research.md](research.md).

## Engineering Alignment

The three existing specify Decision Moments preserve their issue/operator-delegated attribution. No discovery was restarted and no new direct human answer is claimed. The parent supplied and adjudicated the architect's technical recommendation as actionable; this is not Mission acceptance. Planner Priti translates that recommendation into delivery sequencing only. Earlier unreviewed prototypes are not design authority.

Canonical `setup-plan` confirms current, target, planning-base and merge-target branches all equal `issue-5833-pack-fragment-validation`, with `branch_matches_target=true`. Work remains single_branch in the owned topic checkout; no lane worktree, main integration, push, merge or consolidate is authorized by this planning handoff.

## Summary

One focused WP closes the canonical org-fragment endpoint-check gap while preserving graph-document and augmentation behavior. The loader exposes authored provenance; the validator projects schema-trusted identities from its existing scan, loads the org fragment once, binds authored endpoints through the public existing runtime resolver and applies the existing dangling predicate through a minimal typed view. Both public commands consume the same validation result. No command rename, new category or relation-label validation is added.

## Technical Context

**Language/Version**: Python 3.11+; existing Pydantic models and Python 3.11 TypeVar/Protocol conventions.
**Primary Dependencies**: Existing typer/rich CLI, Pydantic artifact schemas, YAML loader and charter DRG facade; no dependency addition, upgrade or removal.
**Storage**: Existing pack YAML files, in-memory validation projections; no persisted product format change.
**Testing**: T001 inspection ONLY; future witnessed/separately committed ATDD RED via existing commands before ANY production-code commit; T003 tidy/provenance/enabler only after RED and before functional code, focused helper/contract and compatibility coverage, owning subsystem fast tiers and named architectural gates. No tests run during planning.
**Target Platform**: Existing Linux/macOS/Windows CLI behavior, no platform-specific timing contract.
**Project Type**: Existing Python CLI application adapter over charter authority; no new subsystem.
**Performance Goals**: One org load threaded to consumers; one schema scan; built-in endpoint catalog/index shared between layout checks, never rebuilt per edge. No wall-clock gate.
**Constraints**: FR-001–FR-012, NFR-001–NFR-004 and C-001–C-009 in the spec; particularly no new parser, second binding policy, runtime severity change or sharded registry rewrite.
**Scale/Scope**: One WP, seven subtasks, one pack plus built-ins; explicit graph identities cover own declared assets/skills without requiring file discovery to prove validity.

## Charter Check

Initial and post-design review: no requested exception to the charter. Single canonical authority is preserved by public promotion of the resolver and generic reuse of dangling_endpoints. Charter seam extensions are necessary provenance/authority work, not broad cleanup. ATDD RED is witnessed and committed separately before ANY production-code commit; pre-RED T001 is inspection only, and T003 tidy-first/provenance extraction is a distinct behavior-preserving enabler after RED and before functional code. Reviewer is independent of implementer. All touched helper branches need focused coverage, >=90% changed-line coverage, complexity <=15, strict types/lint/format without new suppressions. Existing three tracers are preserved and appended through the CLI.

SPDD is selected in plan action context (`structured-prompt-driven-development` and DIRECTIVE_038); [reasons-canvas.md](reasons-canvas.md) links the seven reasoning sections without mirroring code. No supply-chain change is proposed, so dependency security checks/challenge are not applicable. Existing post-spec reviews are dispositioned; later point-cut squads remain advisory and are parent-owned, not fabricated as completed here. No architectural allowlist or new gate with a baseline is needed: the shared authority plus behavior tests close the relevant recurrence paths. No optional god-file sweep or version bump.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/pack-fragment-validation-01M4GC4B/
  spec.md
  plan.md
  research.md
  data-model.md
  contracts/pack-validation.md
  quickstart.md
  reasons-canvas.md
  tasks.md
  tasks/WP01-canonical-fragment-endpoint-validation.md
  analysis-report.md             # persisted by record-analysis after tasks
  traces/                       # existing, append only
```

### Source Code (repository root)

```text
src/specify_cli/doctrine/pack_validator.py
src/charter/offering/drg/{org_pack_loader,merge,validator,__init__}.py
src/charter/drg.py
tests/specify_cli/doctrine/test_pack_validator*.py
tests/doctrine/drg/                # focused loader/resolver/dangling tests
tests/doctrine/test_org_pack_augmentation.py
tests/cli/test_doctrine_org_commands.py
tests/specify_cli/cli/commands/test_doctrine_validate.py
docs/guides/how-to/governance/create-an-org-doctrine-pack.md
docs/changelog/CHANGELOG.md
```

**Structure Decision**: Keep adapter formatting in specify_cli and binding/provenance/dangling semantics in their existing charter owners. Loader/resolver/validator/facade additions are justified scope extensions because adapter-only work would duplicate parsing/policy or confuse generated nodes with authored declarations. No file/module/command migration from draft PR #5962.

## Supplied Design and Data Flow

1. Existing artifact scan produces its unchanged legacy registry and a separate trusted identity projection, populated only after existing schema success. Trusted profile identity comes from its validated contract (`profile-id` and accepted field-name alias); other trusted identities come from validated artifact contracts. Legacy artifact_id/id extraction and profile collision/intent/registry behavior remain unchanged. The both-intent shortcut stays intact for legacy consumers but supplies no schema evidence to the trusted projection. No new schema table or second sweep.
2. `load_org_pack` runs once. `_validate_org_fragment` retains findings and the successful fragment, threading explicit success/failed/absent outcomes into ALL THREE endpoint/intent/sanction consumers. Sanctions keep all loaded nodes, not the endpoint trusted/authored universe. Explicit failed/absent result differs from omitted helper argument: main validation never reloads, while existing one-argument helper callers retain default loading. No fallback parse.
3. Loader-owned `authored_nodes` / `authored_edges` accessors use discovered-node/projected-edge subtype provenance. No serialized discriminator, order or deduplication change; authored metadata still wins. Accessors inspect owning private subtype identities, never a dictionary/dump-reload discriminator or metadata heuristic; existing serialization/duplicate/order oracles remain.
4. Known canonical identities are built-ins plus trusted scan identities plus explicit authored declarations. Preserve fragment node order and local last-assignment behavior; add remaining trusted identities deterministically. An unread graph-document declaration cannot rescue a canonical edge, or vice versa.
5. Promote existing resolver/error to public `resolve_edge_endpoint` / `EndpointResolutionError`, update existing callers and expose through `charter.drg` with necessary __all__ entries, real owner→facade→adapter production callers and existing facade identity-table rows (no wrapper or unused aggregate export). Intent consumers switch to the facade without changing their empty-built-in/source-kind fallback.
6. Resolve each authored edge's source and target independently; retain raw token, role and resolver cause. A generic endpoint-only structural view reaches existing `dangling_endpoints`; no synthetic DRGGraph, model_construct, fake enum relation, new membership predicate or unknown-label skip. Generic read-only properties/Sequence retain original DRGEdge identity/order/result typing for the reconciliation sibling; exact structured-detection and strict reconciliation typing are future oracles, not algorithm edits.
7. Graph documents replace only their inline membership loop with the same predicate, preserving file-order known-node snapshots, wording, duplicate/kind-drift/root findings and legacy registry behavior.
8. Format one `drg_dangling_edge` error per missing side, ordered edge then source/target. Existing JSON fields suffice. Both public commands already call validate_pack.

## Resolved Failure and Compatibility Policies

- Fragment parse/schema/I/O load failure retains existing finding/file attribution, with no derived endpoint noise.
- Governance-profile selection failure returns no fragment: skip the whole canonical endpoint pass. Individual artifact schema failure excludes its identity but still checks authored edges of a successfully loaded fragment; explicit declarations independently confer existence.
- Empty/no-fragment packs add no findings. Missing built-in catalog uses existing empty fallback, not a whole-pass skip; local declarations/trusted identities still validate.
- Malformed known-kind tokens carry `malformed_urn`; ambiguous built-in bare IDs carry `ambiguous_edge_endpoint` and qualification guidance; unresolved and unknown-prefix tokens carry `unresolved_edge_endpoint`. All use drg_dangling_edge.
- Authored missing augmentation targets receive dangling findings plus unchanged unknown_target where the existing intent pass emits it, including its skips. Generated edges are not newly attributed to fragment.yaml.
- Runtime merged-graph scope/severity is unchanged. Touched completeness docstrings explain standalone single-pack closure versus runtime assembled-graph completeness. Intentional sibling targets must be explicitly declared as graph identities here, with correct plural kind and qualified edge. doctor doctrine checks the assembled runtime context but does not bypass failing standalone validation; no copying sibling content or misleading local body_path.

## Delivery Sequence and Verification

WP01 contains seven cohesive subtasks: pre-RED inspection ONLY; witnessed/separately committed issue-pinned RED before ANY production-code commit; post-RED tidy/provenance/public-authority enablers before functional code; trusted scan projection and single-load threading; authored endpoint adapter; compatibility/coverage; documentation plus bounded validation and independent-review handoff. One serial WP avoids shared-surface overlap and keeps RED/refactor/functional commits independently attributable. No artificial parallel WPs or separate implementation agents for the same validator.

[quickstart.md](quickstart.md) and the WP prompt define the future commands/matrix. Use only clone venv, one targeted command at a time, <=2 workers. Named architectural gates only; CI owns heavy full/cross-cutting/performance sweeps. Preserve configured pre-review gate: clone `.venv/bin` first on PATH, `UV_NO_SYNC=1 PYTEST_XDIST_AUTO_NUM_WORKERS=2`; never skip/edit the gate or Makefile/config. Validate changed source/test files, owning subsystem fast tiers, strict mypy and force-excluded format checks; record exact counts and honest baseline classifications. No tests executed by planner.

## Risks and Deferred Scope

- Schema-invalid loader discovery / profile-id / both-intent shortcut: trusted projection and twin tests prevent false green/red.
- Unknown relations / stricter DRG model construction: minimal generic view avoids new relation policy; check both endpoint sides regardless of resolver refusal.
- Order-sensitive graph documents / local duplicate bare ids: retain existing snapshots and precedence, pin compatibility tests.
- Draft PR #5962 overlap: parent rechecks before implementation/rebase; if it lands, re-ground paths rather than restoring retired ones. No rename/migration here.
- Broad campsite cleanup, schema expansion for discovered kinds, runtime warning policy and #5494 policy changes are explicitly out of scope; touched-area tidy work only.

## Parent-Accepted Post-Tasks / Brownfield Dispositions

These are precise planning refinements from independent reviewer-renata and brownfield scout reports, accepted by the parent; not new architecture, human discovery, test proof or WP approval.

| Finding | Disposition | Evidence surface |
|---|---|---|
| R1 pre-RED tidy ambiguity | Accepted/folded: T001 inspection only; T002 witnessed separate RED before ANY production-code commit; T003 enablers after RED/before functional work | Plan Testing/Charter/sequence; tasks T001–T003; quickstart |
| R2 doctor consumer preservation | Accepted/folded: two named doctor files plus qualified intentional sibling standalone-red/assembled-valid pair; separate results, existing severity/health assertions retained | WP T006/T007 validation; quickstart |
| B1 facade identity/dead exports | Accepted/folded: narrowly own existing facade identity-table file, add actual object rows; named no_dead_symbols with real-src export rationale and no allowlist growth | WP ownership/T003/static gates |
| B2 generic reconciliation sibling | Accepted/folded: exact validator_structured_detection.py oracle and strict validator+reconcile typing, original edge/order/return-once contract; no algorithm edit indicated; structured-test ownership only if extending it | WP T003/T006/static oracle; quickstart |
| B3 legacy profile registry | Accepted/folded: validated trusted profile identity/alias extraction separate from unchanged legacy id/duplicate/intent paths and shortcut | WP T004/twins |
| B4 subtype provenance/dumps | Accepted/folded: owning subtype accessor, no dictionary round trip or metadata discriminator; retain dump/duplicate/order/precedence checks | WP T003/T005; plan data flow |
| B5 three consumers/default contract | Accepted/folded: endpoint/intent/sanction share explicit successful/failed/absent outcome; omitted direct-call default remains distinct; sanctions keep all loaded nodes, no failed-load retry | WP T004/T006 one-load/direct-helper oracles |
| B6 policy/order fences | Accepted/folded: promote actual resolver callers only; standalone independently binds both sides without runtime relation bridge or intent skips; preserve per-document current snapshot and unread-shape finding | WP T005/T006; plan data flow |

Scout non-goals explicitly deferred: whole-adapter/untouched lineage-cycle-org-charter cleanup (diagnostic complexity was below configured ceiling); facade-origin census repair and stale historical offering docstrings (separate gate/docs domain); schema expansion and global built-in/sanction unification (broader authority changes); runtime severity/unknown-label policy and resolver indexing redesign (behavior/performance redesign); draft PR #5962 migration (owned by overlapping work). Only bounded touched-seam enablers after RED are authorized. No extra WP or follow-up issue is invented.

Future validation includes bounded doctor_org_layer/hard_fail_surfacing files and structured-detection, strict reconciliation caller typing, existing facade identity rows and named dead-symbol gate. The sibling pair differentiates actual configured assembled runtime resolution from standalone closure without adding cross-pack resolution.

## Complexity Tracking

No charter violations or new architectural layers are justified. Existing authority visibility and loader provenance are proportional, necessary scope extensions recorded above.

## Implementation Concern Map

### IC-01 — Provenance and schema trust
- **Purpose**: distinguish authored declarations from discovery and schema-trusted file identities.
- **Relevant requirements**: FR-005–FR-007, NFR-001, C-002.
- **Affected surfaces**: org_pack_loader.py and pack_validator.py scanner/load threading.
- **Sequencing/depends-on**: none; enables IC-02.
- **Risks**: identity alias, shortcut trust, failed-load twins and serialization/order stability.

### IC-02 — Existing endpoint and dangling authority
- **Purpose**: bind authored endpoints and report missing sides without duplicating domain semantics.
- **Relevant requirements**: FR-001–FR-004, FR-008–FR-010, C-001, C-004–C-006.
- **Affected surfaces**: merge.py, validator.py, charter.drg facade and adapter.
- **Sequencing/depends-on**: IC-01.
- **Risks**: relation enum coercion, private imports, source-failure short circuit and sharded ordering.

### IC-03 — Author-facing contract and evidence
- **Purpose**: explain newly failing packs and prove valid/invalid behavior through both entry points.
- **Relevant requirements**: FR-009–FR-012, NFR-002–NFR-004, C-007–C-009, SC-001–SC-004.
- **Affected surfaces**: focused tests, canonical guide and changelog.
- **Sequencing/depends-on**: IC-01 and IC-02; outside-in RED pins the contract first.
- **Risks**: false RED from augmentation, invented charter JSON flag, sibling remedy misrepresented as gate bypass.
