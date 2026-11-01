---
title: DIR-013 Sub-Issues Filed for Mission 01KSF9HJ
description: Record of the GitHub sub-issues filed per DIR-013 (Pre-existing Failure Reporting Rule) from the mission 01KSF9HJ test-failure triage.
doc_status: deprecated
updated: '2026-06-27'
related:
- docs/archive/plans/engineering-notes/triage/2026-05-25-01KSF9HJ-test-failure-triage.md
---
# DIR-013 Sub-Issues Filed for Mission 01KSF9HJ

This document records the GitHub sub-issues filed per DIR-013
(Pre-existing Failure Reporting Rule) from the triage in
[`triage.md`](2026-05-25-01KSF9HJ-test-failure-triage.md). Parent issue: [Priivacy-ai/spec-kitty#1298].

All issues filed against `Priivacy-ai/spec-kitty` on 2026-05-25 from the
WP04 closeout workstation.

| # | Cluster | Issue # | URL |
|---|---------|---------|-----|
| 1 | C2 / C99-i (umbrella) — Shared-package events drift residual | #1301 | https://github.com/Priivacy-ai/spec-kitty/issues/1301 |
| 2 | C99-b — TOML rendering escape bug (gemini/qwen) | #1302 | https://github.com/Priivacy-ai/spec-kitty/issues/1302 |
| 3 | C99-d — Charter synthesizer non-determinism | #1303 | https://github.com/Priivacy-ai/spec-kitty/issues/1303 |
| 4 | C99-e — Doctrine / glossary anchor drift | #1304 | https://github.com/Priivacy-ai/spec-kitty/issues/1304 |
| 5 | C99-f — `next` CLI exit-code regressions | #1305 | https://github.com/Priivacy-ai/spec-kitty/issues/1305 |
| 6 | C99-g — Status / lifecycle event drift | #1306 | https://github.com/Priivacy-ai/spec-kitty/issues/1306 |
| 7 | C99-h — Charter integration suite regressions | #1307 | https://github.com/Priivacy-ai/spec-kitty/issues/1307 |
| 8 | C99-j docs — README + CHANGELOG drift | #1308 | https://github.com/Priivacy-ai/spec-kitty/issues/1308 |
| 9 | C99-j chokepoints — meta.json + lane regression | #1309 | https://github.com/Priivacy-ai/spec-kitty/issues/1309 |
| 10 | C99-j misc — auth / invocation / doctrine / mypy / mission switching | #1310 | https://github.com/Priivacy-ai/spec-kitty/issues/1310 |

## Body templates

Filed bodies live alongside this document's predecessor at
`/tmp/01KSF9HJ-issue-bodies/01..10-*.md` on the WP04 workstation. The
canonical content of each body is also reachable via the URLs above.

All 10 issues follow this structure:

```
## Context

This issue is filed per DIR-013 (Pre-existing Failure Reporting Rule)
during implementation of mission `test-stabilization-and-debt-pass-01KSF9HJ`
(WP04 — Wave T closeout). Parent: #1298.

## Root cause (per triage)
## Failure count
## Affected tests
## Suggested ownership
## Attribution
```

## Filing log

- 2026-05-25 — 10 issues filed (#1301..#1310) under WP04 (Wave T
  closeout) by `claude:opus-4-7:python-pedro:implementer`.
- All issues reference parent #1298 and the canonical triage at
  `docs/01KSF9HJ-triage/triage.md` on
  `kitty/mission-test-stabilization-and-debt-pass-01KSF9HJ`.

## Repository note

Issues were filed directly against the upstream `Priivacy-ai/spec-kitty`
repository (no PR to upstream — code in this mission remains in the
fork until accepted). DIR-013 mandates issue filing on the upstream
where the triage was performed; this satisfies the rule without pushing
mission code upstream.
