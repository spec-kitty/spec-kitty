# spec-kitty standalone invocation

This host should read Spec Kitty's canonical standalone-invocation skill pack at:

**`src/charter/offering/skills/spec-kitty/SKILL.md`**

That file teaches:
- When to call `spec-kitty dispatch "<request>"` for standalone governed work.
- How to read `governance_context_text` from the response and inject it as binding governance context.
- That `spec-kitty dispatch` only OPENS the Op — after doing the work, the agent
  MUST close it with the real outcome:
  `spec-kitty profile-invocation complete --invocation-id <id> --outcome <done|failed|abandoned>`.
  Failed work closes as `failed`; `spec-kitty doctor ops` reports and sweeps orphans.

LLxprt Code loads the same TOML custom-command schema as Gemini CLI, so this
pointer stands alongside the `/spec-kitty.*` mission-step commands rendered for
the `gemini` command surface. Use them for standalone invocations that are not
part of a running mission workflow.
