# Contract: Template-path credential injection

## Policy

When resolving a doctrine `org init --template` **git** location, Spec Kitty MUST NOT embed `GIT_TOKEN` into the HTTPS URL.

## Mechanism

`GitSource(..., inject_token=False)` (default remains `True` for other callers).

## Documentation

Operator docs MUST state that `--template` HTTPS clones are unauthenticated via `GIT_TOKEN`; use SSH remotes for private templates.
