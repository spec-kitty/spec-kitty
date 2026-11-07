# Tracer friction classification: method and results

Window: 2026-08-06 to 2026-11-06. Data: `tracer-entries.part{1,2,3}.csv`, which has one row per friction entry. Scripts: `scripts/extract.py` and `scripts/classify.py`.

## Method

- **Files.** 322 tooling-friction tracers, found with:
  `find kitty-specs -type f \( -path '*/traces/*' -o -path '*/tracers/*' -o -path '*/tracer/*' -o -name 'tracer-*.md' \) -iname '*friction*'`
- **Dates.** The clone is shallow, so git dates cannot be used. Each entry is dated by the first `YYYY-MM-DD` in its text, with the Mission's `meta.json` `created_at` as fallback (193 entries).
- **Entries.** Each file is split at bullets, date-led lines and blank lines, then boilerplate and headings are dropped. That leaves 2797 entries, of which 1169 (from 239 files) fall in the window.
- **Classification.** Each entry gets a cause code, a model and a severity from ordered regex rules.
- **Accuracy.** A 50-entry hand check agreed with the lane / not-lane split for about 85-90% of entries. About 6% of entries are noise fragments. Severity is the least reliable column.
- **Not mined.** Approach and design-decision tracers, `retrospective.yaml`, `kitty-ops/` Op records and the field reports.

## Results (1169 entries)

| Cut | Values |
|---|---|
| Cause code | NL 793; CT 177; WL 96; WC 56; HC 36; CG 8; HT 2; SD 1; UF 0; DP 0 |
| NL (not lane-related), by area | tests/CI 238; planning/tasks 193; other 116; review process 109; host/env/install 70; charter/packs 31; gates/arch 27; claim-base gate 7; docs 2 |
| Model | none 793; coord 166; worktree 111; single_branch 58; lane-branch 41 |
| Severity | wasted-time 926; forced-override 195; wrong-verdict 26; data-loss 22 |

- **Lane-related share.** 376 of 1169 entries (32%) relate to lanes, worktrees or coordination. Only 111 (9.5%) need persistent per-lane checkouts.
- **Coordination.** 62 of the 177 CT entries are the `specify` command defaulting to coord on a protected branch, after which the scaffold was cleaned up by hand.
- **Lane worktree setup.** 47 of the 96 WL entries are lane worktrees missing `.venv` or `packs/`.
- **Severity skew.** Lane-related entries are 12 of 22 data-loss entries and 12 of 26 wrong-verdict entries. The counts are small and come from keyword rules.
- **Trend.** The lane-related share was 38% in Aug, 33% in Sep, 32% in Oct and 26% in Nov.
- **Subject bias.** 112 of the 376 lane-related entries come from 42 Missions whose own subject is lanes, coord or consolidation. Across the other Missions the share is 28.5%.
- **Coverage bias.** The 2026-09-26 tracer recon (`docs/reports/tracer-friction-recon/2026-09-26/README.md`) found that 25 of 70 Missions never appended beyond their seed entry.

## Telling entries

- `kitty-specs/pack-shipped-builtin-override-sanction-01M45WB7/traces/tooling-friction.md:10`: a lane worktree imports the root checkout's `src/` through the shared editable venv.
- `kitty-specs/coord-artifact-single-home-01M3V4BE/traces/tooling-friction.md:57`: `refs/stash` is shared across worktrees, and a parallel agent's stash hit WP07 twice.
- `kitty-specs/local-event-log-retention-01M5ZCJP/traces/tooling-friction.md:13`: review feedback was lost through the coord-to-lane auto-merge during consolidation.
- `kitty-specs/meta-driver-base-aware-01M490FF/traces/tooling-friction.md:7`: the Mission defaulted to coord, and the worktree and branch were removed by hand.
- `kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/traces/tooling-friction.md:7`: a lane worktree has no `packs/` tree, so the run failed with `BuiltInPackMissing`.
- `kitty-specs/upgrade-project-global-state-01M44538/traces/tooling-friction.md:11`: a commit in the root checkout racing a subagent swept staged status events into an unrelated commit.

The classified rows are split into parts so each file stays under the 256 KiB Mission artifact cap that the corpus check enforces (`tests/contract/test_mission_status_reality.py`, `_CONTENT_CAP`). Each part carries the header row; concatenate them to rebuild the table.
