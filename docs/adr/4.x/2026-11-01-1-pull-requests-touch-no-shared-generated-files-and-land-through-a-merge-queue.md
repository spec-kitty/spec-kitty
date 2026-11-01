---
title: 'ADR: pull requests touch no shared generated file and land through a merge queue'
description: 'Changelog entries become per-PR fragments, the docs index regenerates on main through a bot PR, and main merges through a GitHub merge queue.'
status: Accepted
date: '2026-11-01'
doc_status: active
kind: ADR
updated: '2026-11-01T00:00:00Z'
---

# Pull requests touch no shared generated file and land through a merge queue

**Status:** Accepted (2026-11-01). Operator rulings of 2026-11-01 on the landing-bottleneck brief.

**Date:** 2026-11-01

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- The 2026-10-31/11-01 landing run: 22 PRs merged in about 24.5 hours, a 6-hour Actions deadlock (#6961, #6963), and duplicate changelog entries from rebases that kept both sides of a conflict.
- Dedicated bot token: #6986 (interim use of `CHARTER_SHARD_RECAPTURE_TOKEN`, see Decision 2).
- Amends [ADR 2026-09-23-1](../3.x/2026-09-23-1-auto-merge-required-checks-gate.md) (the required checks gate auto-merge; see Decision 3).

## Context and Problem Statement

Landing throughput was about one PR an hour, and CI latency was not the main reason. Nearly every PR
edited the same files:

- `docs/changelog/CHANGELOG.md` (an `[Unreleased]` entry and the frontmatter `updated:` key);
- the generated `docs/development/docs-retrieval-index.yaml` and `docs/development/page-inventory.yaml`;
- for a new ADR, the era table in `docs/adr/<era>/index.md`.

Each merge to `main` therefore put every other in-flight PR in conflict. Each conflicted PR needed a
rebase and a full CI re-run, 40 to 60 minutes under load. With four PRs in flight, every merge cost
about three wasted CI cycles, and the waste grew with the number of PRs in flight. Rebases that
kept both sides of a changelog conflict re-added duplicate entries three times and once left a second
`updated:` key.

## Decision

### 1. Changelog entries are per-PR fragments

A pull request adds `docs/changelog/unreleased/<id>.<section>.md` and never edits
`docs/changelog/CHANGELOG.md`.

- `<id>` is the PR number; before the PR exists, the issue number plus a branch slug, renamed once
  the PR number is known. Lowercase letters, digits and `-`.
- `<section>` is `breaking`, `upgrade-notes`, `added`, `changed`, `fixed` or `internal`, the six
  `###` headings of `[Unreleased]`, in that order.
- The content is the entry exactly as it reads in the changelog, with no heading and no open code fence.
- The style guard (`scripts/docs/check_changelog_style.py`) and the spelling check
  (`scripts/docs/check_spelling.py`) run on every fragment and report at the fragment's own lines.
- At release time `python -m scripts.release.changelog_fragments assemble --write` folds the fragments
  into `[Unreleased]`, after the existing entries, sets `updated:` and deletes them.
  `validate_release.py` refuses a tag, or a release-cut branch, while any fragment remains.
- **Fragments are not docs pages.** Every other `docs/**/*.md` file needs frontmatter, a row in the
  page inventory and an entry in the docs retrieval index. `scripts/docs/_page_scope.py` is the one
  authority for the page set and leaves `docs/changelog/unreleased/` out, so a fragment touches no
  shared file. The docs site build excludes the directory (`docs/docfx.json`).

The operator chose `docs/changelog/unreleased/` over a root `changelog.d/`, keeping the fragments
beside the changelog they feed, at the cost of the page-scope exclusion.

### 2. The docs retrieval index and its siblings regenerate on `main`, through a bot PR

PRs no longer regenerate `docs-retrieval-index.yaml`, `page-inventory.yaml` or the ADR era tables.
After a merge to `main` that touches `docs/**` (and on a daily schedule as a backstop), a workflow
regenerates all three and opens or updates one PR on a fixed branch, `ci/regen-docs-index`, the way
the shard-timings recapture already does. The per-PR gate checks that the index regenerates cleanly
from the tree instead of comparing it with a committed copy that is expected to lag.

The bot uses a PR, not a commit to `main`: it needs no branch-protection exception and runs the normal
required checks. It authenticates with the existing `CHARTER_SHARD_RECAPTURE_TOKEN` PAT. **Sharing that
token is interim**; a dedicated secret is tracked in #6986.

Generating the index at build or query time (measured about 1.3 s per query, and the generator would
have to move into `src/`) and splitting it into about 915 per-page files were rejected. The wheel has
never shipped the index, so neither choice changes anything for installed users.

### 3. `main` merges through GitHub's merge queue

The queue tests each PR on `main` plus the PRs ahead of it and rebase-merges it when the required
checks pass there, replacing the manual rebase-and-re-run loop.

- `ci-router.yml`, `ci-modules.yml` and `ci-quality.yml`, which produce the three required checks
  (`router gate`, `CI Modules gate`, `Clean install verification`), trigger on `merge_group`. No optional
  workflow joins the queue: path-filtered ones would run on every group.
- The changed-files and prose-scan steps diff a queue run against `merge_group.base_sha`, so it stays
  path-scoped. CI Aggregate skips queue runs. CI Fleet Verdict keys its concurrency on the source
  event, so a queue run never cancels the push-to-main verdict of the same commit.
- Repository settings (operator): require the merge queue on `main`; merge method rebase; only merge
  non-failing pull requests; build concurrency 3; group size minimum 1 and maximum 3; wait time
  5 minutes; status-check timeout 90 minutes.
- Operator prerequisite: the external fleet stops pushing to queued PRs. A push removes a PR from the
  queue and rebuilds every group behind it.

This amends ADR 2026-09-23-1. The three required checks and `strict: false` stand, and auto-merge
now queues a PR instead of merging it.

## Consequences

- Two PRs that each add a changelog fragment or edit unrelated docs no longer conflict.
- `spec-kitty docs query` on a branch can lag by the pages merged since the last bot PR.
- The release gains one step, assembling the fragments, enforced by `validate_release.py`.
- Every PR runs the required checks twice, on the PR and in the queue. The queue run is path-scoped.
- `packs/internal` (in `spec-kitty-open-packs`) still tells agents to edit `CHANGELOG.md` and to
  regenerate the index; that doctrine is updated there and the pin bumped in a follow-up.
