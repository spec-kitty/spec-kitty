# Design decisions

- Two layers: committed block (deterministic, every clone) + clone-local exclude (per clone). Option (b) rejected because a committed block that depends on local files flips between clones.
- `config.toml` is left out of the committed block (team config in a plain project folder) and covered by the clone-local exclude when `.codex/` is a Codex home.
