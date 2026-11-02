# WP01 review feedback (cycle 1) — reviewer-renata

**Verdict: REJECTED** (one blocking defect; everything else checks out).

## Blocking

### B-1. `site/pnpm-lock.yaml` pins doc-kitty to an SSH clone URL, so `pnpm install --frozen-lockfile` needs an SSH credential

`site/pnpm-lock.yaml:699-700`:

```yaml
'@spec-kitty/doc-toolkit@git+https://git@github.com:spec-kitty/doc-kitty.git#45e455b...&path:/src':
  resolution: {commit: 45e455b154b3ea97e9e1914a9962bf0aea55d043, path: /src, repo: git@github.com:spec-kitty/doc-kitty.git, type: git}
```

(the importer `version:` at line 19 and the snapshot key at line 3295 carry the same `git@github.com:` form).

pnpm's git fetcher clones `resolution.repo`. pnpm writes the SSH form when its "is this repository public?" probe of `https://github.com/spec-kitty/doc-kitty` fails; in this sandbox the egress proxy answers that probe with 403 (`curl -o /dev/null -w '%{http_code}' https://github.com/spec-kitty/doc-kitty` → `403`), so pnpm treated the repository as private. The local install and the 642-page build still worked only because this container sets `url.https://github.com/.insteadOf git@github.com:` (and `ssh://git@github.com/`) through `GIT_CONFIG_*` environment variables, which hides the problem.

Reproduction (fresh store, the sandbox rewrite removed):

```
cp site/package.json site/pnpm-lock.yaml <scratch>/ && cd <scratch>
env -u GIT_CONFIG_COUNT -u GIT_CONFIG_KEY_{0,1,2} -u GIT_CONFIG_VALUE_{0,1,2} \
  pnpm install --frozen-lockfile --store-dir <scratch>/store --ignore-scripts
→ pnpm: Command failed with exit code 128: /usr/bin/git clone git@github.com:spec-kitty/doc-kitty.git ...
  fatal: Could not read from remote repository.
```

A GitHub Actions runner has no SSH key and no such rewrite, so the WP03 `docs-site` job, and any maintainer without a GitHub SSH key running `make docs-site` (WP02), would fail at install. This breaks ADR 2026-10-31-1 D-2 ("resolved from the public repository with no token"), NFR-001, SC-002 and SC-004.

**Fix:**
1. Regenerate the lockfile so the toolkit resolves over HTTPS (`repo: https://github.com/spec-kitty/doc-kitty.git`, and the matching `git+https://github.com/spec-kitty/doc-kitty.git#…` keys), in an environment where pnpm's public-repository probe of `https://github.com/spec-kitty/doc-kitty` succeeds. If that probe cannot succeed here, record that in `traces/tooling-friction.md`, make the three occurrences consistent by hand, and prove the result with the reproduction above (rewrite removed, fresh store), which must then exit 0.
2. Add a test to `tests/docs/test_site_scaffold.py` (extend `test_doc_kitty_is_pinned_by_commit_in_manifest_and_lockfile`) that fails when any lockfile entry for `@spec-kitty/doc-toolkit` names `git@`, `ssh://` or `git+ssh`, and asserts `repo: https://github.com/spec-kitty/doc-kitty.git` alongside the commit. The current test only checks that the SHA appears somewhere in the lockfile, so it passes on the SSH form. Commit the new assertion red before you fix the lockfile.
3. Re-run `cd site && pnpm install --frozen-lockfile && pnpm exec astro build` and record the exit code and page count again.

## Non-blocking observations (no change needed for approval)

- O-1. The implementation commit `0867e364` changed the red test's redirect assertion (`tests/docs/test_site_scaffold.py:104-105`), from a substring match to an option-shaped regex, because the config comment mentions "redirects". This makes the test more precise and keeps its intent. It is fine, but say so in the PR so a reader does not read it as the test being loosened during the green step.
- O-2. `docs/_meta/sections.yaml` declares `version: 1`, but no test pins it. Optional: assert `registry["version"] == 1` in `test_every_published_section_is_registered`.

## Verified and passing (for the record)

- Red→green: at `f76923ae` the test module fails at collection (`ImportError: cannot import name 'site_contract'`). On HEAD it passes: 13 passed.
- Single authority: `python -m scripts.docs.site_contract --check` exits 0. `astro.config.mjs` restates no folder and reads `dockitty-contract.json`. The drift and missing-copy negative controls work.
- The ADR values are in place: site URL, `base: '/'`, `docsDir: '../docs'`, `diagrams: false`, no redirects, `DK_PUBLISH_DRAFTS=off`, the 40-character SHA in `package.json`, and no loader shim. `sections.yaml` registers exactly the published top-level folders, and `plans` has `feeds: [sitemap]`.
- ruff check, ruff format --check --force-exclude and mypy --strict on the new Python code are all clean.
- Packaging `-k sdist`: 11 passed. `tests/docs`: 2004 passed, 8 skipped. DocFX `docfx.json` content globs do not reach `_meta/`.
