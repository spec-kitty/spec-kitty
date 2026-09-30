---
title: Changelog
description: 'Changelog landing page: the canonical CHANGELOG.md, the forward-looking release goals, and the historical 1.x/2.x archive folded into this section.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-08-10'
related:
- docs/changelog/CHANGELOG.md
- docs/changelog/release-goals.md
- docs/changelog/3.2.x.md
- docs/changelog/3.3.x.md
- docs/changelog/1x/index.md
- docs/changelog/2x/index.md
- docs/plans/3-2-x-milestone-roadmap.md
---
# Changelog

The canonical Spec Kitty changelog lives in this section as
[`CHANGELOG.md`](CHANGELOG.md) (Mission B, FR-009).

The repository-root `CHANGELOG.md` is a **symlink to this canonical copy**:
release tooling (`scripts/release/`, `pyproject.toml`,
`.github/release-readiness.yml`) reads the root path and is out of relocate
scope. Root is the symlink; `docs/changelog/CHANGELOG.md` is canonical.

## Release goals

Where the project is going next — the declared intent of each release line:

- [Release goals convention](release-goals.md) — how release goals are declared and tracked.
- [3.2.x goals](3.2.x.md) — focus for the 3.2.x line; closed (3.2.7, 2026-09-10, was the last 3.x release); historical.
- [3.3.x goals](3.3.x.md) — retired 2026-08-23 (work re-triaged into 4.0.0 / Product backlog); historical.
- [4.0.0 goals](4.0.0.md) — hosted collaboration + the open-core structural finish.
- [3.2.x milestone roadmap](../plans/3-2-x-milestone-roadmap.md) — operator-facing
  execution roadmap (a plans/ working document under the distil-then-retire lifecycle).

## Historical archive

Previous-release documentation, preserved for audits and older-project behavior
lookup. Do not use these to start a new project or upgrade — see the
[3.2 docs](../index.md) and [migration guide](../migrations/index.md) instead.

- [Spec Kitty 2.x archive](2x/index.md) — the 2.x model before the current 3.2 runtime and Charter-era guidance.
- [Spec Kitty 1.x archive](1x/index.md) — the original workflow model and early command structure.
