# Quickstart: routing a documentation-maintenance request

Mission: `dispatch-router-docs-coverage-01M6BTTX` · Issue #6970

## Before (reproduced on `main` @ `287a226cfe`)

```console
$ spec-kitty dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run --json
{"error": "routing_failed", "error_code": "ROUTER_NO_MATCH", "message": "ROUTER_NO_MATCH: No profile matched. Use 'spec-kitty dispatch \"<request>\" --profile <id>' or run 'spec-kitty profiles list'.", "candidates": [], "suggestion": "..."}
$ echo $?
1
```

No Op, no candidate, no profile id — the caller has to read the catalog and guess.

## After

### A docs-maintenance request routes on its own

```console
$ spec-kitty dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run --json
{"status": "dry_run", "profile_id": "curator-carla", "action": "classify",
 "router_confidence": "domain_keyword",
 "alternatives": [...]}
$ echo $?
0
```

The confidence is `domain_keyword`: the request's documentation-artifact noun (`adr`)
resolves to the documentation domain, and the one profile that declares it is selected.
Add `--profile curator-carla` only when you want a different action.

### A refusal names what to do next

```console
$ spec-kitty dispatch "reticulate the splines" 
No profile matched. Closest: python-pedro (implement), implementer-ivan (implement).
Retry with 'spec-kitty dispatch "reticulate the splines" --profile python-pedro',
or run 'spec-kitty profiles list'.
```

with `--json`:

```console
$ spec-kitty dispatch "reticulate the splines" --json
{"error": "routing_failed", "error_code": "ROUTER_NO_MATCH",
 "message": "ROUTER_NO_MATCH: No profile matched. Closest: ...",
 "candidates": [{"profile_id": "python-pedro", "action": "implement",
                 "match_reason": "partial overlap on 'splines'", "confidence": "partial"}],
 "suggestion": "..."}
```

If a request shares nothing with any profile, `candidates` stays empty and the suggestion
names `spec-kitty profiles list` instead of inventing an id.

### A genuine tie stays a refusal, but says who tied

```console
$ spec-kitty dispatch "fix the unused eslint-disable lint warning" --json
{"error": "routing_failed", "error_code": "ROUTER_AMBIGUOUS",
 "candidates": [ ... tied implementer profiles ... ],
 "suggestion": "Multiple profiles matched: java-jenny (implement), python-pedro (implement). Retry with 'spec-kitty dispatch \"<request>\" --profile java-jenny' (one of the ids above), ..."}
```

Pick one id and re-run with `--profile`; the router does not silently choose between
equals.

## Verify locally

```bash
uv run pytest tests/specify_cli/invocation/test_router.py \
              tests/specify_cli/invocation/test_docs_domain_routing.py \
              tests/specify_cli/invocation/cli/test_dispatch.py -q
```

## Notes

- `spec-kitty profiles list` shows the routing catalog for the current project
  (activation-gated), so it is the authoritative answer to "which id do I pass?".
- A project that deactivated its documentation profile has no docs target; the refusal
  will name the nearest activated profiles rather than a deactivated one.
- Bare `index` is not a documentation signal; say "documentation index" or "ADR index".
