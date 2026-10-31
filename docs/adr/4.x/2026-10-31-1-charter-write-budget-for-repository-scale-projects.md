---
title: 'ADR: a charter-write budget for repository-scale projects, and why 2 s is not it'
description: 'A charter write command is budgeted by a structural round-trip count and a ratio to the cost of reading the same project; the 2 s CLI budget stays for typical projects.'
status: Accepted
date: '2026-10-31'
updated: '2026-10-31'
---

**Status:** Accepted

**Date:** 2026-10-31

**Deciders:** the mission's own measurement and review; recorded for the operator to confirm or amend.

**Technical Story:** [#6506](https://github.com/spec-kitty/spec-kitty/issues/6506) — "charter activate/deactivate take 9-15 s on this repository, far over the 2 s CLI budget". Mission `charter-write-roundtrip-latency-01M68ZVK`.

---

## Context and Problem Statement

`.kittify/charter/charter.md` ("Performance and Scale") sets a budget of **under 2 seconds** for CLI operations, for *typical projects*. On a project the size of this repository — a 165 KB,
1,937-line `charter.yaml` with 264 `catalog.references` — `charter activate` and `charter deactivate`
took 16-18 s (issue #6506). The issue asks for one of two things: bring them under 2 s, or **record a
justified budget for repositories of this size**.

The 2 s number cannot be met here, and the reason is arithmetic rather than a missing optimization:

| Operation | Measured median |
|---|---|
| `charter list` — a pure read that writes nothing and compiles nothing | **2.62-2.77 s** |
| `charter deactivate` before this mission | 16.65 s |
| `charter deactivate` after this mission | 10.39 s |

A pure read already costs more than the entire 2 s budget at this scale. No command that reads the
compiled charter can reach 2 s here; the read floor is the floor.

## Where the time went, and what this mission removed

Wall-clock attribution of one `deactivate` run before the change (inclusive times, so rows nest):

| Cost centre | Before | After |
|---|---|---|
| Compiled-charter write path (`write_compiled_charter`) | 9.14 s | **2.79 s** |
| … owned-section prepare cycles per refresh | 2 | **1** |
| … whole-document comparisons (`yaml_documents_equal`) | ≈3.4 s (2 × ≈1.2 s per render) | **3 ms** for 19 calls |
| Compiler pass (`compile_charter`) | 2.4-2.5 s | 2.4-2.5 s (unchanged, out of scope) |
| Read floor (start-up, project load, charter read) | ≈2.6 s | ≈2.7 s (unchanged) |

Two causes, both structural rather than "this repository is big":

1. `write_compiled_charter` refreshed the two derived sections (`catalog`, `metadata`) with two
   sequential single-section writes, each of which observed, loaded, rendered and verified the whole
   document. One recompile therefore paid the whole cycle twice.
2. The document-equality check, which the writer uses to return the original bytes unchanged and to
   guard against a lossy render, serialised the entire value and re-parsed it whenever `==` failed —
   about 1.2 s per comparison on this document, twice per render.

Both are fixed: one prepared write carries every owned section, and the equality check walks the two
values structurally, round-tripping only the values that genuinely differ. Measured whole-document
comparison cost fell from 1,189 ms to 1.0-3.7 ms with no change of verdict.

**Interleaved before/after measurement** (one frozen checkout per side, same launcher, five rounds,
alternating order, project seeded from this repository's own `.kittify/`):

| | floor (`charter list`) | command (`charter deactivate`) | ratio |
|---|---|---|---|
| before | 2.62 s | 16.65 s | 6.35 |
| after | 2.77 s | 10.39 s | 3.75 |

The command improved **1.60×**; the floor did not move, as expected — it does not touch the write path.

## Decision

For repositories of this size, a command that recompiles and rewrites the compiled charter is
budgeted by two things, in this order of authority:

1. **A structural budget: at most 6 whole-document round trips of the governed charter per recompile,
   ratchet-only-down.** This is exact, deterministic, load-independent, and it runs on every pull
   request (`tests/charter/activation/test_charter_write_roundtrips.py`). It is the regression gate.
   The pre-mission shape measured 18 on the same fixture; 6 is what one merged write cycle needs, and
   the first two of the six read identical bytes, so a future change can lower the number and should.
2. **A runaway guard: at most 8× the cost of reading the same project** (`charter list`), measured
   interleaved in the same run (`tests/performance/test_charter_write_repo_scale_timing.py`,
   `CHARTER_WRITE_RATIO_LIMIT`). Observed 3.4-4.6. This limit deliberately does **not** try to
   discriminate the 1.6× improvement: at 4-6× its own floor the command's variance dominates the
   ratio instead of cancelling against it, and the measured pre-fix (3.5-6.8) and post-fix (3.4-4.6)
   ranges overlap across series taken under different machine load. A tighter limit would false-red on
   the clean tail — the failure mode ADR
   [`2026-10-05-2`](./2026-10-05-2-runner-relative-performance-budgets.md) exists to stop, and the
   reason #3787 retired its own ceiling after four ratchets.

The charter's `< 2 s` budget is **not** changed: it is correct for typical projects, and renegotiating
it is the operator's call, not a mission's.

**Reaching 2 s here would require** an incremental catalog update instead of a full recompile. The
changelog entry for #4785 already accepted "~2.4-2.5 s" for the single-authority `compile_charter`
resolution — deliberately, over a competing minimal writer that the charter's single-canonical-authority
principle forbids — so the compiler is not cheap to trim without re-architecting it. That work is
explicitly out of scope for this mission and would be its own decision record.

## Considered Options

1. **Record a structural budget plus a runaway ratio (chosen).** The exact measure gates; the coarse
   measure bounds catastrophe; the wall clock is recorded as a measurement, not asserted.
2. **Delete the two whole-document equality checks** (the largest single term). Rejected: one is what
   makes a no-op recompile return the original bytes, the other is the "cannot preserve YAML aliases
   or section boundaries" guard. Removing either trades a governed invariant for speed.
3. **Raise the charter's 2 s budget.** Rejected: it is an operator-owned governance statement, correct
   for typical projects. This record adds a budget for a different size band; it does not replace one.
4. **Assert an absolute seconds budget at repository scale.** Rejected by ADR `2026-10-05-2`, on
   evidence: a bare `--help` moved 1.14 s → 1.95 s between nightly runs with no product change.
5. **Make the repository-scale timing test the regression gate.** Rejected on measurement, not
   preference: see the overlapping ranges above. A gate that cannot separate the states it exists to
   separate is noise with a red light.
6. **Incremental catalog update (re-architect the compiler).** Rejected as out of scope; it is the
   only path to 2 s, and it needs its own mission and its own decision record.

## Consequences

- A charter write command at this scale now costs about 10 s where it cost about 17 s. `charter
  generate`, skill rendering and skill installation share the cheaper document comparison and get the
  same reduction for free.
- The exact gate is a **count**, so it runs on every pull request and cannot be flaked by other work
  on a shared runner. A change that adds a document round trip fails immediately and names the count.
- The ratio guard catches a pathologically slow but structurally unchanged write path — a class the
  count cannot see — and records the floor and command medians in its failure message.
- A regression that slows the read floor and the write path alike is invisible to the ratio; the count
  covers the write path, and nothing here covers start-up (the existing start-up tests do).
- **The 6 is a ratchet on today's structure, not a theoretical floor.** Lowering it is a improvement;
  raising it needs a measurement recorded here first.
- The budget is stated per repository size band. A project with a much smaller `charter.yaml` will be
  far closer to the 2 s line, and the count budget applies unchanged.

### Calibration

Machine: a shared development VM with up to twenty concurrent agent runs, Python 3.11.15. Fixture: a
scratch git project holding a copy of this repository's own `.kittify/` (165,004-byte
`charter.yaml`, 264 references) plus `packs/`. Method: one frozen checkout per side, the same launcher
for both, `--repo-root` so the working directory cannot change the work, `XDG_CACHE_HOME` isolated,
rounds alternating base/head order.

| Series | Floor median | Command median | Ratio |
|---|---|---|---|
| before, 5 rounds interleaved | 2.62 s | 16.65 s | 6.35 |
| after, 5 rounds interleaved | 2.77 s | 10.39 s | 3.75 |
| after, 3 rounds (heavier concurrent load) | 2.76 s | 12.67 s | 4.58 |
| before, 2 rounds (lighter load) | 2.95-3.19 s | 11.15-13.09 s | 3.5-4.4 |

The load sensitivity in the last two rows is the evidence for decision 5: the same code produces
ratios from 3.4 to 6.8 depending on what else the machine is doing.

## Questions this record leaves to the operator

1. Is 8× the read floor the right runaway bound, or should it be tighter now that the count carries the
   real gate?
2. Should the incremental-catalog-update work (the only route to 2 s at this scale) be chartered as its
   own mission?
