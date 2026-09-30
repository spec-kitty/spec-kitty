# Contract: docs-lint command line

Both scripts are run from the repository root as modules. Each exposes `main(argv: list[str] | None = None) -> int`.

## `python -m scripts.docs.check_spelling`

| Option | Default | Meaning |
|---|---|---|
| `--repo-root PATH` | the repository containing the script | root that the scope roots and `pyproject.toml` resolve against (tests pass a fixture tree) |
| `--changelog PATH` | `docs/changelog/CHANGELOG.md` | changelog whose Unreleased section gets the US pass; a relative path resolves against `--repo-root` |
| `--pass {typo,us,unreleased,all}` | `all` | run one pass or all three |

- **Exit codes**: `0` means no findings; `1` means one or more findings. `2` means any of these:
  - a usage error;
  - codespell is missing;
  - `pyproject.toml` has no `[tool.codespell]` table;
  - the changelog is unreadable;
  - a selected `typo` or `us` pass scanned 0 files;
  - the Unreleased scratch file matches a configured skip glob.

  An `unreleased` pass on a changelog with no Unreleased section scans 0 lines and exits 0 (pre-PR fold F3).
- **Output**: one line per finding, `path:line: [typo|us-spelling] word — fix: <suggestion>`, then the summary `N finding(s) across M file(s); scanned: typo=K file(s), us=K file(s), unreleased=L line(s)` (only the passes that ran). A pass that enumerates zero files never invokes codespell, because codespell with no path arguments scans `.`. Paths are repo-relative, and Unreleased findings use real changelog line numbers.

## `python -m scripts.docs.check_changelog_style`

| Option | Default | Meaning |
|---|---|---|
| `--changelog PATH` | `docs/changelog/CHANGELOG.md` | file to check; a relative path resolves against the repository root, not the current directory (pre-PR fold F7) |

- **Exit codes**: `0` means no error findings (warnings may be printed); `1` means one or more error findings; `2` means a usage error or an unreadable changelog.
- **Rules added by the pre-PR folds**: `bullet-marker` rejects column-0 `* `/`+ ` bullets (F4). Prose between a `###`/`####` heading and its first bullet gets the banned-token checks (F4). The shared extractor recognizes `~~~` fences and spaceless `##[Unreleased]` headings (F5).
- **No Unreleased section**: exit `0`, with the line `no [Unreleased] section found; nothing to check`.
- **Output**: one line per finding, `path:line: [rule] [<section>] <headline excerpt> — <fix>`. Warnings are prefixed `warning:`. A summary line follows.

## Make

`make docs-lint` runs both commands through `uv run --frozen` and stops at the first non-zero exit. It never runs pytest.

## CI

The always-on `docs-lint` job in `.github/workflows/ci-router.yml` runs the same two commands with no exit-code masking. It is listed in router-gate `needs`.
