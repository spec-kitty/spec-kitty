# Contracts — declaration-first-repo-root-resolution (#6142, Increment 1)

This mission defines **no external/interface contracts**. It adds one in-tree,
command-entry-layer resolution entry (`specify_cli.core.command_target.resolve_command_repo_target`)
consumed only within the `specify_cli` package; it changes no CLI wire surface, no
`--json` envelope, no hosted route, and no cross-package public API. The one user-visible
behaviour change (record-analysis's target branch follows the Mission's stored declaration
rather than the ambient checked-out branch) is recorded in `docs/changelog/CHANGELOG.md`.

The entry's internal contract (inputs/outputs, provenance, fail-closed behaviour) is pinned
by `tests/specify_cli/core/test_command_target.py`.
