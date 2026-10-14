---
type: explanation
updated: 2026-10-13
audience: agentic-framework-core-team
mission: derived-consumer-census-01M4V5P5
issue: 6173
---

# Code grounding — durable derived consumer census for CI fan-out (#6173)

Read-only grounding for #6173 (task **C** of #6166). No edits are made by this
pass. It records the *current* fan-out mechanism verbatim, the runtime-resolved
read path a grep census misses, every lockstep/architectural gate the mechanism
touches, the per-module CI-cost picture, the #6164 collision, and the churn
history — so the mechanism this mission builds is grounded in code-truth, not a
pure grep.

The sense of **routing** throughout this note is **placement / consumer
routing** (which *test module* a changed `src/**` or `packs/**` path is fanned
out to), never dispatch/profile routing, branch-target routing, or model/task
routing (`docs/context/orchestration.md#routing`).

---

## 1. The current fan-out mechanism (verbatim)

### 1.1 The single routing authority — `scripts/ci/gate_selection.py`

`gate_selection.py` is the ONE importable authority for "which shards/modules
does a changed-path set select" (FR-016 / #2476). It **parses** the two
hand-authored routing authorities out of `.github/workflows/ci-router.yml`
(the dorny `changes` filter block `group -> globs[]`, and the job
`if: needs.changes.outputs.<group>` gates) and reads the module inventory from
`.github/ci-module-registry.yml`. It never re-encodes a second path->group map.

The hand-maintained fan-out this mission replaces lives in **one dict**,
`GROUP_MODULE_FANOUT` (L57–86):

```python
GROUP_MODULE_FANOUT: dict[str, frozenset[str]] = {
    "mission_manifest": frozenset({"charter", "dossier", "specify_cli_runtime"}),
    "mission_pack_content": frozenset({"charter", "next", "missions", "execution_context", "dossier", "specify_cli_runtime"}),
    "mission_type_definitions": frozenset({"charter", "core_misc", "upgrade"}),
    "cli_lifecycle": frozenset({"agent", "core_misc"}),
}
```

These four keys are **non-src router groups** (data/path groups that carry no
`src/` glob). The module *sets* are hand-curated — the comment block above each
entry names, per module, why it is included ("reads prompt.md BODIES", "imports
the lifecycle command module", etc.). **This set is exactly what drifts** as new
consumers appear (#6166 Risks): a new test module that reads a mission-step
prompt, or imports `lifecycle.py`, is invisible to this dict until someone edits
it by hand.

Selection flow (`select_modules`, L306–356):

1. `select_gates(paths)` → `matched_groups` (parsed-router answer) + the
   FR-004 fail-closed `unmatched_src` probe.
2. `mode == "full"` or `unmatched_src` → **every** registry module (run-all).
3. otherwise `src_selected = matched_groups & registry_modules`.
4. **fan-out union**: `for group, targets in GROUP_MODULE_FANOUT: if group in matched_groups: src_selected |= (targets & modules)`.
5. **tests-only mirror** (`_modules_for_test_paths`, L257–303): a diff confined
   to `tests/<dir>/**` matches no `src/` glob, so each changed test path is
   mapped back to its owning module(s) via the registry's `test_dirs` plus the
   deterministic "canonical test mirror" (`_canonical_test_mirror`: a root
   `<prefix>/<leaf>/**` mirrors to `tests/<leaf>`; a single-file root
   `<prefix>/<name>.py` mirrors to `tests/<name>`), probed back through the
   router so a tests-only diff never narrows its src twin (#4454).

The module universe is the **registry inventory**
(`_registry_module_names`), NOT `router.src_backed_groups` — because the `ci`
module's group is non-src (`scripts/ci/**` + `.github/workflows/**`) and
intersecting against src-backed groups would silently drop it (#4386).

### 1.2 The router groups — `.github/workflows/ci-router.yml`

The four non-src fan-out groups are declared in three load-bearing places in
the router: the dorny **filter** block (`steps.filter.with.filters`, L180+),
the `changes` job **outputs** block (L80–150), and — for src-backed groups only
— the FR-004 **unmatched** union step. The fan-out groups are **non-src**, so
they appear in the filter + outputs but NOT in the unmatched union (a data-only
pack path can never *mask* an unmapped `src/**` change — FR-004).

The hand-authored globs (the path patterns — the OTHER hand-maintained half):

```yaml
mission_manifest:
  - 'packs/built-in/missions/**/expected-artifacts.yaml'          # #6125
mission_pack_content:                                             # #6166 task A
  - 'packs/built-in/missions/mission-steps/**'
  - 'packs/built-in/missions/*/templates/**'
  - 'packs/built-in/missions/*/mission.yaml'
  - 'packs/built-in/missions/*/mission-runtime.yaml'
  - 'packs/built-in/missions/*/actions/**'
  - 'packs/built-in/missions/*/governance-profile.yaml'
  - 'packs/built-in/missions/built_in_step_contracts/**'
mission_type_definitions:                                         # #6166 landing
  - 'packs/built-in/missions/mission_types/**'
cli_lifecycle:                                                    # #6166 task B
  - '**/specify_cli/cli/commands/lifecycle.py'
```

The globs are **deliberately sub-tree-specific** (not a blanket
`packs/built-in/missions/**`), so a genuinely non-consumed pack file (e.g. a
`README.md`) still selects zero modules and the `corpus` zero-module golden is
preserved. `cli_lifecycle`'s glob is `**/`-prefixed (not `src/...`) so the group
is not src-backed — the same shape `contract_tools` / `mission_state` use to
name a src file without becoming a code-shard gate.

### 1.3 The module registry — `.github/ci-module-registry.yml`

21 `modules[]` rows (consumed verbatim from the WP05 scrub — see §3). Each row
declares `module`, `roots` (`src/**` ownership globs), `cov_targets`,
`shard_count` (from measured `ci-shard-timings.json`, never file counts), and an
optional explicit `test_dirs`. A row without `test_dirs` falls back to the
canonical mirror. `out_of_matrix_test_dirs` records every `tests/` directory no
row claims, with a reason (the #4369 anti-false-green ledger).

Fan-out target modules relevant to this mission and their `test_dirs`:

| Module | `test_dirs` (or mirror) | reads pack content? |
|---|---|---|
| `next` | `tests/next` (mirror of `runtime/**`) | yes — resolves prompts at runtime (§2) |
| `charter` | `tests/charter`, `tests/charter_offering` | yes — asserts on prompt/step-contract/mission-type **content** |
| `missions` | `tests/missions` (mirror) | yes — governance-profile.yaml, mission.yaml |
| `execution_context` | `tests/mission_runtime`, `tests/runtime`, `tests/specify_cli/cli/commands/agent` | yes — mission-runtime.yaml, prompt resolution |
| `dossier` | `tests/dossier`, `tests/specify_cli/dossier` | yes — `expected-artifacts.yaml` manifests |
| `specify_cli_runtime` | `tests/specify_cli/runtime` | yes — real manifests under `src/charter/offering/missions/**` |
| `core_misc` | 18 dirs incl. `tests/specify_cli/design`, `tests/core` | mission_types (default_missions_root) |
| `upgrade` | `tests/specify_cli/upgrade`, `.../migrations` | copies shipped mission-type `*.yaml` |
| `agent` | `tests/agent`, `tests/specify_cli/agent_utils` | imports `cli.commands.lifecycle` |

---

## 2. How a test consumes a src/packs path at RUNTIME without naming it

The canonical case the census must NOT miss (#6156 / the `tests/next` break):
`tests/next/test_discovery_step_contract.py` executes the software-dev
`discovery`/`research` step prompt **through the real `next` CLI**, which
resolves and reads the pack prompt without the assertion path ever naming it.

Traced codepath (verbatim via codegraph):

```
spec-kitty next / research()                              (CLI entry)
  -> runtime.agent_commands / runtime.resolver.resolve_command(name, project_dir, mission)
     resolver.resolve_command  (src/specify_cli/runtime/resolver.py:740)
       -> _resolve_asset(name, "command-templates", project_dir, mission)
          6-tier precedence; tier 6 = package default:
          -> charter.offering.missions.MissionTemplateRepository.default()
             ._command_template_path(mission, name)
          -> resolves to <package>/missions/<mission>/command-templates/<name>
  ... and for the per-step prompt body:
  -> agent_commands.py:366  template = templates_dir / command / "prompt.md"
     agent_commands.py:616  prepared.source(templates / command / "prompt.md")
     -> opens packs/built-in/missions/mission-steps/<mission>/<step>/prompt.md
        via .is_file() / .read_text()  — the path is a RUNTIME-COMPUTED Path,
        never a string literal in the test.
```

`charter.offering.resolver._resolve_asset` (L185–256) walks six tiers and
`.is_file()`-probes each; the package-default tier (6) opens the real
`packs/built-in/missions/...` file. **A static grep of `tests/next/*.py` for
`packs/built-in/missions` would miss this** (the historical #6156 break: the
test named no pack path). Therefore the census needs a **runtime read-capture**
(observe filesystem `open`/`is_file` of `src/**` and `packs/**` paths while the
resolver runs), attributed to the consuming test module — not only a static
import/string scan. This is the acceptance-validating case for the census
(#6173 done-when: "the census reproduces the three pins").

> Note: `tests/next/test_discovery_step_contract.py` today *also* names the
> prompt path in a module-level constant (`_RESEARCH_PROMPT`) for its invocation
> extraction, so a static scan happens to catch *this* file now. The runtime
> capture is still required: the break was real before the test was hardened,
> and other resolver-driven consumers (e.g. `tests/runtime/test_bridge_io.py`,
> `tests/charter_offering/missions/*`) reach pack content through resolution
> without a literal path. The census must be robust to the general case, not to
> one hardened file.

---

## 3. Architectural / lockstep gates that reference these files (must stay honestly green)

The routing surface is guarded by a **three-way lockstep** plus several
authority/wiring gates. The census mechanism must not loosen any of them.

- **`tests/architectural/test_gate_selection_authority.py`** — the single
  authority's own guard. Pins: docs/corpus select zero shards; FR-004
  fail-closed; `test_group_module_fanout_is_wired` **pins the exact fan-out
  sets** (L264–272) and that every fan-out group is a router filter group and
  every target is a registry module; the three #6166 historical pins
  (`test_mission_step_prompt_edit_selects_next`,
  `test_lifecycle_command_edit_selects_agent`,
  `test_manifest_edit_still_selects_dossier_regression_guard`); the
  `_CONSUMED_PACK_SUBTREE_CASES` parametrized pins; the `README.md` zero-module
  guard; and `_modules_for_test_paths` mirror/reachability (#4454). **This is
  the file the three historical pins live in; the new census gate must agree
  with it and must not weaken `test_group_module_fanout_is_wired`.**
- **`tests/architectural/test_ci_router_transcription_guards.py`** — pins the
  router's three transcriptions to their SSOTs: (1)
  `test_router_src_filters_derive_from_scrub_verbatim` — every **scrub** group's
  router globs equal its scrub roots verbatim, and every scrub group is
  transcribed into the router (scrub→router, never router→scrub; so a non-src
  fan-out group that has NO scrub row is allowed to live only in the router);
  (2) `test_changes_outputs_cover_every_routing_group` — `changes.outputs`
  (minus `unmatched`) == filter routing groups; (3)
  `test_unmatched_union_covers_every_src_backed_group` — the unmatched union ==
  src-backed groups exactly. Plus `test_changes_outputs_never_force_run_all_on_push`.
- **`tests/architectural/test_workflow_coherence.py`** — FR-003b: every filter
  group must have a job `if:` consumer **unless** it is in
  `_DELIBERATELY_UNGATED_FILTER_GROUPS` (L337–348), which lists `any_src`, `ci`,
  `scenarios`, `acceptance_jvm`, and the four fan-out groups
  (`mission_manifest`, `mission_pack_content`, `cli_lifecycle`,
  `mission_type_definitions`). It also checks every glob is live (matches ≥1
  tracked path) and every literal `--cov` target exists.
- **`tests/architectural/test_module_shard_registry.py`** — registry consumes
  the scrub verbatim (`test_registry_consumes_scrub_verbatim_no_divergent_rescrub`),
  LPT shard-count/skew, out-of-matrix evidence, and reachability.
- **`tests/architectural/test_ci_quality_path_filters.py`** — `ci-quality.yml`
  path filters.
- **`tests/ci/test_ci_module_wiring.py`** — wires the `ci` module's routing +
  its two deliberate exclusions; the `ci` module exemption in
  `_DELIBERATELY_UNGATED_FILTER_GROUPS` is safe only together with this pin.
- **Three-way lockstep** — router filter / `.github/ci-module-registry.yml` /
  `tests/release/ci_retirement_scrub.json`. The scrub has `groups` (21 src/non-src
  rows consumed verbatim by the registry), plus `non_src_router_groups`
  (docs/corpus/e2e/mission_state) and `excluded_surfaces` (retired subsystems).
  **The fan-out groups (`mission_manifest`/`mission_pack_content`/`cli_lifecycle`/
  `mission_type_definitions`) have NO scrub row** — they are non-src fan-out
  groups that live only in the router filter + `changes.outputs` +
  `GROUP_MODULE_FANOUT` + `_DELIBERATELY_UNGATED_FILTER_GROUPS`. This is the
  precedent (#6131) the census must respect: the census derives the *module
  sets*; it does not add scrub/registry rows for these groups.

Implication for the design: the drift-prone hand-maintained surface is the
**module sets in `GROUP_MODULE_FANOUT`**. The census can become the single
authority for "module M consumes path P"; the fan-out module sets can be
**derived** from it (matching each consumed path against the router's non-src
group globs), which keeps `test_group_module_fanout_is_wired` green while making
those values census-derived rather than hand-curated. The router *globs* stay
hand-authored (GitHub Actions needs literal YAML; pinned by the transcription
guard) but are **verified** by the new census-routing gate: a census consumer
whose path matches no routing group (or a src group that does not select its
module) reds the gate — the "new unrouted consumer reds a gate" property.

---

## 4. CI-cost picture per module (`ci-module-registry.yml` `shard_count`)

| Module | shard_count | Module | shard_count |
|---|---|---|---|
| charter | **7** (long pole) | core_misc | 5 |
| upgrade | 4 | agent | 3 |
| execution_context | 3 | cli | 2 |
| consolidation | 2 | next | 2 |
| missions, dossier, specify_cli_runtime, unit, ci, auth, kernel, glossary, status, review, lanes, post_merge, release | 1 each | | |

Recorded per-edit shard deltas from the #6174 (T0+A+B) PR body:

| Edit | shards selected |
|---|---|
| `lifecycle.py` | 10 (cli 2 + agent 3 + core_misc 5) |
| `mission-steps/.../prompt.md` | 15 (charter 7, next 2, execution_context 3, missions 1, dossier 1, specify_cli_runtime 1) |
| `mission_types/plan.yaml` | 16 (charter 7 + core_misc 5 + upgrade 4) |
| pack `README.md` | 0 |

`charter` at **7 shards** dominates every `mission_pack_content` edit. #6173
"also enables" within-module file selection to shrink that: charter's
prompt-reading coverage concentrates in `tests/charter_offering/missions/*` +
`tests/charter_offering/test_*prompt*` files, so a finer within-module selection
could keep correctness while cutting shards. This mission measures the derived
routing's selected-shard delta on recent merged PR diffs and either lands
within-module selection or carves it to a named follow-up (dispatch §3).

---

## 5. Interaction with the in-flight #6164 session (collision + sequencing)

#6164 ("Remove frozen hosted/sync/drain from core", branch
`issue-6164-remove-hosted-from-core`) may remove module rows / router groups and
so touch `.github/ci-module-registry.yml`, `ci-router.yml`, and the scrub.

Status at grounding (2026-10-13): **#6164 has NOT opened its PR** — a PR search
for `6164` returns only #6168 and #6169, which merely *defer* work to #6164
(`moments.py` removal, a 4th S5779 site), confirming #6164's surfaces
(`zeitgeist_client`, `moments`, hosted/sync/drain) are still present on `main`.
The `issue-6164-remove-hosted-from-core` branch is not yet in the remote branch
list.

Binding consequences for this mission (dispatch §2):
- Branch off the **latest** `main` at each rebase; expect the module set to
  change under me.
- Make the census mechanism **robust to the module set changing** — derive from
  the registry/router *as they are*, never hardcode today's module list. The
  census script and gate read `_registry_module_names()` / `load_router()` at
  runtime, so a removed/renamed module row flows through automatically.
- On a lockstep conflict at rebase: re-run the registry/scrub/transcription
  lockstep gates and keep MY diff to the census mechanism; do not take or revert
  #6164's module-row changes.
- If #6164's direction makes C infeasible as scoped, STOP and report.

The one surface to watch: if #6164 removes `zeitgeist_client` (a `core_misc`
test_dir + router glob) the registry/router/scrub change together; the census is
indifferent (it never names `zeitgeist_client`). No fan-out target module of
this mission is on #6164's removal path, so the collision risk to the census's
*content* is low; the risk is purely textual lockstep churn in the shared files.

---

## 6. 90-day churn / fix history

`git log --since=90.days -- scripts/ci .github/workflows/ci-router.yml
.github/ci-module-registry.yml tests/release/ci_retirement_scrub.json` in this
cloud checkout returns 7 commits, all dated **2026-10-13** — the clone is
depth-limited (`clone_depth=50`), so the visible window is the last ~day, not a
true 90-day history. Within that window the routing files are **hot**:

- `23db9453` fix(ci): fan mission pack content and lifecycle.py out to their
  consumer test modules (#6166) — the T0+A+B PR (#6174) this mission replaces.
- `5908cbbe` fix(landing): route every consumed mission-pack sub-tree to its
  consumer modules — the #6174 landing fold (added `mission_type_definitions`,
  widened the subtree pins).
- scenario-contract landing commits (`18a9ec5e`, `283e4c6e`, `22265860`,
  `09a6539c`, `bcfb0208`) touched `scripts/ci`/workflows the same day.

From the issues read (not git): #6131 (issue #6125) closed the
`expected-artifacts.yaml` row and minted the `dossier` module and the
`mission_manifest` fan-out; #6174 (issue #6172) added `mission_pack_content` /
`cli_lifecycle` / `mission_type_definitions`. The parent epic #4437 ("CI
pipeline honesty") holds same-class siblings: #3463 (coord CLI-shard skip),
#5034 (`tests/agent` never selected), #4368 (six src packages ride the
catch-all), #5623 (Mission Status reality check not selected for its inputs).
The #6166 triage notes part C "would likely subsume #4368 and #5623, and the
routing half of #3463" — i.e. the derived census is intended as the durable
replacement for the whole hand-list class, not only the three #6166 symptoms.

**Reading:** these files churn every time a new consumer appears (three routing
PRs in two days: #6131, #6174, and the landing fold). That recurrence IS the
#6166 Risk ("hand lists drift as new consumers appear") and the direct
justification for a derived census.

---

## 7. Design implications (carried into specify/plan)

1. **Census script** (`scripts/ci/`) — produces, per test module, the `src/**`
   and `packs/**` paths its tests consume, by (a) **static** import + file-read
   + string-literal AST/text scan over each module's `test_dirs`, and (b)
   **runtime** read-capture of resolver-driven opens (the §2 prompt case). Emits
   a committed, regenerable census artifact. Reads `_registry_module_names()` /
   `load_router()` so it is robust to the module set changing (#6164).
2. **Architectural gate** — for each census `(module, consumed-path)`, assert
   `select_modules([path])` ⊇ `{module}`; red when a consumer is unrouted.
   Red-first proof: (a) the three historical pins (green now; demonstrably red
   against a router with the globs stripped, à la the authority gate's YAML-
   mutation test); (b) a **planted** unrouted consumer reds the gate (the whole
   point). Must coexist with `test_group_module_fanout_is_wired` and the
   transcription lockstep without loosening either.
3. **Replace the hand lists** — make the census the single authority and
   **derive** `GROUP_MODULE_FANOUT`'s module sets from it (match each consumed
   path against the router's non-src group globs). Router globs stay hand-
   authored (GHA-required, transcription-pinned) and census-verified. No scrub/
   registry row added for the non-src fan-out groups (the #6131 precedent).
4. **Cost delta + within-module selection** — measure the derived routing's
   selected-shard delta on recent merged PR diffs; land charter within-module
   selection (`tests/charter_offering/missions/*` + `test_*prompt*`) to cut the
   7-shard cost, or carve it to a named follow-up if too large for this PR.

**Non-goals (dispatch §3):** no `src/**` product-behaviour change; do not loosen
or delete any existing gate; no size/length ratchet gate (operator ruling).
