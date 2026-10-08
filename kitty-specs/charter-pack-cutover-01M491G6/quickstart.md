# Quickstart: charter-pack-cutover-01M491G6

## Operator: upgrade an existing project

```bash
spec-kitty upgrade --dry-run     # read the summary: moved, rewritten, reset, kept for review
spec-kitty upgrade
git add -A && git commit -m "chore: spec-kitty charter-pack cutover"
spec-kitty charter list          # active charter after the upgrade
```

Lanes of missions in flight: upgrade the repository root, then merge the target branch into each lane. Do not rebase a lane.

## Operator: choose a starting point

```bash
spec-kitty charter pack list                     # packs and their presets
spec-kitty charter activate --preset minimal     # curated baseline from the built-in pack
spec-kitty charter activate --preset default --force   # back to every built-in artifact
spec-kitty charter activate --pack acme --preset baseline
```

## Pack author

```bash
spec-kitty charter org init --template <tpl> acme   # scaffolds presets/example.yaml
spec-kitty charter pack validate ./acme-pack        # artifacts, graph, presets, retired fields
spec-kitty charter pack regenerate-graph --check
spec-kitty doctor charter-packs --json
```

Remove `accompanies_doctrine_pack` from `pack.yaml` and rename `doctrine_pack_id` to `charter_pack_id` in `org-charter.yaml`; `charter pack validate` names each occurrence.

## Contributor verification

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q
uv run --frozen pytest tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_retired_charter_vocabulary.py -q
```
