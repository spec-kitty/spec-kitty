# Quickstart: docs lint

Seed content for the contributor guidance in WP05. The published home is `docs/development/how-to/review-gates.md`.

```bash
uv sync --frozen            # installs the pinned codespell from the dev group
make docs-lint              # spelling (typo + US) and the changelog Unreleased guard
# or individually:
uv run --frozen python -m scripts.docs.check_spelling
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen python -m scripts.docs.check_changelog_style
```

- **Legitimate word flagged as a typo**: add it, lowercase, to `ignore-words-list` in `[tool.codespell]` in `pyproject.toml`.
- **Quoted literal flagged by the US check** (a CLI message, a status value, a config key or identifier): put it in a code span, or in a fenced block if it is a multi-line example.
- **Do not run bare `codespell`**: without the script's scope roots it scans the whole repository, including frozen trees.
- **Changelog guard failure**: the message names the entry and the fix. For example, move `(#1234)` outside the bold headline, add a `**Before:**` sentence, or replace `spec-kitty merge` with `spec-kitty consolidate`.
