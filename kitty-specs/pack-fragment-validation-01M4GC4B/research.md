# Research and technical handoff: #5833

Audience: software-engineer. Updated: 2026-10-09.

## Evidence and attribution

Parent supplied architect-alphonso's independently profile-loaded static recommendation and adjudicated it actionable. This document records that recommendation, not new planner architecture, direct human discovery, executed product tests or Mission acceptance. Existing specify Decision Moments retain issue/operator-delegated attribution. The unreviewed diagnostic prototypes are excluded.

Source paths below are repository-relative; architect inspected the pre-planning source at `9506b7ee5e3e9d1855ddca6f56e6b8eb864aed07`. Post-spec reviewer-renata and doctrine-daphne findings remain dispositioned in [spec.md](spec.md). Current spec/checklist refinement was committed at `fc4c06dbfae1b6a86fda2aa5de48077040ea0933` before this design handoff.

| Decision from supplied recommendation | Rationale / named source | Alternative rejected |
|---|---|---|
| Loader-owned authored provenance accessors | org_pack_loader.py combines authored and generated nodes/edges; projected edge subtype already distinguishes generation | New YAML reader duplicates parse/load authority; unfiltered discovery falsely confers explicit declaration |
| Separate trusted projection of ONE scan | pack_validator.py::_scan_artifact_directory has a both-intent pre-schema shortcut; AgentProfile identity is profile-id | Reusing legacy set as schema evidence or rescanning artifacts breaks trust/compatibility |
| Promote existing resolver/error through charter.drg | merge.py::_resolve_edge_endpoint owns local/qualified/unique-built-in precedence; charter/drg.py owns adapter access | New resolver predicate, private cross-package leak or #5494 target-kind shortcut for endpoint existence |
| Generic typed endpoint-only dangling view | validator.py::dangling_endpoints needs string source/target plus node_urns; org relations are free strings | Constructing a strict DRGGraph would fabricate relations or skip unknown labels |
| Single org load threaded to consumers | pack_validator.py::_validate_org_fragment already loads; intent collector and sanctions can consume the result | A second loader/fallback parser violates NFR-001 |
| Standalone closure and runtime completeness differ deliberately | merge.py permits qualified forward references; validator.py formats assembled-graph completeness differently | Changing runtime severity, cross-pack resolver or silent warning fallback contradicts recorded sibling decision |

## Settled acceptance alternatives

Governance-profile selection failure prevents successful fragment return: preserve load finding and skip the whole endpoint pass. Individual artifact schema failures exclude their identity but leave authored edges of a successfully loaded fragment checkable. Valid twins prove this is non-vacuous.

Authored missing augmentation targets add drg_dangling_edge; existing unknown_target appears only where unchanged intent logic already emits it. No suppression or promise that all augmentation fixtures produce both findings. Source-kind bare-target fallback remains unchanged.

Unknown relation labels still receive endpoint-existence checks, with no label validation/coercion. Missing built-in graph uses existing empty fallback, not endpoint-pass suppression. Sharded registry/file-order behavior remains unchanged.

Sibling remedy: explicitly declare the qualified graph identity with correct plural kind; do not copy content or imply local artifact/schema validity. doctor doctrine checks the real configured assembled graph but is not a bypass for standalone validation.

## Bounds and outstanding proof

No dependency change; supply-chain dependency decision controls are not applicable. No new schema registry, format, command or version change. Charter loader/resolver/validator/facade files are justified authority/provenance extensions. No unresolved design question remains after parent adjudication; future implementation must prove runtime behavior, serialization stability, compatibility, changed-line coverage and both packs/internal commands. The inherited 87-edge clean observation is not fresh planning proof.

Draft PR #5962 is a re-ground-before-implementation/rebase concern, not permission to migrate paths here. Optional god-file cleanup and schema expansion for discovered skills/templates/glossary/mission kinds are deferred as out-of-scope, not fabricated follow-up work.
