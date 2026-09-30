---
title: 'Repo-Coupling Audit of Built-In Doctrine'
description: Classified audit of repository-local references in shipped built-in doctrine, the gate that currently requires one, and the relocation order for follow-on missions.
doc_status: deprecated
updated: '2026-07-28'
type: explanation
related:
- docs/development/how-to/review-gates.md
- docs/archive/plans/doctrine/charter-activation-reachability-assessment.md
- docs/adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md
---
# Repo-Coupling Audit of Built-In Doctrine

> **Retired (deprecated).** Relocation shipped via merged mission `doctrine-consumer-surface-missions-extraction-01KZ6G6H`. Preserved as a historical record.

**Rule being audited** — [`review-gates.md`, "Shippable doctrine"](../../../development/how-to/review-gates.md):
built-in doctrine under `src/doctrine/**/built-in/` MUST be valid and actionable
in a consumer repository that activated the pack but has **no** access to the
spec-kitty source tree, CI, or tooling.

**Operator ruling, 2026-07-28.** Built-in doctrine is repository-agnostic.
Doctrine that pertains only to this repository belongs in a committed
non-`built-in` tier. This is a **customer-facing bug class**, not hygiene — the
`asset` doctrine kind was created as its direct consequence, and WP-transition
gates hit the same class before that.

This page is the classification that follow-on missions should work from, so
each of them inherits a decision instead of re-deriving one (and getting it
differently).

## 1. Counts, and why the raw number is a trap

The documented quick-check, run on this branch:

```console
$ grep -rEn 'scripts/|\.github/|src/specify_cli|tests/' src/doctrine/*/built-in/ | wc -l
84
$ grep -rlE  'scripts/|\.github/|src/specify_cli|tests/' src/doctrine/*/built-in/ | wc -l
23
```

**84 hits across 23 files — and most are not defects.** `review-gates.md` says
so explicitly: *"Prose that merely describes an internal practice … is fine; a
path presented as a live gate or resolvable artifact is not."* Reporting 84 as a
defect count is the first mistake available here.

| Class | Hits | Files | Disposition |
|---|---|---|---|
| **(a) presented as a live gate or resolvable artifact** | **52** | **7** | the bug — reword or relocate |
| (b) prose describing an internal practice | 31 | 15 | leave alone |
| (b′) regex false positive | 1 | 1 | leave alone |
| **(c) legitimately repo-local artefact** | **0** | 0 | — |

**Class (c) being empty is the finding.** Everything under
`src/doctrine/**/built-in/` ships. "It is fine, it is repo-local" is never an
available defence in that tree — if an artefact is genuinely repo-local it is in
the wrong directory by definition.

## 2. Class (a) — the offenders

Four are **relocations, not rewords**: strip the repo-local paths and almost
nothing consumer-meaningful remains.

- **`procedures/built-in/post-merge-arch-gate-adjudication.procedure.yaml`**
  (8 hits) — the *procedure steps themselves* are
  `PWHEADLESS=1 pytest tests/architectural/ -q`, `pytest tests/integration/`,
  `pytest tests/git/`. Not prose: `steps[].description` with fenced commands the
  actor is told to run. A consumer activating this procedure cannot execute
  step 1.
- **`toolguides/built-in/TERMINOLOGY_GUARD.md`** (6 hits) — the whole artefact
  is a runbook for
  `pytest tests/architectural/test_no_legacy_terminology.py`, including a
  `## Command` section. No consumer-resolvable content at all. (Its manifest
  `terminology-guard.toolguide.yaml` returns **0** hits under this pattern — its
  three are `src/doctrine/` prefixes, so they belong to the §4 class, not this
  one. The 52/7 total is correct precisely because the manifest contributes
  nothing here.)
- **`tactics/built-in/architectural-gate-non-vacuity.tactic.yaml`** (12 hits) —
  names one of our test files as "the current live exemplar", ships a literal
  `_ALLOWLIST` containing `src/specify_cli/git/protection_policy.py`, and
  prescribes an action item against *our* repository.
- **`styleguides/built-in/tiered-standards.styleguide.yaml`** (10 hits) — the
  tier registry *is* the payload: a map from our package paths to rigour tiers.
  A consumer receives rules for packages they do not have, and none for the ones
  they do.

Three are rewords:

- `tactics/built-in/frozen-baseline-shrink-only-ratchet.tactic.yaml` — states
  `tests/architectural/_baselines.yaml` as *the canonical location*, for the
  consumer.
- `glossary_packs/built-in/spec-kitty-core.glossary-pack.yaml` — definitions
  resolve terms by pointing at `src/specify_cli/...::symbol`.
- `tactics/built-in/code-patterns/chain-of-responsibility-rule-pipeline.tactic.yaml`
  — `Examples in tree:` entries presented through `references` as lookups.

**Judgement-call boundary, recorded honestly.** Three artefacts sit on the
(a)/(b) line — the two above plus
`secure-regex-catastrophic-backtracking` — all of the form "concrete provenance
citation of our own tree". They are split on whether the path is offered as a
*lookup* (a) or as *history* (b). A reviewer could reasonably move any of them,
shifting the (a) count by up to 12 hits. **The four MAJOR entries are not in
doubt.**

## 3. Class (b) — do not "fix" these

Generic `tests/**` globs in seven agent profiles'
`specialization-context.file-patterns`; generic commands
(`ruff check src/ tests/`, `uv run pytest tests/ -q`); code illustrations in
`testing-principles.styleguide.yaml`; a path-syntax illustration in
`POWERSHELL_SYNTAX.md`. `tests/` is a universal convention, not our path.

(b′) is `occurrence-classification-workflow.tactic.yaml`, whose text is
`"CLI commands, user-facing strings, tests/fixtures, logs/telemetry"` — a
category list the regex reads as a path.

## 4. The quick-check has a blind spot larger than what it finds

`review-gates.md` greps `src/specify_cli` only. Widening to the other source
roots:

```console
$ grep -rEn 'src/doctrine/|src/mission_runtime|src/charter/|src/runtime/|src/glossary/' \
    src/doctrine/*/built-in/ | wc -l
114
```

Mostly `guide_path:` and `references:` fields carrying the **source-tree prefix**
`src/doctrine/…`. The *content* ships; the *prefix* does not — an installed
consumer has `doctrine/` in site-packages, never `src/doctrine/`. Same defect
class, larger volume, and **invisible to the check written to catch it**.

This class is a mechanical prefix strip and should be one bulk-edit mission
under the occurrence-classification guardrail — deliberately *not* mixed into
the reference slice.

## 5. A gate currently REQUIRES one of these references

The load-bearing constraint for any cleanup, and the reason a naive fix cannot
merge.

`tests/architectural/test_no_dead_doctrine_paths.py:456` asserts **exact
equality** on a one-element list:

```python
excluded = sorted((site.path, site.text) for site in scan.forbidding_mentions)
assert excluded == [
    ("src/doctrine/agent_profiles/built-in/doctrine-daphne.agent.yaml",
     "src/doctrine/graph.yaml")
], "A2's effect set moved -- widening it needs a reason: ..."
```

Verified by mutation on this branch — removing the repo-local path from
`doctrine-daphne.agent.yaml`, i.e. doing exactly what the ruling asks:

```
FAILED test_forbidding_mention_would_false_red_without_its_discriminator
assert [] == [('src/doctrine/agent_profiles/built-in/doctrine-daphne.agent.yaml',
               'src/doctrine/graph.yaml')]
```

**The shippable-doctrine rule and this gate contradict each other, and the gate
wins.** It does not merely tolerate the repo-local reference — it requires it,
by file path and by matched text. Any daphne cleanup must update this gate in
the same commit or it cannot merge.

A second instance of the same shape: Gate C
(`test_every_built_in_doctrine_cross_link_resolves`) requires every relative
markdown link under `src/doctrine/` to resolve **on our disk**, which cements
links that escape the package entirely (e.g.
`src/doctrine/templates/diagrams/README.md` → `../../../../docs/architecture/…`).
Every one of those is dangling in a consumer repo, and the gate's contract is
that they must never be removed.

## 6. What remains repo-local in `doctrine-daphne` after the 2026-07-28 reword

PR #3007 reworded two named paths out of the profile. Three residues survive:

1. **The shipped-pack census** (*"16 built-in profiles carry 50
   `operating-procedures` declarations; exactly 1 is backed by an edge…"*) — a
   measurement of **our** pack, frozen into shipped doctrine. In a consumer repo
   with its own org pack the numbers are simply false, and the actionable rule
   ("treat a named operating procedure as unwired until the edge is confirmed")
   does not need them. This survived the reword because it names no path.
2. **`src/doctrine/graph.yaml`** — a source-tree path, invisible to the
   documented grep, and pinned by the gate in §5.
3. **PR-history narration** — the `applies`-edge story is spec-kitty provenance;
   the universal half is "no traversal follows `applies`".

Everything else in the profile is genuinely universal and should stay exactly
where it is: the canonical path shape and its silent-non-load consequence, the
frozen-legacy `references:` rule, the per-kind fragment model, the
doctrine-offers / charter-activates / runtime-consumes split, the inbound-edge
reachability rule, and the golden-count ledger duty. **The slice is a split, not
a relocation.**

## 7. Where a relocated artefact can actually go

Established while auditing; load-bearing for every follow-on.

- **The project tier cannot host `agent_profile` or `asset`.**
  `DoctrineService._PROJECT_KIND_DIRS` covers four kinds
  (directive/tactic/styleguide/procedure), and project-tier artefacts reach the
  DRG only through synthesis, where `_KIND_TO_NODE_KIND` maps three — `asset`
  and `agent_profile` resolve to `None`, so the caller *skips the node and its
  edges*. Relocating a profile there yields an artefact that loads, validates,
  and **is not a graph node** — the defect class this programme exists to close.
- **`.kittify/doctrine/` is already a parallel surface.** Of its 14 committed
  files, 5 are `.md` written by the retrospective synthesizer (the rest are
  `.provenance/` and `overlays/` YAML); the repositories glob
  `*.<kind>.yaml`. `DoctrineService` reads none of them. Only `overlays/` is
  consumed, by the calibration walker.
- **The org-pack tier does admit assets.** `_ORG_DRG_KIND_ALIASES` includes
  `"assets"`, the pack validator validates any pack's `assets/` tree, and org
  packs register from a committed in-repo `local_path` resolved against the repo
  root. **This is the only seam that admits an asset today.**
- **There is no asset resolution or install path at all.** `DoctrineService`
  exposes nine repositories and assets is not one; resolution returns asset
  **ids**, never paths. The single shipped asset is consumed by a test that
  hard-codes its repo-relative path and `importlib`-loads it. Until that closes,
  "share via the pack system" means "share a filesystem convention".

## 8. Recommended order

1. **Fix the quick-check** (§4) so follow-ons stop inheriting the blind spot.
2. **ADR: destination tier** — in-repo org pack vs a separate internal pack
   (#3023). Both mean *register a non-`built-in` pack root*; they differ only on
   location. ADR [2026-07-26-2](../../../adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md)
   §6 already records the post-extraction layout, so this is an amendment.
3. **Resolve the gate contradiction** (§5) — highest priority, because the gate
   currently *enforces* the bug.
4. **The daphne split** (§6) as the reference slice, landing the gate change in
   lockstep.
5. **The four MAJOR relocations** (§2), individually.
6. **The prefix class** (§4) as one bulk-edit mission.

Sequence by severity, not by grep count. And split
`test_no_dead_doctrine_paths.py` before extracting anything: its Gate A is a
`src/`-wide CLI gate wearing a doctrine name, so moving the module wholesale
would silently drop real coverage of spec-kitty's own code.
