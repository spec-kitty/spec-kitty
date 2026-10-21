---
affected_files: []
cycle_number: 1
mission_slug: persistent-deactivation-ledger-01M59YAA
reproduction_command:
reviewed_at: '2026-10-19T23:15:45Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback, cycle 1 (reviewer: claude / reviewer-renata)

Verdict: **changes requested**. Two blocking defects, both on the `--include` path of
`charter context` that FR-016 / D-21 name explicitly. The rest of the WP is sound: red proof
holds at b6a75db6 (26 failed, 2 collection errors), there is one identity-space subtraction on the
read path, the gate is non-vacuous, and NFR-003 holds.

## Blocking

1. [HIGH] src/charter/activation/context.py:375-385 (`_deactivated_include_note`) - the deny
   check compares the raw selector identifier with the `DenySet` spellings, but the include
   renderer then resolves other spellings of the same directive. With
   `deactivated_directives: [003-decision-documentation-requirement]`, these selectors render the
   full DIRECTIVE_003 body: `directive:directive_003`, `directive:3` and `directive:003`.
   Only `directive:DIRECTIVE_003` and the stem get the note. FR-016 says the deny applies "in
   identity space (stem, declared id and URN agree)" for `--include <kind>:<id>`. Required fix:
   resolve the identifier before the check. One way is to run `resolve_deny(kind, [identifier],
   identity)` with the include's IdentityIndex and refuse when its spellings intersect
   `deny.spellings()`. Another is to check the artifact id the renderer resolved. Add these
   spellings as parametrized cases to the deactivated-note tests (a ledger-seeded new file, or
   test_charter_readers_honour_deny.py).
2. [MEDIUM] src/charter/activation/context.py:426-428 (`kind == "artifact"` branch) -
   `--include artifact:<id>` returns before the deny check, so `artifact:DIRECTIVE_003` and
   `artifact:python-pedro` render artifacts that are denied. T028.3 and D-21 say "gate every
   kind". Required fix: apply the same deactivated note after the generic lookup has resolved
   the artifact's kind and id (exit 0), and add a test with a positive control.

## Required in this cycle (single authority, ruling on the implementer's open question)

3. [MEDIUM] src/charter/activation/activation_engine.py:852-854 (`_promotion_denied`) - this is a
   second deny subtraction, done in raw-string space with the floor exempted by raw strings. It
   can disagree with identity space. Reproduction: `deactivated_directives: [DIRECTIVE_003]` (a
   hand-edited declared-id entry) with an absent `activated_directives`. Seeding through
   `_plan_promotion` then writes `003-decision-documentation-requirement` into the new allow-list,
   and `skipped_denied` does not report it. Readers still net it, so nothing denied is served, but
   ADR 2026-10-19-1 Decision 2 calls for one subtraction, and WP05 owns this file. Required fix:
   derive `denied` from `activation_ledger._effective_deny(...)` (IdentityIndex, built only when
   the deny list is non-empty, NFR-003) and filter with `DenySet.admits` in `_plan_promotion` and
   `_skipped_ids`. Extend the single-helper pin so that no raw deny subtraction remains. If you
   judge it out of scope, hand it to WP07 explicitly in the carry-forward with this
   reproduction. Do not leave it silent.

## Non-blocking (fold if cheap)

4. [LOW] tests/charter/activation/ - add a parity test pinning that the read path
   (`load_denied`, raw `read_org_required_tokens`) and the write path
   (`pack_manager._deny_inputs`: `read_org_required_provenance` stems -> `_effective_deny`)
   give the same D*. Use the fixture where a required id is declared as `DIRECTIVE_003` in one
   pack and as its stem in another (plus the declared-id deny case). The reviewer probed 11 such
   fixtures and all agree: `_effective_deny` re-spells every floor token through IdentityIndex,
   so raw vs stem is neutralised. No test pins that today.
5. [LOW] tests/charter/activation/test_deny_planning.py:256 - the test name still says
   `in_stem_space`; rename it to identity space.
6. [LOW] `PackContext.effective_ids` and `deactivated_urns` have no production consumer yet
   (WP06/WP07 consume them). This is an acceptable transient; keep them in the carry-forward.
7. [LOW] tests/architectural/test_no_raw_activation_membership.py - a truthiness fallback
   (`ctx.activated_x or everything`) is not flagged. This is optional hardening.

## Shared-file coordination

The out-of-map edits are accepted: `pack_manager._deny_inputs` (now `_effective_deny(...).stems`),
WP04's test_deny_planning.py helper test, `kernel.top_level_keys` and
`org_pack_discovery.read_org_required_tokens`. WP06 must drain the six "WP06 removes" gate
entries (already in the carry-forward).
