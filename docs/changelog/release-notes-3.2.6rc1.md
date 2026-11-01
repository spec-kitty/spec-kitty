---
title: Release notes — 3.2.6rc1 (internal Release Candidate)
description: 'Internal Release Candidate notes for spec-kitty-cli 3.2.6rc1: an opt-in prerelease build for maintainer validation, not an official 3.2.6 release.'
doc_status: active
type: reference
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
updated: '2026-09-03'
related:
- changelog/CHANGELOG
- changelog
- changelog/release-goals
---
# Release notes — `3.2.6rc1` (internal Release Candidate)

_For the existing Spec Kitty operator/maintainer deciding whether to pull this candidate into a test environment._

> [!WARNING]
> **`3.2.6rc1` is a Release Candidate — an internal, delta build published for validation, NOT an official `3.2.6` release.** It ships as a GitHub _prerelease_ and to PyPI as a PEP 440 prerelease, so ordinary installers skip it unless you explicitly opt in with `--pre`. Do **not** use it for production or general rollout. The last official release remains `v3.2.5`; when `3.2.6` is finalized its changelog section supersedes this candidate.

> [!NOTE]
> **Update 2026-09-03 — the release-critical work that remained after this candidate has fully landed.** At rc1 time, a set of release-blocking bugs (the 3.2.6 execution DAG, tracker #3692) still gated the final tag. That book is now empty — all twenty DAG nodes are closed, #3692 is closed, and the milestone stands at 0 remaining work items. This candidate's highlights below are the rc1 snapshot; the finalized `3.2.6` changelog section is the authoritative record of everything the release ships.

## Install for testing

This candidate is opt-in. Standard installs will not pick it up without `--pre`.

```bash
pipx install --pre spec-kitty-cli==3.2.6rc1
# or, inside an existing environment:
pip install --pre spec-kitty-cli==3.2.6rc1
```

## Highlights since `v3.2.5`

The operator-facing changes worth exercising in this candidate:

- **Breaking — built-in doctrine content relocated to `packs/built-in/` with no compatibility shim** (mission `relocate-builtin-doctrine-packs`). Repoint any reference that still targets the old `src/doctrine/<kind>/built-in/` path.
- **Breaking — local `beads`/`fp` tracker sync now requires a recorded egress decision** (mission `tracker-egress-refusal-3108`). A binding that never recorded hosted-sync consent stops syncing on upgrade until you record `tracker.egress: permitted` or `sync.enabled: true`.
- **Breaking — the `rtk-search-tooling` toolguide is removed**, and the `3.2.6_retire_rtk_search_tooling` upgrade migration strips it from projects that had it activated (it runs automatically on `spec-kitty upgrade` and is safe to re-run).
- **Breaking — org packs with an unrecognised agent-profile or DRG key now fail to load** (mission `doctrine-silence-guards`). Run `spec-kitty doctor doctrine --json` and check `skipped_profiles` before you upgrade.
- **`charter synthesize` is now non-destructive** — it preserves backed governance content by default, with `--prune` as the explicit opt-in and `--dry-run` to preview (mission `charter-synthesize-reconciliation`; `#3270` P0, folds `#2777` / `#3052`). The `implement` / `next` boundary no longer hard-blocks until you resynthesize.
- **Approving a work package after a rejection now sticks with no override flag required** (mission `review-verdict-write-integrity`; `#3044`) — the reject → fix → approve cycle no longer forces `--skip-review-artifact-check`.
- **Timestamps Spec Kitty writes into your project are now correct aware-UTC** instead of local time mislabelled as UTC (mission `kernel-clock-single-door`; `#3305`, closes `#3289`).
- **CLI UX: shell autocompletion, a `-h` short-help alias, and alphabetical command listing** (`#2232`, `#2234`, `#2235`) — additive, with no behavior change to existing commands.

## Full changelog

These highlights are a curated subset. For the complete, factual list of everything in this candidate — every Added, Fixed, Changed, and Breaking Changes entry — see the `[3.2.6rc1]` section of the [canonical changelog](CHANGELOG.md).
