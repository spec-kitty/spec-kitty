"""ATDD acceptance spec — Case 1 (project-layer doctrine artifact lifecycle).

These tests are the executable specification for Mission B (charter-mediated
doctrine selection), Case 1 from the pre-flight:

    A user authors a new doctrine artifact (``caveman-comments.styleguide.yaml``
    that says "all code comments should be written as a caveman would"). The
    user plugs it into spec-kitty, then writes a charter that says "all LLM
    feedback and code comments are to be written in caveman". During a
    mission run, the implementation prompt must contain something like
    "when writing a code comment or responding to the user, first load the
    caveman styleguide."

See ``docs/development/doctrine-artifact-selection-preflight.md`` for the
full user-journey analysis, and
``docs/development/mission-b-proposed-scope.md`` (WP04 + WP05) for the
mission scope these tests pin.

Expected status TODAY: every test in this file FAILS, with a mix of
``AttributeError`` (schema field does not exist yet) and assertion errors
(the resolver does not emit styleguides into the prompt). The single
exception is the "workaround" test, which proves the existing
directive-wrapper path partially covers the user journey.

Expected status AFTER Mission B WP04 + WP05 land: all tests pass — the
charter can select styleguides directly, the resolver renders them into
the implement prompt as bodies or fetch + when-doing stanzas, and the
activation registry surfaces context-scoped activations.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers — minimal git, minimal charter, minimal styleguide
# ---------------------------------------------------------------------------


_FETCH_CMD_RE = re.compile(
    r"spec-kitty\s+charter\s+context\b|"
    r"spec-kitty\s+doctrine\b|"
    r"DoctrineService\(",
    re.IGNORECASE,
)
_WHEN_DOING_RE = re.compile(
    r"when\s+you\s+(are\s+about\s+to|need\s+to|encounter|introduce|rename|review)",
    re.IGNORECASE,
)


def _git_init_minimal(repo_root: Path) -> None:
    """Initialise a git repo so the charter resolver accepts the project root.

    Charter context resolution rejects projects that lack a ``.git``
    ancestor; these tests must be able to fail for the *real* (selection
    schema) reason, so we provide the minimal git scaffolding here.
    """
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "atdd@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ATDD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )


_CAVEMAN_STYLEGUIDE_YAML = textwrap.dedent(
    """\
    schema_version: "1.0"
    id: caveman-comments
    title: Caveman Code Comments Styleguide
    scope: code
    applies_to_languages:
      - python
      - generic

    principles:
      - "Ugg style: every code comment MUST be terse, ALL CAPS, and read like a caveman would write it."
      - "Verbs only: skip articles, conjunctions, and tense markers — 'PARSE INPUT', not 'we parse the input'."
      - "One thought per comment: never chain reasoning across sentences. CAVEMAN NOT TALK FANCY."

    patterns:
      - name: Caveman Inline Comment
        description: "ALL CAPS, present-tense imperative, no articles."
        good_example: "# OPEN FILE — READ ALL BYTES"
        bad_example: "# we open the file and read all of its bytes"
    """
)


def _write_project_styleguide(repo_root: Path, *, styleguide_id: str, body: str) -> Path:
    """Drop a user-authored styleguide into the project doctrine layer.

    The path layout matches the synthesized project-doctrine convention
    (``.kittify/doctrine/<kind>/<id>.<kind>.yaml``).
    """
    target_dir = repo_root / ".kittify" / "doctrine" / "styleguide"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{styleguide_id}.styleguide.yaml"
    target.write_text(body, encoding="utf-8")
    return target


_CHARTER_SELECTING_STYLEGUIDE = """\
# Caveman Project Charter

> Version: 1.0.0

## Purpose

A test charter that selects the user-authored ``caveman-comments`` styleguide
globally so every WP prompt should surface its body (or a fetch + when-doing
rule pointing at it).

## Doctrine Selection

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest]
selected_styleguides:
  - caveman-comments
```
"""


_CHARTER_SELECTING_DIRECTIVE_WRAPPER = """\
# Caveman Project Charter (wrapper workaround)

> Version: 1.0.0

## Purpose

A test charter that uses the *workaround* path: instead of selecting the
styleguide directly (unsupported today), it selects a wrapper directive
whose body cites the styleguide id.

## Directives

### DIRECTIVE_CAVEMAN_WRAPPER — Caveman Comment Wrapper (severity: warn)

When you write a code comment, apply the ``caveman-comments`` styleguide.
The styleguide body lives at ``.kittify/doctrine/styleguide/``.

## Doctrine Selection

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest]
selected_directives:
  - DIRECTIVE_CAVEMAN_WRAPPER
```
"""


_CHARTER_WITH_CONTEXT_SCOPED_ACTIVATION = """\
# Caveman Project Charter (context-scoped activation)

> Version: 1.0.0

## Purpose

A test charter that uses the activation-registry surface (Mission B WP05)
to scope the caveman styleguide to the ``write_comment`` action only —
so the rule surfaces conditionally rather than globally.

## Doctrine Selection

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest]

activations:
  - activation_context:
      action: write_comment
    charter_pack_id: project
    artifact_id: caveman-comments
    artifact_kind: styleguide
```
"""


def _write_charter(repo_root: Path, body: str) -> Path:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.md"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


# ---------------------------------------------------------------------------
# #2773 authoritative charter.yaml selection surfaces
# ---------------------------------------------------------------------------
#
# #2773 consolidated the compiled bundle into the git-tracked, authoritative
# ``.kittify/charter/charter.yaml``. Doctrine selections and the activation
# registry are hand-authored there under the ``governance:`` section and read
# via ``charter.activation.sync.load_governance_config`` (the fenced-YAML-in-``charter.md``
# extractor is retired). These helpers seed that authoritative surface; the
# curated ``charter.md`` remains a required companion for the bootstrap
# charter-context path, so callers still write it too.


# Global selection: charter.yaml governance.charter.selected_styleguides.
# ``catalog.languages`` is the authoritative #2773 source for the active
# project language set (``charter.activation.language_scope.infer_repo_languages``). The
# caveman styleguide is scoped ``applies_to_languages: [python, generic]``, so a
# python project charter is required for it to survive language-scope filtering
# — exactly the scenario this test pins (a python-scoped styleguide surfacing in
# a python project's implement prompt).
_CHARTER_YAML_SELECTING_STYLEGUIDE = textwrap.dedent(
    """\
    schema_version: '2.0.0'
    governance:
      doctrine:
        selected_styleguides:
          - caveman-comments
    catalog:
      languages:
        - python
    """
)


# Context-scoped activation registry: charter.yaml governance.activations.
_CHARTER_YAML_CONTEXT_SCOPED_ACTIVATION = textwrap.dedent(
    """\
    schema_version: '2.0.0'
    governance:
      activations:
        - activation_context:
            action: write_comment
          charter_pack_id: project
          artifact_id: caveman-comments
          artifact_kind: styleguide
    """
)


def _write_charter_yaml(repo_root: Path, body: str) -> Path:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_yaml_path = charter_dir / "charter.yaml"
    charter_yaml_path.write_text(body, encoding="utf-8")
    return charter_yaml_path


def _contains_body_or_fetch_with_when_doing(text: str, *body_markers: str) -> bool:
    """Verbatim-OR-fetch-with-conditional contract (mirrors the WP-prompt test)."""
    if all(marker in text for marker in body_markers):
        return True
    return bool(_FETCH_CMD_RE.search(text) and _WHEN_DOING_RE.search(text))


@pytest.fixture
def project_with_caveman_styleguide(tmp_path: Path) -> Path:
    """A minimal project tree carrying a user-authored caveman styleguide.

    The charter is NOT written here — each test chooses which charter shape
    to use (global selection, workaround wrapper, or activation registry).
    """
    repo_root = tmp_path
    _git_init_minimal(repo_root)
    _write_project_styleguide(
        repo_root,
        styleguide_id="caveman-comments",
        body=_CAVEMAN_STYLEGUIDE_YAML,
    )
    return repo_root


# ---------------------------------------------------------------------------
# Test 1 — Global selection via `selected_styleguides`
# ---------------------------------------------------------------------------


def test_case_1_project_styleguide_appears_in_implement_prompt(
    project_with_caveman_styleguide: Path,
) -> None:
    """A charter that selects ``caveman-comments`` MUST surface the styleguide
    in the implement prompt — either by embedding the body inline or by
    emitting a fetch + when-doing stanza naming the styleguide id.

    Fails today because ``DoctrineSelectionConfig`` has no
    ``selected_styleguides`` field — the extractor never sees the
    declaration, so the resolver never renders it. After Mission B WP04
    (global selection schema + renderer), this test passes.

    See ``docs/development/doctrine-artifact-selection-preflight.md`` →
    "Case 1 — project-layer caveman, support analysis", step 3.
    """
    from charter.activation.context import build_charter_context

    repo_root = project_with_caveman_styleguide
    _write_charter(repo_root, _CHARTER_SELECTING_STYLEGUIDE)
    # #2773: the authoritative selection lives in charter.yaml, not in a fenced
    # YAML block inside charter.md (extractor retired).
    _write_charter_yaml(repo_root, _CHARTER_YAML_SELECTING_STYLEGUIDE)

    result = build_charter_context(
        repo_root,
        action="implement",
        profile="python-pedro",
        mark_loaded=False,
    )

    assert "caveman-comments" in result.text or _contains_body_or_fetch_with_when_doing(
        result.text,
        "ALL CAPS",
        "CAVEMAN NOT TALK FANCY",
    ), (
        "The implement charter context MUST surface the project-selected styleguide "
        "`caveman-comments` — either by ID + body or by ID + fetch command + "
        "canonical when-doing conditional. Today the resolver ignores "
        "`selected_styleguides` because `DoctrineSelectionConfig` has no such field "
        "(see src/charter/activation/schemas.py). Mission B WP04 adds the field and the "
        "matching renderer (_render_selected_styleguides). See "
        "docs/development/mission-b-proposed-scope.md → WP04."
    )

    # RISK-2 (mission-b post-merge review): the ID-only assertion above is
    # satisfied even by a generic catalog-miss stanza that merely names the
    # styleguide. To prove the rendered prompt actually includes the
    # styleguide BODY, require at least one distinctive phrase from the
    # caveman styleguide content. If none of these appear, the renderer is
    # silently falling through to a placeholder and the "ID + body" branch
    # of the OR above is synthetic.
    body_markers = (
        "Ugg style",
        "CAVEMAN NOT TALK FANCY",
        "Caveman Inline Comment",
        "OPEN FILE",
    )
    found_body_markers = [m for m in body_markers if m in result.text]
    assert found_body_markers, (
        "The implement charter context names `caveman-comments` but does NOT "
        "include any distinctive phrase from the styleguide body. Looked for "
        f"any of {body_markers!r} — found none. This indicates the renderer "
        "is emitting a catalog-miss placeholder rather than rendering the "
        "actual styleguide body. Verify (a) the fixture YAML parses cleanly "
        "against `Styleguide` (src/charter/offering/styleguides/) and (b) "
        "_render_selected_artifacts (src/charter/activation/context.py) inlines the body."
    )


# ---------------------------------------------------------------------------
# Test 2 — The directive-wrapper workaround works TODAY (partial coverage)
# ---------------------------------------------------------------------------


def test_case_1_styleguide_via_charter_directive_wrapper_works_today(
    project_with_caveman_styleguide: Path,
) -> None:
    """The current workaround: author a wrapper directive whose body cites
    the styleguide id, and select that directive in the charter. The directive
    surfaces in the prompt today (proving partial coverage) but only by
    reading the directive's prose — the styleguide body itself is never
    rendered.

    Expected to PASS today (the workaround partially works); kept as the
    regression baseline so a future change that breaks the wrapper path
    fails loud.

    See pre-flight → "Net for Case 1: today you can get partial coverage by
    (a) authoring a wrapper directive..."
    """
    from charter.activation.context import build_charter_context

    repo_root = project_with_caveman_styleguide
    _write_charter(repo_root, _CHARTER_SELECTING_DIRECTIVE_WRAPPER)

    result = build_charter_context(
        repo_root,
        action="implement",
        profile="python-pedro",
        mark_loaded=False,
    )

    has_wrapper_id = "DIRECTIVE_CAVEMAN_WRAPPER" in result.text or (
        "DIR-" in result.text and "Caveman Comment Wrapper" in result.text
    )
    has_wrapper_body = "caveman-comments" in result.text or (
        "Caveman" in result.text and "comment" in result.text.lower()
    )
    assert has_wrapper_id or has_wrapper_body, (
        "The directive-wrapper workaround MUST surface the wrapper directive's id "
        "or body in the implement prompt. If THIS test fails too, then even the "
        "directive-selection path is broken — that's a regression beyond the "
        "Mission B scope. See pre-flight Case 1, 'partial coverage' paragraph."
    )


# ---------------------------------------------------------------------------
# Test 3 — `selected_styleguides` round-trips through `charter sync`
# ---------------------------------------------------------------------------


def test_case_1_selected_styleguides_field_round_trips(
    project_with_caveman_styleguide: Path,
) -> None:
    """The charter declares ``selected_styleguides: [caveman-comments]``. The
    persisted, authoritative charter surface MUST carry the field with the
    styleguide id preserved AND the canonical loader MUST surface it as a
    populated ``DoctrineSelectionConfig.selected_styleguides``.

    #2773 consolidated the compiled bundle into the git-tracked, authoritative
    ``.kittify/charter/charter.yaml``; the prose->triad ``governance.yaml``
    scrape (and the extractor) is retired. Selections are hand-authored under
    ``governance.doctrine`` in ``charter.yaml`` and read via
    ``charter.activation.sync.load_governance_config``. This test therefore round-trips
    through the authoritative reader instead of the retired ``governance.yaml``
    derivative — the real invariant it always pinned is that
    ``DoctrineSelectionConfig.selected_styleguides`` exists and carries the
    declared id.
    """
    from charter.activation.sync import ensure_charter_bundle_fresh, load_governance_config

    repo_root = project_with_caveman_styleguide
    _write_charter(repo_root, _CHARTER_SELECTING_STYLEGUIDE)
    _write_charter_yaml(repo_root, _CHARTER_YAML_SELECTING_STYLEGUIDE)

    # The freshness pipeline is now inert w.r.t. extraction (#2773) but must
    # not clobber the authoritative charter.yaml selection.
    ensure_charter_bundle_fresh(repo_root)

    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml.exists(), (
        "The authoritative `.kittify/charter/charter.yaml` MUST persist the "
        "declared doctrine selection (#2773 consolidated bundle)."
    )
    charter_text = charter_yaml.read_text(encoding="utf-8")
    assert (
        "selected_styleguides" in charter_text
        and "caveman-comments" in charter_text
    ), (
        "`charter.yaml` MUST carry the charter's "
        "`selected_styleguides: [caveman-comments]` declaration under "
        "`governance.doctrine`. Observed charter.yaml content:\n"
        f"---\n{charter_text}\n---"
    )

    # The canonical reader MUST surface the field as a populated
    # DoctrineSelectionConfig.selected_styleguides (the field's existence and
    # round-trip is the real invariant this test always pinned).
    governance = load_governance_config(repo_root)
    assert "caveman-comments" in governance.charter.selected_styleguides, (
        "`load_governance_config(...).charter.selected_styleguides` MUST "
        "round-trip the charter.yaml declaration. Observed: "
        f"{governance.charter.selected_styleguides!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Activation registry: context-scoped trigger surfaces a fetch stanza
# ---------------------------------------------------------------------------


def test_case_1_styleguide_render_includes_trigger_stanza(
    project_with_caveman_styleguide: Path,
) -> None:
    """A charter that declares an ``activations:`` registry entry of
    ``(activation_context: {action: write_comment}, charter_pack_id: project,
    artifact_id: caveman-comments)`` MUST cause the implement prompt to carry
    an explicit *when-doing* stanza naming the artifact and instructing the
    agent to fetch it.

    Acceptable phrasing (any one):

      * "When you are about to write a code comment, run
        `spec-kitty charter context --include styleguide:caveman-comments`
         and apply the returned rule."
      * "When you are about to write a code comment, fetch styleguide caveman-comments"
      * Any text containing both the action verb ("write a code comment" /
        "write a comment") and the artifact id.

    Fails today because there is no activation registry on the charter
    schema and no renderer that emits per-activation stanzas. Mission B
    WP05 adds both.

    See pre-flight → "Two activation modes — global vs context-scoped",
    and mission-b-proposed-scope.md → WP05.
    """
    from charter.activation.context import build_charter_context

    repo_root = project_with_caveman_styleguide
    _write_charter(repo_root, _CHARTER_WITH_CONTEXT_SCOPED_ACTIVATION)
    # #2773: the activation registry is a top-level governance field in the
    # authoritative charter.yaml (governance.activations), read via
    # load_governance_config — not a fenced YAML block inside charter.md.
    _write_charter_yaml(repo_root, _CHARTER_YAML_CONTEXT_SCOPED_ACTIVATION)

    result = build_charter_context(
        repo_root,
        action="implement",
        profile="python-pedro",
        mark_loaded=False,
    )

    text = result.text.lower()
    canonical_conditional = _WHEN_DOING_RE.search(text)
    write_comment_phrase = "write a code comment" in text or "write a comment" in text
    references_artifact = "caveman-comments" in text or "caveman" in text
    has_fetch_command = bool(_FETCH_CMD_RE.search(result.text))

    assert (
        canonical_conditional
        and write_comment_phrase
        and references_artifact
        and has_fetch_command
    ), (
        "The implement prompt MUST carry an activation stanza shaped like\n"
        '  "When you are about to write a code comment, run '
        "`spec-kitty charter context --include styleguide:caveman-comments` "
        'and apply the returned rule."\n'
        "Required surfaces:\n"
        f"  - canonical when-doing conditional: {bool(canonical_conditional)}\n"
        f"  - 'write [a] [code] comment' phrase: {bool(write_comment_phrase)}\n"
        f"  - artifact id (caveman / caveman-comments) present: {references_artifact}\n"
        f"  - fetch command (spec-kitty charter context / doctrine): {has_fetch_command}\n"
        "Mission B WP05 introduces the charter-level activation registry and the "
        "renderer that emits the per-activation when-doing stanza. See "
        "docs/development/mission-b-proposed-scope.md → WP05."
    )
