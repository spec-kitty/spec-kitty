# Changelog fragments

Every pull request with a user-visible change adds its changelog entry here, in its own file,
instead of editing `docs/changelog/CHANGELOG.md`. Two pull requests then never conflict on the
changelog. The release assembles the fragments into the `## [Unreleased]` section and deletes them.

These files are not docs pages: the docs index, the page inventory, the frontmatter rules and
the docs site all skip this directory (`scripts/docs/_page_scope.py`), so adding a fragment
touches no shared file.

## Name

`<id>.<section>.md`

- `<id>`: the pull request number. Before the pull request exists, use the issue number
  followed by your branch slug, such as `6862-keep-lane`, and rename the file to the pull
  request number once you know it. Lowercase letters, digits and `-` only. Two fragments with
  the same name are a git conflict: if you hit one, rename yours, never merge the two files.
- `<section>`: one of `breaking`, `upgrade-notes`, `added`, `changed`, `fixed`, `internal`.
  It picks the `###` heading the entry lands under.

Put entries for two sections in two files, for example `6862.fixed.md` and `6862.upgrade-notes.md`.

## Content

The entry exactly as it reads in the changelog, with no heading:

```markdown
- **`spec-kitty consolidate` keeps a lane it cannot prove empty** (#6862, #6850). **Before:** it deleted the lane. **After:** it refuses with `LANE_WORK_TIP_UNKNOWN` and names the restore command.
```

A file may hold more than one entry of the same section. The same style and US spelling rules
as the changelog apply, reported at the fragment's own lines:

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

## Release

`uv run --frozen python -m scripts.release.changelog_fragments assemble` prints the assembled
section; add `--write` to fold the fragments in and delete them. `validate_release.py --mode tag`
refuses while any fragment is left. See `RELEASE_CHECKLIST.md`.
