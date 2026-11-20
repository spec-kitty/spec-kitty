# Contract: per-key precedence

For a Mission of type `T` and a key `k` the Mission declares in `paths:`:

1. `k` is artifact-routed (`deliverables`) → the mission default (never overridable).
2. `project.path_conventions.T.k` is set → that value.
3. `project.path_conventions.k` is set → that value.
4. Otherwise → the mission default `mission.config.paths[k]`.

Then, unchanged from #3783:
- a value colliding with a Mission artifact token is dropped with a warning;
- research `path_prefix` is applied after the remap;
- the absence decision: strict → blocking `path_violations`; `--lenient`, the per-run waiver or a well-formed `meta.json` waiver → an advisory warning. Metadata strictness follows `--lenient` only.

`T` is `meta.json` `mission_type`, defaulting to `software-dev`, which is the same value the Mission was loaded from.
