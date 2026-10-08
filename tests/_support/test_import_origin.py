from pathlib import Path

import pytest

from tests._support.import_origin import assert_checkout_source


def test_checkout_source_accepts_own_src(tmp_path: Path) -> None:
    module = tmp_path / "src/specify_cli/__init__.py"
    module.parent.mkdir(parents=True)
    module.touch()
    assert_checkout_source(module, tmp_path)


def test_checkout_source_rejects_foreign_src(tmp_path: Path) -> None:
    module = tmp_path / "other/src/specify_cli/__init__.py"
    module.parent.mkdir(parents=True)
    module.touch()
    with pytest.raises(RuntimeError, match="outside this checkout"):
        assert_checkout_source(module, tmp_path / "lane")
