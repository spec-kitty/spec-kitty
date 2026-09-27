# Exemption mechanism -- `_GATE_ARTIFACT_FILENAMES`

<!-- Machine-readable exemption-registry row (R-014). Parsed by
     tests/architectural/test_exemption_registry_ratchet.py. ONE mechanism per
     file, so a retirement WP deletes ONLY its own row and never collides with a
     sibling retirement editing a shared file (squad-mandated design; the plan's
     stated reason for rejecting golden-count mode).

     Registered 2026-08-07 as a landing-pass fix for PR #3245
     (verdict-seam-write-unification): the R-014 negative scan is scoped to
     `src/specify_cli/consolidation/executor.py` (a CHURN_SURFACE_MODULES member) and
     discovered this pre-existing #2804/FR-009 (write-surface-coherence WP08)
     literal, which predates the tool_artifact_enrolment ratchet's own WP10
     landing census and was never enumerated. This row is `status:
     justified-survivor`, not `expected-present` -- see "Why this cannot route
     onto the owner" below. -->


- mechanism: `_GATE_ARTIFACT_FILENAMES`
- module: `src/specify_cli/consolidation/executor.py`
- literals: `_GATE_ARTIFACT_FILENAMES`
- symbol: `_GATE_ARTIFACT_FILENAMES`
- retirement-wp: `n/a — pre-existing #2804/WP08 mechanism, landing-pass registration`
- retirement-ref: `n/a`
- owner-route: `n/a — genuine survivor, outside is_toolchain_generated_churn's scope`
- status: `justified-survivor`

## Why this cannot route onto the owner

`_GATE_ARTIFACT_FILENAMES` is consulted by `_gate_artifact_paths` to build the
TARGET-checkout paths `_capture_pre_target_gate_artifacts` snapshots before the
mission -> target squash merge, and `_restore_regressed_gate_artifacts` restores
verbatim afterward if the squash step's `-X theirs` conflict resolution
clobbered an already-accepted copy (#2804). Both filenames
(`acceptance-matrix.json` / `issue-matrix.json`) do happen to be the basenames
of the two `MissionArtifactKind.ACCEPTANCE_MATRIX` / `ISSUE_MATRIX` PLACEMENT-
partition kinds `is_toolchain_generated_churn`'s residue leg
(`is_coord_residue_churn`) already classifies -- but that owner answers a
different question than the one this call site asks:

- `is_toolchain_generated_churn(path)` classifies **one already-observed path**
  as toolchain-generated churn a *dirty-state gate* should ignore. It cannot
  hand back "the canonical basenames for kind X" -- `mission_runtime` exposes
  only the forward `basename -> kind` classifier
  (`kind_for_mission_file`/`_MISSION_FILE_KIND_BY_BASENAME`), no public reverse
  `kind -> basename` lookup this call site could consult instead.
- This mechanism needs the reverse direction UNCONDITIONALLY: it must build
  the two candidate target-checkout paths (to snapshot bytes, possibly `None`
  when the file does not yet exist) *before* the squash merge runs, not
  classify an existing path's dirty-state disposition after the fact. Even a
  hypothetical `is_toolchain_generated_churn`-backed rewrite would still need
  to re-spell the same two basenames somewhere to construct the candidate
  paths -- routing through the owner would not remove the literal, only
  relocate it behind an unjustified extra indirection.
- Forcing this through the owner would also silently widen scope: the owner's
  full union additionally matches self-bookkeeping kinds (`meta.json`, Op
  records) this call site has no interest in snapshotting/restoring across the
  squash boundary (#2804 is specifically about the two gate-artifact kinds).

`_GATE_ARTIFACT_FILENAMES` is therefore the minimal, narrow, **registered**
survivor for exactly these two basenames: enumerated here so it is visible to
any audit of unowned filename exemptions, never a silent module-level tuple.
