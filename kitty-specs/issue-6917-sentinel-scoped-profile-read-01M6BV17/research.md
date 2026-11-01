# Discovery — issue #6917 (scoped agent-profile sentinel read)

Mission `issue-6917-sentinel-scoped-profile-read-01M6BV17`. Findings captured before the
plan, on the mission branch, against `main` @ `287a226cfe`.

## Reproduction and measurement

Measured in one process against this checkout (`uv run python`, warm imports, isolated `HOME`):

| Step | Cost | Evidence |
| --- | --- | --- |
| `build_active_charter_service(repo_root)` | **1.136 s** | `infer_repo_languages` 0.342 s + `PackContext.from_config` 0.361 s + catalog/service construction |
| `.agent_profile_repository` (first read) | **0.935 s** | parses **26** agent-profile YAML documents |
| …of which the shipped lineage graph | **0.543 s** | `load_built_in_graph()` (`packs/built-in/graph.yaml`, 358 nodes) |
| …of which the 26 profile documents | **0.247 s** | memoised per change (#5526), so a second read is ~0.02 s |

`agent tasks status` reaches that pair through `_st_render_human`
(`src/specify_cli/cli/commands/agent/tasks_status_cmd.py`) to answer one structural boolean per
claimed row (`_get_hic_marker` → `profile.sentinel`). Confirmed reproduction: the call site builds
the service and calls `.agent_profile_repository`, which is the only reason the whole profile
catalogue and the lineage graph are materialised on a read-only render.

## Decisions

### D1 — Scope the *existing* loader instead of adding a second profile reader

`AgentProfileRepository` gains a keyword-only, opt-in `only_ids` scope: when set, `_load_layer`
parses only files whose canonical name is `<profile-id>.agent.yaml` in each layer. Everything else
is the repository's own pipeline — `parse_shipped_yaml`, inline-reference rejection, schema
validation, skip diagnostics, built-in→org→project field merge, the `applies_to_languages` scope
filter and provenance. Default `None` keeps today's load byte-for-byte (C-003).

Precedent: #6462 solved the same class of problem for the catalog with
`load_offering_catalog(domains=...)` — a validated scope on the existing loader, `None` meaning
"everything", rather than a parallel loader. A hand-rolled raw-YAML reader was rejected: it would
silently disagree with the repository on invalid files and language scope, which is exactly the
"second source of truth" the charter's Single canonical authority principle forbids.

**Open point, resolved:** the id→file mapping. The repository derives `profile-id` from YAML
content, but every profile in this repo and in the documented layouts
(`docs/development/how-to/create-a-doctrine-artifact.md`, `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`)
is authored as `<profile-id>.agent.yaml`. The scoped read therefore resolves by that file
convention and documents it; a parity test compares the scoped lookup against the full repository
for every id shipped in `packs/built-in/agent_profiles/` so drift is caught.

### D2 — Restore #6462's lazy lineage graph

`9041b3bbfa perf(6462): build profile lineage on first use` made the shipped DRG lazy through one
`_graph()` accessor. It is **not** in the current tree: `repository.py` again does
`self._drg = drg if drg is not None else self._default_drg()` in `__init__` (line 266), so every
profile-map reader pays 0.543 s for a graph it never reads. The loss is not a decision anyone can
point at — it disappeared during a later lineage refactor.

Restoring the accessor is required here for a clean scoped read (a sentinel read must not pay the
graph) and it is what #6462 already shipped and documented. It is behaviour-preserving: an explicit
`drg=` stays authoritative, the `DRGLoadError` empty-graph degradation moves inside `_graph()`, and
`_drg` is touched in exactly one class (no external reach-arounds — verified with
`grep -rn '\._drg\b' src tests`).

### D3 — One new accessor on the sole door, no new construction site

* `CharterOfferingService.agent_profile_sentinels(ids)` (offering layer, the repository's owner)
  builds a scoped repository from the same layer directories it already derives.
* `ActiveCharterService.agent_profile_sentinels(ids)` (sole door) delegates to it, documenting that
  `sentinel` is structural and never activation-gated — the same rationale WP01 of
  `charter-sole-door-bypass-closure-01KZ3WAA` records for `agent_profile_repository`.
* `build_agent_profile_sentinels(repo_root, ids)` in `active_charter_service_builder.py` (the ONE
  builder module) resolves the layers and returns the mapping **without** building `PackContext`
  or the activation ledger, because no activation key gates a structural field.

All three live in files Gate 1 / Gate 2 already exempt, so `specify_cli` gains no construction site
and the boundary ratchet needs no new exclusion. `specify_cli` calls the builder function only —
this is the first `specify_cli` consumer of the new accessor.

### D4 — Board reads the ids its rows name, once per render

`_st_render_human` already scans every row (`_needs_profile_lookup`). It now collects the distinct
non-empty `agent_profile` ids from the view, performs ONE scoped lookup, and threads the resulting
mapping into `_get_hic_marker`, which becomes a dict hit. Falsy/non-`str` ids keep returning `""`;
an unknown id yields no marker and no exception.

## Evidence trail

- Issue #6917 body (measurement table `main @ dfe9efb0e8`), its acceptance sketch.
- `kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/contracts/charter-doctrine-service-contract.md`
  — the pinned accessor semantics the new accessor extends.
- `tests/architectural/test_charter_sole_door_agent_profile_repository.py` gate 1,
  `…_offering_service.py`, `…_inner_reacharound.py`, `…_resolver_imports.py` — the gates that must
  stay green with zero new exclusions.
- `tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py` and
  `tests/charter_offering/test_human_in_charge_profile.py` — the structural-sentinel ratchets that
  pin marker behaviour under deny and narrowing.

## Open questions for plan

1. Whether the restore in D2 needs its own changelog bullet or rides on the #6917 entry (leaning:
   one entry, naming both effects, since both are the same user-visible latency on the same path).
2. Exact census-test shape: count `parse_shipped_yaml`/`yaml.load` calls on the agent-profile
   directory through the production entry point (`agent tasks status` render), following #6462's
   `tests/charter/test_*_census*.py` style, plus a positive control that a non-scoped
   `list_all()` read still parses the whole catalogue.
