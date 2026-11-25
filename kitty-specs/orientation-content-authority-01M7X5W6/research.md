# Research: One authority for committed orientation content

## Reproduction (verified on ba1aa571, unchanged on origin/main 996f5d6a)

- S1: `init --ai claude` in `dirname-differs`, set `project.slug: local-agent-bus`. `upgrade --project --yes` exits 0 and leaves `project: dirname-differs`; `doctor tool-surfaces --fix` reports repairs but the block is unchanged; `session-start` prints `local-agent-bus`.
- S3: stamp the block `v4.0.0rc8` with the right slug; `upgrade --project --yes` auto-commits `project: dirname-differs`.
- S4: `doctor tool-surfaces --fix` writes the directory name through the same provider path.

## Findings

- Decision: a single authority module in `specify_cli.session_presence`.
  Rationale: three content builders (`manager._build_content`, `local_presence_content(project_root.name)`, `update(dry_run)`) and three staleness rules (provider probe version-only, writer `prepare` version+invocation shortcut, rc39 full equality) disagree.
  Alternatives: pass projected content from upgrade assessment (fixes only upgrade, not doctor or probe); a new migration (rejected by ruling 3; a one-shot ledger entry is not convergence).
- Decision: committed health is "healthy"; live health only in the hook.
  Rationale: ruling 1; removes the #2265 churn source (migrations wrote live health via `_build_content`).
- Decision: slug fallback `project.slug` → git remote name → "unknown".
  Rationale: ruling 2. `derive_project_slug` itself falls back to the directory name, so its remote part is extracted as `slug_from_git_remote`.
- Decision: the writer `prepare` shortcut becomes full block equality.
  Rationale: otherwise correct content never replaces a wrong slug at the current version (newly found gate (f)).
- Decision: hand-edited blocks keep preserve semantics; drift for a non-canonical block is version-only, as before.

## Blast radius (tests to run)

tests/specify_cli/session_presence/, tests/specify_cli/tool_surface/providers/test_session_presence*.py, tests/specify_cli/tool_surface/test_plan.py, tests/specify_cli/tool_surface/test_surface_repair_wiring.py, tests/specify_cli/tool_surface/integration/test_projection_honesty_e2e.py, tests/specify_cli/upgrade/migrations/test_m_3_2_0rc39_*, test_m_session_presence_*, test_session_presence_upgrade_smoke.py, tests/specify_cli/cli/commands/test_session_start.py, tests/upgrade/test_upgrade_assessment_boundary.py, tests/specify_cli/identity/, architectural: test_dead_symbols (allowlist), test_layer_rules.

## Supply chain

No dependency added, upgraded or removed; DIRECTIVE_051 not triggered.
