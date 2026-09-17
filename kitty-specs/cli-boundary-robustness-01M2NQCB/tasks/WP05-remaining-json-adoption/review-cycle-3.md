---
affected_files: []
cycle_number: 3
mission_slug: cli-boundary-robustness-01M2NQCB
reproduction_command:
reviewed_at: '2026-09-16T22:05:56Z'
reviewer_agent: user
wp_id: WP05
---

# WP05 review feedback — cycle 3 reopening

**Blocking regression — strict package mypy lost `Path` narrowing in `archive.py`.**

The downstream terminal gate found three WP05-introduced type errors in `src/specify_cli/cli/commands/archive.py` at the current lines 74, 85, and 127. `locate_project_root()` returns `Path | None`, but WP05 replaced the direct `raise typer.Exit(...)` branches with `_exit_error(...)` annotated as returning `None`. Mypy therefore cannot prove that execution terminates when `root is None`, and the subsequent calls pass `Path | None` where `Path` is required. These errors are absent on the lane-b dependency base, so they are a WP05 delta rather than baseline debt.

Fix this within WP05 ownership while preserving the already-approved runtime behavior, JSON envelopes, human output, and exit codes. Make the non-returning control-flow contract explicit (for example, an accurate `NoReturn` annotation on the helper) rather than adding casts or ignores that conceal the invariant.

Before resubmission, retain evidence that:

- strict package mypy reports no WP05-introduced errors and specifically clears all three `archive.py` sites;
- the 22-test WP05 boundary suite remains green;
- archive JSON/human transport and exit-fidelity tests remain green;
- Ruff, repository format, and diff checks remain green;
- the diff contains no blanket type suppression and no unrelated refactor.

## Reopening verdict

Approval is revoked because the terminal quality gate contradicts WP05's NFR-006 completion claim. Return WP05 to `planned`; source changes remain with the implementer.
