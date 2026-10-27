# Quickstart: verify the mission by hand

```bash
mkdir /tmp/qs && cd /tmp/qs && git init -q && mkdir .kittify && echo 'charter_packs: {}' > .kittify/config.yaml
spec-kitty charter activate --no-compile mission-type software-dev --only
# expect: "Activated: software-dev", "Now listed for mission-type (1): software-dev",
#         "No longer in force (0): (none)", and no "initialized from" / "could not be resolved" warning
```

Skill (needs an org pack with `required_skills`): `spec-kitty charter activate skill <id>` on an absent key and
`... --only` both print the org-required freeze warning; neither recommends `--only`.
