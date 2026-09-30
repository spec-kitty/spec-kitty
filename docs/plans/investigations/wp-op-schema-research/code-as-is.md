---
title: 'WP & Op Schema Research — Code As-Is (architect-alphonso)'
description: 'Verbatim research report: current reality of WP and Op records and the content-address machinery, grounding the WP & Op schema-model idea.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/investigations/wp-op-schema-research/README.md
- docs/plans/investigations/wp-op-schema-model.md
---
# Code-As-Is Map: WP & Op Lifecycle and Content-Address Machinery

> **Historical (verbatim research report, 2026-07-16).** Archived input to the [WP & Op schema model](../wp-op-schema-model.md) idea note; milestone references are to the closed 3.2.x cycle and the retired 3.3.x line. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

Lens: the current reality of Work-Package and Op records, so the schema-model idea can be judged. All paths relative to the repo root.

## 1. WP file lifecycle — where WPs are created, mutated, parsed, validated

**The working reality is markdown, not YAML.** A hard prevalence check settles the central ambiguity in the idea note:

- `tasks/WP*.md` markdown files: **278 missions** use them.
- `wps.yaml` structured manifest: **5 missions** (`find kitty-specs -name wps.yaml`).

So the markdown-with-frontmatter WP file *is* the source of truth in practice. A structured `wps.yaml` precedent already exists but never became authoritative — see §5.

**Distinct frontmatter parse entrypoints (5 competing implementations):**

| Entrypoint | Location | Style |
|---|---|---|
| `read_frontmatter` / `FrontmatterManager.read` | `src/specify_cli/frontmatter.py:327`, class `:35` | ruamel round-trip, canonical writer |
| `parse_frontmatter` | `src/specify_cli/template/renderer.py:23` | returns `(fm, body, padding)` |
| `split_frontmatter` + `extract_scalar` | `src/specify_cli/task_utils/support.py:191` | **regex line-scraping**, no YAML parse |
| `_parse_frontmatter_scripts` | `src/specify_cli/manifest.py:68` | bespoke line loop |
| `parse_frontmatter` | `src/specify_cli/doc_analysis/gap_analysis.py:83` | doc-analysis variant |

**Two competing typed WP models on top of those parsers:**
- `WPMetadata` — `src/specify_cli/status/wp_metadata.py:183`. A proper frozen Pydantic model, `extra="forbid"`, ~40 fields. This is the closest thing to the idea's "code-owned logical model" and it *already exists*.
- `WorkPackage` — `src/specify_cli/task_utils/support.py:269`. A dataclass holding raw `frontmatter: str` / `body: str` strings, whose accessors (`work_package_id`, `title`, `agent`, `shell_pid`) each call `extract_scalar` regex on the raw string. This is the "parses defensively" drift the idea complains about, in one file.

**Breadth of the parse surface:** ~**49 modules** import a WP frontmatter/body reader (`grep` for `WorkPackage|WPMetadata|read_frontmatter|parse_frontmatter|split_frontmatter|extract_scalar` across `src/specify_cli/`). Notable classes of call site:
- **Create/materialize:** `cli/commands/agent/tasks_materialization.py`, `mission_finalize.py`, `core/mission_creation.py` (layout/templating at `:86`, `:369`).
- **Mutate frontmatter:** `frontmatter.py:176/:347` `add_history_entry`; `task_metadata_validation.py:82` `repair_lane_mismatch` (marked **MIGRATION-ONLY**).
- **Parse dependencies from prose:** `core/dependency_parser.py` — three regex declaration formats (`Depends on`, `**Dependencies**:`, bullet list) scanned out of tasks.md free text (`:152–:264`).
- **Validate:** `core/dependency_graph.py:153` raises on filename↔frontmatter WP-ID mismatch; `task_metadata_validation.py:181` `validate_task_metadata`; ownership validation in `ownership/frontmatter_source.py`, `ownership/validation.py`.

Bottom line: the idea's premise #4 ("numerous call sites parse WP frontmatter and bodies … one code-owned model is exactly the consolidation degodding favours") is **accurate and understated** — there are five parsers and two typed models, one of which (`WorkPackage`) is a raw-string regex scraper.

## 2. Hash / content-address machinery — what trips the "mismatch"

The "hashcode mismatch" the idea cites is the **mission dossier parity/content hash**, not a review-time hash (the review-prompt binding in `review/prompt_metadata.py` is field-based context matching, not content hashing; the review flow itself does no content hash — confirmed).

- **What is hashed:** the **whole file, as opaque bytes.** `src/specify_cli/dossier/hasher.py` `hash_file()` streams the raw bytes through SHA-256 — no frontmatter/body split, no semantic normalization.
- **What is classified as a hashable artifact:** `src/specify_cli/dossier/indexer.py:242` — `tasks.md` **and any `wp*.md`** are indexed as dossier artifacts, each getting `content_hash_sha256` (`dossier/models.py:57`).
- **How drift is computed:** `dossier/snapshot.py:25` `compute_parity_hash_from_dossier` = SHA-256 over the **sorted list of per-artifact content hashes** (`:42`, `:65`). `parity_hash_sha256` (`models.py:336`) is the mission's content-address; drift = parity inequality (`models.py:390` `__ne__`).

**Why a semantically-inert edit trips it:** because the hash is over the entire file's bytes, *any* change — flipping a subtask checkbox in the prose body, appending a `history` entry to frontmatter — mutates `content_hash_sha256` → mutates the sorted-hash parity → drift. The machinery has no notion of "semantic vs bookkeeping." The idea's premise #1 is **confirmed exactly**.

**Is the mutable bookkeeping already separated? Partly — this is the most important nuance.**
- **Lane / review status: YES, already event-sourced.** `frontmatter.py:49` `WP_FIELD_ORDER` carries the explicit comment: *"Mutable status fields (lane, review_status, reviewed_by, review_feedback) are managed exclusively via the canonical event log and are NOT written here."* Lane lives in `status.events.jsonl` (append-only, reduced by `status/reducer.py`); `WorkPackage.lane` (`task_utils/support.py`) delegates to `get_wp_lane(feature_dir, wp_id)`, not to frontmatter. `task_metadata_validation.py`'s lane read/repair is explicitly **MIGRATION-ONLY**.
- **Still-in-file bookkeeping: `history`.** `frontmatter.py:68` still lists `history`, and `add_history_entry` (`:176/:347`) appends to it in place — a mutable list that perturbs the file hash. `shell_pid` / `shell_pid_created_at` (claim-time, mutable) also live in frontmatter (`:65–66`).

So the "bookkeeping churn" half is **substantially already solved** for the field that used to churn hardest (lane). What remains perturbing the content hash: the residual mutable frontmatter (`history`, `shell_pid`) **and** any body edits (checkbox flips). The append-only status model (`src/specify_cli/status/`) is the working proof-of-concept for the exact separation the idea wants.

## 3. Frontmatter ↔ body duplication — the real cost

Concretely duplicated across the three representations that can coexist:

| Fact | Frontmatter | Prose body | `wps.yaml` (when present) |
|---|---|---|---|
| WP id | `work_package_id` | `## Work Package WP01: …` heading | `id` |
| Title | `title` | same heading | `title` |
| Dependencies | `dependencies: [...]` | `**Dependencies**: WP01, WP02` (parsed by `dependency_parser.py`) | `dependencies` |
| Requirement refs | `requirement_refs` | prose `**Requirement Refs**:` | `requirement_refs` |
| Owned files | `owned_files` | prose scope headings | `owned_files` |
| Subtasks | `subtasks` | checkbox list in body | `subtasks` |

The concrete cost is not storage — it is **three parsers that can disagree**:
- `dependency_graph.py:153` exists *solely* to catch filename↔frontmatter WP-id divergence (a guard that would be unnecessary if id had one home).
- `core/dependency_parser.py` is 298 lines of regex whose entire job is to recover, from prose, a `dependencies` list that already exists structured in frontmatter — because for the 278 markdown missions the prose and frontmatter are authored separately and `wps_manifest.generate_tasks_md_from_manifest` (`:170`) re-emits the same facts into `tasks.md`. That is duplication maintained by regex.

Real cost, honestly stated: it is **moderate, not catastrophic** — the duplication is mostly a maintenance/consistency tax (defensive parsing, divergence guards, a 298-line prose dependency scraper), not a data-loss risk. The hash-churn cost (§2) is the sharper pain.

## 4. Op record today — facts vs. intent/scope

`src/specify_cli/invocation/record.py` (schema v2) is already a clean, frozen Pydantic pair, and there is already a contract at **`kitty-specs/do-dispatch-open-op-lifecycle-01KTSJ2H/contracts/op-record-events.md`** (the idea's question "is there already a contracts/op-record-events.md" — **yes**).

**`OpStartedEvent` (`record.py:39`) persists:** `invocation_id` (ULID), `profile_id`, `action` (canonical token), `request_text` (the raw ask), `actor`, `mode_of_work` (`task_execution|advisory|mission_step|query`), `governance_context_hash` + `governance_context_available`, `router_confidence`, optional `mission_id`/`wp_id`.

**`OpCompletedEvent` (`record.py:65`) persists:** `outcome` (`done|failed|abandoned`), `closed_by`, optional `evidence_ref`.

**What is genuinely captured about "why/what":** only `request_text` (verbatim user ask) and `action` (a verb token). Governance context is captured as a **hash**, not content — so the *why the router chose this* is fingerprinted, not readable. Intent is the raw request string; no structured decomposition.

**What a "WP-shaped intent+scope+outcome" would add that is not captured today:**
- **Scope / change surface** — no analogue of WP `owned_files` / `scope`. An Op does not record what surface it intended to touch.
- **Structured intent** — no `requirement_refs`-style "this addresses X" linkage; only free `request_text`.
- **Reasoning / decision trail** — captured only as `governance_context_hash` and (optionally, opt-in) a Tier-2 evidence blob (`.kittify/evidence/<id>/evidence.md`, `record.py:325` `promote_to_evidence`), which is free-form, not schema'd.
- **Acceptance / done-criteria** — `outcome` is a 3-value enum; there is no structured "what would make this done."

The idea's framing — "it stores *that* something was done, not *what* was undertaken and to what end" — is **accurate**. The gap is real. Note the mitigating design intent: `MinimalViableTrailPolicy` (`record.py:128`) deliberately keeps Ops lightweight (Tier 1 mandatory JSONL; scope/evidence Tier 2/3 opt-in). Adding a mandatory structured scope block cuts against that "minimal viable trail" philosophy and must be reconciled with it, not bolted on.

## 5. Model-first precedent — how cleanly WP/Op could reuse it

`scripts/generate_schemas.py` is real and proven (idea premise #3 confirmed): a `REGISTRY` (`:60`) maps schema stem → Pydantic model; `register()`/`register_custom()` (`:65`/`:78`); `model_json_schema()` → deterministic post-processing (enum inlining, `$defs`→`definitions`, anyOf-null simplification, `--check` drift gate). **But it is scoped entirely to `src/doctrine/*/models.py` → `src/doctrine/schemas/`** (`SCHEMA_DIR` at `:34`). The post-processing (`_REFERENCE_KINDS`, `ArtifactKind` subsetting, kebab-case aliasing) is doctrine-shaped.

**Reuse assessment for WP/Op:**
- **Models already exist and are Pydantic:** `WPMetadata` (`status/wp_metadata.py:183`), `WpsManifest`/`WorkPackageEntry` (`core/wps_manifest.py:15/:61`), `OpStartedEvent`/`OpCompletedEvent` (`record.py:39/:65`). None are registered in `generate_schemas.py`, none emit a YAML schema today.
- **Registering them is mechanically cheap** — a few `register()` calls + a widened `SCHEMA_DIR` or a second registry. The post-processing pipeline is generic enough for flat models like `WPMetadata`.
- **The hard part is not schema generation** — it is (a) collapsing the 5 parsers + 2 models onto one, and (b) making one representation *authoritative* with markdown derived. The `wps.yaml` experiment (`core/wps_manifest.py`, only 5/278 missions) is direct evidence that **shipping the model is easy; making it the source of truth and getting missions/agents onto it is what stalls.**

## Verdict

**The code-as-is substantially *supports* the idea's diagnosis but materially *undercuts* two of its framing assumptions — in ways that shrink the useful scope.**

Supported:
- The parse-surface sprawl is real and worse than stated: **5 frontmatter parsers, 2 typed WP models** (one a regex scraper), ~49 consumer modules. Consolidation is genuinely the degodding-shaped win.
- The whole-file content-address is real: `dossier/hasher.py` hashes entire bytes; `dossier/indexer.py:242` feeds `wp*.md` into a parity hash; any inert edit → drift. Premise #1 confirmed exactly.
- The Op intent/scope gap is real, and `contracts/op-record-events.md` already exists to extend.
- The model-first machinery (`generate_schemas.py`) is proven and reusable.

Undercut / de-scoped:
- **"Bookkeeping churn needs a new store" is half-false.** Lane/review status is *already* event-sourced out of the file into `status.events.jsonl` (`frontmatter.py:49` comment; `status/reducer.py`). The idea's "separate mutable bookkeeping from semantic content" is **already the shipped architecture for the fields that churned most.** What remains in-file is `history` + `shell_pid` + prose body edits. So the WP file mostly needs to **shed its last mutable fields and stop being whole-file-hashed**, not adopt a brand-new authoritative store.
- **The structured-authoritative precedent already exists and stalled.** `wps.yaml` (`core/wps_manifest.py`) is exactly "code-owned Pydantic model + YAML persistence + generated markdown" — and it reached 5 of 278 missions. The blocker was never the model; it was authority migration and agent/human editing workflows. Any spec must confront *why wps.yaml didn't win* or it repeats the experiment.

**Smallest de-risking first slice** (highest signal, lowest blast radius, no authority migration):

> **Make the WP content-address semantic-only.** Change dossier hashing (`dossier/indexer.py` + `dossier/hasher.py`) so a WP artifact's `content_hash_sha256` is computed over a **normalized semantic projection** — parse via the *one* canonical model (`WPMetadata`), drop the mutable fields (`history`, `shell_pid`, `shell_pid_created_at`) and normalize the body, then hash that. This directly kills the hash-churn pain (premise #1) **without** touching the source-of-truth question, without a markdown→YAML migration, and without agent-workflow disruption. It also forces the first real consolidation step: routing dossier indexing through `WPMetadata` instead of raw bytes, retiring one parser path.

Two independent follow-on slices, each shippable alone: (2) collapse the `WorkPackage` regex-scraper (`task_utils/support.py:269`) onto `WPMetadata` and register `WPMetadata` in `generate_schemas.py` (pure consolidation, no format change); (3) extend the Op record with an **optional** structured `scope`/`intent` block on `OpStartedEvent` — respecting the `MinimalViableTrailPolicy` opt-in philosophy rather than making it mandatory. The full "YAML authoritative, markdown derived" ambition should be treated as a *separate, higher-risk decision* explicitly informed by the `wps.yaml` post-mortem — not folded into the de-risking slice.

Key files for a spec author: `src/specify_cli/dossier/{hasher,indexer,models,snapshot}.py` (hash boundary), `src/specify_cli/status/wp_metadata.py` (the model to canonicalize on), `src/specify_cli/task_utils/support.py` (the scraper to retire), `src/specify_cli/core/wps_manifest.py` (the stalled precedent), `src/specify_cli/invocation/record.py` + `kitty-specs/do-dispatch-open-op-lifecycle-01KTSJ2H/contracts/op-record-events.md` (Op extension surface), `scripts/generate_schemas.py` (reusable schema machinery).
