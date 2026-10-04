# Design decisions — wp-snapshot-backfill

- 2026-10-03 (operator): base on `main`, independent of PR #5581; #5581 sets its ceiling to 0 when it lands.
- 2026-10-03 (operator): finished Missions are seeded `planned` then forced to `done`, so progress stays truthful; "finished" means `meta.json` `accepted_at`/`merged_at` or an explicit evidence-manifest entry.
- 2026-10-03: frozen-root modifications are ledgered as operator-sanctioned corrections (precedent #5258) instead of carving out the gate.
- 2026-10-03: snapshot-only WPs (no file) are recorded as reasoned exemptions; files are never invented.

2026-10-03 · implementer-ivan · 2026-10-03 (WP02): (1) Manifest is strict — unknown top-level/entry keys, blank reason, non-string slug, and slugs that are not exact kitty-specs directory names are all refused (exit 1, nothing written), validated BEFORE any write and even when --mission scopes elsewhere. (2) Unused-manifest-entry warning (WP01 reviewer note) classifies 'nothing to seed' (already seeded planned; late evidence is a silent no-op) vs 'not in scope' (--mission names another Mission); surfaced in human WARNING lines and JSON manifest.unused. (3) A no-project failure under --json stays parseable JSON ({success:false,error_code:NO_PROJECT_ROOT}) so the command is PARSEABLE in the JSON-contract inventory, not DEFERRED #4664 debt. (4) Dry-run still takes the empty, git-ignored per-mission status lock file (.kittify/spec-kitty-locks/*.status.lock); tests compare kitty-specs/ bytes only.

## WP03 corpus drain (commit 1270000bdc)

- Evidence rule (28 manifest entries): dossier reached `main` of the upstream repository through a merged PR (found via `GET /commits/<sha>/pulls`, or issue/PR search for direct-commit dossiers), the PR shows the work was delivered, and no existing WP is in an active lane. 13 more finished Missions came from `meta.json` `merged_at`/`accepted_at`.
- Left planned (3): `062-fix-doctrine-migration-test-failures` (WPs still claimed/in_progress), `blocked-wp-unblock-path-01M29093` (WP02 descoped before merge, PR #4245), `sync-sleep-count-3136-01KZ9B5A` (PR #3252 rescoped; WP02/WP04 not delivered as planned). Per-WP descope cannot be expressed in a Mission-level manifest, so a forced `done` would have recorded a falsehood.
- Run: 417 events seeded across 44 Missions; second dry-run seeds 0. Event logs only grew (append-only); `status.json` regenerated only where it already existed.
- Modified pre-existing frozen files (WP04 sanctioned-corrections ledger) and the bucket-C list with reasons: see the handoff table below (copied verbatim from the WP03 hand-off).

Sanctioned-corrections ledger: every MODIFIED pre-existing frozen file under `kitty-specs/` (git status `M`):

- kitty-specs/005-refactor-mission-system/status.events.jsonl
- kitty-specs/005-refactor-mission-system/status.json
- kitty-specs/055-agent-skills-pack/status.events.jsonl
- kitty-specs/055-agent-skills-pack/status.json
- kitty-specs/057-doctrine-stack-init-and-profile-integration/status.events.jsonl
- kitty-specs/057-doctrine-stack-init-and-profile-integration/status.json
- kitty-specs/062-fix-doctrine-migration-test-failures/status.events.jsonl
- kitty-specs/062-fix-doctrine-migration-test-failures/status.json
- kitty-specs/asset-preservation-migrate-fetch-01M3E857/status.events.jsonl
- kitty-specs/asset-preservation-migrate-fetch-01M3E857/status.json
- kitty-specs/ci-main-concurrency-fanout-cap-01M2K46V/status.events.jsonl
- kitty-specs/ci-scoping-gate-reliability-01KZP80D/status.events.jsonl
- kitty-specs/ci-scoping-gate-reliability-01KZP80D/status.json
- kitty-specs/cli-error-surface-seam-01M2WJD2/status.events.jsonl
- kitty-specs/cli-error-surface-seam-01M2WJD2/status.json
- kitty-specs/decide-out-of-matrix-test-dirs-01M2TKC7/status.events.jsonl
- kitty-specs/decide-out-of-matrix-test-dirs-01M2TKC7/status.json
- kitty-specs/drg-reachability-metric-wiring-01KZS5VR/status.events.jsonl
- kitty-specs/drg-reachability-metric-wiring-01KZS5VR/status.json
- kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/status.events.jsonl
- kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/status.json
- kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/status.events.jsonl
- kitty-specs/git-tip-helper-consolidation-01M3D4RT/status.events.jsonl
- kitty-specs/glossary-modeling-delta-01M1GXV9/status.events.jsonl
- kitty-specs/next-committed-state-authority-01M1CA8W/status.events.jsonl
- kitty-specs/next-committed-state-authority-01M1CA8W/status.json
- kitty-specs/post-convergence-governance-01M1TMPH/status.events.jsonl
- kitty-specs/resume-primary-staged-deletion-integrity-01M3CCH9/status.events.jsonl
- kitty-specs/sync-sleep-count-3136-01KZ9B5A/status.events.jsonl
- kitty-specs/sync-sleep-count-3136-01KZ9B5A/status.json
- kitty-specs/team-kitty-launch-defaults-01M1XJ4Y/status.events.jsonl
- kitty-specs/team-kitty-launch-defaults-01M1XJ4Y/status.json
- kitty-specs/terminus-integrity-followups-01M393QR/status.events.jsonl
- kitty-specs/terminus-integrity-followups-01M393QR/status.json
- kitty-specs/terminus-merge-integrity-01M380R6/status.events.jsonl
- kitty-specs/terminus-merge-integrity-01M380R6/status.json
- kitty-specs/terminus-safety-invariant-01M2XFT7/status.events.jsonl
- kitty-specs/terminus-safety-invariant-01M2XFT7/status.json
- kitty-specs/up-mission-type-seam-01KZY1JB/status.events.jsonl
- kitty-specs/up-mission-type-seam-01KZY1JB/status.json
- kitty-specs/up-org-doctrine-consumers-01M05YAB/status.events.jsonl
- kitty-specs/up-org-doctrine-consumers-01M05YAB/status.json

Added files (status `A`, no ledger entry): 20 new `status.events.jsonl` (the bucket-A Missions) plus `kitty-specs/wp-snapshot-backfill-01M41NSY/evidence-manifest.yaml`.

## Bucket C (snapshot-only WPs; exemption entries for the FR-009 gate)

| Mission | Snapshot-only WP ids | Why the file is absent |
|---|---|---|
| 023-documentation-sprint-agent-management-cleanup | WP07 | `tasks/WP07-jujutsu-reference-cleanup.md` deleted in c2b10ce05d (2026-03-20, "Remove Jujutsu (jj) VCS implementation entirely", #314) |
| 035-frontmatter-history-to-canonical-jsonl | WP01-WP06 | spec-only dossier (4a6c947691); `tasks/` never committed, tasks.md names WPs |
| 036-kittify-runtime-centralization | WP01-WP08 | no `tasks/` dir in the dossier; tasks.md names WPs (not counted as snapshot_only by the CLI because there are no WP files at all) |
| 037-mission-dsl-foundation | WP01-WP09 | spec-only dossier (c725036d21); `tasks/` never committed |
| journal-project-consent-3030-01KYKWQS | WP03 | WP03 file never committed to main (no git history on the path; tasks/ has WP01,02,04-12) |
| single-planning-surface-authority-01KVPR00 | WP08, WP09, WP10 | WP files never committed to main (tasks/ stops at WP07; tasks.md has no WP08-10) |
| synthesized-drg-stale-refresh-01KXN8KZ | WP05 | WP05 file never committed to main (tasks/ has WP01-WP04) |

Note: the repair CLI reports 6 snapshot-only Missions; 036 is the 7th (spec FR-009 says 7) and has no WP files, so a gate must handle it explicitly.
# Design decisions — wp-snapshot-backfill

- 2026-10-03 (operator): base on `main`, independent of PR #5581; #5581 sets its ceiling to 0 when it lands.
- 2026-10-03 (operator): finished Missions are seeded `planned` then forced to `done`, so progress stays truthful; "finished" means `meta.json` `accepted_at`/`merged_at` or an explicit evidence-manifest entry.
- 2026-10-03: frozen-root modifications are ledgered as operator-sanctioned corrections (precedent #5258) instead of carving out the gate.
- 2026-10-03: snapshot-only WPs (no file) are recorded as reasoned exemptions; files are never invented.
- 2026-10-03 (WP01): seed `at` is `meta.json` `created_at` (UTC-normalised), else the fixed Unix epoch; the forced `done` lands `planned.at + 1s` so `(at, event_id)` order is planned-then-done. Ids are `deterministic_ulid(mission_id-or-slug|wp|to_lane|wp-status-backfill)`; actor is `migration:backfill_wp_status`. `evidence` is a `{slug: reason}` manifest mapping; `meta.json` `merged_at` beats `accepted_at` beats the manifest.
- 2026-10-03 (WP01): `apply_wp_status_backfill` and friends have no `src/` caller until WP02 wires the CLI, so `tests/architectural/test_no_dead_symbols.py` is transiently red for exactly those three names. No allowlist entry was added (charter SO #5); WP02 must turn it green.
- 2026-10-04 (pre-PR review folds 1-2): the backfill REFUSES (no plan, no write; skip_reason `COORD_SURFACE_LIVE`, counted as skipped, exit 0) a Mission whose coordination surface is live, because the PRIMARY-partition log is not that Mission's status authority; it only degrades to PRIMARY when the coordination branch is gone. Liveness comes from the canonical `resolve_status_surface_with_anchor`, not a re-derivation. The parity gate SKIPS such Missions and lists them in its diagnostic instead of exempting them. Resolved (fold 11): the liveness rule is "the resolved surface differs from the Mission directory AND its log exists or the declared coordination branch is a local ref"; the resolver returns the would-be coordination path even when no worktree and no branch exist, which had misclassified 5 of the 6 Missions the drain seeded (decide-out-of-matrix-test-dirs, drg-reachability-metric-wiring, terminus-safety-invariant, pack-metadata-manifest-unification, partition-authority-residuals) as live. Those were false positives and their seeds stand. The sixth, upgrade-idempotent-worktree-metadata-01M38X2Y, is genuinely live locally (stale residue); its `meta.json` `accepted_at` 2026-09-24 matches the committed seeded `done`, so its seeds are kept. A read-only probe over the 47 coordination-declaring Missions reports only that one as live.
