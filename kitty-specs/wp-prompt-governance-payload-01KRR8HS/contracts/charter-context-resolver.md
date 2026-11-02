# Contract: `build_charter_context` with `profile=` load-bearing

**Mission**: `wp-prompt-governance-payload-01KRR8HS`
**Surface**: `charter.context.build_charter_context`
**FRs covered**: FR-001, FR-002, FR-003, FR-008
**ATDD anchors**: `TestCharterContextResolverCompleteness::*`, `TestImplementPromptContainsActionableGovernance::*`, `TestProfileDirectivesSurfacedInWpPrompt::*`, `TestPromptReferencesAuthorityPaths::*`

---

## 1. Input contract

```python
def build_charter_context(
    repo_root: Path,
    *,
    profile: str | None = None,         # NEW: now load-bearing
    action: str,
    mark_loaded: bool = True,
    depth: int | None = None,
    org_root: Path | None = None,
) -> CharterContextResult:
    ...
```

| Parameter | Type | Pre-condition | Post-condition |
|---|---|---|---|
| `repo_root` | `Path` | Directory containing `.kittify/charter/charter.md` (resolved via `charter.resolution.resolve_canonical_repo_root`). | Unchanged. |
| `profile` | `str \| None` | When provided, MUST be a profile ID resolvable via `AgentProfileRepository.default().get(profile)`. Unknown profiles do NOT raise — resolver renders the prompt with profile sections omitted and logs a warning. | Profile YAML loaded once per call; not mutated. |
| `action` | `str` | One of `BOOTSTRAP_ACTIONS` (`specify`, `plan`, `implement`, `review`) for the bootstrap path; any string for the compact path. Case-insensitive. | Normalised to lowercase in output. |
| `mark_loaded` | `bool` | When True, records first-load timestamp into `.kittify/charter/context-state.json`. | Side effect identical to today. |
| `depth` | `int \| None` | Override the auto-computed effective depth. | Unchanged. |
| `org_root` | `Path \| None` | Path to org doctrine snapshot. | Unchanged. |

---

## 2. Output contract

Returns `CharterContextResult` (frozen dataclass, shape unchanged). The
`text` field MUST contain the following sections **when** `profile=<known-id>`
**and** `action` is a bootstrap action:

| # | Section header (anchor) | Required when | Content |
|---|---|---|---|
| 1 | `Charter Context (Bootstrap):` | always | Source path + first-load guidance. |
| 2 | `Policy Summary:` | charter has `## Policy Summary` OR resolver falls back to bullets | Up to 8 bullets. |
| 3 | `Project authority paths:` | bootstrap action | At minimum `glossary/contexts/` and `architecture/2.x/adr/` (when those directories exist on disk); additionally every path in `governance.doctrine.authority_paths`. Each entry carries a one-sentence "When you …, …" conditional. |
| 4 | `Action-Critical Charter Sections (<action>):` | bootstrap action AND charter has at least one action-critical section | For each section in the action-critical set, either the verbatim body OR the fetch + when-doing stanza. The action-critical set for `software-dev` defaults to `Terminology Canon`, `Code Review Checklist`, `Regression Vigilance`; missions MAY extend the set. |
| 5 | `Profile-Cited Directives (<profile-id>):` | bootstrap action AND `profile=<id>` resolvable AND profile has at least one `directive_references` entry | For each `DIRECTIVE_NNN` in `profile.directive_references`, an entry `- DIRECTIVE_NNN: <title> — <rationale>`. Verbatim body inlined when under budget; otherwise replaced with the fetch + when-doing stanza. |
| 6 | `Profile-Cited Tactics (<profile-id>):` | same conditions, for `tactic_references` | Same shape as section 5. |
| 7 | `Action Doctrine (<action>):` | bootstrap action | Existing resolver-driven `Directives:` and `Tactics:` lists (today's behaviour). |
| 8 | `Reference Docs:` | always | Up to 10 reference entries, filtered by action. |

### Verbatim-OR-fetch stanza

Both halves are required. The stanza format is:

```
Run: spec-kitty charter context --include <selector>
When you <action-verb conditional>, run this command and apply the returned rule.
```

The selector is one of:

- `directive:DIRECTIVE_NNN`
- `tactic:<tactic-id>`
- `section:<kebab-cased-heading>`

The conditional matches the regex pinned by the ATDD test helper
`_WHEN_DOING_RE`:

```python
r"when\s+you\s+(are\s+about\s+to|need\s+to|encounter|introduce|rename|review)"
```

### Token budget

The aggregate `text` MUST stay under 32 000 characters. If a render exceeds the
budget, the longest-body section is auto-substituted with its fetch stanza;
substitution iterates until under budget. When all bodies have been substituted
and the prompt is still over budget, the result carries a single line:

```
# Governance payload: <N> sections substituted with fetch commands (budget=32000).
```

---

## 3. Failure modes

| Failure | Behaviour | Side effect |
|---|---|---|
| `profile=<unknown-id>` | Sections 5 and 6 omitted; rest of the payload rendered normally. | Single `WARNING` log line `Profile '<id>' not found; profile-cited sections omitted.` No exception. |
| Catalog citation unresolvable (`DIRECTIVE_NNN` referenced but not in catalog) | The entry appears in section 5 with the ID and the placeholder body `<not found in catalog>`. | Single `WARNING` log line per unresolvable ID. |
| Charter missing the section a `_render_critical_section_bodies` call expected | The section is silently omitted from section 4. | No log line (charter sections are optional). |
| `charter.md` absent | Returns a `CharterContextResult` with `mode="missing"`, exactly as today. | No change to existing behaviour. |
| `profile=<id>` provided but `action` not in `BOOTSTRAP_ACTIONS` | The compact-mode path runs; sections 3-6 are not emitted. | `profile=` is honoured by being recorded in compact view's metadata only; no profile rendering occurs in compact mode. |

---

## 4. Backward compatibility guarantee

When `profile=None` (the default), `result.text` is byte-identical to today's
output for the same `(repo_root, action, depth, org_root)` tuple, with two
additive exceptions:

1. Section 3 (`Project authority paths:`) appears when at least one default
   authority directory (`glossary/contexts/` or `architecture/2.x/adr/`) is
   present on disk. This is a new section that today's callers do not expect.
2. Section 4 (`Action-Critical Charter Sections`) appears when the charter body
   contains at least one section in the action-critical set. This is a new
   section that today's callers do not expect.

Both additions are pure prepends to existing content; existing string-matching
callers that look for `Charter Context (Bootstrap):`, `Policy Summary:`,
`Action Doctrine (...):`, or `Reference Docs:` continue to find their anchors.

When `profile=<id>` is provided, sections 5 and 6 additionally appear. No
existing call sites pass `profile=`, so no caller is affected by this change
without an explicit opt-in.

---

## 5. Layer-rule preservation (C-001 / NFR-004)

This contract is implementable without any new import from `specify_cli` in
`charter`. The profile lookup uses
`from doctrine.agent_profiles.repository import AgentProfileRepository` — an
import from `doctrine`, which is below `charter` in the layer order
(`kernel ← doctrine ← charter ← specify_cli`). The test suite
`tests/architectural/test_layer_rules.py` (8 tests) MUST stay green.
