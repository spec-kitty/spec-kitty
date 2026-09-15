---
title: Contributing to Spec Kitty
description: The full contributor guide for Spec Kitty — developer setup, running tests, submitting pull requests, AI-assistance disclosure, and the release process.
doc_status: active
updated: '2026-09-14'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/guides/index.md
- docs/development/how-to/review-gates.md
- docs/development/how-to/pr-landing.md
- docs/development/how-to/manage-issue-tracker.md
- docs/development/how-to/create-a-doctrine-artifact.md
- docs/development/testing/testing-parallel.md
- docs/guides/how-to/installation/diagnose-installation.md
---

# Contributing to Spec Kitty

Hi there! We're thrilled that you'd like to contribute to Spec Kitty. Contributions to this project are [released](https://help.github.com/articles/github-terms-of-service/#6-contributions-under-repository-license) to the public under the [project's open source license](../../LICENSE).

Spec Kitty is inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit). Please preserve upstream attribution when referencing historical work or documentation.

Please note that this project is released with a [Contributor Code of Conduct](../../CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## Ways to contribute (no code required)

You don't need to write code to help shape Spec Kitty. **Ideas, use-cases, and objections are genuinely wanted** — especially on design decisions still in flight.

- **Look for the [`feedback-welcome`](https://github.com/Priivacy-ai/spec-kitty/labels/feedback-welcome) label.** Issues carrying it are open for community input; many contain an **Open decision** block calling out exactly where we'd like your perspective. Comment freely — a rough thought is more useful than silence.
- **Filing something new?** Use the **💡 Idea / brainstorm / feedback** issue template (it auto-applies `feedback-welcome`), or the bug / enhancement templates for concrete reports. A partial sketch is fine — a maintainer will triage it and, if it's actionable, turn it into a tracked mission.
- **No pressure to formalize.** You don't have to write a full proposal; tell us the problem you hit or the outcome you want, and we'll take it from there.

Well-scoped feedback often becomes the seed of a mission, so this is one of the highest-leverage ways to contribute.

## Developer Setup

After cloning, bootstrap your environment:

```bash
uv sync --frozen --all-extras
make dev-setup
```

`make dev-setup` syncs dependencies and installs all spec-kitty slash commands
for your configured AI agents (including `/spec-kitty.specify` and related
commands in Claude Code). Re-run after pulling changes or after any
spec-kitty template change.

Without running `make dev-setup`, planning commands like `/spec-kitty.specify`
may be absent from your AI coding agent. `make dev-setup` always repairs this —
it is idempotent, so running it multiple times is safe.

> **Windows users**: `make` requires WSL or a GNU Make equivalent.
> Alternatively, run the setup steps manually:
> ```bash
> uv sync --frozen --all-extras
> uv run spec-kitty doctor skills --fix
> ```

## Contributor Recognition

This repository uses [All Contributors](https://allcontributors.org/) to recognize project contributions beyond code.

Code contributions are synced automatically by the scheduled GitHub workflow in
`.github/workflows/all-contributors-sync.yml`, which updates `.all-contributorsrc`
and `README.md` from repository activity without requiring PR comments.

Non-code recognition remains maintainer-driven. That includes both new
contributions and retroactive backfill for earlier docs, design, bug reports,
feature requests, mentoring, or other project help that deserves recognition.

For non-code contributions or manual corrections, maintainers can still add recognition from an issue or PR comment:

```text
@all-contributors please add @github-username for doc,design,ideas,bug
```

Supported contribution types are listed in the [emoji key](https://allcontributors.org/en/emoji-key/).

## Supported AI Agents

Spec Kitty supports **13 AI coding agents**. When contributing features that affect slash commands, migrations, or templates, ensure changes apply to ALL agents:

- **Claude Code** (`.claude/commands/`)
- **GitHub Copilot** (`.github/prompts/`)
- **GitHub Codex** (`.codex/prompts/`)
- **OpenCode** (`.opencode/command/`)
- **Google Gemini** (`.gemini/commands/`)
- **LLxprt Code** (`.llxprt/commands/`)
- **Cursor** (`.cursor/commands/`)
- **Windsurf** (`.windsurf/workflows/`)
- **Qwen Code** (`.qwen/commands/`)
- **Kilocode** (`.kilocode/workflows/`)
- **Augment Code** (`.augment/commands/`)
- **Roo Cline** (`.roo/commands/`)
- **Amazon Q** (`.amazonq/prompts/`)

**For contributors**: Use the `AGENT_DIRS` constant from `src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py` when writing migrations or features that affect slash commands.

## Prerequisites for running and testing code

These are one time installations required to be able to test your changes locally as part of the pull request (PR) submission process.

1. Install [Python 3.11+](https://www.python.org/downloads/)
1. Install [uv](https://docs.astral.sh/uv/) for package management
1. Install [Git](https://git-scm.com/downloads)
1. Have an [AI coding agent available](../../README.md#which-ai-coding-agents-does-spec-kitty-support)

### Global CLI Install on macOS

Contributor tests run from a source checkout, not from a globally installed
`spec-kitty` binary. Use a global install when you want to run Spec Kitty outside
this repository or when you are explicitly testing install/update behavior.
Use one tool manager for a normal global install; installing with both can put
two `spec-kitty` binaries on your `PATH`.

To install the latest `main` branch from GitHub with `uv`:

```bash
uv tool install "spec-kitty-cli @ git+https://github.com/Priivacy-ai/spec-kitty.git@main"
uv tool update-shell
# Open a new shell if uv changed your PATH, then verify:
spec-kitty --version
```

To install the latest `main` branch from GitHub with `pipx`:

```bash
pipx install "git+https://github.com/Priivacy-ai/spec-kitty.git@main"
pipx ensurepath
# Open a new shell if pipx changed your PATH, then verify:
spec-kitty --version
```

To update an existing GitHub-based global install to the latest `main` branch,
force a reinstall through the same tool manager:

```bash
uv tool install --force --upgrade "spec-kitty-cli @ git+https://github.com/Priivacy-ai/spec-kitty.git@main"
```

```bash
pipx install --force "git+https://github.com/Priivacy-ai/spec-kitty.git@main"
```

For the latest PyPI release instead of GitHub `main`, install or upgrade by
package name:

```bash
uv tool install spec-kitty-cli
uv tool upgrade spec-kitty-cli
```

```bash
pipx install spec-kitty-cli
pipx upgrade spec-kitty-cli
```

After a new PyPI release, CDN caching can make upgrades lag briefly. If that
happens, reinstall the exact version instead:

```bash
uv tool install --force spec-kitty-cli==X.Y.Z
pipx install --force spec-kitty-cli==X.Y.Z
```

### Shared Dependencies

Spec-kitty's shared libraries are published to PyPI and resolved automatically by
`uv sync` — **no SSH access or special repository permissions are required for
local development**:

- **[spec-kitty-events](https://pypi.org/project/spec-kitty-events/)** — event system and mission-next integration.
- **[spec-kitty-tracker](https://pypi.org/project/spec-kitty-tracker/)** — tracker consumer surface.

Compatibility ranges are declared in `pyproject.toml`; exact pinned versions live
in `uv.lock`.

`spec-kitty-runtime` is no longer a dependency: the CLI's runtime surface is
internalized under `src/runtime/next/`, and its absence is enforced by
`tests/architectural/test_pyproject_shape.py`.

## Running Tests

Spec Kitty's test suite is designed to run against source code, not installed packages. This ensures tests verify the current code, not a previously installed version.

### Quick Start

```bash
# Install dependencies (one time)
uv sync

# Run all tests
pytest

# Run specific test categories
pytest tests/integration/        # Integration tests
pytest tests/unit/               # Unit tests
pytest tests/integration/test_version_isolation.py  # Isolation tests
```

To run the suite in parallel (typically ≥2× faster on a ≥4-core machine), plus
the serial marker passes and the coverage-neutrality gates, see
[Running the test suite in parallel](testing/testing-parallel.md).

### Testing Unreleased Main or a Pull Request

When you need to test the current `main` branch or a specific pull request
before it is published to PyPI, avoid replacing your normal global
`spec-kitty` install unless that is the thing you are testing.

For normal contributor work, run from a source checkout:

```bash
git clone https://github.com/Priivacy-ai/spec-kitty.git
cd spec-kitty

# Latest main:
git switch main
git pull --ff-only

# Or a specific pull request:
gh pr checkout <PR_NUMBER>

uv sync --frozen --all-extras

SPEC_KITTY_NO_UPGRADE_CHECK=1 SPEC_KITTY_NO_NAG=1 \
  .venv/bin/spec-kitty --version
```

For a one-shot smoke test without cloning or installing a persistent tool, use
`uvx --isolated`:

```bash
# Latest main:
SPEC_KITTY_NO_UPGRADE_CHECK=1 SPEC_KITTY_NO_NAG=1 \
  uvx --isolated --from "git+https://github.com/Priivacy-ai/spec-kitty.git@main" \
  spec-kitty --version

# Specific pull request:
SPEC_KITTY_NO_UPGRADE_CHECK=1 SPEC_KITTY_NO_NAG=1 \
  uvx --isolated --from "git+https://github.com/Priivacy-ai/spec-kitty.git@refs/pull/<PR_NUMBER>/head" \
  spec-kitty --version
```

For a temporary installed binary, isolate both the tool environment and the
generated executable:

```bash
tmp="$(mktemp -d)"

UV_TOOL_DIR="$tmp/tools" UV_TOOL_BIN_DIR="$tmp/bin" \
  uv tool install --force \
  "spec-kitty-cli @ git+https://github.com/Priivacy-ai/spec-kitty.git@refs/pull/<PR_NUMBER>/head"

SPEC_KITTY_NO_UPGRADE_CHECK=1 SPEC_KITTY_NO_NAG=1 \
  "$tmp/bin/spec-kitty" --version

rm -rf "$tmp"
```

If you are testing a fork branch or an exact commit, replace the URL/ref with
`git+https://github.com/<OWNER>/spec-kitty.git@<BRANCH_OR_SHA>`. Hosted
tracker and sync flows are opt-in; set `SPEC_KITTY_ENABLE_SAAS_SYNC=1` only
when the scenario explicitly exercises those flows.

### Test Isolation

Tests use several mechanisms to ensure they run against source code:

- **PYTHONPATH**: Points to `src/` directory
- **SPEC_KITTY_CLI_VERSION**: Overrides version detection
- **SPEC_KITTY_TEST_MODE**: Prevents fallback to installed package
- **isolated_env fixture**: Provides consistent environment for all tests

All integration tests use the `run_cli` fixture which handles this automatically.

### Pytest collection fails with "cannot import name 'normalize_event_id' from 'spec_kitty_events'"

**Symptom**: Pytest collection fails before any tests run with:

```
ImportError: cannot import name 'normalize_event_id' from 'spec_kitty_events' (unknown location)
```

**Cause**: Local PEP 420 namespace-package corruption from a partial `pip uninstall`. The wheel
is fine; CI is unaffected. This is **NOT** a Spec Kitty bug — it is a Python install integrity
issue.

**Diagnostic**:

```bash
python -c "import spec_kitty_events; print(repr(spec_kitty_events.__file__), spec_kitty_events.__path__)"
# Healthy:   prints a path ending in __init__.py
# Corrupt:   prints None followed by _NamespacePath([...])  ← this is the bad state
```

**Fix**:

```bash
uv sync --reinstall-package spec-kitty-events
```

Per the closing comment on [#1137](https://github.com/Priivacy-ai/spec-kitty/issues/1137), the
Spec Kitty code path deliberately does NOT fall back to importing from
`spec_kitty_events.models.*` — that would violate the FR-024 frozen public-surface architectural
contract (enforced by `tests/architectural/test_events_tracker_public_imports.py`) and mask local
environment corruption that future contributors should still encounter visibly.

---

### Troubleshooting Version Issues

If you see errors like "Version Mismatch Detected", it means you have a pip-installed version of spec-kitty-cli that doesn't match your source code version.

**Solution:**

```bash
# Uninstall any installed version
pip uninstall spec-kitty-cli -y

# Run tests again
pytest
```

This is the most common test issue and is easy to fix. The test isolation system will detect mismatches automatically.

### Troubleshooting Shared Package Import Issues

If pytest fails during collection with an error like:

```text
ImportError: cannot import name 'normalize_event_id' from 'spec_kitty_events' (unknown location)
```

check whether Python is resolving `spec_kitty_events` as a namespace package:

```bash
python - <<'PY'
import spec_kitty_events

print(repr(getattr(spec_kitty_events, "__file__", None)))
print(spec_kitty_events.__path__)
PY
```

Healthy output points at `spec_kitty_events/__init__.py`. Broken output shows
`None _NamespacePath(...)`, which means the local install is corrupted. Rebuild
the project environment with:

```bash
uv sync --reinstall-package spec-kitty-events
```

If the broken package lives in a global or Homebrew Python environment, remove
the stale `spec_kitty_events/` directory and matching `.dist-info/` metadata
from that interpreter's `site-packages`, then reinstall
`spec-kitty-events`. See
[Diagnose Installation Problems](../guides/how-to/installation/diagnose-installation.md#9-shared-package-imports-resolve-as-a-namespace-package)
for the full recovery procedure.

### How Test Isolation Works

The test infrastructure guarantees that tests always use source code:

1. **Environment Variables**: Set by `isolated_env` fixture in `tests/integration/conftest.py`
2. **Test Mode Enforcement**: `SPEC_KITTY_TEST_MODE=1` forces CLI to use source version
3. **Fail-Fast**: If fixtures are misconfigured, tests fail immediately with clear error
4. **CI Verification**: GitHub Actions verify version consistency before running tests

For more details, see `tests/README.md`.

## Submitting a pull request

>[!NOTE]
>If your pull request introduces a large change that materially impacts the work of the CLI or the rest of the repository (e.g., you're introducing new templates, arguments, or otherwise major changes), make sure that it was **discussed and agreed upon** by the project maintainers. Pull requests with large changes that did not have a prior conversation and agreement will be closed.

1. Fork and clone the repository
1. Configure and install the dependencies: `uv sync`
1. Make sure the CLI works on your machine: `uv run spec-kitty --help`
1. Create a new branch: `git checkout -b my-branch-name`
1. Make your change, add tests, and make sure everything still works
1. Test the CLI functionality with a sample project if relevant
1. Push to your fork and submit a pull request
1. Wait for your pull request to be reviewed and merged.

Here are a few things you can do that will increase the likelihood of your pull request being accepted:

- Follow the project's coding conventions.
- Write tests for new functionality.
- Update documentation (`README.md`, `spec-driven.md`) if your changes affect user-facing features.
- Keep your change as focused as possible. If there are multiple changes you would like to make that are not dependent upon each other, consider submitting them as separate pull requests.
- Write a [good commit message](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html), and keep your history clean but not over-squashed: compress your own bookkeeping commits (fixups, "wip", formatting-only) into the related work, but keep genuinely separate logical/code changes as separate commits — each commit should be one coherent, reviewable change.
- If a scoped change also carries incidental formatting-only diffs, call that out explicitly in the PR body so reviewers can distinguish behavior changes from formatting churn.
- Write a PR body that leads with **impact** — what changes for a user or operator, in plain language, before any architecture or test-strategy detail. See [Review gates: PR body style](how-to/review-gates.md#pr-body-style-consumer-focused-bluf).
- If your change is user-facing, add a consumer-focused entry to `docs/changelog/CHANGELOG.md` under `[Unreleased]` — impact-first, one line a user understands, not an internal-mechanism summary. See [Review gates: Changelog update and style](how-to/review-gates.md#changelog-update-and-style).
- Test your changes with the Spec-Driven Development workflow to ensure compatibility.
- Don't request review while your PR title is prefixed `WIP` / `[WIP]` -- a non-draft WIP-titled PR fails the `quality-gate` by design. Drop the prefix or keep the PR in draft. See [Review Gates](how-to/review-gates.md#pr-draft-and-wip-title-conventions).

## Label-driven fleet workflow

This repo is one of the programme's repos worked by the **[SkyKitty agent fleet](agent-fleet.md)**,
and the fleet runs on a **label-driven queue**: GitHub labels are the *only* admission
control. Agents and humans move work by changing labels, never by out-of-band assignment.
As a contributor, two things follow:

- **Issues** flow through a `status:*` lifecycle — `status:triage` → `status:ready` (the
  fleet's admission queue) → `status:claimed` (an implementer VM holds a lease) →
  `status:blocked`. **Never hand-set `status:claimed`**: it is a dispatcher-only lease, and a
  hand-set claim poisons the queue (the dispatcher counts it as occupied capacity, so the
  issue can sit invisible indefinitely).
- **Pull requests** flow through their own lane labels — `ready-for-squad` (request
  adversarial review) → `squad:running` → `squad:passed` / `squad:majors` — plus
  `needs:implementer`, which is **mandatory on any fix/rebase request that expects a new
  push** (the dispatcher only sees fix requests carrying that label).

The full label tables, the dispatcher admission/reaping loop, and the source control files
are documented in
[Managing the issue tracker → Label-driven fleet workflow](how-to/manage-issue-tracker.md#label-driven-fleet-workflow).
For the roles behind the queue, see [The SkyKitty agent fleet](agent-fleet.md).

## Maintainer guides

- [Landing contributor PRs](how-to/pr-landing.md) — the maintainer runbook for taking a contributor PR from "open with red CI" to "merge-ready, evidence posted, operator merges": claim, isolated worktree, rebase, red classification, folds, red-first verification, push discipline, and hand-off.
- [Managing the issue tracker](how-to/manage-issue-tracker.md) — epics vs. meta-trackers,
  native sub-issue parenting, and triage conventions, including how issue kind (`Task` /
  `Bug` / `Feature`) is set and tracked.
- [Create a doctrine artifact](how-to/create-a-doctrine-artifact.md) — includes how to model
  relationships between doctrine artifacts, including
  [design-opposing tension](how-to/create-a-doctrine-artifact.md#modeling-relationships-between-artifacts-including-tension)
  (`in_tension_with` / `reconciles_tension`; the legacy `opposed_by` field is retired).

## Development workflow

When working on spec-kitty:

1. Test changes with the `spec-kitty` CLI commands (`/spec-kitty.specify`, `/spec-kitty.plan`, `/spec-kitty.tasks`) in your coding agent of choice
2. Verify templates are working correctly in `templates/` directory
3. Test script functionality in the `scripts/` directory
4. Ensure the project charter (`.kittify/charter/charter.md`) is updated if major process changes are made

## Release Process

The repository-root [Release Checklist](../../RELEASE_CHECKLIST.md) is the canonical release runbook. The summary below is intentionally subordinate to that checklist and must remain consistent with branch protection.

### Branch Strategy

Spec Kitty's active release line is:

- **`main`** — The release branch. All tags MUST be created from `main`.
- **`1.x-maintenance`** — Deprecated, critical-maintenance-only line; no new 3.x work or PyPI releases.

### Quick Release (Patch)

For a small release whose product changes have already landed on `main`:

```bash
# 1. Create a release branch, then bump version and update changelog
git checkout -b release/X.Y.Z main
#    Edit pyproject.toml: version = "X.Y.Z"
#    Edit CHANGELOG.md: add section after [Unreleased]

# 2. Commit on a release branch, push it, and merge its PR
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): prepare X.Y.Z"
git push origin release/X.Y.Z
gh pr create --base main --title "Release X.Y.Z" --fill
gh pr merge --squash --delete-branch

# 3. Tag and push
git tag -a vX.Y.Z -m "Release vX.Y.Z - Brief description"
git push origin vX.Y.Z

# 4. Monitor
unset GITHUB_TOKEN && gh run list --workflow=release.yml --limit=1
unset GITHUB_TOKEN && gh run watch <run-id>

# 5. Verify
unset GITHUB_TOKEN && gh release view vX.Y.Z
pipx install --force spec-kitty-cli==X.Y.Z

# 6. Open the next development cycle on main (Release Checklist, step 8)
#    PR: next version in pyproject.toml, the uv.lock project entry and
#    .kittify/metadata.yaml, plus a new "## [Unreleased] - <next version>" heading
```

### Full Release (Minor/Major)

For larger releases with multiple changes:

1. **Create a release branch**
   ```bash
   git checkout -b release/X.Y.Z main
   ```

2. **Update version number** in `pyproject.toml`
   - Use [Semantic Versioning](https://semver.org/):
     - **Patch** (X.Y.Z): Bug fixes, small improvements
     - **Minor** (X.Y.0): New features, backward compatible
     - **Major** (X.0.0): Breaking changes

3. **Update CHANGELOG.md**
   - Add a new version section immediately after `## [Unreleased]`:
     ```markdown
     ## [X.Y.Z] - YYYY-MM-DD

     ### <emoji> <Category>

     **Short bold summary**:
     - Bullet point details
     ```
   - Categories used in this project (with emoji headings):
     - `### ✨ Added` — New features
     - `### 🔧 Improved` — Enhancements to existing features
     - `### 🐛 Fixed` — Bug fixes
     - `### 💥 Breaking` — Breaking changes
     - `### 📝 Architecture` — ADRs, design decisions
     - `### 🧹 Maintenance` — Refactoring, dependency updates
   - Use ISO date format: `YYYY-MM-DD`

4. **Create a pull request**
   ```bash
   git push origin release/X.Y.Z
   gh pr create --title "Release X.Y.Z: Brief description" --base main
   ```

5. **Wait for PR checks and merge**
   - The Release Readiness Check workflow validates version and changelog metadata. Require the repository test and package checks to pass on the same commit before publishing.
   - Get approval from a maintainer
   - Squash-merge the PR so the main-protection workflow can verify its PR marker

6. **Create and push the release tag**
   ```bash
   git checkout main && git pull origin main
   git tag -a vX.Y.Z -m "Release vX.Y.Z - Brief description"
   git push origin vX.Y.Z
   ```

7. **Monitor the workflow**
   ```bash
   unset GITHUB_TOKEN && gh run list --workflow=release.yml --limit=1
   unset GITHUB_TOKEN && gh run watch <run-id>
   ```
   Note: `unset GITHUB_TOKEN` is needed because the env var token may have limited scopes (e.g., only `copilot`). The keyring token has full `repo` scope.

8. **Verify the release**
   ```bash
   unset GITHUB_TOKEN && gh release view vX.Y.Z
   pipx install --force spec-kitty-cli==X.Y.Z
   ```

9. **Open the next development cycle**
   - Right after the tag, open a pull request that moves `main` to the next development or candidate version: `pyproject.toml`, the project entry in `uv.lock`, `.kittify/metadata.yaml`, and a new `## [Unreleased] - <next version>` heading in `CHANGELOG.md`.
   - Until it merges, branch-mode release validation on `main` fails with "Version does not advance beyond latest tag". The canonical step is step 8 of the [Release Checklist](../../RELEASE_CHECKLIST.md).

10. **Clean up**
    ```bash
    git branch -d release/X.Y.Z
    git push origin --delete release/X.Y.Z
    ```

### What the Release Workflow Does

Pushing a `v*.*.*` tag triggers `.github/workflows/release.yml`, which:

1. Checks out the tagged commit
2. Installs dependencies (including private `spec-kitty-events` via SSH deploy key)
3. Verifies no version mismatch between source and installed package
4. Runs release-specific tests; the broad module matrix remains owned by main CI
5. Validates release metadata (`scripts/release/validate_release.py --mode tag`)
6. Validates repository URLs match `pyproject.toml`
7. Builds wheel and source distributions
8. Verifies wheel contains all migration files
9. Extracts changelog for release notes
10. Publishes to PyPI
11. Creates a GitHub Release with artifacts

### Release Checklist

Before tagging a release, ensure:

- [ ] You are on the `main` branch
- [ ] Version number follows semantic versioning
- [ ] CHANGELOG.md is updated with emoji category headings
- [ ] Tests pass locally: `pytest tests/`
- [ ] Broad CI, release readiness, and shared-package drift checks are green

After tagging, open the next development cycle on `main` (Full Release step 9).

### Important Notes

- **Tags MUST be created from `main`** after the release PR lands
- **Use annotated tags** — always use `git tag -a`, not `git tag`
- **Monitor the release workflow** — watch for failures and be ready to fix issues
- **PyPI is immutable** — once published, a version cannot be changed (only yanked)
- **PyPI CDN caching** — `pipx upgrade` may not find the new version immediately; use `pipx install --force spec-kitty-cli==X.Y.Z` instead

### Troubleshooting Releases

#### Release workflow fails — check the actual error first

The workflow prints a generic error listing three possible causes ("PYPI_API_TOKEN", "version/changelog mismatch", "Tests failed") whenever ANY step fails. Check the actual failing step:

```bash
unset GITHUB_TOKEN && gh run view <run-id> --log-failed | head -80
```

#### Tests fail in the release workflow

The most common cause. To fix:

```bash
# 1. Fix the failing test
# 2. Commit on a new release branch and merge its PR; never push main directly
# 3. Delete the unpublished broken tag
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
# 4. Re-tag from the fixed commit
git tag -a vX.Y.Z -m "Release vX.Y.Z - Brief description"
git push origin vX.Y.Z
```

#### Tag was created from the wrong commit

If you accidentally tagged a commit that is not on `main`:

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
git checkout main
git tag -a vX.Y.Z -m "Release vX.Y.Z - Brief description"
git push origin vX.Y.Z
```

#### Version already exists on PyPI

- You attempted to release a version that's already published
- Bump to the next version number and retry

#### Changelog validation fails

- Ensure CHANGELOG.md has a section matching the version in pyproject.toml
- Check the date format is `YYYY-MM-DD`
- Verify the version number is monotonically increasing

## AI contributions in Spec Kitty

> [!IMPORTANT]
>
> If you are using **any kind of AI assistance** to contribute to Spec Kitty,
> it must be disclosed in the pull request or issue.

We welcome and encourage the use of AI tools to help improve Spec Kitty! Many valuable contributions have been enhanced with AI assistance for code generation, issue detection, and feature definition.

That being said, if you are using any kind of AI assistance (e.g., agents, ChatGPT) while contributing to Spec Kitty,
**this must be disclosed in the pull request or issue**, along with the extent to which AI assistance was used (e.g., documentation comments vs. code generation).

If your PR responses or comments are being generated by an AI, disclose that as well.

As an exception, trivial spacing or typo fixes don't need to be disclosed, so long as the changes are limited to small parts of the code or short phrases.

An example disclosure:

> This PR was written primarily by GitHub Copilot.

Or a more detailed disclosure:

> I consulted ChatGPT to understand the codebase but the solution
> was fully authored manually by myself.

Failure to disclose this is first and foremost rude to the human operators on the other end of the pull request, but it also makes it difficult to
determine how much scrutiny to apply to the contribution.

In a perfect world, AI assistance would produce equal or higher quality work than any human. That isn't the world we live in today, and in most cases
where human supervision or expertise is not in the loop, it's generating code that cannot be reasonably maintained or evolved.

### What we're looking for

When submitting AI-assisted contributions, please ensure they include:

- **Clear disclosure of AI use** - You are transparent about AI use and degree to which you're using it for the contribution
- **Human understanding and testing** - You've personally tested the changes and understand what they do
- **Clear rationale** - You can explain why the change is needed and how it fits within Spec Kitty's goals  
- **Concrete evidence** - Include test cases, scenarios, or examples that demonstrate the improvement
- **Your own analysis** - Share your thoughts on the end-to-end developer experience

### What we'll close

We reserve the right to close contributions that appear to be:

- Untested changes submitted without verification
- Generic suggestions that don't address specific Spec Kitty needs
- Bulk submissions that show no human review or understanding

### Guidelines for success

The key is demonstrating that you understand and have validated your proposed changes. If a maintainer can easily tell that a contribution was generated entirely by AI without human input or testing, it likely needs more work before submission.

Contributors who consistently submit low-effort AI-generated changes may be restricted from further contributions at the maintainers' discretion.

Please be respectful to maintainers and disclose AI assistance.

## Resources

- [Spec-Driven Development Methodology](../context/spec-driven.md)
- [How to Contribute to Open Source](https://opensource.guide/how-to-contribute/)
- [Using Pull Requests](https://help.github.com/articles/about-pull-requests/)
- [GitHub Help](https://help.github.com)
