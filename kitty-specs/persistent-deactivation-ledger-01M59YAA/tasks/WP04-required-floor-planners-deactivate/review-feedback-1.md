# WP04 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata). Base c593757b; commits 01e7f221 (red), 62eaa26d, f65c5832, cf2b6225, 1b0b37c1, 2db3047e.

The design, the floor reader, the planners, the refusal seam, the CLI and the retirement of the error are sound.
The only blocking gap: the activation-side deny glue in the manager is new production code that no test runs.
A manual probe shows that it works. The fix needed is tests only, plus optional lows.

## Blocking

- [MEDIUM] src/charter/activation/pack_manager.py:524-554 (`_deny_inputs` non-empty branch, `_without_denied`), :1037 (the "Cleared the exclusion" line).
  - **Issue:** no test runs this code. Diff coverage over the WP04 suite: pack_manager 43/55 added lines, and lines 537-554 are all missed. That leaves four gaps:
    - FR-008 at the manager/CLI level: `charter activate` clears a deny entry, including the rewrite of a declared id (`DIRECTIVE_003`) to its stored stem.
    - The deny subtraction when an absent list is materialised (#4253 path): activating A while D is denied must not write D into the allow list.
    - The strict floor read on activate when a deny list is present (FR-013), which is a new refusal path.
    - NFR-001 ("asserted by tests for every refusal path") for that activate-side refusal.

    The planner tests in test_deny_planning.py do not reach the manager.
  - **Required fix:** add a ledger-seeded, strict test file (append it to `SWEPT_PREFIXES`) that drives `charter activate` through `CliRunner`, or `ActiveCharterManager.activate`. It must cover:
    1. `deactivate directive DIRECTIVE_003`, then `activate directive DIRECTIVE_003` → `deactivated_directives` is removed and `activated_directives` stays absent.
    2. Absent allow list with D denied, then `activate` A → the materialised list holds A and leaves out D, and D stays denied.
    3. `[A, D]`, deactivate D, then activate D → allow `[A, D]` and no deny key.
    4. A deny list is present and the declared org pack's `org-charter.yaml` is malformed → `activate` exits non-zero and all three activation files stay byte-identical. Put a same-fixture positive control first (an activation that succeeds before the pack is corrupted).

## Non-blocking (fold if cheap)

- [LOW] src/charter/activation/org_pack_discovery.py:187, :325, :326 - `# noqa: PLC0415` has no inline rationale. The charter requires one for each suppression, and :551 already has one. Add a short reason, e.g. "lazy: avoids an import cycle".
- [LOW] src/specify_cli/cli/commands/charter/deactivate.py:145-146, :185-194 - three branches have no test: the cascade child's `ValueError` branch, the agent-profile mission-binding warning in a cascade, and the `UnknownArtifactIdError` skip in `urns_of`. Add a test, or note them for WP10's conformance table.
- [LOW] src/charter/activation/pack_manager.py:754 - the guard "never create an empty ledger" (carry-forward from WP03) has no strict test. Add one: a no-op write on a fresh project creates no `activation.yaml`.

## Judged points (accepted)

- **NFR-003:** WP04 did not cause the slow timings; it only inherited them. Same commands on a copy of this repository's `.kittify/`, warm runs 2-3, base bffd2ff9 then head:

  | Command | Base | Head |
  |---|---|---|
  | `deactivate` | 8.9 / 9.6 s | 8.6 / 8.7 s |
  | `activate` | 15.1 / 14.9 s | 13.2 / 13.4 s |
  | `list` | 3.9 / 3.5 s | 3.2 / 3.2 s |

  This is a pre-existing NFR gap for the orchestrator to file. The fixture timing test passes (1 passed).
- **test_resynthesize_and_hotpath `*without_resynthesize*`:** both fail on bffd2ff9 too, so they were already failing before WP04.
- **Deviations:** all accepted.
  - The cascade tests use agent profile randy-reducer.
  - A denied id counts as known, so a second deactivate warns.
  - Org-pack fixtures live in `org-packs/`.
  - Strict mode also refuses an empty `org-charter.yaml` and a non-directory pack path. This matches the "unreadable or malformed" wording, and `require_org_skill_policy_readable` set the precedent.
  - The floor is read on activate only when a deny list is present, which matches the spec edge case.
  - Edits outside the owned files are forced by the iterator signature change, or were asked for by carry-forward L4/L5. Shared-file note for WP05/WP07: `activation_block.py`, `consistency_check.py`, `command_renderer.py`, the `api.py` re-export, `test_pack_skill_lifecycle.py` and `test_charter_activate_cli.py` were touched here.
- **C-005:** no definition of `_fold_policies`, `resolve_pack_chain` or `_resolve_chain` changed (only calls were added).
- **C-008:** `NoActivationRestrictionsError` is gone from src/ and tests/. It appears only in the accepted ADR (2 mentions).
- **Red first:** 01e7f221 gives 13 failed and 2 collection errors.
- **Baseline:** went from 236 to 235 in the same commit (f65c5832) as the import removal.
- **Refusal tests:** they have positive controls on the same fixture and assert byte identity.
- **Signatures:** all commits are signed.
