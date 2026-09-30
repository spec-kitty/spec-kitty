---
title: 'Issue #797 Analysis: Events and Tracker Fork Census'
description: Read-only census of the EXPERIMENTAL events and tracker lines against their public/PyPI predecessors, with the D6 publication recommendation.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/investigations/index.md
---
# Issue #797 Analysis: Events and Tracker Fork Census

> **Historical (decided).** The D6 publication question this census informed is settled: the CLI now pins `spec-kitty-events>=10.4.0,<11` (see `pyproject.toml`). Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

This is the read-only evidence record for issue #797. It makes no ports and changes no
dependency pins. All commit counts include merge commits unless explicitly labelled
non-merge.

## Recommendation for D6

Publish **spec-kitty-events 8.2.0** and **spec-kitty-tracker 0.5.2**, not events 9.1.4,
for the Phase 5 dependency cutover.

- Events: the CLI and SaaS already resolve the same 8.2.0 commit,
  `c93dbfbf5243330349452a31d05bca2ece26ceea`. A public promotion merge can join public
  main to that commit without losing any public product change; the only public product
  commit after the fork was already ported into the experimental line.
- Tracker: there is no public `Priivacy-ai/spec-kitty-tracker` Git repository, so D6's
  "public repos" premise is incorrect for this package. The owner must first create that
  repository. The publish candidate should be
  `69d327feeee98b6198c968490b1200cc01079577`: it is on experimental main, declares 0.5.2,
  has the required 0.5.2 release-matrix entry, and still carries the acceptance and
  PyPI publish workflows. Its package tree is identical to the CLI's current 67a6 pin;
  69d327 only adds release bookkeeping and test-target wiring.
- Align both consumers on one exact tracker SHA before publication. The coordinated pin
  is `69d327feeee98b6198c968490b1200cc01079577`: SaaS moves from
  `f9dbd014410a137d70dab230007d415652d9bff8`, and the CLI moves from
  `67a6ecc91f4b4a5fa82492a80ced4f49ce98851e`. This satisfies PROGRAM.md's same-commit rule
  while selecting the workflow-complete release candidate.
- In SaaS `contracts/consumer-compatibility.json`, record the contracts actually being
  consumed: change events `supported_range` from `==8.0.0` to `==8.2.0`, change tracker
  `supported_range` from `==0.4.3` to `==0.5.2`, and set tracker
  `allow_source_override` to `true` while 0.5.2 remains unpublished. After publication,
  issue #828 can replace both source pins with PyPI ranges and turn source overrides back
  off.

Events 9.1.4 is not recommended for this cutover: it is 156 commits beyond the commit both
current consumers test, and experimental main has deleted its publish workflow. Choosing it
would require a new consumer test pass, restoration of a publish workflow, and a second
coordinated pin change before Phase 5 could proceed.

## Events census

| Ref | Role | Version | Commit date |
|---|---|---:|---|
| `d9518544916a6253bd206042699ee84f037dea8e` | fork point | 6.1.0 line | 2026-08-03 |
| `e385e5ae35b44ce2bab8a5820dd0d44aa6c5545f` | public main | 6.1.0 | 2026-08-24 |
| `c93dbfbf5243330349452a31d05bca2ece26ceea` | CLI/SaaS pin | 8.2.0 | 2026-08-27 |
| `f9de396ade213077d412a040bac2babec016243a` | experimental main | 9.1.4 | 2026-08-30 |

The fork point is `d9518544916a6253bd206042699ee84f037dea8e`. Relative to that point:

- Experimental 8.2.0 has 71 commits (43 non-merge).
- Public main has 8 commits (7 non-merge).
- Experimental main has 227 commits not reachable from public main (130 non-merge).
- Experimental 8.2.0 is **not** a commit-level superset of public main: public main has 8
  commits not reachable from the 8.2.0 pin.

The public-only set contains one product change:
`0012fff9ec7172442974d6039482ff15cbddbd52`, which adds two invalid dossier conformance
fixtures. The experimental line already contains that work as
`0a2d9dacd4f4e4bb7c7a7a16f658bf213bb567b8`; the port commit says explicitly that it came
from public PR #50 and deliberately omitted the other repository's mission bookkeeping.
The two new fixture files and the dossier test are byte-identical, and the port registers
equivalent manifest entries. The complete manifest files differ because the experimental
line had already removed cutover fixtures and added later contract fixtures; that is
expected experimental-line divergence, not a missing part of the public product change. The
other public-only non-merge commits are mission/planning bookkeeping plus review-lock and
charter changes, followed by the PR #50 merge. There is therefore no public product-code gap
that blocks publishing 8.2.0.

Publishing events 8.2.0 from the public repository requires:

1. Create a two-parent promotion commit joining public main to experimental `c93dbfbf`,
   with the experimental 8.2.0 tree as the result. Do not force-push over public main.
2. Push that commit to `Priivacy-ai/spec-kitty-events` main.
3. Confirm PyPI trusted publishing is configured for that repository, the
   `publish-pypi.yml` workflow, and the `pypi` environment. Repository contents prove the
   workflow and environment name, but not the external PyPI trust assignment.
4. Tag the promoted commit `v8.2.0` and push the tag.

Both public main and `c93dbfbf` carry `publish-pypi.yml` and `publish-testpypi.yml`.
`publish-pypi.yml` triggers on `v*` tags and manual dispatch, runs the release acceptance
job, checks that the tag matches `pyproject.toml`, builds and checks the distribution,
validates package metadata, and publishes with OIDC in the `pypi` environment.

## Tracker census

| Ref | Role | Version | Commit date |
|---|---|---:|---|
| `dd56a86d4f9b157cfa3bbdabe7f4514c30ac829d` | PyPI 0.4.3 source baseline | 0.4.3 | 2026-04-27 |
| `f9dbd014410a137d70dab230007d415652d9bff8` | current SaaS source pin | 0.5.2 | 2026-08-26 |
| `67a6ecc91f4b4a5fa82492a80ced4f49ce98851e` | current CLI source pin | 0.5.2 | 2026-08-27 |
| `69d327feeee98b6198c968490b1200cc01079577` | recommended publish candidate | 0.5.2 | 2026-08-27 |
| `c6835970ef7749b951bd631601b76799f04be36a` | experimental main | 0.5.2 | 2026-08-29 |

The public GitHub organization has **no `Priivacy-ai/spec-kitty-tracker` repository**. The
organization repository list contains `Priivacy-ai/spec-kitty-events` but no tracker
repository, and GitHub repository search returns no match for `spec-kitty-tracker`. A Git
fork point therefore cannot be measured against a public tracker main because that side has
no public Git history.

The published PyPI 0.4.3 wheel provides a source-level baseline instead. All 39 package
files in the wheel are byte-identical to `src/spec_kitty_tracker` at
`dd56a86d4f9b157cfa3bbdabe7f4514c30ac829d`, which is an ancestor of experimental main.
Relative to that baseline:

- The current CLI pin is 110 commits ahead (102 non-merge).
- The recommended publish candidate is 111 commits ahead (103 non-merge).
- Experimental main is 154 commits ahead (121 non-merge).

The recommended publish candidate, `69d327feeee98b6198c968490b1200cc01079577`, is one
commit after the CLI pin and 43 commits before experimental main. It is preferable to
current main for publication because current main deleted `.github/workflows/`; 69d327
still contains `acceptance.yml`, `publish-pypi.yml`, and `publish-testpypi.yml`, and its
release matrix includes the required `[tracker."0.5.2"]` entry. The CLI pin itself would
fail the matrix validation because its matrix stops at 0.5.0.

Publishing tracker 0.5.2 therefore requires:

1. Create `Priivacy-ai/spec-kitty-tracker` as the public source repository.
2. Push the experimental history/tree at `69d327feeee98b6198c968490b1200cc01079577` (or a
   later reviewed commit that restores the acceptance and publish workflows while retaining
   the 0.5.2 matrix entry).
3. Configure PyPI trusted publishing for the new repository, `publish-pypi.yml`, and the
   `pypi` environment.
4. Tag that promoted commit `v0.5.2` and let the tag-triggered workflow run acceptance,
   tests, matrix and metadata validation, build checks, and OIDC publication.

This is an owner/controller release action. The experimental repository's charter explicitly
forbids programme agents from pushing release tags or dispatching its publish workflow.

## Evidence commands

The counts and ancestry above were produced with `git fetch`, `git merge-base`,
`git rev-list --count`, and `git merge-base --is-ancestor` against:

```text
https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-events
https://github.com/Priivacy-ai/spec-kitty-events
https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-tracker
```

Public repository presence was checked with the GitHub organization repository listing and
repository search. PyPI versions came from `https://pypi.org/pypi/<package>/json`; the
tracker wheel comparison extracted the 0.4.3 wheel and compared every packaged file with the
named experimental source tree.
