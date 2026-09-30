---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T17:04:30Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1) — reviewer-renata

Verdict: changes requested. Two accuracy gaps against the locked design; everything else passes.
Both fixes are small additions to amendment text. Neither adds a heading, so the docs index is unaffected.

## Required changes

1. **ADR 2026-09-03-1-adjacent: ADR 2026-06-07-1 amendment omits the second new public symbol (C-005).**
   `data-model.md:68`, `plan.md:165/212` and WP01 T00x (`tasks/WP01-*.md:96,185-187`) lock
   `OwnedRefusalCode` (`StrEnum`, value == name) as a **second** new `mission_runtime` root export,
   added to `__all__` and pinned in `_PUBLIC_SURFACE` alongside `OwnedCheckout`. C-005 requires a
   note on ADR 2026-06-07-1 for each new public mission-runtime symbol, and this ADR is the governing
   statement of the lean surface. The new bullet records only `OwnedCheckout`.
   Fix: extend the 2026-09-28 bullet (no new heading) to also record `OwnedRefusalCode` — the
   `OWNED_*` refusal-code registry from `data-model.md`, exported on the root with `OwnedCheckout`
   so code and tests import members instead of repeating literals (Sonar S1192), also pinned in
   `_PUBLIC_SURFACE`. Optionally note that `OwnedCheckoutPathRefused` is deliberately NOT exported
   (it subclasses the already-public `ActionContextError`). Adjust the bullet title if it names only
   `OwnedCheckout` (e.g. "`OwnedCheckout` and `OwnedRefusalCode` added to the root surface").

2. **ADR 2026-08-12-1 flagless-adoption bullet omits the required retirement statement (T013 step 3).**
   The WP prompt requires: "State the retirement: `missions/operation_context.py`, which adopted
   cwd without validation, is deleted (research R-09)." `grep operation_context` over the amended
   ADRs returns nothing. This is the concrete code path the "not inferred from CWD" qualification
   replaces, so readers need it. Fix: add one sentence to the "Validated flagless adoption" bullet
   naming `missions/operation_context.py` as the retired unvalidated cwd adopter (research R-09).

## Optional nits (non-blocking)

- 2026-08-12-1 amendment: the create-time governance bullet could cite FR-016/FR-017/C-004 and the
  repository-root refusal bullet research R-14, as the WP prompt lists them (traceability only).

## Verified PASS (no action)

- Original Decision/Consequences text untouched (diff is additions only, plus the sanctioned
  Related-terms edit on `repository root checkout`); ADR frontmatter unchanged; `execution.md`
  `updated:` bumped to 2026-09-28.
- Per-command topology: `NEXT_OWNED_TOPOLOGIES = {single_branch, lanes, lanes_with_coord, coord}`
  matches `data-model.md:36` (the WP03 prompt's 3-member set was stale; LANES is correct per U1/R-02).
- Five new error codes match `data-model.md:61-65` exactly.
- Flagless adoption exclusions match `contracts/owned-checkout-carrier.md` §6; mission-context
  conflict refusal stated; create-time reads vs repository-root-only charter authoring (#4785, #4250) correct.
- Unified claim-commit review base, sole minter / `_mint` / `TypeError`, validate-once, G4/G5
  empty-allowlist gate with the org-pack module rule: accurate.
- Glossary entry: Definition / Use when / Do NOT use when / Related terms present; two-way link
  with `repository root checkout`; `#target-branch` anchor resolves.
- Terminology: no new bare "primary" checkout alias or "feature" in added text.
- Docs index regenerated with only this WP's 5 anchors; out-of-map edit declared.
- Gates: pytest (terminology, ADR invariance, docs index, index freshness, glossary linker)
  145 passed; `docs_index --strict` drift=False (833 pages); `check_docs_freshness --ci
  --link-check spot` exit 0, no findings in touched files (14 network/proxy link warnings, all in
  untouched files).
- Scope: `git show --stat 2c5e9a05e` touches only the 4 owned files + the declared index file.
