---
work_package_id: WP03
title: Conformance case table, docs and changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
- FR-006
- SC-001
- SC-002
- SC-003
- SC-004
- NFR-004
- C-004
planning_base_branch: issue-6733-charter-escape-report-convergence
merge_target_branch: issue-6733-charter-escape-report-convergence
branch_strategy: Planning artifacts for this mission were generated on issue-6733-charter-escape-report-convergence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6733-charter-escape-report-convergence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-escape-report-convergence-01M66YM0
base_commit: fda12b6769968f0221e84e4eb59265025348622f
created_at: '2026-10-30T19:10:21.757630+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Make the convergence inheritable and visible
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/conformance/
create_intent:
- tests/charter/conformance/pack_containment_cases.yaml
- tests/charter/conformance/test_pack_containment_conformance.py
execution_mode: code_change
model: ''
owned_files:
- tests/charter/conformance/pack_containment_cases.yaml
- tests/charter/conformance/test_pack_containment_conformance.py
- tests/charter/conformance/__init__.py
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
- tests/scenarios/charter/PROMISES.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Conformance case table, docs and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or
any user-defined profile), and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting, and
address every feedback item as its own TODO. Record what you changed with
`spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

The issue's fourth bullet asks that the containment rule exist as a conformance case, "so the
spec-kitty-charter replacement inherits the rule". The repository's only corpus
(`activation_ledger_cases.yaml`, `activation-ledger-conformance/1`) covers activation answers and has
no pack-validation section, so this WP adds a small, additive, plain-data table in the same directory
plus a runner that asserts **all three surfaces** against each pack shape.

After this WP:

- `tests/charter/conformance/pack_containment_cases.yaml` states the rule as data (four cases:
  escaping `body_path`, escaping asset `path`, both, contained);
- `tests/charter/conformance/test_pack_containment_conformance.py` drives the three production entry
  points (doctor's collector, the status collector, the `charter org validate` CLI) and fails if any
  surface disagrees;
- the table is green only when WP01 and WP02 are both in place, and goes red if either fix is
  reverted (the half-by-half proof);
- `docs/api/charter-commands.md` documents the status behaviour and the `body_path_escape` category;
- `docs/changelog/CHANGELOG.md` carries one `[Unreleased]` entry for #6733;
- `tests/scenarios/charter/PROMISES.md` names all three surfaces for `PR-CHARTER-SHARING-004`.

Success: corpus, docs gates and the touched modules are green; no existing corpus row or schema
changed.

## Context & Constraints

- Mission: `kitty-specs/charter-escape-report-convergence-01M66YM0/` — read `spec.md` (FR-005,
  FR-006), `plan.md` (D-3, D-4), `research.md` (D4).
- Do **not** extend or modify `activation_ledger_cases.yaml`: #6534 owns that corpus and is on hold.
  Additive, separate file only.
- The runner must call production entry points, never helpers: a helper-only test can stay green
  while the wiring is broken (`acceptance-criteria-non-vacuity`).
- An `expect` key an adapter does not observe must fail the case — copy the discipline from
  `tests/charter/conformance/test_activation_ledger_conformance.py::assert_expected`.
- Keep the case file plain data, no expressions and no repository paths.
- No new doc page, so no docs-index regeneration is expected; run the freshness/terminology gates
  anyway.

## Branch Strategy

- **Strategy**: planning and merge target are this Mission's topic branch; the PR targets `main`.
- **Planning base branch**: `issue-6733-charter-escape-report-convergence`
- **Merge target branch**: `issue-6733-charter-escape-report-convergence`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them by
> hand unless the topology has genuinely changed.

## Subtasks & Detailed Guidance

### Subtask T011 – Author the case table

- **Purpose**: state the rule as portable data (FR-005).
- **Steps**:
  1. Create `tests/charter/conformance/pack_containment_cases.yaml` with `schema: pack-containment-conformance/1`
     and a header comment saying what the table is for, that it is ported by the replacement
     offering, and that each case asserts every reporting surface.
  2. Four cases, each naming the pack shape and the expected finding per surface, for example:
     - `escaping-body-path` — `pack: {node_body_path: "../../../../etc/hostname"}`,
       `expect: {doctor: ["ORG_FRAGMENT_BODY_PATH_ESCAPE"], status: {errors: 1, names: ["team-asset"]}, validate: {categories: ["body_path_escape"], ok: false}}`
     - `escaping-asset-path` — `pack: {asset_path: "../../../../etc/hostname"}`,
       `expect: {doctor: ["ORG_ASSET_PATH_ESCAPE"], status: {errors: 1, names: ["team-logo"]}, validate: {categories: ["asset_path_escape"], ok: false}}`
     - `both-escapes` — both shapes; all three surfaces report both findings.
     - `contained` — `pack: {node_body_path: "bodies/team.md", asset_path: "img/logo.png"}`; every
       surface clean (doctor `[]`, status `errors: 0`, validate `ok: true`, no categories).
  3. Keep the file's vocabulary plain: `pack`, `expect`, and per-surface keys only.
- **Files**: `tests/charter/conformance/pack_containment_cases.yaml`.

### Subtask T012 – Author the runner with three adapters

- **Purpose**: prove the three surfaces agree, on the production paths (FR-005, FR-006).
- **Steps**:
  1. Create `tests/charter/conformance/test_pack_containment_conformance.py`. Load the table once;
     parametrize one test per case.
  2. Build the project from the case's `pack` shape: copy
     `tests/architectural/_fixtures/org_packs/example_org`, write `.kittify/config.yaml` with
     `charter_packs.org.packs[0]`, add the authored node and/or the asset sidecar the case names
     (create the referenced blob for the contained case so its path is genuinely usable).
  3. Adapters:
     - **doctor** — `specify_cli.cli.commands.doctor._collect_org_layer_data(repo)`: codes from
       `body_path_escapes` + `asset_path_escapes`, and the `errors` list.
     - **status** — `specify_cli.cli.commands.charter._collect_org_layer_status(repo)`: the
       `errors` list; assert the count and that each expected `name` appears in a message.
     - **validate** — the `charter org validate <pack>` CLI through `CliRunner`: `exit_code`, the
       set of issue categories, and the rendered output.
  4. Assert exactly the case's `expect` per surface; fail on an unknown `expect` key. Add a
     module-level `assert_expected`-style helper rather than repeating the comparison.
  5. Register the new corpus in the package docstring (`tests/charter/conformance/__init__.py`), which
     currently describes only the activation corpus.
- **Files**: `tests/charter/conformance/test_pack_containment_conformance.py`,
  `tests/charter/conformance/__init__.py`.
- **Notes**: `pytestmark = [pytest.mark.fast]` (the activation runner uses `fast`); no network, no
  git. The corpus must be readable with `yaml.safe_load` only.

### Subtask T013 – Document the surfaces

- **Purpose**: the user-facing reference tells the same story as the code.
- **Steps**: in `docs/api/charter-commands.md`, beside the existing #6418 documentation:
  1. `charter status --json`: an escaping `body_path` or asset `path` is reported in
     `org_layer.errors` (same wording as `doctor charter-packs`), and a check that could not run is
     reported there too;
  2. `charter org validate`: add `body_path_escape` to the category list with one sentence, next to
     `asset_path_escape`.
  Keep the page's Divio type (reference) and its `updated:` date current.
- **Files**: `docs/api/charter-commands.md`.

### Subtask T014 – Changelog entry

- **Purpose**: an operator reading the changelog learns what changed for them.
- **Steps**: add one `[Unreleased]` bullet in `docs/changelog/CHANGELOG.md`: bold impact-first lead
  ending with `(#6733)`, then before/after, under 1,200 characters. Name the two commands and the
  fact that `doctor charter-packs` is unchanged. Follow the surrounding entries' style.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Notes**: the root `CHANGELOG.md` is a symlink to this file — edit this one only.

### Subtask T015 – Promise index row

- **Purpose**: the frozen-contract index names every surface that now carries the guarantee.
- **Steps**: extend the `PR-CHARTER-SHARING-004` authority cell in
  `tests/scenarios/charter/PROMISES.md` to name `charter status` and `charter org validate` beside
  `doctor charter-packs`, and note #6733. Do not change the scenario or its step bindings.
- **Files**: `tests/scenarios/charter/PROMISES.md`.

### Subtask T016 – Run the gates

- **Steps**:
  1. `uv run pytest tests/charter/conformance/test_pack_containment_conformance.py -q`
  2. `uv run pytest tests/specify_cli/cli/commands/charter/ tests/charter/packs/ -q`
  3. `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0)
  4. `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  5. Half-by-half proof: with the WP01 change stashed, the status assertions in the corpus must go
     red; with the WP02 change stashed, the validate assertions must go red. Record both outcomes in
     the WP history.
  6. NFR-004, structurally: confirm the two surfaces add no `load_org_drg`/`load_built_in_graph` call,
     no subprocess and no read of a declared `body_path`/asset target — the checks reuse the loaded
     fragments. Record the confirmation in the WP history.
- **Files**: none (validation only).
- **Notes**: no full-suite sweep.

## Test Strategy

- The corpus runner is the cross-surface test; per-surface edge cases stay in the WP01/WP02 modules.
- Positive control: the `contained` case runs on the same builder as the escaping cases, so the
  table cannot pass by flagging everything.
- Docs gates: freshness + terminology, as listed in T016.

## Risks & Mitigations

- **Corpus drift from the unit tests** → the corpus asserts only cross-surface agreement; details stay
  in the owning module.
- **A second corpus confusing a reader** → the package docstring and the case file header say what
  each corpus is for, and the activation corpus is untouched.
- **Docs freshness gate** → update `updated:` on the touched page.

## Review Guidance

- Confirm the table is plain data and additive (no edit to `activation_ledger_cases.yaml`).
- Confirm the runner drives the three production entry points and that reverting either fix turns the
  corresponding surface's assertion red.
- Confirm the changelog entry is impact-first, has `(#6733)`, and is under 1,200 characters.
- Confirm the docs page states the behaviour that actually ships.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`), never in this
file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
