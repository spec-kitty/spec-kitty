# Tasks: Host-aware mode predicate for tool-surface planners

**Mission**: `host-aware-mode-predicate-01M7X6B1` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-4927-host-aware-mode-predicate`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | NTFS emulation fixture (shared test helper) | WP01 | |
| T002 | Red: predicate unit matrix (both hosts) | WP01 | [P] |
| T003 | Red: global skills + global assets converge under emulated Windows; POSIX twins | WP01 | [P] |
| T004 | Predicate + `effect_action` in `tool_surface/operations.py`; validator uses it | WP01 | |
| T005 | `runtime/asset_preparation.py` delegates to `effect_action` (delete local `_action`) | WP01 | |
| T006 | Red: Windows read-only drift + latent sites (bundles, profiles, native_config) + re-pins | WP02 | |
| T007 | Unify `command_installer.effect` and installer project ladder on `effect_action` | WP02 | |
| T008 | Re-point stamp rechecks (`_command_parent_receipts`, `_recheck_command_completion`) to `state_equivalent`; delete `windows_dir_mode_only_divergence` | WP02 | |
| T009 | Latent sites: `projection` (`_stage_effect`, recheck substitutions, finalize), `agent_profiles`, `native_config` | WP02 | |
| T010 | Apply-side conditional chmods (`installer` symlink, `skills/manifest.py`) + `charter_yaml_io` seam campsite | WP02 | |
| T011 | Red: gate self-mutation and stale-exemption tests | WP03 | |
| T012 | AST ratchet gate with adjudicated exemption table and floor | WP03 | |
| T013 | Live-mutation control + changelog fragment | WP03 | |

## WP01 — Shared predicate and global planners converge (P1)

**Prompt**: [tasks/WP01-predicate-and-global-planners.md](tasks/WP01-predicate-and-global-planners.md)
**Goal**: one host-aware mode equivalence (IC-01) and the reported leak (IC-02) fixed: global skills and global assets plan zero effects after one apply on an emulated Windows host, and POSIX drift still converges.
**Independent test**: `tests/specify_cli/runtime/test_global_mode_convergence_windows.py` is red on the base commit and green after.
**Requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, C-001, C-002, SC-001, SC-002

T001 NTFS emulation fixture (WP01)
T002 Red: predicate unit matrix (WP01)
T003 Red: global convergence + POSIX twins (WP01)
T004 Predicate + effect_action + validator (WP01)
T005 asset_preparation delegates to effect_action (WP01)

**Dependencies**: none. **Risks**: the host-aware validator refuses raw chmod planners on Windows until WP02 lands; both land in the same PR.

## WP02 — Project/provider planners, rechecks and latent sites (P2)

**Prompt**: [tasks/WP02-project-planners-and-latent-sites.md](tasks/WP02-project-planners-and-latent-sites.md)
**Goal**: every remaining observed-vs-planned decision and recheck goes through the predicate (IC-03); `windows_dir_mode_only_divergence` is gone; Windows read-only drift converges for project skills; latent refusals do not fire.
**Requirements**: FR-002, FR-005, FR-006, FR-007, FR-008, FR-009, FR-011, C-006

T006 Red: read-only drift, latent sites and re-pins (WP02)
T007 Unify command_installer and installer ladders (WP02)
T008 Re-point stamp rechecks; delete the old helper (WP02)
T009 Latent sites: projection, agent_profiles, native_config (WP02)
T010 Apply-side conditional chmods + charter_yaml_io campsite (WP02)

**Dependencies**: WP01. **Risks**: project-skill Windows semantics change (file mode ignored → write bit compared); projection substitution sites must keep `same_observation` exact for non-mode fields.

## WP03 — Ratchet gate and changelog (P1)

**Prompt**: [tasks/WP03-ratchet-gate-and-changelog.md](tasks/WP03-ratchet-gate-and-changelog.md)
**Goal**: `tests/architectural/test_mode_equality_authority.py` fails on any raw observed-vs-planned mode decision in `skills/`, `tool_surface/` or `runtime/`, proven non-vacuous; changelog fragment records the fix and the semantic change (IC-04, IC-05).
**Requirements**: FR-010, NFR-004, SC-003, C-006

T011 Red: gate self-mutation and stale-exemption tests (WP03)
T012 AST ratchet gate + exemption table + floor (WP03)
T013 Live-mutation control + changelog fragment (WP03)

**Dependencies**: WP02. **Risks**: AST shape over-match; mitigated by per-entry rationale and stale-entry failure.

## Sequencing

WP01 → WP02 → WP03 (linear; each review needs a separate reviewer session).
