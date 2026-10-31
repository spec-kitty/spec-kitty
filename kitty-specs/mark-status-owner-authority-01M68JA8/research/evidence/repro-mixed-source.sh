#!/bin/bash
set -u
SK=/home/exedev/work/sk-6463/.venv/bin/spec-kitty
D=/tmp/r6463/f2
rm -rf $D; mkdir -p $D/kitty-specs/001-repro/tasks $D/.kittify
(cd $D && git init -q -b main . 2>/dev/null)
printf 'version: 1\n' > $D/.kittify/config.yaml
printf '{"mission_id": "01TESTMISSION6463", "mission_slug": "001-repro", "mission_type": "software-dev", "status_phase": "1"}\n' > $D/kitty-specs/001-repro/meta.json
cat > $D/kitty-specs/001-repro/tasks.md <<'EOF'
# Tasks

## WP01
Subtasks: T001

## WP02
Subtasks: T001
EOF
printf -- "---\nwork_package_id: WP01\ntitle: WP01\nsubtasks: [T001]\n---\n# WP01\n" > $D/kitty-specs/001-repro/tasks/WP01-a.md
printf -- "---\nwork_package_id: WP02\ntitle: WP02\n---\n# WP02\n" > $D/kitty-specs/001-repro/tasks/WP02-b.md
(cd $D && git add -A >/dev/null && git -c user.email=a@b -c user.name=t commit -qm init)
echo "--- unscoped T001 (WP02 is the legacy WP that claims it in tasks.md)"
(cd $D && timeout 120 "$SK" agent tasks mark-status T001 --status done --mission 001-repro --json --no-auto-commit 2>&1 | tail -2)
echo "events:"; cat $D/kitty-specs/001-repro/status.events.jsonl 2>/dev/null | python3 -c 'import sys,json
for l in sys.stdin:
  l=l.strip()
  if l: r=json.loads(l); print("  wp:",r.get("wp_id"),r.get("delta",{}).get("subtasks"))'
