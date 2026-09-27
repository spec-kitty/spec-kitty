# Tracer: approach — analyze-prompt-context-load-01M3F4BV

## Plan phase (2026-09-26)

This mission's plan is deliberately small, mirroring the spec's own scope discipline
(Operator Decisions 1–4, 6): FR-001 (delete the stale `analyze.md` project-local override so
resolution falls through to canonical) and FR-002 (advisory doctrine naming the
size-assumption-bypass failure mode, plus the required DRG-regeneration companion step).
FR-005/006/007 (governance-context budget gap) are explicitly out of scope per Operator
Decision 6 and are not designed for in this plan.

The approach for FR-001 leans entirely on an existing, unmodified resolution chain
(`charter.offering.resolver.resolve_command` -> `MissionTemplateRepository._command_template_path`):
deleting the one shadowing file is the entire mechanism. No code change. This was verified,
not assumed — the resolver code was read line-by-line during plan authoring to confirm the
canonical fallback path it lands on after the override is gone, and a live (read-only)
invocation of `resolve_command("analyze.md", ...)` against this checkout confirmed it
currently returns `tier=OVERRIDE` today (i.e., the red-first test sketch in plan.md would
genuinely fail before FR-001 lands).

The approach for FR-002 leans on the existing tactic/directive YAML shape (both schemas read
in full; both already accept free-form string arrays for `failure_modes` /
`procedures` with no additional constraint) rather than proposing any schema change —
appending one more string to each array is a same-shape addition, dry-run-validated against
the unedited files during plan authoring (`spec-kitty doctrine validate` on both files
already passes today).

Gate-selection claims in plan.md are backed by the real, importable authority
(`scripts.ci.gate_selection.select_gates`) invoked directly against the planned file set,
not by reading workflow YAML and guessing — the same authority `make ci-parity` itself calls,
so the answer is the actual CI answer for that file set, not a paraphrase of it.

## Plan-revision pass (2026-09-26, Operator Decision 7)

Between the plan-phase entry above and this pass, upstream PR #5133 merged into `main`
(2026-09-26T19:56:16Z), resynced all 10 stale `.kittify/overrides/missions/software-dev/command-templates/`
files — including `analyze.md` — to byte-parity with canonical, and added a new gate,
`tests/cross_cutting/test_kittify_override_parity.py` (nightly-only, no per-PR lane). This
branch subsequently merged `origin/main` @ `34b53d78e` (which includes #5133). Operator
Decision 7 (2026-09-26, binding) responded by dropping FR-001 as a build item entirely:
deleting the override now would remove content a gate this mission did not author depends
on, for zero behavior change (the bytes already match canonical). This pass's approach was
therefore to strip FR-001's entire mechanism, seam, and red-first test from the plan rather
than adapt them, and to re-verify — not merely reuse — every FR-002 claim the plan still
made, on this merged checkout, right now:

- Re-read and re-ran `spec-kitty doctrine validate` against both FR-002 target files
  (unedited) — both still pass, unchanged in content by #5133.
- Re-ran `spec-kitty doctrine regenerate-graph --check` — still exits 0 (`DRG graph is
  fresh`).
- Discovered, by actually running `--collect-only`, that the prior round's suggested FR-002
  test home (`tests/doctrine/directives/test_schema_compatibility.py`) and the alternative
  considered in the same round (`tests/doctrine/test_tactic_compliance.py`) both glob a
  pre-relocation path (`src/charter/offering/{directives,tactics}/built-in`) that no longer
  exists on this checkout, so their content-facing tests collect as vacuous `[NOTSET]`
  parametrizations that can never exercise real doctrine content. Chose
  `tests/doctrine/test_directive_consistency.py` instead — the one file in this test tree
  that correctly resolves the post-relocation `packs/built-in/` layout — and added a new,
  genuinely RED (verified by actually running it, not asserted) content-assertion test there.
- Re-derived the gate set from scratch against the narrower FR-002-only file set (no more
  `.kittify/overrides/...analyze.md`), re-running both `select_gates()` and `select_modules()`
  in-process and `make ci-parity` for real, and cross-checked against
  `~/.hermes/skills/sk/SKILL.md`'s §Gates table (found two new, non-PR-blocking workflow
  files not yet reflected in that table — `ci-fleet-verdict.yml`, `ci-stale-running-sweep.yml`
  — neither changes the gate set for this diff).
- Re-baselined at the current merged `main` tip (`34b53d78e`), not the old, now-stale
  merge-base, in a fresh disposable worktree under the sibling mission-workspace directory
  (never `/tmp`), removed cleanly afterward.
- Re-checked the open-PR list fresh (`gh pr list`/`gh pr view`, read-only) against the
  actual, narrower write set — zero overlap, and the #5133 modify/delete git-mechanics risk
  the prior round spent significant text resolving no longer applies at all, since #5133 is
  merged and this mission's diff no longer touches the file it once conflicted over.

## Tasks phase (2026-09-26)

Per Operator Decision 7, this mission's actual build scope collapsed to a single
`code_change` work package (WP01) covering FR-002 alone: one failure-mode/procedure entry
in the two canonical-source-unification doctrine files, the required
`spec-kitty doctrine regenerate-graph` write-mode companion step, and one new red-first
content test in `tests/doctrine/test_directive_consistency.py`. No second WP was invented —
plan.md's Charter Check explicitly found no campsite-clean substitute for this mission
("dropped per Operator Decision 7 — no substitute found"), and the tasks-phase re-check of
that same question (the WP's target files, checked for any other domain-matched staleness)
turned up nothing new either.

**PR shape**: this repo's default is one PR per mission (not one per WP), stated explicitly
here per the sk overlay to the design pipeline; with exactly one WP, this is trivially
satisfied — a single PR carries WP01's entire diff.

Followed the canonical `tasks-outline` -> `tasks-packages` -> `tasks-finalize` CLI flow
verbatim: `spec-kitty agent context resolve --action tasks_outline`, hand-wrote `wps.yaml`
(one entry, `cross_cutting: true` since plan.md declares no `IC-##` implementation-concern
IDs to cite), materialized `tasks/WP01-unverified-size-assumption-doctrine.md` directly
(no sub-agent dispatch needed for a single WP), then `finalize-tasks --validate-only`
followed by the mutating `finalize-tasks` run. See `tracer-tooling-friction.md` for the one
real friction point hit (`FR-005` requirement-mapping false positive) and
`tracer-design-decisions.md` for how it was resolved.

## WP01 implementation (2026-09-27)

Followed the WP prompt's T001-T004 order exactly: red-first test committed standalone
(`13ce597e6`), confirmed genuinely RED via `AssertionError` (not a collection/import error)
against the pre-edit doctrine files, then T002's single `failure_modes` entry (tactic file
only — plan.md/spec.md's "and/or" was satisfied by editing the tactic file; the directive
file was left untouched to keep the diff minimal per smallest-viable-diff), then T003's
`regenerate-graph` write mode (no structural graph diff resulted — `failure_modes`/
`procedures` text isn't part of a DRG node's urn/kind/label/edges — but the required
companion `pack-manifest.yaml` content/manifest hash DID change and was committed alongside
per the dispatch's own KNOWN WRITE-SCOPE RISK note: the write-scope guard warned
(`ACTIVE_WP_SCOPE_VIOLATION`) but did not refuse, so it was committed as instructed
(`a4c4e9c69`)), then T004's companion-test confirmation. See `tracer-tooling-friction.md`
for the three pieces of lane-worktree tooling friction this round surfaced (DRG root
resolution, stale global CLI on PATH, `make lint`/`format-check` creating a broken
worktree-local `.venv` via `uv run`) and the workarounds used for each.
