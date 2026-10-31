---
affected_files: []
cycle_number: 1
mission_slug: pinned-service-binaries-01M64N66
reproduction_command:
reviewed_at: '2026-10-29T22:17:17Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (cycle 1): reviewer approved; orchestrator folds four small defects before approval

The contract, tests, layering and quality gates all pass (119 tests). Fix these four, then resubmit:

1. **Credential leak in refusal text (security, must fix).** The repository refusal shows a 40-character preview of the value, so a URL such as `https://user:ghp_xxx@host/...` exposes part of the token. Redact the userinfo before previewing (render `https://***@host/...`), or name the field without echoing the value. Add a test where the token never appears in the message.
2. **Whitespace-only `requires_core`.** `'   '` is accepted. Refuse a blank value after `strip()`, and add a parametrized case.
3. **Weak stem-mismatch assertion.** `test_stem_mismatch_refuses` matches on `"service"`. Assert the specific phrase, for example `"does not match the file name"`.
4. **Immutability on direct construction.** `ServicePin(protocol_versions=[1])` keeps a list. Coerce `protocol_versions` to a tuple in `__post_init__` (via `object.__setattr__`), and test that a directly built pin holds a tuple.

Optional: a missing-key test for one more required key besides `requires_core`.

Same rules as before: only the 3 owned files, ruff/format/mypy/C901 clean, and no allowlist entry for the dead-module flag (WP03 adds the caller).
