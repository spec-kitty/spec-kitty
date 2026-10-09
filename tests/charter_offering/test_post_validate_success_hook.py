"""Tests for ``BaseArtifactRepository._post_validate`` (T025).

The base loader had a ``_pre_validate`` hook only, called before
``model_validate``/``_merge`` at all three item-entry points
(built-in load, overlay merge branch, overlay new-item branch). A subclass
that records bookkeeping in ``_pre_validate`` (e.g.
``AssetRepository._source_paths``, pre-fix) observes a split-brain: the
bookkeeping is written even when the subsequent validation fails, because
``_pre_validate`` runs *before* the try/except that catches
``ValidationError``.

``_post_validate(obj, yaml_file)`` closes that gap: a symmetric hook fired
*only* on success, at the same three call sites, gated by the same
``_include_item`` condition that gates the actual ``self._items`` write.
These tests prove the hook's firing contract generically, via a minimal
``BaseArtifactRepository`` subclass with a recording spy, independent of any
concrete doctrine artifact type.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML

from charter.offering.base import BaseArtifactRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


class _MinimalItem(BaseModel):
    """Smallest possible schema for a ``BaseArtifactRepository`` subclass."""

    model_config = ConfigDict(extra="forbid")

    id: str
    value: str


class _RecordingRepository(BaseArtifactRepository[_MinimalItem]):
    """Minimal repository subclass exercising the ``_post_validate`` hook."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.post_validate_calls: list[tuple[str, Path]] = []
        super().__init__(*args, **kwargs)

    @property
    def _schema(self) -> type[_MinimalItem]:
        return _MinimalItem

    @property
    def _glob(self) -> str:
        return "*.item.yaml"

    def _post_validate(self, obj: _MinimalItem, yaml_file: Path) -> None:
        self.post_validate_calls.append((obj.id, yaml_file))


def _write_item(path: Path, *, item_id: str, value: str = "v") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump({"id": item_id, "value": value}, handle)


def _write_invalid_item(path: Path) -> None:
    """Write YAML that fails ``_MinimalItem`` validation (missing ``value``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump({"id": "broken"}, handle)


class TestPostValidateFiresOnSuccess:
    def test_fires_for_the_built_in_load_site(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        _write_item(built_in / "a.item.yaml", item_id="a")

        repo = _RecordingRepository(built_in_dir=built_in)

        assert repo.post_validate_calls == [("a", built_in / "a.item.yaml")]

    def test_fires_for_the_overlay_merge_branch(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        _write_item(built_in / "a.item.yaml", item_id="a", value="orig")
        org = tmp_path / "org"
        _write_item(org / "a.item.yaml", item_id="a", value="override")

        repo = _RecordingRepository(built_in_dir=built_in, org_dirs=[org])

        # Fires once for the built-in load, once for the successful org merge.
        assert repo.post_validate_calls == [
            ("a", built_in / "a.item.yaml"),
            ("a", org / "a.item.yaml"),
        ]

    def test_fires_for_the_overlay_new_item_branch(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir(parents=True)
        project = tmp_path / "project"
        _write_item(project / "b.item.yaml", item_id="b")

        repo = _RecordingRepository(built_in_dir=built_in, project_dir=project)

        assert repo.post_validate_calls == [("b", project / "b.item.yaml")]


class TestPostValidateNeverFiresOnFailure:
    def test_never_fires_for_a_built_in_validation_failure(
        self, tmp_path: Path
    ) -> None:
        built_in = tmp_path / "built-in"
        _write_invalid_item(built_in / "broken.item.yaml")

        with pytest.warns(UserWarning, match="Skipping invalid built-in"):
            repo = _RecordingRepository(built_in_dir=built_in)

        assert repo.post_validate_calls == []
        assert repo.get("broken") is None

    def test_never_fires_for_an_overlay_validation_failure(
        self, tmp_path: Path
    ) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir(parents=True)
        project = tmp_path / "project"
        _write_invalid_item(project / "broken.item.yaml")

        with pytest.warns(UserWarning, match="Skipping invalid project"):
            repo = _RecordingRepository(built_in_dir=built_in, project_dir=project)

        assert repo.post_validate_calls == []
        assert repo.get("broken") is None
