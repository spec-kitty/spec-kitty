---
name: spec-kitty.status
description: Show mission and work package status
user-invocable: true
---

## Startup Upgrade Check

Run this at most once per active agent session before the first Spec Kitty command workflow.
If you already ran `spec-kitty upgrade --agent-check --json` in this session, reuse that result and skip this block.
Do not run or announce an upgrade check again for later Spec Kitty commands in the same session.
Otherwise, before continuing, run:

```bash
spec-kitty upgrade --agent-check --json
```

If JSON `action` is `none`, continue.
If `action` is `auto_upgrade`, run `upgrade_command` before continuing. If it fails, tell the user and continue with the current Spec Kitty version.
If `action` is `guidance`, show `upgrade_note` briefly, then continue.
If `action` is `prompt`, ask the user with the host-native question UI when available:

`Spec Kitty {latest_version} is available. You are on {installed_version}. Upgrade now?`

Use these choices:

1. Upgrade now (recommended) - record `upgrade_now`, run `upgrade_command`, then continue.
2. Always keep me up to date - record `always`, run `upgrade_command`, then continue.
3. Not now - record `not_now`, then continue.
4. Never ask again - record `never_ask`, then continue.

Record the selected choice before continuing:

```bash
spec-kitty upgrade --agent-choice <upgrade_now|always|not_now|never_ask> --agent-latest <latest_version> --json
```

If no host-native question UI is available, present the same four choices in plain text and wait for the user.
In non-interactive hosts, choose `not_now` and continue.


# /spec-kitty.status - Show mission and work package status

## Purpose

Run the canonical Spec Kitty CLI command for this workflow and treat its output as authoritative.

Do not rediscover mission context from branches, files, prompt contents, or separate charter loads. If mission selection is required, pass `--mission <handle>` where `<handle>` is a mission_id, mid8, or mission_slug.

## User Input

The content of the user's message that invoked this skill is the User Input. Consider it before proceeding. If it contains CLI arguments, append them to the command below.

## Steps

Run this command from the repository root:

```bash
spec-kitty agent tasks status <user-provided-args-if-any>
```

Report the command output and follow any next-step instructions it prints.
