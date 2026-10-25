# Quickstart: verifying the residue-safe migration sweep

## Reproduce the P0 and see it fixed

```bash
# On main (before the fix) the reproduction is red; it runs only with the nightly flag:
SPEC_KITTY_RUN_P0_REPRO=1 uv run --frozen pytest tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py -q
# On this Mission's branch (marker removed, five leftover shapes) it is a per-PR guard:
uv run --frozen pytest tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py tests/integration/migration/test_upgrade_residue_identity_6627.py -q
```

## By hand

```bash
mkdir -p /tmp/demo && cd /tmp/demo && git init -q -b main
mkdir -p .kittify kitty-specs/real-01REALMIS && echo '{"mission_id":"01REALMISZZZZZZZZZZZZZZZZZ"}' > kitty-specs/real-01REALMIS/meta.json
git add -A && git commit -qm init
mkdir -p kitty-specs/my-mission-01M5JYRC/tasks && printf -- '---\nlane: doing\n---\n' > kitty-specs/my-mission-01M5JYRC/tasks/WP01-x.md
spec-kitty upgrade --yes      # one residue notice for my-mission-01M5JYRC; nothing written there
git status --short            # only the untracked leftover remains
```

## Check the doctor finding

```bash
spec-kitty doctor mission-state --audit --json | python -c "import json,sys; d=json.load(sys.stdin); print([f for m in d['missions'] for f in m['findings'] if f['code']=='FABRICATED_IDENTITY_SUSPECTED'])"
```

## Check the shipped migrations are untouched

```bash
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'   # must print nothing
```
