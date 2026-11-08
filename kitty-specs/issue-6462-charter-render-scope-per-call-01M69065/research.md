# Discovery — #6462 "Every CLI call re-renders full charter context"

Mission: `issue-6462-charter-render-scope-per-call-01M69065`. Grounding commit:
`main` @ `dfe9efb0e8`. Issue: spec-kitty/spec-kitty#6462.

## What the report claims, and what actually happens

The report (on `spec-kitty-cli` 3.2.7) says every CLI invocation re-renders the full
charter/doctrine catalog for the caller's persona, costing 90–150 s per call and
flooding the console with `CharterCatalogMissWarning` lines for artifact kinds scoped
to languages the project does not use.

Measured on this checkout (`4.0.0rc8`), in a warm isolated `HOME`, with a counting
harness (`/tmp/count_stacks3.py` in the run log, re-implemented for the mission in
`tests/charter/test_charter_render_scope_6462.py`):

| Command | Wall clock | Shipped docs parsed | Charter-service builds |
|---|---|---|---|
| `spec-kitty --version` | 2.2 s | 0 | 0 |
| `spec-kitty agent tasks status --mission <m>` | 4.0–4.5 s | 107 | 1 |
| `spec-kitty agent profile list` | 3.2 s | 101 | 2 DRG loads |
| `spec-kitty charter context --action implement` | 5.0–5.1 s | 265 (+43 vocab, +30 step contracts) | 1 |
| `spec-kitty next … --json` (mission complete) | 1.3–2.0 s | 10 | 0 |

So the **magnitude** does not reproduce (4–5 s, not 90–150 s; this host is shared with
~20 concurrent missions, so seconds are reported, never asserted). The **mechanism**
does reproduce, and it is a work-doesn't-match-need bug, not a budget bug:

1. `charter.activation.catalog.load_offering_catalog()` parses **all eight built-in
   domains** — 265 documents in this repo's pack — for every caller.
   `resolve_project_governance()` (`src/charter/activation/resolver.py:958`) reads only
   `paradigms`, `directives`, `template_sets` and sets
   `GovernanceResolution.tactics/styleguides/toolguides/procedures` to `[]`
   unconditionally, so five of the eight scans (tactics 32, styleguides 24,
   toolguides 18, procedures 23, agent_profiles 26 = 123 files) are provably unused on
   every persona render. `default_interview()`
   (`src/charter/activation/interview.py:316`) reads only `paradigms` and `directives`.
2. The read-only `agent tasks status` board
   (`src/specify_cli/cli/commands/agent/tasks_status_cmd.py:890`) builds the whole
   `ActiveCharterService` (pack context, activation ledger, offering service) and a
   complete `AgentProfileRepository` — 26 profile files **plus 13 DRG fragments** — to
   answer `profile.sentinel` for the board's 👤 marker
   (`_get_hic_marker`, same file line 1062).
3. `AgentProfileRepository.__init__` (`src/charter/offering/agent_profiles/repository.py:266`)
   calls `_default_drg()` eagerly, yet `self._drg` is only read by
   `_lineage_parent`/`_build_hierarchy_index`/`_profile_channel_reachable`. The profile
   map and its lineage graph are different reads, and only the former is needed to read
   `sentinel` (a plain boolean field, `profile.py:279`).
4. Catalog-miss warnings: measured **0–2 per call**, deduplicated once per process
   (`#4572`, `_catalog_miss.py` `_EMITTED`) with `SCOPE_FILTERED` already quiet for
   `agent_profile` (`_QUIET_SCOPE_FILTERED_KINDS`). The remaining scope-filtered warning
   for a toolguide/styleguide is a **pinned charter-offering contract**
   (`tests/charter/test_context_catalog_miss.py`), and the CHANGELOG records the #4572
   decision that a scope-filtered miss must stay visible. "Never warn about an artifact
   scoped to another language" is therefore a governance ruling, not a bug fix.

## What is already cached or fixed (so this mission does not redo it)

- **#5526** — shipped doctrine is parsed at most once per change per process
  (`charter/offering/yaml_utils.py:69`, `parse_shipped_yaml`, keyed on
  path+size+mtime+variant). The built-in DRG is memoised the same way
  (`drg/loader.py` `_BUILT_IN_GRAPH_MEMO`). These memoise *repeat* reads; they do not
  shrink the *first* read set, which is what this mission targets.
- **#6858** (open PR, branch `issue-6777-cascade-stem-resolution-pass`) — the cascade
  activation loop now resolves a whole target batch through one `ResolutionPass`
  instead of one pass per artifact, and it is the template for this mission's honest
  guard style: **count calls/parses, never assert seconds** on this shared host, and
  fix the cause rather than tune a timeout. That PR touches
  `charter/activation/kind_vocabulary.py` consumers and
  `src/specify_cli/cli/commands/charter/activate.py`; this mission touches neither, so
  the two can land in either order.
- **#4211** — global startup assets (`~/.kittify`) are skipped when a freshness stamp
  matches; measured here: 1.3 s of the 4.0 s status call on a *clean* HOME, and two
  full command-bundle re-renders on a HOME whose stamp was written by another agent's
  checkout (a shared-machine artefact, not a product defect). Out of scope.
- **#6473/#4703/#5588** — startup-asset owners warn instead of failing, and session-start
  / live-work hooks already bypass the asset and schema gates. Out of scope.
- **#6638/#6584** — CLI import cost is already down to ~1.2 s (httpx, `__version__`
  deferred). Startup assets and imports are therefore *not* where the remaining work
  is; the render set is.

## Decisions

**D-1 — Fix the read set, not the budget.** No TTL cache, no on-disk render cache, no
`--no-charter-render` flag. The issue proposes all three; triage records that no cache
architecture is pre-approved, and a cache would hide the same over-read behind
invalidation bugs. Evidence: 211 of the 265 documents parsed by a persona render are
provably unread by that render (`GovernanceResolution` hard-codes the five other kinds
to `[]`).

**D-2 — Scope is explicit and defaults to today's behaviour.** `load_offering_catalog`
gains a keyword that names the domains to scan (`None` = all eight). A default change
would silently alter `charter validate`, the JSON context surfaces and every test that
constructs a catalog, and C-004 pins the compat requirement. An unknown domain name
fails closed (`ValueError`), never a silently empty catalog (FR-006).

**D-3 — The scope is declared by the caller, not guessed from its imports.** Each
governance call site states the domains it reads; a census test pins the pair. This is
the smallest change that keeps one catalog authority (C-002) while making over-read a
test failure rather than a silent tax.

**D-4 — Lineage is loaded on demand, in the repository that owns it.** The DRG is
loaded lazily on first lineage access. `AgentProfileRepository(drg=…)` keeps working;
the empty-graph degradation on `DRGLoadError` moves with the lazy build, so a lineage
call still degrades exactly as today and a profile-map-only read never touches the
graph at all.

**D-5 — Leave the read-only board's service build alone.** `agent tasks status` must
keep going through `ActiveCharterService` (charter-sole-door-bypass-closure-01KZ3WAA
FR-001 pinned the accessor for exactly this marker). A narrow "sentinel-only" reader
would have to re-resolve built-in/org/project layers itself — a second profile reader,
which C-002 forbids. Lazy lineage already removes the graph parse from this path; the
remaining service build is the price of the sole door and is not touched here.

**D-6 — No warning-contract change.** Keep the scope rule as written; report the measurement
and defer the "don't warn about another language's artifact" ruling (see Deferred in
the PR).

## Open questions for specify/plan

- Q1 — Should the census guard drive the real CLI in a subprocess (faithful, ~5 s per
  case) or call the render entry points in-process (fast, but needs a spy that survives
  import caching)? Decision: in-process, with the spy installed on
  `charter.offering.yaml_utils.parse_shipped_yaml` and the profile loader, and one
  end-to-end subprocess case for the two headline numbers.
- Q2 — Where does `tests/charter/test_charter_render_scope_6462.py` get a pack fixture
  that contains a tactic for a language the fixture project does not use? Decision: use
  the shipped built-in pack through the existing test seams (`built_in_dir`), not a
  hand-built fixture tree, so the guard counts what a real install reads.
- Q3 — Does any caller rely on `OfferingCatalog.domains_present` naming domains it did
  not scan? Checked: only the three selection helpers read it, each for its own kind;
  `charter validate` and the JSON surfaces call the unscoped default.
