# Phase 0 Research — Per-PR Sonar reuses CI Modules coverage

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Date**: 2026-09-14
**Prior evidence**: `work/4334-sonar-coverage-reuse/findings.md` (research pass),
`work/4334-sonar-coverage-reuse/squad-post-spec.md` (4-lens adversarial squad, adjudicated).

Every claim below is grounded in a file+line, a live GitHub Actions run id, or a command whose
output is quoted. Unsourced statements are labelled as hypotheses per the research-citation rule.

---

## 1. Coverage-report union semantics (underpins the breadth ruling)

**Decision**: Broaden every registry row's `cov_targets` to the top-level packages it can reach.

**Rationale**: Coverage XML consumers merge by **union** — a line marked covered in any report is
covered. SonarCloud merges server-side across a comma-joined `reportPaths`
(`.github/workflows/sonar.yml:232`); `diff-cover` accepts multiple report paths positionally
(`ci-aggregate.yml:410`). So broadening cannot *reduce* the union: a shard that measures code its
own tests never touch contributes zeroes that another shard's ones override.

This is what makes the ruling correct *by construction* rather than by bookkeeping. The rejected
"broaden only the orphaned packages" option would need a package→row mapping that drifts every time
code moves — a new canonical-source violation in a mission whose point is to reduce them.

**Alternatives considered**: surgical per-package broadening (rejected: drift surface); a second
broad-target row (rejected: duplicates execution, the exact thing being removed).

**Open cost (measured in WP01, not assumed)**: `coverage.py` traces more code per shard, so shard
runtime and XML size grow. NFR-002 budgets ≤3 min on the longest affected shard against a 30-minute
job cap (`module-tests.yml:98`). Two rows already carry comments documenting that measured
call-phase durations *undercount* per-test fixture overhead (`ci-module-registry.yml`, the `upgrade`
and `agent` rows), so this must be measured on CI, not extrapolated from a local run.

---

## 2. The measurement-breadth defect (why FR-013 exists)

**Finding** (squad, orchestrator-verified): 16 of 17 registry rows declare **narrow** `cov_targets`;
only `core_misc` is broad (`specify_cli`, `glossary`, `mission_runtime`).

```
58 of 72 src/specify_cli subpackages are measured ONLY via core_misc's broad --cov
  — auth(37 files), tool_surface(41), core(48), compat(19), tracker(18),
    migration(18), audit(16), skills(16), session_presence(16), retrospective(15), …
core_misc's test_dirs cover 7 directories, which do not exercise most of them.
```

Mechanism: `module-tests.yml:239-243` builds `--cov=<target>` flags from the row's `cov_targets`.
When a `tests/cli` test executes `src/specify_cli/retrospective/writer.py`, the `cli` shard's
`--cov=specify_cli.cli` drops the hit. The file then appears only in `core_misc`'s reports, where it
reads uncovered because its exercisers live elsewhere.

**Quantified** (delegate, from the live reconciled artefact of run `34830199996` vs a reproduced
fast-tier run): matrix union 71,070 covered statements (55.15%); retiring step 42,933 (33.31%);
**4,391 covered only by the retiring step**, of which the two new rows recover 1,583 and **2,808
would be lost permanently** without FR-013.

**Caveat recorded**: the two coverage sets come from different heads, so small per-file deltas may be
drift. The headline magnitudes are far beyond plausible drift.

---

## 3. Trigger semantics — the three mechanism changes

**Decision**: express the report's trigger condition in `workflow_run` vocabulary, with three
explicit conjuncts.

**Rationale**, each grounded:

| Property | Present mechanism | Mechanism after the move |
|---|---|---|
| Not on the primary branch (C-001) | `if: github.event_name == 'pull_request'` (`ci-quality.yml:144`) | **Unsatisfiable** under `workflow_run` — that expression is always false. `collect`'s `if:` (`ci-aggregate.yml:74-78`) filters only on `conclusion`, and `ci-modules.yml:26-27` fires on push to main. Needs `github.event.workflow_run.event == 'pull_request'`. |
| No fork reporting (C-003/NFR-004) | Platform-enforced: secrets withheld on fork `pull_request` | **Gone.** `workflow_run` runs in base-repo context with full secret access regardless of origin. Needs an explicit same-origin conjunct. `aggregate_source.py` records no origin signal — verified: `source.json` carries `repository, run_id, run_attempt, head_sha, base_sha, tested_sha, pr_number` and **never** `head_repository`. |
| Complete measurement only (FR-007) | n/a | `collect` writes `complete=false` **before** `sys.exit(1)` (`ci-aggregate.yml:287-297`) and the artefact uploads anyway (`:301` `if: always()`, `:306` `if-no-files-found: warn`). The condition must require `needs.collect.result == 'success' && needs.collect.outputs.complete == 'true'`, **without** `always()` — deliberately *not* mirroring `diff-cover`'s shape. |

**Hypothesis, not established**: that `workflow_run` grants secrets on fork-originated runs is taken
from the platform contract, not from an observed run in this repository. It is the documented
behaviour and the basis of the standard advisory, but no delegate produced a live run proving it
here. **WP02 must not treat it as verified** — the guard is required either way, and its absence is
the unsafe direction.

---

## 4. Untrusted-source handling

**Decision**: trusted default-branch checkout stays the working directory; the validated
`tested_sha` is fetched into a subdirectory; every `sonar.*` setting is passed as an explicit `-D`
argument resolved from the trusted tree.

**Rationale**: `ci-aggregate.yml:14-15` states the invariant plainly — *"the trusted default-branch
checkout remains in place"* — and the `collect` design honours it by treating PR content as **data**
(`aggregate_source.py:62-72` uses `git fetch` + `git show`, never a checkout). The scanner however
reads `sonar.sources=src` from the working tree, and `sonar-project.properties` from the checkout.
Leaving that file PR-controlled would let the change under review redirect `sonar.projectKey` /
`sonar.organization` — violating NFR-005 regardless of the same-origin guard, because same-repo
branches are routinely pushed by agents in this programme.

**Alternatives considered**: check out the PR tree and restore config from a trusted ref (rejected:
relies on enumerating every file the scanner might read); scan the trusted tree and accept
mis-projection (rejected: NFR-008 — produces a plausible, silently wrong report).

**Open question for WP02**: whether `sonar.projectBaseDir` pointed at a subdirectory interacts
correctly with coverage XML paths, which are recorded `relative_files = true` against the merge
tree. This is the highest-risk unknown in the mission and is why WP02 carries the largest
verification burden.

---

## 5. PR identity provenance

**Decision**: take the change identity from `ci-aggregate-source`'s `source.json`, never from
`github.event.workflow_run.pull_requests[]`.

**Rationale**: `aggregate_source.py:44-62` derives `pr_number` from the **immutable**
`referenced_workflows` merge ref and explicitly documents why the live projection is refused —
*"pull_requests[] is a LIVE PR projection: after a push its head/base change even on old run
records"* (`:45-47`). Using the projection would attribute a correct measurement to a stale
identity: the same defect class as NFR-006, on a field NFR-006 does not cover.

`source.json` supplies the key. The head branch **name** and base branch **name** are not in it; a
single authenticated read keyed on the already-validated `pr_number` yields `head.ref`, `base.ref`
and `head.repo.full_name` from a trusted API in one call — strictly better than the event payload
the surrounding code deliberately avoids.

---

## 6. Non-blocking enforcement

**Decision**: terminal verdict job in `ci-aggregate.yml` mirroring `ci-quality.yml`'s pattern.

**Rationale**: three independent surfaces can block, and `continue-on-error` covers only the first.
(i) the job's own conclusion; (ii) the workflow run conclusion, which
`scripts/ci/fleet_verdict.py:36` folds in via `AGGREGATE = "ci-aggregate.yml"` and `classify()`
(`:86-95`) renders `red` on `failure`/`timed_out`; (iii) branch protection, verified live as
`["Clean install verification"]` only — i.e. currently permissive, outside the repository, and
pinnable by no test.

A terminal verdict job gives the workflow a seam where "excluded from the verdict" is **declared**
and therefore assertable, the way `NON_BLOCKING_ALLOWLIST` declares it for `ci-quality.yml`.

**Unverified, flagged for WP02**: whether job-level `continue-on-error: true` keeps the *run*
conclusion green and therefore keeps `fleet_verdict.classify()` out of `red`. Platform docs say yes;
no delegate confirmed it against this repository's `workflow_run` records. Since SC-006 is absolute,
WP02 must confirm empirically or add the explicit exclusion.

---

## 7. Supply-chain posture (DIR-051)

**No dependency is added, upgraded, or removed by this mission.** The two SonarSource actions stay
SHA-pinned at their current commits. The relevant risk is **pin-parity drift**:
`tests/release/test_sonar_workflow.py:305` asserts both surfaces pin the *same* commits, and its
second operand is resolved from `ci-quality.yml` (`:272`, `:280-283`). Relocating the job breaks that
operand, and the naive fix (delete the assertion) would silently drop the anti-drift guarantee —
exactly the C-005 failure mode. Disposition: **relocate**, re-pointing the parity assertion at the
new host.

Secondary: a verbatim relocation would carry `actions/checkout@v4` and `astral-sh/setup-uv@v5`
(`ci-quality.yml:161`, `:169`) — floating tags — into a file whose every other step is SHA-pinned
(`ci-aggregate.yml:84`). WP02 pins them.

**Adversarial evidence**: the post-spec squad is the challenge pass for this mission's
security-impacting decisions. Dispositions:

| Contested finding | Disposition |
|---|---|
| Fork guarantee evaporates under `workflow_run` (3 lenses) | **changed** — FR-011 added; A-004 rewritten to state the new mechanism |
| Analysis config readable from the change under review | **changed** — FR-012 added with the trusted-`-D` mechanism |
| Analysed tree may differ from measured tree | **changed** — NFR-008 added |
| Report may publish on a partial measurement | **changed** — condition specified without `always()` |
| `continue-on-error` insufficient for "any outcome" | **changed** — terminal verdict job (plan DM) |
| Concurrency `cancel-in-progress: true` is wrong for a publisher | **deferred_with_rationale** — inherited workflow-level property; a job cannot opt out, and the residual window shrinks from ~22 min to ~17 s. Recorded, not fixed here. |
| Concurrency key is a branch name, not a PR identity | **deferred_with_rationale** — pre-existing in `ci-aggregate.yml`; out of scope, recorded for a follow-up |
| Fourth topology option never offered to the operator | **accepted** — recorded in the tracer files; rejectable on billed-idle-minutes grounds, and the record now makes the rejection auditable |

No contested finding was silently dropped.

---

## 8. Prior art — the mission is aligned, not novel

`kitty-specs/ci-pipeline-reinstatement-01M1X35E/sonar-identity-verification.md:129-149` documents
this exact promotion path and recommends the reuse: *"No new artefact contract … is required."*
`grep -rin "sonar" docs/adr/` returns **zero hits** — no ADR constrains this. No prior attempt,
revert, or wontfix exists. `ci-quality.yml` is flagged interim (#830 Phase-1); `ci-aggregate.yml` is
`introduced`/permanent — the mission moves work from the shorter-lived surface to the longer-lived one.

**Note the caveat this cuts both ways**: that same document (`:147`) pre-bakes the *false* fork
premise — *"a fork PR still has no access to repository secrets"* — into the documented path. The
recommendation is sound; its stated safety rationale is not. FR-011 exists because of this.

---

## 9. Issue landscape

| Issue | State | Relationship |
|---|---|---|
| **#4334** | OPEN P0 | This mission. |
| **#825** | OPEN P1, assigned | *"Restore push-time SonarCloud"*. **Reconciled, not conflicting.** Filed 2026-04-27, before the scheduled `sonar.yml` existed (#3995); its ask was then the only route to a primary-branch analysis, a goal the nightly now serves. Live content is quality-gate backlog → #2969/#2970. C-001 stands. |
| **#4248** | OPEN P2 | *"SonarCloud PR scans cannot resolve current GitHub pull requests"* — one of three observed exit-3 causes, on the **old** project key whose ALM binding is broken. #4325 retargeted to the new key, which is `BOUND`. Partly overtaken; not this mission's to close. |
| **#4011** | OPEN | `docs/development/reference/coverage-signals.md` is factually wrong today. FR-010/C-010 make it in-scope for WP05. |
| **#2969 / #2970** | OPEN | The real content of #825's backlog. Untouched here. |
| *(to file)* | — | The Automatic-Analysis conflict on `spec-kitty_spec-kitty`. FR-009 requires the handle before approval, because the issue-matrix verdict gate needs a real `#NNN`. |

---

## 10. What remains genuinely unknown

Carried into WP-level verification rather than guessed:

1. **`sonar.projectBaseDir` + relative coverage paths** (§4) — the mission's highest-risk unknown.
2. **Whether `continue-on-error` keeps the run conclusion green** for `fleet_verdict` (§6).
3. **Real CI cost of broadened coverage targets** (§1) — must be measured on CI.
4. **Whether tonight's scheduled run hits the Automatic-Analysis wall** on the new key — probable
   (`sonar-project.properties:8` now names it) but not yet observed.
5. **Whether `workflow_run` secret exposure on fork-origin runs reproduces here** (§3) — the guard is
   required regardless; this only affects how the evidence is worded.
