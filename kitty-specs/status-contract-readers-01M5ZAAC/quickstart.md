# Quickstart: verify the structured actor

```bash
# On a Mission whose WP01 declares agent_profile: python-pedro
spec-kitty agent tasks mark-status T001 --status done --mission <handle>
spec-kitty agent tasks move-task WP01 --to for_review --agent claude --mission <handle>
spec-kitty agent tasks move-task WP01 --to approved --agent claude-reviewer --profile reviewer-renata --mission <handle>

tail -n 4 kitty-specs/<mission>/status.events.jsonl | python -c 'import sys,json;[print(json.loads(l)["actor"]) for l in sys.stdin]'
# {'tool': 'user', 'role': 'implementer', 'profile': 'python-pedro', 'profile_source': 'wp_frontmatter', 'model': None}
# {'tool': 'claude', 'role': 'implementer', 'profile': 'python-pedro', 'profile_source': 'wp_frontmatter', 'model': None}
# ...
# {'tool': 'claude-reviewer', 'role': 'reviewer', 'profile': 'reviewer-renata', 'profile_source': 'flag', 'model': None}

python -c 'from specify_cli.status_lanes import CANONICAL_LANES, PACKAGE_LANES; print(PACKAGE_LANES, CANONICAL_LANES)'
```
