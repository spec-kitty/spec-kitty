---
work_package_id: WP01
title: Standing URL baseline and moves ledger
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-012
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-005
- C-006
- SC-001
- SC-002
- SC-005
planning_base_branch: issue-6927-url-baseline-moves-ledger
merge_target_branch: issue-6927-url-baseline-moves-ledger
branch_strategy: Planning artifacts for this mission were generated on issue-6927-url-baseline-moves-ledger. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6927-url-baseline-moves-ledger unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - S-3 ledgers (#6927)
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- site/url-baseline.txt
- site/moves.yaml
- scripts/docs/moves_ledger.py
- tests/docs/test_moves_ledger.py
execution_mode: code_change
model: ''
owned_files:
- site/url-baseline.txt
- site/moves.yaml
- scripts/docs/moves_ledger.py
- scripts/docs/redirect_stub_generator.py
- scripts/docs/redirect_map.yaml
- .github/workflows/docs-pages.yml
- tests/docs/test_moves_ledger.py
- tests/docs/test_redirect_stub_generator.py
- tests/docs/test_redirect_spine.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Standing URL baseline and moves ledger

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `site/moves.yaml` and `site/url-baseline.txt` exist, follow `contracts/moves-ledger.md` and `contracts/url-baseline.md`, and carry a provenance header.
- `scripts/docs/moves_ledger.py` is the single reader and validator of both ledgers.
- `redirect_stub_generator.py regenerate-map` / `check-map` derive `scripts/docs/redirect_map.yaml` from `site/moves.yaml` alone, with chain collapse. `MISSION_SLUG` and `DEFAULT_OCCURRENCE_MAP` are gone from the module.
- The 124 file moves of #3914 have redirects to a published route. The forward reconcile, run against the convergence occurrence map once as a check, reports 0 findings.
- `coverage` defaults to `site/url-baseline.txt`. A new `baseline-drift` subcommand warns (exit 0) about pages missing from the baseline.
- Tests: SC-001, SC-002 and SC-005 hold; NFR-002 (deterministic) and NFR-004 (< 5 s) hold.

## Context & Constraints

- Spec: `kitty-specs/docsite-url-ledgers-01M6BRMR/spec.md`. Plan: `plan.md`. Decisions: `research.md` D1–D6. Entities and invariants: `data-model.md`. Facts and numbers: `research/code-grounding.md`.
- ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-5 (URL contract, ledgers, rules 1–4).
- DocFX keeps deploying (C-001). The deploy job runs these scripts with system `python3` plus PyYAML. Do not add a dependency.
- Do not edit the closed occurrence maps under `kitty-specs/common-docs-*` (pinned by `tests/architectural/test_archive_root_byte_identical.py`).
- Charter: complexity ≤ 15, ruff, `ruff format --check --force-exclude`, mypy clean, no blanket suppressions.

## Branch Strategy

- **Strategy**: single_branch (WPs run sequentially in the repository root checkout)
- **Planning base branch**: issue-6927-url-baseline-moves-ledger
- **Merge target branch**: issue-6927-url-baseline-moves-ledger

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission docsite-url-ledgers-01M6BRMR`

## Subtasks & Detailed Guidance

### Subtask T001 – Acceptance tests for the ledgers (red)

- **Purpose**: pin the user-observable contract before any code (ATDD, C-011). Commit this file alone first and show it red.
- **File**: `tests/docs/test_moves_ledger.py` (new). Mark it `pytestmark = pytest.mark.fast` if sibling docs tests use that marker (check `tests/docs/conftest.py` / neighbours).
- **Tests on the committed ledgers** (they fail today because the files do not exist):
  1. `test_baseline_contains_old_manifest`: every URL of `scripts/docs/redirect_baseline_urls.json` (`site_url` stripped, leading `/` added) is in `site/url-baseline.txt`. **FR-002**
  2. `test_baseline_contains_every_redirect_key`: every key of `scripts/docs/redirect_map.yaml` (with leading `/`) is in the baseline. **FR-002**
  3. `test_committed_map_is_the_ledger_derivation`: `derive_redirect_map(load_moves(site/moves.yaml))` equals the committed map, and rendering it twice is byte-identical to the file. **FR-004, NFR-002**
  4. `test_issue_3914_forward_reconcile_clean`: for every `.md` file move (destination not `RETIRE`) in `kitty-specs/common-docs-convergence-01KZMTR9/occurrence_map.yaml`, its old route is a key. Read the file directly here; it is test evidence of #3914, not tooling. **FR-006, SC-002**
  5. `test_every_baseline_route_is_published_or_redirected`: PR-time mirror of `coverage`. Each baseline route is either a route the docs tree publishes (derive-from-source via `capture_baseline_urls.derive_urls_from_source`, `.html` only) or a map key whose collapsed target is published. **NFR-001**
  6. `test_no_redirect_key_is_a_published_page` and `test_every_redirect_target_is_published`. **FR-005**
  7. `test_ledger_header_records_manifest_amendments`: the header comments name each amendment `pr`/`date` of the JSON manifest (`#2350` twice, the 2026-07-20 Mission extension). **FR-003**
- **Unit tests on `moves_ledger`** (`tmp_path` fixtures):
  - chain collapse (A→B, B→C ⇒ A→C, B→C);
  - cycle refused (`MovesLedgerError`);
  - duplicate `from` refused;
  - wrong `kind`/`version` refused;
  - `validate()` reports a live `from` and a dead target, each with a passing fixture beside it (positive control);
  - baseline parsing skips comments and blanks, refuses a line without a leading `/`;
  - `route_to_source('/a/b.html') == 'docs/a/b.md'` and back.
- **Validation**: `uv run --frozen pytest tests/docs/test_moves_ledger.py -q` fails (import or missing files). Record the red output in the commit message or a history note.

### Subtask T002 – `scripts/docs/moves_ledger.py`

- **Purpose**: one authority for reading and validating both ledgers (charter: single canonical authority).
- **API** (declare `__all__`, full type hints, stdlib + PyYAML only):
  - `REPO_ROOT`, `DEFAULT_MOVES_LEDGER = REPO_ROOT / "site" / "moves.yaml"`, `DEFAULT_URL_BASELINE = REPO_ROOT / "site" / "url-baseline.txt"`, `LEDGER_KIND = "docs-moves-ledger"`, `LEDGER_VERSION = 1`.
  - `class MovesLedgerError(ValueError)`.
  - `@dataclass(frozen=True) class Move: from_route: str; to_route: str; ref: str; note: str = ""`.
  - `load_moves(path) -> list[Move]`: checks `kind`/`version`, that each route starts with `/`, that `ref` is non-empty, and that no `from` repeats.
  - `collapse(moves) -> dict[str, str]`: follows each chain to its end and raises on a cycle.
  - `derive_redirect_map(moves) -> dict[str, str]`: collapsed, keys and values without the leading `/` (DocFX map form), sorted.
  - `validate(mapping, published: set[str]) -> list[str]`: problems in the slash-less form: `"<k>: source is a published page"`, `"<k> -> <v>: target is not published"`.
  - `load_baseline(path) -> list[str]`: sorted, de-duplicated routes; raises on a line without a leading `/`.
  - `route_to_source(route) -> str | None` and `source_to_route(path) -> str | None`, for `.md` pages only (`.html` resources map as-is).
  - `source_pairs(moves) -> list[tuple[str, str]]`: `docs/` source-path pairs, for WP02's link rewriters. Skip pairs whose `to` is not a page source.
- Keep each function ≤ 15 complexity. No CLI here.

### Subtask T003 – Seed the ledgers

- **Purpose**: FR-001, FR-003, FR-006.
- **Steps**:
  1. Write a throwaway seeding script under `/tmp` (not committed). It reads:
     - the committed `redirect_map.yaml` (163);
     - the convergence occurrence map's 124 violating file moves, each resolved to a route (old route → recorded destination route, as `_resolve_new_url` computed it);
     - the DocFX walk JSON (`/tmp/walk.json` from the grounding, or re-run DocFX per the grounding note §2).
  2. `site/moves.yaml` sections, each opened by a comment block:
     - **(a)** carried map entries, `ref: "mission:common-docs-structural-move-01KW3SBK / common-docs-convergence-01KZMTR9"`;
     - **(b)** #3914 reconcile, `ref: "#3914"`;
     - **(c)** follow-on entries for destinations that moved again or were archived. Example: `/development/create-a-doctrine-artifact.html → /development/how-to/create-a-doctrine-artifact.html`. Archived and unpublished pages go to their section hub (ADR D-5 rule 4): `/development/reference/index.html`, `/plans/investigations/index.html`, `/plans/testing/index.html`, `/plans/index.html`, `/adr/<era>/index.html` for `architecture/README-<era>.html`. Each gets a `note`. Grounding §3 lists the 11.

     Flow-style one-line entries.
  3. Ledger header comments:
     - purpose and append-only rule;
     - the route form;
     - how to add a move (point at `quickstart`);
     - provenance: the 2 closed Missions, the #3914 reconcile, the seeding date and base commit;
     - the three amendments of `redirect_baseline_urls.json` copied verbatim in summary (date, PR, ground, ruling, counts).
  4. `site/url-baseline.txt`: walk routes (excluding `/kitty-specs/**` and `/toc.html`) ∪ every derived key, sorted, leading `/`. Header:
     - sources, with the DocFX version and base commit;
     - counts;
     - exclusions and why (ADR D-5 "Dropped dashboards"; `toc.html` is a navigation fragment);
     - the amendment rule;
     - that the JSON manifest's amendments are recorded in `site/moves.yaml`'s header.
- **Validation**: T001 tests 1, 2, 4, 6 and 7 go green after T004 regenerates the map.

### Subtask T004 – Repoint `redirect_stub_generator.py` and regenerate

- **Purpose**: FR-004, FR-005, FR-012; #2358 for this script.
- **Steps**:
  - Add the sys.path bootstrap used by `relative_link_fixer.py` and import from `scripts.docs.moves_ledger`.
  - Delete `MISSION_SLUG`, `DEFAULT_OCCURRENCE_MAP`, `Move`, `load_moves`, `_url_path_to_repo_paths`, `_relocate`, `_repo_path_to_url_path`, `_resolve_new_url`, the old `derive_redirect_map` and `_default_occurrence_map`. No dead code stays behind.
  - `regenerate-map` / `check-map` take `--moves` (default `DEFAULT_MOVES_LEDGER`) and drop `--occurrence-map`.
  - `regenerate-map` validates against the published set (derive-from-source `.html`) and exits 1 with the problems listed.
  - Update `REDIRECT_MAP_HEADER` to name `site/moves.yaml`.
  - `load_baseline` accepts either the JSON manifest or a `.txt` ledger (dispatch on suffix), returning slash-less paths. `DEFAULT_BASELINE` becomes `site/url-baseline.txt`; the JSON keeps its non-`.html` refusal.
  - `generate` reads the site URL constant (the `.txt` has none; keep `SITE_URL`).
  - New subcommand `baseline-drift --site-dir`: walk `*.html` pages (reuse `capture_baseline_urls.urls_from_site`), drop `kitty-specs/` and `toc.html`, and print `::warning title=URL baseline::<route> is published but not in site/url-baseline.txt` per missing route plus a count. Always exit 0.
  - Rewrite the module docstring: standing ledger, no Mission binding.
  - Run `python3 scripts/docs/redirect_stub_generator.py regenerate-map`, then `check-map`.

### Subtask T005 – Re-pin the generator and spine tests

- **Purpose**: the old tests pin the Mission-bound derivation (judge the test: stale → re-pin, charter SO #4).
- `tests/docs/test_redirect_stub_generator.py`:
  - drop the prefix-relocation unit tests (their behaviour is deleted; T001 covers collapse);
  - rewrite `test_committed_redirect_map_is_diff_stable` on the ledger;
  - keep the stub, coverage, baseline and amendment tests;
  - add a test that `load_baseline` reads the `.txt` form.
- `tests/docs/test_redirect_spine.py`: keep the frozen 149-key guarantees (`FROZEN_PRIOR_REDIRECT_KEYS ⊆ derived`, the archive twice-move composed to `changelog/`, stable values) but derive from the ledger. Replace `test_empty_moves_regresses_coverage` with an empty-ledger equivalent. Replace `test_tool_default_targets_this_convergence_mission` with `test_tool_default_is_the_standing_ledger` (the default is `site/moves.yaml`, and no module constant names `kitty-specs`). Update the docstring.

### Subtask T006 – `docs-pages.yml`

- Add `'site/url-baseline.txt'`, `'site/moves.yaml'`, `'scripts/docs/moves_ledger.py'` and `'scripts/docs/capture_baseline_urls.py'` to the push `paths`.
- After `Verify redirect coverage`, add `Report URL baseline drift (grow-on-publish, #6927)` running `python3 scripts/docs/redirect_stub_generator.py baseline-drift --site-dir docs/_site`, with a comment that it reports, never gates. Update the comments on the stub and coverage steps: the map is derived from `site/moves.yaml`, and coverage reads `site/url-baseline.txt`.
- Check `tests/ci/` for a workflow-shape test that pins step names or path lists, and run it.

## Test Strategy

- `uv run --frozen pytest tests/docs/test_moves_ledger.py tests/docs/test_redirect_stub_generator.py tests/docs/test_redirect_spine.py tests/docs/test_capture_baseline_urls.py tests/docs/test_publish_manifest_coherence.py -q`
- `uv run --frozen mypy scripts/docs/moves_ledger.py scripts/docs/redirect_stub_generator.py`
- `uv run --frozen ruff check <changed>`; `uv run --frozen ruff format --check --force-exclude <changed>`
- NFR-001: local DocFX build (grounding §2), then `generate --site-dir` and `coverage --site-dir` on it: 0 dead, 0 uncovered.

## Risks & Mitigations

- **A seeded `from` is a live page**: `validate` refuses it; fix the seed.
- **A target is archived**: use the hub (rule 4) with a `note`.
- **Deploy `coverage` on a page deleted later**: the PR-time mirror test catches it before merge.

## Review Guidance

- Red→green: T001 is red at its own commit.
- The two ledgers parse; the header provenance is complete; no line of the seed was hand-invented without a `ref`.
- `grep -n "kitty-specs\|occurrence" scripts/docs/redirect_stub_generator.py` finds no binding.
- Local DocFX coverage evidence is recorded.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP01 --note "..."` and `spec-kitty agent tasks move-task WP01 --to <status>`.
