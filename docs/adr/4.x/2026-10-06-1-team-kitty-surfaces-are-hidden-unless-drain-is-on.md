---
title: 'ADR: the Team Kitty surfaces are hidden unless hosted drain is on'
description: 'Team Kitty is no longer supported: the spk-team-* skills are retired and its six CLI entries are hidden from listings unless the hosted drain posture is on.'
status: Accepted
date: '2026-10-06'
updated: '2026-10-06'
---

**Status:** Accepted

**Date:** 2026-10-06

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** the 4.0.0 [direction amendment](../../changelog/4.0.0.md) (2026-10-01) froze Team Kitty / SaaS work; this record takes the step from "frozen" to "no longer actively supported" for the surfaces the CLI ships.

**Reader:** a maintainer changing the root command registration, the shipped skill pack, the generated CLI reference, or anything under the hosted drain posture.

---

## Context and Problem Statement

Team Kitty is the hosted collaboration product: the SaaS authenticates a team member and mints a capability, and the CLI publishes each status moment to the team's Zeitgeist relay. Since 2026-10-01 nothing hosted gates 4.0.0 GA. This record ends active support.

Hosted interaction is already off by default ([ADR 2026-09-26-3](../3.x/2026-09-26-3-hosted-interaction-opt-in.md)), behind two gates. Moments, Live Work and the relay commands need the drain posture (`specify_cli.core.hosted_posture`): `hosted.drain` in the repository's `.kittify/config.yaml` and `[hosted] drain` in the personal `config.toml` must both be true, and no environment variable can turn it on. Authentication and the SaaS-backed tracker calls need a configured endpoint (`SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url`, `specify_cli.auth.server_target`). Neither ships configured.

What still pointed at Team Kitty was the guidance:

- Four shipped skills, `spk-team-auth`, `spk-team-sync`, `spk-team-tracker` and `spk-team-connectors`, were installed into every configured agent's skill root. `spk-start-here` routed "team, SaaS, tracker, or sync" questions to them, and three of them told the agent that hosted mode "is already on" and explained the residue variable `SPEC_KITTY_ENABLE_SAAS_SYNC`, which does not gate the moment path.
- Six top-level CLI entries that only serve the hosted surface were listed in `spec-kitty --help`, in shell completion and in the generated CLI reference: `auth`, `issue-search`, `live-work`, `moments`, `routes` and `zeitgeist`.

A user or an agent harness reading either surface was steered toward an offering that is not supported.

## Decision

1. **The four `spk-team-*` skills are retired.** Their sources are deleted and their names join `RETIRED_CANONICAL_SKILL_NAMES` (`specify_cli.skills.retired`), so the existing installers remove the copies Spec Kitty installed and preserve any unproven custom skill. The skill-selection lines that named them are removed.
2. **The six hosted entries register hidden.** `register_commands` marks every entry named in `_HOSTED_SURFACE_NAMES` hidden on the full and the single-command registration paths. The `next` and `live-work hook` fast paths skip it; neither renders the root listing. Each one still runs when invoked by name, so a script or an operator who knows the command is not broken.
3. **They are listed again only when drain is on.** `reveal_hosted_surfaces`, called from the CLI entry point's app assembly, unhides them when `hosted_posture.drain_posture()` is enabled for the current checkout. It reads the posture only when argv does not resolve to one top-level command, because only the root listing reads the flag; a normal command invocation pays no extra config read. An unparseable posture file is treated as off, as the hosted edges treat it, and its warning is not printed on the root listing.
4. **Generated artifacts describe the default posture.** The completion manifest and `docs/api/cli-commands.md` are built from the registration tree without the reveal, so they are deterministic and record the six entries as hidden whatever the generating machine's drain posture is. The CLI reference walker (`scripts/docs/_typer_walker.py`) now counts a path under a hidden group as hidden, since `--help` never lists it.
5. **`tracker` stays visible.** It also serves the local providers (`beads`, `fp`), which need no SaaS. Its help no longer sends SaaS-backed providers to `auth login`; it says they need a Team Kitty sign-in, which is not supported.

## Considered Options

1. **Gate visibility on the drain posture (chosen).** Drain is the opt-in for the moment and relay edges, it is off by default and no environment variable can enable it, so the default listing is clean and a checkout that opted in still sees what it opted into. The endpoint opt-in that gates `auth` is weaker, because an environment variable can supply it.
2. **Gate visibility on `SPEC_KITTY_ENABLE_SAAS_SYNC`.** Rejected. It is residue of the retired sync transport and defaults to on since the #3980 launch defaults, so the surfaces would stay listed for everyone.
3. **Hide unconditionally.** Rejected. An operator who turned drain on deliberately would lose discoverability of the commands that drive it.
4. **Remove the hosted command groups.** Rejected for now. The relay client and the moment path are still wired to the status pipeline behind the drain gate, and removing the commands is a larger change than the support decision requires.

## Consequences

- With the default posture, `spec-kitty --help`, shell completion and the CLI reference no longer offer the hosted entries; an agent loading the shipped skills is no longer routed to Team Kitty.
- The reveal depends on the live posture, so with drain on the root listing shows the six entries while completion (served from the committed manifest) does not. Completion describes the default posture by design.
- Children of groups that were already hidden (for example the deprecated `doctrine` group) leave the main CLI reference body too. That is the walker rule from point 4 applied to every hidden group, not only the hosted ones.
- The visible-path baseline in `tests/docs/test_check_cli_reference_freshness.py` drops from 310 to 252.
- In the charter, the SaaS Docker-mode rules bind only requested hosted work, and the CLI-to-SaaS contract section says no new hosted work starts unasked; a change to the hosted wire surface still updates the contract.
- `docs/context/team-kitty.md` and the 4.0.0 declaration carry the support status.
- Remediation messages on hosted-only paths still name `spec-kitty auth login`, which still runs by name. This is deliberate: a user who reaches a hosted path needs the real command. The sites are `_saas_error_hint` and the `tracker` authentication message (~759) in `src/specify_cli/cli/commands/tracker.py`, `_AUTH_LOGIN_REMEDIATION` in `src/specify_cli/readiness/render.py`, and the missing-auth remedy in `src/specify_cli/tracker/saas_readiness.py` (~85).
- Reversible: removing a name from `_HOSTED_SURFACE_NAMES` and from the retired-skill set, and restoring the skill sources, brings a surface back.
