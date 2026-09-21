---
work_package_id: WP04
title: WS provisioning guard (defence-in-depth)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-001
- NFR-006
planning_base_branch: issue-4755-token-target-issuer-guard
merge_target_branch: issue-4755-token-target-issuer-guard
branch_strategy: Planning artifacts for this mission were generated on issue-4755-token-target-issuer-guard. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4755-token-target-issuer-guard unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-token-target-issuer-guard-01M319HS
base_commit: 3895b8083257a74cfe77f0e1e4d7d9897eda758c
created_at: '2026-09-21T07:12:03.662223+00:00'
subtasks:
- T015
- T016
- T017
history:
- Created by /spec-kitty.tasks (#4755)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/auth/websocket/
create_intent:
- tests/auth/test_ws_provisioning_issuer.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/auth/websocket/token_provisioning.py
- tests/auth/test_ws_provisioning_issuer.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile before anything else: `/ad-hoc-profile-load python-pedro`. Adopt its identity,
boundaries, and governance scope for this work package.

## Objective

Close the dormant WebSocket-token-provisioning leak (Path 4) as defence-in-depth: route
`/api/v1/ws-token` to the session's issuer or refuse. This path has no caller today (the WP08 sync
client died with the sync transport), so it is verified by **direct invocation**, not an integration
reproduction.

## Context

Read: `contracts/issuer-target-helper.md`. Current leak:
- `auth/websocket/token_provisioning.py:110` — `saas_url = get_saas_base_url()` → `:111`
  `/api/v1/ws-token` → `:112-113` `Authorization: Bearer {access_token}`. Also does a pre-connect
  refresh via `tm.refresh_if_needed()` (`:108`) which routes through the (WP02-guarded) refresh path.

### T015 — Guard before the send
- In `WebSocketTokenProvisioner.provision`, resolve the endpoint via `resolve_token_endpoint(session)`
  and guard **before** building the URL (`:110`) and before `get_access_token` (`:112`). On a mismatch
  (or split-brain), raise `WebSocketProvisioningError` wrapping the shared decision's remedy — so the
  refusal reaches the WS caller and blocks the ws_token POST. Remove the `get_saas_base_url()` call.
- Obtain the `session` from `tm.get_current_session()` (already fetched at `:100` for the pre-connect
  refresh check); reuse it.

### T016 — Direct-invocation tests
- `tests/auth/test_ws_provisioning_issuer.py`: mismatch → `WebSocketProvisioningError` (token-free
  message, NFR-006); issuer == target → provisions against the issuer host (existing behaviour
  unchanged); legacy `issuer_url = None` → routes to the resolved target, no raise.

### T017 — Chained pre-connect-refresh propagation
- Assert that when the nested `tm.refresh_if_needed()` (`:108`) raises the mismatch refusal, it
  propagates out of `provision()` rather than being swallowed (the method has no bare-except around it) —
  a chained-path guard so the ws flow can't leak via its inner refresh.
- **Keep this WP WP01-only**: do NOT depend on WP02's boundary-guard implementation. Monkeypatch
  `tm.refresh_if_needed` to raise `IssuerTargetMismatchError` and assert `provision()` re-raises it
  (verifying only that `provision` has no swallowing `except`). This tests the propagation contract, not
  WP02's refresh internals, so WP04 can run in parallel with WP02.

## Branch Strategy
Planning base + local merge target: `issue-4755-token-target-issuer-guard`. Execution worktree is the
per-lane worktree from `lanes.json` via `spec-kitty implement WP04`. Depends on WP01.

## Definition of Done
- `token_provisioning.py` no longer calls `get_saas_base_url()`; mismatch → `WebSocketProvisioningError`
  (token-free); happy path + legacy path covered by T016; chained refusal covered by T017.
- `ruff`/`ruff format`/`mypy` clean; complexity ≤ 15; new branches covered in the same commit.

## Risks
- **Dormant ≠ ignorable** — a future resurrection would re-leak; fix it now, but note in review it is not
  a live exploit path.

## Reviewer guidance (reviewer-renata)
Confirm the guard precedes both the URL build and `get_access_token`, the error is token-free, and the
nested-refresh refusal propagates.
