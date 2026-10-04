"""Unit tests for :func:`apply_org_charter_to_interview` cross-kind union.

Mission B WP06 (T026/T031) extends ``apply_org_charter_to_interview`` to
union every ``required_<kind>`` declared in an org pack's
``org-charter.yaml`` into the matching ``selected_<kind>`` field on the
in-memory interview.  This module pins the union semantics for each of
each kind in :data:`specify_cli.doctrine.org_charter.REQUIRED_KIND_FIELDS`
and the non-destructive merge contract.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from specify_cli.doctrine.org_charter import (
    REQUIRED_KIND_FIELDS,
    apply_org_charter_to_interview,
    load_org_charter_policies,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_kittify_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    """Write ``.kittify/config.yaml`` with the given pack entries."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["doctrine:", "  org:", "    packs:"]
    for name, path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_charter(pack_dir: Path, body: str) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "org-charter.yaml").write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


class _Interview:
    """Minimal interview shape declaring every Mission B selection field."""

    def __init__(self) -> None:
        self.answers: dict[str, str] = {}
        for kind in REQUIRED_KIND_FIELDS:
            setattr(self, f"selected_{kind}", [])


@pytest.mark.parametrize("kind", list(REQUIRED_KIND_FIELDS))
def test_apply_org_charter_unions_required_kind_into_selection(
    kind: str, tmp_path: Path
) -> None:
    pack = tmp_path / "pack"
    _write_org_charter(
        pack,
        f"""
        schema_version: "1"
        org_name: "ATDD"
        required_{kind}:
          - org-id-1
          - org-id-2
        """,
    )
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _write_kittify_config(consumer, [("pack", pack)])

    interview = _Interview()
    messages = apply_org_charter_to_interview(interview, consumer)

    assert getattr(interview, f"selected_{kind}") == ["org-id-1", "org-id-2"], (
        f"required_{kind} entries MUST union into selected_{kind} in declaration order."
    )
    assert any(f"required_{kind}" in m for m in messages), (
        f"apply messages MUST disclose what was added per required_{kind}."
    )


@pytest.mark.parametrize("kind", list(REQUIRED_KIND_FIELDS))
def test_apply_org_charter_is_non_destructive_per_kind(
    kind: str, tmp_path: Path
) -> None:
    pack = tmp_path / "pack"
    _write_org_charter(
        pack,
        f"""
        schema_version: "1"
        required_{kind}:
          - existing
          - new-from-org
        """,
    )
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _write_kittify_config(consumer, [("pack", pack)])

    interview = _Interview()
    # Pre-populate project selection — should be preserved.
    setattr(interview, f"selected_{kind}", ["existing", "project-pinned"])
    apply_org_charter_to_interview(interview, consumer)
    final = getattr(interview, f"selected_{kind}")

    assert "existing" in final
    assert "project-pinned" in final, "project-selected ids MUST be preserved (non-destructive)"
    assert "new-from-org" in final, "org-required new ids MUST append"
    # First-seen order preserved: project ids first, then org additions.
    assert final.index("project-pinned") < final.index("new-from-org")


def test_load_org_charter_policies_unions_required_kinds_across_packs(
    tmp_path: Path,
) -> None:
    pack_a = tmp_path / "a"
    pack_b = tmp_path / "b"
    _write_org_charter(
        pack_a,
        """
        schema_version: "1"
        required_styleguides:
          - sg-a-1
        required_directives:
          - d-shared
          - d-a-only
        """,
    )
    _write_org_charter(
        pack_b,
        """
        schema_version: "1"
        required_styleguides:
          - sg-a-1
          - sg-b-1
        required_directives:
          - d-shared
          - d-b-only
        """,
    )
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _write_kittify_config(consumer, [("a", pack_a), ("b", pack_b)])

    merged = load_org_charter_policies(consumer)

    # Union preserves first-seen order across packs (declaration-order precedence).
    assert merged.required_styleguides == ["sg-a-1", "sg-b-1"]
    assert merged.required_directives == ["d-shared", "d-a-only", "d-b-only"]


def test_apply_org_charter_initialises_missing_selection_attribute(
    tmp_path: Path,
) -> None:
    """Legacy interview shapes that pre-date a kind's ``selected_<kind>``
    field still receive the org union — the helper sets the attribute
    defensively rather than raising AttributeError.
    """
    pack = tmp_path / "pack"
    _write_org_charter(
        pack,
        """
        schema_version: "1"
        required_styleguides:
          - org-sg
        """,
    )
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _write_kittify_config(consumer, [("pack", pack)])

    class _LegacyInterview:
        def __init__(self) -> None:
            self.answers: dict[str, str] = {}
            self.selected_directives: list[str] = []
            # No selected_styleguides — pre-WP01 shape.

    interview = _LegacyInterview()
    apply_org_charter_to_interview(interview, consumer)

    assert interview.selected_styleguides == ["org-sg"]
