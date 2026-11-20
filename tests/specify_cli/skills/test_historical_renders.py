"""The frozen historical-render list proves Spec Kitty's own earlier skill output (#7700).

Contract pinned here:

* A digest proves only the ``<skill>/<relative path>`` it shipped under.
* Every current render (raw bytes; for ``SKILL.md`` also the shared and native
  frontmatter projection) is listed, so a pull request that edits a shipped skill
  must re-run the generator.
* The reader fails closed: a missing or malformed data file proves nothing and
  never raises.
* The generator only ever adds digests (append-only).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts.skills import build_historical_skill_digests as generator
from specify_cli.runtime.asset_preparation import digest
from specify_cli.skills import historical_renders
from specify_cli.skills.catalog import resolve_builtin_skill_catalog
from specify_cli.skills.skill_frontmatter import SKILL_FILENAME, project_skill_bytes

pytestmark = pytest.mark.fast

#: sha256 of ``src/doctrine/skills/spk-run-implement-review/SKILL.md`` at ``dd83e5b6f``
#: (2026-07-13), one of the six files #7700 found stale on a user machine.
_SHIPPED_2026_07_13 = "56df985f0ef13174cda1d874929a4eb58a9b9675675f9921ad1dd6a0eb320fda"
_REGENERATE = "uv run --frozen python -m scripts.skills.build_historical_skill_digests"


def _sha256(data: bytes) -> str:
    # The same digest the install surfaces record (FileState.sha256), so the list and the sync agree.
    return str(digest(data))


@pytest.fixture(autouse=True)
def _fresh_reader_cache() -> Iterator[None]:
    historical_renders.clear_cache()
    yield
    historical_renders.clear_cache()


def test_known_historical_blob_is_proven_for_its_path() -> None:
    assert historical_renders.is_historical_render("spk-run-implement-review", "SKILL.md", _SHIPPED_2026_07_13)


def test_digest_is_not_proven_for_another_path() -> None:
    assert not historical_renders.is_historical_render("spk-run-next", "SKILL.md", _SHIPPED_2026_07_13)
    assert not historical_renders.is_historical_render("spk-run-implement-review", "references/x.md", _SHIPPED_2026_07_13)


def test_absent_digest_is_never_proven() -> None:
    assert not historical_renders.is_historical_render("spk-run-implement-review", "SKILL.md", None)
    assert not historical_renders.is_historical_render("spk-run-implement-review", "SKILL.md", "0" * 64)


def test_every_current_render_is_listed() -> None:
    registry = resolve_builtin_skill_catalog()
    assert registry is not None
    missing: list[str] = []
    for skill in registry.discover_skills():
        for source in skill.all_files:
            relative = source.relative_to(skill.skill_dir).as_posix()
            data = source.read_bytes()
            variants = [data]
            if relative == SKILL_FILENAME:
                variants += [project_skill_bytes(data, shared=shared, skill_name=skill.name) for shared in (True, False)]
            missing += [f"{skill.name}/{relative}" for variant in variants if not historical_renders.is_historical_render(skill.name, relative, _sha256(variant))]
    assert not missing, f"Shipped skill renders missing from the historical list; run `{_REGENERATE}` and commit the result: {sorted(set(missing))}"


@pytest.mark.parametrize("content", [None, b"not json", b'{"schema_version": 2, "renders": {}}', b'{"schema_version": 1, "renders": {"a/SKILL.md": ["xyz"]}}'])
def test_reader_fails_closed_on_missing_or_malformed_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: bytes | None) -> None:
    data_file = tmp_path / "historical_skill_renders.json"
    if content is not None:
        data_file.write_bytes(content)
    monkeypatch.setattr(historical_renders, "_data_bytes", lambda: data_file.read_bytes())
    assert not historical_renders.is_historical_render("spk-run-implement-review", "SKILL.md", _SHIPPED_2026_07_13)
    assert historical_renders.historical_render_digests("spk-run-implement-review", "SKILL.md") == frozenset()


def test_generator_union_never_drops_a_digest() -> None:
    existing = {"a/SKILL.md": ["b" * 64, "a" * 64], "gone/SKILL.md": ["c" * 64]}
    new = {"a/SKILL.md": {"d" * 64, "a" * 64}, "new/x.md": {"e" * 64}}
    merged = generator.merge_renders(existing, new)
    assert merged == {
        "a/SKILL.md": ["a" * 64, "b" * 64, "d" * 64],
        "gone/SKILL.md": ["c" * 64],
        "new/x.md": ["e" * 64],
    }


def test_generator_digests_cover_both_projections_for_skill_md() -> None:
    body = b"---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n"
    digests = generator.digests_for("SKILL.md", body, "demo")
    assert _sha256(body) in digests
    for shared in (True, False):
        assert _sha256(project_skill_bytes(body, shared=shared, skill_name="demo")) in digests
    assert generator.digests_for("references/x.md", b"plain", "demo") == {_sha256(b"plain")}


def test_generator_tolerates_an_unprojectable_historical_skill_md() -> None:
    broken = b"no frontmatter at all\xff"
    assert generator.digests_for("SKILL.md", broken, "demo") == {_sha256(broken)}


def test_build_keeps_every_existing_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Append-only: a digest the committed list holds survives a rebuild that history no longer yields."""
    data_file = tmp_path / generator.DATA_PATH
    data_file.parent.mkdir(parents=True)
    kept = {"gone-skill/SKILL.md": ["f" * 64]}
    data_file.write_text(generator._serialize(kept), encoding="utf-8")
    monkeypatch.setattr(generator, "_history_renders", lambda repo: {"live/SKILL.md": {"e" * 64}})

    rebuilt = generator.build(tmp_path)

    assert '"gone-skill/SKILL.md"' in rebuilt and "f" * 64 in rebuilt
    assert "e" * 64 in rebuilt


def test_generator_refuses_uncommitted_skill_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Only committed bytes enter the frozen list: an edited, uncommitted skill would be recorded forever."""
    monkeypatch.setattr(generator, "_is_shallow", lambda repo: False)
    monkeypatch.setattr(generator, "_dirty_sources", lambda repo: ["src/charter/offering/skills/x/SKILL.md"])

    assert generator.main(["--repo", str(tmp_path)]) == 2
    assert "uncommitted" in capsys.readouterr().err
