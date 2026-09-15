# Data Model: Org Init Template Security Remediation

No persistent domain entities added. Pipeline value objects remain:

| Type | Module | Notes |
|---|---|---|
| `ParsedTemplate` | resolve | `kind` stays `local` \| `git`; scheme reject happens before git kind accepted for http/git |
| `ResolveError` | resolve | New rule ids: `template.scheme_rejected` |
| `SubstituteError` | substitute | New rule id: `substitute.path_token` (entry names) |
| `PipelineError` | pipeline | Used for explicit nil-source and install guards |
| `GitSource` | git_source | New construction flag `inject_token: bool = True` |

Ignore / copy behaviour: symlink entries are non-copied; not represented as a separate type.
