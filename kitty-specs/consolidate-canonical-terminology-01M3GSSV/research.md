# Research — Consolidate terminology (#3080)

## Method

Pre-spec research & grounding was run as a bounded 4-lens squad (census / classification /
architecture / adversarial), each grounded against live `main`, then orchestrator-adjudicated.
Full synthesis: `work/3080-consolidate-terminology/GROUNDING.md` (gitignored) and posted on issue
#3080. No new dependency is added/upgraded/removed → the supply-chain-install-safety check is
**N/A** for this mission (recorded, not silently skipped).

## Key decisions

- **Decision**: `consolidate` (verb) / `consolidation` (noun) / `CONSOLIDATED` (state) is canonical
  for the lane-consolidation sense (glossary Sense 1). **Rationale**: extends the already-landed ADR
  `2026-07-30-1` + glossary. **Alternatives**: keep overloaded `merge` (rejected — active false-verdict cost).
- **Decision**: `spec-kitty merge` removed this cycle with a migration-error stub, no working alias.
  **Rationale**: pre-stable 4.0.0rc is the correct window for a clean rename (operator ruling).
  **Alternatives**: deprecated back-compat alias (the issue's AC — overridden, C-004); indefinite alias (rejected — overload never retires).
- **Decision**: physically rename module files. **Rationale**: full terminology fidelity (operator ruling).
  **Alternatives**: symbols-in-place keeping filenames (rejected by operator despite lower blast radius).
- **Decision**: v1 breadth = command + code + gate-step + templates + guard + high-value docs; defer long-tail.
  **Rationale**: drift guard is shrink-only, so deferred prose stays grandfathered and cannot regress.

## Frozen KEEPS (adjudicated against source — do NOT rename)

- `baseline_merge_commit` **meta.json wire-key** — drives phase derivation at
  `src/mission_runtime/lifecycle_phase.py:237-239` (absent → `PRE_CONSOLIDATION`; present + Target Ref → CONSOLIDATED).
  Renaming the persisted key split-brains phase routing across versions. Freeze the key; boyscout only local identifiers.
- `MergeStrategy` enum + `MergeState.strategy` **value `"merge"`** (`merge/config.py`) — git-strategy serialized contract (Sense B).
- `state.json` filename under `.kittify/runtime/merge/<id>/` — renaming strands in-flight resumable consolidations.
- `merge-driver-*` commands + `.gitattributes` wiring — literal git plumbing (Sense B).

## Adversarial-evidence dispositions (contracts/adversarial-evidence-contract.md)

| Finding (source lens) | Disposition | Note |
|---|---|---|
| `baseline_merge_commit` should be renamed (classification/larry) | **changed** | Adjudicated against source → FREEZE the wire-key; larry's Sense-A word-call correct, operational verdict is keep. |
| `baseline_merge_commit` is Sense-B (adversarial/paula) | **changed** | Sense is A (post-merge review reviews the consolidated mission); but Paula's freeze hazard is decisive → keep key. |
| Brief sense-numbering inverted vs glossary (adversarial/paula) | **accepted** | Spec adopts glossary numbering (Sense 1 = lane consolidation). |
| Census "no merge mission-step / one source edit" (census/robbie) | **changed** | Operator-flagged: gate-step + prompt templates ARE in scope (IC-04/IC-05); addendum posted to issue. |
| `MergeState.strategy="merge"` persisted value (adversarial/paula) | **accepted** | Frozen KEEP. |
| Drift-guard false-negative + packs/ unscanned + size-pinned baseline (adversarial/paula) | **accepted** | Folded into IC-07 guard delta. |
| Second module `lanes/merge.py` (census/robbie) | **accepted** | Folded into IC-02 scope. |

No contested finding was silently dropped.

## Open risks carried into implementation

- Physical file rename × ~41 test files + ~15 external importers — coordinate importer/test updates in the same WP (IC-02).
- Byte-stable public `__all__` (#2057) must grow, never shrink, during the package rename.
- The `consolidate` word is already overloaded in-repo (`consolidate-charter-bundle`) — do not assume every existing `consolidate` is Sense 1; do not create new collisions.
