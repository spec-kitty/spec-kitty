---
name: adversarial-squad
description: >-
  Deploy a bounded, profile-loaded adversarial review squad at a mission point-cut
  so independent doctrine lenses converge on findings one reviewer would miss.
  Triggers: "deploy a squad", "adversarial squad", "post-tasks anti-laziness pass",
  "pre-spec investigation squad", "brownfield check", "second opinion on this design",
  "review squad", "run a multi-lens review".
  Does NOT handle: the implement-review loop (use spec-kitty-implement-review),
  spec/plan/tasks generation, or direct code editing by the orchestrator. It is an
  optional, charter/memory-activated enrichment — it never gates a mission.
---

# Adversarial Squad Deployment (harness)

The operational alias for the doctrine procedure `adversarial-squad-deployment`
(`packs/built-in/procedures/adversarial-squad-deployment.procedure.yaml`), which is
the single owner of when, who, and how to run a squad. This skill changes **no**
mission type or guard; it is a technique the orchestrator opts into.

## Load the procedure

Before dispatching, load the procedure's full playbook:

```
spec-kitty charter context --include procedure:adversarial-squad-deployment
```

Apply its point-cut list, casting rule, dispatch discipline, model-tier routing,
synthesis step, and findings-disposition contract as written there — this skill
does not restate them.

## Invocation

Invoke by name (`adversarial-squad`) with the point-cut + question, e.g.
*"adversarial-squad: post-tasks anti-laziness on WP01–WP08."* This skill is the alias
surface; the doctrine procedure is the canonical record of the technique.
