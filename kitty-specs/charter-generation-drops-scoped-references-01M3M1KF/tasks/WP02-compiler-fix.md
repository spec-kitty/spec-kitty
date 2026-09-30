---
work_package_id: WP02
title: Compiler fix — scope-filtered placeholders, reason classification, whole-kind fail-closed
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: fix/charter-generation-drops-scoped-references-5257
merge_target_branch: fix/charter-generation-drops-scoped-references-5257
branch_strategy: Planning artifacts for this mission were generated on fix/charter-generation-drops-scoped-references-5257. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-generation-drops-scoped-references-5257 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-generation-drops-scoped-references-01M3M1KF
base_commit: 3759ea9e4f334e5fea85f4c74a9e99fb831bb7fc
created_at: '2026-09-28T21:17:16.172215+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
history: []
agent_profile: implementer-ivan
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_compiler_scope_filtered_placeholder.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/compiler.py
- tests/charter/test_compiler_scope_filtered_placeholder.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Compiler fix: scope-filtered placeholders, reason classification, whole-kind fail-closed

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Fix `src/charter/activation/compiler.py` so an activated-but-unresolvable reference is never
silently dropped: a `SCOPE_FILTERED` miss becomes a reason-bearing placeholder
`CharterReference`; a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` miss stays diagnostics-only (Contract
C4 preserved) but gains a reason; a whole-kind-unresolvable case fails `generate` closed; a
total DRG graph-load failure is reported loudly without failing closed. Turn every fixture in
WP01's two red-first commits GREEN, keep the existing 56-test baseline green, and expose a new
structured-records field on the compiler's result type for WP03 to consume.

**`compiler.py` is this mission's sole chokepoint file, and this WP is its single owner** — no
other WP touches `src/charter/activation/compiler.py`. There is no chokepoint contention to
reconcile within this mission.

## Context

Read `kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/plan.md` in full,
especially: "WP-CORE reconciliation: Contract C4 scope and placeholder text format" (three
binding design decisions), the "Round-5 restatement" (I1-I5, binding), and "Binding mechanism
decisions retained from prior rounds" (URN split, diagnostics sink shape, `cause` typing —
these are OPERATOR RULINGS, not suggestions; do not deviate). Also read
`kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/reviews/plan.ruling.md` rounds
3-7 for the full verbatim rulings if any of the summaries below feel underspecified — the
rulings are binding and this prompt does not restate every word of them.

**Why this is the root cause** (spec.md Key Entities "Raw-but-language-scoped repository"):
`_raw_kind_repository`/`DoctrineService.raw_repository(kind)` strips only the *activation-config*
filter. The underlying per-kind repository (`StyleguideRepository`/`ToolguideRepository`/
`AgentProfileRepository`/etc.) was already constructed with
`active_languages=infer_repo_languages(repo_root)` baked in at `__init__`
(`src/charter/offering/service.py`, `src/charter/activation/doctrine_service_builder.py`), so it
STILL filters by language/scope inside `.get(id)` even against this "raw" accessor. A
language/scope-filtered id therefore misses the lookup exactly like a genuinely nonexistent id
— today both produce the identical opaque `"Unresolved reference: <kind>/<id>"` string and the
id vanishes from `catalog.references`.

**Three binding design decisions (plan.md "WP-CORE reconciliation" — read the full section for
the "why", this is the "what"):**

1. **Contract C4 is NOT superseded.** `tests/charter/test_catalog_completeness_4785.py::test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder`
   (currently green, part of the baseline) pins that a genuinely-nonexistent id (`MISSING_ARTIFACT`/
   `TYPO_SUSPECTED`) stays diagnostics-only — `references == []` for that id, never a placeholder
   row. Your placeholder mechanism applies ONLY to the `SCOPE_FILTERED` cause. Do not make this
   test go red.
2. **`SCOPE_FILTERED` placeholder summary text extends the existing baseline string, as a
   stable prefix.** The current fallback text (`_doctrine_yaml_reference`'s pattern,
   `compiler.py` ~line 1505: `"Definition unavailable in bundled doctrine."`) is already
   committed verbatim in this repo's own `.kittify/charter/charter.yaml` for still-unresolved
   ids. Your new `SCOPE_FILTERED` placeholder's `summary` MUST keep that literal prefix
   byte-for-byte and append a reason-bearing suffix sourced from `classify_scope_filtered_miss`'s
   own suggestion text: `"Definition unavailable in bundled doctrine. Reason: scope_filtered —
   <suggestion>"`.
3. **A new aggregate, cause-agnostic whole-kind fail-closed check** closes the gap decision 1's
   `SCOPE_FILTERED`-only narrowing reopens: FR-001 requires that a whole-kind-unresolvable case
   (e.g. a misconfigured pack root — a `MISSING_ARTIFACT`-class cause) either preserves every id
   as a placeholder OR fails closed. Decision 1 means `MISSING_ARTIFACT`/`TYPO_SUSPECTED` ids
   never get a placeholder, so this check supplies the OTHER mechanism: if, after all sources for
   a kind have contributed, that kind had at least one activated id and NONE of them produced a
   reference (no resolution, no `SCOPE_FILTERED` placeholder), raise a fail-closed error naming
   the kind and its unresolved ids, BEFORE `_build_references_from_service` returns, so
   `compile_charter` never completes and `generate.py`'s existing `RuntimeError` handler
   (`generate.py:584`) exits non-zero before `write_compiled_charter` runs.

**The five binding invariants (I1-I5) and the two extra fixture rows (I1/I2 carve-out,
`_raw_kind_repository` degrade)** are pinned by WP01's two red-first commits — re-read those
test files (`tests/charter/test_charter_generate_scoped_reference_parity.py`,
`tests/charter/test_charter_whole_kind_invariants.py`) before writing any code; they ARE your
acceptance contract for this WP, more concretely than any prose restatement here.

**Binding mechanism decisions (operator rulings — not optional design choices):**

- **URN split and kind mapping.** Split a `graph.unresolved` URN with
  `kind_prefix, _, bare_id = urn.partition(":")` (matches `resolve_transitive_refs`'s own
  successful-lookup branch pattern in `src/charter/offering/drg/query.py`). Map the singular
  `kind_prefix` to the plural repository key using the EXISTING `ArtifactKind(kind_prefix).plural`
  property (`src/charter/offering/artifact_kinds.py`) — never invent a new mapping. Handle:
  `ArtifactKind(kind_prefix)` raising `ValueError` (unrecognized kind, e.g. `action`,
  `glossary_scope`, `glossary`, `mission_type`); a valid `ArtifactKind` whose repository is
  genuinely `None` (`template`/`asset`/`anti_pattern`); a valid `ArtifactKind` with a real
  repository but outside the six tracked kinds (`paradigm`/`mission_step_contract`/
  `glossary_pack`); and no `":"` in the URN at all. NEVER crash (no unguarded `.get()`/`in ...`
  on a `None` repository), NEVER silently drop from the count/placeholder output — see I3 and
  the contract doc's Round-5 addition for the exact four entry shapes.
- **Diagnostics/structured-record sink, not a return-type widening.** Pass the existing
  `diagnostics: list[str]` list AND a new structured-records list INTO
  `_resolve_transitive_reference_graph` as parameters (mutable-list sink pattern — the caller
  passes them in, the callee appends). Append the graph-load-failure record INSIDE its `except
  Exception:` branch, immediately before `return fallback`. The function's return type stays
  `ResolveTransitiveRefsResult`, UNCHANGED — do NOT widen it to a tuple/NamedTuple, do NOT use a
  marker exception (both explicitly declined by the operator).
- **`cause` is a plain `str`, never `CatalogMissCause`.** The new structured record's `cause`
  field (including `"graph_load_failed"`, `"malformed_urn"`, `"unattributed_kind"`) is typed
  `str`. `CatalogMissCause`/`src/charter/activation/_catalog_miss.py` stay REUSED, NOT MODIFIED
  — do not add a fifth enum member.
- **Graph-load failure never fails closed** (I4). It does not participate in the six-kind
  whole-kind aggregate count either — no per-kind bucket exists to attribute it to.
- **Classification reuses the canonical `_diagnose_catalog_miss` gate — no `active_languages`
  threading (round-8 fix, closes analyze findings D1/C1/U1).** Do NOT write a new classify
  function or thread `active_languages` through `compile_charter` /`_build_references` /
  `_build_references_from_service` / `_render_kind_references`. Instead, import and call
  `_diagnose_catalog_miss(raw_id, repository)` from
  `charter.activation.context_renderers.catalog_diagnosis` (it is in that module's `__all__`, so
  importing it is legitimate — do not rename it). That single call already implements the
  `scope_filtered_ids`-check-then-`classify_catalog_miss`-fallback sequence AND already reads
  `active_languages` off `repository._active_languages` and the fuzzy-match corpus off
  `_available_catalog_ids(repository)` — see T007/T008 below and plan.md's IC-02. This does not
  change the whole-kind check, the `graph.unresolved` URN-split/kind-mapping, the graph-load
  diagnostics sink, the plain-`str` cause typing, or the `_raw_kind_repository` fold-in above.
- **`--force` (FR-003) touches nothing in this path.** It already only gates catalog-file
  overwrite permission upstream of `_build_references`, never reference resolution. Do not add
  any `force`-conditioned branch to the logic below; FR-003 is verified by a paired
  with/without-`--force` run producing identical diagnostic/placeholder content (a test
  assertion, not a code change).

**Reuse, do not reinvent (DIRECTIVE_044):**
- `charter.activation.context_renderers.catalog_diagnosis._diagnose_catalog_miss(missing_id,
  repository)` — THE canonical single gate for this classification (already wired for FR-013,
  already called by `selection_block.py` and `profile_sections.py`). Call it directly from your
  new classify-and-placeholder helper instead of re-deriving its logic. It already: (a) checks
  `getattr(repository, "scope_filtered_ids", frozenset())` — defensively, so a bare test double
  with no `scope_filtered_ids` attribute (e.g. `_EmptyRepository` in
  `tests/charter/test_catalog_completeness_4785.py`) never raises `AttributeError` (closes analyze
  finding C1 — do not add your own separate `getattr` for this, the gate already has it); (b) on a
  genuine miss, calls `classify_catalog_miss(missing_id, _available_catalog_ids(repository))` —
  the fuzzy-match corpus (analyze finding U1) comes from the gate's own `_available_catalog_ids`,
  you do not build or pass an `available_ids` list yourself; (c) reads `active_languages` straight
  off `getattr(repository, "_active_languages", None)` — no threading needed, see the Binding
  mechanism decisions above. Import direction `compiler.py` → `catalog_diagnosis.py` is verified
  cycle-free (`catalog_diagnosis.py` depends only on the `_catalog_miss` leaf; nothing in
  `context_renderers/` imports `compiler`) — see plan.md IC-02.
- `charter.activation._catalog_miss`: `CatalogMissCause`, `classify_catalog_miss`,
  `classify_scope_filtered_miss` — already built, already tested
  (`tests/charter/test_context_catalog_miss.py`, part of the baseline); consumed transitively via
  `_diagnose_catalog_miss` above, not called directly by `compiler.py`. Do not modify this module.
- `BaseDoctrineRepository.scope_filtered_ids` (`src/charter/offering/base.py`) — a `frozenset`
  already populated at repository load time; `_diagnose_catalog_miss` is what distinguishes
  `SCOPE_FILTERED` from `MISSING_ARTIFACT`/`TYPO_SUSPECTED` using it defensively (above). Your
  helper calls the gate BEFORE any placeholder-construction code (Contract C4 regression risk
  otherwise) — it does not access `scope_filtered_ids` itself.
- `ArtifactKind(kind_prefix).plural` (`src/charter/offering/artifact_kinds.py`) for the URN
  kind-mapping above (unrelated to the classification-reuse above; still your own responsibility
  for the `graph.unresolved` routing in T009).

## Commits

Land T007-T013 as four logically-scoped commits, not one, so each mechanism is independently
reviewable:

1. **T007 + T008** — the shared classify-and-placeholder helper wired into
   `_render_kind_references`, calling the canonical `_diagnose_catalog_miss` gate (round-8 fix,
   no `active_languages` threading — see Binding mechanism decisions above), plus T008's
   assertion that the gate's language-set-naming suggestion text actually surfaces end-to-end.
   These two are one mechanism: the helper's reason-bearing output is not meaningfully testable
   without confirming the gate's richer suggestion text reaches the emitted diagnostic/summary.
2. **T009 + T010** — routing `graph.unresolved` through the same shared helper, plus the
   diagnostics/structured-record sink (and graph-load-failure sentinel) on
   `_resolve_transitive_reference_graph`. These two together close the mission's "second,
   unmentioned unresolved-tracking site" gap (plan.md Round-3 note) for both failure shapes on
   that bucket.
3. **T011 alone** — the aggregate, cause-agnostic whole-kind fail-closed check. This is the WP's
   highest-risk mechanism (a new fail-closed exit path); isolating it in its own commit lets a
   reviewer verify its once-per-kind-after-all-sources timing without the noise of the other six
   subtasks' diffs.
4. **T012 + T013** — the `_raw_kind_repository` `getattr` fallback fix and its
   placeholder-text-format test, plus exposing the structured unresolved-reference-records field
   WP03 depends on. Both are small, additive residuals that do not interact with commits 1-3's
   logic.

Each commit must independently pass `tests/charter/test_catalog_completeness_4785.py` (the
Contract C4 regression oracle) — do not defer that check to the final commit.

## Subtask T007: Shared classify-and-placeholder helper, wired into `_render_kind_references`

**Purpose**: Replace the duplicated `diagnostics.append(f"Unresolved reference: {kind}/{raw_id}")`
call inside `_render_kind_references` (`compiler.py` ~line 1140) with a single new private
helper — e.g. `_classify_and_placeholder_reference(kind, raw_id, repository)` — that: (a) calls
the existing canonical gate `_diagnose_catalog_miss(raw_id, repository)` (import from
`charter.activation.context_renderers.catalog_diagnosis` — it is in that module's `__all__`, so
importing it is legitimate; do not rename it) to get a `CatalogMissDiagnosis`. The gate already
implements the `scope_filtered_ids`-check-then-`classify_catalog_miss`-fallback sequence, already
guards `scope_filtered_ids` access with `getattr(..., frozenset())` (so `_EmptyRepository` in
`tests/charter/test_catalog_completeness_4785.py` never raises — closes analyze finding C1), and
already sources its fuzzy-match corpus from `_available_catalog_ids(repository)` internally
(closes analyze finding U1) — **do not re-implement any of that inline** (closes analyze finding
D1); (b) if the returned diagnosis's `cause` is `CatalogMissCause.SCOPE_FILTERED`, ALWAYS builds
and returns a placeholder `CharterReference` (decision 3's placeholder-text format from Context
above); (c) otherwise (`TYPO_SUSPECTED`/`MISSING_ARTIFACT`) returns no placeholder — `references`
stays `[]` for that id, diagnostics-only (Contract C4); (d) in both branches, appends a
reason-bearing diagnostic string to `diagnostics: list[str]` — extend, don't replace, the
existing format: `"Unresolved reference: {kind}/{id} ({cause}): {detail}"`, using the diagnosis's
own `cause`/suggestion text; (e) in both branches, appends a structured `(kind, id, cause,
detail)` record to the new structured-records sink (a new parameter/list this helper receives and
populates), so a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` miss is STILL machine-readable even without a
placeholder row.

**Steps**:
1. Add the private helper function (module-private, leading underscore — NOT added to
   `__all__`; see the C-007 note below). It takes `(kind, raw_id, repository)` — no
   `active_languages` parameter; the gate reads that off `repository` itself.
2. Replace `_render_kind_references`'s existing unresolved-append call site with a call to this
   helper.
3. This same helper is also the target for T009's `graph.unresolved` routing (do not write a
   second, parallel classify function).

**Files**: `src/charter/activation/compiler.py` (~30-60 new lines for the thin helper — smaller
than the original estimate since `_diagnose_catalog_miss` absorbs the classification logic;
modifying the `_render_kind_references` call site; one new import line for
`_diagnose_catalog_miss`).

**Validation**: `tests/charter/test_charter_generate_scoped_reference_parity.py` should now
resolve every fixture id via this path (full GREEN also needs T010's whole-kind check to not
spuriously trip). `tests/charter/test_catalog_completeness_4785.py` must stay green — add a
targeted run after this subtask:
`.venv/bin/python -m pytest -q tests/charter/test_catalog_completeness_4785.py`.

## Subtask T008: Confirm `_diagnose_catalog_miss` surfaces the real active-language suggestion (no threading)

**Purpose (round-8 fix — supersedes the original "thread `active_languages` across four call
levels" task)**: Analyze findings D1/C1/U1 established that `_diagnose_catalog_miss` already
reads `active_languages` directly off `getattr(repository, "_active_languages", None)` — the
value each per-kind repository already carries from its own construction
(`BaseDoctrineRepository.__init__`, `src/charter/offering/base.py:106`) — so there is no
`active_languages` parameter to thread through `compile_charter` → `_build_references` →
`_build_references_from_service` → `_render_kind_references`; none of those four signatures
change for this reason, and none of the six per-kind call sites in
`_build_references_from_service` gain a new argument. This subtask is now a verification step,
not a plumbing change: confirm T007's helper passes the real `repository` object (not a stripped
or partial view) into `_diagnose_catalog_miss`, so `classify_scope_filtered_miss`'s richer,
language-set-naming suggestion text (`src/charter/activation/_catalog_miss.py:261-305`) reaches
the emitted diagnostic/placeholder `summary` unmodified — required for NFR-002's "actionable
diagnostic content" bar and for decision 2's placeholder-text-format test (T012) to have real
content to assert against.

**Steps**:
1. Do NOT add `active_languages` parameters anywhere in `compiler.py` — verify none of
   `compile_charter`, `_build_references`, `_build_references_from_service`, or
   `_render_kind_references` gained a new signature parameter for this purpose.
2. Confirm T007's helper calls `_diagnose_catalog_miss(raw_id, repository)` with the same
   `repository` object `_render_kind_references` already receives (the raw per-kind repository,
   which already carries `_active_languages` from construction) — not a copy or a stripped view.
3. Add the language-set-naming assertion (see Validation below) proving the suggestion text is
   real, not the generic fallback.

**Files**: `src/charter/activation/compiler.py` (no signature changes expected from this
subtask — if a diff shows one, that is a regression against this ruling, not progress).

**Validation**: Add one assertion to T012's new file, `tests/charter/test_compiler_scope_filtered_placeholder.py`
(not WP01's `test_charter_generate_scoped_reference_parity.py`, which WP01 owns) asserting that
the emitted `detail`/suggestion text for a `SCOPE_FILTERED` case names the actual active language
set, matching the contract doc's worked example (`"...does not include the active language set
('python')."` pattern).

## Subtask T009: Route `graph.unresolved` through the same shared helper

**Purpose**: Close the "second, unmentioned unresolved-tracking site" gap (plan.md's Round-3
note) — `_build_references_from_service`'s own `graph.unresolved` loop
(`compiler.py:1250-1251`) must ALSO route through T007's shared helper so I1/I2 hold for both
source buckets, not just direct per-kind lookups.

**Steps**:
1. For each `graph.unresolved` URN: split with `urn.partition(":")`, map `kind_prefix` via
   `ArtifactKind(kind_prefix).plural` (per the Binding mechanism decisions in Context above).
2. On a successful kind mapping to one of the six tracked kinds: route through T007's helper
   exactly as a direct per-kind miss would (same classify → placeholder-or-diagnostics-only
   logic), so it counts toward I2's per-kind OR condition.
3. On any of the four unattributable classes (no `":"`, unrecognized kind, `None`-repository
   kind, valid-but-untracked kind): build the corresponding structured record per I3's shapes
   (see Context above and `contracts/charter-generate-json-diagnostics.md`'s "Round-5 addition"
   — reproduce the exact `kind`/`cause`/`detail` values documented there; do not invent new
   sentinel strings). These four classes do NOT participate in the six-kind whole-kind aggregate
   count (no bucket to attribute them to).

**Files**: `src/charter/activation/compiler.py` (rewrites the `graph.unresolved` loop).

**Validation**: `tests/charter/test_charter_whole_kind_invariants.py`'s I3 fixtures (T003 in
WP01) and the Fixture B routing case (T002 in WP01) should now pass.

## Subtask T010: Diagnostics/structured-record sink on `_resolve_transitive_reference_graph` + graph-load-failure sentinel

**Purpose**: I4 — a total DRG graph-load failure yields a loud, structured diagnostic instead
of vanishing, without attempting to reconstruct the transitive closure.

**Steps**:
1. Add two new parameters to `_resolve_transitive_reference_graph`: `diagnostics: list[str]` and
   a new structured-records list (both mutable-list sinks the caller passes in — NOT a return-type
   change).
2. Inside its existing `except Exception:` branch (currently ~line 1296-1307, immediately
   before `return fallback`), append: (a) a diagnostic string to `diagnostics`, e.g. `"Graph load
   failed: <exception summary>. Transitive closure not resolved; direct-root ids only."`; (b) a
   structured record `{"kind": "_graph", "id": "_load_failure", "cause": "graph_load_failed",
   "detail": "<short exception summary>"}` to the structured-records sink.
3. Return type stays `ResolveTransitiveRefsResult`, UNCHANGED.
4. Confirm this entry does NOT participate in T010/T011's whole-kind aggregate count (no
   per-kind bucket).

**Files**: `src/charter/activation/compiler.py`.

**Validation**: `tests/charter/test_charter_whole_kind_invariants.py`'s I4 fixture (T004 in
WP01) and the I1/I2 carve-out fixture (T005 in WP01) should now pass.

## Subtask T011: Aggregate, cause-agnostic whole-kind fail-closed check

**Purpose**: Close FR-001's "misconfigured pack root" gap (decision 3 above) — the SECOND
mechanism (alongside `SCOPE_FILTERED` placeholder-preservation) that satisfies FR-001 "at any
cardinality".

**Steps**:
1. In `_build_references_from_service`, after ALL sources for a kind have contributed (every
   per-kind `_render_kind_references` call for that kind AND the kind-mapped `graph.unresolved`
   pass — I2's single evaluation point, evaluated ONCE per kind), determine: did this kind have
   at least one activated id (from EITHER `graph.<kind>` non-empty OR at least one
   `graph.unresolved` URN attributed to it via the kind-mapping step — I2's OR condition), and
   did it produce ZERO references (no resolution, no `SCOPE_FILTERED` placeholder)?
2. If both are true for any kind: raise a fail-closed error (e.g. a `RuntimeError` or a new
   narrow exception type — implementer's choice, but it must propagate up through
   `compile_charter` to `generate.py`'s EXISTING `RuntimeError` handler at `generate.py:584`, so
   no new CLI-layer error handling is needed) naming the kind and its unresolved ids, BEFORE
   `_build_references_from_service` returns — so `compile_charter` never completes and
   `write_compiled_charter` never runs (no catalog is written).
3. **Timing — this is evaluated ONCE per kind, after ALL sources, never "immediately after" any
   single source.** A kind with even one `SCOPE_FILTERED` id among otherwise-`MISSING_ARTIFACT`
   ids must NOT trip this path (non-empty reference list for that kind).
4. **Carve-out**: a kind whose activated ids are ALL transitively-reachable only (no direct
   root of that kind) is never evaluated by this check under total graph-load failure — T010's
   `_graph`/`_load_failure` sentinel stands in for that kind's coverage instead (I1/I2's
   carve-out).

**Files**: `src/charter/activation/compiler.py`.

**Validation**: `tests/charter/test_charter_whole_kind_invariants.py`'s Fixture A/B (T002 in
WP01) and I5's idempotency assertions (T005 in WP01) should now pass — run the full new test
file: `.venv/bin/python -m pytest -q tests/charter/test_charter_whole_kind_invariants.py`.

## Subtask T012: `_raw_kind_repository` `getattr` fallback fix + placeholder-text-format test

**Purpose**: (a) Fold in the round-6 residual — `_raw_kind_repository`'s raw-service fallback
branch (`compiler.py:1093`, `return getattr(doctrine_service, kind)`, no default) raises
`AttributeError` for kinds like `"templates"`/`"anti_patterns"` when `doctrine_service` is the
raw/unwrapped shape. Change to `getattr(doctrine_service, kind, None)` so it degrades to a
reported miss (`None`), matching how the rest of this function's callers already handle a
missing raw repository. (b) Add the concrete decision-2 placeholder-text-format test.

**Steps**:
1. Change `compiler.py:1093`'s fallback branch as above.
2. Create `tests/charter/test_compiler_scope_filtered_placeholder.py` (new, narrow unit test
   file — deliberately NOT the same file as WP01's owned test files, to keep ownership
   disjoint). Add one test: regenerate a fixture seeded with today's exact baseline placeholder
   row shape (`"Definition unavailable in bundled doctrine."`, already committed verbatim in
   this repo's own `.kittify/charter/charter.yaml`) for a still-unresolvable `SCOPE_FILTERED` id,
   and assert the post-fix `summary` matches `"Definition unavailable in bundled doctrine.
   Reason: scope_filtered — <suggestion>"` exactly (byte-for-byte prefix preserved, suffix
   present).
3. Add T008's language-set-naming assertion (see T008 Validation above) to this same new file.

**Files**: `src/charter/activation/compiler.py` (one-line fallback change);
`tests/charter/test_compiler_scope_filtered_placeholder.py` (new, ~40-80 lines).

**Validation**: WP01's `_raw_kind_repository` degrade fixture (T006) now returns `None`
instead of raising — run
`.venv/bin/python -m pytest -q tests/charter/test_charter_whole_kind_invariants.py -k raw_kind_repository`
and confirm GREEN. New file's own tests pass.

## Subtask T013: Expose structured unresolved-reference records via a new field on the compiler's result type

**Purpose**: WP03 (JSON diagnostics) depends on this — it must be able to read the accumulated
structured records (from T007/T009/T010) after `compile_charter` runs, without touching
`compiler.py` itself (compiler.py is this WP's sole-owned chokepoint; WP03 only reads what you
expose here).

**Steps**: Add a new field (e.g. `unresolved_reference_records: list[dict[str, str]]` or a small
typed record class — implementer's choice of shape, but it must carry `kind`/`id`/`cause`/
`detail` for every entry the helper and the graph-load-failure/unattributable-URN paths
produced) to `CompiledCharter` or `WriteBundleResult` (whichever already carries `diagnostics`
today — mirror that field's placement exactly) in `compiler.py`. Populate it from the same
structured-records sink T007/T009/T010 build. This is a genuinely new field, not a rename —
`compile_charter`'s existing callers that do not know about it are unaffected (additive).

**Files**: `src/charter/activation/compiler.py`.

**Validation**: Confirm the new field is populated identically in content to `diagnostics`'
per-line reasons (same records, structured form) for a fixture with a mix of `SCOPE_FILTERED`,
`MISSING_ARTIFACT`, and graph-load-failure causes.

## Definition of Done

- Every fixture in WP01's `tests/charter/test_charter_generate_scoped_reference_parity.py`
  AND `tests/charter/test_charter_whole_kind_invariants.py` (all 7 rows of the ATDD-First
  Discipline invariant→fixture table: I1, I2, I3 [4 sub-classes], I4, I5, the I1/I2 carve-out,
  and the `_raw_kind_repository` degrade case) passes GREEN.
- The existing 56-test baseline stays green — run:
  `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py tests/charter/test_catalog_completeness_4785.py`
  → must report 56 passed, 0 failed. `test_catalog_completeness_4785.py` specifically proves
  Contract C4 (the `MISSING_ARTIFACT`/`TYPO_SUSPECTED` diagnostics-only path) is undisturbed.
- `tests/charter/test_compiler_scope_filtered_placeholder.py` (new) passes.
- No `force`-conditioned branch was added anywhere in this logic (FR-003 verified by test
  assertion only).
- `_classify_and_placeholder_reference` (or your chosen name) is module-private (leading
  underscore) and NOT added to `compiler.py`'s `__all__`.
- Per-subtask completion evidence recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T007-T013.
- T007-T013 land as the four logically-scoped commits the "Commits" section above defines
  (T007+T008, T009+T010, T011 alone, T012+T013) — not one undifferentiated commit — and each
  commit independently passes `tests/charter/test_catalog_completeness_4785.py`.

## Risks

- **Risk**: The existing diagnostic string format (`"Unresolved reference: <kind>/<id>"`) is
  extended, not replaced. **Mitigation**: grep the test suite for any exact-string assertion on
  the OLD format before changing it — `grep -rn "Unresolved reference:" tests/` — to avoid an
  unrelated test regression outside this mission's stated scope.
- **Risk**: Contract C4 regression — a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` id falls through to
  the placeholder branch by mistake. **Mitigation**: the `_diagnose_catalog_miss(raw_id,
  repository)` call MUST run BEFORE any placeholder-construction code, and its returned `cause`
  MUST gate whether a placeholder is built — not a separate, hand-written
  `scope_filtered_ids` membership check (the gate already does that defensively);
  `test_catalog_completeness_4785.py` is your regression oracle — run it after EVERY subtask, not
  just at the end.
- **Risk**: Re-deriving the classify-then-placeholder logic inline in `compiler.py` instead of
  calling `_diagnose_catalog_miss` — this would reintroduce analyze finding D1's duplication and
  silently drop C1's/U1's defensive precedents (the gate's `getattr` guard and
  `_available_catalog_ids` corpus). **Mitigation**: grep the diff for a hand-written
  `scope_filtered_ids` membership check or a direct `classify_catalog_miss`/
  `classify_scope_filtered_miss` call in `compiler.py` — either is a regression against this
  round's ruling; only `_diagnose_catalog_miss` should be called directly.
- **Risk**: Timing bug in the whole-kind check (evaluating per-source instead of per-kind-after-
  all-sources). **Mitigation**: I2 is unambiguous — evaluate once per kind, after ALL sources
  (all per-kind `_render_kind_references` calls AND the kind-mapped `graph.unresolved` pass)
  have contributed. WP01's Fixture A/B and the negative control (a kind with one `SCOPE_FILTERED`
  id among `MISSING_ARTIFACT` ids must NOT trip) directly test this.
- **Risk**: Inventing a new URN-to-repository mapping instead of reusing `ArtifactKind.plural`.
  **Mitigation**: this is an explicit operator ruling (round 4) — use `ArtifactKind(kind_prefix).plural`,
  cited above; do not write a second mapping.
- **Risk**: Complexity ceiling (charter: max 15, ruff C901/Sonar S3776). `_build_references_from_service`
  and `_render_kind_references` both gain nontrivial new branching. **Mitigation**: extract small
  helpers (the classify-and-placeholder helper IS one such extraction; extract the whole-kind
  aggregate check into its own helper too if the host function approaches the ceiling) rather
  than inlining everything into one large function.

## Gates (run these; do not invent others)

- `.venv/bin/python -m ruff check .` (whole-repo, always-on)
- `.venv/bin/python -m ruff format --check .` (whole-repo, always-on)
- `.venv/bin/python -m pytest -q tests/charter/test_charter_generate_scoped_reference_parity.py tests/charter/test_charter_whole_kind_invariants.py tests/charter/test_compiler_scope_filtered_placeholder.py` — must be all GREEN.
- Baseline (must stay 56 passed, 0 failed):
  `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py tests/charter/test_catalog_completeness_4785.py`
- Full `tests/charter/` blast-radius shard (this is the owning subsystem for `compiler.py`; run
  the directory, not the whole `tests/`):
  `.venv/bin/python -m pytest -q tests/charter/`
- Cross-WP regression check (per TASKS-SEQ-001): `tests/specify_cli/charter_runtime/test_references_parity_refresh.py`
  is WP04's owned test file, but its `test_references_parity_drift_recompiles_the_catalog` test
  drives `compile_charter` end-to-end through the real `generate` CLI, reaching straight into this
  WP's sole-owned `compiler.py` — the one test file outside this WP's own owned files that
  exercises it that way. Run it after this WP's changes land to confirm no regression:
  `.venv/bin/python -m pytest -q tests/specify_cli/charter_runtime/test_references_parity_refresh.py`
- `spec-kitty regen --check` — **NOT APPLICABLE**: no schema-generated file changes in this
  mission's diff; stated explicitly, not silently assumed.
- `tests/architectural/test_no_dead_symbols.py` — the new classify-and-placeholder helper is
  module-private and deliberately NOT added to `compiler.py`'s `__all__` (per C-007's own
  precedent: `_render_kind_references`, `_doctrine_model_reference`, `_doctrine_yaml_reference`
  are likewise not listed). Since this gate walks `__all__` and this WP adds no new listed name,
  it does not fire for this WP — run it anyway as a cheap regression check since `compiler.py`'s
  EXISTING `__all__` entries are still present:
  `.venv/bin/python -m pytest -q tests/architectural/test_no_dead_symbols.py`.
- `tests/architectural/test_no_legacy_terminology.py` — `src/charter/activation/` is a SIBLING
  path to `src/charter/offering/`, not within it, so the charter's path-based trigger does not
  apply by the literal rule. However, this WP DOES introduce new user-facing diagnostic/detail
  prose (the reason-bearing diagnostic strings and placeholder summaries). Run it anyway as a
  cheap (~0.1s) precaution — it gates exactly two retired terms ("ceremony", canonical
  `status commit` vs `status-writing`) unrelated to this mission's vocabulary, so it is expected
  to stay green:
  `.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py`.
- diff-cover ≥90% of changed lines — informational locally; the real gate is `ci-aggregate.yml`'s
  `diff-cover` job. `make ci-parity` should be re-run once this WP's `src/` diff lands, per
  plan.md's "Gate set" section — do this once WP02/WP03/WP04 have all landed (or at minimum
  after this WP, to see the real module-shard/diff-cover scoping for `src/charter/`).

## Reviewer Guidance

- Verify RED→GREEN: every fixture in both WP01 commits was RED on `af847be71` and is GREEN on
  this WP's final commit.
- Verify Contract C4 is genuinely undisturbed — don't just trust the test passing; read
  `test_catalog_completeness_4785.py`'s assertion and confirm the code path it exercises
  (`MISSING_ARTIFACT`/`TYPO_SUSPECTED`) truly never reaches placeholder-construction code.
- Verify the `_diagnose_catalog_miss(raw_id, repository)` call precedes any placeholder
  construction (ordering bug risk explicitly called out in Risks above) — the gate's own
  `getattr(repository, "scope_filtered_ids", frozenset())` guard is what makes this safe against
  `_EmptyRepository`, not a separate check in `compiler.py`.
- Verify no `--force`-conditioned branch exists anywhere in the new logic.
- Verify `ArtifactKind(kind_prefix).plural` is the ONLY kind-mapping mechanism used — grep for
  any second, hand-rolled mapping dict/if-chain and reject if found.
- Verify the classify-and-placeholder helper calls `_diagnose_catalog_miss(raw_id, repository)`
  (imported from `charter.activation.context_renderers.catalog_diagnosis`) rather than
  re-deriving the `scope_filtered_ids`-check-then-classify sequence inline, and that `compiler.py`
  gained NO `active_languages` parameter anywhere (`git diff -- src/charter/activation/compiler.py`
  should show no new `active_languages` in any function signature) — round-8 fix, closes analyze
  D1/C1/U1.
- Verify the whole-kind check's evaluation point: read the code and confirm it runs once per
  kind, after every per-kind `_render_kind_references` call AND the `graph.unresolved` pass for
  that kind have both executed — not interleaved per-source.
- Verify `_resolve_transitive_reference_graph`'s return type is still exactly
  `ResolveTransitiveRefsResult` (no widening).
- Verify `CatalogMissCause`/`_catalog_miss.py` were NOT modified (`git diff` should show zero
  changes to that file).
- Verify T007-T013 landed as four separate commits per the "Commits" section (`git log
  --oneline` on this WP's branch shows T007+T008, T009+T010, T011, T012+T013 as distinct
  commits) — not squashed into one.

## Implementation Command

```bash
spec-kitty agent action implement WP02 --agent claude
```
