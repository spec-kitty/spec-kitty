---
type: reference
updated: 2026-11-12
audience: mission orchestrator, implementer, reviewer
---

# Code grounding for #7578 (review prompt carries the WP diff and cited requirement text)

Base: `origin/main` `73a18543`. This file aggregates a read-only squad: code
grounding, evidence mining and issue discovery. A fresh-context second opinion then
challenged the claims, and its verdicts are folded in below (marked **2nd**).
Citations are `path:line` on the base. Everything here was read, not run.

## 1. Evidence (why this matters)

From the rc7 benchmark step register (gist `robertDouglass/c7325343…`). The gist was
read through a summariser, so the quotes are paraphrased and the numbers are exact.

- **7.1 + 7.2 (rank 1, score 20).** On `single_branch` the printed `git log/diff
  <base>..HEAD --stat` came back empty, because the base is the branch HEAD is on.
  Models then spent about 100 git and listing commands hunting the implementation
  commit. The harness compensated with `git log -p --max-count=5`, which added 7,500
  to 14,000 characters of unrelated history.
- **7.3 (rank 3, score 16).** 104 reads of `spec.md`/`plan.md`, the largest group in
  review, because the prompt lists `requirement_refs` IDs with no text.
- **C7 (prompt bloat).** The WP01 review prompt was 30,398 characters. The gist sets
  no diff-size cap.
- **Tracers.**
  - `kitty-specs/mission-status-artifact-reads-01M57KY3/tracer-tooling-friction.md:27-29`:
    a WP's code committed inside another WP's claim window. The range needs an upper
    bound and an honest note.
  - SK-240 / `reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:38-48`:
    `requirement_refs` is stored in three places. Read it from the WP frontmatter,
    which finalize validates, and never drop an unresolved ID silently.
- **Rough diff sizes.** Over the last 49 non-merge commits on main, excluding
  `kitty-specs/` and `docs/`: p50 1.9 KB, p90 19 KB, max 72 KB. These are
  per-commit, not per-WP.

## 2. Two independent review-prompt builders (C1, 2nd: CONFIRMED)

| Path | Entry | Base / range today | Prints |
|---|---|---|---|
| A: `spec-kitty agent action review` | `cli/commands/agent/workflow.py:2429-2655`. `_resolve_review_context` (1956-2033) gives an untyped dict (`branch_name`, `base_branch`, `base_ref`, `commit_count`, …). Rendered by `workflow_executor.build_review_prompt_lines` (2262-2409) → `_review_context_line` (2115-2147). Metadata goes to `review/prompt_metadata.py` `ReviewPromptMetadata.base_ref`. | Repo root: `claim_commit_for_wp..HEAD` (`review_context_for_repo_root_workspace`, 2534-2565), owned_files pathspec; **open above** (later WPs leak in), and the lower bound is the *last* claim, which disagrees with FR-021 on rework. Lane: `context.base_branch`, then the Mission branch, then a scored search over `main`/`2.x`/… (2568-2610). | Command strings only (`git log`, `git diff --stat`, "Full diff" command); no diff body; no requirement text |
| B: `spec-kitty next` | `src/runtime/next/prompt_builder.py` `_build_wp_prompt` (207-271) → `_review_command_lines` (371-414) | Repo-root `single_branch` workspaces get `lane_id="lane-planning"` (truthy; `workspace/context.py:1030`), so they always take the **lane arm**: `_lane_review_base` → `<target>..HEAD`. Commit-to-target: **empty** (the reported bug). Minted Mission branch: Mission-wide (2nd). No pathspec on the lane arm, so lane-mates leak in (2nd). Only owned checkouts (`lane_id=None`, `context.py:1140`) reach the claim-commit arm. | `git log --oneline`, `git diff --stat` command strings |

- The docstring at `prompt_builder.py:383-388` says repo root uses the claim commit.
  The code disagrees (2nd).
- The unit tests `tests/next/test_prompt_builder_review_base.py:88-109` use
  `lane_id=None` stand-ins, so the production `single_branch` arm is untested.

## 3. Recorded anchors per topology (C4, 2nd: PARTIAL, corrected)

| Topology | `wp_window.open_sha` (claimed/in_progress) | `lane_head` on `for_review` | Other per-WP anchors |
|---|---|---|---|
| lanes / lanes_with_coord | yes, after the lane exists. The first claim often records the gap `lane_branch_missing`, and the `in_progress` opener then carries the SHA. | yes (lane branch head) | – |
| single_branch, minted Mission branch (protected target) | yes (`lane_head.py:240-257,276-278`, FR-070) | yes | `wp-base` ref |
| single_branch, commit-to-target | **no** (`_read_lane_head` → `not_applicable` for `lane-planning`, `lane_head.py:283-286`; `transition_pipeline.py:189`) | **no** | `refs/spec-kitty/wp-base/<slug>/<WP>` (`lanes/claim_base.py:44`; **cleared on done/canceled**, 183); the commit that introduced the opener event (`claim_commit_for_wp` technique, `mission_runtime/claim_commit.py:118`); **2nd:** the commit that introduced the `for_review` event id (the same `git log -S<event_id>` technique) gives the upper bound |

**Window semantics (ADR `2026-11-08-2`, FR-021).**
- The opener is the first claimed/in_progress move after the WP last returned to
  `planned` from a non-review lane. A review rejection keeps the window.
- Leading `lane_branch_missing` openers are skipped. An unrecorded first opener is a
  gap.

**Gap kinds.**
- Written: `capture_failed`, `lane_branch_missing`.
- Reader-only: `not_recorded` (pre-#7403), `not_on_lane` (rewritten or rebased).

**Residuals.**
- Parallel claims or a parked claim on one lane make the window over-wide (strict
  xfail `test_parallel_claims_window_is_not_over_wide`; #5721).
- `open_sha` is `BRANCH_RELATIVE` and may not resolve after a rebase landing
  (`test_dossier_sha_provenance.py`).

**Readers.**
- Codec: `parse_wp_window` / `ParsedWpWindow`, `status/wp_window.py:62-116`, git-free.
- FR-021 selection: `window_opener_events` / `window_open_of` / `WindowOpen` /
  `WindowGap` in `consolidation/wp_attribution.py:859,909`. This is pure over
  injected `on_lane`/`is_ancestor` predicates.
- `approved_bound.approval_stamp` (312), and
  `write_branch_bound.bind_lane_predicates`/`classify_windows` (278, 304).
- None of these returns "open SHA + for_review lane_head" for one WP, and none reads
  through the status read door. The caller passes the events.

## 4. Layering (C5, 2nd: CONFIRMED)

- The enforced chain is `kernel <- charter <- {glossary, runtime, mission_runtime} <-
  specify_cli`.
- `runtime → specify_cli` is a frozen ledger, `_RUNTIME_ALLOWED_SPECIFY_CLI`
  (`tests/architectural/test_layer_rules.py:178-203`).
  - It is counted per first-level subpackage (`_specify_cli_subpackage`, 217), cap 22
    (`_baselines.yaml:22`).
  - It allows `status`, `lanes`, `review`, `workspace`, `requirement_mapping`,
    `core`, … but **not `consolidation`**.
  - A new module under an allowed subpackage does not grow the count.
- The CLI already imports `consolidation`.
- **Consequence.** To share one FR-021 rule between consolidation and the review
  prompt, move the pure opener selector down into `status/wp_window.py`, and
  re-export it from `wp_attribution` so consolidation keeps one rule. Leaving it in
  consolidation would force a second selector, which violates the single-authority
  principle.

## 5. Requirement text (C7, 2nd: CONFIRMED)

- **Grammar.** `requirement_mapping/grammar.py`:
  - kinds `FR|NFR|SC|C` (75), plus `DR|AR|QR` for research Missions (76, 80);
  - an optional `<slug>#` cross-Mission qualifier (111);
  - lowercase suffix `FR-003a`;
  - `parse`/`canonical`/`tokenize_refs` (189/213/319).
- **WP field.** `WPMetadata.requirement_refs` (`status/wp_metadata.py:237`).
  `runtime_bridge_cores.py:227 _iter_requirement_refs` already extracts cited IDs in
  runtime.
- **Declaration parsers.**
  - `_declaration_occurrences` (`requirement_mapping/__init__.py:133-172`): table
    row, heading, list item, bold lead.
  - `_requirement_named_sections` (255).
  - `parse_requirement_ids_from_spec_md` (528) returns IDs only.
- **ID → text: no function exists.** It belongs in `requirement_mapping`
  (runtime-importable), built on `_declaration_occurrences`, so it is not a third
  parser (#3481).
- **spec.md source.** Read through the placement seam
  (`mission_runtime/artifacts.py:80,303`).
- **Canonical template.** FR, NFR and C are table rows; SC are bold-led bullets
  (`spec-template.md:112-160`).
- Cross-Mission refs are shown as "cites another Mission", not resolved locally.

## 6. Gates that constrain the design

| Gate | Constraint |
|---|---|
| `test_git_path_listing_owner.py` (empty allowlist; census `_git_path_listing_census.py:63-99`) | No `diff/log/show` with `--stat/--numstat/--name-only/--name-status/--raw/--summary`, and no bare `diff-tree/-index/-files`, in `src/` outside `kernel/git`. Use `kernel.git.listing.numstat_entries`/`changed_paths`/`log_paths` (390-484). A plain `git diff a..b -- paths` (patch text) is **not** flagged. No `kernel.git` helper returns patch text today; a new one belongs in `kernel.git`. Command text inside prompt f-strings is not argv, so it is safe. |
| `test_layer_rules.py` | No `consolidation` import from `src/runtime`; ledger cap 22. |
| `test_status_read_single_door.py` | An AST scan bans the legacy finders across `src/` (shrink-only `LEGACY_READ_ALLOWLIST`, 204). `DOOR_ONLY_MODULES` (245-256) is opt-in and bans path-typed readers. A new reader calls `resolve_status_read` and should opt in. |
| `test_execution_context_parity.py` | Required for `src/runtime/next/**` and `src/specify_cli/status/**`. |
| `test_dossier_sha_provenance.py` | `wp_window` is BRANCH_RELATIVE; review must degrade, not fail. |
| `test_no_dead_symbols.py`, `test_cold_import_status_boundary.py` | New public names need a `src/` caller; keep heavy imports lazy. |
| ruff format ratchet | `workflow.py` and `workflow_executor.py` are in `[tool.ruff.format].exclude`; check with `--force-exclude`. |
| Changed-file single source | `core.vcs.git.merge_base_changed_files` is the pre-review gate's changed-file authority (`tasks_move_task_gates.py:310-324`). The review range is a **different** question (one WP's window) and must not replace or re-derive it. Sub-epic E owns that gate. |

No review-prompt size gate or budget exists. Precedents:
`review/fix_prompt.py:27 _MAX_FULL_FILE_LINES=100` and
`charter/activation/context_renderers/token_budget.py`.

## 7. Not reusable as the WP range (2nd)

- **#6715 evidence window** (`consolidation/wp_evidence.py:166-179`;
  `lanes/single_branch_landing.py:284 single_branch_evidence_window`). It runs
  Mission-wide, `planning_commit_sha..<tip>`, and returns paths only.
  - Its bookkeeping-prefix filter (`for_review_gate.status_only_excluded_prefixes:167`)
    **is** reusable for dropping status-only commits from the commit list.
- **`claim_commit_for_wp`.** It reads `status.events.jsonl` by path, which is fine on
  `single_branch`, but on coord topologies the log is not on the lane HEAD. Prefer
  the door.

## 8. Tests and cost

| File | Tests | Real git |
|---|---|---|
| `tests/next/test_prompt_builder_review_base.py` | 8 | yes |
| `tests/next/test_prompt_builder_unit.py` | 34 | some |
| `tests/runtime/test_wp_prompt_task_placement.py` | 11 | no |
| `tests/specify_cli/cli/commands/agent/test_workflow_cores.py` (out-of-matrix, nightly) | 33 | no |
| `tests/agent/test_workflow_mixed_dependency_review_context.py` | 2 | yes |
| `tests/integration/review/test_canonical_review_diff_refs.py` | 1 | yes |
| `tests/integration/test_owned_lifecycle_acceptance_review.py` | 7 | yes |
| `tests/characterization/test_trio_pure_cores.py` | 60 | no |

No test drives a real `single_branch` (`lane-planning`) workspace through either
builder. That is the red-first acceptance seam.

## 9. Sizes, complexity, churn

- **Lines.**
  - `prompt_builder.py` 748; `workflow.py` 2655; `workflow_executor.py` 2650.
  - `wp_attribution.py` 1259; `wp_window.py` 116; `lane_head.py` 300.
  - `read_surface.py` 780; `requirement_mapping/__init__.py` 641.
- **C901.** `build_review_prompt_lines` 7, `_review_command_lines` 5,
  `_review_context_line` 5, `review` 10. `workflow.implement` is 18 already and is
  untouched.
- **90-day churn.** `prompt_builder.py` 25 commits (about 19 fixes);
  `workflow.py` / `workflow_executor.py` 48 each. These are hot files, so keep
  edits there minimal: call a helper and render a block.

## 10. Recommended design (subject to operator rulings)

1. **Tidy-first enabler.** Move the pure FR-021 opener selector (`window_opener_events`,
   `window_open_of`, `WindowOpen`/`WindowGap`/reason) from `consolidation/wp_attribution.py`
   to `status/wp_window.py`. Re-export it from `wp_attribution`, preserving behaviour.
   The consolidation tests stay green unchanged.
2. **One range function.** `resolve_wp_review_range(...) -> WpReviewRange`, in
   `specify_cli/review/` (runtime-importable).
   - It reads events through `resolve_status_read`, and binds the ancestry predicates
     through `kernel.git`.
   - **Base:** the recorded FR-021 window open, then the commit that introduced the
     opener event, then the `wp-base` ref.
   - **Tip:** the newest `for_review` `lane_head`, then the commit that introduced that
     `for_review` event.
   - Each resolution carries a typed `source` and a named `gap` reason. If no base
     resolves, the range is UNAVAILABLE with that reason, never empty and never
     unbounded.
3. **Diff rendering.** Scope the range with the WP's owned_files pathspecs.
   - Implementation commits come from `base..tip`, minus status-only bookkeeping
     commits.
   - The stat comes from `kernel.git.listing.numstat_entries`.
   - Patch text comes from a new `kernel.git` helper.
   - The inline diff is capped, with an explicit truncation marker and the exact
     command for the remainder.
4. **Requirement text.** `requirement_mapping.resolve_requirement_text(spec_text, ids)`,
   built on `_declaration_occurrences`. An unresolved ID is flagged, and a
   cross-Mission ID is labelled.
5. **Both builders render from (2)–(4).** The REVIEW COMMANDS of path B and the GIT
   REVIEW CONTEXT of path A print the same `base..tip`, and
   `ReviewPromptMetadata.base_ref` agrees with them.

## 11. Open design questions (escalated to the operator)

See the Mission's decision log. The questions are:

- Q1: the inline-diff size policy.
- Q2: the range tip, recorded `for_review` stamp vs live tip.
- Q3: commit-to-target anchors, event-commit fallback vs a new writer stamp.
- Q4: pathspec scope on lane topologies.
- Q5: whether to move the FR-021 selector into `status/`.
- Q6: an empty fold set.
