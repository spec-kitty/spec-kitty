# Code grounding: URL baseline, moves ledger and the dual-index folders

Mission `docsite-url-ledgers-01M6BRMR`, for #6927 (S-3) and #6928 (S-4), absorbing #2358 and
folding #3914. Governing record: ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`
(D-1, D-5, D-7). Read-only pass on `origin/main` at `7e2ca9fd` (2026-11-01). Every number below was
measured in this session; the command is named next to it.

Audience: the implementer and reviewer of this Mission (lead developer, docs tooling).

## 1. Current redirect machinery

### `scripts/docs/redirect_stub_generator.py` (447 lines)

Four subcommands, each taking `--baseline`, `--redirect-map`, `--site-dir` and `--occurrence-map`:

| Subcommand | What it does | Inputs |
|---|---|---|
| `regenerate-map` | Derives `redirect_map.yaml` from the baseline manifest plus an occurrence map's `moves:` spine and **overwrites** the map. | `redirect_baseline_urls.json` + occurrence map |
| `check-map` | Re-derives and compares with the committed map (freshness). | same |
| `generate` | Writes a `<meta refresh>` stub at each old path inside `_site`; a target missing from `_site` is a `dead_target` and exits 1. | `redirect_map.yaml` + `_site` |
| `coverage` | Every baseline URL resolves directly or through a stub to a live target; refuses an empty baseline. | baseline manifest + `redirect_map.yaml` + `_site` |

The binding #2358 reports is still live, one mission later: `MISSION_SLUG =
"common-docs-convergence-01KZMTR9"` and `DEFAULT_OCCURRENCE_MAP =
kitty-specs/<MISSION_SLUG>/occurrence_map.yaml` (lines 77–80). The closed structural-move Mission's
default was retired, but the replacement is another closed Mission (`common-docs-convergence-01KZMTR9`).
`_relocate` is single-move and first-match, so that map had to carry the earlier Mission's spine
forward as a "collapsed cumulative spine". The derivation filters on the 180-URL manifest, so a move
whose old URL is not in that manifest never earns a redirect. That filter is the source of #3914.

### Data files

- `scripts/docs/redirect_map.yaml`: 163 entries (header + `old.html: new.html`). Every target is a live
  page in today's DocFX build; no key is a live page (measured, §2).
- `scripts/docs/redirect_baseline_urls.json`: 180 URLs (`url_count`), `capture_method`, `site_url` and an
  `amendments` list with 3 records (2026-07-04 operator ruling #2350 `migration/`→`migrations/` with no
  stubs; 2026-07-04 capture defect `assets/index.html`; 2026-07-20 Mission extension adding 13
  `guides/*.html` URLs). That list is the provenance the new ledger header must carry.
- Occurrence maps of closed Missions:
  - `kitty-specs/common-docs-structural-move-01KW3SBK/occurrence_map.yaml` (625 lines);
  - `kitty-specs/common-docs-convergence-01KZMTR9/occurrence_map.yaml` (349 lines, 247 `moves:`
    entries, the current default).

### `scripts/docs/capture_baseline_urls.py` (302 lines)

Two methods: `--site-dir` (DocFX site walk, the canonical capture) and derive-from-source (resolves
`docfx.json` globs). It writes the JSON manifest. It is documented as "must not be regenerated after
the move", amendments only.

### `scripts/docs/rename_reconcile.py` (387 lines)

Two gates over one occurrence map (default: the convergence Mission's):

- `rename_reconcile`: every git rename or deletion under `docs/` (plus the map's non-`docs/` roots) is
  covered by a `moves:` `from:` prefix.
- `occurrence_subset_redirect`: every concrete `.md` file move not `RETIRE` has its old URL as a
  redirect-map key.

### Other scripts that read a Mission-scoped occurrence map

These are in scope for "no script reads a Mission-scoped occurrence map":

- `scripts/docs/bulk_ref_rewrite.py`: `DEFAULT_OCCURRENCE_MAP` is env-overridable, falls back to the
  closed structural-move map; `load_moves` returns `(from, to)` source-path pairs.
- `scripts/docs/relative_link_fixer.py`: imports `DEFAULT_OCCURRENCE_MAP` and `load_moves` from
  `bulk_ref_rewrite`.
- `scripts/docs/touched_set_gates.py` reads **no** occurrence map (checked). It carries the
  `one_index_per_dir` check (advisory, config-driven), which is the structural rule S-4 satisfies for
  the four folders.

ADR D-6 classes `bulk_ref_rewrite.py`, `rename_reconcile.py` and `touched_set_gates.py` (the last needs no repoint) as "keep for
the README rename, then drop", and says their binding to a closed Mission's map "is replaced by
`site/moves.yaml`".

### Tests on this machinery

- `tests/docs/test_redirect_stub_generator.py` (312 lines): derivation unit tests, `committed map is
  diff-stable` (re-derives from the occurrence map), stub/coverage tests, baseline loading and
  amendments.
- `tests/docs/test_redirect_spine.py` (380 lines): pins the collapsed cumulative spine (149-key frozen
  snapshot, superset, archive twice-move, and `test_tool_default_targets_this_convergence_mission`,
  which asserts the Mission binding itself).
- `tests/docs/test_capture_baseline_urls.py` (271 lines), `tests/docs/test_publish_manifest_coherence.py`
  (311 lines) + `_publish_manifest_helpers.py`.
- `tests/docs/test_bulk_ref_rewrite.py`, `test_relative_link_fixer.py`, `test_touched_set_gates.py`
  (fixture-driven; they pass their own maps).
- `tests/architectural/test_archive_root_byte_identical.py` pins the convergence map as an
  append-only spine (`SPINE`, `_APPEND_ONLY_SPINE_EXCEPTIONS`). That map is a closed Mission artifact
  and stays byte-identical; this Mission does not edit it.

## 2. `docs-pages.yml` and deriving the baseline from a DocFX build

`docs-pages.yml` (push to `main`/`2.x` and dispatch only; no `pull_request` trigger) builds DocFX
(`generate_kitty_specs_docs.py`, `docfx docfx.json`, `seo_postprocess.py`), runs the glossary linker and
PlantUML, then:

- line 166: `redirect_stub_generator.py generate --site-dir docs/_site`;
- line 172: `redirect_stub_generator.py coverage --site-dir docs/_site`;
- then `seo_verify.py --strict` and upload.

Neither step reads the occurrence map: `generate` reads `redirect_map.yaml`, `coverage` reads the
manifest. Repointing `regenerate-map` therefore changes nothing in the deploy job, as long as the
committed map stays the generator's output.

**Local DocFX build (done in this session).** The container had no .NET; `dotnet-sdk-8.0` came from
the Ubuntu archive and `docfx` 2.81.0 from NuGet. In a throwaway worktree of `HEAD` I ran the
workflow's build steps. `www.plantuml.com` is unreachable from the sandbox, so the five
` ```plantuml ` fences were rewritten to ` ```text ` in that copy only. That changes diagram rendering,
not which pages are emitted. Results:

| Measure | Count |
|---|---|
| `capture_baseline_urls.py --site-dir docs/_site` (all) | 6,267 `.html` |
| of which `kitty-specs/**` (generated dashboards, outside the baseline per ADR D-5 "Dropped dashboards") | 5,594 |
| of which `toc.html` (DocFX's navigation fragment, not a page) | 1 |
| **site-walk pages** | **672** |
| derive-from-source on the clean tree | 673 = 672 `.html` + `assets/index.md` (resource, outside the `.html` universe per the 2026-07-04 amendment) |
| site walk minus derive-from-source | only `toc.html` |
| `redirect_map.yaml` keys that are live pages | 0 |
| redirect targets missing from the build | 0 |
| old 180-URL manifest URLs not in walk ∪ map keys | 0 |
| **walk ∪ map keys** | **835** |

The ADR measured 668 + 163 = 831 at its base; `main` has since gained four pages. The seed is
therefore 835 before this Mission's own additions, and the ADR's number is a point-in-time count.

DocFX publishes 16 `README.html` URLs, including the four collision folders' `adr/1.x/README.html`,
`adr/2.x/README.html`, `adr/3.x/README.html` and `architecture/README.html` (the ADR says 16; matches).

For CI, the same walk can run in `docs-pages.yml` after `Build documentation`. It is a deploy-time job,
so this Mission uses it only to **report** URLs missing from the baseline. It does not gate the deploy.
The PR-time guard is a `tests/docs/` test over derive-from-source, which matches the walk except for
`toc.html`.

## 3. #3914 reproduced

`rename_reconcile.py --base a60425c… --strict` cannot run here as written: the clone is shallow and
does not hold that commit. The forward gate needs no git, so I ran it directly
(`check_occurrence_subset_redirect(load_moves(DEFAULT_OCCURRENCE_MAP), redirect keys)`):

- 247 moves examined, 163 redirect keys, **124 `occurrence_subset_redirect` violations**, matching the
  issue.
- None of the 124 old URLs is in the 180-URL manifest, which is why the derivation never emitted them.
  None of the old source paths still exists.
- Resolving each through the convergence spine against today's build:
  - **113** resolve to a live page (for example `status-model.html` → `architecture/status-model.html`,
    and the ADR renumberings the issue names);
  - **11** resolve to a page that has since moved again or been folded, so a stub would be a dead
    target:
    - `architecture/README-{1,2,3}.x.html`, distilled into the era indexes;
    - `doctrine/create-a-doctrine-artifact.html`, now under `development/how-to/`;
    - `development/process-global-inventory-3115.html`;
    - three `plans/*.html` files;
    - `plans/{initiatives,next-mission-mappings}/README.html`;
    - `plans/saas-hosted-sync-domain-plan.html`.

  Each needs its final destination looked up, or a hub redirect (D-5 rule 4).

Reconciling means a ledger entry per moved URL to its final live page, which closes the class: every
file move in the ledger carries a redirect. The 124 URLs join the baseline as redirect keys (D-5:
baseline = walk ∪ every map key). Whether each was once live cannot be proven from this shallow
history. A stub for a URL that was never live costs one HTML file and breaks nothing, so the Mission
redirects all of them instead of claiming they were never published.

## 4. The four collision folders

| Folder | `README.md` | `index.md` | Inbound references to the README |
|---|---|---|---|
| `docs/adr/1.x/` | 7-line redirect stub ("moved to index.md") | era index | `tests/ci/test_regen_docs_index.py` (path classification only); `freshen_adr_inventory.py` falls back to `README.md` only when `index.md` is absent |
| `docs/adr/2.x/` | 7-line stub | era index | `tests/docs/test_adr_readme_prose.py` reads `docs/adr/2.x/README.md` (and the other two); it must move to the `index.md` files or drop the deleted stubs |
| `docs/adr/3.x/` | 7-line stub | era index | `docs/plans/engineering-notes/651-docs-consolidation/index.md` (plan, immutable) |
| `docs/architecture/` | 131-line landing page (boundary rule, living vs frozen, decay rule) | 127-line page index that links `README.md` twice and lists it in `related` | `architecture/vision/README.md` and `architecture/diagrams/README.md` `related:`; `src/charter/offering/templates/diagrams/README.md` (two links); `tests/charter_offering/test_wp_authoring_contract_roundtrip.py` (`DOC_AUTHORED_OWNED_FILES`); `CLAUDE.md` / `AGENTS.md` ("following `docs/architecture/README.md` template"); `tests/docs/test_touched_set_gates.py:121` (a `tmp_path` fixture, unaffected); ADR bodies 1.x `2026-01-23-1` and 3.x `2026-06-27-1` (immutable, prose mentions) |

Removing `docs/architecture/README.md` from three `related:` lists is a frontmatter edit, the only one
in this Mission. #6929 (the frontmatter migration) runs in parallel and will meet those three lines. ADR
ruling 11 says each PR resolves its own conflicts.

### Generated surfaces: the current process on `main`

#6993 moved the docs retrieval index, the page inventory and the ADR era table rows to a post-merge bot
(`docs-index-regen.yml` → `scripts/ci/regen_docs_index.py`, proposing the fixed branch
`ci/regen-docs-index`). A PR that edits `docs/development/docs-retrieval-index.yaml` or
`page-inventory.yaml`, or adds an ADR era table row, fails the `docs-lint` guard
(`scripts/ci/check_generated_docs_untouched.py`). So #6928's "`docs_index.py --write` and the page
inventory are regenerated" is met by the bot after merge, and this PR must **not** touch them. Deleting
the README stubs adds no era table row, so the guard passes. `tests/docs/test_docs_index_regenerates_cleanly.py`
is the per-PR content check to run.

Changelog: per-PR fragment in `docs/changelog/unreleased/<id>.<section>.md` (#6988), never
`CHANGELOG.md`.

## 5. Gates that reference these files

- `tests/architectural/test_archive_root_byte_identical.py`: the convergence occurrence map is an
  append-only spine. Do not edit it.
- `tests/architectural/test_no_legacy_terminology.py`: run before push.
- `tests/architectural/test_gate_remedy_presence.py`, `global_state_allowlist/S6.yaml`,
  `test_no_dead_doctrine_paths.py`: they name `relative_link_fixer` / `bulk_ref_rewrite` test files.
  Run them if those scripts change.
- `tests/cross_cutting/packaging/test_packaging_safety.py`: the sdist `include` is an allowlist
  (`src/**/*`, `packs/built-in/**`, `pins/**`, root files). `site/` is not in it, and it is not under a
  wheel package, so the two new data files do not ship. #6926 (another session) narrows the bare
  `README.md` include; nothing here touches packaging.
- `scripts/ci/check_generated_docs_untouched.py` (`docs-lint`): see §4.
- `docs/docfx.json` content globs are rooted in `docs/`; a root-level `site/` is outside DocFX.

## 6. Churn (90 days, from a `--shallow-since=2026-08-01` deepen)

- `scripts/docs/redirect*`, `rename_reconcile.py`, `capture_baseline_urls.py`: 5 commits. Two
  `2026-08-10` convergence commits created the current shape (`e0d09b88e`, `54108a7c9`). Two `2026-10-01`
  dashboard-removal sweeps (#5530) adjusted the map. On `2026-11-01` `0278515da` fixed
  `capture_baseline_urls`' exclude matching. Low churn, so the surface is stable to change.
- `docs/adr/*/README.md` + `docs/architecture/README.md`: 8 commits. They are mostly index refreshes
  and convergence sweeps, with the stubs created by the convergence (2026-08-10). The last change was
  2026-09-30 (`e84cb84f1` and `28b32dd3f`, the 4.x re-anchor and archive sweep).

## 7. Consequences for the design

1. **Ledger format.** Use the published route in its legacy DocFX form (`a/b.html`, site-relative,
   no leading slash) on both sides of a move. Both generators can read it. DocFX uses it as is. A
   doc-kitty generator maps `X.html` to `X/` and `dir/index.html` / `dir/README.html` to `dir/`
   (D-5 rule 1). Routes and `docs/` source paths convert one to one for pages, which the rename gate
   and link rewriters need.
2. **Append-only with chain collapse.** When a destination moves later, append a new entry. The
   generator collapses chains to the final route, as D-5 rule 2 requires and `_relocate` could not.
3. **`redirect_map.yaml` is derived from `site/moves.yaml` alone** (every ledger `from:`, collapsed).
   No baseline filter, so a ledgered move always earns a redirect. A test asserts no key is a live page
   and every target is.
4. **`site/url-baseline.txt` = site walk (672) ∪ every derived map key** (163 existing, plus #3914's 124,
   plus the S-4 entries), with a provenance header. A test asserts it contains every URL of the old
   manifest and every map key.
5. **The convergence and structural-move occurrence maps stay untouched** (closed Mission artifacts).
   Nothing reads them after this Mission.
