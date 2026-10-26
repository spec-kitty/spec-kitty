#!/usr/bin/env bash
# Shell port of governance-in-force.feature PR-CHARTER-GOVERNANCE-002 fixture (#6417).
# usage: repro.sh <dir> <variant: old|fixed> [nodeid]
set -e
D="$1"; V="${2:-old}"; NODE="${3:-team-rule}"
rm -rf "$D" && mkdir -p "$D" && cd "$D"
git init -q -b main . && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m init
spec-kitty init --non-interactive --ai claude >/dev/null 2>&1
git add -A && git commit -qm setup
spec-kitty charter interview --defaults --profile minimal --json >/dev/null
spec-kitty charter generate --from-interview >/dev/null
P=.kittify/team-pack
if [ "$V" = old ]; then DIR=directive; BODY='schema_version: "1.0"\nid: team-rule\ntitle: Team rule\nscope: docs\nbody: >\n  the team-wide default\n';
else DIR=directives; BODY='schema_version: "1.0"\nid: TEAM_RULE\ntitle: Team rule\nintent: >\n  the team-wide default\nenforcement: required\nscope: docs\n'; fi
mkdir -p $P/drg $P/$DIR
printf 'pack_id: 01M4P01D5TWB5FKZGNNQG3900A\nparent_pack: null\nname: team-pack\npack_level: org\nactive_charter: org-charter.yaml\npack_drg: drg/fragment.yaml\n' > $P/pack.yaml
printf 'org_name: team\nskill_namespace: team\nrequired_directives:\n  - team-rule\n' > $P/org-charter.yaml
printf "pack_name: team-pack\nsource_kind: local_path\nsource_ref: .kittify/team-pack\nlayer_index: 1\nprovenance_marker: org\nnodes:\n  - id: $NODE\n    kind: directives\n    title: Team rule\n    body_path: $DIR/team-rule.directive.yaml\n" > $P/drg/fragment.yaml
printf "$BODY" > $P/$DIR/team-rule.directive.yaml
grep -q charter_packs: .kittify/config.yaml || printf '\ncharter_packs:\n  org:\n    packs:\n    - name: team-pack\n      local_path: .kittify/team-pack\n' >> .kittify/config.yaml
spec-kitty charter synthesize --json >/dev/null
echo "== charter list"; spec-kitty charter list 2>&1 | grep -E "directive |team" || true
echo "== context"; spec-kitty charter context --action implement 2>&1 | grep -i team || true
set +e; spec-kitty doctor charter-packs >/dev/null 2>&1; echo "doctor exit=$?"
