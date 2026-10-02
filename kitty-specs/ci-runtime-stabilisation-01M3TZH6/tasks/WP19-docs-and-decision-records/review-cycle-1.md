---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T16:37:49Z'
reviewer_agent: claude-reviewer
wp_id: WP19
---

# WP19 review feedback (cycle 1) — reviewer-renata

Verdict: changes requested. The work is close. Red-first, append-only, docs gates, the T082 evidence and most facts are correct. Two statements in the ADR amendments do not match the shipped code. An ADR amendment is append-only once accepted, so fix them now, before the text is frozen. Do not edit any accepted text above the amendment headings.

## Blocking

1. **`docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md:115`: "uploads a zero-content artifact" is false for the shipped code.**
   - **Problem.** `scripts/ci/green_match.py::_marker_body` (lines 489-499) writes a JSON body: `pr`, `head`, `base`, `merge_sha`, `workflow`, `run_id`, `run_attempt` and `decision`. The router, CI Modules and Packs upload steps publish that file by name (`ci-router.yml:299-308`, `ci-modules.yml:353-362`, `packs.yml:~165-172`). The phrase comes from `contracts/green-match.md:9`, but WP17's implementation diverged from the contract, and the brief says the merged behaviour wins.
   - **Required fix.** Describe the marker as it ships: a small JSON body that records the run's own tested key and decision. Then make the Trust-surface bullet at line 148 consistent with it. `decide` matches on the artifact **name** plus run metadata and never reads the body, and the body is self-reported, so it does not prove what the run executed. For example: "The artifact's JSON body is self-reported and `decide` does not read it."

2. **`docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md:144-146`: the contrast between the fast job and the heavy legs is misleading.**
   - **Problem.** The text reads "The new `architectural-fast` job is part of the router gate's `needs`; the heavy legs are not required contexts." That implies the heavy legs differ from the fast job in gating. In `ci-router.yml:838-858`, `router-gate.needs` lists both `architectural-fast` and `architectural-heavy`, so a red in either one reds the required `router gate`. Neither job is itself a required context. The amendment's own sibling doc states this correctly (`ci-gate-mechanics.md`, the heavy job "whose failure reds the router gate").
   - **Required fix.** Say that both the fast job and the heavy legs are in `router-gate`'s `needs`, so a red in either reds `router gate`, and that none of them is a required context (C-004 and ADR 2026-09-23-1: never require a path-scoped job).

## Non-blocking (fix while you are in the file if cheap)

3. `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md:121-123`: "The fast roster, the shard count, the worker count and the base selection live in one place, `.github/ci-module-registry.yml`." The workflows also carry literal copies (`-n 4`, the base marker and the deselects in `ci-router.yml` and `ci-nightly.yml`), and guards keep them equal to the registry (`tests/ci/test_xdist_worker_policy.py`, the partition proof). Consider "are held in the registry, and the workflow literals are guarded against it."
4. `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md` §Consequences: "Main's nightly was already red when this landed" is written before the mission lands. Consider "is red at the time of this amendment".
5. `docs/development/reference/ci-gate-mechanics.md`, §Skip-if-green: the "Symptom of a surprise skip" bullet is one unwrapped long line. The rest of the page wraps near 80 columns.

## Verified OK (no action)

- Red-first: `cb107cdaf5` adds only the test. It fails 4/4 on the pre-amendment ADRs and passes 4/4 on the tip.
- Mutations go red: amendment heading undated (A or B), a broken contract link (A or B), an interloper H2 that moves the link out of the slice, and the 18.6% figure removed.
- The ADR diffs are append-only, plus the `updated:` line. Both descriptions are unchanged.
- Facts confirmed against the code:
  - backstop: job name and display name, 40-minute timeout, Python 3.12, `-n 4` with no `-q`, base marker and four deselects, no partition plugin, listed in `nightly-summary.needs`, escalation key `architectural`, triage fields (#5106, Bug, `from:ci`, milestone);
  - roster: registry-held under `special_tiers.architectural` (34 entries, `workers: 4`, `shard_count: 2`);
  - battery legs: `include:` with `1/2` and `2/2`;
  - `ci_config` paths, including `.github/actions/**`;
  - `tests (corpus-blocking)` (job key `tests-corpus-blocking`): 40 node-ids (34+5+1); Packs deselects them; Packs job name;
  - the removed router `tests (cli|status|consolidation|corpus)` jobs;
  - green-match: tested key, parent binding, attempt-1-only, never-suppressed cases, the lookup-error `::warning::`, and Aggregate `effective-source` with "re-run CI Modules to execute";
  - `module-tests (cli shard 1/2)`;
  - the Makefile still uses `-n auto`.
- Gates:
  - docs index: `drift=False`;
  - freshness: errors=0;
  - spelling: 0 findings;
  - description length: 0 violations;
  - pinning `--check`: exit 0;
  - targeted pytest: 161 passed;
  - ruff, format and mypy --strict on the test file: clean.
- T082 holds:
  - #4351: 52 node-ids in the `unit` row;
  - #4729: `1e290b09ae` is an ancestor of the tip; `integration-next` is at line 912, its command at 938, and it is in `nightly-summary.needs` at 1201.
