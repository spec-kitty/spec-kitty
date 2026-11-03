# Implementation Plan: Report-only pinned pack inputs (#7128)

**Branch**: `issue-7128-report-only-pinned-pack-inputs` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/spec.md`

## Summary

`record-analysis --report-only` refuses with `DIRTY_ANALYSIS_INPUT` in any clone that ran
`make sync-packs`, because the preflight's "material input with no committed state" rule counts the
gitignored, pin-fetched `packs/<name>/` tree as dirty. The plan adds exactly one exemption: a pack
tree whose content verifies against the pin recorded in the **tracked and clean**
`packs/<name>.source.yaml` is clean by construction, so it is not a dirty input. Every other
untracked/ignored material input keeps refusing, unchanged.

## Technical Context

**Language/Version**: Python 3.11 (repository `>=3.11`), src-layout under `src/`
**Primary Dependencies**: `charter.offering.packs.pack_pin` (pin model + `verify_pack_pin`),
`kernel.git` (`status_entries`, `tracked_paths`), `charter.drg.load_pack_registry` (already imported
by `analysis_inputs`), `mission_runtime` / `specify_cli.analysis_report` (unchanged)
**Storage**: Git. The exemption is derived state: pin file (committed) + pack tree (fetched, ignored)
**Testing**: pytest. New end-to-end cases in
`tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py` (real git fixture, real
`CliRunner` invocation of `record-analysis`, marked `integration` + `git_repo`); fast helper cases in
a unit module. No full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION)
**Target Platform**: Linux/macOS/Windows CLI (path handling is POSIX repo-relative everywhere)
**Project Type**: single project (Python CLI + libraries)
**Performance Goals**: the exemption costs two git listings plus one tree digest per candidate
pack — measured 8 ms for this repository's 67-file `packs/internal` tree; no network
**Constraints**: offline; fail closed on every doubt; no machine-local absolute path in code or logs
**Scale/Scope**: at most a handful of registry packs per repository; ~20 lines of production code
across two modules, plus tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
| --- | --- | --- |
| Single canonical authority | PASS | The pin format, its digests and its verification stay in `charter.offering.packs.pack_pin`; the plan adds a caller, never a second parser (C-002) |
| Locality of change / smallest viable diff (DIRECTIVE_024, `change-apply-smallest-viable-diff`) | PASS | One predicate beside the material-input authority, one filter in the preflight; no refactor of `report_transaction` or the fetch machinery (C-003) |
| ATDD-first (DIRECTIVE_034) | PASS | Red-first: the end-to-end CLI test must fail on `main` before the fix; negative controls ship with it |
| No gate weakened (C-001) | PASS | The `ignored_input` refusal case and every `DIRTY_ANALYSIS_INPUT` parameter case stay byte-identical and passing |
| Proof trail | PASS | Reproduction numbers and measurements in `research.md` (D1–D6); tracers in `traces/` |
| Pre-existing failure reporting | N/A at plan time | CI reds in the shared fleet are classified at PR time and named in `## Deferred` |
| `__all__` convention | PASS | `analysis_inputs` gains one public predicate, added to any module-level export list it belongs to |

No requirement in this plan needs an external contract change, a new pack tier, or a schema change.

## Project Structure

### Documentation (this mission)

```
kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/
├── plan.md              # This file
├── research.md          # Phase 0: reproduction + measurements (D1-D6)
├── data-model.md        # Phase 1: the exemption as a derived relation
├── quickstart.md        # Phase 1: how to reproduce and verify by hand
├── spec.md              # Mission spec (FR/NFR/C/SC)
├── reasons-canvas.md    # SPDD canvas
├── issue-matrix.json    # #7128
└── tasks.md             # Phase 2 (not created here)
```

No `contracts/`: this mission changes no externally visible contract (no CLI flag, JSON key, exit
code or file format changes — the only new observable is that a previously refused invocation now
succeeds in the documented setup, which the spec's acceptance scenarios pin).

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── analysis_inputs.py          # + pinned_pack_tree_roots(repo_root)
│   └── git/
│       └── report_transaction.py   # untracked-material rule subtracts verified pack roots
tests/
├── specify_cli/
│   ├── cli/commands/agent/
│   │   └── test_analysis_report_transaction.py   # + end-to-end red-first cases
│   └── test_analysis_inputs_pinned_packs.py      # + fast predicate cases
```

## Implementation Concern Map

- **IC-01 — The predicate.** A read-only function that answers "which material pack trees are
  exempt, and why". Owns the pin↔tree convention (`<pack root>.source.yaml`, `pin.subtree`), the
  committed-authority check (pin tracked and clean), the digest verification
  (`verify_pack_pin`), and fail-closed behaviour on every error path.
- **IC-02 — The preflight filter.** In `record_report_transaction`, the untracked-material rule
  subtracts only the exempt roots, by repo-relative prefix, and nothing else about the four dirty
  rules changes.
- **IC-03 — Red-first end-to-end proof.** One fixture that reproduces the reported clone shape
  (gitignored `packs/<name>/`, tracked pin, registry entry, matching digests), one positive case and
  three negative controls on that same fixture (modified pack byte, dirty pin, unpinned ignored
  input), all through the real CLI.
- **IC-04 — Fast predicate cases.** Unit coverage for the branches the end-to-end fixture cannot
  cheaply reach: pin `subtree` mismatch, pin with an unverifiable digest, missing pin, pack root
  outside the repository, and the prefix scoping (a sibling directory with a common string prefix
  is not exempt).

## Phase 0: Outline & Research

Complete: `research.md` D1–D6. Decisions carried into design:

1. Take the issue's second remedy (pin-verified tree is clean), not the first (ignore ignored
   paths) — the first would admit operator-authored ignored material input.
2. "Committed pin" is proved by the pin file being tracked **and** clean; no second pin parser and
   no `HEAD`-blob plumbing.
3. Generalise over `load_pack_registry(root).packs` → `effective_root(root)`; never hard-code
   `packs/internal`.

## Phase 1: Design

`data-model.md` states the exemption as a derived relation over (pack root, pin file, tree digest)
and its fail-closed arms; `quickstart.md` gives the manual reproduction and the verification
commands. Re-ran the Charter Check after design: unchanged, all PASS.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| The exemption becomes "ignored is clean" through a later edit | FR-004/SC-002 pin the existing `ignored_input` refusal; the predicate returns roots, not a boolean, so a caller cannot blanket-disable the rule |
| Pin verification is slow on a large pack | Measured 8 ms on the real 67-file pack; verification runs only when an untracked material path exists, and only for registry packs |
| A registry pack root outside the repository or behind `$ENV` expansion | The predicate skips any root it cannot express as a repo-relative path; `collect_material_inputs` already refuses external mutable authority |
| A pack tree edited in place passes | `verify_pack_pin` compares two independent digests (declared set, LF-normalised; every file, raw bytes), so a byte change fails |
| Test fixture drifts from the real pack shape | The fixture is built with the same `clean_tree_digest`/`full_tree_digest`/`write_pack_pin` calls that `make sync-packs` verifies with; no hand-written digest |

## Complexity Tracking

No charter violation to justify. One new public predicate, one filtered generator, four new tests.
