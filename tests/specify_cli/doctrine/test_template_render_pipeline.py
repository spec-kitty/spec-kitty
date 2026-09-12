"""Pipeline orchestration tests (WP02 T010)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render import RenderRequest
from specify_cli.doctrine.template_render.pipeline import render_org_pack
from specify_cli.doctrine.template_render.ignore_copy import IgnoreRules

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


def test_pipeline_force_overwrites_existing(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _make_template(tpl)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "old.txt").write_text("prior\n", encoding="utf-8")

    err = render_org_pack(
        RenderRequest(
            pack_path=dest,
            template=str(tpl),
            org_name="acme-corp",
            force=True,
        )
    )
    assert err is None
    assert (dest / "pack" / "org-charter.yaml").is_file()
    assert not (dest / "old.txt").exists()
    # No leftover backup dirs from successful force swap
    leftovers = list(tmp_path.glob("out.bak-*"))
    assert leftovers == []


def test_pipeline_stages_on_destination_filesystem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.doctrine.template_render import pipeline

    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    destination = tmp_path / "different-volume" / "output"
    observed: list[Path] = []
    original_copy = pipeline.copy_template_tree

    def inspect_staging(source: Path, staging: Path, rules: IgnoreRules) -> None:
        observed.append(staging)
        assert staging.parent == destination.parent
        original_copy(source, staging, rules)

    monkeypatch.setattr(pipeline, "copy_template_tree", inspect_staging)
    assert pipeline.render_org_pack(RenderRequest(destination, str(template), "acme")) is None
    assert observed and not observed[0].exists()
    assert (destination / "README.md").read_text() == "# acme\n"


@pytest.mark.parametrize("partial_destination", [False, True])
def test_failed_atomic_promotion_restores_original_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, partial_destination: bool) -> None:
    from specify_cli.doctrine.template_render import pipeline

    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    destination = tmp_path / "output"
    destination.mkdir()
    (destination / "original.bin").write_bytes(b"original\x00pack")
    rename = Path.rename
    promotions: list[Path] = []

    def fail_promotion(source: Path, target: Path) -> Path:
        if source.name.startswith(".spec-kitty-render-") and Path(target) == destination:
            promotions.append(source)
            if partial_destination:
                destination.mkdir()
                (destination / "partial.txt").write_text("incomplete replacement")
            raise OSError("injected promotion failure")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_promotion)
    error = pipeline.render_org_pack(RenderRequest(destination, str(template), "acme", force=True))
    assert promotions, "installation must use atomic rename, never shutil.move's copy fallback"
    assert error is not None and error.rule_id == "pipeline.force_swap"
    assert (destination / "original.bin").read_bytes() == b"original\x00pack"
    assert not (destination / "partial.txt").exists()
    assert not (destination / "README.md").exists()
    assert not promotions[0].exists()
    assert not list(tmp_path.glob("output.bak-*"))


def test_template_inside_replaced_destination_is_refused(tmp_path: Path) -> None:
    destination = tmp_path / "output"
    template = destination / "template"
    template.mkdir(parents=True)
    _make_template(template)
    error = render_org_pack(RenderRequest(destination, str(template), "acme", force=True))
    assert error is not None and error.rule_id == "pack_path.overlap"
    assert (template / "README.md").read_text() == "# {{ORG_NAME}}\n"


def test_destination_inside_template_is_refused_before_staging(tmp_path: Path) -> None:
    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    destination = template / "rendered"
    error = render_org_pack(RenderRequest(destination, str(template), "acme"))
    assert error is not None and error.rule_id == "pack_path.overlap"
    assert not destination.exists()
    assert not list(template.glob(".spec-kitty-render-*"))


def test_failed_restore_names_preserved_original_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    destination = tmp_path / "output"
    destination.mkdir()
    (destination / "original.bin").write_bytes(b"original")
    rename = Path.rename

    def fail_promotion_and_restore(source: Path, target: Path) -> Path:
        if Path(target) == destination:
            raise OSError("injected destination unavailable")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_promotion_and_restore)
    error = render_org_pack(RenderRequest(destination, str(template), "acme", force=True))
    assert error is not None and error.rule_id == "pipeline.force_restore"
    backups = list(tmp_path.glob("output.bak-*"))
    assert len(backups) == 1
    assert (backups[0] / "original.bin").read_bytes() == b"original"
    assert str(backups[0]) in error.message


def test_copy_failure_leaves_original_pack_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.doctrine.template_render import pipeline

    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    destination = tmp_path / "output"
    destination.mkdir()
    (destination / "original.bin").write_bytes(b"original")

    def fail_copy(source: Path, staging: Path, rules: IgnoreRules) -> None:
        (staging / "partial.txt").write_text("incomplete")
        raise OSError("injected copy failure")

    monkeypatch.setattr(pipeline, "copy_template_tree", fail_copy)
    error = render_org_pack(RenderRequest(destination, str(template), "acme", force=True))
    assert error is not None and error.rule_id == "pipeline.copy"
    assert (destination / "original.bin").read_bytes() == b"original"
    assert not list(tmp_path.glob(".spec-kitty-render-*"))


@pytest.mark.parametrize("broken", [False, True])
def test_destination_symlink_is_refused_without_touching_target(tmp_path: Path, broken: bool) -> None:
    template = tmp_path / "template"
    template.mkdir()
    _make_template(template)
    target = tmp_path / "target"
    if not broken:
        target.mkdir()
        (target / "original.txt").write_text("preserved")
    destination = tmp_path / "output"
    destination.symlink_to(target, target_is_directory=True)
    error = render_org_pack(RenderRequest(destination, str(template), "acme", force=True))
    assert error is not None and error.rule_id == "pack_path.symlink"
    assert destination.is_symlink()
    assert not target.exists() if broken else (target / "original.txt").read_text() == "preserved"
