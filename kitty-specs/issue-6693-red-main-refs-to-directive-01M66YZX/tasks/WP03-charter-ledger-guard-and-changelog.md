---
work_package_id: WP03
title: Repoint the charter ledger, guard it, and record the change
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- NFR-002
- SC-002
- SC-004
planning_base_branch: issue-6693-red-main-refs-to-directive
merge_target_branch: issue-6693-red-main-refs-to-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6693-red-main-refs-to-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6693-red-main-refs-to-directive unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - The repository's own governance surface
history:
- at: '2026-10-30T17:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .kittify/charter/
create_intent:
- tests/charter_offering/test_red_main_ledger_resolution.py
execution_mode: code_change
model: ''
owned_files:
- .kittify/charter/activation.yaml
- .kittify/charter/charter.yaml
- .kittify/charter/synthesis-manifest.yaml
- .kittify/charter/charter.md
- .kittify/charter-packs/graph.yaml
- tests/charter_offering/test_red_main_ledger_resolution.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Repoint the charter ledger, guard it, and record the change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6693-red-main-refs-to-directive-01M66YZX`) and address every item before handing back.

## Objectives & Success Criteria

- This repository's activation ledger activates the directive and no longer names the
  retired procedure, so governed commands resolve against the bumped packs. Spec FR-004.
- `spec-kitty charter context --action implement` reports no catalog miss and
  `spec-kitty doctor charter-packs` reports no activation-ledger warning. Spec SC-002.
- A fast, network-free guard test fails on the un-repointed ledger and passes on the
  repointed one. Spec FR-005.
- `.kittify/charter/charter.md` points Standing Order #9 at the directive. Spec FR-004.
- The changelog tells a consumer what changed and what they must do. Spec FR-006.

## Context

The issue's list stops at the curated edge, five tests and one fixture. The pin bump
also dangles **this repository's own charter**, which is the user-visible half of the
same defect:

```
Charter catalog miss for procedure:red-main-release-discipline; cause=missing_artifact
DENY_UNKNOWN_ID: deactivated_procedures in .kittify/charter/activation.yaml lists
  red-main-release-discipline, which no layer provides. Remove the stale entry by hand.
```

The first appears on every `spec-kitty charter context` render (so on every governed
command), and it makes Standing Order #9's doctrine pointer unresolvable. Fixing it is
in scope and proportional: one deactivation, one activation, one stale deny line.

## Subtasks

### T010 — Write the red guard test first

Create `tests/charter_offering/test_red_main_ledger_resolution.py`. It must fail on the
current tree and pass after T011.

Shape it as a resolver test over the **repository's own** ledger and the **fetched**
packs, using the production surfaces (acceptance-criteria-non-vacuity: exercise the
production path, not a helper):

- Read `.kittify/charter/activation.yaml` through the real loader
  (`charter.activation.activation_ledger.load_activation_ledger` or the public
  accessor the doctor uses — read the source, do not guess).
- Resolve each `activated_*` and `deactivated_*` id against the fetched built-in +
  internal pack roots (`packs/built-in`, `packs/internal`; `packs/internal` is declared
  under `charter_packs.org` in `.kittify/config.yaml`).
- Assert: every activated id resolves, and no `deactivated_*` id names an id no layer
  provides.

Non-vacuity, both required:

- **Positive control on the same fixture.** In the same test module, assert that a
  *known-good* id (e.g. `DIRECTIVE_034` / `034-test-first-development`) does resolve, so
  a broken resolver cannot make the negative assertion pass by seeing nothing.
- **Production entry point.** Prefer the same code path `spec-kitty doctor
  charter-packs` uses; if you assert on CLI output, invoke the CLI through
  `typer.testing.CliRunner` as `tests/charter_offering/test_doctor_activation_ledger.py`
  does.

Mark the module `pytestmark = [pytest.mark.fast]` (the fast tier, no network, no
`make sync-packs`). If the fetched trees are absent, `pytest.skip` with a message naming
`make sync-packs` rather than failing on a clean CI shard — the same preamble style the
other pack-reading tests in `tests/charter_offering/` already use (read
`test_testing_doctrine_single_owner.py` for the exact idiom).

Show the red: run it before T011 and paste the failure into your hand-back.

### T011 — Repoint the ledger through the CLI seam

Order matters: activating the directive while the retired procedure is still activated
makes the compile seam refuse (`Catalog not recompiled: No procedure artifact with
config ID 'red-main-release-discipline' found …`).

```bash
uv run --frozen spec-kitty charter deactivate procedure red-main-release-discipline
uv run --frozen spec-kitty charter activate directive RED_MAIN_RELEASE_DISCIPLINE --cascade all
```

Then remove the stale deny entry **by hand**: the deactivation appends
`deactivated_procedures: [red-main-release-discipline]`, and because no layer provides
that procedure any more, the doctor reports `DENY_UNKNOWN_ID` and prescribes exactly
this removal. Delete the now-empty `deactivated_procedures:` key.

Never hand-edit `.kittify/charter/charter.yaml` or `synthesis-manifest.yaml`: the CLI
regenerates them. The expected diff is small (catalog entry moved from `PROCEDURE:` to
`DIRECTIVE:`, `local_path` becomes `_LIBRARY/directive-red-main-release-discipline.md`,
`generated_at` stamp, bundle/manifest hashes, plus a one-line project-DRG label refresh
that regeneration emits).

### T012 — Refresh the two charter.md pointers

`.kittify/charter/charter.md`:

- Standing Order #9's pointer (`→ \`red-main-release-discipline\` procedure, ADR
  \`2026-07-17-1\`.`) becomes the `RED_MAIN_RELEASE_DISCIPLINE` **directive**.
- The `NO_FULL_HEAVY_SUITES_IN_MISSION` paragraph that says it reconciles with
  `no-parallel-duplicate-test-runs` and `red-main-release-discipline` becomes the
  directive id.

Add a dated `Updated:` line to the charter header recording the repoint and the issue
number, matching the existing header style. Do not reword the standing order itself.

### T013 — Verify the governance surface is clean

```bash
uv run --frozen spec-kitty charter context --action implement 2>&1 | grep -i "catalog miss" ; echo "exit=$?"
uv run --frozen spec-kitty doctor charter-packs 2>&1 | tail -5
uv run --frozen spec-kitty charter consistency-check 2>&1 | tail -3
uv run --frozen pytest -q -p no:randomly tests/charter_offering/test_red_main_ledger_resolution.py
```

Expected: no catalog miss, `Activation ledger warnings — 0` (or no warning block at
all), `Active charter is coherent.`, guard test green. Note: the pre-existing
`toolguide:typescript-mutation-tools` scope-filtered warning is unrelated and may stay.

### T014 — Changelog entry

Under `[Unreleased]` in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink
to it), add one entry following the file's house style: a bold impact-first lead with
`(#6693)`, then before/after, under 1,200 characters. Content to convey:

- The red-main rule now ships as the built-in `RED_MAIN_RELEASE_DISCIPLINE` directive
  (and the internal pack's as the `SPEC_KITTY_RED_MAIN_POLICY` directive), following
  `spec-kitty-open-packs#74`; the pin moves to `72cb7dbc`.
- Before: activating the internal pack on the previous core release produced three
  dangling `directive:RED_MAIN_RELEASE_DISCIPLINE` edges; after: the reference resolves.
- **Consumer action**: if your project's `.kittify/charter/activation.yaml` lists
  `red-main-release-discipline` under `activated_procedures`, run
  `spec-kitty charter deactivate procedure red-main-release-discipline` then
  `spec-kitty charter activate directive RED_MAIN_RELEASE_DISCIPLINE`, and remove the
  stale deny entry the doctor reports.

Run `uv run --frozen python -m scripts.docs.check_changelog_style` and
`uv run --frozen python -m scripts.docs.check_spelling` (the `docs-lint` target) before
handing back.

## Branch Strategy

Planning branch and final merge target: `issue-6693-red-main-refs-to-directive`.
`single_branch` mission; the runtime allocates the workspace. WP01 must be `done` or
`approved` before this WP can be claimed.

## Test strategy

Fast-tier only: the new guard module plus `tests/charter_offering/test_doctor_activation_ledger.py`
(its machinery is what you are relying on). No full heavy suite
(NO_FULL_HEAVY_SUITES_IN_MISSION).

## Definition of Done

- [ ] The guard test is red before T011 and green after, with the red run recorded.
- [ ] `git diff .kittify/charter/charter.yaml` shows a regenerated catalog (kind moved, `local_path` renamed, hash/stamp refreshed) — never a hand-edited one.
- [ ] `deactivated_procedures` no longer lists the retired id.
- [ ] `charter context`, `doctor charter-packs` and `charter consistency-check` are clean.
- [ ] `charter.md` has exactly two pointer changes plus the dated `Updated:` line.
- [ ] Changelog entry passes `docs-lint` and is under 1,200 characters.
- [ ] Tracer entry appended via `spec-kitty agent tracer-append`.

## Risks & Reviewer Guidance

- **Hand-edited compiled charter.** If `.kittify/charter/charter.yaml` changes look
  hand-made (a deleted block with no regenerated replacement, a missing stamp), reject.
- **Guard test that cannot fail.** Reviewer: revert `.kittify/charter/activation.yaml`
  and confirm the guard goes red, then restore. A green test on the broken ledger is a
  vacuous guard.
- **Deactivated-id residue.** Leaving `deactivated_procedures:` in place keeps a
  doctor warning alive — the very thing this WP exists to clear.
- **Silent scope creep.** `charter.md` wording of the standing order must not change;
  only the pointers and the header line.
