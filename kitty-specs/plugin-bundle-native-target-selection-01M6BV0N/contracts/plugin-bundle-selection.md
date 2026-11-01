# Contract — plugin bundle target-native selection and repair reporting

Status: active for mission `plugin-bundle-native-target-selection-01M6BV0N` (#6273).

## Selection

1. Each distribution target declares an ordered list of accepted tool keys for every per-harness
   rendered kind (`AGENT_PROFILE`, `COMMAND_SKILL`, `CHARTER_SKILL`). Index = preference rank.
2. For one bundle member, the lowest-rank accepted source wins; sources with a higher rank for that
   member are dropped before preparation and are not read.
3. Sources of equal rank merge as today; if their bytes differ the assessment is incomplete with
   `Conflicting prepared bundle member: <member>` and **no file is written**. A source that is the
   same physical path as an already-selected member only adds its ownership claim.
4. A source absent from the accept-list is never a candidate, so a Codex `.toml` profile can neither
   collide with nor be renamed into a Markdown agent member.
5. An agent member is named from its own native suffix (`.agent.md` before `.md`), so a Copilot
   profile stages as `agents/<id>.agent.md`, not `<id>.agent.agent.md`.
6. Non-rendered surface kinds (`HOOK`, `NATIVE_CONFIG`) are unaffected by the accept-list.

## Diagnostics

1. `PluginBundleProvider.probe` keeps the assessment cause when a staged bundle exists but no longer
   matches its prepared batch; the finding message includes the provider diagnostic.
2. `SurfaceRepairService.repair` returns the providers' `findings_after` in `RepairResult`.
3. `doctor tool-surfaces --fix` prints every failed surface id and its reason, and exits 1.
4. A successful `--fix` prints `Repaired: N surface(s)` and exits 0.
5. The audit-only path is unchanged: a missing OPTIONAL plugin manifest does not flip `ok` and does
   not change the exit code.
