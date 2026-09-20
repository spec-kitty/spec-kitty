# Tracer — Tooling Friction (terminus-safety-invariant)

Seeded at planning 2026-09-19.

- `spec-commit` silently commits only recognized spec artifacts (spec.md/meta.json/checklists) — decision records + status.events.jsonl needed a plain `git commit` on the feature branch.
- `issue-verdict` (issue-matrix) routes writes to the COORDINATION branch (write_target(ISSUE_MATRIX)), not the working tree — the matrix isn't visible in the working checkout.
- `.kittify/charter/synthesis-manifest.yaml` gets a version-string bump (3.2.6→4.0.0rc3) + manifest_hash recompute on CLI invocations (installed-version drift vs committed seed); discarded to keep planning commits clean — pre-existing environmental drift, not mission content.
- Installed CLI reports `4.0.0rc3` in command headers while `pyproject.toml` says `4.0.0rc4` — minor version-string skew.
- Doctrine subagent (DIRECTIVE_052) friction: worktree ≠ install (built_in_root/editable spec-kitty resolve to primary); regenerate-graph + activate needed PYTHONPATH+SPEC_KITTY_PACKS_ROOT forced onto the worktree; `test_regenerate_graph_check_is_byte_identical` false-reds via the stale installed binary (resolves once branch is installed / in CI). `charter context` / `doctor doctrine --json` are NOT valid activation-verification surfaces — use `charter_activated_urns`.

## Append log (implementation)
- (WPs append here)

- CHANGELOG.md is a symlink → docs/changelog/CHANGELOG.md; not in any code WP's owned_files, so the [Unreleased] entry is orchestrator-owned at closeout (not per-WP).
- ruff caught a 3rd latent `terminal_lanes` f-string reference in doctor.py that a manual grep for the symbol name missed — trust the linter for rename completeness.

- WP02: pre-existing baseline red `tests/migration/test_birth_cutover.py::test_birth_cutover_reconciles_at_merge_no_manual_backfill[coord]` (subtasks mismatch / deterministic seed) — confirmed red on branch pre-WP02 via stash; MUST verify vs skupstream/main at closeout before classifying pre-existing vs mission-introduced (charter Pre-existing-Failure rule).
- WP02: `git revert <sha>..HEAD` cannot cross a lane-consolidation merge commit without -m → transactional rollback must be scoped to a span with no merge commit (pre-mutation checkpoint before `_phase_merge_lanes` only).
- ruff format 'drift' on merge/executor.py + policy/merge_gates.py is the local ruff 0.15.14-vs-pinned-0.15.12 skew (same on base via stash); verify at closeout with pinned whole-repo `ruff format --check .`.

- WP03: the FR-011 'queryable event' for the unreachable-fallback was NOT added — reusing MergeState.pending_coord_reconcile would corrupt the #2367-B coord-strand doctor surface (_parse_reconcile_marker expects specific keys); a real event needs a new merge/state.py field or status notices surface (outside ordering.py owned_files). Merge-summary line used instead (FR-011 'or' satisfied). Optional minor follow-up.

- WP04: `spec-kitty charter context --action implement` fails with 'Global asset input changed: ~/.kittify/cache/slash_commands-assets.json' (the multi-install version-mosaic footgun) — subagents fall back to `agent profile show` + ad-hoc-profile-load. Consider `rm` the cache stamp+lock if it becomes obstructive; pre-existing env, not mission-caused.

- WP05: a genuinely-completing skip-lanes mission must target a NON-protected branch (main/master are protected; a flat/legacy-topology mission can't redirect bookkeeping there → PROTECTED_BRANCH_REFUSED). CliRunner needs monkeypatch.chdir(repo) — some resolution seams fall back to process CWD and otherwise resolve against the real dev checkout. merge.py has pre-existing whole-file ruff-format drift (blank-line-before-comment across import blocks), confirmed via stash — resolve at closeout with pinned ruff, not per-WP.

- CLOSEOUT BASELINE-RED LEDGER (verify vs skupstream/main before classifying):
  1. tests/migration/test_birth_cutover.py::...[coord] — subtasks-mismatch/seed (WP02).
  2. tests/charter/test_org_cascade_chain.py (2 cases) — stashed-out identical on branch (WP06); verify on main.
  3. **MISSION-INTRODUCED (must fix): tests/.../test_merge_cli_golden.py::test_help_pins_one_line_help_and_every_visible_flag** — WP05's --skip-lanes/--no-lanes flags outpace the golden fixture (behavior-change golden-shard blindspot). Update the golden at closeout.
- WP06 regen used SPEC_KITTY_ENABLE_SAAS_SYNC=1 to bypass the daemon boundary for `python -m specify_cli.completion --regenerate`.

- Pre-PR aggregate squad caught a HIGH cross-WP defect (WP02 coord-rollback × WP03 primary-tree bake) that BOTH per-WP reviews missed because the rollback-coherence test MOCKED the bake out — the composition seam was untested. Lesson: a behavior-change that moves a commit onto a DIFFERENT partition (primary vs coord) silently defeats a same-partition rollback guard; the aggregate/integration review is the layer that catches it.
