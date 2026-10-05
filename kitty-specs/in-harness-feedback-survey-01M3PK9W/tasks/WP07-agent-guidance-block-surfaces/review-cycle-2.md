# WP07 review cycle 2 — APPROVED

Reviewer: claude:opus:reviewer-renata:reviewer. Fix commits 911f8381e..870818560 (lane-g).

## Cycle-1 blockers
- Shell injection (B1): `_BLOCK_BODY` and both pack prompts now show `--comment '<text>'` / `--email '<address>'` plus the single-quote rule (`'\''`, collapse newlines, never double quotes). Fixed.
- TOML shim (gemini/qwen): `generator.py` now escapes `\` before `"""`; `test_toml_shims_round_trip_the_block_byte_exact` parses the TOML and proves the rule survives. Fixed.
- op_close: SKILL.md "After closing" and the dispatch capsule line limit the survey to outcome `done` or `failed`, never `abandoned`. Fixed.
- Ordering (N1): `tasks/prompt.md` moves the survey block before Step 10 (handoff); test pins index order. Fixed.
- Consent (N2): SKILL.md and capsule line name "Send feedback?" and `--consent yes`. Fixed.
- Neutral wording: no company/vendor names in the changed text.

## Tests
911f8381e adds 68 test lines only, before the source fix in 2daef086e, so the new tests were red on arrival by construction. 890283e27 is a format-only change.

## T041 parity test
Net diff vs 9e7c7c2e6 is +24/-3: retired glob replaced by the pack glob, zero-match assertion added, zero-match negative control and pack-scan positive control added. Not weakened.

## Not re-run (per operator)
feedback suite, shims/skills/dispatch, architectural gates, mypy/ruff, DRG — already verified by the operator.
