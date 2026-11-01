# Data model — scoped catalog and lazy lineage

## OfferingCatalog

| Field | Today | After |
|---|---|---|
| `paradigms` … `agent_profiles` (8 id sets) | always populated from a full scan | populated only for scanned domains; empty for a domain the caller did not scope |
| `domains_present` | names each domain whose directory exists **and** was scanned | unchanged meaning; names only *scanned* domains, so an unscanned domain is absent (identical to "not deployed" for a caller that asked not to read it) |
| `domains_scanned` (new) | — | the exact domain set this catalog was built for; the guard tests read it to prove a call site's declared scope |

Domain vocabulary: `paradigms`, `directives`, `template_sets`, `tactics`,
`styleguides`, `toolguides`, `procedures`, `agent_profiles` — the same tokens
`domains_present` already uses, so no new vocabulary is introduced.

Invariants:

- `domains` omitted → all eight scanned, byte-identical result to today (C-004).
- `domains` given → every requested token must be a known domain token (the
  `domains_present` vocabulary); an unknown token raises `ValueError` before any file is
  read (FR-006, fail-closed).
- `domains=()` → no file read, every id set empty, `domains_present` empty. Legal.
- A scoped domain whose directory is absent stays absent from `domains_present`
  (unchanged semantics).
- `template_sets` keeps its existing derivation (`MissionTemplateRepository`), gated on
  the same scope.

Read sets on this repository's pack (measured, `packs/built-in/`):

| Domain | Files |
|---|---|
| paradigms | 14 |
| directives | 38 |
| template_sets | 2 (derived from mission dirs) |
| tactics | 32 |
| styleguides | 24 |
| toolguides | 18 |
| procedures | 23 |
| agent_profiles | 26 |
| **all** | **265** (includes mission-type and step-contract documents) |
| **governance resolution** | **52** (14 paradigms + 38 directives; template sets are derived, not parsed) |
| **interview defaults** | **52** |

## AgentProfileRepository

| Concern | Today | After |
|---|---|---|
| `self._drg` | built in `__init__` via `_default_drg()` → 13 fragment parses | built on first lineage read; `None` until then |
| `drg=` argument | used verbatim | used verbatim and marks the graph resolved, so no lazy build happens |
| `DRGLoadError` | degrades to an empty graph inside `_default_drg()` | degrades identically, at first lineage read |
| profile map, provenance, source paths, `get()`, `list_all()`, `sentinel` | available after `_load()` | unchanged — no graph needed |

Lineage readers (the only `self._drg` consumers): `_lineage_parent` (and therefore
`_build_hierarchy_index`, `get_ancestors`, `get_children`, `get_descendants`) and the
profile-channel reachability helper. All of them call one `_graph()` accessor.

## Census counter (test-side)

A test-only counter over two production seams:

- `charter.offering.yaml_utils.parse_shipped_yaml` — every memo miss is one document
  actually parsed (memo hits are not charged, matching what the user pays).
- `charter.offering.agent_profiles.repository` profile loader — counts profile documents
  (they route through the same seam, so the DRG/profile split is attributed by
  file suffix: `*.graph.yaml` vs `*.agent.yaml`).

The counter is a `Counter[str]` keyed by the parsed file's kind token. Guards assert
ceilings and forbid zero-tolerance domains; they never assert seconds.
