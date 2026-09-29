"""Scope: mock-boundary tests for charter generator — no real git."""

import os
from pathlib import Path

import pytest

from charter.activation.compiler import CompiledCharter, write_compiled_charter

pytestmark = pytest.mark.fast


@pytest.mark.requires_symlinks
def test_write_compiled_charter_ignores_stale_symlinked_charter_md(tmp_path: Path) -> None:
    """WP03 (T014b) re-pin: the retired force-clobber-rejects-symlink
    contract guarded ``charter.md`` specifically, which ``write_compiled_charter``
    no longer writes at all (data-model.md Landmine 3 -- the clobber is
    removed, not merely force-gated). A symlinked ``charter.md`` left over
    in the output dir is therefore inert to this call: the write only ever
    touches ``charter.yaml``, so the stale symlink is neither followed nor
    disturbed. (The output-*directory*-level symlink guard is still
    enforced -- see ``test_write_compiled_charter_rejects_symlinked_output_dir``.)
    """
    target = tmp_path / "outside.md"
    target.write_text("# Outside\n", encoding="utf-8")
    output_dir = tmp_path / ".kittify" / "charter"
    output_dir.mkdir(parents=True)
    try:
        os.symlink(target, output_dir / "charter.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    compiled = CompiledCharter(
        mission="software-dev",
        template_set="software-dev-default",
        selected_paradigms=[],
        selected_directives=[],
        available_tools=[],
        markdown="# Generated\n",
        references=[],
    )

    result = write_compiled_charter(output_dir, compiled, force=True)

    assert result.files_written == ["charter.yaml"]
    assert target.read_text(encoding="utf-8") == "# Outside\n"
    assert (output_dir / "charter.md").is_symlink(), "the stale symlink itself is left untouched"


@pytest.mark.requires_symlinks
def test_write_compiled_charter_rejects_symlinked_output_dir(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside-charter"
    outside_dir.mkdir()
    output_dir = tmp_path / ".kittify" / "charter"
    output_dir.parent.mkdir()
    try:
        os.symlink(outside_dir, output_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    compiled = CompiledCharter(
        mission="software-dev",
        template_set="software-dev-default",
        selected_paradigms=[],
        selected_directives=[],
        available_tools=[],
        markdown="# Generated\n",
        references=[],
    )

    with pytest.raises(FileExistsError, match="Charter output path"):
        write_compiled_charter(output_dir, compiled, force=True, repo_root=tmp_path)

    assert not (outside_dir / "charter.yaml").exists()
    assert list(outside_dir.iterdir()) == []


@pytest.mark.requires_symlinks
def test_write_compiled_charter_rejects_symlinked_output_dir_without_repo_root(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside-charter"
    outside_dir.mkdir()
    output_dir = tmp_path / ".kittify" / "charter"
    output_dir.parent.mkdir()
    try:
        os.symlink(outside_dir, output_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    compiled = CompiledCharter(
        mission="software-dev",
        template_set="software-dev-default",
        selected_paradigms=[],
        selected_directives=[],
        available_tools=[],
        markdown="# Generated\n",
        references=[],
    )

    with pytest.raises(FileExistsError, match="Charter output directory"):
        write_compiled_charter(output_dir, compiled, force=True)

    assert not (outside_dir / "charter.yaml").exists()
    assert list(outside_dir.iterdir()) == []


def test_write_compiled_charter_rejects_output_dir_that_resolves_outside_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    compiled = CompiledCharter(
        mission="software-dev",
        template_set="software-dev-default",
        selected_paradigms=[],
        selected_directives=[],
        available_tools=[],
        markdown="# Generated\n",
        references=[],
    )

    with pytest.raises(FileExistsError, match="resolves outside repository root"):
        write_compiled_charter(
            repo_root / ".." / "outside-charter",
            compiled,
            force=True,
            repo_root=repo_root,
        )

    assert not (tmp_path / "outside-charter" / "charter.md").exists()
