# Mission Specification: tracer-append routes through the owned Mission checkout

**Mission Branch**: `kitty/mission-tracer-append-owned-checkout-01M6G9FW`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue #7081 — `spec-kitty agent tracer-append` loses an owned Mission
checkout: it resolves `get_main_repo_root()`, writes an untracked `traces/<category>.md`
under the repository root checkout, and refuses `PROTECTED_BRANCH_REFUSED` on `main`. The
command exposes no `--owned-checkout`.

**Guidance recorded** (operator brief): this is a small, single-purpose CLI-surface fix.
Route the tracer append through the canonical owned-Mission fact before selecting its
write surface, and refuse *before* writing on an invalid target. Do not weaken any gate,
do not invent a second ownership resolver, and keep the non-owned path byte-identical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tracer append from an owned checkout writes into that checkout (Priority: P1)

An agent is working an owned `single_branch` Mission in its own linked checkout `P`
(the Mission's `kitty-specs/<slug>/` lives in `P`, and `P` is on the Mission branch, not
on `main`). It runs
`spec-kitty agent tracer-append --mission <handle> --category approach --actor <actor> --entry <text> --json`
from inside `P`. Today the command resolves the repository root `R`, selects `R` as its
write surface, and the tag commit is refused `PROTECTED_BRANCH_REFUSED` because `R` is on
the protected `main`; an untracked `traces/approach.md` is left behind in `R`. After this
mission the finding lands on the Mission's tracer surface in `P`, committed on the
branch `P` is actually on, and `R` is untouched.

**Why this priority**: this is the issue. It is tooling friction that costs every owned
Mission its tracer trail: the three tracer files are the Mission's running log, and the
one command that writes them is unusable from the checkout the Mission actually lives in.

**Independent Test**: invoke the real `tracer-append` entry point from inside an owned
`single_branch` checkout and assert (a) the write is staged and committed under `P`, (b)
the repository root `R` gains no `traces/` file and no commit, and (c) the invocation does
not refuse `PROTECTED_BRANCH_REFUSED`. Fails on unmodified `src`, passes after.

**Acceptance Scenarios**:

1. **Given** an owned `single_branch` Mission in checkout `P` with repository root `R` on
   `main`, **When** `tracer-append --mission <handle>` runs with cwd inside `P`, **Then**
   the entry is appended on `P`'s tracer surface and no refusal is raised.
2. **Given** the same Mission, **When** the caller passes `--owned-checkout P` explicitly,
   **Then** the result is the same as the adopted (flagless) invocation.
3. **Given** a repository with no owned checkout (the ordinary, non-owned case), **When**
   `tracer-append` runs from the repository root, **Then** today's behavior and payload are
   unchanged.

---

### User Story 2 - An invalid owned target is refused before anything is written (Priority: P2)

An operator or agent points the command at a checkout that does not own the named Mission,
or that is the repository root, or that is a lane/coordination worktree. The command
refuses with the canonical owned-checkout refusal (the C2 `{"ok": false, "error": {"code",
"message"}}` envelope) naming the code and the recovery, and it does so before staging,
materialising a coordination surface, or writing any file.

**Why this priority**: the issue explicitly asks to "refuse before writing on an invalid
target". A refusal that leaves untracked residue in the wrong checkout is the second half
of the same defect.

**Independent Test**: invoke `tracer-append --owned-checkout <repository root>` and
`--owned-checkout <unrelated checkout>` and assert exit 1, a typed owned refusal code, no
`traces/` file created anywhere, and the tracer writer never invoked.

**Acceptance Scenarios**:

1. **Given** `--owned-checkout` names the repository root checkout, **When** the command
   runs, **Then** it exits 1 with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` and writes nothing.
2. **Given** `--owned-checkout` names a checkout that does not own the named Mission,
   **When** the command runs, **Then** it exits 1 with a typed owned refusal and writes
   nothing.
3. **Given** the tracer writer raises its existing structured refusals (unmaterialised
   coordination worktree, corrupt UTF-8 traces file, blank actor), **When** the command
   runs through the owned path, **Then** the existing `{"ok": false, ...}` payload shapes
   are unchanged.

---

### Edge Cases

- cwd is a lane worktree of the Mission: flagless adoption deliberately does not adopt a
  lane worktree (`adopt_owned_checkout` returns `None`), so the command keeps today's
  repository-root behavior; an explicit `--owned-checkout` pointing at a lane worktree is
  refused.
- `--owned-checkout` is a relative path: it is resolved against `cwd`, as every other
  owned-capable command does.
- The Mission's `meta.json` carries `commit_to_target: true`: the protection policy must be
  the mission-scoped one (`ProtectionPolicy.resolve_for_owned`) so the Mission's own
  branch is honoured, and no other mission's target is un-protected.
- The Mission handle is unknown or ambiguous: the owned minter's own typed refusal is
  surfaced, not re-derived.
- A non-owned invocation must not gain the `--owned-checkout` behavior by accident: with no
  flag and no adoptable checkout, `repo_root`, policy and target branch are exactly what
  they are today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Owned selector on tracer-append | As an agent, I want `tracer-append` to expose `--owned-checkout` so that I can name the checkout that owns the Mission. | High | Open | [build] | no |
| FR-002 | Flagless adoption from an owned checkout | As an agent working in an owned checkout, I want the command to adopt that checkout without a flag so that the ordinary invocation stops writing into the repository root. | High | Open | [build] | no |
| FR-003 | Write surface resolved from the owned fact | As a maintainer, I want the tracer write (repo root, write branch, protection policy, lock and placement) resolved from the validated owned fact so that a second ownership interpretation never appears. | High | Open | [build] | no |
| FR-004 | Refuse before writing | As an operator, I want an invalid owned target refused with a typed error before any staging or materialisation so that a refusal leaves no residue in the wrong checkout. | High | Open | [build] | no |
| FR-005 | Non-owned path unchanged | As a maintainer, I want the non-owned invocation's payloads, refusal shapes and exit codes unchanged so that existing consumers and pins keep working. | High | Open | [ratchet] | no |
| FR-006 | Writer threads the owned fact | As a maintainer, I want `append_tracer_finding` to accept and thread the owned fact into its write/read seam so that the placement seam does not have to re-derive ownership. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single ownership authority | Zero new callers of `resolve_owned_mission` / `adopt_owned_checkout` outside `specify_cli/cli/commands/_owned_checkout.py`; `tests/architectural/test_owned_checkout_single_authority.py` stays green with an empty allowlist. | Maintainability | High | Open |
| NFR-002 | One validation per invocation | The owned claim is validated exactly once per `tracer-append` invocation (the `resolve_owned_or_refuse` contract). | Performance | Medium | Open |
| NFR-003 | Changed-line coverage | The diff-cover gate's ≥ 90 % on changed lines is met by tests that exercise the production entry point, not by mocks of it. | Reliability | High | Open |
| NFR-004 | No new residue on refusal | A refused owned invocation creates no file, directory, worktree or commit under either checkout, asserted by snapshotting both roots. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the one owned CLI seam | The new flag is declared with `OwnedCheckoutOption` and validated with `resolve_owned_or_refuse`; no bespoke claim parsing, no renamed parameter (the G5 `CLI_CLAIM_INPUT_RULE`). | Technical | High | Open |
| C-002 | Mission-scoped protection policy | The owned path resolves protection through `ProtectionPolicy.resolve_for_owned`; the non-owned path keeps `ProtectionPolicy.resolve`. | Technical | High | Open |
| C-003 | No new topology support | `tracer-append` accepts the lifecycle topology set (`LIFECYCLE_OWNED_TOPOLOGIES`, today `single_branch`); the flag must not widen which topologies lifecycle commands support. | Technical | High | Open |
| C-004 | No full heavy suites | Validation runs the targeted fast suites and the architectural gates only, per `NO_FULL_HEAVY_SUITES_IN_MISSION`. | Business | Medium | Open |

### Key Entities

- **Owned checkout (`P`)**: a linked checkout that owns a Mission; carries the validated
  fact (`owned_root`, `mission_dir`, `write_branch`, `topology`).
- **Repository root (`R`)**: the primary checkout, whose branch is protected (`main`).
- **Tracer surface**: the Mission's `kitty-specs/<slug>/traces/<category>.md`, written
  through the coord-partition write seam.
- **Owned refusal**: the C2 envelope `{"ok": false, "error": {"code", "message"}}` emitted
  by `emit_owned_refusal`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `tracer-append` invocation from inside an owned `single_branch` checkout lands its entry in that checkout and raises no `PROTECTED_BRANCH_REFUSED`; proven through the real CLI entry point on a two-checkout fixture. — [build] · no-op passable: no
- **SC-002**: After that invocation the repository root holds no `traces/` file and no new commit. — [build] · no-op passable: no
- **SC-003**: `tracer-append --owned-checkout <repository root>` exits 1 with a typed owned refusal and writes nothing under either checkout. — [build] · no-op passable: no
- **SC-004**: The non-owned invocation's JSON payload keys, refusal shapes and exit codes are identical to `main`'s. — [ratchet] · no-op passable: no
- **SC-005**: The owned single-authority architectural gate passes with an empty allowlist. — [ratchet] · no-op passable: no
