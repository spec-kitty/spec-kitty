# Discovery: charter consistency-check and the project layer

Mission: `charter-consistency-project-layer-01M67J5F` — issue
spec-kitty/spec-kitty#6749.

## Decisions

### D-001 — The reported directive/styleguide symptom is already fixed; pin it, do not re-fix it

**Evidence.** `origin/main` at `512567eee7` contains #6433
(`a8dd1812a6`, "consistent activate output, skill freeze warning, one stored
activation spelling", 2026-10-29), which rewrote
`charter.activation.consistency_check._is_known` so artifact kinds resolve through
the run's `IdentityIndex` (built-in + org + **project** layers) instead of the
built-in/org-only id catalog:

```
def _is_known(cli_kind, token, identity, all_offering_ids):
    kind = _artifact_kind(cli_kind)
    if kind is not None:
        return identity.knows(kind, token)          # built-in, org AND project
    return token in all_offering_ids.get(cli_kind, frozenset())   # mission-type only
```

The issue cites `main` `6a3e5cde`; `git merge-base --is-ancestor 6a3e5cde
origin/main` is true and `git rev-list --count 6a3e5cde..origin/main` is 199, so
#6433 post-dates the cited commit.

Reproduction at the CLI on `512567eee7`, in a scratch git project: `charter new
directive PROJ_DIR_900` + `charter new styleguide proj-style-900` (both land under
`.kittify/charter-packs/`), `charter activate` both, then
`charter consistency-check --json` → `coherent: true`, `unknown_references: []`.
The declared-id and `<kind>:<id>`-URN spellings of the same project-layer artifacts
give the same result.

**Consequence.** FR-007 pins the fixed behaviour as a regression, it is not
re-implemented.

### D-002 — The named root cause is still live, and it still produces a false incoherence

**Evidence.** `_collect_all_offering_ids` still resolves only the org chain:

```python
org_chain = resolve_pack_chain(ctx.require_repo_root(), strict=False)
for kind in YAML_KEY_MAP:
    all_ids[kind] = manager.list_available(ctx, kind, org_root_chain=org_chain)
```

No `layer_roots=resolve_layer_roots(...)`, so the project pack root
(`.kittify/charter-packs/`) is never scanned. #6338 added the org chain; the
project layer was never added.

The one kind that still consults that catalog is `mission-type`
(`_artifact_kind("mission-type")` returns `None`). Reproduced on `512567eee7`:

- project layer: `.kittify/missions/mission_types/proj-mission.yaml`
  (`schema_version: 1`, `id: proj-mission`, `display_name`, `extends: software-dev`);
- `.kittify/charter/activation.yaml`: `mission_type_activations: [proj-mission]`;
- `charter mission-type list --json` →
  `[{"id": "proj-mission", "source_layer": "project", "activated": true, ...}]`
  (the reader resolves it, layer included — positive control);
- `charter consistency-check --json` → `coherent: false`,
  `"unknown_references": ["mission-type/proj-mission"]`,
  `suggestion: "mission-type/proj-mission: Not found in doctrine..."`, exit 1.

`charter.activation.missions.resolve_layered_mission_types(built-in mission_types
dir, PackContext.from_config(root))` returns
`['documentation', 'plan', 'proj-mission', 'research', 'software-dev']` — the
authority every reader (runtime roster, `charter mission-type list`, `charter
activate`'s preflight) already uses.

**Consequence.** FR-001/FR-002. The check's mission-type membership must come from
the layered roster, not from `list_available`, whose mission-type branch is
deliberately flat/built-in-only (`_scan_layout_for(None)` → `layered=False`), so
passing layer roots to it could never fix this kind.

### D-003 — `list_available`'s mission-type branch cannot be layered; the roster is the authority

`_scan_layout_for(ArtifactKind | None)` returns `("missions/mission_types",
"*.yaml", layered=False)` for `kind is None`, and `_scan_layer_dirs` only walks
layer roots when `layered=True`. The project layer's mission types live at
`.kittify/missions/mission_types/` (`mission_type_repository.PROJECT_MISSION_TYPES_RELATIVE`),
which is **not** under the project pack root, so joining
`.kittify/charter-packs/` + `missions/mission_types` would scan a path the runtime
never reads. Threading roots into `list_available` alone is therefore necessary
(FR-003, the catalog must stop being structurally blind) but not sufficient
(FR-002, membership for this kind comes from the roster).

### D-004 — Keep one authority per kind; no third scanner

- artifact kinds → `IdentityIndex` (already the case since #6433);
- `mission-type` → `resolve_layered_mission_types` through the `charter.missions`
  facade (layer rule: `charter` must not import `specify_cli`);
- the catalog keeps its `list_available` scan for every other kind, now with the
  canonical project layer roots, so it cannot drift from the readers again.

Rejected: a hand-rolled project `missions/mission_types` walk inside
`consistency_check` (a second membership rule); re-deriving the roster from
`MissionTypeRepository.default()` (built-in only, the bug itself); changing
`_scan_layout_for` to layer mission types (CLI-wide availability blast radius, and
it would scan a path the runtime does not read).

### D-005 — Malformed project mission-type must fail closed

`scan_mission_types_dir` loud-fails on a malformed/unreadable file anywhere in a
scanned layer (documented contract; `charter activate`'s preflight relies on it).
Today such a file is invisible to the check (built-in-only catalog) and the
artifact is reported `unknown`. After the fix the roster raises, and the check must
surface a `verification_errors` entry ("could not verify"), exactly like its other
corrupt-input branches (#2530), never raise out of `run_consistency_check` and
never pass silently. This is a deliberate behaviour change from `unknown` to
`could not verify`: both are incoherent, the new one is honest about why.

### D-006 — Out of scope: the activation writer's availability refusal

`charter activate mission-type proj-mission` on a project-layer type is refused by
`ActiveCharterManager.activate`'s availability scan with `Unknown mission-type ID`
(same project-blind catalog), even though the preflight's layered roster resolved
the type one step earlier. Same root cause, different surface: fixing it means
deciding what the mission-type availability layout should be across every
consumer (`charter list --all`, `charter activate`, doctor). Filed as a follow-up
issue and named in the PR's `## Deferred` section; not changed here.

## Evidence index

- Pre-fix behaviour: `charter consistency-check --json` on the project-layer
  mission-type fixture (reproduced above, exit 1).
- Reader agreement: `charter mission-type list --json` (`activated: true`,
  `source_layer: project`).
- Code: `src/charter/activation/consistency_check.py` (`_collect_all_offering_ids`
  L376, `_is_known` L426, call site L1663), `src/charter/activation/pack_manager.py`
  (`_scan_layout_for` L239, `list_available_detailed` L1350),
  `src/charter/offering/missions/mission_type_repository.py` (`PROJECT_MISSION_TYPES_RELATIVE`
  L379, `_resolve_layered_mission_types_uncached` L518),
  `src/charter/activation/mission_type_profile_repository.py` (project override
  dir), `src/specify_cli/cli/commands/charter/mission_type.py`
  (`resolve_layered_roster` L81), `src/charter/missions.py` (facade re-export).
- Prior art: #6338 (org chain added to the catalog), #6337 (org-overlay coherence
  test pair in `tests/charter_offering/test_activation_parity_guard.py`), #6433
  (identity index), #2530 (fail-closed corrupt input).

## Open questions

- None blocking. The one operator-visible decision (mission-type availability
  layout for the activation writer) is explicitly deferred to the follow-up issue;
  the consistency check is fixed without it.
