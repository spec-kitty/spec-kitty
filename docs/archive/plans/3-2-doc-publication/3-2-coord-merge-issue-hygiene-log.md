---
title: 3.2 Coordination & Merge Cluster — Issue Hygiene Log
description: 'Issue-hygiene action log for the coordination-merge-stabilization mission (WP01 / FR-011): the tracker cleanup performed on 2026-06-12 against the repo.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# 3.2 Coordination & Merge Cluster — Issue Hygiene Log

Mission: `coordination-merge-stabilization-01KTXRVR`, WP01 (FR-011). All actions performed 2026-06-12 against `Priivacy-ai/spec-kitty`, following the Debbie/Paula validation pass (2026-06-12). Authoritative disposition: `kitty-specs/coordination-merge-stabilization-01KTXRVR/validation/cluster-validation-brief.md` §2 and research.md R8.

## Actions

| Issue | Action | Citation | URL | Timestamp (UTC) |
|---|---|---|---|---|
| #1770 | Closed with comment | PR #1793 (`c5a10ce56`, FR-035/FR-037 tempdir bake) + PR #1850 accept anchor | https://github.com/Priivacy-ai/spec-kitty/issues/1770 | 2026-06-12T12:00:19Z |
| #1789 | Closed with comment | PR #1850 WP11/WP12 (`8544012fa`): git-op guard, write-free dashboard materialize, scoped reaper | https://github.com/Priivacy-ai/spec-kitty/issues/1789 | 2026-06-12T12:00:21Z |
| #1816 | Closed with comment | PR #1850 WP06 unified CommitTarget/FLATTENED classification | https://github.com/Priivacy-ai/spec-kitty/issues/1816 | 2026-06-12T12:00:23Z |
| #1771 | Closed with comment | PR #1850 WP08 (FR-006 canonical tracked path; `test_record_committable_1771.py`) | https://github.com/Priivacy-ai/spec-kitty/issues/1771 | 2026-06-12T12:00:25Z |
| #1571 | Closed with comment | PR #1719 push-gated sync preflight; superseded by #1706 | https://github.com/Priivacy-ai/spec-kitty/issues/1571 | 2026-06-12T12:00:27Z |
| #1784 | Closed with comment (duplicate of #1777) | PR #1850 `resolve_placement_only`; P3 crumbs carried in mission WP02/WP03 | https://github.com/Priivacy-ai/spec-kitty/issues/1784 | 2026-06-12T12:00:29Z |
| #1735 | Closed with comment | PR #1850 WP08; residuals tracked in mission WP05 **and** umbrella #1878 (finding U2) | https://github.com/Priivacy-ai/spec-kitty/issues/1735 | 2026-06-12T12:01:09Z |
| #1814 | Re-scoped (retitled `residual:`; prepended "## Re-scoped 2026-06-12") | Status-file deadlock fixed by #1850 WP06 (`8544012fa`); residual `lanes.json`/`tasks/*` residue → mission WP02/T008 | https://github.com/Priivacy-ai/spec-kitty/issues/1814 | 2026-06-12T12:01:29Z |
| #1736 | Re-scoped (retitled `residual:`; prepended "## Re-scoped 2026-06-12") | Bugs A/B/C fixed (`a5f30616e`/`c5a10ce56`/`8544012fa`); residual `_make_merge_env`, narrow `status_transition.py:399` except, mixed-timestamp ratchet → mission WP03/T015–T017 | https://github.com/Priivacy-ai/spec-kitty/issues/1736 | 2026-06-12T12:01:31Z |
| #1833 | Re-scoped (retitled `residual:`; prepended "## Re-scoped 2026-06-12") | F-001 naming trigger fixed in #1850 (`8544012fa`); residual husk fall-through guards + doctor check → mission WP04 | https://github.com/Priivacy-ai/spec-kitty/issues/1833 | 2026-06-12T12:01:33Z |
| #1861 | Re-scoped (retitled `residual:`; prepended "## Re-scoped 2026-06-12") | Part 2 resolved by `SafeCommitHeadMismatch` (`8e79b3f6d`, AC-C3); residual Part 1 validate-only guard → mission WP02/T006 | https://github.com/Priivacy-ai/spec-kitty/issues/1861 | 2026-06-12T12:01:35Z |
| #1878 | Filed follow-up umbrella under epic #1666 | C-001 deferred non-goals + fresh evidence (analysis finding I2); labels: epic, git, reliability, priority:P2 | https://github.com/Priivacy-ai/spec-kitty/issues/1878 | 2026-06-12T12:00:58Z |

## Umbrella issue

**#1878 — Umbrella: complete the coordination placement/identity strangler (post-3.2.0)**
https://github.com/Priivacy-ai/spec-kitty/issues/1878

## Explicitly untouched

- **#1826** — left open and unmodified; fixed by WP03 of this mission, not by hygiene.
