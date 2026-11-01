# REASONS Canvas — Plugin bundle native target selection

> Mission: `plugin-bundle-native-target-selection-01M6BV0N`
> Source: [#6273](https://github.com/spec-kitty/spec-kitty/issues/6273). [spec.md](spec.md) is authoritative; this canvas is non-governing and advisory.

## Requirements

- **Problem.** A project that configures Claude and Codex together never stages its plugin bundles:
  the Claude bundle maps `.codex/agents/<id>.toml` onto `agents/<id>.md`, collides with the Claude
  Markdown rendering, and the shared-member guard refuses the batch. `--fix` then exits 0 and prints
  nothing about the failure.
- **Decision.** A bundle target accepts only the agent renderings native to its harness family
  (Claude ← `claude`; Copilot/VS Code ← `copilot`/`vscode`), with the other Markdown family as a
  lower-priority fallback and non-Markdown renderings never accepted. The conflict guard stays for
  genuine same-family disagreements.
- **Diagnostics.** A failed repair names the failed surfaces and the cause, and `--fix` exits 1; a
  staged bundle that no longer matches its prepared batch keeps the underlying cause in its finding.
- **Acceptance.** FR-001 … FR-005, SC-001 … SC-004; the issue reproduction is the primary fixture,
  with the pre-fix `missing == 3` state captured as the negative control.

## Entities

- **Distribution target** — a bundle package identity (`claude_code_plugin`, `copilot_skill_package`,
  `vscode_extension`). Owns its layout, manifest path and accepted renderings.
- **Bundle member** — one in-bundle relative path with exactly one accepted byte sequence.
- **Agent-profile rendering** — a tool-native projection of one canonical profile; `.md`, `.agent.md`
  and `.toml` are different renderings, not interchangeable.
- **Repair outcome** — `repaired`/`skipped`/`failed` surface ids plus the findings that explain a
  failure; the operator-visible signal that a repair was attempted.

## Approach

- Prefer target-native sources per bundle member, keep same-family fallback for single-harness
  projects, and leave hooks/native-config aggregation untouched.
- Carry the provider's own diagnostics through the repair service rather than synthesising a new
  message in the CLI.

## Structure

- `src/specify_cli/tool_surface/bundles/projection.py` — entry selection and member merging.
- `src/specify_cli/tool_surface/bundles/{claude,copilot,vscode}.py` — per-target accepted families.
- `src/specify_cli/tool_surface/providers/plugin_bundle.py` — probe cause, repair findings.
- `src/specify_cli/tool_surface/repair.py` and `src/specify_cli/cli/commands/_command_surface_doctor.py`
  — repair reporting and exit code.

## Operations

- Research → specify → plan → tasks → red-first implement/review → accept → local consolidation →
  aggregate review → changelog → draft PR → CI green → ready for review. The operator merges.
