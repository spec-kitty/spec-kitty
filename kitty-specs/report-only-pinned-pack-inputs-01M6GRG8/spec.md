# Mission Specification: Report-only pinned pack inputs (#7128)

**Mission Branch**: `issue-7128-report-only-pinned-pack-inputs`
**Created**: 2026-11-03
**Status**: Ready
**Input**: Issue #7128 — "[bug] record-analysis --report-only refuses with DIRTY_ANALYSIS_INPUT on the gitignored packs/ trees".

## Context (grounding, before this mission)

The defect **reproduces on current `origin/main`** (`f1e860a17f`, `spec-kitty-cli 4.0.0rc8`).
In a clone that ran the documented `make sync-packs` step, `packs/internal/` holds 67 fetched
files that `.gitignore` lines 251-252 deliberately exclude (`/packs/built-in/`, `/packs/internal/`)
because they are fetched from the commit pinned in the tracked `packs/*.source.yaml`
(`charter.offering.packs.pack_fetch`, `scripts/sync_packs.py`). The project charter registers that
tree as an org pack (`charter_packs.org.packs[0].local_path: packs/internal`), so
`specify_cli.analysis_inputs.collect_material_inputs` walks it into the report's material manifest
— correctly: it *is* an input.

`specify_cli.git.report_transaction.record_report_transaction` then refuses, before writing,
with `DIRTY_ANALYSIS_INPUT`. Two rules contribute the paths:

- `relevant = dirty & (material_paths | {relative})` — index/worktree dirt on a material path;
- `relevant.update(path for path in material_paths if ... is_file() and path not in tracked)` —
  the "material input with no committed state" rule, which is what fires here: the pack tree is on
  disk, is an input, and is *not* in the index by design.

Measured on this clone: `_dirty_paths(repo)` is empty (ignored files are not status entries), the
material-path set has 110 pack paths, and the untracked-material rule adds exactly the 67
`packs/internal/*` files — the reported refusal. `--report-only` is therefore unusable in the
configuration it exists for, pushing operators to the looser mode that skips the material-manifest
transaction (issue body, "Why it matters").

The rule's intent is sound and must survive: an untracked material input has no committed state, so
a report over it cannot be qualified by the commit that records it (the existing
`test_unsafe_state_refuses_without_report_write[ignored_input]` ratchet pins exactly that for
`.kittify/templates/`). What is missing is the *other* way a path can have committed state: a
fetched pack tree is **content-addressed by the tracked pin** (`packs/<name>.source.yaml` records
`commit`, `subtree`, `tree_digest` and `snapshot_sha256`), and
`charter.offering.packs.pack_pin.verify_pack_pin` can prove, offline, that the tree on disk is
byte-for-byte the tree that pin names. Such a tree is clean by construction; nothing about it is
uncommitted.

Related but not superseding: #5125 (relocate `report_transaction` out of `git/`), #5380 (a different
report-only refusal), #7106 (analysis freshness; observed this defect, did not fix it).

## Intent Summary

- **Primary actor**: the mission operator (a maintainer or an agent acting for one) recording an
  analysis over a clone that ran `make sync-packs`.
- **Trigger**: `spec-kitty agent mission record-analysis --mission <slug> --input-file <carrier>.md
  --report-only`.
- **Desired outcome**: the report is committed with its material manifest, instead of the command
  refusing on the fetched pack tree that the tracked pin already content-addresses.
- **Rule/invariant**: the preflight refuses *any* material input whose committed state it cannot
  establish — and a pack tree verified against the pin in the tracked `packs/<name>.source.yaml`
  has committed state, so it is not such an input.
- **Canonical terms**: *material input*, *report qualification*, *pack*, *pin* — as used in
  `src/specify_cli/analysis_inputs.py`, `src/specify_cli/git/report_transaction.py` and
  `src/charter/offering/packs/`.

**Assumptions** (recorded because the discovery interview was skipped non-interactively — the
issue body, its reproduction steps and the operator's brief are the confirmed intent):

1. The fetched-`packs/` layout (`packs/<name>/` ignored, `packs/<name>.source.yaml` tracked) is the
   documented, supported clone shape; `make sync-packs` is a required setup step, not an accident.
2. Refusing to relax the ignore rule is in scope; relaxing it is not.
3. Registering the pin file itself as a material input is out of scope unless it falls out of the
   fix for free.

## User Scenarios & Testing

### User Story 1 - `--report-only` records on a correctly set-up clone (Priority: P1)

An operator clones the repository, runs the documented `make sync-packs`, starts a mission and
records its analysis with `spec-kitty agent mission record-analysis --report-only`. The recording
must commit the report instead of refusing on the fetched pack tree.

**Why this priority**: this is the reported defect and the whole value of the flag; without it the
stricter transactional mode is unreachable in every ordinary developer clone.

**Independent Test**: one end-to-end CLI test on a git fixture whose `packs/internal/` tree is
gitignored, present on disk and matching a tracked pin — `record-analysis --report-only` exits 0 and
commits exactly the report; removing the pin (or dirtying a pack file) on the same fixture makes the
same invocation refuse.

**Acceptance Scenarios**:

1. **Given** a repository whose `.gitignore` excludes `packs/internal/`, whose `packs/internal/`
   tree on disk matches the digests recorded in the tracked `packs/internal.source.yaml`, and whose
   charter registers it as an org pack, **When** `record-analysis --report-only` runs, **Then** it
   exits 0, `commit_status` is `committed`, and the commit's changed paths are exactly the analysis
   report.
2. **Given** the same fixture, **When** any file inside the pack tree is edited so the tree no
   longer matches the pin, **Then** the same invocation is refused with `DIRTY_ANALYSIS_INPUT`,
   naming the edited path, and writes no report.
3. **Given** the same fixture, **When** the pin file is edited (uncommitted) so the on-disk pin is
   no longer the committed pin, **Then** the invocation is refused with `DIRTY_ANALYSIS_INPUT` and
   names the pin path — the exemption never rests on uncommitted authority.
4. **Given** the same fixture, **When** the pack tree matches the pin, **Then** an untracked,
   ignored material input outside any pinned pack tree (for example `.kittify/templates/hidden.md`)
   still refuses — the existing `ignored_input` ratchet is unweakened.

### User Story 2 - The exemption is the pin, not the ignore rule (Priority: P2)

A maintainer must be able to tell, from the refusal and from the code, that the exemption is a
content verification and not "ignored paths do not count".

**Why this priority**: ignoring all ignored paths would silently admit any operator-authored,
gitignored material input — a real hole in report qualification. The fix must not open it.

**Independent Test**: the same fixture with a gitignored, unpinned pack directory (no
`<root>.source.yaml`) refuses; the pinned one succeeds. One fixture, two trees, opposite outcomes.

**Acceptance Scenarios**:

1. **Given** a gitignored `packs/extra/` tree with no `packs/extra.source.yaml` and no matching
   pin, **When** its files are material inputs, **Then** they are still counted as dirty material
   input.
2. **Given** a pin whose `subtree` does not name the pack root being considered, **Then** no
   exemption is granted for that root.

### Edge Cases

- The pack root may be nested (`local_path: packs/internal`, `subdir` set) — the exemption covers
  the resolved pack root and everything under it, by repo-relative prefix, never by string suffix.
- A pack root outside the repository, or one registered under `$ENV` expansion, contributes no
  repo-relative material paths and must not change behaviour.
- A pin that cannot be verified (unknown digest algorithm, absent `snapshot_sha256`, unreadable
  `pack.yaml`, symlink in the tree) yields no exemption — fail closed, never an exception out of the
  preflight.
- `packs/built-in/` is digested as a *package* input (`path: null`) rather than a path set, so the
  exemption must be harmless (and unnecessary) for it.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Pin-verified pack trees are clean input | As an operator, I want `--report-only` to record when the fetched pack tree matches its committed pin so that the documented setup works. | High | Open | [build] | no |
| FR-002 | A modified pack tree still refuses | As a maintainer, I want a pack file that no longer matches the pin to keep refusing so that uncommitted authority is never recorded. | High | Open | [ratchet] | no |
| FR-003 | Uncommitted or absent pin grants nothing | As a maintainer, I want a dirty or missing pin file to grant no exemption so that the read authority is always committed state. | High | Open | [build] | no |
| FR-004 | Unpinned ignored input still refuses | As a maintainer, I want ignored material input outside a verified pack tree to keep refusing so that the exemption cannot become "ignored is clean". | High | Open | [ratchet] | no |
| FR-005 | Exemption is prefix-scoped to the verified root | As a maintainer, I want the exemption applied to the verified pack root's repo-relative prefix only so that a sibling tree cannot inherit it. | Medium | Open | [build] | no |
| FR-006 | Refusal text names the paths | As an operator, I want a refusal to list the offending paths (pack file or pin) so that I can fix the cause without reading the source. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No network during the preflight | Verification is offline: `record-analysis --report-only` performs zero network or remote git operations; only local hashing of the pack tree (measured: the existing 67-file `packs/internal` tree in under 0.4 s). | Performance | High | Open |
| NFR-002 | Fail closed | No pin, malformed pin, digest mismatch, symlink, unreadable file or unparseable `pack.yaml` yields "not exempt" (the strict refusal), never an exception escaping the preflight and never a silent pass. | Reliability | High | Open |
| NFR-003 | No machine-local paths | No absolute or machine-local path enters code, tests, or the report; the exemption is computed from repo-relative paths only. | Portability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakened | No existing test, gate, allowlist or assertion may be deleted, skipped or xfailed; the `ignored_input` refusal case keeps passing unchanged. | Technical | High | Open |
| C-002 | Single authority for the pin | The pin format, its digests and its verification stay owned by `charter.offering.packs.pack_pin`; this mission adds a caller, never a second parser or a second digest. | Technical | High | Open |
| C-003 | Smallest viable diff | The change is confined to the analysis-input/report-transaction seam; no refactor of `report_transaction` or of the pack fetch machinery. | Technical | Medium | Open |
| C-004 | Charter vocabulary | Use the canonical terms for pack, pin, material input, report qualification and mission. | Business | Medium | Open |

### Key Entities

- **Pack pin**: the tracked `packs/<name>.source.yaml` lockfile — repository, commit, subtree,
  tree digest, snapshot digest. Committed state for a fetched pack tree.
- **Pinned pack tree**: the gitignored directory `packs/<name>/` fetched by `make sync-packs`.
- **Material input**: a path whose content the analysis report hashes; the report is qualified only
  over inputs whose committed state the recording commit can establish.
- **Report transaction**: the preflight, render, commit and post-condition checks in
  `record_report_transaction`.

## Success Criteria

- **SC-001**: On a fixture reproducing the reported setup, `record-analysis --report-only` exits 0 and commits only the report; on the same fixture with one pack byte changed, the identical invocation exits 1 with `DIRTY_ANALYSIS_INPUT` naming that file. — [build] · no-op passable: no
- **SC-002**: The pre-existing `ignored_input` refusal case and every `DIRTY_ANALYSIS_INPUT` parameter
  case still pass, with no test edited to accommodate the fix. — [ratchet] · no-op passable: no
- **SC-003**: A dirty pin file on the same fixture refuses, naming the pin path, proving the
  exemption is pinned-committed-state and not path-ignoring. — [build] · no-op passable: no
- **SC-004**: Changed-line coverage stays at or above the 90% diff-cover bar without weakening a
  gate. — [build] · no-op passable: no
