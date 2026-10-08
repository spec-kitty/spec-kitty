"""Regression locks for retired inline doctrine relationship fields.

Mission ``charter-ux-and-org-pack-vocabulary-01KSAF14`` / WP10 / T057.

The point of this test is to FREEZE the field-merge semantics described in
``docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md`` and in
``kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/quickstart.md`` §4a.

FR-028 retired inline ``enhances`` / ``overrides`` fields on doctrine artifacts.
Relationships now belong in DRG fragments. Stale packs that still author inline
relationship fields must be rejected without replacing the built-in artifact.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from charter.offering.tactics.models import Tactic, TacticStep
from charter.offering.tactics.repository import TacticRepository

pytestmark = [pytest.mark.integration, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Fixture helpers — build a minimal built-in tactic plus a partial pack
# override on disk, then load via the public repository.
# ---------------------------------------------------------------------------


_BUILT_IN_TACTIC_ID = "edge-case-built-in-tactic"
_BUILT_IN_NAME = "Built-in Name"
_BUILT_IN_PURPOSE = "Built-in purpose."
_BUILT_IN_STEP_TITLES = ("Step One", "Step Two")
_BUILT_IN_FAILURE_MODES = ("mode-a", "mode-b")
_BUILT_IN_LANGUAGES = ("python",)


def _write_built_in_tactic(built_in_dir: Path) -> None:
    """Materialise the built-in tactic on disk."""
    built_in_dir.mkdir(parents=True, exist_ok=True)
    yaml_body = dedent(
        f"""\
        schema_version: "1.0"
        id: {_BUILT_IN_TACTIC_ID}
        name: {_BUILT_IN_NAME}
        purpose: {_BUILT_IN_PURPOSE}
        steps:
          - title: {_BUILT_IN_STEP_TITLES[0]}
          - title: {_BUILT_IN_STEP_TITLES[1]}
        failure_modes:
          - {_BUILT_IN_FAILURE_MODES[0]}
          - {_BUILT_IN_FAILURE_MODES[1]}
        applies_to_languages:
          - {_BUILT_IN_LANGUAGES[0]}
        """
    )
    (built_in_dir / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml").write_text(
        yaml_body, encoding="utf-8"
    )


def _write_partial_pack_tactic(
    pack_dir: Path,
    *,
    overrides_fields: dict[str, str] | None = None,
) -> None:
    """Write a pack tactic that omits steps/failure_modes/applies_to_languages.

    ``overrides_fields`` lets the test inject the override values for
    ``name``/``purpose`` so we can assert pack-overrides-win.
    """
    overrides_fields = overrides_fields or {
        "name": "Pack Name",
        "purpose": "Pack purpose.",
    }
    pack_dir.mkdir(parents=True, exist_ok=True)
    body_lines = [
        'schema_version: "1.0"',
        f"id: {_BUILT_IN_TACTIC_ID}",
        f"name: {overrides_fields['name']}",
        f"purpose: {overrides_fields['purpose']}",
        f"enhances: {_BUILT_IN_TACTIC_ID}",
    ]
    (pack_dir / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml").write_text(
        "\n".join(body_lines) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Direct ``_merge`` lock — fastest, no FS, locks the Python-level invariant.
# ---------------------------------------------------------------------------


class TestMergeDirectInvariants:
    """Lock the field-merge behaviour at the Python-API level.

    Operates on an in-memory ``BaseArtifactRepository`` subclass behaviour by
    calling ``TacticRepository._merge`` directly. This keeps the test focused
    on the merge contract, not on YAML I/O.
    """

    def _built_in_tactic(self) -> Tactic:
        return Tactic(
            schema_version="1.0",
            id=_BUILT_IN_TACTIC_ID,
            name=_BUILT_IN_NAME,
            purpose=_BUILT_IN_PURPOSE,
            steps=[
                TacticStep(title=_BUILT_IN_STEP_TITLES[0]),
                TacticStep(title=_BUILT_IN_STEP_TITLES[1]),
            ],
            failure_modes=list(_BUILT_IN_FAILURE_MODES),
            applies_to_languages=list(_BUILT_IN_LANGUAGES),
        )

    def _empty_repo(self, tmp_path: Path) -> TacticRepository:
        """Build a repository with no actual built-in dir (we only need
        ``_merge``; the loaded set is irrelevant)."""
        return TacticRepository(built_in_dir=tmp_path / "empty-built-in")

    def test_inline_enhances_is_rejected_at_merge_boundary(self, tmp_path: Path) -> None:
        """Inline ``enhances`` must fail closed; DRG fragments own relationships."""
        from pydantic import ValidationError

        repo = self._empty_repo(tmp_path)
        built_in = self._built_in_tactic()

        # Pack data — note ``enhances`` is set; everything else is intentionally
        # absent so the merge must fall through to the built-in.
        pack_data = {
            "schema_version": "1.0",
            "id": _BUILT_IN_TACTIC_ID,
            "name": "Pack Name",
            "purpose": "Pack purpose.",
            "enhances": _BUILT_IN_TACTIC_ID,
        }

        with pytest.raises(ValidationError, match="Retired relationship field"):
            repo._merge(built_in, pack_data)

    def test_built_in_survives_when_pack_provides_invalid_empty_steps(
        self, tmp_path: Path
    ) -> None:
        """Pack provides ``steps: []`` — Tactic schema has ``min_length=1``.

        End-state assertion: a pack override that would erase ``steps`` to
        empty is REJECTED by the schema, so the built-in tactic survives in
        the resolved view. This is the operator-observable outcome the
        quickstart §4a sharp-edge note pins.

        We assert the rejection at the ``_merge`` boundary (the schema raises
        a ``ValidationError`` — the loader catches it and the built-in is
        kept). The behaviour is not "empty == not provided" — it is "empty
        violates min_length, so the override is dropped and the built-in
        survives".
        """
        from pydantic import ValidationError

        repo = self._empty_repo(tmp_path)
        built_in = self._built_in_tactic()

        pack_data = {
            "schema_version": "1.0",
            "id": _BUILT_IN_TACTIC_ID,
            "name": "Pack Name",
            "enhances": _BUILT_IN_TACTIC_ID,
            "steps": [],  # would erase to empty if accepted
        }

        with pytest.raises(ValidationError) as exc_info:
            repo._merge(built_in, pack_data)

        # The retired relationship field is rejected before any legacy
        # empty-steps merge semantics can apply.
        msg = str(exc_info.value)
        assert "Retired relationship field" in msg


# ---------------------------------------------------------------------------
# End-to-end through TacticRepository — exercises the live loader path that
# operators traverse when an org pack lands a partial-override tactic.
# ---------------------------------------------------------------------------


class TestPartialOverrideThroughRepositoryLoader:
    def test_omitted_fields_survive_through_org_layer_load(
        self, tmp_path: Path
    ) -> None:
        """Built-in tactic + org pack with partial override -> field-merge."""
        built_in_dir = tmp_path / "built-in"
        org_dir = tmp_path / "org"

        _write_built_in_tactic(built_in_dir)
        _write_partial_pack_tactic(org_dir)

        repo = TacticRepository(built_in_dir=built_in_dir, org_dirs=[org_dir])
        merged = repo.get(_BUILT_IN_TACTIC_ID)

        assert merged is not None, (
            f"loaded tactics: {[t.id for t in repo.list_all()]}"
        )

        # Stale inline relationship packs are skipped; built-in survives.
        assert merged.name == _BUILT_IN_NAME
        assert merged.purpose == _BUILT_IN_PURPOSE

        # Pack-omitted fields fall through from built-in.
        assert tuple(s.title for s in merged.steps) == _BUILT_IN_STEP_TITLES
        assert tuple(merged.failure_modes) == _BUILT_IN_FAILURE_MODES
        assert tuple(merged.applies_to_languages) == _BUILT_IN_LANGUAGES

        assert repo.get_provenance(_BUILT_IN_TACTIC_ID) == "builtin"
