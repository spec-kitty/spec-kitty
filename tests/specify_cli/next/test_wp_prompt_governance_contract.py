"""ATDD acceptance spec: WP prompt governance completeness contract.

These tests are the executable specification for the next mission. They
encode the contract that:

1. `spec-kitty agent action implement` (and `... review`) build the WP prompt
   from a command template AND invoke the charter/doctrine pipeline to fetch
   governance content.
2. The fetched content is **amended into** the WP prompt — either as
   **verbatim rule bodies** for the directives, tactics, glossary terms,
   and ADR entries that govern the action, OR as **explicit fetch commands
   paired with a "when doing X, run …" conditional rule** so the executing
   agent can pull the body on demand.
3. The loaded agent profile's `directive-references` and `tactic-references`
   (e.g. python-pedro citing DIRECTIVE_010, reviewer-renata citing
   DIRECTIVE_032) MUST surface in the prompt — either by ID + content or by
   fetch command. Today these are loaded into the profile object but never
   rendered in the prompt; that gap is the structural cause of the
   shipped → built-in / provenance → source-attribution drift documented in
   `docs/development/org-doctrine-layer-architecture-review.md`.
4. The compact governance lookup (`spec-kitty charter context --action
   implement`) must surface section bodies, not only anchors, for sections
   the action depends on (Terminology Canon, Code Review Checklist,
   Regression Vigilance, etc.).
5. The runtime implement template at
   `src/specify_cli/missions/software-dev/command-templates/implement.md`
   currently includes a forbid clause that says "do not separately call
   `spec-kitty charter context` …". Either that clause must be removed
   (and the prompt augmented to carry the rule bodies), or the template
   must explicitly declare which governance bodies are guaranteed to be in
   the prompt and which require a fetch.
6. The two directive namespaces — charter-extracted `DIR-NNN` (auto-emitted
   by `spec-kitty charter sync` into `.kittify/charter/directives.yaml`)
   and doctrine-catalog `DIRECTIVE_NNN` (hand-authored in
   `src/charter/offering/directives/built-in/*.directive.yaml`) — must be
   cross-linked when one cites the other, so the resolver can surface the
   right body regardless of which ID the citation used.

These tests will fail today (the current implementation injects only
section anchors with the wrong directive namespace and zero tactics).
That failure is the spec for the next mission. Do not modify the tests
to make them pass via mocks; modify the implementation.

Background: the root-cause analysis lives at
`docs/development/org-doctrine-layer-architecture-review.md`, sections
"Process architecture: where the glossary / architecture alignment failed",
"Root cause", and "Empirical addendum".
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.context import build_charter_context
from charter.activation.scope import CharterScopeNotFound
from runtime.next.prompt_builder import _build_wp_prompt, _governance_context
from tests.lane_test_utils import write_single_lane_manifest


pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures: a minimal but realistic project skeleton with a charter that
# DECLARES its template set and available tools, plus a WP whose frontmatter
# selects the python-pedro agent profile.
# ---------------------------------------------------------------------------


_MINIMAL_CHARTER_MD = """\
# Test Project Charter

> Version: 1.0.0

## Purpose

A minimal charter used by the WP-prompt governance contract acceptance
tests. The body of this charter intentionally declares both a
``template_set`` and an ``available_tools`` selection so the resolved
charter context surfaces those declarations instead of falling back to
``software-dev-default`` with a diagnostics warning.

## Technical Standards

Python 3.11+, pytest, mypy strict.

## Terminology Canon

- The canonical term for a unit of governed work is **Mission**.
- ``feature`` and ``features`` are prohibited in canonical, operator, and
  user-facing language; legacy aliases are permitted only as hidden
  secondary CLI flags.

## Regression Vigilance (2026-04-06)

When renaming any identifier-bearing term (e.g. shipped → built-in,
provenance → source-attribution), the reviewer MUST grep the diff for the
old term, MUST consult the project glossary at ``docs/context/``,
and MUST flag any unconverted occurrence as a defect.

## Code Review Checklist

- The WP diff respects the agent profile's directive-references.
- Terminology in code and docs aligns with the project glossary
  (DIRECTIVE_032 — Conceptual Alignment).
- No new code path violates an architectural ADR in
  ``docs/adr/3.x/``.

## Charter Resolution Hints

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest, mypy, ruff]
```
"""


def _write_minimal_kittify_charter(repo_root: Path) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_MINIMAL_CHARTER_MD, encoding="utf-8")
    # A usable project is provisioned: the mission-type-use boundary
    # (prompt build during implement/review) resolves ``software-dev``
    # through the project's activation set, so the fixture must declare it.
    # Without this, ``resolve_mission_type_context`` hard-fails with
    # ``UnknownMissionTypeError`` (empty activation set) exactly as it would
    # for a genuinely unprovisioned project (WP04 construction-total pivot:
    # the fail-closed lives at the create / use boundary, not construction).
    (repo_root / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


_WP_WITH_PYTHON_PEDRO = """\
---
work_package_id: WP01
title: Reconcile shipped vs built-in terminology
dependencies: []
requirement_refs: [FR-001]
subtasks: [T001, T002]
agent: claude
agent_profile: python-pedro
role: implementer
authoritative_surface: src/charter/offering/service.py
owned_files: [src/charter/offering/service.py]
execution_mode: code_change
history: []
---
# WP01 — Reconcile shipped vs built-in terminology

Replace literal ``shipped`` path strings with ``built-in`` across
``src/charter/offering/`` and update tests accordingly.
"""


_WP_WITH_REVIEWER_RENATA = """\
---
work_package_id: WP02
title: Review the rename
dependencies: [WP01]
requirement_refs: [FR-001]
subtasks: [T003]
agent: claude
agent_profile: reviewer-renata
role: reviewer
authoritative_surface: src/charter/offering/service.py
owned_files: [src/charter/offering/service.py]
execution_mode: code_change
history: []
---
# WP02 — Review the rename

Review WP01's terminology rename for completeness, glossary alignment, and
ADR-fit.
"""


def _git_init_minimal(repo_root: Path) -> None:
    """Initialise a git repo so charter resolution accepts the project root.

    `charter.resolution.NotInsideRepositoryError` is raised when the resolver
    cannot find a `.git/` ancestor; we satisfy that precondition here so the
    governance-contract tests fail for the real (payload) reason rather than
    for missing git infrastructure.
    """
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "atdd@example.com"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "ATDD"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_root, check=True, capture_output=True)


@pytest.fixture
def project_with_implement_wp(tmp_path: Path) -> tuple[Path, Path, str]:
    """Construct a repo_root + feature_dir + mission_slug fixture.

    The fixture writes:
      - a git-initialised repository root,
      - a charter.md with a declared template_set and available_tools,
      - a single-lane manifest for WP01 + WP02,
      - WP01 frontmatter selecting agent profile ``python-pedro``,
      - WP02 frontmatter selecting agent profile ``reviewer-renata``.
    """
    repo_root = tmp_path
    _git_init_minimal(repo_root)
    mission_slug = "999-gov-contract"
    feature_dir = repo_root / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks" / "WP01.md").write_text(_WP_WITH_PYTHON_PEDRO, encoding="utf-8")
    (feature_dir / "tasks" / "WP02.md").write_text(_WP_WITH_REVIEWER_RENATA, encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"))
    _write_minimal_kittify_charter(repo_root)
    return repo_root, feature_dir, mission_slug


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FETCH_CMD_RE = re.compile(
    r"spec-kitty\s+charter\s+context\b|"
    r"spec-kitty\s+doctrine\b|"
    r"ActiveCharterService\(",
    re.IGNORECASE,
)
_WHEN_DOING_RE = re.compile(
    r"when\s+you\s+(are\s+about\s+to|need\s+to|encounter|introduce|rename|review)",
    re.IGNORECASE,
)


def _contains_either_body_or_fetch_with_conditional(text: str, *body_markers: str) -> bool:
    """Return True if *text* satisfies the verbatim-OR-fetch-with-conditional contract.

    The contract: for each body marker (a sentence the rule body would
    contain), the prompt must EITHER include the verbatim phrase OR include
    BOTH a fetch command (``spec-kitty charter context …`` etc.) AND a
    ``when …`` conditional. This is the "amend with verbatim contents OR
    fetch command + when-doing-X rule" requirement.
    """
    if all(marker in text for marker in body_markers):
        return True
    return bool(_FETCH_CMD_RE.search(text) and _WHEN_DOING_RE.search(text))


_RUN_CMD_SELECTOR_RE = re.compile(
    r"Run:\s+spec-kitty\s+charter\s+context\s+--include\s+(\S+)", re.IGNORECASE
)


def _when_you_stanzas(prompt: str) -> list[tuple[str | None, str]]:
    """Pair every rendered ``When you …`` stanza line with its selector.

    NFR-003 / SC-003 (#3082): ``_WHEN_DOING_RE.search(prompt)`` (used
    throughout this module above) passes if ANY single line anywhere in the
    whole prompt matches — it says nothing about the other stanzas. This
    per-line extraction lets a caller assert EVERY emitted stanza
    individually, which is the real per-stanza grammaticality guarantee.

    Returns ``(selector, when_you_line)`` tuples in document order. The
    selector is read from the fetch-command line immediately preceding the
    ``When you ...`` line (every current renderer emits the pair together);
    it is ``None`` if no such line precedes (defensive).
    """
    lines = prompt.splitlines()
    stanzas: list[tuple[str | None, str]] = []
    for index, line in enumerate(lines):
        if not re.match(r"^\s*When you\b", line, re.IGNORECASE):
            continue
        selector = None
        if index > 0:
            match = _RUN_CMD_SELECTOR_RE.search(lines[index - 1])
            if match:
                selector = match.group(1)
        stanzas.append((selector, line.strip()))
    return stanzas


# ---------------------------------------------------------------------------
# Contract 1 — The implement / review WP prompt MUST invoke the charter
#              pipeline and inject its output into the prompt.
# ---------------------------------------------------------------------------


class TestImplementPromptInvokesCharterPipeline:
    """The entry point IS wired. This pins it so a refactor cannot silently remove it."""

    def test_build_wp_prompt_for_implement_calls_governance_context(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """`_build_wp_prompt(action="implement", ...)` MUST call `_governance_context`.

        Today this is verified at `src/specify_cli/next/prompt_builder.py:147`.
        Pin it so a refactor cannot silently drop the call.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        with patch("runtime.next.prompt_builder._governance_context") as gov:
            gov.return_value = "Governance: stub for test"
            _build_wp_prompt(
                action="implement",
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                agent="claude",
                repo_root=repo_root,
                mission_type="software-dev",
            )
        assert gov.called, (
            "_build_wp_prompt MUST invoke _governance_context for implement actions. "
            "If this fails, the structural entry point is broken — see "
            "docs/development/org-doctrine-layer-architecture-review.md "
            "section 'Empirical addendum'."
        )
        call_kwargs = gov.call_args.kwargs
        assert call_kwargs.get("action") == "implement", (
            "Governance must be resolved with the action label, not a stale default."
        )

    def test_build_wp_prompt_for_review_calls_governance_context(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        with patch("runtime.next.prompt_builder._governance_context") as gov:
            gov.return_value = "Governance: stub for test"
            _build_wp_prompt(
                action="review",
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP02",
                agent="claude",
                repo_root=repo_root,
                mission_type="software-dev",
            )
        assert gov.called
        assert gov.call_args.kwargs.get("action") == "review"

    def test_governance_context_output_is_present_in_wp_prompt_text(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """The text returned by `_governance_context` MUST appear in the rendered prompt."""
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        sentinel = "GOVERNANCE-INJECTION-SENTINEL-7af3b9"
        with patch(
            "runtime.next.prompt_builder._governance_context", return_value=sentinel
        ):
            prompt = _build_wp_prompt(
                action="implement",
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                agent="claude",
                repo_root=repo_root,
                mission_type="software-dev",
            )
        assert sentinel in prompt, (
            "_build_wp_prompt MUST embed the _governance_context output into the prompt "
            "string returned to the agent."
        )


# ---------------------------------------------------------------------------
# Contract 2 — The WP prompt MUST contain actionable governance content,
#              not only section anchors.
# ---------------------------------------------------------------------------


class TestImplementPromptContainsActionableGovernance:
    """The payload MUST be either verbatim rule body OR fetch + when-doing rule."""

    def test_implement_prompt_terminology_canon_body_or_fetch_with_when_doing_rule(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """The Terminology Canon section governs renames. The implementer MUST receive
        either the body of that section or a fetch command paired with an explicit
        ``when you rename / introduce a term, …`` conditional. Today the prompt
        contains only the section ANCHOR (the title), which is the gap that produced
        the shipped → built-in drift in the layered-doctrine-org-layer mission.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        ok = _contains_either_body_or_fetch_with_conditional(
            prompt,
            # Verbatim-path markers: characteristic phrases from the body of the
            # Terminology Canon section in the fixture charter.
            "canonical term for a unit of governed work is **Mission**",
        )
        assert ok, (
            "The implement WP prompt MUST include the Terminology Canon rule body "
            "OR a fetch command (`spec-kitty charter context ...`) paired with a "
            '"when you rename / introduce a term, …" conditional. Currently the '
            "prompt only includes the section TITLE 'Terminology Canon'."
        )

    def test_implement_prompt_regression_vigilance_body_or_fetch_with_when_doing_rule(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """The Regression Vigilance section is the project's explicit guard against
        the very class of drift this contract is designed to prevent. Implementers
        MUST receive its rules, not only its heading.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        ok = _contains_either_body_or_fetch_with_conditional(
            prompt,
            "reviewer MUST grep the diff for the old term",
        )
        assert ok, (
            "The implement WP prompt MUST surface the Regression Vigilance rule body "
            "OR the fetch + when-doing pair so the implementer can apply the rule."
        )

    def test_implement_prompt_is_not_only_section_anchors(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """Detection: if the prompt's governance block lists section titles but
        contains no body text, the implementer is governance-blind. We require at
        least one body sentence (or at least one fetch command + conditional) to
        accompany the anchors.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        has_anchors = "Section Anchors:" in prompt or "Terminology Canon" in prompt
        has_body_or_fetch = (
            "canonical term for a unit of governed work is **Mission**" in prompt
            or bool(_FETCH_CMD_RE.search(prompt) and _WHEN_DOING_RE.search(prompt))
        )
        assert not (has_anchors and not has_body_or_fetch), (
            "Anchors-only injection is the documented failure mode. The prompt has "
            "the Terminology Canon ANCHOR but neither the body nor a fetch + "
            "when-doing rule. See the Empirical addendum in "
            "docs/development/org-doctrine-layer-architecture-review.md."
        )


# ---------------------------------------------------------------------------
# Contract 3 — The loaded agent profile's directive_references and
#              tactic_references MUST surface in the prompt the profile's
#              own agent will read.
# ---------------------------------------------------------------------------


class TestProfileDirectivesSurfacedInWpPrompt:
    """The python-pedro / reviewer-renata profiles each declare a curated set of
    DIRECTIVE_NNN / tactic-id references. Those references MUST appear in the
    WP prompt — either as the directive bodies inline OR as fetch commands
    paired with a 'when doing X, fetch directive Y' rule.
    """

    def test_python_pedro_directive_010_referenced_in_implement_prompt(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """python-pedro's profile (`src/charter/offering/agent_profiles/built-in/`
        `python-pedro.agent.yaml`) declares directive 010 (Specification Fidelity).
        The implement WP whose frontmatter selects python-pedro MUST surface
        DIRECTIVE_010 in the prompt: either the rule body verbatim or a fetch
        command coupled with a `when you implement code, fetch directive 010`
        conditional.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        directive_id_present = "DIRECTIVE_010" in prompt or "directive 010" in prompt.lower()
        body_present = "Specification Fidelity" in prompt
        fetch_with_conditional = bool(
            _FETCH_CMD_RE.search(prompt) and _WHEN_DOING_RE.search(prompt)
        )
        assert directive_id_present and (body_present or fetch_with_conditional), (
            "WP01 selects agent_profile=python-pedro, which carries directive 010 in "
            "its directive-references. The prompt MUST cite DIRECTIVE_010 and either "
            "embed its body or pair a fetch command with a when-doing conditional. "
            "Today profile-referenced directives are loaded into the profile object "
            "and never rendered into the WP prompt — that is the structural gap "
            "this test pins."
        )

    def test_python_pedro_directive_024_locality_referenced_in_implement_prompt(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """Locality of Change (DIRECTIVE_024) is a python-pedro directive."""
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert "DIRECTIVE_024" in prompt or "Locality of Change" in prompt, (
            "Implement prompt MUST surface DIRECTIVE_024 (Locality of Change) when the "
            "loaded profile is python-pedro."
        )

    def test_python_pedro_directive_030_test_typecheck_gate_referenced(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """Test + Typecheck Quality Gate (DIRECTIVE_030) is the most concrete check
        for an implementer — must be surfaced explicitly.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        assert (
            "DIRECTIVE_030" in prompt
            or "Test and Typecheck Quality Gate" in prompt
        ), (
            "Implement prompt MUST surface DIRECTIVE_030 — pre-handoff quality gate."
        )

    def test_reviewer_renata_directive_032_conceptual_alignment_in_review_prompt(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """The reviewer-renata profile cites DIRECTIVE_032 (Conceptual Alignment) with
        the rationale: 'Terminology in code and docs must align with the project
        glossary — language drift signals architectural drift'. THIS is the
        directive that would have caught the shipped → built-in / provenance →
        source-attribution drift. The review WP prompt MUST surface it.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="review",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        directive_present = (
            "DIRECTIVE_032" in prompt or "Conceptual Alignment" in prompt
        )
        glossary_pointer = (
            "docs/context/" in prompt or "project glossary" in prompt
        )
        assert directive_present and glossary_pointer, (
            "Review WP prompt MUST cite DIRECTIVE_032 (Conceptual Alignment) AND "
            "include a glossary pointer. This is the directive whose absence "
            "produced the shipped → built-in drift documented in the post-merge "
            "review of mission layered-doctrine-org-layer-01KRNPEE."
        )

    def test_reviewer_renata_tactic_language_driven_design_in_review_prompt(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """reviewer-renata declares the `language-driven-design` tactic with rationale:
        'Detect terminology conflicts in diffs as early signals of architectural
        problems'. This MUST appear in the review prompt — either inline or via
        fetch command.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="review",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        tactic_present = (
            "language-driven-design" in prompt
            or "Detect terminology conflicts" in prompt
        )
        fetch_with_conditional = bool(
            _FETCH_CMD_RE.search(prompt) and _WHEN_DOING_RE.search(prompt)
        )
        assert tactic_present or fetch_with_conditional, (
            "Review prompt MUST surface the profile-declared `language-driven-design` "
            "tactic, either by name + rationale or via a fetch command paired with a "
            "when-doing-X conditional."
        )

    def test_profile_directives_use_doctrine_catalog_namespace_in_prompt(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """When the prompt cites a profile-declared directive, the citation MUST use
        the doctrine-catalog namespace (`DIRECTIVE_NNN`), not the charter-extracted
        namespace (`DIR-NNN`). The two namespaces exist today; the contract is that
        profile-cited directives use the catalog form so the agent can locate the
        body at `src/charter/offering/directives/built-in/<id>.directive.yaml`.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        catalog_re = re.compile(r"\bDIRECTIVE_\d{3}\b")
        charter_only_re = re.compile(r"\bDIR-\d{3}\b")
        catalog_hits = catalog_re.findall(prompt)
        charter_hits = charter_only_re.findall(prompt)
        assert catalog_hits, (
            "Prompt MUST cite at least one doctrine-catalog DIRECTIVE_NNN when the "
            "loaded profile carries directive_references. Today the prompt cites only "
            "charter-extracted DIR-NNN entries, which live in a parallel namespace "
            "the profile does not reference."
        )
        # We do not forbid DIR-NNN entirely — both namespaces may legitimately appear —
        # but catalog citations must accompany them.
        if charter_hits and not catalog_hits:
            pytest.fail(
                "Prompt contains charter-extracted DIR-NNN directives without any "
                "doctrine-catalog DIRECTIVE_NNN counterpart. The profile-loaded "
                "doctrine references are not being surfaced."
            )


# ---------------------------------------------------------------------------
# Contract 4 — The prompt MUST point at the glossary and at the ADRs.
# ---------------------------------------------------------------------------


class TestPromptReferencesAuthorityPaths:
    """The glossary and the architecture ADRs are the canonical sources of truth
    for terminology and architectural intent. The prompt must surface their paths
    explicitly (verbatim path or via fetch command), so the agent can locate them.
    """

    def test_implement_prompt_references_glossary_path(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        glossary_path_present = (
            "docs/context/" in prompt or "glossary/" in prompt
        )
        glossary_fetch_with_conditional = bool(
            re.search(r"spec-kitty\s+.*glossary", prompt, re.IGNORECASE)
            and _WHEN_DOING_RE.search(prompt)
        )
        assert glossary_path_present or glossary_fetch_with_conditional, (
            "Implement prompt MUST reference the project glossary path "
            "(`docs/context/`) OR include a fetch command paired with a "
            'when-doing-X conditional ("when you introduce a new term, consult …").'
        )

    def test_implement_prompt_references_adr_path(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        adr_path_present = "docs/adr/3.x/" in prompt or "architecture/adr" in prompt
        adr_fetch_with_conditional = bool(
            re.search(r"adr", prompt, re.IGNORECASE) and _WHEN_DOING_RE.search(prompt)
        )
        assert adr_path_present or adr_fetch_with_conditional, (
            "Implement prompt MUST reference the architecture ADR directory or include "
            "a when-doing-X conditional pointing at ADRs."
        )


# ---------------------------------------------------------------------------
# Contract 5 — The runtime implement template MUST NOT both (a) forbid the
#              agent from calling `charter context` AND (b) leave the prompt
#              without the rule bodies. Either remove the forbid clause OR
#              guarantee bodies are present.
# ---------------------------------------------------------------------------


class TestImplementTemplateForbidClauseIsHonest:
    """The current template at
    `packs/built-in/missions/mission-steps/software-dev/implement/prompt.md` says:

        > The output of `spec-kitty agent action implement ...` is the authoritative
        > work package prompt and execution context. Do **not** separately call
        > `spec-kitty charter context` or rummage through unrelated files looking
        > for a "newer" prompt unless the command output tells you to.

    That is only a defensible instruction if the prompt actually carries the
    governance bodies. The next mission must either remove the forbid clause OR
    add a guarantee section that lists the bodies the prompt is contractually
    required to carry.
    """

    template_path = Path("packs/built-in/missions/mission-steps/software-dev/implement/prompt.md")

    def test_template_either_drops_forbid_or_guarantees_governance_payload(self) -> None:
        text = self.template_path.read_text(encoding="utf-8")
        # The exact forbid clause as it stands today, normalised for whitespace.
        has_forbid_clause = bool(
            re.search(
                r"Do\s+\*\*not\*\*\s+separately\s+call\s+`spec-kitty\s+charter\s+context`",
                text,
                re.IGNORECASE,
            )
        )
        if not has_forbid_clause:
            return  # Template was updated to drop the clause — contract satisfied.
        # Otherwise, the template MUST explicitly declare the governance payload
        # the prompt is guaranteed to carry. We accept several phrasings as proof.
        guarantee_re = re.compile(
            r"governance\s+payload\s+contract|"
            r"the\s+prompt\s+is\s+guaranteed\s+to\s+include|"
            r"governance\s+sections?\s+below\s+contain\s+the\s+rule\s+bodies",
            re.IGNORECASE,
        )
        assert guarantee_re.search(text), (
            "The implement template still forbids the agent from looking elsewhere "
            "for governance, but does not declare which governance bodies the prompt "
            "is contractually required to carry. Either drop the forbid clause or "
            "add a 'Governance Payload Contract' section that enumerates the "
            "guaranteed bodies (Terminology Canon, Code Review Checklist, profile "
            "directives, etc.)."
        )


# ---------------------------------------------------------------------------
# Contract 6 — `build_charter_context(action="implement")` MUST surface the
#              section bodies, not only the anchors, for sections marked
#              critical to the action.
# ---------------------------------------------------------------------------


class TestCharterContextResolverCompleteness:
    """The lookup that the WP-prompt builder calls (`build_charter_context`) is
    the boundary where bodies-vs-anchors is decided. Pin its contract here so the
    next mission knows where to make the change.
    """

    def test_implement_action_context_includes_terminology_canon_body(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, _feature_dir, _mission_slug = project_with_implement_wp
        result = build_charter_context(repo_root, action="implement", mark_loaded=False)
        assert (
            "canonical term for a unit of governed work is **Mission**" in result.text
            or "## Terminology Canon" in result.text
            and "Mission" in result.text
            and "feature" in result.text.lower()
        ), (
            "build_charter_context(action='implement') MUST return the body of the "
            "Terminology Canon section, not only its anchor. Today the resolver "
            "returns only the section title."
        )

    def test_implement_action_context_includes_code_review_checklist_body(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, _feature_dir, _mission_slug = project_with_implement_wp
        result = build_charter_context(repo_root, action="implement", mark_loaded=False)
        assert "agent profile's directive-references" in result.text or (
            "## Code Review Checklist" in result.text
            and "DIRECTIVE_032" in result.text
        ), (
            "build_charter_context(action='implement') MUST surface the Code Review "
            "Checklist body for the implement action (it is the precondition the "
            "reviewer will measure against)."
        )

    def test_implement_action_context_emits_no_template_set_fallback_diagnostic(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """The fixture charter declares a template_set explicitly. The resolver MUST
        NOT emit the 'fallback applied' diagnostic when a declaration exists.
        Today the resolver emits it unconditionally because the parser does not
        read the declaration block; that is the symptomatic gap.
        """
        repo_root, _feature_dir, _mission_slug = project_with_implement_wp
        result = build_charter_context(repo_root, action="implement", mark_loaded=False)
        assert "Template set not selected in charter; fallback" not in result.text, (
            "The fixture charter declares `template_set: software-dev-default` in a "
            "YAML block in the body. The resolver MUST read that declaration and "
            "suppress the fallback diagnostic. Today it emits the fallback notice "
            "regardless of declaration, which is what hides the operator gap."
        )

    def test_implement_action_context_includes_profile_directive_references_when_profile_known(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """When `build_charter_context` is called with `profile=` set, it MUST resolve
        the agent profile's `directive-references` and either embed their bodies or
        emit fetch commands. The `profile=` kwarg exists in the signature today
        (line 73 of `src/charter/activation/context.py`) but is unused (`_ = profile`). The
        contract is that the kwarg becomes load-bearing.
        """
        repo_root, _feature_dir, _mission_slug = project_with_implement_wp
        result = build_charter_context(
            repo_root, action="implement", profile="python-pedro", mark_loaded=False
        )
        carries_catalog_directive = bool(re.search(r"\bDIRECTIVE_\d{3}\b", result.text))
        carries_specification_fidelity_body = "Specification Fidelity" in result.text
        carries_fetch_with_conditional = bool(
            _FETCH_CMD_RE.search(result.text) and _WHEN_DOING_RE.search(result.text)
        )
        assert (
            carries_catalog_directive
            or carries_specification_fidelity_body
            or carries_fetch_with_conditional
        ), (
            "build_charter_context(profile='python-pedro') MUST surface at least one "
            "of the profile's directive-references (DIRECTIVE_010 / 024 / 025 / 030 / "
            "034) — either by ID, by body, or by fetch + when-doing rule. Today the "
            "`profile=` parameter is discarded (`_ = profile`)."
        )


# ---------------------------------------------------------------------------
# Contract 8 — End-to-end: the `_build_wp_prompt` output MUST be self-sufficient.
#              An implementer reading only the prompt MUST be able to satisfy
#              the project's terminology, profile-directive, and architectural
#              checks without consulting any source outside what the prompt
#              cites by path or fetch command.
# ---------------------------------------------------------------------------


class TestPromptSelfSufficiency:
    """The ultimate acceptance test: the rendered prompt is the complete contract
    the implementer needs. Anything the implementer must consult must be either
    inline OR cited by an actionable command + when-doing rule.
    """

    def test_implement_prompt_self_sufficiency(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        # Define the minimum surface area that the prompt MUST expose to be
        # self-sufficient against the documented drift pattern.
        required_surfaces = {
            "profile_directive_id": re.compile(r"\bDIRECTIVE_\d{3}\b"),
            "glossary_pointer": re.compile(r"glossary/?", re.IGNORECASE),
            # Post common-docs move ADRs live at docs/adr/<era>/; the pre-move
            # architecture/<era>/adr path is still accepted for robustness (mirrors
            # test_implement_prompt_references_adr_path above).
            "adr_pointer": re.compile(
                r"docs/adr/|architecture/([23]\.x/)?adr", re.IGNORECASE
            ),
            "terminology_canon_body_or_fetch": re.compile(
                r"canonical term|spec-kitty\s+charter\s+context", re.IGNORECASE
            ),
            "regression_vigilance_body_or_fetch": re.compile(
                r"grep the diff|reviewer MUST|spec-kitty\s+charter\s+context",
                re.IGNORECASE,
            ),
            "fetch_command_with_when_doing": None,  # special-case below
        }
        missing: list[str] = []
        for name, pattern in required_surfaces.items():
            if name == "fetch_command_with_when_doing":
                if not (
                    _FETCH_CMD_RE.search(prompt) and _WHEN_DOING_RE.search(prompt)
                ):
                    # only required if any other surface is NOT verbatim — then we
                    # need at least one fetch command + conditional rule to cover
                    # those.
                    other_misses = [
                        n for n in required_surfaces if n != name and n not in missing
                    ]
                    if len(other_misses) < len(required_surfaces) - 1:
                        missing.append(name)
                continue
            assert pattern is not None
            if not pattern.search(prompt):
                missing.append(name)
        assert not missing, (
            "Implement prompt is not self-sufficient. Missing surfaces: "
            f"{missing}. The prompt MUST contain — verbatim or as a "
            "fetch command paired with a when-doing-X rule — every surface "
            "an implementer needs to satisfy directives, terminology, and "
            "architectural constraints without consulting any uncited source."
        )


# ---------------------------------------------------------------------------
# Contract 9 — `.kittify/charter/charter.md` for a real project MUST declare a
#              `template_set` and `available_tools` block so the resolver does
#              not fall back silently.
# ---------------------------------------------------------------------------


class TestProjectCharterDeclaresResolverInputs:
    """This is a project-level architectural test against spec-kitty's OWN charter.
    The spec-kitty project ships .kittify/charter/charter.md as part of dogfooding.
    That charter MUST declare template_set and available_tools so its own resolver
    does not emit the 'fallback applied' diagnostic when building WP prompts for
    spec-kitty's own missions.
    """

    project_charter = Path(".kittify/charter/charter.md")

    def test_project_charter_declares_template_set(self) -> None:
        if not self.project_charter.exists():
            pytest.skip("No project charter in this checkout.")
        text = self.project_charter.read_text(encoding="utf-8")
        assert re.search(r"template_set\s*:\s*\S+", text), (
            "spec-kitty's own .kittify/charter/charter.md MUST declare a "
            "`template_set` so the charter context resolver does not emit the "
            "'Template set not selected in charter; fallback software-dev-default "
            "applied' diagnostic when building WP prompts for its own missions."
        )

    def test_project_charter_declares_available_tools(self) -> None:
        if not self.project_charter.exists():
            pytest.skip("No project charter in this checkout.")
        text = self.project_charter.read_text(encoding="utf-8")
        assert re.search(r"available_tools\s*:\s*\[", text), (
            "spec-kitty's own .kittify/charter/charter.md MUST declare an "
            "`available_tools` list so the resolver does not fall back to the "
            "runtime tool registry. Fallback diagnostics hide which directives "
            "the charter actually intends to inject."
        )


# ---------------------------------------------------------------------------
# Contract HIGH-1 — _governance_context MUST use build_with_scope so
# monorepo CharterScope resolution is active in the production path.
#
# ATDD anchor: post-merge remediation cycle 1 (2026-05-18)
# covers: FR-010 (Axis 2 production wiring)
# ---------------------------------------------------------------------------


class TestGovernanceContextUsesMonorepoAwarePath:
    """_governance_context MUST delegate to build_with_scope, not call
    build_charter_context directly. This pins the Axis 2 production wiring so
    a future refactor cannot accidentally bypass the CharterScope resolver.
    """

    def test_governance_context_uses_build_with_scope_not_direct_call(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """_governance_context MUST call build_with_scope (not build_charter_context
        directly) so that monorepo CharterScope resolution is exercised.

        This is the production-wiring test for HIGH-1 (Slice F post-merge
        remediation cycle 1). Before the fix, _governance_context called
        build_charter_context(repo_root, ...) directly, bypassing the
        CharterScope resolver entirely. After the fix, it routes through
        build_with_scope(repo_root, feature_dir, ...) so a monorepo operator
        running from packages/auth/ gets the auth charter, not the root charter.
        """
        import runtime.next.prompt_builder as _pb  # noqa: PLC0415

        # HIGH-1 RED condition: build_with_scope is not yet imported into
        # prompt_builder, so the attribute doesn't exist. Verify that the
        # module imports build_with_scope (after the fix it will).
        assert hasattr(_pb, "build_with_scope"), (
            "runtime.next.prompt_builder MUST import build_with_scope "
            "from charter.activation.scope_router to enable monorepo CharterScope "
            "resolution (HIGH-1 / FR-010). Currently build_charter_context "
            "is called directly, bypassing CharterScope.resolve. "
            "Fix: add 'from charter.activation.scope_router import build_with_scope' to "
            "prompt_builder.py and route _governance_context through it."
        )

        repo_root, feature_dir, mission_slug = project_with_implement_wp

        calls: list[tuple] = []

        def _capturing_build_with_scope(
            r: Path, f: Path, **kwargs  # type: ignore[no-untyped-def]
        ):
            calls.append((r, f))
            from charter.activation.context import build_charter_context  # noqa: PLC0415
            return build_charter_context(r, **kwargs)

        with patch(
            "runtime.next.prompt_builder.build_with_scope",
            side_effect=_capturing_build_with_scope,
        ):
            _governance_context(repo_root, feature_dir=feature_dir, action="implement")

        assert calls, (
            "_governance_context MUST call build_with_scope to enable monorepo "
            "CharterScope resolution (HIGH-1 / FR-010). Currently it calls "
            "build_charter_context directly, which bypasses CharterScope.resolve. "
            "Fix: import build_with_scope in prompt_builder and route through it."
        )
        called_repo_root, called_feature_dir = calls[0]
        assert called_repo_root == repo_root
        assert called_feature_dir == feature_dir

    def test_build_wp_prompt_passes_feature_dir_to_governance_context(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """_build_wp_prompt MUST forward feature_dir to _governance_context.

        Without feature_dir, the CharterScope resolver cannot determine which
        sub-project charter to load in a monorepo. This test pins the call-site
        signature so the feature_dir argument is never silently dropped.
        """
        repo_root, feature_dir, mission_slug = project_with_implement_wp

        captured_feature_dir: list[Path] = []

        orig_governance_context = __import__(
            "runtime.next.prompt_builder",
            fromlist=["_governance_context"],
        )._governance_context

        def _spy_governance_context(
            r: Path,
            *,
            feature_dir: Path | None = None,
            action: str | None = None,
            profile: str | None = None,
        ) -> str:
            if feature_dir is not None:
                captured_feature_dir.append(feature_dir)
            return orig_governance_context(r, feature_dir=feature_dir, action=action, profile=profile)

        with patch(
            "runtime.next.prompt_builder._governance_context",
            side_effect=_spy_governance_context,
        ):
            _build_wp_prompt(
                action="implement",
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                agent="claude",
                repo_root=repo_root,
                mission_type="software-dev",
            )

        assert captured_feature_dir, (
            "_build_wp_prompt MUST pass feature_dir to _governance_context so the "
            "CharterScope resolver has the feature directory path available. "
            "Without it, monorepo operators always get the root-project charter."
        )
        assert captured_feature_dir[0] == feature_dir

    def test_governance_context_does_not_mask_scope_routing_failures(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        """Scope resolver failures must fail closed instead of falling back."""
        repo_root, feature_dir, _mission_slug = project_with_implement_wp

        with (
            patch(
                "runtime.next.prompt_builder.build_with_scope",
                side_effect=CharterScopeNotFound("feature outside configured charter scopes"),
            ),
            pytest.raises(CharterScopeNotFound),
        ):
            _governance_context(repo_root, feature_dir=feature_dir, action="implement")


# ---------------------------------------------------------------------------
# Contract 6 — Every rendered "When you ..." stanza, individually, must match
#              the closed _WHEN_DOING_RE lead-in set (#3082, WP01 T004).
# ---------------------------------------------------------------------------


class TestPerStanzaWhenDoingGrammaticality:
    """SC-003 (#3082): the whole-prompt ``_WHEN_DOING_RE.search(prompt)``
    check used throughout this module passes if ANY one line matches
    anywhere in the prompt. That is not the real guarantee — every rendered
    stanza must individually be grammatical and match the closed lead-in
    set. This is the per-stanza authority the fetch-stanza normalization
    fix (``charter.activation.context_renderers.fetch_stanza._normalize_when_clause``)
    is pinned against; see also
    ``tests/charter/test_fetch_stanza_normalization.py`` for the isolated
    unit coverage of the normalization helper itself (gerund clauses, full
    sentences, and the authored double-``when`` shape).

    Scope note (WP01/#3082 discovery, flagged rather than silently
    absorbed): ``section:*`` selector stanzas are rendered by a SEPARATE,
    hand-rolled composer — ``charter.activation.context_renderers.section_bodies.
    _render_fetch_stanza`` / ``CRITICAL_SECTION_WHEN_CLAUSES`` — that does
    NOT go through ``fetch_stanza.fetch_stanza_lines`` and pre-dates this
    mission. Two of its authored clauses ("prepare a WP for review",
    "perform a terminology cutover") do not match the closed lead-in set
    either, but fixing that duplicate choke point is outside WP01's
    authoritative surface (``src/charter/activation/context_renderers/fetch_stanza.py``
    only); ``section_bodies.py`` is not in WP01's owned files. This check is
    scoped to the fetch_stanza.py-owned selector kinds (directive, tactic,
    styleguide, toolguide, procedure, paradigm, mission_step_contract,
    agent_profile) so it asserts what WP01 actually delivers, and the
    ``section:`` gap is left for a follow-up rather than masked here.
    """

    def test_every_fetch_stanza_when_you_line_matches_the_closed_lead_in_set(
        self, project_with_implement_wp: tuple[Path, Path, str]
    ) -> None:
        repo_root, feature_dir, mission_slug = project_with_implement_wp
        prompt = _build_wp_prompt(
            action="implement",
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            agent="claude",
            repo_root=repo_root,
            mission_type="software-dev",
        )
        stanzas = _when_you_stanzas(prompt)
        fetch_stanza_owned = [
            (selector, line)
            for selector, line in stanzas
            if selector is None or not selector.startswith("section:")
        ]
        assert fetch_stanza_owned, (
            "Expected at least one fetch_stanza.py-rendered 'When you ...' "
            "stanza line in the implement WP prompt for python-pedro (whose "
            "profile carries directive/tactic references rendered via the "
            "fetch stanza)."
        )
        for selector, line in fetch_stanza_owned:
            assert _WHEN_DOING_RE.search(line), (
                "Rendered stanza line does not match the closed _WHEN_DOING_RE "
                f"lead-in set (#3082 SC-003 per-stanza guarantee) for selector "
                f"{selector!r}: {line!r}"
            )
