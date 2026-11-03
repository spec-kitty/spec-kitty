# REASONS Canvas — ASCII-by-construction mission scaffolding

> Mission: ascii-mission-scaffold-01M6GRG6
> Generated: 2026-11-03
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: core scaffolds `kitty-specs/<slug>/tasks/README.md` from a constant that contains U+2013, so `spec-kitty validate-encoding` refuses a freshly created mission before any content is authored (reproduced: 2 files Needs Fix at birth); the four template files behind `spec.md`/`plan.md`/`tasks.md`/WP prompts are pack-owned and equally non-ASCII ([research.md](research.md) D-1, D-2).
- Acceptance: [spec.md](spec.md) FR-001 through FR-007, NFR-001/002, C-001 through C-004, SC-001 through SC-007. The core half is fixed by construction; the pack half is filed and cited.
- Definition of done: red-first test proving the current constant fails, ASCII template text, one renderer for both `tasks/README.md` emitters, a pin with a self-mutation case, changelog fragment, independent review, draft PR flipped to ready for review. The implementer never merges.

## Entities
- `TASKS_README_TEMPLATE` — the single core-owned scaffold text; `render_tasks_readme_content(planning_branch)` is its only renderer.
- `setup_feature_directory()` — the legacy second emitter in `core/worktree.py`, which today inlines its own ~55-line copy of the same document.
- `detect_problematic_characters` / `PROBLEMATIC_CHARS` (`specify_cli.text_sanitization`) — the gate's authority for "problematic"; the pin reuses it rather than restating the character list (C-003).
- Not an entity here: the pack templates. They are `spec-kitty-open-packs` content, pinned by `packs/built-in.source.yaml`, and out of this repository's edit authority (C-001).

## Approach
- Fix the source text, never the write. No `sanitize_markdown_text` call is added to any create/scaffold path: a write-boundary sanitizer cannot tell scaffold text from authored text and would rewrite a maintainer's prose (the #6579 precedent, NFR-001, FR-004).
- Converge the two `tasks/README.md` emitters onto `render_tasks_readme_content` so one literal owns the text and one pin covers both (FR-006, DIRECTIVE_044). The legacy inline copy is ASCII by luck, which is exactly why pinning the constant alone would be vacuous.
- Align the constant's `history:` example to the pack template's `at:`/`actor:` shape while the block is being edited — the pack is the canonical source for WP structure, and the example is copied by agents (FR-007).
- Tradeoff: converge rather than pin-two-texts. Pinning two divergent texts preserves a known drift and a second authority; converging costs one content change in a legacy, test-only path.

## Structure
- Production surface: `src/specify_cli/core/mission_creation_scaffold.py` (`TASKS_README_TEMPLATE`, `render_tasks_readme_content`), `src/specify_cli/core/worktree.py` (`setup_feature_directory`).
- Tests: a new pin module under `tests/core/` for the rendered text, byte range, gate-detector emptiness and the self-mutation case; `tests/git_ops/test_worktree.py` for the converged emitter.
- Changelog fragment `docs/changelog/unreleased/<pr>.fixed.md`.
- One work package; implementer owns product and tests, the reviewer is independent, the planner owns reasoning and sequencing only.

## Operations
1. Opening campsite check of the two touched surfaces; record whether any enabler is needed (expected: none, the constant and the emitter are small and isolated).
2. Write the failing-first pin and the convergence test through pre-existing entry points (`render_tasks_readme_content`, `setup_feature_directory`); run and record RED before the production edit.
3. Replace the glyphs in the constant and align the `history:` example; point `setup_feature_directory` at the renderer and delete the inline copy.
4. Re-run the pin and the touched test files; record commands and counts, red to green.
5. Changelog fragment; draft PR; follow CI to green; flip to ready for review. No merge, no auto-merge, no push to `main`.

## Norms
- Canonical sources only: the pack template is the authority for WP structure, the gate's own detector is the authority for "problematic" (C-003), the resolver/renderer seam is the authority for where scaffold text lives.
- Explicit mission handle on every spec-kitty command; targeted staging only; conventional commits naming the issue.
- Python typing and lint standards; no new dependencies; no version numbers in scope.
- New/changed-line coverage >= 90 % (diff-cover gate); independent review of the aggregate diff before the PR flips.

## Safeguards
- Authored non-ASCII survives verbatim: the round-trip test in FR-004 asserts it, so a future "helpful" sanitizer is caught by the suite.
- No pack edit and no pin bump in this PR (C-001, C-002): `packs/built-in/` is gitignored, digest-pinned and regenerated, and moving the pin is an operator decision under the 2026-11-01T09:35Z ruling.
- Existing missions keep their glyphs; `validate-encoding --fix` still repairs them. No history migration here.
- No full heavy-suite runs locally; CI owns the full sweep. No credentials or machine-local paths in commits.
- All code work on the mission lane worktree; planning artifacts on `issue-6877-ascii-mission-scaffold`; never push `main`.

## Deviations (append-only)

(none yet)
