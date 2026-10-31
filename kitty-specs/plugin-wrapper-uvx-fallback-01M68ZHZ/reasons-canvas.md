# REASONS Canvas — Plugin wrapper uvx fallback

> Mission: plugin-wrapper-uvx-fallback-01M68ZHZ
> Generated: 2026-10-31
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: the generated Claude bundle bootstrap cannot run the CLI on a machine without `spec-kitty` installed, because it asks `uvx` for an executable (`spec-kitty-cli`) that the distribution does not ship ([research.md](research.md), D-01).
- Acceptance: [spec.md](spec.md), FR-001 through FR-007 and SC-001 through SC-005; both wrappers, the series gate, the unpublished-pin retry, the corrected remedy, docs and changelog.
- Definition of done: failing-first test through the rendered script, scoped template fix, targeted green evidence, one independent review round, changelog + how-to updated, PR only. No merge by an implementation agent.

## Entities
- Generated wrapper (POSIX bash, Windows CMD), pinned version spec, supported series — defined once in [spec.md](spec.md#key-entities). "Wrapper" never means the Python package wrapper modules.
- No new entity or module: the two templates and one pure helper already exist in `src/specify_cli/tool_surface/bundles/claude_wrapper.py`.

## Approach
- Edit the two existing templates: `uvx --from "<requirement>" spec-kitty …`, one series helper, PATH gate on the series, series-range retry.
- Rejected: a `spec-kitty-cli` console-script alias (publishes a second CLI name for a P2 wrapper fix), and an unconditional `uvx spec-kitty-cli` latest fallback (runs an unsupported CLI silently). See [research.md](research.md), D-02/D-03.
- Tradeoff: one extra `--version` probe on the installed-CLI path in exchange for version coherence; no uvx resolution on that path.

## Structure
- Production surface: `src/specify_cli/tool_surface/bundles/claude_wrapper.py` only. Callers `claude.py:244-247` and `projection.py:943-945` stay unchanged.
- Tests: `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py`; hermetic PATH stubs, no network, no reliance on the developer's `uvx`.
- Docs: `docs/guides/how-to/installation/install-claude-code-plugin.md`, `docs/changelog/CHANGELOG.md`.
- One WP; implementer owns product/tests/docs, reviewer is independent.

## Operations
1. Campsite check the touched module and its tests; record no scope widen.
2. Write failing-first tests through the rendered script (stub `uvx`, stub `spec-kitty`), run and commit RED before touching the templates.
3. Apply the bounded template + helper change; verify each half independently (fallback form, series gate, retry, remedy text).
4. Run the bundle test module set, ruff/mypy on the changed module, then the docs freshness check for the touched docs surface.
5. Open the PR as a draft; the operator merges.

## Norms
- Canonical pack/charter sources; explicit `--mission` handle; targeted staging only.
- Python typing/lint standards, no broad suppressions, no new dependencies.
- New-code coverage on changed lines meets the diff-cover gate; reviewer verifies the actual diff and live targeted evidence, not a summary.
- Do not claim planning evidence as implementation evidence.

## Safeguards
- No gate, marker or test selection may be relaxed to land this (spec C-003).
- Bundle layout and manifests untouched (spec C-001); #6479 owns those.
- The `.cmd` wrapper keeps `EXIT /B %ERRORLEVEL%` outside parenthesized blocks (#623) and `%*` forwarding; the POSIX wrapper keeps `set -euo pipefail`.
- No personal data or machine-local paths in commits; no `main` push, no merge, no auto-merge.
- No full heavy suite in-mission.

## Deviations (append-only)
