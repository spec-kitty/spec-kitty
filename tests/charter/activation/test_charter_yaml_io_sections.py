"""Several owned sections in one prepared write must produce the same bytes as one each.

``compiler.write_compiled_charter`` used to refresh ``catalog`` and ``metadata`` with two
sequential single-section writes. Each write observed, loaded, rendered and re-verified the
whole governed document, so one recompile paid that cycle twice (#6506). The merged form
(:func:`charter.activation.charter_yaml_io.prepare_charter_yaml_sections`) carries both in one
cycle.

This module is the byte-identity guard (FR-007 / SC-003): for a corpus of documents and a
matrix of section sets, the bytes a merged write leaves on disk must equal the bytes the
sequential single-section writes left — including key insertion order, comment retention,
framing, line endings and the no-op case. A governed document's bytes are the contract here,
so the assertions compare raw bytes and never parsed structures.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from charter.activation.charter_yaml_io import (
    PreparedYamlWrite,
    UnknownCharterYamlSectionError,
    _yaml_loader,
    apply_yaml_write,
    prepare_charter_yaml_section,
    prepare_charter_yaml_sections,
)

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_CHARTER = _REPO_ROOT / ".kittify" / "charter" / "charter.yaml"

#: A small governed document with a document-prefix comment, a section-prefix comment, a
#: trailing comment and a key whose value is an inline comment — every span the renderer has
#: to preserve.
_SMALL_DOCUMENT = """\
# Charter for the probe project
schema_version: "5"

# Governance section
governance:
  purpose: probe   # keep this comment
  version: 1

directives:
  keep_me: true

metadata:
  generated_at: "2026-01-01T00:00:00Z"
  generator: probe

trailing_key: last
"""

_CATALOG_VALUES = {"mission": "software-dev", "references": [{"urn": "tactic:probe"}], "languages": ["python"]}
_METADATA_VALUES = {"generated_at": "2026-10-31T00:00:00Z", "generator": "probe-2"}
_ACTIVATION_VALUES = {"activated_directives": ["probe-directive"]}


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_bytes(body.encode("utf-8"))
    return path


def _apply(prepared: PreparedYamlWrite) -> None:
    apply_yaml_write(prepared)


def _sequential(path: Path, steps: list[tuple[str, dict[str, Any]]]) -> bytes:
    """Apply each section as its own write cycle — the pre-#6506 behaviour."""
    for section, values in steps:
        _apply(prepare_charter_yaml_section(path, section, values))
    return path.read_bytes()


def _merged(path: Path, sections: dict[str, dict[str, Any]]) -> bytes:
    """Apply every section in one cycle."""
    _apply(prepare_charter_yaml_sections(path, sections=sections))
    return path.read_bytes()


def _both(tmp_path: Path, body: str, steps: list[tuple[str, dict[str, Any]]]) -> tuple[bytes, bytes]:
    sequential_path = _write(tmp_path, "sequential.yaml", body)
    merged_path = _write(tmp_path, "merged.yaml", body)
    sequential = _sequential(sequential_path, steps)
    merged = _merged(merged_path, dict(steps))
    return sequential, merged


_CASES: tuple[tuple[str, list[tuple[str, dict[str, Any]]]], ...] = (
    ("catalog-then-metadata", [("catalog", _CATALOG_VALUES), ("metadata", _METADATA_VALUES)]),
    ("metadata-then-catalog", [("metadata", _METADATA_VALUES), ("catalog", _CATALOG_VALUES)]),
    ("activation-then-catalog", [("activation", _ACTIVATION_VALUES), ("catalog", _CATALOG_VALUES)]),
    ("catalog-only", [("catalog", _CATALOG_VALUES)]),
    ("activation-only", [("activation", _ACTIVATION_VALUES)]),
)

_BODIES: tuple[tuple[str, str], ...] = (
    ("full", _SMALL_DOCUMENT),
    # Both derived sections absent: the merged path must append them in the same place, in the
    # same order, as two sequential appends did.
    ("missing-sections", 'schema_version: "5"\ngovernance:\n  purpose: probe\n'),
    # Only metadata present.
    ("missing-catalog", 'schema_version: "5"\nmetadata:\n  generator: probe\n'),
    # Windows line endings survive both paths identically.
    ("crlf", _SMALL_DOCUMENT.replace("\n", "\r\n")),
)


@pytest.mark.parametrize(("body_name", "body"), _BODIES, ids=[name for name, _ in _BODIES])
@pytest.mark.parametrize(("case_name", "steps"), _CASES, ids=[name for name, _ in _CASES])
def test_merged_write_matches_sequential_carousel(tmp_path: Path, body_name: str, body: str, case_name: str, steps: list[tuple[str, dict[str, Any]]]) -> None:
    sequential, merged = _both(tmp_path, body, steps)
    assert merged == sequential, f"{case_name} on the {body_name} document produced different bytes"
    # Both paths must actually have changed something, or this comparison is vacuous.
    assert merged != body.encode("utf-8"), f"{case_name} on the {body_name} document wrote nothing"


def test_repository_charter_is_byte_identical(tmp_path: Path) -> None:
    """The large real document, with both derived sections replaced, must match byte for byte."""
    if not _REPO_CHARTER.is_file():  # pragma: no cover - an installed sdist has no project charter
        pytest.skip(f"no project charter at {_REPO_CHARTER}")
    body = _REPO_CHARTER.read_bytes()
    sequential, merged = _both(tmp_path, body.decode("utf-8"), [("catalog", _CATALOG_VALUES), ("metadata", _METADATA_VALUES)])
    assert merged == sequential
    assert merged != body
    # Everything the writer does not own survives untouched: the whole point of the round trip.
    governance_marker = b"governance:"
    if governance_marker in body:
        assert governance_marker in merged


def test_noop_write_returns_the_input_bytes(tmp_path: Path) -> None:
    """A write with nothing to change keeps the original bytes and reports no change."""
    body = _yaml_loader().load(_SMALL_DOCUMENT)
    catalog = body.get("catalog") if isinstance(body, dict) else None
    assert catalog is None, "the small fixture is expected to start without a catalog"
    path = _write(tmp_path, "noop.yaml", _SMALL_DOCUMENT)
    prepared = prepare_charter_yaml_sections(path, sections={"catalog": dict(_CATALOG_VALUES)})
    _apply(prepared)
    written = path.read_bytes()

    again = prepare_charter_yaml_sections(path, sections={"catalog": dict(_CATALOG_VALUES)})
    assert again.desired_bytes == written
    assert again.changed is False


def test_sections_from_document_sees_the_unmodified_document(tmp_path: Path) -> None:
    """The callback is handed exactly what is on disk, before any section is written."""
    path = _write(tmp_path, "from-doc.yaml", _SMALL_DOCUMENT)
    on_disk = path.read_bytes()
    seen: list[Any] = []

    def build(document: Any) -> dict[str, dict[str, Any]]:
        seen.append(document)
        assert document["metadata"]["generator"] == "probe"
        assert "catalog" not in document
        return {"catalog": dict(_CATALOG_VALUES)}

    _apply(prepare_charter_yaml_sections(path, sections_from_document=build))
    assert len(seen) == 1
    assert path.read_bytes().startswith(on_disk.split(b"\n")[0])


def test_sections_from_document_is_validated(tmp_path: Path) -> None:
    """A callback that names an unowned section is refused before anything is written."""
    path = _write(tmp_path, "invalid.yaml", _SMALL_DOCUMENT)
    with pytest.raises(UnknownCharterYamlSectionError):
        prepare_charter_yaml_sections(path, sections_from_document=lambda _document: {"not-a-section": {}})


def test_exactly_one_of_the_two_keyword_forms(tmp_path: Path) -> None:
    path = _write(tmp_path, "either.yaml", _SMALL_DOCUMENT)
    with pytest.raises(TypeError):
        prepare_charter_yaml_sections(path)
    with pytest.raises(TypeError):
        prepare_charter_yaml_sections(path, sections={"catalog": {}}, sections_from_document=lambda _doc: {"catalog": {}})


def test_removal_is_carried_through_the_merged_form(tmp_path: Path) -> None:
    """``remove=`` still deletes activation keys, and still refuses another section's."""
    body = _SMALL_DOCUMENT + "activated_directives:\n  - probe\n"
    path = _write(tmp_path, "remove.yaml", body)
    _apply(prepare_charter_yaml_sections(path, sections={"catalog": dict(_CATALOG_VALUES)}, remove=["activated_directives"]))
    written = path.read_bytes()
    assert b"activated_directives" not in written
    assert b"catalog:" in written

    with pytest.raises(ValueError, match="Unknown activation key"):
        prepare_charter_yaml_sections(path, sections={"catalog": {}}, remove=["not_an_activation_key"])


def test_overlap_between_write_and_removal_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "overlap.yaml", _SMALL_DOCUMENT + "activated_directives:\n  - probe\n")
    with pytest.raises(ValueError, match="both written and removed"):
        prepare_charter_yaml_sections(
            path,
            sections={"activation": {"activated_directives": ["other"]}},
            remove=["activated_directives"],
        )


def test_missing_document_is_a_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        prepare_charter_yaml_sections(tmp_path / "absent.yaml", sections={"catalog": {}})


def test_sequential_is_a_thin_delegation(tmp_path: Path) -> None:
    """The single-section entry point keeps its own error precedence and message."""
    path = _write(tmp_path, "precedence.yaml", _SMALL_DOCUMENT)
    with pytest.raises(ValueError, match="remove= is only supported for the 'activation' section"):
        prepare_charter_yaml_section(path, "catalog", {}, remove=["activated_directives"])


def _copy_repository_charter(tmp_path: Path) -> Path:
    if not _REPO_CHARTER.is_file():  # pragma: no cover - an installed sdist has no project charter
        pytest.skip(f"no project charter at {_REPO_CHARTER}")
    target = tmp_path / "charter.yaml"
    shutil.copyfile(_REPO_CHARTER, target)
    return target


def test_one_cycle_reads_the_document_once(tmp_path: Path) -> None:
    """The receipt covers the document exactly once, whichever sections are written.

    ``prepare_yaml_write`` also records the target's parent directories (to refuse a write
    whose containment moved), so the document is the one observation that carries content.
    """
    path = _copy_repository_charter(tmp_path)
    prepared = prepare_charter_yaml_sections(path, sections={"catalog": dict(_CATALOG_VALUES), "metadata": dict(_METADATA_VALUES)})
    documents = [observation for observation in prepared.observations if observation.content is not None]
    assert [observation.path for observation in documents] == [path]
    assert prepared.section == "catalog,metadata"

    one_section = prepare_charter_yaml_sections(path, sections={"catalog": dict(_CATALOG_VALUES)})
    assert [o.path for o in one_section.observations if o.content is not None] == [path]
