# Semantic Drift Examples

Concrete patterns of terminology drift with detection signals and correction strategies.

---

## Pattern 1: Synonym Substitution

**What happens:** An artifact uses an informal synonym instead of the canonical
term. The glossary is never consulted because the synonym is a different surface
form.

**Example:**

- Glossary defines: `work package` -- "Execution slice inside a mission run"
- A plan document says: "Each **task** will be assigned to an agent"
- "task" is not a glossary term, so no conflict fires, but the meaning is
  identical to "work package"

**Detection signals:**

- `spec-kitty glossary conflicts` shows no conflicts, yet reviewers flag
  inconsistent language
- Full-text search finds domain concepts expressed with non-canonical words
- The `unknown` conflict type fires on the synonym if strictness is `max`

**Correction:**

1. Replace the synonym in the artifact with the canonical term
2. If the synonym is genuinely useful, add it to the glossary as a separate
   surface with a cross-reference definition (e.g., `task` -- "See: work
   package. Not a Spec Kitty term; use 'work package' in mission artifacts")
3. Set the cross-reference entry to `status: deprecated` so it does not
   participate in resolution but documents the mapping

---

## Pattern 2: Definition Erosion

**What happens:** The glossary definition is correct at creation time, but the
project's actual usage gradually shifts. The glossary becomes stale without
anyone noticing.

**Example:**

- Glossary defines: `workspace` -- "Git worktree directory created for
  implementing a work package"
- Over time, team members start using "workspace" to mean "the VS Code window
  where I develop," which has nothing to do with git worktrees
- New specs written with the colloquial meaning pass through the `medium`
  strictness gate because there is only one active sense (no AMBIGUOUS conflict)

**Detection signals:**

- Reading recent artifacts reveals that the term's contextual usage no longer
  matches the stored definition
- An INCONSISTENT conflict may fire if the LLM output contradicts the
  definition (but heuristic detection is not guaranteed)
- Manual review during `/spec-kitty.review` catches the mismatch

**Correction:**

1. Update the seed file definition to match current authoritative usage
2. If both meanings are valid, add a second sense in the appropriate scope and
   let the AMBIGUOUS conflict force explicit disambiguation
3. Add a comment in the seed file explaining why the definition changed

---

## Pattern 3: Scope Leakage

**What happens:** A term defined in a narrow scope (e.g., `mission_local`)
starts appearing in artifacts that belong to a broader context, carrying its
narrow definition where it does not apply.

**Example:**

- `mission_local` defines: `endpoint` -- "The /api/v2/reports REST route"
- A team-wide architecture document references "endpoint" assuming the
  mission-local definition, but readers outside the mission interpret it as
  any API route
- The narrower definition "wins" during resolution (mission_local has highest
  precedence), masking the broader team meaning

**Detection signals:**

- Terms that appear in cross-mission documents but are only defined in
  `mission_local`
- No conflict fires because scope precedence silently selects the narrow sense
- Reviewers from other teams flag confusion

**Correction:**

1. Add a `team_domain` definition for the broader meaning
2. Keep the `mission_local` definition for the specific mission
3. When the mission ends, either deprecate the `mission_local` sense or promote
   the broader definition to `team_domain`

---

## Pattern 4: Ghost Deprecation

**What happens:** A term is deprecated in the seed file but continues to appear
in active artifacts. The glossary no longer enforces it, so drift goes unnoticed.

**Example:**

- `lane` was deprecated in favour of `status` in the seed file
- Existing WP frontmatter still contains `lane: doing`
- No conflict fires because deprecated terms are excluded from resolution

**Detection signals:**

- `spec-kitty glossary list --status deprecated` shows terms that may still
  appear in artifacts
- Full-text search for deprecated surface forms in `kitty-specs/` finds hits
- Reviewers flag outdated terminology

**Correction:**

1. Search all active artifacts for the deprecated surface form
2. Replace with the canonical successor term
3. If the deprecated term must remain for backward compatibility (e.g., in
   YAML keys), document the mapping in the seed file comment

---

## Pattern 5: Confidence Decay

**What happens:** Auto-extracted terms enter the glossary as `draft` with low
confidence. They are never promoted to `active`, so they participate in
resolution with weak authority. Over time, higher-confidence extractions
with slightly different definitions accumulate, creating silent ambiguity.

**Example:**

- Auto-extraction adds: `primitive` (confidence 0.4, draft) -- "A step in the
  mission"
- Later extraction adds: `primitive` (confidence 0.6, draft) -- "A custom
  operation defined in mission.yaml"
- Neither is promoted to `active`, so both participate in resolution
- The AMBIGUOUS conflict may not fire because neither sense is `active`
  (ambiguity detection checks active senses only)

**Detection signals:**

- `spec-kitty glossary list --status draft` shows terms with multiple low-
  confidence senses
- `spec-kitty glossary list --json` piped through a script can flag surfaces
  with more than one sense

**Correction:**

1. Review draft senses and promote the correct one to `active`
2. Deprecate or delete incorrect draft senses
3. Set confidence to 1.0 on the promoted sense

---

## Pattern 6: Cross-Mission Collision

**What happens:** Two missions define the same term in `mission_local` with
different meanings. When both missions are active (parallel development), the
glossary state depends on which seed file was loaded last.

**Example:**

- Mission A defines: `component` -- "React UI component"
- Mission B defines: `component` -- "Microservice deployment unit"
- Both are in `mission_local.yaml` (which is per-project, not per-mission)
- The second definition overwrites the first in the store

**Detection signals:**

- `spec-kitty glossary conflicts` shows AMBIGUOUS conflicts on the colliding
  term
- Agents working on different missions get unexpected definitions
- Event log shows repeated `GlossarySenseUpdated` events for the same surface

**Correction:**

1. Qualify the surface forms: `react component` and `service component`
2. Or move one definition to `team_domain` if it is the broader concept
3. Ensure each mission's local terms do not collide with parallel missions

---

## Prevention Checklist

Use this checklist during `/spec-kitty.review` or when auditing terminology:

- [ ] Every canonical term in the spec appears in the glossary
- [ ] No informal synonyms are used where a canonical term exists
- [ ] Glossary definitions still match actual project usage
- [ ] No `mission_local` terms leak into cross-mission documents
- [ ] Deprecated terms do not appear in active artifacts
- [ ] Draft terms with multiple senses are reviewed and one is promoted
- [ ] Parallel missions do not define the same surface in `mission_local`
