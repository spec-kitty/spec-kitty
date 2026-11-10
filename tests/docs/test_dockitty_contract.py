"""Unit tests for ``scripts/docs/_dockitty_contract.py`` (#6929, #6931): slugs, publication, personas, history, frontmatter rules."""

from __future__ import annotations

import json
from kernel.clock import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts.docs import _dockitty_contract as contract
from scripts.docs._dockitty_contract import (
    DESCRIPTION_MAX,
    DOCKITTY_PIN,
    DOC_STATUSES,
    DOC_TYPES,
    EXCLUDED_FOLDERS,
    KINDS,
    NOT_A_DATE_MESSAGE,
    REQUIRED_FIELDS,
    body_of,
    format_instant,
    is_dated_adr,
    is_excluded,
    is_immutable,
    is_published,
    page_for_slug,
    parse_instant,
    persona_page,
    profile_of_persona_path,
    slug_of,
    split_frontmatter,
    validate_frontmatter,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("rel", "slug"),
    [
        ("guides/x.md", "guides/x"),
        ("adr/4.x/index.md", "adr/4.x"),
        ("architecture/README.md", "architecture"),
        ("index.md", ""),
        ("README.md", ""),
        ("guides/index-of-things.md", "guides/index-of-things"),
        ("Guides/Mixed.md", "Guides/Mixed"),
        ("guides/Readme.md", "guides"),
        ("guides/INDEX.md", "guides"),
    ],
)
def test_slug_of(rel: str, slug: str) -> None:
    assert slug_of(rel) == slug


@pytest.mark.parametrize(
    ("rel", "excluded"),
    [
        ("archive/x.md", True),
        ("reports/a/b.md", True),
        ("convergence/x.md", True),
        ("changelog/unreleased/1.fixed.md", True),
        ("archived/x.md", False),
        ("changelog/CHANGELOG.md", False),
        ("plans/archive/x.md", False),
    ],
)
def test_is_excluded(rel: str, excluded: bool) -> None:
    assert is_excluded(rel) is excluded


def test_excluded_folders_name_the_site_exclusions() -> None:
    assert EXCLUDED_FOLDERS == ("archive", "reports", "convergence", "changelog/unreleased")


@pytest.mark.parametrize(
    ("rel", "frontmatter", "published"),
    [
        ("guides/x.md", {"doc_status": "active"}, True),
        ("guides/x.md", {"doc_status": "deprecated"}, True),
        ("guides/x.md", {"doc_status": "draft"}, False),
        ("guides/x.md", {}, False),
        ("guides/x.md", {"doc_status": "proposal"}, True),
        ("archive/x.md", {"doc_status": "active"}, False),
    ],
)
def test_is_published(rel: str, frontmatter: dict[str, str], published: bool) -> None:
    assert is_published(rel, frontmatter) is published


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntitle: t\n---\n", encoding="utf-8")


def test_page_for_slug_prefers_file_then_readme_then_index(tmp_path: Path) -> None:
    _touch(tmp_path, "a.md")
    _touch(tmp_path, "b/README.md")
    _touch(tmp_path, "c/index.md")
    _touch(tmp_path, "index.md")
    assert page_for_slug(tmp_path, "a") == tmp_path / "a.md"
    assert page_for_slug(tmp_path, "b") == tmp_path / "b/README.md"
    assert page_for_slug(tmp_path, "c/") == tmp_path / "c/index.md"
    assert page_for_slug(tmp_path, "") == tmp_path / "index.md"
    assert page_for_slug(tmp_path, "missing") is None
    assert page_for_slug(tmp_path, "a/deeper") is None


def test_page_for_slug_finds_an_index_in_any_case(tmp_path: Path) -> None:
    _touch(tmp_path, "d/Readme.md")
    _touch(tmp_path, "e/INDEX.md")
    assert page_for_slug(tmp_path, "d") == tmp_path / "d/Readme.md"
    assert page_for_slug(tmp_path, "e") == tmp_path / "e/INDEX.md"


def test_persona_resolution(tmp_path: Path) -> None:
    _touch(tmp_path, "context/audience/internal/maintainer.md")
    _touch(tmp_path, "context/audience/external/index.md")
    assert persona_page(tmp_path, "internal/maintainer") == tmp_path / "context/audience/internal/maintainer.md"
    assert persona_page(tmp_path, "external") == tmp_path / "context/audience/external/index.md"
    assert persona_page(tmp_path, "internal/ghost") is None
    assert persona_page(tmp_path, "") is None
    assert persona_page(tmp_path, "../secrets") is None


@pytest.mark.parametrize(
    ("value", "profile"),
    [
        ("docs/context/audience/internal/maintainer.md", "internal/maintainer"),
        ("../context/audience/external/project-owner.md", "external/project-owner"),
        ("../../context/audience/internal/lead-developer.md", "internal/lead-developer"),
        ("end-users", None),
        ("docs/context/charter.md", None),
    ],
)
def test_profile_of_persona_path(value: str, profile: str | None) -> None:
    assert profile_of_persona_path(value) == profile


@pytest.mark.parametrize(
    ("rel", "adr", "immutable"),
    [
        ("adr/4.x/2026-10-31-1-x.md", True, True),
        ("adr/4.x/index.md", False, False),
        ("adr/1.x/README.md", False, False),
        ("plans/x.md", False, True),
        ("reports/x.md", False, True),
        ("changelog/CHANGELOG.md", False, True),
        ("archive/x.md", False, True),
        ("guides/x.md", False, False),
        ("plans/x.yaml", False, False),
    ],
)
def test_adr_and_immutable(rel: str, adr: bool, immutable: bool) -> None:
    assert is_dated_adr(rel) is adr
    assert is_immutable(rel) is immutable


def test_split_frontmatter_keeps_body_bytes() -> None:
    text = "---\r\ntitle: x\r\n---\r\n\r\n# Body\r\n"
    parts = split_frontmatter(text)
    assert parts == ("---\r\ntitle: x\r\n---\r\n", "\r\n# Body\r\n")
    assert body_of(text) == "\r\n# Body\r\n"


@pytest.mark.parametrize("text", ["# No frontmatter\n", "", "---\ntitle: never closed\n"])
def test_text_without_closed_frontmatter_is_all_body(text: str) -> None:
    assert split_frontmatter(text) is None
    assert body_of(text) == text


# ---------------------------------------------------------------------------
# Frontmatter rules mirrored from doc-kitty (#6931)
# ---------------------------------------------------------------------------

_SITE_PACKAGE = Path(__file__).resolve().parents[2] / "site" / "package.json"

_VALID: dict[str, Any] = {
    "title": "A page",
    "description": "A description that is long enough to pass the soft lower bound of fifty.",
    "doc_status": "active",
    "updated": "2026-11-01T00:00:00Z",
    "kind": "How-To",
}


def _page(**changes: Any) -> dict[str, Any]:
    data = {**_VALID, **changes}
    return {key: value for key, value in data.items() if value is not ...}


def test_mirror_is_pinned_to_the_doc_kitty_commit_the_site_installs() -> None:
    """A toolkit bump moves ``site/package.json`` off the pin, which forces a re-check of the copied rules."""
    dependencies = json.loads(_SITE_PACKAGE.read_text(encoding="utf-8"))["dependencies"]
    assert f"#{DOCKITTY_PIN}&" in dependencies["@spec-kitty/doc-toolkit"]


def test_vocabularies_match_doc_kitty_at_the_pin() -> None:
    """Values copied from ``src/lib/vocabulary-core.mjs`` at :data:`DOCKITTY_PIN`."""
    assert REQUIRED_FIELDS == ("title", "description", "doc_status", "updated", "kind")
    assert DOC_STATUSES == ("draft", "active", "deprecated", "superseded", "durable")
    assert KINDS[:6] == ("Tutorial", "How-To", "Reference", "Explanation", "Hub", "ADR")
    assert len(KINDS) == 15 and len(set(KINDS)) == 15
    assert len(DOC_TYPES) == 18 and "Guide" in DOC_TYPES and "how-to" not in DOC_TYPES
    assert DESCRIPTION_MAX == 180


def test_a_complete_page_passes_clean() -> None:
    assert validate_frontmatter("guides/x.md", _VALID).errors == ()
    assert validate_frontmatter("guides/x.md", _VALID).warnings == ()


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
@pytest.mark.parametrize("missing", [..., None, ""])
def test_an_absent_required_field_is_an_error(field: str, missing: object) -> None:
    findings = validate_frontmatter("guides/x.md", _page(**{field: missing}))
    assert f"`{field}`: required" in findings.errors


def test_a_page_without_frontmatter_fails_every_required_field() -> None:
    assert validate_frontmatter("guides/x.md", {}).errors == tuple(f"`{field}`: required" for field in REQUIRED_FIELDS)


@pytest.mark.parametrize("value", ["2026-11-01", "not a date", "2026-13-45x", "1", 20261101])
def test_updated_that_is_not_an_instant_is_an_error_unless_date_only(value: object) -> None:
    findings = validate_frontmatter("guides/x.md", _page(updated=value))
    if value == "2026-11-01":
        assert findings.errors == ()
        assert findings.warnings == ("`updated: 2026-11-01` is date-only; use a UTC instant (YYYY-MM-DDTHH:MM:SSZ)",)
    else:
        assert findings.errors == (f"`updated`: {NOT_A_DATE_MESSAGE}",)


def test_a_yaml_date_is_a_date_only_warning_and_a_yaml_datetime_is_clean() -> None:
    assert validate_frontmatter("guides/x.md", _page(updated=date(2026, 11, 1))).warnings[0].endswith("is date-only; use a UTC instant (YYYY-MM-DDTHH:MM:SSZ)")
    assert validate_frontmatter("guides/x.md", _page(updated=datetime(2026, 11, 1, 12, 0))) == validate_frontmatter("guides/x.md", _VALID)


def test_stale_after_is_held_to_the_instant_grammar_without_the_date_only_advisory() -> None:
    assert validate_frontmatter("guides/x.md", _page(stale_after="soon")).errors == (f"`stale_after`: {NOT_A_DATE_MESSAGE}",)
    assert validate_frontmatter("guides/x.md", _page(stale_after="2027-01-01")).warnings == ()


@pytest.mark.parametrize(
    ("value", "advisory"),
    [
        ("2026-11-01T10:00:00+02:00", "is not UTC; write the instant with a `Z` offset"),
        ("2026-11-01T10:00:00", "has no zone (read as UTC); write the instant with a `Z` offset"),
        ("2026-02-30T00:00:00Z", "is not a real calendar date; read as 2026-03-02T00:00:00Z"),
    ],
)
def test_instant_spellings_upstream_accepts_are_warnings(value: str, advisory: str) -> None:
    findings = validate_frontmatter("guides/x.md", _page(updated=value))
    assert findings.errors == ()
    assert findings.warnings == (f"`updated: {value}` {advisory}",)


@pytest.mark.parametrize(
    ("value", "canonical"),
    [
        ("2026-11-01T10:00:00Z", "2026-11-01T10:00:00Z"),
        ("2026-11-01T10:00Z", "2026-11-01T10:00:00Z"),
        ("2026-11-01T10:00:00.4+0130", "2026-11-01T08:30:00Z"),
        ("2026-11-01 10:00:00-05", "2026-11-01T15:00:00Z"),
        ("2026-11-01", "2026-11-01T00:00:00Z"),
        (date(2026, 11, 1), "2026-11-01T00:00:00Z"),
        (datetime(2026, 11, 1, 10, tzinfo=UTC), "2026-11-01T10:00:00Z"),
    ],
)
def test_parse_instant_reads_iso_spellings(value: object, canonical: str) -> None:
    instant = parse_instant(value)
    assert instant is not None
    assert format_instant(instant.moment) == canonical


@pytest.mark.parametrize("value", ["2026-11-01T10:00:00+15:00", "2026-11-01T10:00:00+02:60", "0000-00-01", "October 1, 2026", None, 3])
def test_parse_instant_refuses_what_is_not_an_instant(value: object) -> None:
    assert parse_instant(value) is None


def test_description_over_the_bound_is_an_error_and_under_the_soft_bound_a_warning() -> None:
    too_long = validate_frontmatter("guides/x.md", _page(description="x" * (DESCRIPTION_MAX + 1)))
    assert too_long.errors == (f"`description`: must be at most {DESCRIPTION_MAX} characters",)
    short = validate_frontmatter("guides/x.md", _page(description="Too short."))
    assert short.errors == ()
    assert short.warnings == ("description is 10 chars; convention suggests 50–180",)


@pytest.mark.parametrize(
    ("field", "value", "noun"),
    [("doc_status", "point_in_time", "legal set"), ("kind", "Runbook", "canonical set"), ("type", "how-to", "canonical set")],
)
def test_a_value_outside_an_open_vocabulary_is_a_warning(field: str, value: str, noun: str) -> None:
    findings = validate_frontmatter("guides/x.md", _page(**{field: value}))
    assert findings.errors == ()
    assert len(findings.warnings) == 1
    assert findings.warnings[0].startswith(f"`{field}: {value}` is not in the {noun} (")


def test_a_non_string_value_is_an_error() -> None:
    assert validate_frontmatter("guides/x.md", _page(kind=["How-To"])).errors == ("`kind`: must be a string",)


def test_presentation_kind_must_live_under_presentations() -> None:
    assert validate_frontmatter("presentations/deck.md", _page(kind="Presentation")).errors == ()
    assert validate_frontmatter("guides/deck.md", _page(kind="Presentation")).errors == (
        "`kind: Presentation` must live under `presentations/` (ADR-0021 path+kind invariant, FR-022)",
    )


def test_persona_kind_requires_its_attributes() -> None:
    assert validate_frontmatter("context/audience/x.md", _page(kind="Persona")).errors == (
        "`role`: persona requires a non-empty string",
        "`goals`: persona requires a non-empty list of non-empty strings",
        "`responsibilities`: persona requires a non-empty list of non-empty strings",
    )
    complete = _page(kind="Persona", role="Maintainer", goals=["ship"], responsibilities=["review"])
    assert validate_frontmatter("context/audience/x.md", complete).errors == ()


# ---------------------------------------------------------------------------
# The unpublished set (#6932, FR-003): one derivation the gates, the built-site
# check and the redirect generator (#6933) all read.
# ---------------------------------------------------------------------------

_DOCS_LLMS = Path(__file__).resolve().parents[2] / "docs" / "llms.txt"


def _page_at(root: Path, rel: str, frontmatter: str | None) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "" if frontmatter is None else f"---\ntitle: t\n{frontmatter}---\n"
    path.write_text(f"{head}\n# Body\n", encoding="utf-8")


@pytest.fixture
def docs_tree(tmp_path: Path) -> Path:
    _page_at(tmp_path, "index.md", "doc_status: active\n")
    _page_at(tmp_path, "guides/live.md", "doc_status: active\n")
    _page_at(tmp_path, "guides/old.md", "doc_status: 'deprecated'\n")
    _page_at(tmp_path, "guides/wip.md", "doc_status: draft\n")
    _page_at(tmp_path, "guides/unstated.md", "")
    _page_at(tmp_path, "guides/bare.md", None)
    _page_at(tmp_path, "guides/nested/README.md", 'doc_status: "draft"\n')
    _page_at(tmp_path, "archive/guides/gone.md", "doc_status: active\n")
    _page_at(tmp_path, "plans/engineering-notes/note.md", "doc_status: deprecated\n")
    _page_at(tmp_path, "plans/roadmap.md", "doc_status: active\n")
    (tmp_path / "guides" / "notes.txt").write_text("not a page\n", encoding="utf-8")
    return tmp_path


def test_unpublished_routes_name_drafts_excluded_folders_and_draft_folders(docs_tree: Path) -> None:
    assert contract.unpublished_routes(docs_tree) == frozenset(
        {
            "/guides/wip/",
            "/guides/unstated/",
            "/guides/bare/",
            "/guides/nested/",
            "/archive/guides/gone/",
            "/plans/engineering-notes/note/",
        }
    )


def test_a_status_key_nested_under_another_key_does_not_publish_a_page(docs_tree: Path) -> None:
    _page_at(docs_tree, "guides/nested-key.md", "meta:\n  doc_status: active\n")

    assert "/guides/nested-key/" in contract.unpublished_routes(docs_tree)


@pytest.mark.parametrize(
    ("rel", "in_draft_folder"),
    [
        ("plans/engineering-notes/x.md", True),
        ("plans/investigations/a/b.md", True),
        ("plans/research/index.md", True),
        ("plans/research-notes.md", False),
        ("plans/roadmap.md", False),
        ("guides/engineering-notes/x.md", False),
    ],
)
def test_is_in_draft_folder(rel: str, in_draft_folder: bool) -> None:
    assert contract.is_in_draft_folder(rel) is in_draft_folder


def test_route_of_matches_the_built_directory_route() -> None:
    assert contract.route_of("guides/x.md") == "/guides/x/"
    assert contract.route_of("adr/4.x/README.md") == "/adr/4.x/"
    assert contract.route_of("index.md") == "/"


def test_the_hand_written_llms_txt_still_carries_the_stance() -> None:
    """``docs/llms.txt`` keeps a copy of the stance until #6938 deletes it; the copies must agree."""
    assert contract.LLMS_STANCE.startswith("## Current Version Stance\n")
    assert contract.LLMS_STANCE in _DOCS_LLMS.read_text(encoding="utf-8")
