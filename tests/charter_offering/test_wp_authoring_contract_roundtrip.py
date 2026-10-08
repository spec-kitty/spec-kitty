"""Golden round-trip ratchet for the WP-authoring frontmatter contract (#2220 + #2221).

The WP-frontmatter ownership contract is encoded in three independent places that
historically drifted apart:

1. Doctrine prose — ``mission-steps/software-dev/tasks/guidelines.md``, the sole
   owner of tasks guidelines (#5202; the former ``actions/`` runtime copy was
   retired and is no longer read by the loader).
2. The authoring template — ``software-dev/templates/task-prompt-template.md``
   frontmatter, plus (since #3795) the ``documentation`` mission's copy, which
   had drifted and omitted the ownership keys and the REQUIRED profile-load
   section that ``/spec-kitty.tasks`` pins for every mission type.
3. The ownership validator — ``specify_cli.ownership.validation`` whose
   ``_CODE_PREFIXES = ("src/", "tests/")`` is **repo-root-relative**.

Per C-004 the *code* (the validator) is the single source of authority for the
path shape: ``owned_files`` must be **repo-root-relative**, never absolute. This
module is the SSOT ratchet that locks the prose and template to that authority so
they cannot silently re-diverge:

- A mandatory prose ratchet pins the single-owner ``guidelines.md`` copy to
  repo-root-relative guidance and forbids the literal ``absolute path`` drift
  vector.
- A golden round-trip drives the REAL ownership validator + finalize resolve path
  (read from the on-disk template, not a hand-written fixture): a WP authored with
  repo-relative ``owned_files`` passes; an absolute-path entry fails consistently.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.frontmatter import read_frontmatter
from specify_cli.ownership.frontmatter_source import (
    InMemoryFrontmatterSource,
    resolve_wp_manifests,
)
from specify_cli.ownership.validation import validate_glob_matches, validate_ownership
from specify_cli.status import WPMetadata
from tests.charter_offering.conftest import BUILT_IN_MISSIONS_ROOT, REPO_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

# --- The three drifting encodings, pinned to disk -------------------------------

# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated missions/ from src/charter/offering/missions (nested under
# OFFERING_SOURCE_ROOT) to packs/built-in/missions (BUILT_IN_MISSIONS_ROOT,
# see tests/charter_offering/conftest.py).
SOFTWARE_DEV_ROOT = BUILT_IN_MISSIONS_ROOT / "software-dev"

GUIDELINES_STEPS = (
    BUILT_IN_MISSIONS_ROOT
    / "mission-steps"
    / "software-dev"
    / "tasks"
    / "guidelines.md"
)
TASK_PROMPT_TEMPLATE = SOFTWARE_DEV_ROOT / "templates" / "task-prompt-template.md"
DOCUMENTATION_TASK_PROMPT_TEMPLATE = (
    BUILT_IN_MISSIONS_ROOT / "documentation" / "templates" / "task-prompt-template.md"
)
RESEARCH_TASK_PROMPT_TEMPLATE = (
    BUILT_IN_MISSIONS_ROOT / "research" / "templates" / "task-prompt-template.md"
)

# Every bundled mission whose WP prompts /spec-kitty.tasks authors from a
# task-prompt-template.md must declare the same ownership contract (#3795: the
# documentation copy had none of it while software-dev had all of it; #4060: the
# research copy had none of it either). Add a mission here as soon as it ships a
# task-prompt-template.md, so the ratchet covers every shipped copy.
TASK_PROMPT_TEMPLATES = {
    "software-dev": TASK_PROMPT_TEMPLATE,
    "documentation": DOCUMENTATION_TASK_PROMPT_TEMPLATE,
    "research": RESEARCH_TASK_PROMPT_TEMPLATE,
}

# The four ownership-contract keys a template-authored WP must self-declare so it
# validates + finalizes on the first pass.
OWNERSHIP_CONTRACT_KEYS = (
    "owned_files",
    "authoritative_surface",
    "execution_mode",
    "create_intent",
)

# The drift vector the prose ratchet forbids (C-004: code is repo-relative).
FORBIDDEN_PROSE_TOKEN = "absolute path"
# The instruction the prose must now carry instead.
REQUIRED_PROSE_TOKEN = "repo-root-relative"

# Production-shaped, repo-root-relative owned_files for the authored WP. Both are
# real existing files under the authoritative surface, so the surface-prefix check
# and the literal-path glob check both resolve them.
AUTHORED_AUTHORITATIVE_SURFACE = "src/specify_cli/ownership/"
AUTHORED_OWNED_FILES = (
    "src/specify_cli/ownership/validation.py",
    "src/specify_cli/ownership/models.py",
)
# A planned-new file modelled in create_intent (real-format repo-relative path).
AUTHORED_CREATE_INTENT = ("src/specify_cli/ownership/_roundtrip_probe.py",)

# Documentation-mission authored WP: the template's placeholders resolve to
# docs/ surfaces (execution_mode "planning_artifact" — planning prefixes are
# kitty-specs/ and docs/), so the round-trip probes use real files there.
DOC_AUTHORED_AUTHORITATIVE_SURFACE = "docs/architecture/"
DOC_AUTHORED_OWNED_FILES = (
    "docs/architecture/documentation-mission.md",
    "docs/architecture/README.md",
)
DOC_AUTHORED_CREATE_INTENT = ("docs/architecture/_roundtrip_probe.md",)

# The REQUIRED first body section of every task-prompt template
# (mission-steps/software-dev/tasks/prompt.md: "REQUIRED, must be the first
# body section ... See task-prompt-template.md for the exact block").
PROFILE_LOAD_SECTION_HEADING = "## ⚡ Do This First: Load Agent Profile"
# Frontmatter fields the profile-load block's placeholders resolve against.
PROFILE_LOAD_FIELDS = ("agent_profile", "role", "agent")


# --- T003 step 2: mandatory prose ratchet (pins the doctrine TEXT) ---------------


def test_guidelines_copy_instructs_repo_root_relative_owned_files() -> None:
    """The single-owner ``guidelines.md`` must instruct repo-root-relative owned_files.

    The validator is repo-root-relative (C-004); the prose must match it and must
    not carry the ``absolute path`` drift vector that contradicts the validator.
    ``mission-steps/software-dev/tasks/guidelines.md`` is the sole owner (#5202);
    the former ``actions/`` runtime copy was retired.
    """
    assert GUIDELINES_STEPS.exists(), f"missing doctrine copy: {GUIDELINES_STEPS}"
    text = GUIDELINES_STEPS.read_text(encoding="utf-8").lower()

    assert FORBIDDEN_PROSE_TOKEN not in text, (
        f"{GUIDELINES_STEPS} still instructs '{FORBIDDEN_PROSE_TOKEN}' owned_files — "
        "this contradicts the repo-root-relative ownership validator (C-004)."
    )
    assert REQUIRED_PROSE_TOKEN in text, (
        f"{GUIDELINES_STEPS} must instruct '{REQUIRED_PROSE_TOKEN}' owned_files paths "
        "to match the ownership validator."
    )


# --- T003 step 3: GREEN round-trip — drive the REAL validator from the template --


def _template_frontmatter() -> dict[str, Any]:
    """Read the on-disk task-prompt template frontmatter (raw mapping)."""
    frontmatter, _body = read_frontmatter(TASK_PROMPT_TEMPLATE)
    return dict(frontmatter)


def test_template_declares_ownership_contract_keys() -> None:
    """The on-disk template must declare all four ownership-contract keys.

    Read from disk (not fabricated) so the ratchet fails if the template omits a
    key — this forbids the ``template-exists``-by-fabrication anti-pattern.
    """
    frontmatter = _template_frontmatter()
    missing = [key for key in OWNERSHIP_CONTRACT_KEYS if key not in frontmatter]
    assert not missing, (
        f"task-prompt-template.md frontmatter omits ownership-contract keys: {missing}. "
        "A template-authored WP cannot validate + finalize on the first pass without them."
    )


def _authored_wp_from_template(owned_files: tuple[str, ...]) -> WPMetadata:
    """Build a WP as if authored from the on-disk template.

    Pulls ``execution_mode`` and ``authoritative_surface`` from the REAL template
    frontmatter (so the test fails if the template drops or mis-shapes them) and
    fills the placeholder ``owned_files``/``create_intent`` with the supplied
    production-shaped repo-relative paths — mirroring how an author completes the
    template before finalize.
    """
    frontmatter = _template_frontmatter()
    for key in OWNERSHIP_CONTRACT_KEYS:
        assert key in frontmatter, f"template must declare {key!r} before round-trip"

    return WPMetadata(
        work_package_id="WP01",
        title="WP-authoring contract round-trip probe",
        execution_mode=str(frontmatter["execution_mode"]),
        owned_files=list(owned_files),
        authoritative_surface=AUTHORED_AUTHORITATIVE_SURFACE,
        create_intent=list(AUTHORED_CREATE_INTENT),
    )


def test_template_authored_wp_passes_ownership_and_finalize_first_time() -> None:
    """A WP authored from the template with repo-relative owned_files validates.

    Drives the REAL resolve→validate seam (``resolve_wp_manifests`` →
    ``validate_ownership``) plus the finalize-time literal-path glob check, exactly
    as ``spec-kitty agent mission finalize-tasks`` does — not a structural
    template-exists assertion (C-006).
    """
    wp_meta = _authored_wp_from_template(AUTHORED_OWNED_FILES)
    source = InMemoryFrontmatterSource({"WP01": wp_meta})
    manifests = resolve_wp_manifests(source)
    assert "WP01" in manifests, "authored WP did not resolve to an ownership manifest"

    ownership_result = validate_ownership(manifests, {"WP01": []})
    assert ownership_result.passed, (
        f"repo-relative authored WP unexpectedly failed ownership validation: "
        f"{ownership_result.errors}"
    )

    create_intent = {"WP01": list(AUTHORED_CREATE_INTENT)}
    glob_result = validate_glob_matches(manifests, REPO_ROOT, create_intent=create_intent)
    assert glob_result.passed, (
        f"repo-relative authored WP failed the finalize literal-path glob check: "
        f"{glob_result.errors}"
    )


# --- T003 step 4: RED case — an absolute-path entry fails consistently -----------


def test_absolute_owned_files_entry_fails_validation_consistently() -> None:
    """An absolute ``owned_files`` path fails ownership validation, every run.

    Models the drift the contract forbids: the author used absolute paths. The
    only difference from the green case is the leading ``/abs/`` on every entry, so
    the failure is attributable to absoluteness alone. The repo-root-relative
    validator rejects them (an absolute path is not under the repo-relative
    authoritative_surface), so finalize would Exit(1) before lanes are written.
    Asserted across repeated runs to prove the failure is consistent, not
    order-dependent.
    """
    absolute_entries = tuple("/abs/" + path for path in AUTHORED_OWNED_FILES)
    wp_meta = _authored_wp_from_template(absolute_entries)

    for _ in range(3):
        source = InMemoryFrontmatterSource({"WP01": wp_meta})
        manifests = resolve_wp_manifests(source)
        result = validate_ownership(manifests, {"WP01": []})
        assert not result.passed, (
            "absolute owned_files paths were accepted by ownership validation — "
            "the repo-relative contract (C-004) is not enforced."
        )
        assert any(absolute_entries[0] in err for err in result.errors), (
            f"validation failed but the absolute path was not surfaced: {result.errors}"
        )


# --- #3795: mission-parity ratchet — documentation must match software-dev ------


@pytest.mark.parametrize("mission", sorted(TASK_PROMPT_TEMPLATES))
def test_task_prompt_template_declares_ownership_contract_keys(mission: str) -> None:
    """Every mapped mission's template must declare the ownership-contract keys.

    ``/spec-kitty.tasks`` applies the same finalize-tasks requirements regardless
    of mission type, so a template that omits the keys authors WPs that fail
    ``finalize-tasks --validate-only`` (or pass with inferred ownership). Read
    from disk (not fabricated) so the ratchet fails if a template omits a key.
    """
    frontmatter, _body = read_frontmatter(TASK_PROMPT_TEMPLATES[mission])
    missing = [key for key in OWNERSHIP_CONTRACT_KEYS if key not in frontmatter]
    assert not missing, (
        f"{mission} task-prompt-template.md frontmatter omits "
        f"ownership-contract keys: {missing}. A template-authored WP cannot "
        "validate + finalize on the first pass without them."
    )


@pytest.mark.parametrize("mission", sorted(TASK_PROMPT_TEMPLATES))
def test_task_prompt_template_carries_required_profile_load_section(mission: str) -> None:
    """Every mapped mission's template must carry the REQUIRED profile-load block.

    ``/spec-kitty.tasks`` marks ``## ⚡ Do This First: Load Agent Profile`` as
    REQUIRED and instructs the agent to "See ``task-prompt-template.md`` for the
    exact block" — the named file must actually carry it, and the frontmatter
    must declare the fields its placeholders resolve against (#3795: the
    documentation copy carried neither).
    """
    frontmatter, body = read_frontmatter(TASK_PROMPT_TEMPLATES[mission])
    assert PROFILE_LOAD_SECTION_HEADING in body, (
        f"{mission} task-prompt-template.md omits the REQUIRED "
        f"'{PROFILE_LOAD_SECTION_HEADING}' section that /spec-kitty.tasks pins."
    )
    missing_fields = [field for field in PROFILE_LOAD_FIELDS if field not in frontmatter]
    assert not missing_fields, (
        f"{mission} task-prompt-template.md omits profile-load frontmatter "
        f"fields {missing_fields} that the REQUIRED section references."
    )


def test_documentation_template_authored_wp_passes_ownership_and_finalize() -> None:
    """A documentation-mission WP authored from its template validates first time.

    Same seam as the software-dev green round-trip (``resolve_wp_manifests`` →
    ``validate_ownership`` → ``validate_glob_matches``), driven by the
    documentation template's real ``execution_mode``/``authoritative_surface``
    shape with production-shaped docs/ paths — proving the template's
    placeholder contract is completable, not just present.
    """
    frontmatter, _body = read_frontmatter(DOCUMENTATION_TASK_PROMPT_TEMPLATE)
    for key in OWNERSHIP_CONTRACT_KEYS:
        assert key in frontmatter, f"documentation template must declare {key!r}"

    wp_meta = WPMetadata(
        work_package_id="WP01",
        title="Documentation WP-authoring round-trip probe",
        execution_mode=str(frontmatter["execution_mode"]),
        owned_files=list(DOC_AUTHORED_OWNED_FILES),
        authoritative_surface=DOC_AUTHORED_AUTHORITATIVE_SURFACE,
        create_intent=list(DOC_AUTHORED_CREATE_INTENT),
    )
    source = InMemoryFrontmatterSource({"WP01": wp_meta})
    manifests = resolve_wp_manifests(source)
    assert "WP01" in manifests, "authored documentation WP did not resolve to a manifest"

    ownership_result = validate_ownership(manifests, {"WP01": []})
    assert ownership_result.passed, (
        f"documentation authored WP unexpectedly failed ownership validation: "
        f"{ownership_result.errors}"
    )

    glob_result = validate_glob_matches(
        manifests, REPO_ROOT, create_intent={"WP01": list(DOC_AUTHORED_CREATE_INTENT)}
    )
    assert glob_result.passed, (
        f"documentation authored WP failed the finalize literal-path glob check: "
        f"{glob_result.errors}"
    )
