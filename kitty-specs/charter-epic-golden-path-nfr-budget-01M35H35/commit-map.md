# Pre-rebuild commit references

This mission's branch was rebuilt before its first push. The original local branch
carried a fixed-at-tip local absolute filesystem path (present in six earlier
commits' history) and several tool-generated commit messages that this repository's
commitlint configuration rejects (`type-enum`/`type-empty`). Rather than rewrite
that history with `git rebase`, the branch was rebuilt from scratch: a fresh branch
was cut from `origin/main`, and this mission's changes (the diff between the old
branch's merge-base and its tip) were re-applied as a small number of clean,
Conventional-Commits-conforming commits.

As a result, every SHA the review trail (`reviews/*.yaml`, `tracer-*.md`,
`analysis-report.md`, etc.) cites from the old branch now dangles — it exists only
in local history and was never pushed. This file maps each SHA referenced from the
review trail to what actually carries that change now.

## How to read the table

- **New commit** — the commit on this rebuilt branch that carries the same content.
- **"bookkeeping, folded"** — a pipeline status/administrative commit (a `status.json`
  / `status.events.jsonl` transition record) with no independent code or doc content;
  its net effect is captured inside the mission-artifact commit below.
- **"rebuilt; content superseded"** — one of the six commits whose history carried the
  local path leak. Its file content is superseded by the corresponding file in this
  rebuilt branch; nothing from the leaked history is present in the new object graph.

## Commits still valid on `origin/main`

These SHAs were already on `origin/main` before this mission started and are cited
correctly as-is; no mapping needed.

| SHA | Subject |
|---|---|
| `6b4164dbf` (`6b4164dbfa96549d2833b3f9e4b374b2da72b212`) | fix(#4917): compose specializes_from lineage in the dispatch-capsule profile funnel — this mission's merge-base |
| `177e062694b4` | test: assertively sanitize low-signal suite cruft (#3285) |

## Commits from the old local mission branch (now dangling)

| Old SHA | One-line subject | Maps to |
|---|---|---|
| `bd3d62922` | Add scaffold for feature charter-epic-golden-path-nfr-budget-01M35H35 | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `7024671b7` | docs(spec): apply operator rulings and record spec review trail | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `641a3f694` | docs(plan): fix confirmed plan-review findings (8/9; GOV-001 pending operator decision) | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `f59453e09` | Add tasks for feature charter-epic-golden-path-nfr-budget-01M35H35 | **rebuilt; content superseded** — `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `5daf1c9ae` | docs(record-analysis): record analysis report for mission charter-epic-golden-path-nfr-budget-01M35H35 | **rebuilt; content superseded** — `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `d654f114c` | docs(tasks): fix confirmed tasks-review findings | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `af7b6886c` | docs(baseline): capture WP01 pre-change baseline at merge-base 6b4164dbf | **rebuilt; content superseded** — `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `5a8391d54` | docs(baseline): redact local path and disclose PWHEADLESS prefix (WP01 review cycle 1) | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `1d3b7e723` | chore(spec-kitty): status transition batch WP01 | bookkeeping, folded |
| `26d56981c` | chore(spec-kitty): status transition WP01 | bookkeeping, folded |
| `4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2` | chore(spec-kitty): record WP01 for_review annotation note | bookkeeping, folded |
| `ddd292d19` | chore(spec-kitty): status transition batch WP01 | bookkeeping, folded |
| `a21dc32db` | chore(spec-kitty): status transition WP08 | bookkeeping, folded |
| `30c6ea685` | fix(agent-commands): isolate cli_version freshness check and close review-cycle-1 gaps | `perf(runtime): skip redundant global agent-command renders with a freshness stamp (#4211)` |
| `cf3dcca54` | feat(agent-commands): add freshness pre-check to skip redundant global command renders | `perf(runtime): skip redundant global agent-command renders with a freshness stamp (#4211)` |
| `fc9767c93` | fix(agent-commands): promote AssetPreparation.overwrite_internal as the public overwrite primitive (PR-BOUNDARY-001) | `perf(runtime): skip redundant global agent-command renders with a freshness stamp (#4211)` |
| `c186f4cbc` | feat(WP05): lazy command-lookup table in register_commands() | `perf(cli): register only the invoked command in register_commands() (#4211)` |
| `a2bcad3d0` | fix(cli): derive root boolean-flag tokens from the real callback in _resolve_single_leaf_command (PR-CONTRACT-001) | `perf(cli): register only the invoked command in register_commands() (#4211)` |
| `d393cba28` | test(cli): make PR-CONTRACT-001 fallback tests collide with a real command name | `perf(cli): register only the invoked command in register_commands() (#4211)` |
| `748b9770c` | test(cli): relocate lazy-command-import behavioral tests into a CI-selected directory (PR-TESTS-001) | `perf(cli): register only the invoked command in register_commands() (#4211)` |
| `9791b3923` | test(WP02): un-skip test_charter_epic_golden_path per FR-001/C-004 | `test(e2e): un-skip charter-epic golden path under its 120s budget (#4213)` |
| `3bf8af0f1` | docs(review): record round-1 verify and fresh-sweep trail for pre-merge squad | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `461f13eff` | Add tasks for feature charter-epic-golden-path-nfr-budget-01M35H35 (WP re-plan) | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `c2be30e94` | docs(WP08): redact local path from tracer close-out (review cycle 1) | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `e196a39ba` | docs(WP08): final integration validation, T026-T029 tracer close-out | **rebuilt; content superseded** — `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `e7e5ef086ccf95f91307760fc4de432639db5d79` | docs(tasks): record lane-cycle finding and PR-shape assessment in tracer-design-decisions | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |
| `fdb4e5a4d` | docs(tasks): fix round-2 fresh-sweep documentation drift | `docs(mission): add charter-epic-golden-path-nfr-budget spec, plan, tasks and review trail (#4213)` |

## Non-commit hex strings in the review trail

`grep -rhoE '\b[0-9a-f]{9,40}\b'` over the mission directory also matches strings that
look like SHAs but are not commit ids. Listed for completeness; no mapping needed.

| Value | What it actually is |
|---|---|
| `1790133864`, `1790134942`, `1790134959`, `1790135199`, `1790162821`, `1790162864`, `1790164127`, `1790165953`, `1790172859`, `1790174250`, `1790175064`, `1790177549` | Unix epoch timestamps recorded in evidence/tooling-friction notes |
| `35853033595`, `35872503133` | GitHub Actions run IDs (evidence runs cited in the PR body) |
| `b31664abfee4` | Fragment of a UUID (`project_uuid`) recorded in `status.events.jsonl`, not a commit |
| `107155051340` | A recorded numeric measurement/id in the review trail, not a commit |

## The six leaked-path commits

Of the six commits that carried the local absolute path (fixed at the tip but
present in history): `f59453e09`, `5daf1c9ae`, `74e03a156`, `7a653a206`, `af7b6886c`,
`e196a39ba`.

- `f59453e09`, `5daf1c9ae`, `af7b6886c`, `e196a39ba` are cited by SHA in the review
  trail — each is marked **rebuilt; content superseded** in the table above.
- `7a653a206` is also cited by SHA in `analysis-report.md` — **rebuilt; content
  superseded**, folded into `docs(mission): add charter-epic-golden-path-nfr-budget
  spec, plan, tasks and review trail (#4213)`.
- `74e03a156` is not cited anywhere in the mission review trail.
