---
title: 'ADR: Charter-Wheel Assessment — Extractable in Principle, Cut Over Kernel→Doctrine→Charter as One No-Partial Follow-On'
description: '`src/charter` carries zero `specify_cli` import edges and is extractable in principle, but the kernel, doctrine and charter wheels must cut over together, never in stages.'
status: Accepted
date: '2026-08-02'
doc_status: active
kind: ADR
updated: '2026-08-02T00:00:00Z'
---

## Context and Problem Statement

[#3101](https://github.com/Priivacy-ai/spec-kitty/issues/3101) wants `src/doctrine/` — and,
assessed here, `src/charter/` — to ship as installable wheels on the documented dependency
chain, shown below, which runs from the dependency-free kernel at the root through doctrine
and charter to glossary/runtime and finally `specify_cli`.

```
kernel (root) <- doctrine <- charter <- glossary/runtime <- specify_cli
```

The Mission `doctrine-charter-split-unification-01KZ0SRB` was scoped as **groundwork for**
that cutover, not the cutover (spec C-002). Two of its work packages changed what is
knowable about charter's extractability, and this ADR records the resulting assessment plus
the sequencing decision, so the follow-on is mechanical rather than exploratory:

- **WP10 / FR-008** deleted the single real upward layer edge out of the charter layer — a
  lazy in-function `import specify_cli` in `charter/synthesizer/synthesize_pipeline.py`,
  used only as a `__version__` fallback — and shipped a **non-vacuous AST-walk gate** for
  it. The pre-existing `pytestarch` `LayerRule` in
  [`tests/architectural/test_layer_rules.py`](../../../tests/architectural/test_layer_rules.py)
  was **green with the violation present**, because pytestarch's import resolution
  (`ImportConverter.convert`) recurses into a module's and a function's `.body` but never
  into an `except` handler's body — and the deleted edge sat inside an `except Exception:`
  block, so it was invisible to that specific blind spot, not to function-scope imports in
  general. A gate that cannot fail on the one violation it nominally guards is worse than no
  gate: it manufactures false confidence.
- **WP12 / FR-009+FR-010** minted [`src/kernel/pyproject.toml`](../../../src/kernel/pyproject.toml)
  (`spec-kitty-kernel`, zero first-party dependencies — the true root of the chain) and
  closed `src/doctrine/pyproject.toml` with its real
  `spec-kitty-kernel` dependency plus a working hatchling build hook for the **out-of-tree**
  `packs/` tree. Both were **build-verified with a real `hatch build`**, not asserted from
  manifest shape.

The open architectural question this ADR answers: *given a charter layer with no upward
import edge, can `src/charter` simply be lifted into its own wheel — and if not now, in what
order and under what discipline?*

The failure mode to avoid is already documented in this repository. ADR
[2026-04-25-1](./2026-04-25-1-shared-package-boundary.md) records
[PR #779](https://github.com/Priivacy-ai/spec-kitty/pull/779): a *partial* package cutover
that moved code into the target tree while leaving the old production imports alive. The
resulting hybrid was structurally identical to the pre-cutover state from a clean-install
perspective, and it re-imposed cross-package release lockstep. It was rejected.

## Decision Drivers

- **Claim precision.** An over-broad "charter is decoupled" claim would be load-bearing for
  the follow-on and is not what the landed evidence supports. The claim must be no wider
  than its proof.
- **Transitive closure, not local cleanliness.** Charter imports `doctrine` (109 import
  statements) and `kernel` (8). A charter wheel with no doctrine wheel and no kernel wheel
  beneath it is unresolvable at install time, regardless of how clean charter itself is.
- **No-partial discipline.** The #779 precedent makes a half-executed cutover the specific
  named risk, not a hypothetical one.
- **Reuse the landed boundary pattern.** This repository already has an enforcement triad
  that works. Inventing a second, parallel packaging-enforcement idiom would split the
  authority and rot.
- **C-002 must hold.** The groundwork Mission must not leave the tree in a state where CI
  builds or installs a nested wheel whose `kernel` dependency is not yet published.

## Considered Options

- **Option A — Extract the charter wheel now**, on top of the landed WP10/WP12 groundwork.
- **Option B — Assess and sequence: one atomic kernel→doctrine→charter cutover, deferred**
  as an explicit no-partial follow-on that extends the `2026-04-25-1` pattern.
- **Option C — Abandon the split**; keep kernel/doctrine/charter permanently in the root
  wheel and close #3101.

## Decision Outcome

**Chosen option: "Option B"**, because charter is extractable *in principle* but not *in
isolation*: its transitive closure needs the kernel and doctrine wheels published first, and
splitting the move into stages is precisely the partial cutover the #779 precedent forbids.

### (a) The extractability claim, scoped to its proof

**`src/charter` is extractable in principle: it carries zero `specify_cli` import
entanglement — that is, zero static `specify_cli` import edges at any scope, module-level or
in-function — as proven by WP10's AST-walk gate,
[`tests/architectural/test_charter_no_specify_cli_import.py`](../../../tests/architectural/test_charter_no_specify_cli_import.py).**

That gate is the durable proof and the exact boundary of the claim. It walks the full AST
(`ast.walk`) of every module under `src/charter/**`, so in-function, in-class, in-`try`, and
in-`except`-handler imports are all caught — including the exact `except` blind spot
`pytestarch`'s converter misses. Its
non-vacuity was demonstrated by self-mutation (NFR-004): re-adding the deleted in-function
import turns it red naming the exact line, while `test_layer_rules` stays green throughout.

**What this gate does NOT prove.** Citing it for anything below is a misreading:

| Not covered | Why it is out of scope |
|---|---|
| `importlib.import_module(...)` / `__import__(...)` string indirection | The gate matches `ast.Import` / `ast.ImportFrom` nodes; a name assembled as a string is invisible to it. (Charter has no such call site today — but that is an observation, not an enforced invariant.) |
| Entry points / plugin discovery | Resolved at runtime from installed distribution metadata; never an AST edge. |
| Duck-typed objects passed in as data | A caller handing charter a `specify_cli`-owned object is a real runtime coupling with no import edge anywhere in `src/charter/**`. |
| Non-import couplings — shared on-disk paths, config keys, environment contracts | Not imports. |
| **Charter ↔ glossary / runtime / re-export edges** | Explicitly **unproven** by this gate (research.md D10). The gate's forbidden root is `specify_cli` alone. These edges are a separate assessment the cutover follow-on must perform. |

So: "zero `specify_cli` import entanglement". Not "zero entanglement".

### (b) The cutover is sequenced kernel→doctrine→charter, and is NO-PARTIAL

The publish order is forced by the dependency chain — `spec-kitty-kernel` has zero
first-party dependencies, `spec-kitty-doctrine` depends on kernel, a future
`spec-kitty-charter` depends on both:

```
spec-kitty-kernel  ->  spec-kitty-doctrine  ->  spec-kitty-charter
   (zero first-party deps)     (needs kernel)        (needs kernel + doctrine)
```

**This ordering is a publish sequence inside one cutover, not a schedule of three shippable
milestones.** A partial cutover is forbidden: ADR
[2026-04-25-1](./2026-04-25-1-shared-package-boundary.md) records, under *Alternatives
considered*, that constraint **C-007** of the shared-package-boundary Mission spec
explicitly forbids partial cutovers, with PR #779 as the cautionary example. The follow-on
therefore lands the three wheels together — root-wheel `packages` removal, published
dependency declarations, boundary enforcement, and clean-install proof in one reviewed unit
— or it does not land. Stopping after kernel+doctrine, with charter still bundled in the
root wheel while its dependencies are external, reproduces the #779 hybrid exactly.

### (c) This ADR extends `2026-04-25-1`; it does not introduce a new pattern

The follow-on reuses the existing, landed enforcement triad. Each mechanism gets a charter
analogue — same idiom, same file conventions, no second authority:

| `2026-04-25-1` mechanism | Landed instance | Charter-cutover analogue |
|---|---|---|
| **Boundary test** (no forbidden import edge, pytestarch + AST fallback) | [`tests/architectural/test_shared_package_boundary.py`](../../../tests/architectural/test_shared_package_boundary.py) | **Already landed** as [`test_charter_no_specify_cli_import.py`](../../../tests/architectural/test_charter_no_specify_cli_import.py) (WP10). The follow-on extends its forbidden-root set to cover glossary/runtime once those edges are assessed. |
| **pyproject-shape test** (no exact pins, no committed path/editable sources, no retired deps) | [`tests/architectural/test_pyproject_shape.py`](../../../tests/architectural/test_pyproject_shape.py) | Extend with the same assertions for `spec-kitty-kernel` / `spec-kitty-doctrine` / `spec-kitty-charter`: compatibility ranges in pyproject, exact pins only in `uv.lock`, no `[tool.uv.sources]` path entries. Partly pre-figured by WP12's `test_doctrine_wheel_closure.py`. |
| **`clean-install-verification` CI job** (fresh venv, wheel install, real command run) | `.github/workflows/ci-quality.yml` (deleted per PROGRAM.md §2 / planning#57 — this repo runs no GitHub Actions) + [`tests/integration/test_clean_install_next.py`](../../../tests/integration/test_clean_install_next.py) | Extend the **same job** to install the published kernel/doctrine/charter wheels into the clean venv and exercise a charter command path. A new parallel job would fragment the gate. |

WP12 supplies the groundwork this reuse rests on, and it is **build-executed, not asserted**
(research.md §D7, spike status RESOLVED):

- `src/kernel/pyproject.toml` — `spec-kitty-kernel` 1.0.0, `dependencies = []`.
- `src/doctrine/pyproject.toml` — declares `spec-kitty-kernel>=1.0.0,<2.0.0`, a real
  import-closure need (`doctrine/resolver.py`, `missions/primitives.py`,
  `shared/schema_utils.py` all `from kernel...`).
- `src/doctrine/hatch_build.py` — a hatchling
  `BuildHookInterface.initialize` hook that force-includes the repo-root `packs/` tree as a
  **wheel-root sibling** of `doctrine/`, matching what `pack_paths._resolve_built_in`
  expects (`files("doctrine").parent / "packs" / "built-in"`). A naive
  `force-include ../../packs` escapes the project root and hatchling refuses it; a blanket
  `sources` rename re-nests the hook's own `force_include` entries under `doctrine/`. Both
  were found by running the build, not by reading it.
- Proof: `hatch build -t wheel` in both trees, `unzip -l` confirming `doctrine/` and
  `packs/` as true siblings, and an install-and-import closure run in a scratch venv where
  `resolve_pack_root("built-in")` resolved against the installed sibling.

### (d) Deferred follow-on issue set

The cutover follow-on owns this set. They are deferred, not dropped:

| Issue | Title | Relation to the cutover |
|---|---|---|
| [#3101](https://github.com/Priivacy-ai/spec-kitty/issues/3101) | Split `src/doctrine/` (and assess `src/charter/`) into a separate installable wheel/package | The cutover itself — the parent. This ADR is its assessment half. |
| [#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091) | Phase 1b: relocate the `missions/` doctrine tree to `packs/built-in` | Changes what the doctrine wheel must carry; sequence before or with the cutover. |
| [#3022](https://github.com/Priivacy-ai/spec-kitty/issues/3022) | Extract built-in doctrine packs into `spec-kitty-packs-open` | A further split of the payload WP12's build hook currently ships inside the doctrine wheel. |
| [#3036](https://github.com/Priivacy-ai/spec-kitty/issues/3036) | Architectural gate requires the repo-coupling the shippable-doctrine rule forbids | A live contradiction between two gates; must be resolved before doctrine ships standalone. |
| [#3039](https://github.com/Priivacy-ai/spec-kitty/issues/3039) | Split `test_no_dead_doctrine_paths.py`: Gate A is a `src/`-wide CLI gate wearing a doctrine name | Mis-scoped gate; would follow the wrong package after the split. |
| [#2986](https://github.com/Priivacy-ai/spec-kitty/issues/2986) | runtime→doctrine boundary ratchet sees only module-level imports; 61 function-local imports across 30 files bypass it | **The same blind spot WP10 closed for charter**, still open for runtime→doctrine. Directly relevant: the boundary-test half of the extended pattern is unsound for that pair until it is fixed. |

### (e) C-002 — this Mission performed NO wheel cutover

Stated explicitly, because "packaging groundwork landed" is easy to misread as "the split
happened":

**The Mission `doctrine-charter-split-unification-01KZ0SRB` performed no wheel cutover. It
is groundwork only.** Concretely, as of this ADR:

- `src/kernel`, `src/doctrine` and `src/charter` **remain in the root wheel** — the root
  [`pyproject.toml`](../../../pyproject.toml) `packages` list is untouched and still names
  all three, and `packs/` is still root-force-included.
- **No wheel was published.** `spec-kitty-kernel` and `spec-kitty-doctrine` exist as
  manifests and build locally; they are not on PyPI.
- **No release gate was added, and no CI job builds or installs the nested wheels
  standalone.** This is load-bearing: doctrine's newly declared `kernel` dependency is
  unresolvable until the follow-on publishes the kernel wheel, so a CI job building the
  nested doctrine wheel today would break — which is why "groundwork only" is a CI-verified
  constraint, not just an intention.
- There is deliberately **no** `src/charter/pyproject.toml`. Minting one now would be the
  first half of the forbidden partial cutover.

### Consequences

#### Positive

- The follow-on starts from a settled assessment and a forced ordering, not a fresh
  investigation; the remaining unknowns are named (glossary/runtime/re-export edges) rather
  than assumed absent.
- The one real upward edge out of the charter layer is gone, and re-introducing it at any
  scope now fails CI.
- The kernel/doctrine manifests are build-verified, so the follow-on inherits two solved
  packaging problems (root-relative `packages`, out-of-tree `packs/`) instead of rediscovering
  them.
- Enforcement stays in one idiom: three mechanisms, extended, not duplicated.

#### Negative

- The charter wheel is not available until the whole chain ships; consumers wanting only the
  charter layer keep installing `spec-kitty-cli`.
- The no-partial rule makes the follow-on a large single reviewed unit, which is harder to
  review than three small ones. This cost is accepted: #779 is the evidence that the cheaper
  path is the expensive one.
- `src/kernel/pyproject.toml` and `src/doctrine/pyproject.toml` are dormant manifests in the
  tree until the cutover — a standing "is this live?" question for readers, mitigated by this
  ADR and by the closure test.

#### Neutral

- The three-wheel end state is unchanged from #3101's original intent; this ADR fixes the
  order and the atomicity, not the destination.

### Confirmation

This decision is confirmed correct when the follow-on can execute mechanically: the extended
pyproject-shape assertions and the extended `clean-install-verification` job go green on a
fresh venv that installs the three published wheels and runs a charter command path, with no
new enforcement idiom introduced. It is falsified if the charter layer turns out to carry
non-import coupling to `specify_cli` that the AST gate never covered — which is exactly why
the claim above is scoped to import edges and why the unproven-edge table is part of the
decision rather than a footnote.

## Pros and Cons of the Options

### Option A — Extract the charter wheel now

**Pros:**

- Delivers a visible piece of #3101 immediately.
- Exercises the packaging path while WP10/WP12 context is fresh.

**Cons:**

- Unresolvable: charter's 109 `doctrine` and 8 `kernel` import statements need both wheels
  published first. Neither is.
- It is the #779 hybrid by construction — charter external, its dependencies still bundled
  in the root wheel.
- Violates C-002 (no cutover this Mission) and the C-007 no-partial rule of
  `2026-04-25-1`.

### Option B — Assess and sequence one atomic cutover (chosen)

**Pros:**

- Matches the real dependency closure; the publish order is derived, not chosen.
- Reuses a landed, proven enforcement triad instead of inventing one.
- Keeps the groundwork honest: the manifests exist and build, and nothing pretends the split
  has happened.
- Names the unproven couplings so the follow-on scopes its own assessment correctly.

**Cons:**

- Defers all user-visible packaging value.
- Concentrates risk in one large follow-on PR.

### Option C — Abandon the split

**Pros:**

- Zero further cost; the monorepo wheel works today.

**Cons:**

- Forfeits the independent doctrine/charter distribution that #3022 and #3091 depend on.
- Wastes the landed WP10/WP12 groundwork.
- Leaves the layer chain a convention enforced only by tests, never by package boundaries.

## More Information

- Extends: ADR [2026-04-25-1 — Shared Package Boundary Cutover](./2026-04-25-1-shared-package-boundary.md)
  (the boundary-test + pyproject-shape-test + `clean-install-verification` pattern, and the
  C-007 no-partial rule)
- Mission spec: `kitty-specs/doctrine-charter-split-unification-01KZ0SRB/spec.md`
  (FR-011, SC-007, C-002, User Story 4)
- Research: `kitty-specs/doctrine-charter-split-unification-01KZ0SRB/research.md`
  (§D7 executed `hatch build` spike result, §D8 sequencing DAG, §D10 claim-scope correction)
- Landed enforcement and groundwork:
  - [`tests/architectural/test_charter_no_specify_cli_import.py`](../../../tests/architectural/test_charter_no_specify_cli_import.py) — the AST-walk gate this ADR's claim rests on
  - [`tests/architectural/test_layer_rules.py`](../../../tests/architectural/test_layer_rules.py) — the pytestarch layer rule; does not catch imports nested inside `try`/`except` handlers (the exact shape of the deleted edge), so it stayed green with the violation present
  - `tests/architectural/test_doctrine_wheel_closure.py` — non-vacuous doctrine manifest closure (removed along with the rest of this dormant wheel groundwork by mission `charter-code-topology-01M152G1`)
  - [`src/kernel/pyproject.toml`](../../../src/kernel/pyproject.toml), `src/doctrine/pyproject.toml`, `src/doctrine/hatch_build.py`
- Runbook precedent: [`docs/migrations/shared-package-boundary-cutover.md`](../../migrations/shared-package-boundary-cutover.md)
