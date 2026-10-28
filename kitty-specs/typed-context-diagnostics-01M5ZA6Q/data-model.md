# Data Model: Typed context JSON diagnostics

## GovernanceDiagnosticCode (closed enum, JSON-stable strings)

| Code | Producer sites (message, abridged) |
|------|-------------------------------------|
| `UNKNOWN_SELECTION_DROPPED` | `Unknown selected {kind} '{token}' dropped: ...` (paradigm, directive) |
| `CATALOG_DEFAULT_APPLIED` | `No activated paradigm set configured; using built-in catalog default (N paradigms).`; same for directives |
| `FALLBACK_APPLIED` | `No available_tools selection provided; using runtime tool registry fallback.`; `Template set not selected in charter; fallback '<x>' applied.` |
| `SELECTION_MERGED` | `Charter declared additional tool(s) beyond the runtime registry: ...`; `Charter selected N {noun}(s) beyond the <base> base: ...`; `All N charter-selected {noun}(s) already present ...; none added: ...`; `Merged N project-local directive(s) onto the <base> set: ...`; `All N project-local directive(s) already present ...; none added: ...` |
| `UNRESOLVED_REFERENCE` | `Unresolved reference: {type}/{id}` (profile governance path) |

## GovernanceDiagnostic (value object, immutable)

- `code: GovernanceDiagnosticCode` — classification; consumers match on it.
- `message: str` — human-readable detail; wording may change without notice.
- JSON form: `{"code": "<CODE>", "message": "<text>"}`, exactly two keys.

## GovernanceResolution.diagnostics

`list[GovernanceDiagnostic]`, in producer order, `[]` when nothing to report.

## Invariants

- Every entry's code is a member of the enum (closed set).
- Classification never depends on `message`.
- Text renderings show `message` only, unchanged from today.
