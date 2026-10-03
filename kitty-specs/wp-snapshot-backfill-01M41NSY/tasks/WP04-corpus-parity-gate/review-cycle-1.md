---
affected_files: []
cycle_number: 1
mission_slug: wp-snapshot-backfill-01M41NSY
reproduction_command:
reviewed_at: '2026-10-03T22:21:49Z'
reviewer_agent: reviewer-rachel
wp_id: WP04
---

# WP04 review — REJECT (rework), reviewer-rachel

Mission `wp-snapshot-backfill-01M41NSY` (#5579), commits `bcaa82460d` + `cd750d0b07`.

## Blocking

**Issue (F1): the gate is not selected by the CI lane its own regression class routes to.**
`tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py:39` sets
`pytestmark = [pytest.mark.integration]` only. The gate reads `kitty-specs/*/tasks/WP*.md`,
and `kitty-specs/**/tasks/**` is a live corpus trigger glob (router `corpus` filter group).
`pytest.ini:86` is explicit: *"New corpus-reading tests MUST carry this marker"*, and
`tests/architectural/test_ci_corpus_trigger_completeness.py:15-20` states the consequence —
an unmarked corpus reader "is neither run by the corpus lane NOR caught by that exit-5 floor —
it just silently never re-runs on a corpus-only change." The regression this gate exists to
catch (a `tasks/WP*.md` added or removed without seed events) **is** a corpus-only change.
The registry-driven marker guard structurally cannot flag a brand-new module, so it passes
(22 passed) while the hole stands. Under Standing Order #5 a gate that does not run when its
defect arrives is not a non-vacuous gate.

Fix: add `pytest.mark.corpus` to the module's `pytestmark`, and add the module to the corpus
reader registry in `test_ci_corpus_trigger_completeness.py` if that registry is the enforced
inventory.

## Should fold before re-review

**Issue (F2): two of seven bucket-C exemption reasons are factually wrong.**
`_NO_TASKS_DIR_REASON` (line 56) asserts "no `tasks/` dir was ever committed for this Mission"
and is applied to `035-frontmatter-history-to-canonical-jsonl` (line 68) and
`037-mission-dsl-foundation` (line 75). Both Missions DO have a committed `tasks/` directory:
`git ls-files` shows `kitty-specs/035-.../tasks/.gitkeep` and
`kitty-specs/037-.../tasks/.gitkeep` tracked. Only `036-kittify-runtime-centralization`
genuinely has no `tasks/` dir. The substance (no WP file exists, so `snapshot_only` is
unrepairable) is correct; the stated reason is not. A priced exemption under Standing Order #5
is only as good as its reason — reword to "tasks/ holds only .gitkeep; no WP file was ever
committed". The same wording error is in the WP03 handoff, so fix it there too.

Knock-on: `test_corpus_census_is_non_vacuous` (line 260) computes `no_tasks_dir` from
`not (…/tasks).is_dir()`, so that sub-assertion covers only 036, not the three Missions the
docstring implies.

**Issue (F3): the justification for the second WP-id reader is empirically refuted.**
`read_work_package_id` (lines 118-128) duplicates the authority of the repair's
`collect_wp_file_ids` (`src/specify_cli/migration/wp_status_backfill.py:108-130`, canonical
`read_authored_wp_frontmatter`). The docstring at lines 121-124 justifies the split with
"~9 ms per file and ~3,200 WP files would blow the 15 s corpus budget (NFR-001)". Measured in
this worktree: **1.87 ms/file, 5.97 s for all 3189 WP files** — roughly 4x cheaper than
claimed. The canonical path therefore fits NFR-001 with 2x headroom (current 1.51 s + ~6 s
≈ 7.5 s < 15 s).

Agreement today is total, so this is a drift/accuracy finding rather than a correctness
defect: a reader-by-reader comparison over all **3189** WP files in the corpus found
**0 disagreements**; the canonical reader never raised and never returned a null id; and the
regex's accepted shape `WP\d{2,}` is identical to the `WPMetadata.validate_wp_id` pattern
`^WP\d{2,}$`.

Pick one:
- Preferred (Standing Order #6, "chase unification, not parity"): call
  `read_authored_wp_frontmatter` and mirror the repair's malformed-handling, deleting the
  second authority.
- Or keep the regex as a declared test-only fast path, **correct the false cost claim**, and
  add a cross-check test that pins `read_work_package_id == read_authored_wp_frontmatter`
  over a sample of real corpus WP files, so canonical schema drift cannot silently decouple
  the gate from the repair.

## Verified passing (no action)

- Set-based comparison in both directions (`files_only` / `snapshot_only`), per FR-009.
- `files_only` is never exemptable — proven at line 288 against a deliberately sneaky
  exemption naming the injected id.
- Exactly 7 bucket-C exemptions; the 023 reason (WP07 deleted in `c2b10ce05d`) checks out
  against `git log --diff-filter=D`.
- Stale-exemption control covers absent Mission, now-agreeing Mission, over-wide set, and
  empty reason.
- Positive census: floor 400, 532 Missions live.
- Self-mutation controls are non-vacuous — both assert the *unmutated* copy agrees first,
  then that the injected/deleted WP file is reported in the right direction.
- Red-first evidence reproduced independently: a detached worktree at `1270000bdc^` with the
  gate file copied in gives `1 failed, 8 passed in 1.49s` and 45 Missions reporting
  `files_only`, matching the commit message exactly.
- Runtime 1.51 s, well inside NFR-001's 15 s.
- T016 ledger: the 42 added `_OPERATOR_SANCTIONED_CORRECTIONS` entries are byte-identical to
  `git diff --diff-filter=M --name-only 1270000bdc^ 1270000bdc` (24 `status.events.jsonl` +
  18 `status.json`), with a correctly dated comment block naming the operator, Decision
  Moment, mission and issue, plus a removal follow-up.
- `materialize_snapshot` is used throughout; `materialize` is never called on a real Mission.
- ruff check, `ruff format --check --force-exclude`, and mypy are all clean on both files.

## Commands run

```
PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py -q
  -> 9 passed in 1.51s
PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/architectural/test_archive_root_byte_identical.py tests/specify_cli/migration/ -q
  -> 1 failed, 314 passed, 1 skipped in 28.76s
     (sole failure: test_dogfood_corpus_backfilled::test_all_eligible_missions_snapshot_non_empty_and_verify_ok,
      "eligible missions not cut over: ['wp-snapshot-backfill-01M41NSY']" — the known
      status_phase gap fixed on the issue branch, not in lane-c; untouched by WP04's two files)
PYTHONPATH=$PWD/src .venv/bin/python -m pytest tests/architectural/test_ci_corpus_trigger_completeness.py -q
  -> 22 passed in 1.61s  (passes despite F1; the registry cannot see a new module)
pytest on a detached worktree of 1270000bdc^ with the gate copied in
  -> 1 failed, 8 passed in 1.49s; 45 Missions files_only  (red-first)
ruff check / ruff format --check --force-exclude / mypy on both owned files
  -> All checks passed / 2 files already formatted / Success: no issues found in 2 source files
reader comparison script over kitty-specs/*/tasks/WP*.md (canonical reader from lane-b)
  -> 3189 files, AGREE 3189, DISAGREE 0; canonical 5.97s total, 1.87 ms/file
```
