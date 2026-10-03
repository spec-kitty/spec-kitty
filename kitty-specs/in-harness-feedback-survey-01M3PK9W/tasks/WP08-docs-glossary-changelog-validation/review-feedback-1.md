# WP08 Review Feedback — REQUEST_CHANGES (cycle 1)

**Reviewer:** claude:opus:reviewer-renata:reviewer
**Commits reviewed:** `c447f41c3` (docs), `a77def08e` (CLI baseline re-pin 281->282)

## Verdict

REQUEST_CHANGES. The content is correct; one required deliverable is missing.

## Blocking

### B1. Validation evidence is not recorded (T046; Review Guidance "quickstart evidence is present")

T046 and the WP Review Guidance require the quickstart walkthrough evidence, the gate commands with counts, the grep-neutrality command with its zero-hit result, and the SC-006 status to be recorded in the WP Activity Log. The Activity Log contains only "Prompt created", and `traces/*.md` carry only one-line "verified against a live quickstart run" statements. Nothing records:

1. The quickstart steps 1-7 key outputs: `--status` text, the received JSON body, and the agent-check/submit JSON, so they can be compared with `contracts/feedback-submission.schema.json`.
2. The commands and counts of the gates run: terminology, env-var-scope, `tests/docs` (1465 pass, 1 pre-existing fail `test_human_table_renders_with_no_rich_markup_leak`, also failing on the primary checkout) and `test_check_cli_reference_freshness.py` (33 pass).
3. The neutrality grep command and its zero-hit result.
4. SC-006 stated honestly as PARTIALLY verified: generated surfaces carry the survey block for Claude (`.claude/skills/spec-kitty/SKILL.md`), Codex (`.agents/skills/*`) and Cursor, plain terminal covered by quickstart, and no interactive harness session was run (the reason).
5. The out-of-map edits and one-line rationale each: the page inventory, the docs retrieval index, the tracer files, and the `tests/docs` re-pin (+1 for the spec-required top-level `feedback` command; band 254..310; no weakening beyond that).
6. That root `CHANGELOG.md` is a symlink and the canonical `docs/changelog/CHANGELOG.md` was edited.
7. That no `.contextive/feedback.yml` was produced (already in the trace; repeat it in the log).

**Fix:** append these as dated Activity Log entries in the WP08 prompt, chronological order. No code change is needed.

## Verified OK (no action)

- Every command, flag, field, env var and path in the how-to and reference pages matches the shipped code: `--status`/`--prompts`/bare command, `never` and Enter skip tokens, https-or-loopback validation, the 2000-char comment cap, the `feedback.json` fields and 0600/64 KiB/symlink/owner checks, the config-dir resolver, and `DistributionProfile.feedback_endpoint = None`.
- The "what is sent" list equals `ALLOWED_KEYS` and the contract. The known limitation about an unwatched agent session is stated plainly.
- The glossary has 4 terms as `candidate` with avoid lists. "Telemetry" appears only as an avoid term. Each new page has one Divio type and `updated:`. The pages are indexed in the context index, collaboration index, `toc.yml`, the inventory and the retrieval index.
- Neutrality grep over the added lines: no company or product names, and no hosts other than `example.test` and loopback.
- The CHANGELOG entry is under Unreleased with no version number. The symlink is legitimate.
- The re-pin is minimal: baseline +1 and band shifted +1, with the docstring explaining why.
