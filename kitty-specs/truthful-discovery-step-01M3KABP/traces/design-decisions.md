# Design decisions

- 2026-09-28: No software-dev research scaffold; the plan step stays the owner of research.md/data-model.md (single authority). Discovery prompt becomes an authoring instruction.
- 2026-09-28: `research.py` moves to the canonical `runtime.resolver.resolve_template`; legacy `resolve_template_path` retired. Accepts the tier change (drops `.kittify/missions/<type>/templates/` and root `templates/`), documented in the changelog.
- 2026-09-28: #5233: the shim and its patches are removed in one commit, because `patch()` fails on a missing attribute.
