"""Pipeline orchestration tests (WP02 T010)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render import RenderRequest
from specify_cli.doctrine.template_render.pipeline import render_org_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_template(root: Path) -> None:
    (root / "pack").mkdir()
    (root / "pack" / "org-charter.yaml").write_text(
        'org_name: "{{ORG_NAME}}"\nlocal: "{{LOCAL_PATH}}"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# {{ORG_NAME}}\n", encoding="utf-8")
    (root / "kitty-specs").mkdir()
    (root / "kitty-specs" / "x.md").write_text("skip\n", encoding="utf-8")
    (root / ".templateignore").write_text("kitty-specs/\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")


def test_pipeline_happy_path(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _make_template(tpl)
    dest = tmp_path / "out"

    err = render_org_pack(
        RenderRequest(
            pack_path=dest,
            template=str(tpl),
            org_name="acme-corp",
            local_path=None,
            force=False,
        )
    )
    assert err is None
    assert (dest / "pack" / "org-charter.yaml").is_file()
    text = (dest / "pack" / "org-charter.yaml").read_text(encoding="utf-8")
    assert "acme-corp" in text
    assert "pack" in text
    assert "{{ORG_NAME}}" not in text
    assert not (dest / "kitty-specs").exists()
    assert not (dest / ".git").exists()


def test_pipeline_rejects_invalid_org_before_write(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _make_template(tpl)
    dest = tmp_path / "out"

    err = render_org_pack(
        RenderRequest(
            pack_path=dest,
            template=str(tpl),
            org_name="Acme",
            force=False,
        )
    )
    assert err is not None
    assert err.rule_id == "org_name.format"
    assert not dest.exists()


def test_pipeline_refuses_existing_without_force(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _make_template(tpl)
    dest = tmp_path / "out"
    dest.mkdir()

    err = render_org_pack(
        RenderRequest(
            pack_path=dest,
            template=str(tpl),
            org_name="acme-corp",
            force=False,
        )
    )
    assert err is not None
    assert err.rule_id == "pack_path.exists"
