# Contract — the per-change reporting job

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Owner**: WP02 · **Host**: `.github/workflows/ci-aggregate.yml`

This mission adds no HTTP API. Its externally-visible contracts are the **conditions under which a
report may be produced** and the **provenance of every input**. Each clause below maps to a spec
requirement and is independently assertable — the mission's gates assert clauses, never the whole
condition string, so dropping one clause is caught.

## C1 — Execution condition (all conjuncts required)

| # | Conjunct | Requirement | Why not the obvious thing |
|---|---|---|---|
| 1 | triggering run's event is a pull request | FR-014, C-001 | `github.event_name == 'pull_request'` is **always false** under `workflow_run`. A verbatim port passes its gate over a job that never runs. |
| 2 | triggering run's head repository equals this repository | FR-011, NFR-004, C-003 | Secret withholding no longer provides this. `source.json` carries no origin field. |
| 3 | the assembly job succeeded | FR-004, FR-007 | — |
| 4 | the assembly reported a **complete** set | FR-007, NFR-006 | The artefact uploads even on failure, so presence ≠ completeness. |
| 5 | the quality-service credential is present | FR-008 | Absent ⇒ skip with an advisory notice, never fail. |

**`always()` is prohibited on this job.** The sibling change-coverage gate uses `always()` plus an
internal re-check; copying that shape without the re-check publishes a partial figure that reads as a
coverage regression.

## C2 — Input provenance

| Input | Source | Prohibited source |
|---|---|---|
| coverage reports | the reconciled per-change set | any other run's reports; the stale fallback |
| change identity | `source.json` `pr_number` (validated against the immutable merge ref) | `workflow_run.pull_requests[]` — a mutable projection the producing script explicitly refuses |
| analysed revision | `source.json` `tested_sha` | the trusted checkout's own revision; `github.sha` |
| head/base branch names, origin repository | one authenticated read keyed on the validated `pr_number` | the event payload |
| every analysis setting | the **trusted** checkout, passed explicitly | any file read from the change under review |

## C3 — Analysis-configuration trust (FR-012, NFR-005)

The scanner must not consume a configuration file supplied by the change under review.

**Mechanism (corrected 2026-09-14 — see the refutation below): keep the analysis base directory at
the trusted checkout root and replace ONLY the two analysed trees in place.**

```
fetch the change's tested revision
verify the fetched revision equals the recorded tested revision, and FAIL LOUD on mismatch  (NFR-008)
remove, then restore, exactly the two analysed trees from that revision
```

Removing before restoring is required so deletions in the change are honoured rather than leaving
stale files behind. Trust becomes an **allowlist of two replaced paths**: the analysis configuration,
the build configuration, and the workflow definitions all stay at trusted content.

### ⚠️ The subdirectory design is REFUTED — do not reintroduce it

An earlier version of this contract specified placing the change's sources in a subdirectory and
pointing the analysis base directory at it. That is **wrong, in the exact way it was trying to be
right**: the scanner locates its configuration file **relative to the base directory**, so pointing
the base directory at the change's subtree makes it load **the change's own configuration** — the
precise FR-012/NFR-005 breach the subdirectory was chosen to prevent.

It also traded a *file*-enumeration problem for a *key*-enumeration problem: explicit arguments
override only the keys they name, while a contributor-authored configuration file can set keys the
trusted side never passes.

Recorded here rather than deleted, because the reasoning is the useful part: a mechanism can defeat
its own purpose through a detail of where a tool looks for its configuration.

**Open risk retired**: whether a base-directory shift breaks coverage path resolution was ranked this
mission's largest unknown. It was resolved **negative** — coverage reports carry an empty `<source>`
and repo-root-relative filenames, so both roots move together. The mechanism above sidesteps the
question entirely by not shifting the base directory at all.

## C4 — Non-blocking guarantee (NFR-003, SC-006)

Three surfaces can block; the guarantee must hold at all three.

| Surface | Mechanism |
|---|---|
| job conclusion | job-level continue-on-error |
| workflow-run conclusion (read by the aggregate verdict script) | the terminal verdict job explicitly excludes this job |
| branch protection | outside the repository; currently permissive. **Declared, not claimed** — no test can pin it. |

The terminal verdict job is what makes "excluded" *declarable*, and therefore assertable.

## C5 — Regression battery (NFR-007, SC-007)

A permanent in-tree fault-injection battery. Each mutation must be demonstrated **red**:

| # | Mutation | Why it is in the battery |
|---|---|---|
| 1 | reintroduce the retiring step in its canonical form | the literal regression |
| 2 | reintroduce it inlined, with no shared-target reference | defeats a literal-string rule |
| 3 | reintroduce it behind indirection (a shell wrapper or script) | defeats both |
| 4 | reintroduce it in a **new** workflow file | closed candidate lists miss net-new files |
| 5 | remove the non-blocking declaration | NFR-007's second half; asserted by nothing today |
| 6 | remove the same-origin conjunct | FR-011 / SC-008 |

**Non-vacuity floor**: the rule's workflow set must be asserted non-empty **and** to include the new
host. The existing substrate is documented as blind to the retiring step's invocation form, and a
sibling assertion currently passes while that step is present in the file — so a rule built naively
on it is vacuous by construction.

## C6 — Documentation-only changes

The retiring step runs one always-on check unconditionally on every change; its replacement home is
code-scoped. Either preserve that check's unconditional execution or record the reduction
deliberately. Silent loss is not acceptable.
