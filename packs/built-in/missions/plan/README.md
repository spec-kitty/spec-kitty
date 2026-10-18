# Plan Mission

Mission type for standalone planning workflows that produce structured plans without
necessarily proceeding to implementation.

## Runtime DAG (v1.0.0)

4 sequential steps: specify → research → plan → review. The planner profile handles
the plan step; the reviewer profile handles review.

## Contents

- `mission.yaml` — Mission identity and its step list
- `mission-runtime.yaml` — Runtime DAG with step ordering
- `command-templates/` — Prompt files for plan, research, review, specify
