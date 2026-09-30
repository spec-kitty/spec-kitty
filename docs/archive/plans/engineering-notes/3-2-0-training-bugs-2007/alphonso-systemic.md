---
title: '#2007 — Systemic Architecture Connection (Architect Alphonso)'
description: "Architect Alphonso's systemic-architecture connection for #2007 (read-only research op): how the training bugs trace to a shared architectural root (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# #2007 — Systemic Architecture Connection (Architect Alphonso)

**Author:** Architect Alphonso (architecture lens; research op, read-only — no commit/switch)
**Date:** 2026-06-16
**Branch:** `pr/tool-surface-contract-residuals` @ spec-kitty 3.2.x
**Question:** does #2007's prescribed "single typed mission-context/read-path authority" == the #1619
`ExecutionContext` SSOT; is #2007 the data that flips the 3.2.1 lead from safety→impact; and what is
the single highest-leverage structural fix.

> **Governance (architect-alphonso).** DIR-001 (Architectural Integrity — one owning module per
> concern; duplicate resolvers are seams to strangle), DIR-003 (Decision Documentation — every verdict
> carries authority/contract/citation), DIR-031 (Context-Aware Design — coord/primary is a bounded-
> context boundary preserved by a builder-owned translation layer, never collapsed into consumers),
> DIR-032 (Conceptual Alignment — terms keyed to the #1619 doc-09 fragment vocabulary and the
> SCORING-SYNTHESIS candidate set). Builds on
> `naming-identity-ssot-strangler/context-threading-alphonso-design-verdict.md` and
> `3-2-x-goal-corroboration/SCORING-SYNTHESIS.md`.

---

## Verdict line (TL;DR)

1. **#2007's authority == the #1619 `ExecutionContext` SSOT — VERIFIED, with one sharpening.** The
   prescribed "single typed mission-context/read-path authority shared by `next`, `agent context
   resolve`, `setup-plan`, `finalize-tasks`, `decision open`, `agent action implement/review`" is
   *literally* `resolve_action_context` → `ExecutionContext` (`src/mission_runtime/`). It is not a new
   thing to build. Four of the six named commands **already import and route through it** today; the
   failing ones fail **precisely because they bypass it or re-derive a parallel surface** — the
   non-adoption thesis, now corroborated by real-world screenshots instead of churn forensics.

2. **#2007 does NOT cleanly flip 3.2.1 safety→impact — it RE-SCOPES the impact lead and adds a new
   peer track.** The neutral panel leaned impact (#1832→#1716, write-side single-resolution); the
   operator chose safety (naming rider). #2007 is corroborating field evidence for the *read-side /
   adoption* grain of that same surface — but its single loudest, most-repeated failure class
   (bugs #1/#5/#9/#13/#16 + the acceptance criterion) is **command-contract drift**, which is a
   *different* architectural class than write-side topology and was barely weighted in the panel. So
   #2007 (a) hardens the case that the read-side adoption work is real user pain, and (b) elevates a
   **command-surface contract guard** to co-lead status — it does not retroactively make #1716 the
   safe opener.

3. **Single highest-leverage structural fix:** **make every named command consume the resolved
   `ExecutionContext` and preserve its typed `ActionContextError.code` end-to-end (no reclassification),
   gated by a repo-wide command-snippet guard that validates CLI snippets in skills/prompts/doctrine —
   not just `docs/api/` — against the live Typer registry.** One adoption ratchet kills bugs
   #4/#7/#8/#11/#12/#14/#15 (wrong-authority + flattened-error class); one snippet guard kills
   #1/#5/#9/#13/#16 (drift class). Both extend mechanisms that already exist on this branch.

---

## 1. Is #2007's authority the #1619 ExecutionContext SSOT? — **YES (verified on checkout).**

### 1a. The prescribed outcome is the existing object, named

Issue #2007's "Architectural Diagnosis" prescribes:

> *"a single, typed mission-context/read-path authority shared by `next`, `agent context resolve`,
> `setup-plan`, `finalize-tasks`, `decision open`, and `agent action implement/review`."*

That object exists and is exactly this surface:

- `src/mission_runtime/resolution.py:682` — `resolve_action_context(repo_root, *, action, feature,
  wp_id, ...) -> ExecutionContext`, documented in-source as *"the single sanctioned resolver
  (FR-003/FR-005) … no parallel resolver survives (NFR-002)."*
- `src/mission_runtime/context.py:184` — `ExecutionContext`, the doc-09 op-composite carrying the
  frozen fragments `identity / branch_ref / workspace / status_surface / artifact_placement /
  prompt_source`.
- `ActionContextError` (`resolution.py:62`) — *"the single error type consumers catch … there is never
  a silent fallback,"* carrying a typed `.code` (`FEATURE_CONTEXT_UNRESOLVED`,
  `STATUS_READ_PATH_NOT_FOUND`, `WORK_PACKAGE_UNRESOLVED`, …).

This is the same object the prior design verdict adjudicated as the intended SSOT
(`context-threading-alphonso-design-verdict.md` §1, §5): *"the intended SSOT is exactly a
Context-value-object + consolidated-builder design … the residual split-brain is non-adoption."* #2007
is the field-evidence instance of that verdict.

### 1b. The named commands' adoption status (verified)

| Command (#2007) | Routes through `resolve_*`? | Evidence | Bug |
|---|---|---|---|
| `agent context resolve` | **YES** | `agent/context.py:135` calls `resolve_action_context` | #5/#14 |
| `agent action implement/review` | **YES** (target branch) | `agent/workflow.py:964` routes target-branch via `resolve_action_context` | #16 |
| `next` (advance) | **YES** | `runtime/next/runtime_bridge.py:3118,3256` | #15 |
| `setup-plan` | **partial** | uses `_build_setup_plan_detection_error` builder (`mission.py:1298`); placement via `resolve_placement_only` | #4/#7 |
| `finalize-tasks` | **partial** | `resolve_placement_only` (`mission.py:744`) for *placement*, but reads planning inputs on a coord-aware dir | #11/#12 |
| `decision open` | **split** | `decision.py:425` uses `resolve_mission_read_path` **after** a separate `kitty-specs/` escape-walk (`decision.py:86–107`) | #8 |
| `agent mission tasks` | YES | `tasks.py:351` `resolve_placement_only` | — |

**The pattern is unambiguous:** the commands that fully consume the resolved context behave; the
commands that fail do so because they **re-derive a parallel surface** or **flatten the typed error**:

- **#8 (decision open)** is the cleanest specimen. `decision.py` resolves the mission read path through
  the canonical primitive (`resolve_mission_read_path`, line 425) **but** also runs an independent
  walk-up-to-`kitty-specs/` + escape-validation (lines 86–107). The coord-aware resolver returns a path
  under `.worktrees/<mission>-coord/kitty-specs/`, then the *primary*-anchored escape check rejects it
  as *"Mission path would escape kitty-specs/"*. Two authorities, one decision — the textbook
  bounded-context leak (DIR-031). Fix = resolve identity/path through the context **first**, validate
  traversal on raw operator tokens **only** (#2007's own fix direction).

- **#11 (finalize-tasks reads from wrong surface)** is non-adoption on the *read* axis: it correctly
  resolves *placement* via `resolve_placement_only` (write authority) but reads planning inputs
  (`meta.json`, `spec.md`) from the coord-aware mission dir instead of the primary. The resolver
  already knows the primary root (`WorkspaceFragment.primary_root`, `context.py:144`) — the command
  just doesn't thread it for the *input* read. This is precisely C-LANES-1 (three surfaces, one
  composite; the consumer picks the wrong fragment).

- **#12, #14, #15 (flattened typed failures)** are the *error-preservation* face of non-adoption. The
  resolver raises a typed `ActionContextError(STATUS_READ_PATH_NOT_FOUND, …)` / `FEATURE_CONTEXT_
  UNRESOLVED` with checked paths; the consumer catches and **reclassifies** it into a generic
  "pass `--mission`" / `MISSION_NOT_FOUND` remediation, discarding the code and the checked-path
  diagnostics. #2007's acceptance criterion — *"failures preserve their original error codes and
  checked paths through JSON output"* — is the contract the resolver already offers and the consumers
  already throw away.

### 1c. The "single typed authority" is real but **mid-strangler** — the panel's verified caveat still holds

The SCORING-SYNTHESIS verified-facts are **still true on this checkout** (I re-verified):

- `ExecutionContext` is **mutable** — `@dataclass` at `context.py:184` while every *fragment* is
  `@dataclass(frozen=True)`.
- The builder **mutates substrate fields after freezing the fragments**: `resolution.py:793–801`
  assigns `context.branch_name`, `context.workspace_path`, etc. *after* `branch_ref` (carrying
  `target_branch`) is frozen — so `branch_name` and `branch_ref.target_branch` are written from two
  resolutions and **can disagree inside the claimed SSOT**. The split-brain is not only at the
  periphery; a residual lives *in* the authority.

So #2007's authority **is** the #1619 SSOT, but the SSOT is *real-and-load-bearing yet unfinished*:
the fragments exist and are frozen; the composite is a mutable transitional shape with a flat substrate
consumers can still read instead of the fragments. **#2007 does not require building the object — it
requires (a) finishing its immutability/substrate retirement and (b) adopting it at the seven named
call sites with typed-error pass-through.** That is the exact membership the prior verdict already
named (§4: "the WPs are adoption/routing/ratchet, not greenfield construction").

**Verdict 1: SUPPORTED.** #2007's prescribed authority is literally `resolve_action_context` /
`ExecutionContext`. The failing commands fail because they bypass it (decision-open dual-resolve,
finalize-tasks input read) or flatten its typed errors (#12/#14/#15) — the non-adoption thesis,
corroborated by field screenshots.

---

## 2. Does #2007 flip 3.2.1 safety→impact? — **NO clean flip; it RE-SCOPES impact and adds a co-lead.**

### 2a. What the panel decided, and what #2007 adds

The neutral panel (SCORING-SYNTHESIS) leaned **impact** (open the write-side single-resolution surface #1832→#1716); the operator chose **safety** (naming rider first), recorded as a *values choice, not a
data verdict*. The panel's own neutral read was: *"impact, entered through #1832 — the safety of the
naming-first plan is available inside the impact plan."*

Issue #2007 is **field evidence for the read-side / adoption grain** of that surface — `STATUS_READ_PATH_
NOT_FOUND` flattening (#14/#15), wrong-authority reads (#8/#11), the implement read-path (#16) are all
the *consumer* face of #1832's "consume the same resolved context the claim used; single resolution
path." It **strengthens** the impact case (these are real, screenshot-reproduced, agent-cycle-wasting
failures, not churn metrics) but it does so on the **read/adoption** axis, not the **write-side
topology** axis that #1716 owns.

### 2b. Why it is not a clean flip

Two honest reasons #2007 does not retroactively justify "impact-first, #1716-first":

1. **#2007's loudest class is orthogonal to the write-side surface.** Five of sixteen bugs
   (#1 doctrine `list`, #5 `--action`, #9 stale Python import, #13 `worktree repair`, #16 implement
   `--json`) plus the **first acceptance criterion** are **command-contract drift** — docs/prompts/
   skills referencing surfaces that don't exist or are internal. This class has **nothing to do with
   `ExecutionContext` topology**; it is a DevEx/G3 enabler. The panel weighted it at ~zero. #2007
   re-weights it to *co-lead* — but that pulls *toward* the cheap-safe end, not toward #1716.

2. **The remaining read-side bugs validate the panel's own "enter through the safe WP" framing, not
   "lead with #1716."** #2007's read-path/error-preservation fixes are adoption-and-pass-through WPs —
   the SCORING-SYNTHESIS's WP1 (#1832) shape — which are exactly the *safe entry* the panel said lives
   inside the impact plan. #1716 (write-side coord topology) is barely touched by #2007's inventory
   (the closest is #11's placement-vs-input split, which is read-side adoption, not topology redesign).

### 2c. The honest re-scoping

> **#2007 corroborates the panel's verified diagnosis (the SSOT exists, the split-brain is
> non-adoption + an in-authority mutation residual) and supplies the missing real-world severity
> evidence for the READ-SIDE adoption grain — but it does NOT make #1716 the right opener, and it
> ELEVATES command-contract-drift (a class the panel ignored) to co-lead.** The defensible reading:
> the operator's safety lead (naming rider, low-risk momentum) is **compatible** with starting #2007's
> work, because #2007's safest, highest-evidence WPs are *also* low-risk adoption/pass-through cuts —
> the same "safe entry inside the impact plan" the panel described. #2007 is the data that says *do the
> read-side adoption now*, not the data that says *lead with #1716 now*.

**Verdict 2: NO flip; RE-SCOPE.** #2007 is corroborating field evidence for the read-side/adoption
grain of the impact surface and promotes a new command-surface-contract co-lead. It does not overturn
the operator's safety values-call; it tightens what "the safe opener" should *contain*: typed-error
pass-through + command-snippet guard, both low-risk, both real user pain.

---

## 3. Command-contract drift as an architectural class — the CI snippet guard, and where it belongs

### 3a. It is a distinct class, and the right fix is structural (a guard), not editorial (find-and-fix)

Bugs #1/#5/#9/#13/#16 share one shape: a **published surface (skill / prompt / doctrine prose / docs /
`--help` text) asserts a CLI contract the registered Typer app does not honour.** Editorial
find-and-replace fixes the *instances*; it does not fix the *class* — drift regrows the moment a
command is renamed or a flag added. The structural fix is an **executable contract**: a guard that
parses every CLI snippet in the published corpus and asserts it resolves against the live Typer
registry (command path exists, is non-hidden, accepts the named flags).

### 3b. The seam already exists — extend its *reach*, don't build it

This branch (`pr/tool-surface-contract-residuals`) already carries most of the mechanism:

- `src/specify_cli/tool_surface/docs.py` — `DocsLinter`, `RegistryPathIndex`, `FINDING_UNREGISTERED_PATH`
  (`tests/specify_cli/tool_surface/test_docs.py`). A registry-backed docs linter exists.
- `tests/architectural/test_docs_cli_reference_parity.py` — walks the live Typer surface via
  `scripts.docs._typer_walker.walk` and asserts parity against `docs/api/cli-commands.md` +
  `agent-subcommands.md`. **It also already scans skill docs for `spec-kitty agent profile <sub>` tokens
  and asserts each `<sub>` is registered (FR-017/FR-018)** — the *exact* pattern #2007 wants, but scoped
  to one command family.

**The gap is reach, not mechanism.** Today the parity guard covers `docs/api/*.md` and one
profile-subcommand token scan. #2007 needs that token-scan generalized across the **whole published
corpus**: `src/doctrine/missions/mission-steps/**/prompt.md` (the SOURCE prompts), `.agents/skills/**/
SKILL.md` and the 12 agent command dirs (generated copies — guard the SOURCE), and `docs/**`.

### 3c. The seam sketch

```
tool_surface/registry.py        ──► RegistryPathIndex   (live, from _typer_walker.walk)
                                       • command_paths: set[tuple[str,...]]
                                       • flags_for(path): set[str]   (incl. hidden/internal markers)

tool_surface/snippet_extract.py ──► extract_cli_snippets(corpus_root) -> list[Snippet]
                                       • regex for `spec-kitty <...>` in fenced blocks + inline code
                                       • Snippet = (file, line, command_path, flags, raw)

tool_surface/snippet_lint.py    ──► lint(snippets, index) -> list[Finding]
                                       FINDING_UNREGISTERED_PATH   (#1, #9, #13)
                                       FINDING_UNKNOWN_FLAG        (#5)
                                       FINDING_INTERNAL_AS_PUBLIC  (#16 — registered but hidden/internal)

tests/architectural/test_command_snippet_contract.py
                                     • corpus = doctrine prompts (SOURCE) + skills + docs
                                     • fail-on-finding; allow-list with inline justification only
```

Three finding codes map 1:1 onto the drift bugs: *unregistered path* (#1 `doctrine list`, #9 stale
`specify_cli.core.templates`, #13 `worktree repair`), *unknown flag* (#5 missing `--action` advertised
as no-flag), *internal-as-public* (#16 `implement --json` exists on the internal allocator but the
canonical `agent action implement` rejects it; the guard flags the snippet that points agents at the
wrong surface). The internal-vs-public axis needs the registry to carry the hidden/internal marker the
`_typer_walker` already discovers (the parity test filters non-hidden — reuse that signal inverted).

### 3d. Where it belongs

**G3 (DevEx enablers) — YES, and it is the cheapest, safest, highest-coverage #2007 WP.** It is
pure-additive (a new guard + corpus scan), carries no topology/semantics risk, directly satisfies
acceptance criterion #1, and is the structural antidote to the entire drift class. It is the part of #2007 most compatible with the operator's safety lead — ship it alongside the naming rider.

**One DIR-001 caution:** the guard must scan **SOURCE** doctrine prompts (`src/doctrine/missions/
mission-steps/**`), not the generated agent copies (CLAUDE.md template-source rule) — otherwise it
lints regenerated artifacts and reports drift the operator cannot fix at the source. The corpus globs
must exclude the 12 generated agent dirs and target the doctrine source + `.agents/skills` SOURCE +
`docs/`.

**Verdict 3:** command-contract drift is a first-class architectural concern; the right fix is an
executable registry-vs-corpus guard; it is a G3 DevEx enabler; the mechanism already exists
(`tool_surface.docs` + the FR-017/018 token scan) and needs its *reach* extended to the doctrine-source
prompt + skill corpus with three finding codes.

---

## 4. Coherent mission shape — decomposition & sequencing

### 4a. The 16 bugs are TWO classes on the two systemic problems #2007 names

- **Class A — Command-contract drift** (#1, #5, #9, #13, #16, partly #3): published surface ≠ registered
  surface. Structural fix = §3 snippet guard + edit the SOURCE prompts/skills/docs to the real surface.
  **Risk: low. Topology: none.**
- **Class B — Mission-state surface split / non-adoption** (#4, #6, #7, #8, #10, #11, #12, #14, #15):
  command resolves the wrong authority or flattens the typed error. Structural fix = thread the resolved
  `ExecutionContext`, anchor primary-vs-coord reads on the right fragment, preserve `ActionContextError.
  code` + checked paths through JSON. **Risk: medium (semantics). Topology: read-side adoption, not the
  #1716 write-side redesign.**
- **Class C — orthogonal point fixes** (#2 charter hash/JSON-safety/side-effects, #6 submodule `.git`
  root detection): real, independently shippable, not part of the context-authority spine.

### 4b. Does this match the 6 suggested sub-issues? — **Mostly, with one consolidation and one split**

| #2007 suggested sub-issue | Class | Verdict |
|---|---|---|
| Command-surface validation & docs/prompt drift | A | ✅ keep — this is the §3 guard (G3) |
| Mission context/read-path resolver unification | B | ✅ keep — the **spine**; this is #1832-shape adoption + error pass-through |
| Coordination worktree repair surface (#13) | A+B | ⚠️ **split**: the *missing command/hint* is Class A (point to existing `doctor workspaces --fix`); the *classification* is Class B |
| Implement/review action JSON contract (#16) | A | ✅ keep — but it is *contract decision* (add `--json` or document text-only), gated by the §3 guard |
| Submodule/root detection hardening (#6) | C | ✅ keep — independent, anytime |
| Charter status/sync/preflight consistency (#2) | C | ✅ keep — independent, anytime |

One **consolidation**: #4, #7, #11, #12, #14, #15 are **not six bugs — they are one surface** (the
resolver-adoption / typed-error-pass-through spine) at six call sites, exactly as the SCORING-SYNTHESIS
reframe said of #1716/#1832/#1619 ("one surface at four grains"). They belong in **one** sub-issue
(the "resolver unification" one), decomposed by call site, not six independent fixes.

### 4c. Sequencing against the parked ExecutionContext-hardening

The #1619 builder-hardening (un-mutate `ExecutionContext`, close `branch_name ≠ branch_ref.target_
branch`, freeze the substrate) is **parked** by the operator's safety values-call. #2007's adoption
spine **depends on** the SSOT being trustworthy. Sequence:

1. **Now, alongside the naming rider (safe, additive):**
   - **WP-G — Command-snippet contract guard** (§3). G3 enabler, satisfies AC#1, zero topology risk.
     Edit SOURCE prompts/skills/docs to real surfaces as the guard's first green pass.
   - **WP-C1/C2 — Class C point fixes** (#6 submodule root, #2 charter). Independent, anytime.

2. **Next (the read-side adoption spine — #1832-shape, the panel's "safe entry inside impact"):**
   - **WP-Adopt — typed-error pass-through**: every named consumer (`next` query mode #15,
     `agent context resolve` #14, `finalize-tasks` #12, `decision open` #8) catches `ActionContextError`
     and **re-emits `.code` + checked paths** in JSON instead of reclassifying. *This is the single
     cheapest, highest-coverage Class-B WP — it is pure pass-through, no resolution change.*
   - **WP-Read — wrong-authority reads**: `decision open` resolves identity through the context before
     traversal validation (#8); `finalize-tasks` reads planning inputs from `WorkspaceFragment.primary_
     root` while writing to the placement ref (#11); `setup-plan` exact-one auto-select or doc-require
     `--mission` consistently (#4/#7).

3. **Then (or in-cycle if capacity) — the builder-hardening the spine leans on:**
   - **WP-Freeze — un-mutate `ExecutionContext`**: stop the post-freeze substrate mutation
     (`resolution.py:793–801`); assemble `branch_name`/`workspace_path` from the resolved fragments in
     one shot; add the action-vs-bulk guardrail. This is the #1619 internal-invariant grain — closing
     the in-authority split-brain the adoption spine assumes away. *Do this before or with WP-Read so
     consumers thread a trustworthy context.*

4. **Deferred to the #1716 write-side patch (NOT in #2007's coherent core):** coordination topology
   redesign. #2007 touches it only at #11's placement edge, which WP-Read handles as adoption. Do **not**
   pull the #1716 topology rework into #2007 — it would re-blow the scope the operator deliberately
   parked.

### 4d. The one DIR-031 guardrail that bounds the whole mission

Threading the resolved context is right; **threading the topology *decision* into consumers is the
failure mode that re-creates the split-brain.** Every Class-B WP must consume *resolved* fragments
(`primary_root`, `status_read_dir`, `placement_ref`) and never re-walk the coord→primary ladder itself.
`decision open`'s dual-resolve (§1b) is the live instance of violating this — the fix is to delete the
second authority (the `kitty-specs/` escape-walk for resolved paths), keeping traversal rejection for
**raw operator tokens only**, exactly as #2007's fix direction states.

---

## 5. Decision-documented summary (for the mission spec)

> **#2007's prescribed "single typed mission-context/read-path authority" IS the #1619
> `ExecutionContext` / `resolve_action_context` SSOT (verified: `context.py:184`, `resolution.py:682`;
> four of six named commands already route through it).** The failing commands fail because they
> **bypass it** (`decision open` dual-resolve `decision.py:86–107` vs `:425`; `finalize-tasks` reads
> inputs off the coord surface) or **flatten its typed `ActionContextError.code`** (#12/#14/#15) — the
> non-adoption thesis, now corroborated by Robert's field screenshots instead of churn forensics. A
> residual split-brain also lives *in* the authority (mutable composite; `branch_name` mutated
> post-fragment-freeze, `resolution.py:793–801`) — so the work is **finish + adopt**, not build.
>
> **#2007 does not flip the 3.2.1 safety→impact values-call.** It (a) supplies the missing real-world
> severity evidence for the **read-side adoption grain** of the impact surface — the panel's "safe entry
> inside the impact plan" — and (b) **elevates command-contract drift**, a class the panel ignored, to a
> cheap safe co-lead. It is the data that says *do the read-side adoption + the snippet guard now*; it is
> **not** the data that says *lead with #1716*. The operator's safety lead is compatible with starting
> #2007 because #2007's safest WPs are the same low-risk adoption/pass-through cuts.
>
> **Single highest-leverage structural fix:** **thread the resolved `ExecutionContext` into the seven
> named commands and preserve `ActionContextError.code` + checked paths end-to-end (no reclassification),
> gated by a repo-wide command-snippet guard that validates CLI snippets in doctrine-SOURCE prompts /
> skills / docs against the live Typer registry** (three finding codes: unregistered-path,
> unknown-flag, internal-as-public). Both extend mechanisms already on this branch
> (`tool_surface.docs`, `test_docs_cli_reference_parity` FR-017/018; `resolve_action_context`
> `ActionContextError`). The error-pass-through WP is the single cheapest, highest-coverage cut — it
> closes #12/#14/#15 with no resolution change — and is the right first Class-B move.
>
> **Coherent decomposition:** Class A (drift → snippet guard, G3, now) · Class B (resolver adoption +
> typed-error pass-through — **one surface, six call sites**, not six bugs) · Class C (#2 charter, #6
> submodule — independent, anytime). The #1619 builder-freeze sequences just before/with the read-side
> adoption; the #1716 write-side topology redesign stays **out** of #2007's core (touched only at #11's
> placement edge). DIR-031 binding guardrail: consumers thread *resolved* fragments; the builder owns the
> coord/primary translation; never thread the topology *decision* into consumers (the `decision open`
> dual-resolve is the live violation to delete).
