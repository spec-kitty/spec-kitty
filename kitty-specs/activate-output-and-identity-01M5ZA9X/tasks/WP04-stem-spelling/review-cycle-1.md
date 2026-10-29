---
affected_files: []
cycle_number: 1
mission_slug: activate-output-and-identity-01M5ZA9X
reproduction_command:
reviewed_at: '2026-10-27T22:17:51Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review (reviewer-renata): changes requested

Most of this WP is correct and well tested. I checked the served (in-force) set through `build_active_charter_service` for every writer on the stem!=id fixtures (org toolguide acme-tool-file/acme-tool-id, project tactic proj-tac/proj-tac-id, built-in 024-locality-of-change/DIRECTIVE_024), base against this lane. For all 13 writer scenarios the served set is identical and only the stored spelling differs. The re-pins are stale assertions of the bug, and several of them tighten the guard. Gates are clean, and mypy shows no new errors (the same 9 as on base). The red-first claim holds: the new test file has 19 failing on base src.

Two items need fixing before approval. Both are small.

## 1. BLOCKING: Decision `no_stem_id` makes `charter compile` fail where base compiled, and nothing pins that WP05 fixes it

Reproduction: use the shadow fixture of `test_stored_spelling_6527.py` (an org directive file `024-locality-of-change` declaring `ACME_024`, plus org `required_directives: [DIRECTIVE_024]`). Run a writer, then call `charter.activation.compiler.resolve_config_activated_roots(repo_root=root)`:

| writer | base | this lane |
|---|---|---|
| org-required union (`_promote_org_required_to_config`) | OK (skipped, warned) | `UnknownArtifactIdError: No directive artifact with config ID 'DIRECTIVE_024' ...` |
| interview (`narrow=False`) | OK | `UnknownArtifactIdError` |
| interview (`narrow=True`) | OK | `UnknownArtifactIdError` |

A writer in this WP can now store a token that blocks compile, where the same project compiled on base. The runtime gate serves `DIRECTIVE_024` correctly; only compile refuses. WP05/FR-016 ought to fix it: `IdentityIndex` knows the token (`declared_id == selection_id == 'DIRECTIVE_024'`), so a compile that resolves declared ids through the index will accept it. But WP05's prompt and test list never name this case. If WP05 resolves through `stem()` and then `resolve_artifact_urn`, the case stays red.

Required: in `tests/charter/activation/test_stored_spelling_6527.py`, add a test that runs the `no_stem_id` writers (org-required union, interview in both modes) on the shadow fixture and then asserts that `resolve_config_activated_roots(repo_root=root)` succeeds and includes `DIRECTIVE_024`. Mark it `xfail(strict=True, reason="WP05/FR-016: compile resolves a known declared id with no single stem through IdentityIndex")`, so WP05 has to flip it in the same PR. Say so in the WP history note.

## 2. Required (CLAUDE.md suppression rule): the two `# noqa: PLC0415` lazy imports in `kind_vocabulary._built_in_step_contract_dir` have an incorrect rationale

The stated reason is "the missions package is heavy; loaded only for this kind". It does not hold. `import charter.activation.kind_vocabulary` already loads `charter.offering.missions.step_contracts` through `charter/offering/service.py`, so the lazy import saves 0 s. There is also no cycle: importing `charter.offering.missions.step_contracts` does not import `charter.activation.kind_vocabulary`. Move both imports (`MissionsRootNotFound`, `MissionStepContractRepository`) to module level and drop the suppressions. If a real cycle appears when you do that, keep the lazy imports and give the actual reason.

## Non-blocking (note in the PR, or as follow-ups)

- **(a) A preset that lists an ambiguous directive id is still refused.** I accept this reading: it is fail-closed before any write, it is unchanged from base, and it never stores another policy's stem. The `PresetIdUnresolvedError` text "lists ids that resolve nowhere in the offering" is wrong for an id that resolves twice, though. Worth a follow-up.
- **(c) Preset warnings appear in text mode only.** Acceptable, because the `--json` contract is unchanged. A `--json` consumer never sees the warning, though. Follow-up: an additive `warnings` field, or a note on stderr.
- **Behaviour change in the shadow case.** `no_stem_id` changes what is in force there, by operator decision. An org-required `DIRECTIVE_024` is now served (base skipped it). Interview `narrow=True` now narrows directives to `[DIRECTIVE_024]`, where base left the key absent and served all 38. State this in the PR, because C-001 otherwise reads "never which artifacts are in force".
- **`test_the_in_force_set_is_unchanged_by_the_spelling` checks only one entry per artifact, not the served set.** Consider also asserting that `build_active_charter_service(root).<kind>` is unchanged across the absent-key materialisation. I verified by hand that it is.
- `cda50a70` only deletes `kitty-specs/.../mission-events.jsonl`, a bookkeeping file. Fine.
- FR-015: every built-in step-contract stem equals its id, so the change to the scan source does not alter any gated or served set. The architectural, offering and step-contract suites are green.
