# Research: CI down-route of prose-only .py diffs

## R1 — The routing surface is TWO independent, content-blind mechanisms (brownfield)

**Decision**: The down-route must act in **both** `ci-modules.yml` and
`ci-router.yml`, because they route the same PR by two different mechanisms.

**Findings** (verified in `.github/workflows/`):
- `ci-modules.yml` computes a `git diff --name-only base..head` list and feeds it
  to `scripts/ci/gate_selection.select_modules(...)` → the **per-module test
  matrix**. This is a Python seam that accepts a path list — reducible.
- `ci-router.yml`'s `changes` job runs `dorny/paths-filter` over **raw** changed
  paths, emitting one boolean per group. Those booleans gate:
  - `architectural-heavy` (`if:` = OR of all 20 src-backed groups) — the heavy battery,
  - `tests-merge` / `tests-status` / `tests-cli` / … (per-group code shards),
  - `tests-docs` (`if: docs == 'true'`) — the CLI-reference / help-drift / docs-freshness lane.
  dorny is content-blind and cannot be made content-aware.

**Consequence**: a prose-only `.py` change lights its dorny group (e.g. `cli`), so
it triggers `architectural-heavy` **and** `tests-cli` in `ci-router.yml` **and**
the `cli` module shard in `ci-modules.yml`. Reducing the `ci-modules.yml` list
alone (the F2 seam) only removes the **module matrix**; the arch battery and the
per-group shards in `ci-router.yml`, plus the skipped docs lane, are untouched.

**Rationale**: therefore `ci-router.yml`'s `changes` job must compute a new
aggregate output `prose_only` (git is available after `actions/checkout`), and:
- `architectural-heavy.if` gains `&& needs.changes.outputs.prose_only != 'true'`,
- each `tests-<code>` shard `if` gains the same guard,
- `tests-docs.if` becomes `docs == 'true' || prose_only == 'true'` (F4 positive
  enablement — a docstring change feeds `--help`, so the CLI-reference freshness
  lane must run).

**Alternatives considered**:
- *ci-modules reduction only* (the issue's/F2's original framing): rejected —
  leaves the arch battery and per-group shards running; does not fix the docs
  inversion. Incomplete.
- *Make dorny content-aware*: impossible; dorny reads paths only.

## R2 — `prose_only` never fights the FR-004 catch-all (CORRECTED by squad Renata HIGH-1)

**Decision**: `prose_only` is a purely *subtractive* signal, enforced by the
WIRING, not by the classifier: every down-routable lane's `if:` keeps its existing
gate ANDed (`(existing gate) && prose_only != 'true'`), so `prose_only` can only
remove an already-selected code lane and the `unmatched` compute stays untouched.

**Retraction**: the original R2 argued "an unmapped `src/**` path is by definition
not proven prose-only, so the two signals can never disagree." **That is false.**
An unmapped `src/**` `.py` whose only change is a docstring IS proven prose by
`is_prose_only`, so a *pure* aggregate could report `prose_only=true` while
`gate_selection.unmatched_src` wants run-all — a widening disagreement. Safety
therefore does **not** come from the classifier; it comes from (a) the classifier
classifying `.py` *content* only and never self-classifying whether a path is
doc/corpus/mapped (see R9), and (b) the wiring keeping every guard subtractive.

## R3 — The `tests/docs` lane is the correct F4 target

**Decision**: force the `tests-docs` lane on for a prose-only PR.

**Findings**: `tests/docs/` contains `test_build_cli_reference.py`,
`test_check_cli_reference_freshness.py`, `test_check_docs_freshness.py`,
`test_check_slash_command_freshness.py` — the CLI-reference/help-drift/docs
freshness gates. Typer derives `--help` from function docstrings, so a
docstring-only change *can* flip these gates; they must run.

## R4 — Doctest gap → doctest-bearing docstring changes are treated as CODE (fail-closed refinement)

**Decision**: extend the classifier so a change to a docstring **containing a
doctest prompt (`>>>`)** on either side is classified as **not prose-only**.

**Rationale**: `tests/docs/` has no dedicated doctest runner; doctests embedded in
module docstrings execute (if anywhere) inside the module matrix, which the
down-route skips. Rather than build a doctest lane, fail closed: a docstring whose
doctest content changed routes fully, so a `>>>` example is never skipped. This is
the same philosophy as the `# type:` guard (R5) — narrow, provable, safe. It
refines FR-002 (semantically-live content) beyond comments to doctest docstrings.

**Alternatives considered**:
- *Retain a dedicated doctest pass in the down-route set*: heavier, and would need
  a new lane; rejected for v1 in favor of the fail-closed refinement.

## R5 — `# type:` / `# noqa` / `# pragma` deltas are code (F3)

**Decision**: parse both sides with `ast.parse(..., type_comments=True)` and
additionally compare the set of `# type:` / `# noqa` / `# pragma` comments via a
`tokenize` pass; any delta ⇒ not prose-only.

**Rationale**: default `ast.parse` discards type comments; a bare AST compare
returns identical trees for a changed `# type:` annotation → false prose-only →
mypy skipped on a real type change. `# noqa`/`# pragma` similarly steer lint and
coverage. The classifier must see them.

## R6 — Supply-chain posture

**Decision**: N/A. No dependency is added, upgraded, or removed. The classifier
uses only the Python standard library (`ast`, `tokenize`, `io`). Recorded as
examined-and-not-applicable per the planning supply-chain section (silence is not
compliance).

## R7 — Adversarial evidence

No security-impacting dependency decision was made, so the mandatory
supply-chain adversarial pass does not apply. A general adversarial-squad
challenge ran at the post-tasks point-cut (R10 dispositions below).

## R8 — Coverage gate is a THIRD consumer surface (squad Paula F1; operator chose "full + honest")

**Decision**: a proven prose-only `.py` is treated as "not code for CI"
uniformly — excluded from the `ci-aggregate.yml` diff-cover diff patch, exactly
as a docs-only PR's (nonexistent) `.py` diff is.

**Mechanism / finding**: `ci-aggregate.yml`'s diff-cover ≥90% gate follows
"Approach-C": a module missing from `current` is fail-closed if it was SELECTED,
but **backfilled from the last successful run if UNSELECTED**, on the invariant
"the diff lives entirely in selected/fresh modules." Reducing the module matrix
for a docstring-changed module makes a *changed* module UNSELECTED, so its
coverage is backfilled STALE; `diff-cover` maps the head diff's docstring lines
(coverable statements in coverage.py) against the stale XML → reads them uncovered
→ **false-red on a docstring PR** (a new false-fail #4437 forbids).

**Resolution**: exclude proven-prose-only `.py` from the diff patch diff-cover
scores (WP03), so there is no coverable changed line to score — same trivially-green
path a docs-only PR already takes. A prose-only line genuinely needs no coverage.

**Alternatives considered**: (A) keep the module matrix (coverage stays fresh),
down-route only the arch battery — rejected by operator as forfeiting ~90% of the
saving that motivates #4842. (B) denominator `--exclude` hack — rejected as less
principled than excluding the file from the scored diff.

## R9 — Classifier is `.py`-content-only; F2 phantom-group avoided by a separate job (squad Renata HIGH-1, Paula F2/F3)

**Decision (scope)**: `is_prose_only(base, head)` classifies `.py` *content* only.
The doc/corpus/mapped-vs-unmapped classification of a *path* stays in the wiring,
which already reuses `gate_selection` (imports `yaml`/`fnmatch`, does IO — which the
pure classifier must not). This closes the C-001-vs-NFR-001 tension: no second path
map in the pure module.

**Decision (F2 mechanism)**: expose `prose_only` from a SEPARATE job (e.g.
`prose-scan`), referenced as `needs.<prose-job>.outputs.prose_only`. `gate_selection.py`'s
`_GROUP_REF = r"needs\.changes\.outputs\.([A-Za-z0-9_]+)"` only captures references
under the `changes` job, so a separate-job output is invisible to the group parser
and the SC-004 oracles — and `gate_selection.py` stays untouched (FR-007). The new
job must be added to each down-routable job's `needs:` and to the `router-gate`
terminal aggregator's `needs:`; the aggregator already treats an `if:`-skip as pass.

## R10 — Adversarial-squad dispositions (post-tasks point-cut)

Two bounded read-only lenses (paula-patterns architecture, reviewer-renata
correctness). Every contested finding is dispositioned; none dropped silently.

| Finding | Severity | Disposition | Where resolved |
|---------|----------|-------------|----------------|
| Paula F1 — coverage-gate stale backfill → false-red | blocker | **accepted** → operator chose full+honest | R8, FR-009, WP03 |
| Paula F2 — `prose_only` phantom routing group reds oracles | blocker | **accepted** (changed mechanism) | R9, WP02 |
| Paula F3 / Renata HIGH-1 — pure aggregate can't classify paths; R2 false | blocker | **accepted** (changed) | R2 retraction, R9, WP01/WP02 |
| Renata HIGH-2 — docstring `__doc__` runtime consumers beyond doctest/help | high | **accepted** (residual risk + suite grep) | WP02, design-decisions |
| Renata HIGH-3 — guard order (no early return True) | high | **accepted** | contract, WP01 |
| Renata HIGH-4 — whitespace-insensitive `#type:`/`#noqa` matching | high | **accepted** | contract, WP01 |
| Renata MEDIUM-1 — encoding cookie / shebang unguarded | medium | **accepted** | contract, WP01 |
| Renata MEDIUM-2 — strip only `body[0]` bare `Constant(str)` | medium | **accepted** | contract, WP01 |
| Paula F4 — golden re-encodes routing / grades own homework | should-fix | **accepted** (hand-pin + extend to ci-modules/ci-aggregate) | WP02/WP03 |
| Paula F5a — FR-004 text omits code shards | nice-to-have | **accepted** | spec FR-004 |
| Paula F5b — `authoritative_surface` imprecise (spans code+test) | cosmetic | **deferred_with_rationale** — owned_files don't overlap; single-dir field is advisory only | — |
| Renata LOW — add `# ruff:`/`# fmt:`/`# mypy:`/`# pyright:`/`# isort:` guards | low | **accepted** (defense-in-depth; cheap) | contract, WP01 |
| Renata LOW — BOM/CRLF/whitespace-only; `ast.dump` numeric equivalences | info | **accepted as safe** — always-on ruff catches lint-visible whitespace; numeric/str-repr equivalences are semantically identical | — |
