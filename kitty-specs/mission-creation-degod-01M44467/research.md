# Research: Mission creation degod

The grounding squad's full evidence is in `research/code-grounding.md` (architect, archaeology, gates, findings G1–G11) and `research/test-remediation.md` (test-suite quality assessment, findings T1–T10). This file records the plan-level decisions.

## R-1 Module layout

- **Decision**: a façade with a pure decision module and ten adapter leaves, using the `mission_creation_` prefix. The façade keeps `create_mission_core` and `_create_mission_core_impl`.
- **Rationale**: most façade patches (`ULID`, `_emit_create_events`, `_commit_create_scaffold`, `now_utc_iso`) are reached from the orchestrator, so they keep intercepting with no routing. The prefix lets gates derive the family from disk.
- **Alternatives considered**: a `core/mission_creation/` package. Rejected: it would change every `specify_cli.core.mission_creation.X` patch string into a package attribute lookup with the same interception problem, and touches more import sites. Moving the orchestrator out was also rejected: every façade patch would then need routing.

## R-2 Patch interception

- **Decision**: the PR #5679 routing rule (a lazy in-function `from specify_cli.core import mission_creation as _mc`, and leaves call `_mc.<name>` for every patched or cross-family name). It is enforced by a family check whose routed-name set must equal the set of names tests patch on the façade and that a leaf reads. That set is computed from the tests by the same AST walk the census uses.
- **Rationale**: 82% of the 277 sites patch imported names. Without routing they become inert without failing. A hand-kept list can drift, so set equality closes that hole (post-specify finding).
- **Alternatives considered**: extending `test_tasks_patch_targets_live.py` to the family. Rejected as the primary check: its scanner counts only bare name loads, so it would read `_mc.` routing as dead. It still runs as a regression check.

## R-3 Golden matrix capture

- **Decision**: a JSON snapshot keyed by cell id, captured with `SPEC_KITTY_REGEN_GOLDEN=1` on the unchanged base commit (recorded in the file). Normalisation is whitelisted (mission_id, mid8 wherever it appears, ISO timestamps, absolute temp paths). After WP01, the test module, normaliser and snapshot are frozen (0 diff lines, NFR-001).
- **Rationale**: a single snapshot makes "byte-identical" checkable at a glance, and freezing the harness blocks the "widen the normaliser" fake.
- **Alternatives considered**: per-cell inline asserts (verbose, easy to weaken), and syrupy (a new dependency, rejected).

## R-4 Error timing

- **Decision**: probes that can raise (`ProtectionPolicy.resolve`, `resolve_primary_branch`, `read_commit_to_target`) run at the same point in the create as today. Facts for a decision are gathered where today's first probe ran, and memoised from there.
- **Rationale**: raising earlier changes the residue left behind, which is the #5704 shape (post-specify finding). Baseline-red follow-up: #5704.

## R-5 Topology default

- **Decision**: not moved. It is pinned by tests that call `_resolve_default_topology_phase` and `coord_topology_reachable` directly, with the no-origin/HEAD fallback and both Primary Branch inputs named (follow-up: #5707).
- **Rationale**: the decision already sits in the CLI and is pure. Moving it would widen the file set into a file with 22 commits in 90 days and duplicate an authority.

## R-6 Patch census

- **Decision**: `tests/_support/patch_census.py` is a reporting tool with a self-test. It counts static sites (string, f-string on module constants, and object forms) for any name the module family reads, in any namespace, and counts runtime applications through a pytest plugin hook on the covering set. It is not a gate (C-002).
- **Rationale**: the issue's grep figure (57) was off by about 5x. A committed counter makes the before/after claim reproducible.

## R-7 Test migration verdicts

- **Decision**: the per-name verdicts in `research/test-remediation.md` §5 are adopted. Retirement needs a coverage-context proof (dead patch) or a planted break of the named guard.
- **Rationale**: Standing Order 4 and DIRECTIVE_041.

## R-8 Out of scope

- **Decision**: these changes are out of scope: the #5676 occupancy precondition, the #5704 hoist, the #5707 bias unification and the INV-COORD-HOME residual. Follow-up: #5676, #5704, #5707.
- **Rationale**: each changes observable behaviour (decision `01M446WTGDPEAGV4MSRD1CJK75`).
