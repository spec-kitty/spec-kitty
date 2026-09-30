---
title: Local Overrides for Cross-Package Development
description: Dev-only patterns for editable cross-package installs of spec-kitty-events and -tracker, and why committing [tool.uv.sources] path overrides in pyproject.toml is prohibited.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
---
# Local Overrides for Cross-Package Development

When working across `spec-kitty-cli`, `spec-kitty-events`, and/or
`spec-kitty-tracker`, you may need editable installs of the sibling
packages so that local changes to one are picked up by the other without
publishing intermediate releases.

> **Do NOT commit `[tool.uv.sources]` editable / path entries for these
> packages in `pyproject.toml`.** That committed override is exactly what
> got [PR #779](https://github.com/spec-kitty/spec-kitty/pull/779)
> rejected: it masked a missing dependency in CI's clean-install
> environment and re-imposed cross-package release lockstep.

Instead, use one of the following dev-only patterns.

## Pattern A — ad-hoc editable installs

In your local `spec-kitty-cli` checkout's venv:

```bash
pip install -e ../spec-kitty-events
pip install -e ../spec-kitty-tracker
```

The editable installs override the wheel-installed copies for the current
venv only. Nothing is committed; `git diff` is empty.

When you're done, drop the editables and reinstall from the lockfile:

```bash
pip install --force-reinstall spec-kitty-events spec-kitty-tracker
# or, with uv:
uv sync
```

## Pattern B — a personal `pyproject.local.toml`

Neither `uv` nor `hatch` reads a `pyproject.local.toml`; it is only a
personal, gitignored scratch file where you keep your override set so you
don't retype it. Apply it through Pattern A (or copy the entries into a
throwaway, uncommitted edit of `pyproject.toml` and revert before you commit).

```toml
# pyproject.local.toml — gitignored
[tool.uv.sources]
spec-kitty-events = { path = "../spec-kitty-events", editable = true }
spec-kitty-tracker = { path = "../spec-kitty-tracker", editable = true }
```

`.gitignore` already excludes `pyproject.local.toml`, so the file itself can
never be committed.

## CI guard

`tests/architectural/test_pyproject_shape.py` fails CI when the
**committed** `pyproject.toml` contains an editable / path source for
`spec-kitty-events`, `spec-kitty-tracker`, or `spec-kitty-runtime`. The
guard exists specifically to prevent re-introducing the pattern that
contributed to PR #779's failure.

## Verification before pushing

```bash
# Confirm your changes don't add committed overrides:
git diff pyproject.toml | grep -E "spec-kitty-(events|tracker|runtime).*path"
# Expected: empty
```

If the grep finds a match, you committed a path source by accident. Move
it to your `pyproject.local.toml` (Pattern B) or drop it and use Pattern A
for the duration of your work.
