# Tooling friction

Tooling touched: `spec-kitty next` (discovery step), `spec-kitty research`, mission-step prompt rendering, `finalize-tasks --validate-only`.

- 2026-09-28: `python3 -m pip install -e .` on the cloud image failed twice uninstalling Debian-owned PyJWT and cryptography; `--ignore-installed` on each fixed it.
- 2026-09-28: `spec-kitty charter context --action specify` prints many `CharterCatalogMissWarning` lines for Java/TypeScript artifacts scope-filtered out of a Python project; the noise buries the context.
- 2026-09-28: `spec-kitty spec-commit` left `status.events.jsonl` and `decisions/index.json` uncommitted after committing the spec and decision record.
