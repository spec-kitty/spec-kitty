# Tracer: Approach

## Spine
Extend the landed `asset_preservation` **removal** ownership-proof chokepoint to the **overwrite/truncate** seam. One invariant (charter §463-479), three defect sites.

## Grounding (pre-spec squad, opus, profile-loaded)
- Alignment/reproduction lens (`debugger-debbie`): all three STILL-REAL on main `1bda7bc19e`, live-reproduced; none superseded. #4931 has TWO destroyers (by-name guard at `init.py:1573` + full-copy `manager.py:118` rmtree). #4926 arch-gate coverage gap: `test_mutation_ownership_routing` polices init+migrations, not research.
- Scope/boundary lens (`paula-patterns`): canonical authority already exists (`src/specify_cli/asset_preservation/`, from `ownership-boundary-preservation-01M32KEN`). #4931 = mis-wired existing chokepoint (drop by-name, use `run_created`). #4926+#4921 = overwrite seam with NO chokepoint. Prior-art to reuse: `verdict-matrix-rmw-preservation-01M32M9G` locked read-modify-write.

## Sequencing
- FR-003 (#4921) is the cleanest structural template (push invariant into chokepoint) — land first as the reusable pattern.
- FR-002 (#4926) reuses the overwrite discipline + extends the arch gate.
- FR-001 (#4931) independent (removal seam re-wire) — parallelizable.
- Audit task: sweep all `guard_destructive_removal` call sites (10 migrations + skills/installer.py) for other `managed_relpaths`-by-name shortcuts.

## Coordination note
#4907 (claimed) is the SAME removal seam as #4931 — both touch guard call-site prover wiring. Keep the prover-wiring approach consistent so the two do not diverge.
