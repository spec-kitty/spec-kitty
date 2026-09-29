# WP09 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** Two statements contradict the shipped code (FR-023: a doc/code disagreement is a doc defect). Everything else checks out; see "Verified" below.

## Blocking

**Issue 1: the wrong doctor subcommand is named for the new findings.**

- **Where.** `AGENTS.md` (Execution Workspace Strategy: "`spec-kitty doctor identity` reports it, plus `LANES_MANIFEST_UNREADABLE`") and `docs/changelog/CHANGELOG.md` ("**New `spec-kitty doctor identity` findings**").
- **What the code does.** The `finding` column (`SINGLE_BRANCH_CODE_LANES_UNMIGRATED`, `LANES_MANIFEST_UNREADABLE`) is emitted by `_identity_audit.run_topology_audit`. That is wired to `@app.command(name="topology")` in `src/specify_cli/cli/commands/doctor.py`, i.e. **`spec-kitty doctor topology`**. `doctor identity` does not report these findings.
- **Required fix.** Say `spec-kitty doctor topology` in both places.

**Issue 2: the CHANGELOG `--commit-to-target` entry claims behaviour the code does not have.**

- **The claim.** "With `--commit-to-target` (persisted, honoured through `ProtectionPolicy` for every later write) the mission commits straight onto the target."
- **What the code does.**
  - Nothing outside mission creation reads `commit_to_target`: not `ProtectionPolicy`, not the commit router, not `safe_commit`.
  - I created a `single_branch` mission with `--commit-to-target` on a protected `main` (`meta.commit_to_target: true`, no mint), then ran `agent mission finalize-tasks`. It exits 1: `Bookkeeping refused: PROTECTED_BRANCH_REFUSED: … destination ref 'main' is on this project's protected branch list`. `implement WP01` also fails.
- **Required fix.** The entry must describe shipped behaviour. Which wording depends on the orchestrator's decision about the WP08 gap reported alongside this review:
  - if FR-008's "honoured through the existing protection authority" gets implemented, the current wording becomes true;
  - otherwise, state that `--commit-to-target` only skips the create-time mint, and that later writes onto a protected target are still refused unless the operator hatch (`SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`) is set.

  The same applies to the `AGENTS.md` bullet ("`--commit-to-target` opts out") and to the `mission-branch` / `protected-target` glossary rows, if they imply commits land on the target.

## Non-blocking

- **Nit 3.** `docs/context/topology.md` "Absorbed lane" omits the contract's third case, `tip == base` (`contracts/lane-work-tip.md`: ancestor, equal to base, or merge-tree no-op). Add it.
- **Nit 4.** "Execution-mode stamp": `direct_repo` is also stamped for `planning_artifact` work packages of every topology, because they resolve to the repo-root lane. The entry reads as `single_branch`-only; one clause fixes it.
- **Nit 5.** CHANGELOG #5115 says "every lane commit records `refs/spec-kitty/lane-tip/<branch>`". With a foreign `post-commit` hook the recorder is skipped (C-010), and only spec-kitty's own record points record the tip. Qualify it: "when the recorder hook is installed".
- **Nit 6.** The new `topology` context is not in `.kittify/traceability/contextive-map.yaml`, so no `.contextive/topology.yml` is generated. Add a map entry if `topology` terms should surface in the IDE. Pre-existing staleness is not a WP09 regression (see "Verified").

## Verified

- **Accurate claims.** These match the code:
  - the refusal codes (`WRITE_CHECKOUT_WRONG_BRANCH/OCCUPIED/DIRTY` in `implement_support.py`; `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` in `mission_runtime/context.py`; `DESTROYED_LANE` plus the restore command);
  - the create default (`lanes` on a non-primary branch; `single_branch` only via `--topology single_branch` / `--owned-checkout`);
  - the mission-branch mint and landing;
  - the ref name `refs/spec-kitty/lane-tip/<branch>`;
  - the migration IDs `4_0_0rc5_single_branch_code_lanes_restamp` and `4_0_0rc5_install_lane_tip_recorder`, and the `--restamp-single-branch [--dry-run]` flag.
- **Glossary.** Every glossary term has a "Do NOT use when" guard, and all cross-anchors resolve.
- **Terminology.** No new `feature` for Mission. `primary`, `merge` and `routing` are sense-qualified. No generic `main`. (The #5100 before-state "resolved the planning lane to `main`" quotes the old literal behaviour.)
- **Pre-existing red.** `tests/contract/test_terminology_guards.py::test_no_feature_flag_in_live_first_party_docs` fails identically on the clean mission base b1d39706. The file `docs/reports/tracer-friction-recon/2026-09-26/coverage-matrix.md` was last touched by 39c988c4, before the mission base. It is tracked by #5187, which is closed on main.
- **Contextive staleness is pre-existing.** `generate_contextive_glossaries.py check` gives identical output on the base and on this lane: `governance.yml` and `orchestration.yml` are stale, and `merge/.contextive.yml` is missing.
- **CLI reference.** `docs/api/*` is a faithful regeneration. `check_cli_reference_freshness.py` shows only pre-existing `moments drain` escaping warnings. The `provenance` wording change reflects current CLI help. Note it in the PR.
- **Sibling test.** The `test_coord_unprotected_lifecycle_loop.py` edits are comment/docstring-only and correct the now-false `SINGLE_BRANCH` default wording.
- **Gates.**
  - `test_terminology_guards` plus `test_no_legacy_terminology`: 111 passed, 1 failed (the pre-existing red above).
  - The docs gates (`test_description_length_gate`, `test_docs_seo`, `test_docs_structural_lint`): 882 passed.
  - `check_docs_freshness.py --ci`: errors=0.
