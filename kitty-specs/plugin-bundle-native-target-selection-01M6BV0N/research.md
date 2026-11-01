# Discovery — plugin bundle native target selection (#6273)

## Reproduction (current `main`, `287a226cfe`)

In a fresh git repo: `spec-kitty init --ai claude,codex,copilot --non-interactive`, then
`spec-kitty doctor tool-surfaces --fix`. Exit 0, no `Repaired:` line, `dist/` never created, audit
reports `missing: 3` (`claude_code_plugin`, `copilot_skill_package`, `vscode_extension`
`plugin.json`). Control `--ai claude,copilot` stages everything. Reproduced on the installed
`spec-kitty-cli 4.0.0rc8` build in this VM.

Direct call of `PluginBundleProvider.assess(selected_targets=("claude_code_plugin",))` returns
`complete=False` with `Conflicting prepared bundle member: agents/analyst-annie.md`.

## Root cause (evidence)

- `PluginBundleProvider._plans_for_projection` builds per-tool plans for every configured tool
  (`build_plans_for_bundles(root, tool_keys=agents)`), and `assess` passes those plans unchanged to
  `projector.entries(plans, root)`.
- `bundle_entries_for_plans` (`bundles/projection.py`) maps **every** plan instance into the target's
  layout and merges entries on `bundle_relative_path`. For `AGENT_PROFILE` it applies the target's
  `agent_filename` to any source stem, so `.codex/agents/analyst-annie.toml` becomes
  `agents/analyst-annie.md` in the Claude bundle and merges with `.claude/agents/analyst-annie.md`.
- The merged entry carries both sources; `supplied_entries` then collects both prepared profile
  projections as candidates and raises `Conflicting prepared bundle member` when their bytes differ
  (`projection.py:535`). Codex renders TOML (`name = "Analyst Annie"`), so they always differ.
- Claude and Copilot renderers share `_render_markdown_agent`, so the Claude `.md` and Copilot
  `.agent.md` bodies are byte-identical; that is why `--ai claude,copilot` stages today.
- The repair path (`PluginBundleProvider.repair`) returns `findings_after` on failure, but
  `SurfaceRepairService._apply` copies only `repaired/skipped/failed` and the returned
  `RepairResult` has no findings; `_print_tool_surface_human` prints only `repaired`; and the command
  exits on `report.ok`, where an absent OPTIONAL manifest is not an error. So the conflict cause is
  invisible and the process exits 0.
- `PluginBundleProvider.probe` returns bare `STATE_MISSING` when the manifest is absent, and the
  generic "Selected staged bundle has missing, drifted, or unavailable members." finding when it is
  present but no longer matches — the prepared-batch diagnostics are discarded.

## Decisions

1. **Target-native selection, not a weakened guard.** Each distribution target accepts only the
   agent-profile renderings native to its own harness family: Claude bundle ← `claude`; Copilot and
   VS Code bundles ← `copilot` / `vscode`. The other Markdown family is a lower-priority fallback so
   single-harness projects keep staging; non-Markdown families (Codex `.toml`) are never renamed into
   a Markdown member. The shared-member conflict guard stays for genuine same-family disagreements
   (two accepted sources, different bytes → fail closed, nothing written).
2. **Optional policy unchanged.** A missing plugin manifest stays a non-error for `ok`; only a failed
   `--fix` changes the exit code (C-002, pinned by
   `tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py`).
3. **Repair reporting** carries the provider's `findings_after` through `SurfaceRepairService` into
   `RepairResult`, prints failed surface ids with their reasons in the human renderer, and makes
   `doctor tool-surfaces --fix` exit 1 when a repair failed.
4. **Probe keeps the cause**: a staged-bundle mismatch finding carries the assessment diagnostics
   instead of only the generic sentence.

## Supersession check

- `git log -S "Conflicting prepared bundle member"` → only `5880e6501c` (WP08 introduction) and
  `3aaf618fd0` (original tool-surface contract). No later fix.
- Changelog mentions one earlier plugin-bundle repair defect, #5843 (unsupported native-config
  sentinel and CWD), which is a different path and already closed.
- Issue comments confirm the defect persists on `5068301dd`; no ADR governs bundle member selection.
- Triage label `triage:needs-revision` is satisfied by decision 1 above and by the spec's pinned
  selection contract (C-001).

## Open questions

- None blocking. Whether Codex should ever ship its own plugin bundle is out of scope (the Codex
  builder is separate and does not include agents).
