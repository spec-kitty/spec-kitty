# Data Model — scoped agent-profile sentinel read

## Entities

### Agent profile (existing)

Authored YAML document at `<layer>/agent_profiles/<profile-id>.agent.yaml`, validated by
`AgentProfile` (pydantic). Fields this mission reads or must preserve:

| Field | Role here |
| --- | --- |
| `profile-id` | the id a work package names in its `agent_profile` frontmatter |
| `sentinel` | **the only field the board needs**: `true` marks a human-in-charge profile, rendered as `👤 ` |
| `applies_to_languages` | language scope; a profile whose scope excludes the active languages is not loaded (parity requirement) |
| every other field | parsed and merged as today, but never read by the board path |

### Profile layer (existing)

| Layer | Directory source | Precedence |
| --- | --- | --- |
| built-in | `built_in_dir(ArtifactKind.AGENT_PROFILE)` (`packs/built-in/agent_profiles/`) | base |
| org | `<org pack root>/agent_profiles/` for each configured pack, in declaration order | overrides built-in |
| project | the project pack overlay (`<project root>/agent_profiles/`, or the caller's overlay dir) | overrides org |

Discovery is recursive in all three layers (`overlay_scan_is_recursive`), matching the existing
loader.

### Scoped sentinel read (new)

| Aspect | Value |
| --- | --- |
| Input | an iterable of profile ids (any string; duplicates, blanks and non-strings are tolerated and ignored) |
| Output | `Mapping[str, bool]` — exactly one entry per *distinct non-empty* requested id; `True` iff the effective profile for that id has `sentinel: true` |
| Missing id | key present with `False` (unknown id, `sentinel: false`, or excluded by `applies_to_languages`); no exception |
| Resolution | ids are matched by the repository's `<profile-id>.agent.yaml` filename convention in each layer |
| Cost shape | parses at most one document per requested id per layer that names it (today ≤ 3 documents for a two-profile board, versus 26) |
| Scope of the object | read-only and id-scoped: it is not a catalogue and exposes no `list_all()`/provenance/lineage answer |

## Invariants

1. **Layer parity** — for any id, the scoped answer equals `AgentProfileRepository().get(id).sentinel`
   (`False` when the repository returns `None`). Proven over the shipped catalogue and over
   org/project overlay fixtures.
2. **Merge parity** — an org/project overlay of a built-in id merges field-by-field onto the
   built-in base, so an overlay that only extends metadata keeps the base `sentinel`, and one that
   declares `sentinel: false` flips it.
3. **Scope parity** — a profile excluded by `applies_to_languages` yields `False`, exactly as
   `get()` yields `None` today.
4. **Activation independence** — no activation key (`activated_agent_profiles`, deny entries) may
   change the answer. `sentinel` is structural, like `get_provenance()`.
5. **Default unchanged** — with no scope requested, `AgentProfileRepository` loads exactly what it
   loads on `main` (same documents, same order, same diagnostics).
6. **Lineage is lazy** — the shipped DRG is parsed only when a lineage/hierarchy/graph answer is
   actually requested; an explicit `drg=` remains authoritative.

## State transitions

None. The read is pure and side-effect free: it builds a transient repository-like object per call
and never mutates a shared cache, so concurrent renders cannot observe each other.
