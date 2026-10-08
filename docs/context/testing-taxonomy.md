---
title: 'Context: Testing Taxonomy'
description: 'Glossary context for the testing taxonomy: the canonical pytest-marker categories for the tests/ tree and how to choose markers for a new test file.'
doc_status: active
updated: '2026-10-08'
---
## Context: Testing Taxonomy

Canonical categories for tests in this project's `tests/` tree. Each category is a pytest marker declared in `pytest.ini` `[pytest] markers`. Every test file MUST declare a module-level `pytestmark = [pytest.mark.<name>]` carrying at least one of these markers (architectural convention enforced by `tests/architectural/test_pytest_marker_convention.py`). CI quality gates and developer-loop profiles select tests by marker (`uv run pytest -m fast`, `-m architectural`, `-m "contract or unit"`, …), so an untagged test is silently invisible to those filters.

When choosing a marker for a new test file:

1. **Start at the category that best describes what kind of *behavior* the test asserts** (unit, integration, contract, architectural, e2e).
2. **Add orthogonal markers** if the test additionally has a property the category alone does not capture (`slow`, `git_repo`, `requires_symlinks`, `platform_linux`, `windows_ci`, …). Multiple markers per file are encouraged when they each carry information.
3. **Never leave a test file untagged.** If the test is for human-driven exploration only, mark it `exploratory` so CI's `-m "not exploratory"` filter excludes it.

The categories below are listed by the question they answer.

---

### Unit

| | |
|---|---|
| **Definition** | A test that asserts the behavior of a single module in isolation. No subprocess invocation, no real filesystem writes beyond `tmp_path`, no network, no real git. Helper modules may be imported, but third-party services and shell commands are off-limits. |
| **Use when** | Testing a pure function, a Pydantic model, a parser, a state-machine transition, or any module whose contract can be exercised by direct calls with synthetic inputs. |
| **Do NOT use when** | The test spawns `git`, hits HTTP, drives the CLI through `typer.testing.CliRunner`, or relies on a real `.kittify/` tree it built itself. Use `integration` instead. |
| **CI role** | Default profile for the developer loop. `-m unit` is the fastest meaningful filter and should turn green in seconds. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Fast](#fast), [Integration](#integration) |

---

### Integration

| | |
|---|---|
| **Definition** | A test that exercises a feature across module boundaries against real (process-local) collaborators: real filesystem under `tmp_path`, real in-process I/O, real git when explicitly needed. No external network, no spawned long-running services. |
| **Use when** | The test verifies that two or more modules compose correctly, that a CLI command produces the expected files on disk via `typer.testing.CliRunner`, that a sync pipeline writes the right rows to a tmp SQLite DB, or that a charter resolver loads real YAML from a real `.kittify/`. |
| **Do NOT use when** | The test only inspects a function's return value (use `unit`); the test calls a real external network (use `e2e` or `live_adapter`); the test runs against a real git repo with subprocess calls (also add `git_repo`). |
| **CI role** | Run in the standard PR gate. Slower than `unit` but still bounded by file/process latency, not network. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Unit](#unit), [E2E](#e2e), [Git Repo](#git-repo) |

---

### Contract

| | |
|---|---|
| **Definition** | A consumer-surface test that pins the shape of an external public API this project depends on (currently `spec-kitty-events` and `spec-kitty-tracker` PyPI packages, and the SaaS HTTP contract). The test fails when an upstream contract changes in a way that would break this CLI's consumption. |
| **Use when** | You are asserting that a serialized event envelope matches a published schema, that a tracker bind payload carries the right keys, or that a vendored fixture from `contracts/` validates against a Pydantic model from `spec_kitty_events`. |
| **Do NOT use when** | The test exercises *internal* CLI-only behavior with no external contract — that is `unit` or `integration`. The test exercises a runtime end-to-end flow — that is `e2e`. |
| **CI role** | Always green; a contract failure is by definition a blocking upstream regression. Run as a dedicated CI gate (`-m contract`). |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Integration](#integration), [E2E](#e2e) |

---

### Architectural

| | |
|---|---|
| **Definition** | A test that asserts an architectural invariant — layer dependency rules (via pytestarch), import-boundary scans, shared-package boundary, naming conventions, schema enforcement, "this directory may not import that subsystem", "every test file must declare a marker", etc. These tests do not run product code; they introspect the source tree. |
| **Use when** | You are pinning a rule about the structure of the codebase, not the behavior of any single module. |
| **Do NOT use when** | The test calls product code (that is `unit` or `integration`). The test only verifies an external contract (that is `contract`). |
| **CI role** | Dedicated CI gate (`-m architectural`). These tests are the rule book for refactors. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Contract](#contract) |

---

### E2E

| | |
|---|---|
| **Definition** | An end-to-end test that drives the full CLI as a subprocess (or via `typer.testing.CliRunner` with maximum integration depth), against a realistic `.kittify/` tree, and asserts the user-visible outcome (files produced, exit code, observable side-effects). May be slow. |
| **Use when** | You are verifying a whole user journey — `spec-kitty specify` → `plan` → `tasks` → `implement` → `review` — or a multi-command flow that no single module owns. |
| **Do NOT use when** | A single CLI invocation in-process is sufficient — that is usually `integration`. |
| **CI role** | Run in a dedicated slow gate (`-m e2e`). Often paired with `-m slow` when wall-clock exceeds the slow threshold. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Integration](#integration), [Slow](#slow) |

---

### Adversarial

| | |
|---|---|
| **Definition** | A security or fuzz-style test that asserts the system rejects malicious or malformed inputs (CSV formula injection, path traversal, malformed YAML, oversized payloads, etc.) without crashing or leaking. |
| **Use when** | The test feeds hostile input to a parser, validator, file reader, or network handler and verifies safe rejection or sanitization. |
| **Do NOT use when** | The test verifies normal happy-path validation — that is `unit` or `integration`. |
| **CI role** | Run alongside the regression suite; a failure indicates a real security regression. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Contract](#contract) |

---

### Doctrine

| | |
|---|---|
| **Definition** | A smoke or integration test against the charter offering package — verifying that directives, tactics, paradigms, styleguides, toolguides, procedures, agent profiles, and mission step contracts load correctly from `src/charter/offering/`, merge across layers (built-in / org / project), and surface through `CharterOfferingService`. |
| **Use when** | The test exercises the three-layer charter offering, the DRG (doctrine reference graph) loader, profile resolution, or the offering catalog. |
| **Do NOT use when** | The test is for charter-side composition (use `unit` and let the file live under `tests/charter/`) or for a single doctrine helper function (use `unit`). |
| **CI role** | Dedicated `-m doctrine` profile for fast feedback on doctrine drift. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Unit](#unit), [Integration](#integration) |

---

### Fast

| | |
|---|---|
| **Definition** | A performance characterization, not a behavioral category. The marker declares the test runs in well under a second per item, performs no subprocess work, no git, no network, and no heavy fixture setup. Orthogonal to the unit/integration/contract category — both a `unit` test and an `integration` test may be `fast` if they happen to be quick. |
| **Use when** | The test reliably finishes in sub-second wall-clock and has no I/O fan-out. Mark it `fast` so the inner developer loop (`uv run pytest -m fast`) selects it. |
| **Do NOT use when** | The test does anything that depends on subprocess timing, git fetches, network, or large fixture trees. Marking such a test `fast` poisons the fast lane and slows everyone's loop. |
| **CI role** | The inner-loop selector. `-m fast` is what developers should be able to run between every edit and have green in seconds. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Slow](#slow), [Unit](#unit) |

---

### Slow

| | |
|---|---|
| **Definition** | A performance characterization declaring the test takes >10 seconds wall-clock per item, requires heavy setup (wheel build, distribution install, large fixture tree), or otherwise should not run on every developer save. Orthogonal to category — an `integration` or `e2e` test may also be `slow`. |
| **Use when** | The test reliably exceeds 10 seconds, builds a wheel, installs a venv, or runs a Docker setup. |
| **Do NOT use when** | The test could be made fast by isolating a dependency or by writing a leaner fixture — fix the test first, then re-evaluate the marker. |
| **CI role** | Excluded from the inner loop (`uv run pytest -m "not slow"`) and run in dedicated slow / nightly gates. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Fast](#fast), [E2E](#e2e), [Distribution](#distribution) |

---

### Git Repo

| | |
|---|---|
| **Definition** | A test that creates a real git repository (via `git init`, `subprocess.run`, or the `GitRepo` fixture) and exercises real git plumbing — commits, branches, worktrees, refs. |
| **Use when** | The test calls `git init` / `git commit` / `git worktree add` either directly or through a fixture, and the assertion depends on real git state. |
| **Do NOT use when** | The test only inspects in-memory git metadata (the bundled `GitRepo` dataclass without `git init`) — that's `unit`. |
| **CI role** | Run with `-m git_repo` for the git-plumbing gate; useful to isolate when the host's git binary or version is suspect. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Integration](#integration) |

---

### Distribution

| | |
|---|---|
| **Definition** | A test that builds a wheel from the working tree, installs it into a temporary venv, and verifies the installed surface (`spec-kitty --version`, CLI commands work from a fresh install with no `SPEC_KITTY_TEMPLATE_ROOT` override, etc.). Catches the "works on developer machine, fails on PyPI install" gap. |
| **Use when** | The test asserts an invariant about the installed package — packaged data files are present, entry points resolve, templates ship correctly. |
| **Do NOT use when** | The test runs against the source tree without installing — that's `unit`, `integration`, or `e2e` depending on scope. |
| **CI role** | Always paired with `slow` (wheel build + install is heavy). Run in the release gate. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Slow](#slow), [E2E](#e2e) |

---

### Platform Darwin / Platform Linux

| | |
|---|---|
| **Definition** | A test that asserts OS-specific behavior (case-insensitive FS on macOS, POSIX path semantics on Linux, etc.). Auto-skipped on the wrong platform via conftest. |
| **Use when** | The test would always fail or always pass on the wrong platform regardless of code correctness. |
| **Do NOT use when** | The test is cross-platform but happens to be written on one OS — that is the default; no platform marker needed. |
| **CI role** | Run on matching CI matrix legs; auto-skipped elsewhere. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Windows CI](#windows-ci) |

---

### Windows CI

| | |
|---|---|
| **Definition** | A test that must pass on the native windows-latest CI job. Auto-skipped on non-Windows hosts via the top-level conftest. Covers Windows-specific hook execution, file-backed auth storage, path helpers, worktree fallback, regression guards for Windows path quirks. |
| **Use when** | The test exercises code that has a Windows-specific code path (CRLF handling, drive letters, junction points, case-insensitive but case-preserving FS). |
| **Do NOT use when** | The test passes on every OS — no platform marker needed. |
| **CI role** | Run on the `windows-latest` matrix leg; skipped on every other host. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Platform Darwin / Platform Linux](#platform-darwin--platform-linux) |

---

### Requires Symlinks

| | |
|---|---|
| **Definition** | A test that needs functioning symlink support on the host filesystem. Auto-skipped where symlinks are unavailable (some Windows configurations, restricted CI runners). |
| **Use when** | The test creates or follows a symlink as part of its setup or assertion. |
| **Do NOT use when** | The test uses only hard links, directory junctions, or path resolution. |
| **CI role** | Skipped on hosts without symlink support; otherwise runs in the standard suite. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Windows CI](#windows-ci) |

---

### Live Adapter

| | |
|---|---|
| **Definition** | A test that calls the real Anthropic API (or any other live external service) instead of a mocked adapter. Always opt-in; default CI excludes it via `-m "not live_adapter"`. |
| **Use when** | The test verifies behavior that only the real service can validate (rate-limit handling, real model responses, real authentication). |
| **Do NOT use when** | A mocked adapter can simulate the contract — use `unit` or `integration` with a mock. |
| **CI role** | Excluded from default runs; activated only when API credentials are present and the contract needs live verification. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Contract](#contract), [Integration](#integration) |

---

### Asyncio

| | |
|---|---|
| **Definition** | A test that requires the `pytest-asyncio` event-loop fixture to run a coroutine. Marker is set automatically by `pytest-asyncio` when the test function is `async def` (the project's `asyncio_mode = auto`), so explicit tagging is optional but harmless. |
| **Use when** | The test function is `async def`. The marker is informational; the asyncio plugin handles execution. |
| **Do NOT use when** | The test is sync; the marker has no effect. |
| **CI role** | Implicit. The marker exists to allow `-m asyncio` selection if a project ever needs to isolate async-only failures. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | — |

---

### Timeout

| | |
|---|---|
| **Definition** | A per-test wall-clock budget enforced by `pytest-timeout`. The marker carries a numeric argument: `@pytest.mark.timeout(N)`. Different in shape from the categorical markers above. |
| **Use when** | A test exercises a code path that could hang (poll loop, retry, network read without timeout) and must fail loudly rather than block the suite. |
| **Do NOT use when** | The test naturally completes in a bounded time; the marker adds noise. |
| **CI role** | Hangs become test failures rather than CI infrastructure failures. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Slow](#slow) |

---

### No Readiness Stub

| | |
|---|---|
| **Definition** | An opt-out from the autouse readiness-stub fixture that the tracker CLI test suite installs by default. The test wires its own readiness machinery and would be perturbed by the stub. Introduced for mission 082 tracker CLI tests. |
| **Use when** | The test exercises the real readiness path of a tracker CLI command and must not be patched by the default stub. |
| **Do NOT use when** | The test is fine with the default stubbed readiness — most tests are. |
| **CI role** | Behavioral opt-out; not used by gate filters. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | — |

---

### Non Sandbox

| | |
|---|---|
| **Definition** | A test that is structurally incompatible with `mutmut`'s forked sandbox (subprocess CLI calls, whole-codebase AST walks, wheel builds, or repo-state fixtures outside `also_copy`). Documented in ADR `docs/adr/2.x/2026-04-20-1`. |
| **Use when** | The test fails inside `mutmut`'s forked-sandbox environment because of one of the structural reasons above. |
| **Do NOT use when** | The test runs cleanly in `mutmut`. |
| **CI role** | Excluded from mutation-testing runs; runs normally in the standard suite. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Flaky](#flaky) |

---

### Flaky

| | |
|---|---|
| **Definition** | A test that passes in the standard suite but is non-deterministic under `mutmut` or forked pipelines. Each entry is debt — the goal is to root-cause and remove the marker, not to accumulate them. See ADR `docs/adr/2.x/2026-04-20-1`. |
| **Use when** | A test passes in the main suite but observably fails under `mutmut` for reasons unrelated to mutation coverage. Add this marker AND open an issue to root-cause it. |
| **Do NOT use when** | The test is genuinely broken in the main suite — that is a bug, not flakiness. |
| **CI role** | Excluded from mutation runs. Each entry has an open issue; reviewers should track the count down, not up. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Non Sandbox](#non-sandbox) |

---

### Orchestrator Smoke / Availability / Fixtures / Happy Path / Review Cycles / Parallel

| | |
|---|---|
| **Definition** | A family of fine-grained markers for the orchestrator test suite. Each marker selects a slice: `orchestrator_smoke` (basic agent invocation), `orchestrator_availability` (agent availability detection), `orchestrator_fixtures` (fixture loading), `orchestrator_happy_path` (E2E happy paths), `orchestrator_review_cycles` (review approval/rejection cycles), `orchestrator_parallel` (parallel execution and dependency graphs). |
| **Use when** | The test specifically exercises one of these orchestrator concerns and wants to be selectable independently of the broader suite. |
| **Do NOT use when** | The test is a generic unit/integration test that happens to touch the orchestrator — use the category marker instead. |
| **CI role** | Dedicated orchestrator gate may filter by these markers. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | — |

---

### Core Agent / Extended Agent

| | |
|---|---|
| **Definition** | `core_agent` declares the test requires a core-tier agent runtime to be available (fails if unavailable). `extended_agent` declares the test prefers an extended-tier agent but skips cleanly when unavailable. |
| **Use when** | The test invokes a real agent runtime and the test's value depends on which tier ran it. |
| **Do NOT use when** | The test mocks the agent runtime — no agent marker needed. |
| **CI role** | Differentiates "agent must be there or fail loudly" (`core_agent`) from "agent nice-to-have, skip on absence" (`extended_agent`). |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | [Live Adapter](#live-adapter) |

---

### Exploratory

| | |
|---|---|
| **Definition** | A test intended for human-driven exploration only, not for CI runs. Satisfies the architectural marker-presence convention without obligating CI to execute it. CI workflows opt these out via `-m "not exploratory"`. |
| **Use when** | The test is a scratchpad for a developer to spike a behavior interactively, depends on a particular local state, or is too costly to run on every PR. |
| **Do NOT use when** | The test is meant to enforce a contract — promote it to a real category marker and stabilise it. |
| **CI role** | Excluded by default. The marker is the project's escape valve for non-CI tests; do not normalize it. |
| **Context** | Testing Taxonomy |
| **Status** | canonical |
| **Applicable to** | `2.x` |
| **Related terms** | — |
