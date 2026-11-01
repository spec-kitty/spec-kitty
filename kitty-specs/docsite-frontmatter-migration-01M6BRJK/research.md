# Research: Docsite build-blocking frontmatter migration

Grounding evidence: [research/code-grounding.md](research/code-grounding.md). This file records the
decisions that follow from it.

## R-1: Excluded trees need no frontmatter

- **Decision**: use doc-kitty's native `exclude` (`archive`, `reports`, `convergence`,
  `changelog/unreleased`); add no `title`/`description` to the 31 pages.
- **Rationale**: doc-kitty `fe835cd` excludes folders before the glob reads them (ADR-0070). Control
  builds: excluded-only tree with `exclude` → exit 0; same tree without → schema failure on
  `convergence/doctrine-drg`.
- **Alternatives**: the spike's post-validation loader filter plus the schema minimum (rejected:
  edits immutable reports for a shim that upstream has retired).

## R-2: `guidance_text`

- **Decision**: `Written for the <persona title> reader.` (persona title read from the persona page);
  free-text values: `Written for <value>.`
- **Rationale**: required by the schema; a mechanical migration cannot author per-page guidance.
- **Alternatives**: copy the page description (duplicates it on the page); empty string (renders as
  an empty block). Decision Moment `01M6BRRS43THXH8SZ861AFG8M3`.

## R-3: `related` entries that are not published pages

- **Decision**: move to `external_references` as `{url: https://github.com/spec-kitty/spec-kitty/blob/main/<path>, title}`;
  title = the target page's `title` when it is a docs page, else the repository path. Drop an entry
  whose target file does not exist (2 today).
- **Rationale**: frontmatter-only, so immutable bodies stay intact; a body link into an excluded
  folder is dead on both DocFX (which does not publish `archive/`) and doc-kitty; no information is lost.
- **Alternatives**: body link (impossible on immutable `plans/` pages, dead link on living ones);
  drop (loses the pointer). Decision Moment `01M6BRRXG0MVX09DH92W1NTEWP`.

## R-4: What "published" means in core

- **Decision**: a page is published when it is not under an excluded folder and its `doc_status`,
  after this migration, is not `draft` (absent counts as `draft`, as in doc-kitty's `isDraftStatus`).
- **Rationale**: mirrors doc-kitty exactly, so the shape test predicts the build.
- **Consequence**: #6932 will mark engineering-notes, investigations and research as drafts; the
  shape test will then point at every published `related` entry into them.

## R-5: Body-hash test design

- **Decision**: `tests/docs/test_immutable_bodies.py` reads each immutable file (dated ADRs,
  `docs/plans/**`, `docs/reports/**`, `docs/changelog/**`, `docs/archive/**`), hashes its body
  (bytes after the closing fence), runs the migration over the file's text in memory and asserts the
  body hash is unchanged; a mutated fixture must fail. The migration script also offers
  `--verify-against <ref>`: for every Markdown file under `docs/` changed since `<ref>`, the body at
  `<ref>` equals the body now. The mission runs it against `origin/main` and records the result.
- **Rationale**: a permanent git-based comparison against a moving base would fail every later
  legitimate ADR amendment (for example #6902); the in-memory check proves the migration is
  body-preserving on the real corpus without that false positive, and the `--verify-against` run
  proves this PR's diff is frontmatter-only.
- **Alternatives**: a test that compares against a pinned base SHA (fails in shallow CI clones, or
  skips and becomes vacuous).

## R-6: DocFX

- **Decision**: no DocFX change. DocFX reads frontmatter as page metadata and none of the changed keys
  drive its output. `dotnet`/`docfx` are not available in the session; the docs-pages workflow
  builds DocFX on `main`.
