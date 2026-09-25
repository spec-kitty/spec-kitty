#!/usr/bin/env bash
set -euo pipefail
SRC="${SPK_QA_SOURCE:?Set SPK_QA_SOURCE to the spec-kitty source checkout}"
SK="$SRC/.venv/bin/spec-kitty"; PY="$SRC/.venv/bin/python"
BASE="${1:-$(mktemp -d)}"; mkdir -p "$BASE"; BASE="$(cd "$BASE" && pwd)"
TOPO="${TOPO:-single_branch}"
summ() { $PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(sys.argv[2],"rc="+sys.argv[3],"kind="+str(d.get("kind")),"state="+str(d.get("mission_state")),"action="+str(d.get("action")),"wp="+str(d.get("wp_id")))' "$@"; }
arm() { local name="$1" root="$BASE/$1"; rm -rf "$root"; mkdir -p "$root/repo"
 (
  export HOME="$root/home" XDG_CONFIG_HOME="$root/xc" XDG_CACHE_HOME="$root/xcache" XDG_DATA_HOME="$root/xd"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
  export SPEC_KITTY_NO_UPGRADE_CHECK=1 SPEC_KITTY_WORKTREE_REMOVAL_DELAY=0 SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1
  export PATH="$SRC/.venv/bin:$PATH"
  git config --global user.name QA; git config --global user.email qa@example.invalid; git config --global commit.gpgsign false
  cd "$root/repo"; git init -q -b main
  timeout 300 "$SK" init --ai claude --non-interactive > "$root/init.log" 2>&1
  git add -A; git commit -qm init
  timeout 300 "$SK" agent mission create rq --mission-type software-dev --topology "$TOPO" --branch-strategy already-confirmed \
    --target-branch main --friendly-name 'Review QA' --purpose-tldr 'review QA' --purpose-context 'Isolated QA fixture.' --json > "$root/create.json" 2>"$root/create.err"
  SLUG="$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["mission_slug"])' "$root/create.json")"; FD="kitty-specs/$SLUG"
  printf '# Spec\n\n## Requirements\n\n- **FR-001**: one works.\n' > "$FD/spec.md"
  printf '# Plan\n\nOne module.\n' > "$FD/plan.md"
  printf '# Tasks\n\n## Work Package WP01: one\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n' > "$FD/tasks.md"
  mkdir -p "$FD/tasks"
  printf -- '---\nwork_package_id: WP01\ntitle: WP01 work\ndependencies: []\nrequirement_refs: [FR-001]\nauthoritative_surface: src/one/\nowned_files:\n  - src/one/**\nsubtasks:\n  - TWP01\n---\n# WP01\n\n- [ ] TWP01 do one\n' > "$FD/tasks/WP01-work.md"
  git add -A; git commit -qm planning
  timeout 300 "$SK" agent mission finalize-tasks --mission "$SLUG" --json > "$root/finalize.json" 2>&1
  printf '# Analysis\n\nNo blocking findings.\n' > "$root/analysis.md"
  timeout 300 "$SK" agent mission record-analysis --mission "$SLUG" --input-file "$root/analysis.md" > "$root/ra.log" 2>&1 || true
  bk() { git add -A; git commit -qm "loop bookkeeping" -q 2>/dev/null || true; }
  adv() { set +e; timeout 300 "$SK" next --agent claude --mission "$SLUG" --result success --json > "$root/next-$1.json" 2>"$root/next-$1.err"; local rc=$?; set -e
          summ "$root/next-$1.json" "$name advancing next [$1]" "$rc"; bk; }
  for i in 1 2 3 4 5; do adv "p$i" | grep 'action=implement' && break || true; done
  timeout 300 "$SK" agent action implement WP01 --mission "$SLUG" --agent claude > "$root/impl.log" 2>&1
  WT="$(git worktree list --porcelain | awk '/^worktree .*-lane-a$/{print $2}')"
  mkdir -p "$WT/src/one"; echo one > "$WT/src/one/a.txt"; git -C "$WT" add -A; git -C "$WT" commit -qm "WP01 work"; bk
  (cd "$WT" && timeout 300 "$SK" agent tasks mark-status TWP01 --status done --mission "$SLUG" >/dev/null 2>&1); bk
  (cd "$WT" && timeout 300 "$SK" agent tasks move-task WP01 --to for_review --mission "$SLUG" --note ready > "$root/fr.log" 2>&1); bk
  printf 'Missing tests for FR-001.\n' > "$root/feedback.md"
  if [ "$name" = early ]; then
    timeout 300 "$SK" agent tasks move-task WP01 --to planned --review-feedback-file "$root/feedback.md" --mission "$SLUG" > "$root/verdict.log" 2>&1; echo "$name: reject rc=$? (before the loop picked up the review)"; bk
  else
    adv r0
    P="$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["prompt_file"])' "$root/next-r0.json")"; grep -E '^\s+(APPROVE|REJECT):' "$P" | sed "s/^/$name: review prompt says /"
    if [ "$name" = bug ]; then
      timeout 300 "$SK" agent tasks move-task WP01 --to planned --review-feedback-file "$root/feedback.md" --mission "$SLUG" > "$root/verdict.log" 2>&1; echo "$name: reject rc=$?"
    else
      timeout 300 "$SK" agent tasks move-task WP01 --to approved --mission "$SLUG" --note "Review passed" > "$root/verdict.log" 2>&1; echo "$name: approve rc=$?"
    fi; bk
  fi
  echo "$name: WP01 lane after verdict: $($PY -c 'import json,sys
st=None
for l in open(sys.argv[1]):
    l=l.strip()
    if l:
        e=json.loads(l)
        if e.get("wp_id")=="WP01" and e.get("to_lane"): st=e["to_lane"]
print(st)' "$FD/status.events.jsonl")"
  set +e; timeout 300 "$SK" next --mission "$SLUG" --json > "$root/query.json" 2>/dev/null; rc=$?; set -e; summ "$root/query.json" "$name query next" "$rc"
  for i in 1 2 3; do adv "a$i"; done
  P="$($PY -c 'import json,sys;print(json.load(open(sys.argv[1])).get("prompt_file") or "")' "$root/next-a3.json")"
  if [ -n "$P" ]; then echo "$name: last prompt file content (first 6 lines):"; head -6 "$P" | sed 's/^/    | /'; fi; true
 ) 2>&1 | tee "$BASE/$name.txt"; }
arm bug; arm approve; arm early
echo "================ verdict"
if grep -q "bug advancing next \[a3\] rc=0 kind=step state=review action=review wp=None" "$BASE/bug.txt" \
   && grep -q "bug query next rc=0 kind=query state=implement action=None wp=WP01" "$BASE/bug.txt" \
   && grep -q "early advancing next \[a1\] rc=0 kind=step state=implement action=implement wp=WP01" "$BASE/early.txt" \
   && grep -Eq "approve advancing next \[a(1|2)\] rc=0 kind=terminal" "$BASE/approve.txt"; then
  echo "CONFIRMED: after a review-step rejection the loop spins on a WP-less placeholder review step (exit 0); controls behave"
else echo "NOT REPRODUCED (see $BASE/*.txt)"; fi
