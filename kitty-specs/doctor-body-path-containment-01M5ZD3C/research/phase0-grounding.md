# Phase 0 grounding — #6418 (doctor charter-packs: escaping body_path reported healthy)

Grounded on `origin/main` 143a39fc (4.0.0rc8), 2026-10-27. Static reading plus an entry-point reproduction.

## 1. Code grounding (re-verified on 143a39fc)

| Claim | Location | Verified |
|---|---|---|
| The doctor's exit code reads `CharterPackHealthReport.healthy`, which treats a non-empty `org_drg["errors"]` as unhealthy | `src/specify_cli/cli/commands/_charter_pack_collect.py` `_collect_profile_health` (l.216–298), `_append_org_errors` (l.829–838) | yes |
| `_collect_org_layer_data` loads the fragments, merges, then runs the dangling-endpoint and override checks. It has **no** `body_path` check | `_charter_pack_collect.py` l.662–759, `_run_post_merge_org_checks` l.791–826 | yes |
| The human org-layer section is a separate renderer that recomputes the same checks (the two halves of one command must agree) | `src/specify_cli/cli/commands/_profile_health_render.py` `_render_org_layer_section` (~l.300–390) | yes |
| An authored fragment node declares `body_path: str \| None` (pack-root-relative per the org-DRG contract) | `src/charter/offering/drg/org_pack_loader.py` `_OrgDRGNode` l.360–391 | yes |
| Discovered nodes (`_DiscoveredOrgDRGNode`) carry `body_path` from artifact YAML, relative to their own file (e.g. skills) | `org_pack_loader.py` `_collect_artifact_nodes` l.719–744; `pack_skills/validation.py` l.115–117 | yes — out of scope (decision: authored nodes only) |
| `OrgDRGFragment.authored_nodes` separates authored from discovered nodes | `org_pack_loader.py` l.468–479 | yes |
| The fragment does not carry its pack root; `load_org_drg` resolves it via `load_pack_registry(repo_root)` → `pack.effective_root(repo_root)` | `src/charter/activation/drg_activation.py` l.159–181 | yes |
| Shared containment primitive: `resolve_relative_path_within_root(root, rel)` rejects absolute (POSIX/Windows/UNC), `..` parts, and resolve-outside (symlink); raises `OrgPackSubdirEscapeError`; does no content read | `src/charter/offering/drg/org_pack_config.py` l.136–180; re-exported by `charter.drg` (l.107–166) | yes |
| `AssetPathEscapeError` (NFR-006, the PROMISES.md authority) wraps the same primitive | `src/charter/offering/assets/repository.py` l.138–157 | yes |
| Nothing in core reads an org fragment node's `body_path` target; only `merge.py`'s layer-rule heuristic reads the string | `src/charter/offering/drg/merge.py` l.411–418 | yes |

### Red-first reproduction (entry point)

A shell port of `CharterSteps.ESCAPING_ASSET_NODES` (`acceptance-jvm/.../CharterSteps.java` l.258): fresh `spec-kitty init`, a team pack at `.kittify/team-pack` with `pack.yaml`, `org-charter.yaml` and `drg/fragment.yaml` declaring `kind: assets, body_path: ../../../../etc/hostname`, registered under `charter_packs.org.packs`.

- `spec-kitty doctor charter-packs --json` → **exit 0**, `org_drg.errors: []`.
- With `body_path: /etc/hostname` → **exit 0**.

The defect is live on `main`.

## 2. Architectural alignment

- ADR `2026-10-16-1` (+ Amendment 2026-10-19): the charter stays in core and is replaced in place behind `charter.offering.api`. The new predicate belongs in the in-core offering layer (`charter.offering.drg`, beside the primitive) and is re-exported through the existing `charter.drg` facade the doctor already imports. No layer-rule, package-set or `pyproject.toml` change. Nothing is extracted.
- Pack tiers: no edit to `packs/built-in/` or `packs/internal/`. The fix is product code plus test fixtures.
- Org-pack loading is unchanged (C-002). Refusing at load would change activation/runtime behaviour for every caller. That is a product change beyond #6418 and is left as a follow-up.
- spec-kitty-charter (bc6ad11): `PackPolicy` checks the asset manifest `path` (`ASSET_PATH_ESCAPE`) and lists `body_path` as an allowed `FRAGMENT_NODE_KEYS` entry, but does not check fragment `body_path` containment. Core and the service agree today (both miss it). After this mission, core's doctor is stricter than the service validator. Follow-up issue to be filed in spec-kitty-charter so the two agree. No conformance-corpus case exists for this.

Nothing here would be redone by an in-flight decision, so there is no stop-and-ask.

## 3. Related issues and surfaces

- No open PR touches `_charter_pack_collect.py`, `_profile_health_render.py` or `org_pack_loader.py` (searched 2026-10-27).
- Open PRs: #6718/#6716 (#6193 lock/glossary Java port), #6620 (#4292 mypy in the agent-profile repository), #5540. None overlaps.
- #6715 (consolidation self-approval), #6675 (write API): no overlap. M3 touches `charter/activation/pack_manager.py`, which this mission does not touch.
- #6419 moved PR-CHARTER-SHARING-004 to `@wip @defect:6418` (closed, merged). #6369 is the escalation and #2519 the parent epic.
- The prior governed mission `doctor-org-body-path-containment` (Ivan-Melck, 2026-10-20) has no folder, branch or PR. Its grounding and approach (issue comment 6292357748) match this one and are credited.

## 4. Tidy-first

- Preparatory, behaviour-preserving step: none is needed beyond keeping `_collect_org_layer_data` under the complexity ceiling. The new check is a separate helper, called once, not inlined into the collector body.
