# Tracer: Design Decisions

Append load-bearing decisions + rationale as they are made.

## D1 — Reuse `asset_preservation`, do not add a parallel proof authority (C-001)
The removal chokepoint (`guard_destructive_removal` + provers) already encodes charter §463-479. The overwrite half must reuse the same `OwnershipProof` vocabulary, not invent a second one. (charter single-canonical-authority)

## D2 — Ownership by provenance/content, never by name (C-002)
`#4931` root cause is proof-by-name (`managed_relpaths`). Fix routes through the already-present `run_created` provenance branch. Name membership is downgraded from "proof" to "hint".

## D3 — Preserve-on-unprovable, exit success (C-003)
Destruction paths preserve+warn on unprovable ownership. The one place a *loud failure* is acceptable is `research` with no resolvable template (there is nothing to destroy — fabricating empty artifacts is the bug), which may fail rather than preserve.

## D4 — RESOLVED: one shared `guard_destructive_overwrite` primitive (WP-A), consumed by brief + research
Single decision rule when the dest holds non-package-owned bytes: proceed iff `authorized AND replacement_substantive`; else refuse (never fabricate empty, never truncate to empty even under --force). Lives in `asset_preservation/` beside `guard_destructive_removal` (one authority, C-001). Lane coupling handled by the dependency graph: primitive in WP-A, WP-B depends on it; WP-C is disjoint.

## D5 — RESOLVED (post-spec squad, reviewer-renata): #4931 needs TWO mechanisms, not one
- init.py (removal seam) → drop by-name `managed_relpaths`, use `run_created` provenance.
- template/manager.py (copy-over-existing = OVERWRITE) → `back_up_operator_subtrees(["templates"])` before the rmtree/copytree, mirroring the in-file `memory/` precedent (line 107, #4759). Forcing it through the *removal* chokepoint would mis-model an overwrite. NFR-003 amended to forbid that conflation.

## D6 — RESOLVED (post-spec squad): the arch gate cannot carry the regression promise
`test_mutation_ownership_routing` is a removal-shaped, line-pinned, shrink-only census over init.py+migrations. It cannot police the overwrite op class, out-of-set modules (manager.py), or a mis-configured-but-routed prover. Durable protection = behavioral issue-pinned regressions (FR-005 / SC-004). Arch-gate extension to research.py (FR-004) is a *partial* add: research's raw `unlink` must be routed away (census won't allowlist a raw user-content op).

## D7 — #4931 is tracker P0 (not P1). Corrected US1/FR-001. Audit sweep must not absorb #4907's `agent/config.py` (claimed).

## D8 — RESOLVED (post-tasks anti-laziness squad): two BLOCKERS folded before implementation
- **B1 (WP01)**: the brief chokepoint must refuse on `brief_path.exists()` **existence alone** (brief-only/sidecar-absent is the #4910 unknown-provenance case) and **before** the XOR cleanup at `mission_brief.py:73-75` — otherwise the XOR unlinks a brief-only file and the writer rewrites it, re-introducing #4910. RED-first must witness the DESTROYER via the base signature, not a `TypeError` from the new kwarg. Real chokepoint is `_commit_brief`/`_write_brief_from_candidate` (thread `overwrite=force`).
- **B2 (WP03)**: `templates/` is unprotected in BOTH `copy_specify_base_from_local:117` AND the pip-default `copy_specify_base_from_package:193` (`copy_package_tree` default `preserve_existing=False`). Fix both (mirror memory/missions). Regression must force the PACKAGE path directly (a repro inside a spec-kitty checkout resolves to the local path and hides the P0).
- **SF4 (WP02)**: the census can't auto-enforce "routed away, not allowlisted" for research (it routes through `guard_destructive_overwrite`, not `_removal`) — added an explicit assertion banning any `research.py:*` key from `_ALLOWLIST`.
- **SF5 (WP02)**: the init allowlist re-pin must verify a line-shift-only delta (same op-kinds/count), so a new literal can't hide as a "line shift".
