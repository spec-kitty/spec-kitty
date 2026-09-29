"""ATDD acceptance spec — Case 2 (org-pack doctrine artifact lifecycle).

These tests are the executable specification for Mission B (charter-mediated
doctrine selection), Case 2 from the pre-flight:

    Same artifact as Case 1, but distributed via an organisational charter
    (org id ``very-serious-developers``) that team members add to their
    ``.kittify/config.yaml``. Same expected prompt behaviour.

See ``docs/development/doctrine-artifact-selection-preflight.md`` →
"Case 2 — org-layer caveman, support analysis", and
``docs/development/mission-b-proposed-scope.md`` (WP04) for the mission
scope these tests pin.

Expected status TODAY: every test in this file FAILS. The org-pack
plumbing already works (Mission A wired the three-layer resolver and
``apply_org_charter_to_interview`` for directives) but the
per-styleguide selection / requirement schema does NOT exist yet, so
the styleguide never reaches the consumer's prompt.

Expected status AFTER Mission B WP04 lands: ``OrgCharterPolicy`` gains
``required_styleguides`` (and the other ``required_<kind>`` fields),
``apply_org_charter_to_interview`` unions them into project selection,
and the consumer's implement prompt surfaces the org-distributed
caveman styleguide just like a project-selected one would.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init_minimal(repo_root: Path) -> None:
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
    title: Caveman Code Comments Styleguide (org-distributed)
    scope: code
    applies_to_languages:
      - python
      - generic

    principles:
      - "Ugg style: every code comment MUST be terse, ALL CAPS, and read like a caveman would write it."
      - "ORG MANDATE: caveman speech only in comments."

    patterns:
      - name: Caveman Inline Comment
        description: "ALL CAPS, present-tense imperative, no articles."
        good_example: "# OPEN FILE — READ ALL BYTES"
        bad_example: "# we open the file and read all of its bytes"
    """
)


_BUILTIN_OVERRIDE_STYLEGUIDE_YAML = textwrap.dedent(
    """\
    schema_version: "1.0"
    id: python-conventions
    title: Org-overridden python-conventions styleguide
    scope: code
    applies_to_languages:
      - python

    principles:
      - "Org override: this declaration shadows the built-in python-conventions styleguide and MUST emit DoctrineLayerCollisionWarning."
    """
)


def _build_org_pack(
    org_root: Path,
    *,
    pack_name: str,
    required_styleguides: list[str] | None = None,
    styleguides: dict[str, str] | None = None,
) -> Path:
    """Create an on-disk org doctrine pack with optional styleguides + org-charter.

    Returns the pack's local_path (a directory on disk).
    """
    pack_dir = org_root / pack_name
    (pack_dir / "styleguides").mkdir(parents=True, exist_ok=True)
    for sg_id, body in (styleguides or {}).items():
        (pack_dir / "styleguides" / f"{sg_id}.styleguide.yaml").write_text(
            body, encoding="utf-8"
        )
    if required_styleguides is not None:
        org_charter_body = (
            "schema_version: \"1\"\n"
            f"org_name: {pack_name}\n"
            "required_styleguides:\n"
            + "\n".join(f"  - {sid}" for sid in required_styleguides)
            + "\n"
        )
        (pack_dir / "org-charter.yaml").write_text(org_charter_body, encoding="utf-8")
    return pack_dir


def _write_consumer_pack_config(repo_root: Path, *, pack_name: str, local_path: Path) -> None:
    """Write the consumer's .kittify/config.yaml pointing at one pack."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        textwrap.dedent(
            f"""\
            doctrine:
              org:
                packs:
                  - name: {pack_name}
                    local_path: {local_path}
            """
        ),
        encoding="utf-8",
    )


_CONSUMER_CHARTER_MINIMAL = """\
# Consumer Project Charter

> Version: 1.0.0

## Purpose

A consumer charter that does NOT itself select the caveman styleguide —
the styleguide must reach the consumer's prompt purely through the org
charter's ``required_styleguides`` field.

## Doctrine Selection

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest]
```
"""


def _write_charter(repo_root: Path, body: str = _CONSUMER_CHARTER_MINIMAL) -> Path:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.md"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


# ---------------------------------------------------------------------------
# Test 1 — Org-pack styleguide appears in consumer prompt
# ---------------------------------------------------------------------------


def test_case_2_org_pack_styleguide_appears_in_consumer_prompt(tmp_path: Path) -> None:
    """A consumer project that configures an org pack with
    ``required_styleguides: [caveman-comments]`` MUST receive the styleguide
    in its implement prompt — with org-layer provenance — even when the
    consumer's own charter does not name the styleguide.

    Fails today because ``OrgCharterPolicy`` does not declare
    ``required_styleguides`` (only ``required_directives``), so the pack's
    declaration is dropped at parse time. Mission B WP04 adds the field
    and unions it into the project selection via
    ``apply_org_charter_to_interview`` (and the resolver renders it).
    """
    from charter.activation.context import build_charter_context

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _git_init_minimal(consumer)
    _write_charter(consumer)

    org_root = tmp_path / "org-doctrine"
    pack_path = _build_org_pack(
        org_root,
        pack_name="very-serious-developers",
        required_styleguides=["caveman-comments"],
        styleguides={"caveman-comments": _CAVEMAN_STYLEGUIDE_YAML},
    )
    _write_consumer_pack_config(consumer, pack_name="very-serious-developers", local_path=pack_path)

    result = build_charter_context(
        consumer,
        action="implement",
        profile="python-pedro",
        mark_loaded=False,
    )

    has_styleguide_id = "caveman-comments" in result.text
    has_org_provenance = (
        '"source":"org"' in result.text.replace(" ", "")
        or "source: org" in result.text
        or "(org)" in result.text
        or "very-serious-developers" in result.text
    )

    assert has_styleguide_id, (
        "Consumer prompt MUST cite the org-distributed styleguide "
        "`caveman-comments`. Today the org-pack's `required_styleguides` "
        "field is dropped at parse time because `OrgCharterPolicy` does not "
        "declare it (see src/specify_cli/doctrine/org_charter.py). "
        "Mission B WP04 adds `required_styleguides` to `OrgCharterPolicy` "
        "and teaches `apply_org_charter_to_interview` to union the field "
        "into the project selection."
    )
    assert has_org_provenance, (
        "When the styleguide is org-distributed, the prompt MUST disclose "
        "the org provenance (source=org or the pack name) so the operator "
        "can audit which pack contributed the rule. Today there is no "
        "provenance because the artifact never reaches the renderer. "
        "Mission B WP04 carries the source layer through the renderer."
    )


# ---------------------------------------------------------------------------
# Test 2 — `required_styleguides` pre-fills the in-memory interview
# ---------------------------------------------------------------------------


def test_case_2_required_styleguides_in_org_charter_pre_fills(tmp_path: Path) -> None:
    """``apply_org_charter_to_interview`` MUST union org-defined
    ``required_styleguides`` into ``interview_data.selected_styleguides``,
    the same way it does for ``required_directives`` today.

    Fails today because:
      * ``OrgCharterPolicy`` has no ``required_styleguides`` field.
      * ``CharterInterview`` has no ``selected_styleguides`` attribute.
      * ``apply_org_charter_to_interview`` only handles directives.

    After Mission B WP04: schema field exists, interview data carries
    the selection field, and the union runs.
    """
    from specify_cli.doctrine.org_charter import apply_org_charter_to_interview

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _git_init_minimal(consumer)

    org_root = tmp_path / "org-doctrine"
    pack_path = _build_org_pack(
        org_root,
        pack_name="very-serious-developers",
        required_styleguides=["caveman-comments"],
        styleguides={"caveman-comments": _CAVEMAN_STYLEGUIDE_YAML},
    )
    _write_consumer_pack_config(consumer, pack_name="very-serious-developers", local_path=pack_path)

    # Construct an interview shape that mirrors today's CharterInterview surface.
    # The assertion will fail because today's CharterInterview has no
    # ``selected_styleguides`` field; Mission B WP04 must add it.
    class _FakeInterview:
        def __init__(self) -> None:
            self.answers: dict[str, str] = {}
            self.selected_directives: list[str] = []
            self.selected_styleguides: list[str] = []  # the field WP04 must add

    interview = _FakeInterview()
    messages = apply_org_charter_to_interview(interview, consumer)

    assert "caveman-comments" in interview.selected_styleguides, (
        "`apply_org_charter_to_interview` MUST union the org pack's "
        "`required_styleguides` into `interview_data.selected_styleguides`. "
        "Today the function only handles `required_directives`; the "
        "`required_styleguides` field is dropped at parse time (the org "
        "charter schema does not declare it).\n"
        f"Observed selected_styleguides: {interview.selected_styleguides!r}\n"
        f"Apply messages: {messages!r}\n"
        "Fix lives in Mission B WP04 — extend the schema in "
        "src/specify_cli/doctrine/org_charter.py:OrgCharterPolicy, "
        "extend CharterInterview in src/charter/activation/interview.py, and extend "
        "apply_org_charter_to_interview to union the new field."
    )


# ---------------------------------------------------------------------------
# Test 3 — Collision warning for org styleguide vs built-in id
# ---------------------------------------------------------------------------


def test_case_2_org_styleguide_collision_with_builtin_warns(tmp_path: Path) -> None:
    """An org pack that ships a styleguide whose id collides with a built-in
    styleguide (e.g. ``python-conventions``) MUST emit
    ``DoctrineLayerCollisionWarning`` with the styleguide id and the
    artifact kind in the message.

    Mission A wired collision warnings for the directive kind. The contract
    pinned here is that the same surface extends to styleguides.

    May fail today if styleguide-layer collisions are silent (no warning
    fired). Mission B WP04 must verify / extend the collision pipeline for
    every artifact kind that becomes per-artifact selectable.
    """
    from charter.offering.base import DoctrineLayerCollisionWarning
    from charter.offering.service import DoctrineService

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _git_init_minimal(consumer)
    _write_charter(consumer)

    org_root = tmp_path / "org-doctrine"
    pack_path = _build_org_pack(
        org_root,
        pack_name="very-serious-developers",
        styleguides={"python-conventions": _BUILTIN_OVERRIDE_STYLEGUIDE_YAML},
    )
    _write_consumer_pack_config(
        consumer, pack_name="very-serious-developers", local_path=pack_path
    )

    # No explicit built-in root: the styleguide repository self-resolves
    # the shipped ``packs/built-in/styleguides/`` tier, which really ships
    # ``python-conventions`` -- the collision this test asserts requires
    # the built-in styleguide to actually load (a stale ``src/doctrine``
    # root loads zero styleguides, so nothing could ever collide).
    service = DoctrineService(
        project_root=consumer / ".kittify" / "doctrine",
        org_roots=[pack_path],
    )
    # Force the styleguides repository to load — the warning fires at load time
    # (repositories load lazily, so construction above emits nothing).
    with pytest.warns(DoctrineLayerCollisionWarning) as warning_records:
        _ = list(service.styleguides.all())

    messages = [str(record.message) for record in warning_records]
    matching = [
        m for m in messages
        if "python-conventions" in m and ("styleguide" in m.lower())
    ]
    assert matching, (
        "An org-layer styleguide that collides with a built-in id MUST emit "
        "DoctrineLayerCollisionWarning naming both the id (`python-conventions`) "
        "and the artifact kind (`styleguide`). Observed warnings:\n"
        + "\n".join(f"  - {m}" for m in messages)
        + "\n\n"
        "If no warning fires at all, the styleguide repository never reaches "
        "the collision pipeline. If a warning fires but mentions only the id "
        "(no kind), the message format is incomplete and operators cannot tell "
        "which artifact kind collided. Mission B WP04 must extend the "
        "collision surface to every kind that becomes per-artifact selectable."
    )


# ---------------------------------------------------------------------------
# Test 4 — Consumer references a pack that isn't on disk → loud error
# ---------------------------------------------------------------------------


def test_case_2_consumer_without_fetched_pack_fails_loudly(tmp_path: Path) -> None:
    """A consumer that configures an org pack whose ``local_path`` does not
    exist on disk (e.g. ``doctrine fetch`` has not run, or the path is a
    typo) MUST raise a clear, actionable error when context resolution
    runs. Silent skip is the failure mode this test forbids.

    Today the pack-registry loader silently filters out missing paths
    during context resolution (per Mission A's policy). This test pins
    the *required* future policy: a charter that references a pack must
    either find the pack OR fail loud — never carry on as if the pack
    declaration were absent.

    See pre-flight edge case 9 — "Caveman in org-charter.yaml but consumer
    project lacks the pack on disk."
    """
    from charter.activation.context import build_charter_context

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _git_init_minimal(consumer)
    _write_charter(consumer)

    # Point the consumer at a pack path that does NOT exist.
    missing_pack_path = tmp_path / "this-pack-was-never-fetched"
    _write_consumer_pack_config(
        consumer,
        pack_name="missing-pack",
        local_path=missing_pack_path,
    )

    # We expect a loud error mentioning the missing path or the pack name.
    # Either an exception OR a result whose text carries a hard-error
    # diagnostic is acceptable; silent success is the failure mode.
    raised_loudly = False
    error_text = ""
    try:
        result = build_charter_context(
            consumer,
            action="implement",
            profile="python-pedro",
            mark_loaded=False,
        )
    except Exception as exc:  # noqa: BLE001 — we want to inspect any exception
        raised_loudly = True
        error_text = str(exc)
    else:
        # Accept a result whose text carries a clear hard-error diagnostic.
        diagnostic_re = re.compile(
            r"(pack.*not\s+found|missing\s+pack|local_path.*does\s+not\s+exist|"
            r"fetch.*pack)",
            re.IGNORECASE,
        )
        if diagnostic_re.search(result.text):
            raised_loudly = True
            error_text = result.text

    assert raised_loudly, (
        "Consumer configured an org pack whose `local_path` "
        f"`{missing_pack_path}` does NOT exist on disk. Context resolution "
        "MUST fail loudly — either by raising or by emitting a clear "
        "diagnostic in the rendered text mentioning the missing pack / "
        "path. Today the resolver silently skips missing packs (per "
        "Mission A's pack-registry loader policy), which produces "
        "silently-incorrect prompts. Mission B must pin the policy: a "
        "charter that *references* a pack must either find it or fail loud.\n"
        f"Observed result text:\n---\n{error_text or '(no error and no diagnostic)'}\n---"
    )
