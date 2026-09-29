---
affected_files: []
cycle_number: 1
mission_slug: requirement-id-grammar-01M3NRCA
reproduction_command:
reviewed_at: '2026-09-29T13:33:40Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review feedback (cycle 1) from reviewer-renata

## What holds

The measurements are sound, and none of the corrections below needs a new scan.

- I re-ran the scan at `ddf114f06c`, which is the true merge-base. The result is byte-identical to the committed `corpus-scan.json`, apart from `head_sha`: HEAD has moved to `09ea84976f`, which changes no `src/`.
- The paired WP tokens are equal on both sides: 0 mismatches over 10,854 tokens.
- The SC-005 positive control holds.
- The HTML-comment shrink class is confirmed empty. 13 specs contain `<!-- -->`, and none of those comments contains a requirement ID.
- I sampled 22 (c) growths and all 46 (d) items. All are correctly bucketed.
- The benchmark reproduces at +6.3 ms. Each wrapped function is called exactly once per side, finalize exits 0 on both sides, and the fixture stays clean.
- ruff, format, C901 and `mypy --strict` are clean. The ratchet gate shows 5 passed.

The committed REPORT, however, contains factual errors. For an evidence WP, those errors block approval.

## Issue 1 (medium, blocking): (d) misstates the base finalize verdict, so the list of "newly failing missions" is wrong

`corpus-scan.md` says of `kept/unknown -> rejected:unknown_spec_id` that "the old gate recorded these as 'unknown' but never blocked on it". It also says that excise and spdd will "newly (and correctly) fail". Both statements are false at the merge-base:

- `mission_finalize.py@ddf114f06c:1276-1297`: `_validate_requirement_mapping` emits the report and calls `raise typer.Exit(1)` whenever `unknown_requirement_refs` is non-empty.
- `mission_finalize.py@ddf114f06c:878-885`: `_read_spec_requirement_ids` calls `typer.Exit(1)` on a missing `spec.md`. This is `charter-doctrine-mission-type-configuration-01KSWJVX`.

So all 29 items are **fail -> fail**, not a new failure. The "not a regression" conclusion stands; the reason given for it is wrong.

A related point concerns `058-mission-template-repository-refactor`. At base, the `requirement_refs` of WP08 (`Constitution terminology canon`) were dropped entirely, which left WP08 in `missing_requirement_refs_wps`, and so it was already failing. Only WP10 (`ADR 2026-03-27-1` beside `FR-018`) newly fails.

**Fix:**
- Rewrite the `kept/unknown` paragraph with the correct base semantics, citing the lines above.
- Correct the "missions whose next re-finalize will newly fail" list: it is only 058, via WP10.
- Correct the "felt for the first time by 6 already-existing missions" sentence in Interpretation.

## Issue 2 (medium, blocking): (c) claims an assertion the script does not have

The report says: "a script assertion would have failed loudly had any addition NOT matched the declared-shape grammar". `corpus_scan.py` contains no such assertion. `_compare_declared_growth` only computes set differences. The `(FR|NFR|C|SC)-\d+[a-z]?` breakdown (2,603 / 28 / 6) was evidently an ad hoc post-hoc check.

**Fix:** remove the claim. State that the breakdown was a post-hoc reviewer-side check, and give the exact command. Do NOT add a requirement-ID regex to the script, because C-008 forbids it.

## Issue 3 (low, blocking because it is a number in the evidence): the (b) token count is wrong

The report says `doctrine-enrichment-...-01KQ48XA` has 74 tokens. `corpus-scan.json` holds 71, so the total is 84 refused tokens, not 87.

**Fix:** correct the count, and restate the total if you mention one.

## Non-blocking nits (fix if touching the files anyway)

- **Method commands:**
  - The script path is `research/corpus_scan.py`; it should be `kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py`.
  - The `PYTHONPATH=$(pwd)/src` prefix on the driver is unnecessary, so drop it or explain it.
  - `<tmp>/rig-base` and `/tmp/rig-base` are used inconsistently.
- **`latency_bench.py`:**
  - The docstring says the fixture is modelled on `tests/integration/test_ac5_hash_guard.py`; the prompt named `test_finalize_tasks_validate_only_readonly.py`.
  - The fixture lives under `--out-dir` and is never removed; the prompt asked for a `TemporaryDirectory`.
- **`_wp_transition_entries`:** it discards the head token (`_head_token`) without asserting `base_token == head_token`. I verified it holds today; an assertion would make it self-proving.
- **The driver:** it never asserts `base_src != head_src`. Isolation is proven only by construction, and the recorded relative paths are identical per side.
