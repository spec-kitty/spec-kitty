# Tracer: Design Decisions

Seeded at planning; append during implementation.

## Decisions

- **D1 — Canonical source = charter `ResolvedMissionType`.** Not an extension of the legacy
  `mission.yaml`, not a `mission_runtime` surface. Justification: charter is the governance
  authority; enforced chain `kernel <- charter <- {glossary,runtime,mission_runtime} <- specify_cli`;
  `specify_cli` already imports `charter`; C-001 forbids the reverse; `mission_runtime` outbound
  ledger is shrink-only.
- **D2 — `paths` is the only new schema.** Add a `path_conventions` doctrine slot; relocate
  `VALID_PATH_KEYS` from `specify_cli/mission.py` into `charter` (charter cannot import specify_cli).
- **D3 — artifacts migrate, not reinvented.** `artifacts.required/.optional` sourced from
  `ResolvedMissionType.expected_artifacts` / dossier `ManifestRegistry` (already carries
  required+optional+blocking — no lossy collapse).
- **D4 — Retire vestigial fields** (`workflow.phases` descriptions, `domain`, `version`,
  `validation`, `mcp_tools`, `agent_context`, `commands`, `task_types/metadata`) — zero functional
  consumers. `name`/`description` → doctrine `display_name`.
- **D5 — Preserve typeless→software-dev TEMPLATE default (C-006/FR-003a).** Removing it is #2660,
  sequenced later. Typed-but-unknown surfaces visibly; typeless stays silent+default.
- **D6 — Name the placement `routing` sense** (artifact-placement seam), distinct from #3830's
  dispatch/profile routing.

- **D7 — Typed-unknown correction is in-scope (#3831), not #2660.** Two distinct fallbacks:
  `mission.py:783` typeless coalesce = PRESERVED (C-006/FR-003a, #2660 removes it later);
  `mission.py:801-806` typed-but-unknown warn-and-substitute = IN SCOPE (it *is* the org-blind
  defect). The post-spec squad caught that the grounding lumped both under #2660 — corrected here.
- **D8 — #4088 fixed by migration, not a second override path.** Charter's override home is
  `.kittify/doctrine/mission_types/` (precedence project>org>builtin); the legacy
  `.kittify/overrides/missions/` is migrated there (FR-008) rather than taught to charter — single
  canonical authority (C-003).
- **D9 — `Mission` name collision** (`specify_cli/mission.py` vs `charter/offering/missions/models.py:137`)
  — name both in the ADR.

- **D10 — RE-SCOPE (2026-09-21, operator decision): targeted org-aware loader, NOT full resolver retirement.**
  WP03 discovered the planning premise was wrong: the charter/doctrine tier does NOT carry
  built-in path/artifact data equivalent to legacy `mission.yaml`, and the two encode *different
  concerns* — legacy `artifacts.required/.optional` is **template-selection**; charter
  `expected_artifacts.required_by_step` is **runtime step-gate completeness**. `path_conventions`
  is `null` for all three built-ins (WP02 added the slot, nothing populates it). Token sets diverge
  (software-dev optional missing `contracts/`/`checklists/`, adds `gap-analysis.md`/`lint-report.json`;
  documentation `release.md` required-vs-optional; etc.). So "retire the resolver, converge on
  charter" is the **full #2652 epic** (needs a two-concern merge + canonical built-in data authoring),
  not this slice. The architect's "expected_artifacts already carries required+optional+blocking —
  no loss" was incorrect.
  **New approach:** extend the loader (`_mission_path_by_name`/`get_mission_by_name`/
  `get_mission_for_feature`) to resolve through the org-aware tiers (override → project → org →
  packaged), building a `Mission` for an org-tier type that ships only the sparse
  `mission_types/<type>.yaml` (neutral own conventions, NOT software-dev's). Built-ins keep their
  legacy path unchanged (NFR-001 safe). #4088's override tier is consulted **live** (no migration).
  Typeless→software-dev *template* default preserved; typed-unknown surfaces. This is exactly the
  #3831 author's originally-suggested minimal fix. WP04 (retire resolver) and WP05 (migration) are
  DROPPED/canceled; full convergence deferred to #2652.

## Open questions (resolve during plan/implement)
-
