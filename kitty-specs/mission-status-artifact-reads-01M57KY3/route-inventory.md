# Removed dashboard routes: inventory and new homes (#5533)

**Source of the inventory.** `src/specify_cli/dashboard/handlers/router.py` and its handlers (`api.py`, `features.py`,
`glossary.py`, `lint.py`, `static.py`) and `src/specify_cli/dossier/api.py`, read at `3d5c85d09^`, the parent of the commit
that removed the dashboard (`3d5c85d09 feat(dashboard): remove the bundled dashboard (#5530)`, PR #5545, 2026-10-01).
Recover any file with `git show 3d5c85d09^:<path>`. Nothing here comes from the retracted PRs #6264 and #6265.

**Homes.** A route goes to exactly one of these:

- **Contract.** An operation of `contracts/mission-status/openapi.yaml` (`1.0.0-SNAPSHOT`). The column "served" says
  whether `services/mission-status-api/` answers it after this Mission.
- **Verb.** A governance or CLI domain verb with `--json`. The ADR keeps governance out of the Read API (route table of ADR
  `2026-10-01-2`).
- **DROPPED.** The route had no consumer beyond the dashboard process or its own UI. Each one is listed in this
  inventory, and the #957 / #5533 changelog entry under `[Unreleased]` points here (the released #5530 removal entry is
  left as it shipped; the changelog style gate caps an entry's length).

**Coverage.** "full" means the new home answers everything the route answered **for every file the contract allows**. The
contract deliberately refuses what the dashboard served: files over 262,144 bytes (413), files that are not strict UTF-8
text (415, where the dashboard decoded with replacement characters), and files holding a credential (422). It also
redacts host paths and e-mail addresses. "partial" means part of the route's answer has no home, and the gap is named.

## Status routes (D-2; listed for completeness)

| # | Method and route | Handler | What it served | New home | Coverage |
|---|---|---|---|---|---|
| R01 | `GET /api/features` | `FeatureHandler.handle_features_list` | Every Mission, with kanban counts, the active Mission and worktree, and the project path | Contract `listMissions` (served) and `getProject` (served) | partial: `active_feature_id`, `active_worktree` and `worktrees_root` described the dashboard process's working directory and are DROPPED. `project_path` is a host path and is never served (redaction). |
| R02 | `GET /api/kanban/<mission>` | `FeatureHandler.handle_kanban` | One Mission's WPs by lane, weighted percentage, legacy flag | Contract `getMission` and `getWorkPackage` (not served yet: the #957 detail slice). Interim: verb `spec-kitty agent tasks status --mission <h> --json` | partial until the #957 detail slice lands. `is_legacy` / `upgrade_needed` are DROPPED (migration-era flags). |

## Artifact routes (this Mission)

| # | Method and route | Handler | What it served | New home | Coverage |
|---|---|---|---|---|---|
| R03 | `GET /api/artifact/<mission>/spec` | `handle_artifact` | `spec.md` as text/plain | Contract `getArtifactContent?path=spec.md` (served) | full. Kind `spec`; the body is JSON with redacted text, not raw text. |
| R04 | `GET /api/artifact/<mission>/plan` | `handle_artifact` | `plan.md` | `getArtifactContent?path=plan.md` (served) | full (kind `plan`) |
| R05 | `GET /api/artifact/<mission>/tasks` | `handle_artifact` | `tasks.md` | `getArtifactContent?path=tasks.md` (served) | full (kind `tasks`) |
| R06 | `GET /api/artifact/<mission>/research` | `handle_artifact` | `research.md` | `getArtifactContent?path=research.md` (served) | full (kind `research`) |
| R07 | `GET /api/artifact/<mission>/quickstart` | `handle_artifact` | `quickstart.md` | `getArtifactContent?path=quickstart.md` (served) | full (kind `quickstart`) |
| R08 | `GET /api/artifact/<mission>/data-model` | `handle_artifact` | `data-model.md` | `getArtifactContent?path=data-model.md` (served) | full (kind `data_model`) |
| R09 | "analyze" (named in #5533) | none: the dashboard had no route for `analysis-report.md` | nothing | `getArtifactContent?path=analysis-report.md` (served) | new: kind `analysis_report`, a read the dashboard never offered |
| R10 | `GET /api/research/<mission>` | `handle_research` | The content of `research.md` as `main_file`, plus a listing of `research/**` with icons | Contract `listArtifacts` (served), filtered by kind `research` client-side, plus `getArtifactContent?path=research.md` (served) | full. Two calls instead of one. Icons are DROPPED (a UI concern). |
| R11 | `GET /api/research/<mission>/<path>` | `handle_research` | One research file | `getArtifactContent?path=research/<path>` (served) | full |
| R12 | `GET /api/contracts/<mission>` | `_handle_artifact_directory("contracts")` | Listing of `contracts/**` | `listArtifacts` (served), kind `contract` | full |
| R13 | `GET /api/contracts/<mission>/<path>` | `_handle_artifact_directory("contracts")` | One contract file | `getArtifactContent?path=contracts/<path>` (served) | full |
| R14 | `GET /api/checklists/<mission>` | `_handle_artifact_directory("checklists")` | Listing of `checklists/**` | `listArtifacts` (served), kind `checklist` | full |
| R15 | `GET /api/checklists/<mission>/<path>` | `_handle_artifact_directory("checklists")` | One checklist file | `getArtifactContent?path=checklists/<path>` (served) | full |
| R16 | `GET /api/dossier/artifacts?feature=<slug>&class=&wp_id=&step_id=&required_only=` | `DossierAPIHandler.handle_dossier_artifacts` | The dossier index of a Mission's artifacts, filterable | `listArtifacts` (served) | partial: the listing covers every eligible file and its kind. The dossier's `class`, `wp_id`, `step_id` and `required_only` filters and its required/optional flags have no contract field. No page loaded a caller: `dashboard.js` never called `/api/dossier`, and `static/js/dossier-panel.js` did (lines 16, 53, 69, 308), but no template included it. |
| R17 | `GET /api/dossier/artifacts/<artifact_key>?feature=<slug>` | `handle_dossier_artifact_detail` | One artifact's content (up to 5 MB) and media type | `getArtifactContent` (served) | partial: addressed by path, not by dossier key; the cap is 262,144 bytes (contract) |
| R18 | `GET /api/dossier/overview?feature=<slug>` | `handle_dossier_overview` | Completeness status, counts, parity hash from the dossier snapshot | Verb `spec-kitty reconcile --mission <slug> --json` (parity against the recorded snapshot) | partial: parity is served; the completeness counts have no verb. Not covered by the contract (contract CHANGELOG, #5625). |
| R19 | `GET /api/dossier/snapshots/export?feature=<slug>` | `handle_dossier_snapshot_export` | The snapshot JSON "for SaaS import" | **DROPPED** | Hosted import surface. Frozen (AGENTS.md "Team Kitty", ADR D-9). The snapshot file stays on disk for `reconcile`. |

## Governance and diagnostics routes (not the Read API; ADR route table)

| # | Method and route | Handler | What it served | New home | Coverage |
|---|---|---|---|---|---|
| R20 | `GET /api/charter` | `APIHandler.handle_charter` | The `charter.md` prose body (404 when no charter, empty when only `charter.yaml` exists) | Verb `spec-kitty charter status --json` (presence and sync state) | partial: no verb returns the prose body as JSON. Proposed slice G1. |
| R21 | `GET /api/charter-lint` | `LintTileHandler.handle_charter_lint` | Decay-watch tile counts read from the cached `.kittify/lint-report.json` | Verb `spec-kitty charter lint --json` (`scanned_at`, `feature_scope`, `duration_seconds`, `finding_count`, `findings`) | partial: the verb recomputes, and also writes the report, instead of reading the cache. The per-category counts are derivable from `findings`. Proposed slice G3 (#955 stays closed). |
| R22 | `GET /api/glossary-terms` | `GlossaryHandler.handle_glossary_terms` | Every term: surface, definition, status, confidence | Verb `spec-kitty glossary list --json` (`surface`, `scope`, `definition`, `status`, `confidence`) | full |
| R23 | `GET /api/glossary-health` | `GlossaryHandler.handle_glossary_health` | Term counts by status, high-severity drift count, orphaned-term count, entity-page state, last conflict, seed validation errors | Verbs `spec-kitty glossary validate .kittify/glossaries --json` (seed errors; the path argument is required), `glossary conflicts --json` (conflicts; the high-severity drift count needs the severity filter the handler applied to `iter_semantic_conflicts`), `glossary list --json` (counts by status) | partial: the orphaned-term count, the entity-page state and a ready-made high-severity count have no verb. Proposed slice G2 (#954 stays closed). |
| R24 | `GET /glossary` | `GlossaryHandler.handle_glossary_page` | An HTML glossary page | **DROPPED** | UI page. The docs-site glossary page assets moved to `scripts/docs/glossary_page/` (ADR D-8). |
| R25 | `GET /api/diagnostics` | `APIHandler.handle_diagnostics` | Project diagnostics | Verb `spec-kitty verify-setup --diagnostics --json` | full, less the dashboard health panel (`dashboard_health` key removed in #5530) |

## Daemon and UI routes

| # | Method and route | Handler | What it served | New home | Coverage |
|---|---|---|---|---|---|
| R26 | `GET /` | `APIHandler.handle_root` | The dashboard HTML | **DROPPED** | Replaced by the separate UI (#5531) |
| R27 | `GET /static/*` | `StaticHandler.handle_static` | Dashboard JS, CSS and assets | **DROPPED** | Replaced by the separate UI |
| R28 | `GET /api/health` | `APIHandler.handle_health` | Daemon identity, token, preflight banner | **DROPPED** | Daemon removed. The token leak was #4768. |
| R29 | `GET /api/shutdown`, `POST /api/shutdown` | `APIHandler.handle_shutdown` | Stops the daemon | **DROPPED** | Daemon removed |

**Count.** The router dispatches 18 path patterns (17 for GET, plus POST `/api/shutdown`). Expanded by the
`/api/artifact/<name>` table (6 names), the listing/file split of the three artifact-directory routes, and the 4 dossier
sub-routes, that gives 28 rows (R01–R08, R10–R29). R09 is not a removed route: it records the "analyze" view that #5533
names but the dashboard never served. Every route of `router.py` at `3d5c85d09^` has exactly one row.

## Proposed replacement slices for the governance reads (operator to decide; not implemented)

These replace the closed #954 (glossary service) and #955 (lint/decay-watch service). Each is a domain verb with `--json`
in its own context, not a Read API operation (ADR `2026-10-01-2`, route table and Decision Drivers, "Bounded contexts").

- **G1 — charter body read.** `spec-kitty charter show --json`: `{present, source: "charter.md"|"charter.yaml"|null,
  body}`, read-only, redacted like the artifact reads. It closes R20's gap. Owner: charter context (`src/charter/`), through
  `charter.activation.api`.
- **G2 — glossary health.** `spec-kitty glossary health --json`: the `GlossaryHealthResponse` fields (counts by status,
  high-severity drift, orphaned terms, entity-page state, last conflict, validation errors) composed from the existing
  glossary services (`src/glossary/`). It closes R23's gap.
- **G3 — decay-watch summary without a rescan.** `spec-kitty charter lint --json --cached` (or `charter lint report
  --json`): read `.kittify/lint-report.json` without recomputing or writing, with per-category counts. It closes R21's gap,
  and a UI poll would then not rewrite the report.
- **G4 (optional) — dossier completeness.** Add completeness counts to `spec-kitty reconcile --json`, or a `dossier
  overview --json` verb. It closes R18's gap. Low value: no dashboard UI read it.

If the operator wants a UI to reach any of these through the read service rather than a subprocess, that is a contract
change (a new operation in a minor version) and a separate decision.
