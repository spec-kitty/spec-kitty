# Design decisions

- Two layers: committed block (deterministic, every clone) + clone-local exclude (per clone). Option (b) rejected because a committed block that depends on local files flips between clones.
- `config.toml` is left out of the committed block (team config in a plain project folder) and covered by the clone-local exclude when `.codex/` is a Codex home.
- Review cycle 1: the agent-folder notice became its own clone-local step, so the Codex home exclusion settles only after it excludes one (a clone that gets a Codex home later is still protected). The exclusion rule is anchored at the project (`/<prefix>.codex/`), so a sibling project's team `.codex/` stays visible.
