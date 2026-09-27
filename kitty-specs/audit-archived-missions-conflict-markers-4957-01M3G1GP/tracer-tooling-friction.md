# Tracer: Tooling Friction

Mission: `audit-archived-missions-conflict-markers-4957-01M3G1GP` (#4957)

Per Charter Standing Order #3, seeded at plan phase, appended during implementation, assessed
at close.

## Plan-phase entries

1. **`StartupAssetError` transient (spec phase, not reproduced this phase).** During the spec
   phase, both `spec-kitty agent mission create` (scaffolding this mission) and, independently,
   `spec-kitty safe-commit --help` first failed with:
   ```
   Error: slash_commands: Global asset input changed: <cache-path>; re-run the command
   ```
   against a stale global asset-freshness lock cache (`agent-commands-freshness.lock`), then
   succeeded cleanly on an immediate, identical retry — three occurrences total during the spec
   phase, one retry resolved it every time observed. **This phase (plan):** `spec-kitty agent
   mission setup-plan --mission audit-archived-missions-conflict-markers-4957-01M3G1GP --json`
   succeeded on the **first** invocation — no `StartupAssetError` was hit during plan
   scaffolding. Recorded as a non-reproduction, not evidence the underlying cache-staleness
   class is fixed (it is intermittent by nature).

2. **CLI ULID-suffix behavior on the requested mission slug (observation, not a defect).** The
   mission was scaffolded from a short requested slug
   (`audit-archived-missions-conflict-markers`), and the CLI appended a ULID-derived `mid8`
   suffix (`-4957-01M3G1GP`, where `01M3G1GP` is `meta.json`'s `mid8` field, itself the first 8
   characters of the full `mission_id` ULID `01M3G1GPR5K5J3Z57ZQC45Z93V`) to produce the actual
   `mission_slug`. This is expected, documented CLI behavior per `CLAUDE.md`'s Mission Identity
   Model section (083+): `mission_id` is the canonical, immutable identity; `mission_slug` is a
   human handle; the ULID suffix disambiguates collisions on the human-chosen short name. Not a
   tooling defect — noted here purely as an observed friction point for anyone expecting the
   requested slug verbatim.

3. **SK-248/SK-276 re-verification result (plan phase): byte-identical scaffold confirmed, no
   discrepancy found.** Per the plan-phase hazard note, `diff
   .kittify/overrides/missions/software-dev/templates/plan-template.md
   packs/built-in/missions/software-dev/templates/plan-template.md` was re-run fresh this phase
   (not reused from the orchestrator's earlier pre-scaffold diff) — output was empty
   (byte-identical). The scaffolded `plan.md` was then independently inspected and confirmed to
   carry the canonical `## Charter Check` section heading (not a retired `## Constitution
   Check`), plus the canonical `## Implementation Concern Map` / `## Complexity Tracking`
   sections in the expected order. No SK-248 or SK-276 recurrence on this checkout at this
   commit. This is a **non-finding** worth recording precisely because both prior ledger
   entries describe this exact repo having previously shipped a stale override — a clean result
   here is informative, not merely "nothing to report."

4. **`make ci-parity` on a spec-only diff previews an incomplete gate set for this mission's
   real (future) diff — expected, not a defect.** Running `make ci-parity` this phase (before
   any implementation change) reported 12 selected jobs and 0 selected code shards, computed
   against the current diff (spec.md + review artifacts + meta.json — no `tests/` or
   `kitty-specs/025-.../tasks/` paths yet). This is the correct, honest output for *that* diff;
   it is not a preview of what the mission's *eventual* implementation diff will select. The
   plan (Section C) reasons statically from `ci-router.yml` / `ci-module-registry.yml`'s
   literal path filters for the two files this mission will actually touch, cross-checked
   against this `ci-parity` run's baseline gate list (ruff, uv-lock, import-linter, regen-check,
   terminology, layer-rules, archive-freeze, router-gate, markdownlint, commit-msg all already
   appear for the spec-only diff and are expected to persist unchanged once the two
   implementation-phase files are added; `tests-corpus` is newly triggered once the WP01 path is
   touched, per the `kitty-specs/**/tasks/**` filter).

5. **`PlanStarted`/`PlanCompleted` asymmetry on this mission's own event log — SK-279
   verified first-hand, non-blocking.** This mission's own `status.events.jsonl` carries a
   `PlanStarted` event (emitted by `spec-kitty agent mission setup-plan`) with no matching
   `PlanCompleted` event, even though `plan.md` is fully authored, R-reviewable, and now
   committed at `HEAD` (`2c7132a03`, "plan(4957): author implementation plan and seed mission
   tracer files for archived-conflict-marker audit"). This is the exact symptom the tracker
   ledger's SK-279 entry describes: `setup-plan` emits `PlanCompleted` only if `plan.md` is
   already substantive at invocation time, so the scaffold-then-author flow (scaffold first,
   author the content afterward — this mission's own flow) never records plan completion.
   Independently confirmed here, not inferred from the ledger text. Per SK-279's own noted
   precedent this is non-blocking: downstream `finalize-tasks`/`record-analysis` do not refuse
   on the missing event, so it does not gate this mission's progress — recorded here as a
   verified-first-hand recurrence so the close-phase assessment does not have to rediscover it
   from scratch.

6. **`StartupAssetError` transient recurred once more, at the very end of the plan phase.**
   The orchestrator's own `spec-kitty safe-commit` invocation to commit the whole plan-phase
   `reviews/` trail (11 files, PASSED) failed on the first attempt with:
   ```
   Error: slash_commands: Global asset input changed: /home/<user>/.agent/workflows/spec-kitty.analyze.md; re-run the command; if it persists, run `spec-kitty doctor --help` to find the right diagnostic
   ```
   against the same stale global asset-freshness lock cache class as the spec-phase
   occurrences (item 1 above), this time naming `spec-kitty.analyze.md` rather than the
   `agent-commands-freshness.lock`/slash-commands cache named earlier — same failure family,
   different cache entry. An immediate, identical retry succeeded cleanly and committed the
   trail. Fourth occurrence of this transient across the mission so far (3 in spec phase, 1 in
   plan phase), one retry resolving it every time observed — still consistent with "reproducible
   but not a spec-level or plan-level defect," per item 1's original framing.

## Implementation-phase entries

7. **`StartupAssetError` transient recurred twice during WP01's implementation
   phase — same failure family as items 1 and 6, still one-retry-resolves.**
   `spec-kitty safe-commit` failed on its first invocation for WP01's repair
   commit with:
   ```
   Error: global_assets: Global asset input changed: /home/<user>/.agents/skills/ad-hoc-profile-load; re-run the command; if it persists, run `spec-kitty doctor --help` to find the right diagnostic
   ```
   An immediate retry got past that error but surfaced a real usage error
   (missing required `FILES...` / `--to-branch` arguments — this WP's own
   invocation mistake, not tooling friction; corrected on the next call).
   The corrected `safe-commit` invocation then hit the same transient family
   again, this time naming a different global asset:
   ```
   Error: slash_commands: Global asset input changed: /home/<user>/.kittify/cache/agent-commands-freshness.lock; re-run the command; if it persists, run `spec-kitty doctor --help` to find the right diagnostic
   ```
   A second immediate, identical retry succeeded and committed cleanly
   (`687dcebf6`). Sixth and seventh occurrences of this transient across the
   mission so far (3 spec phase, 1 plan phase, 2 WP01 implementation phase),
   one retry resolving it every time observed — consistent with items 1 and 6's
   "reproducible but not a phase-level defect" framing.

## Close-phase assessment

_(to be appended at mission review/close)_
