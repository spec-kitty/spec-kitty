---
work_package_id: WP02
title: Endpoint Resolution & Distribution Seam
dependencies:
- WP01
requirement_refs:
- C-004
- FR-016
- FR-017
- NFR-006
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: a41a9844e0965e3ce8a2096ffe6411661fd22bd6
created_at: '2026-09-30T12:35:52.226859+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Foundation
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/endpoint.py
create_intent:
- src/specify_cli/feedback/endpoint.py
- tests/specify_cli/feedback/test_endpoint.py
- tests/specify_cli/distribution/test_profile_feedback_endpoint.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/endpoint.py
- src/specify_cli/distribution/profile.py
- tests/specify_cli/feedback/test_endpoint.py
- tests/specify_cli/distribution/test_profile_feedback_endpoint.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Endpoint Resolution & Distribution Seam

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `cursor`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for `task_type: implement`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress**: Update the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- `DistributionProfile` gains one optional, defaulted field, `feedback_endpoint: str | None = None`. The stock profile and the degraded sentinel both resolve to `None`, so **the upstream build ships dormant** (decision R-05). Downstream distributions set it through their existing `spec_kitty.distribution_profile` entry point.
- `specify_cli.feedback.endpoint` resolves the effective Feedback Endpoint with the precedence **`SPEC_KITTY_FEEDBACK_URL` env var > user override > distribution default > none**, and validates it (HTTPS, or HTTP only for loopback hosts). Any invalid value resolves to "none" with a machine-readable reason.
- A `describe_endpoint()` helper returns what `spec-kitty feedback --status` shows: the effective URL (or none) and where it came from.
- **Vendor neutrality**: no company name, product name, or URL is hard-coded anywhere in `src/specify_cli/feedback/` or in the stock profile. A test guards this.
- mypy `--strict`, ruff, and format are clean; new code ≥ 90% covered; all existing `tests/specify_cli/distribution/` tests still pass.

## Context & Constraints

- `spec.md`: FR-016, FR-017, NFR-006, C-004, and User Story 5.
- `plan.md`: Key Design Decision 5; IC-02. `research.md`: R-05, R-06.
- `data-model.md`: FeedbackEndpoint.
- Existing seam: `src/specify_cli/distribution/profile.py` (`DistributionProfile`, `stock_distribution_profile()`, `_degraded_profile()`, `_synthesize_from_phase1()`). Read the whole module first; note that `_synthesize_from_phase1` derives from `stock_distribution_profile()` with `dataclasses.replace`, so a defaulted field flows through automatically.
- Sonar guidance (CLAUDE.md): loopback HTTP is intentionally allowed; do not "fix" it by forcing HTTPS on loopback.
- The endpoint module must **not** import preferences internals. It takes the user override as a plain `str | None` argument; callers (WP04/WP05) pass `prefs.endpoint_override`.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `spec-kitty agent mission finalize-tasks`; your lane worktree comes from `lanes.json` via `spec-kitty agent action implement WP02 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first tests for precedence and the dormant default

- **Purpose**: Pin the observable behaviour first (C-011); commit separately before implementation.
- **Steps**: In `tests/specify_cli/feedback/test_endpoint.py` write failing tests:
  1. No env, no override, stock profile → `None` with source `none`.
  2. Profile default `https://feedback.example.test/v1` → that URL, source `distribution`.
  3. Override set → override wins over profile; env set → env wins over both.
  4. `http://127.0.0.1:8765/x`, `http://localhost/x`, `http://[::1]/x` → accepted (loopback).
  5. `http://feedback.example.test/x` (non-loopback HTTP) → `None`, reason `insecure_scheme`.
  6. `ftp://…`, `not a url`, empty string, whitespace → `None`, reason `invalid_url`.
  7. Degraded profile → `None`.
  - Use only `example.test` / loopback hosts in fixtures (reserved names; vendor-neutral).
- **Files**: `tests/specify_cli/feedback/test_endpoint.py`

### Subtask T009 – `DistributionProfile.feedback_endpoint`

- **Purpose**: A packager-facing knob in the existing single authority for distribution defaults.
- **Steps**:
  1. Add `feedback_endpoint: str | None = None` as the **last** field of `DistributionProfile` (keeps positional construction by existing entry points working).
  2. Extend the class docstring's Attributes section: "Default Feedback Endpoint for the Feedback Survey; `None` leaves automatic surveys dormant. Validated at resolution time, not here."
  3. Leave `stock_distribution_profile()` and `_degraded_profile()` producing `None` (explicitly pass `feedback_endpoint=None` in `stock_distribution_profile()` so the dormant default is visible to readers).
  4. Do **not** add validation in the dataclass; resolution (T010) validates.
- **Files**: `src/specify_cli/distribution/profile.py`
- **Parallel?**: Yes, with T010.
- **Notes**: This is an additive change to a dataclass used by packagers. Keep it backward-compatible; no `__init__.py` changes in `specify_cli` (which would force a version bump per CLAUDE.md).

### Subtask T010 – `resolve_feedback_endpoint()` + validation

- **Purpose**: The single resolution function every caller uses.
- **Suggested shape**:

```python
EndpointSource = Literal["env", "user", "distribution", "none"]

@dataclass(frozen=True)
class ResolvedEndpoint:
    url: str | None
    source: EndpointSource
    rejected_reason: Literal["insecure_scheme", "invalid_url"] | None = None

ENV_FEEDBACK_URL = "SPEC_KITTY_FEEDBACK_URL"

def resolve_feedback_endpoint(
    *,
    override: str | None,
    env: Mapping[str, str] | None = None,
    profile: DistributionProfile | None = None,
) -> ResolvedEndpoint: ...
```

- **Steps**:
  1. Pick the first non-blank candidate in precedence order (`env[ENV_FEEDBACK_URL]`, `override`, `profile.feedback_endpoint`); remember its source.
  2. Validate with `urllib.parse.urlsplit`: scheme must be `https`, or `http` with hostname in `{"127.0.0.1", "::1", "localhost"}`; a hostname is required. Failure → `ResolvedEndpoint(None, source, reason)`. Do **not** fall through to a lower-precedence candidate when a higher one is invalid; an invalid explicit choice means "none", which is safer and more predictable.
  3. `profile` defaults to `resolve_distribution_profile()`; `env` defaults to `os.environ`.
  4. Never raise.
- **Files**: `src/specify_cli/feedback/endpoint.py`

### Subtask T011 – `describe_endpoint()`

- **Purpose**: Feed `--status` (FR-019) without duplicating resolution logic.
- **Steps**: `describe_endpoint(resolved: ResolvedEndpoint) -> str` returns human text, for example `https://… (from distribution default)`, `none (no feedback endpoint configured)`, or `none (SPEC_KITTY_FEEDBACK_URL rejected: must use https unless loopback)`. Keep all strings as module constants (Sonar S1192).
- **Files**: `src/specify_cli/feedback/endpoint.py`

### Subtask T012 – Tests: profile field, endpoint matrix, neutrality guard

- **Steps**:
  1. `tests/specify_cli/distribution/test_profile_feedback_endpoint.py`: stock profile → `None`; degraded profile → `None`; a profile constructed with a value keeps it; `replace()` from stock keeps `None`; an entry-point-provided profile (reuse the monkeypatch style from `tests/specify_cli/distribution/test_profile.py`) exposes its value.
  2. Complete the T008 matrix plus `describe_endpoint` strings.
  3. Neutrality guard (same test file as T008): scan `src/specify_cli/feedback/**/*.py` text for `https?://` literals and assert none exist except loopback examples in docstrings. Include a positive control: the scanner flags a synthetic string containing a URL, so the scan cannot be vacuous.
  4. Run the existing distribution tests unchanged.
- **Files**: `tests/specify_cli/distribution/test_profile_feedback_endpoint.py`, `tests/specify_cli/feedback/test_endpoint.py`

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/feedback/test_endpoint.py tests/specify_cli/distribution -q
uv run --frozen mypy --strict src/specify_cli/feedback/endpoint.py src/specify_cli/distribution/profile.py
uv run --frozen ruff check src/specify_cli/feedback src/specify_cli/distribution tests/specify_cli/feedback tests/specify_cli/distribution
uv run --frozen ruff format --check src/specify_cli/feedback src/specify_cli/distribution tests/specify_cli/feedback tests/specify_cli/distribution
make test-fast
```

Record commands and counts in the Activity Log.

## Risks & Mitigations

- **Existing profile equality tests** → the defaulted trailing field keeps equality semantics; run the whole `tests/specify_cli/distribution/` directory.
- **A tempting upstream default URL** → forbidden (dormant upstream, vendor neutrality). The guard test enforces it.

## Review Guidance

- Confirm the stock profile ships `feedback_endpoint=None` and no URL literal exists in the feedback package.
- Confirm an invalid higher-precedence value yields "none" rather than silently falling through.
- Confirm the loopback allowance is limited to the three hostnames.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
