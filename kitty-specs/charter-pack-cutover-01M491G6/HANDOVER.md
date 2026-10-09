# Handover: mission `charter-pack-cutover-01M491G6` (#3732) — closeout

You are picking up a governed Spec Kitty mission in `spec-kitty/spec-kitty` at the
closeout stage. Read `.kittify/charter/charter.md` and `CLAUDE.md` first (binding).

## State at handover (2026-10-09)

- All 25 WPs **approved** (independent reviewer per WP; 9 needed one rework cycle).
- **Consolidation is NOT done.** `spec-kitty consolidate --mission charter-pack-cutover-01M491G6 --keep-branch`
  (run 2026-10-09) merged lanes a,b,j,c,d,e,q,f,k,g,h,i,l,m into the mission branch, then **refused lane-r**:
  "Lane lane-r is stale: overlapping files [...] Lane lane-r must incorporate mission changes before merging.
  Run: cd .worktrees/*-lane-r && git merge kitty/mission-charter-pack-cutover-01M491G6". It rolled back
  cleanly (planning branch unchanged at 09b428a3; mission branch restored to 3a68f1c). Full log was in the
  session scratchpad; the overlap list is ~37 files, mostly generated files (pack-manifest, cli-commands.md,
  docs-retrieval-index, completion manifest), rosters (pyproject, ci-nightly, shard roster, coverage baseline),
  `_charter_pack_cutover_skills.py` (WP12/WP14/WP18 all edited it), and tests that WP13/WP14 touched in parallel
  with WP18 (lane-r branched off lane-l before lanes m/n landed).
  **Next step:** in `.worktrees/charter-pack-cutover-01M491G6-lane-r`, `git merge kitty/mission-charter-pack-cutover-01M491G6`;
  resolve conflicts (regenerate generated files with tooling: `spec-kitty charter pack regenerate-graph`,
  `python -m specify_cli.completion --regenerate`, `python -m scripts.docs.build_cli_reference`,
  `python -m scripts.docs.docs_index --write`; for source/test conflicts take the union, using the already-merged
  resolution on lane-y as the reference — lane-y (658a32f) contains every lane merged and its acceptance suite
  is green: 352 passed / 1 skipped / 0 failed / 0 xfailed / 0 xpassed, nfr003 passes with -n0). Expect the same
  "stale" refusal for later lanes (n, o, p, s, ...) — repeat per lane, re-running `spec-kitty consolidate`
  (or `--resume`) after each. Watch the approval-bound gate (LANE_MOVED_AFTER_APPROVAL): merge commits are
  dropped by it, but do NOT add non-merge commits to approved lanes; if a refusal names a lane, follow its
  printed remedy. Never hand-merge lanes into the planning branch.
  Lane branches `kitty/mission-charter-pack-cutover-01M491G6-lane-{a..y}` and the mission branch are on origin.
- Acceptance suite at the combined lane tip (lane-y): 352 passed, 1 skipped, 0 failed, 0 xfailed,
  0 xpassed (`-k "not nfr003"`), nfr003 passes with `-n0` (load-sensitive timing test).
- `spec-kitty accept --diagnose` blocker: **acceptance matrix** (`acceptance-matrix.json`, 19 criteria
  FR-001..FR-019, all `pending` with TODO placeholder descriptions). Nothing else blocked.
- PR #5827 (#5538/#4836) is separate, ready for review — stand down on it.

## What is left (in order)

1. **Finish consolidation (see above), then verify** on `issue-3732-charter-pack-rename`: acceptance suite
   (`uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -n 4 --dist loadfile -k "not nfr003"`,
   then nfr003 with `-n0`), `make test-fast`, `ruff check .`, `ruff format --check .`. The main checkout
   now carries `.kittify/charter-packs` (WP11 migrated this repo), so the LEGACY_CHARTER_STATE local-env
   issue that forced standalone clones should be gone — confirm with any `spec-kitty charter ...` command.
2. **Acceptance matrix**: for each FR-001..FR-019 record a real verdict with
   `spec-kitty agent mission acceptance-verdict --mission charter-pack-cutover-01M491G6 --criterion FR-0NN --result pass --verification-method automated_test --evidence <test node ids> --actor claude`,
   mapping each FR to its tests in `tests/acceptance/charter_pack_cutover/` (tests carry `@covers`/FR ids).
   Then `spec-kitty accept --mission charter-pack-cutover-01M491G6`.
3. **Issue matrix** (`issue-matrix.json` in the mission dir): terminal verdicts for in-mission rows
   #3732 (WP25), #4400 (WP06), #4573 (WP14), #5323 (WP12), #5825 (WP03), #5826 (WP24).
   #4573 and #5825 need `deferred-with-followup` for their out-of-scope halves (open the follow-ups).
4. **Follow-up issues to open** (owner-approved): NFR-002 census residue — owner ruled *ship as is*
   (see `research/posttasks-fold-decisions.md`, "Owner ruling 2026-10-09"): TICKETED_BASELINE 2
   (`override_policy` via `_charter_pack_collect.py`; `hand_authored_overlay` via
   `charter/pack_tooling.py`), ORPHAN_REACHED_EXCEPTIONS 10; plus the `mock.patch.dict(sys.modules)`
   whole-table-restore advisory in the WP01 acceptance helpers. Other small follow-ups noted during the
   mission: slow cascade tests (~100 s each, timeout risk under load); shared YAML writer cannot render
   a mapping emptied of its last key (WP12 works around it with `{}`); edited retired skills in
   `~/.claude/skills` are kept silently.
5. **Mission review** (`spec-kitty-mission-review` skill), then a **pre-PR adversarial squad**
   (`adversarial-squad` skill). Fix findings on the branch.
6. **Draft PR** from `issue-3732-charter-pack-rename` → `main` (use the repo PR template). Body must
   call out: NFR-002 partly met (census residue, follow-up issue); this repo's own active charter
   changed by the migration (removed `activated_mission_step_contracts: []`,
   `activated_glossary_packs: []`, and `activated_paradigms` equal to the released default → six more
   built-in paradigms active); Tests-run section with commands/counts; the CHANGELOG `## Unreleased`
   Before/After (no version bump). Unsigned commits: the spec-kitty CLI's own status/merge commits are
   unsigned; make sure the PR shows no "Unverified" commits (squash/signed merge or re-sign only where
   no one builds on the branch; never force-push someone else's branch).
7. Drive CI green; then mark **ready for review** and post a handoff comment. **Merges are the owner's
   (Stijn) call** — do not merge.
8. After merge: open the public-packs sidecar PR from `research/sidecar-public-packs-pr-draft.md`.

## Rules that bind you (owner directives)

- Do NOT run full `tests/architectural/`, e2e or performance suites locally — targeted tests only; CI
  runs the full suites on the PR.
- No aliases/shims (C-001); edit SOURCE templates only; pack tiers (`packs/internal` never ships).
- Commit often; push the branch frequently (container disk/reclaim risk). Never push to `main`.
- Disk is tight: use `git clone --shared` for scratch clones and delete them.
- `.github/CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — exclude from bulk rewrites.

## Where everything is

- Mission dir: `kitty-specs/charter-pack-cutover-01M491G6/` — `spec.md`, `plan.md`, `tasks.md`,
  `tasks/WP01..WP25*.md` (each with Activity Log + review cycles), `contracts/`, `research/`
  (incl. `posttasks-fold-decisions.md` = every owner/orchestrator ruling), `occurrence_map.yaml`.
- Governing ADR: `docs/adr/4.x/2026-10-06-1-charter-offering-active-charter-and-activation-presets.md`.
- Upgrade runbook: `docs/migrations/charter-pack-cutover.md`.
