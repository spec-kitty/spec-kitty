# Research: Doctrine Org Init From Template

## Decision: Extend `org init` (not a new command)

- **Rationale**: Spec and operator intent are to extend the existing
  `spec-kitty doctrine org init` surface. A second command would split
  discovery and violate single canonical CLI authority.
- **Alternatives considered**: `doctrine org render` / `doctrine template init` —
  rejected as parallel surfaces for the same operator job.

## Decision: Full-tree copy minus `.templateignore`

- **Rationale**: Confirmed in planning; reference templates are repo roots
  (Makefile, `pack/`, scripts). Default LOCAL_PATH=`pack` matches that layout.
- **Alternatives considered**: Copy only `pack/` contents into PACK_PATH —
  rejected (planning choice A).

## Decision: Reuse `GitSource` for git TEMPLATE

- **Rationale**: `specify_cli.doctrine.sources.git_source.GitSource` already
  clones HTTPS/SSH with optional `ref`, token redaction, and cleanup on failure.
  Fetch into a temp directory, then run the same local copy/ignore/substitute
  path as a filesystem TEMPLATE.
- **Alternatives considered**: Ad-hoc `subprocess` clone in the CLI command —
  rejected (duplication, weaker error redaction). Persistent clone under
  `~/.spec-kitty` — rejected for one-shot init (operator destination is
  PACK_PATH; no need for a long-lived cache in v1).

## Decision: Branch via `--branch` and/or TEMPLATE encoding

- **Rationale**: Confirmed in planning (both supported). Encoded forms for v1:
  - HTTPS/SSH URL with `#<ref>` fragment (e.g. `https://…/repo.git#main`)
  - Trailing `@<ref>` when not ambiguous with SCP-like `git@host:path` userinfo
    — prefer `#ref` as the documented encoding; support `@ref` only on
    `https://` URLs and on `ssh://` URLs to avoid eating `git@`.
- **Conflict rule**: If `--branch` is set and TEMPLATE also encodes a ref, and
  the values differ → error naming both; if equal → accept.
- **Alternatives considered**: `--branch` only, or encoding only — rejected.

## Decision: Ignore matching via stdlib `fnmatch` (no new dependency)

- **Rationale**: Repo already uses `fnmatch` for path filters; `pathspec` is not
  a project dependency. Implement gitignore-like subset: comments, blank lines,
  directory patterns ending in `/`, `*` / `?` / `**`-style recursive patterns
  via careful relative-path matching. Always built-in-exclude `.git/` and
  `.templateignore` from the written tree.
- **Alternatives considered**: Add `pathspec` dependency — rejected for v1
  scope (locality of change). Shell out to `git check-ignore` — only works
  inside a git work tree and couples render to git binary even for local
  copies.

## Decision: Validate before any PACK_PATH write for template path

- **Rationale**: FR-004/FR-010 fail-closed; avoid partial trees on bad ORG_NAME.
  Overwrite guard (`exists` without `--force`) still applies before write.
- **Alternatives considered**: Write then validate — rejected.

## Decision: ORG_NAME rules copied from doctrine-template contract

- **Rationale**: C-001 / FR-004. Regex
  `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, length 2–64, not `doctrine-org`, not
  placeholder/`TODO` literals. No silent sanitising.
- **Alternatives considered**: Reuse a looser slug sanitiser from elsewhere in
  the CLI — rejected (would diverge from template contract).

## Open items carried into design (resolved)

| Item | Resolution |
|---|---|
| Binary / non-UTF8 files during substitute | Attempt UTF-8 decode; if fails, leave bytes unchanged and do not scan for tokens (document in contract); leftover-token check applies only to successfully decoded text files |
| Post-render quality-check gate | Out of scope for init success (spec assumption) |
| Template authoring | Out of scope |
