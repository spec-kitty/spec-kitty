---
affected_files: []
cycle_number: 1
mission_slug: requirement-id-grammar-01M3NRCA
reproduction_command:
reviewed_at: '2026-09-29T09:26:02Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (reviewer-renata), cycle 1

Verdict: changes requested. Most of the WP holds up. Red→green is proven: at 8277177502 the function-level repro fails with `'FR-006a' in ['FR-001']` and the CLI repro exits 0; both are green at the tip. The validation surface (371), the named gates (186), mypy --strict, ruff check, C901 and the retention controls all pass, and scope is clean. Three items block approval.

## BLOCKING

### 1. The required `classify_stale_refs` re-pin was not done, so a synthetic pin still asserts behaviour that FR-003 retired
- `tests/specify_cli/test_requirement_mapping.py:69-76` (`TestClassifyStaleRefs::test_splits_malformed_and_unknown`) still hand-feeds `malformed=["FR-003A"]` and asserts that `FR-003a` is `malformed`.
- T004 "Re-pins" requires two things here:
  - `FR-003a` moves to `unknown_spec_id`;
  - the test is fed the real `validate_ref_format(...)` output.
- As written, the test passes only because of the hand-typed list. Deleting the grammar would leave it green (a synthetic fixture). It also contradicts the production path: the WP03 smoke flip shows that `FR-003a` is now `unknown_spec_id`.
- Fix:
  - Compute `_, malformed = validate_ref_format(["FR-003a", "FR-999"])`, pass that in, and assert `{"malformed": [], "unknown_spec_id": ["FR-003a", "FR-999"]}`, with a one-line FR-003 comment.
  - Keep a malformed control on the same fixture (for example `FR-003.1` or `<FR-XXX>`).
  - Update the stale `classify_stale_refs` docstring (`requirement_mapping/__init__.py:505-507`), which still cites `FR-003a` as a malformed example.

### 2. A second hand-written kind alternation, and a C-001 floor that is non-vacuous only by accident
- `grammar.py:283`: `MALFORMED_DECLARED_LEAD` hand-writes `(?:FR|NFR|SC|C)`. The WP forbids this ("Do not write any second ID alternation literal anywhere"; every pattern must be generated from the core).
- That literal is the ONLY grammar.py site the gate detects. The live census shows exactly one grammar.py site, at line 278. The core (`_KIND_DIGITS` at `grammar.py:83`, built from a `"|".join` plus an f-string) is invisible to the detector.
- As a result, `test_floor_grammar_py_has_at_least_one_site` (`test_requirement_id_grammar_single_source.py:311`) goes red as soon as #2 is fixed.
- Mutation check: a scratch module that copies grammar.py's own idiom, `_K = "|".join(("FR","NFR","C")); re.compile(rf"\b(?:{_K})-\d+\b")`, is NOT flagged. A plain `r"(?:NFR|FR|C)-\d+"` is flagged.
- Fix:
  - Define the contract's single core string as ONE detectable literal (e.g. `_CORE = r"(?:FR|NFR|SC|C)-\d+"`, or a kinds literal `"FR|NFR|SC|C"`).
  - Generate every pattern from it, `MALFORMED_DECLARED_LEAD` included. Its kind part must stay case-sensitive, so reuse the alternation without `(?i:)`.
  - Make the floor test assert that the detected grammar.py site IS that core constant (by constant name), not just any site.

### 3. `find_all` leaks a local ID out of an invalid qualifier (FR-009)
- `grammar.py:186-187`: `#` counts as a `\b` boundary, so when the slug fails the qualifier grammar the match restarts after the `#`. Observed at the tip:
  - `Other-Mission#FR-001` → `['FR-001']` (local);
  - `other_mission#FR-001` → `['FR-001']`;
  - `x.y#FR-001` → `['y#FR-001']`.
- `parse()` returns `None` for these tokens, so the two functions disagree. Through `normalize_requirement_refs_value` (the finalize write path until WP02) and `_parse_requirement_refs_from_tasks_md`, a mis-typed foreign citation silently becomes local coverage. FR-009 and the spec edge cases say a qualified citation is never counted as this mission's own.
- Fix: add an in-code leading-context check that mirrors `_is_compound_tail` (no lookbehind). Drop a match whose start is preceded by `#`, or treat the whole `...#ID` run as not-an-ID. Pin each case above with a same-text positive control.

## NON-BLOCKING (please fold if cheap)
- `test_requirement_id_grammar_single_source.py:401-438`:
  - the growth and drop tests only assert arithmetic on synthetic YAML, not a gate function;
  - the live test hard-codes `3`, so WP04 must edit the test as well as the YAML.
  - Suggestion: one `check_allowlist_ratchet(path) -> list[str]` helper, used by both the live test and the synthetic tests.
- `test_requirement_id_grammar.py:188-200`:
  - the declared-shape test covers only `SC-001`, not `FR-006a`, per shape;
  - it uses `any(...)` instead of asserting `group(1)` from the intended shape.
- `test_requirement_mapping.py` (HTML-comment pin): the positive control uses a different ID (`FR-005`), not the same `FR-004` row outside the comment, as T004 step 2 asks.
- `test_re2_is_active_and_every_exported_pattern_compiles` omits `_LEGACY_REF_FIND_PATTERN`, the comment patterns, `_COMPOUND_TAIL` and `_TOKEN_SPLIT`.
- `grammar.py:155,186,187` each re-spell `(?P<kind>(?i:{_KIND_ALT}))-(?P<digits>\d+)`. Prefer one named-group core.
- `__init__.py` reaches into `grammar._is_compound_tail`. Consider a public helper, or folding the check into the declared scan.
- `RequirementId.is_functional` and `is_success_criterion` have no production caller yet. This is fine if WP02/WP03 consume them; record that in the tracer notes.
