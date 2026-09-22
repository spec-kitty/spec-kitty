"""Shrink-only ratchet over `pyproject.toml`'s `[tool.ruff.format].exclude`.

Issue #559 (filed by the adversarial squad reviewing #531, which introduced
the exclude list): the formatter-debt baseline was unpinned in both
directions — nothing stopped it growing (a new unformatted file could be
appended and the gate would stay green) and nothing caught stale entries
(a reformatted or renamed file's entry silently drops out of the gate
forever). This guard closes both gaps the same way
`test_tid251_enforcement.py` closed the whole-directory `per-file-ignores`
scope hole: assert the property live, against the real ruff config, rather
than trusting the list's own header comment.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Shrink-only high-water mark. #559 dropped the list from 2,812 to 2,809 by
# removing three dead entries under `kitty-specs/isolated-home-pin-guard-r1a-
# 01KZNMA3/research/` that `ruff.toml`'s `extend-exclude` already drops from
# collection independently. Growing the list requires bumping this constant
# in the same PR as the new entry, which is the point of the ratchet.
_BASELINE_EXCLUDE_COUNT = 2808


def _load_exclude_list() -> list[str]:
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return config["tool"]["ruff"]["format"]["exclude"]


def test_exclude_list_does_not_exceed_baseline() -> None:
    """Growth requires an explicit, reviewed bump of `_BASELINE_EXCLUDE_COUNT`."""
    entries = _load_exclude_list()
    assert len(entries) <= _BASELINE_EXCLUDE_COUNT, (
        f"`[tool.ruff.format].exclude` grew to {len(entries)} entries, above "
        f"the pinned baseline of {_BASELINE_EXCLUDE_COUNT}. A new formatter-"
        "debt entry needs a bump of `_BASELINE_EXCLUDE_COUNT` in this file "
        "in the same PR, with a reason the new file cannot simply be "
        "formatted instead."
    )


def test_exclude_list_has_no_duplicate_or_glob_entries() -> None:
    """The baseline is a flat list of exact paths, never a glob or a repeat.

    A glob or duplicate would let one line quietly cover more files than the
    header comment's "remove entries as files are reformatted" policy can
    account for.
    """
    entries = _load_exclude_list()
    duplicates = {entry for entry in entries if entries.count(entry) > 1}
    assert not duplicates, f"Duplicate exclude entries: {sorted(duplicates)}"
    globs = [entry for entry in entries if "*" in entry]
    assert not globs, f"Glob exclude entries widen scope silently: {globs}"


def test_every_exclude_entry_exists_on_disk() -> None:
    """A renamed or deleted file's entry must be removed, not left dangling.

    A dangling entry is a permanently-unguarded path with no signal that it
    ever mattered — the second gap #559 identified.
    """
    entries = _load_exclude_list()
    missing = [entry for entry in entries if not (_REPO_ROOT / entry).exists()]
    assert not missing, (
        f"{len(missing)} exclude entries no longer exist on disk: "
        f"{missing[:20]}{'...' if len(missing) > 20 else ''}. Remove stale "
        "entries when their file is renamed or deleted."
    )


def test_every_exclude_entry_still_genuinely_reformats() -> None:
    """No entry may protect a file that already passes `ruff format --check`.

    Once a file is reformatted, its entry becomes dead weight: it still
    silently drops the file out of the format gate even though the gate
    would now pass anyway. Passing every entry explicitly bypasses the
    exclude list itself (explicit paths on the command line are always
    checked), so a file that ruff would now format cleanly shows up as
    absent from the "Would reformat" output.
    """
    entries = _load_exclude_list()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "--no-cache",
            *entries,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    reformatted = {line.removeprefix("Would reformat: ").strip() for line in proc.stdout.splitlines() if line.startswith("Would reformat: ")}
    unformattable = {
        line.removeprefix("error: Failed to format ").split(":", 1)[0].strip() for line in proc.stderr.splitlines() if line.startswith("error: Failed to format ")
    }
    assert not unformattable, (
        f"{len(unformattable)} exclude entries cannot be checked by "
        f"`ruff format`: {sorted(unformattable)[:20]}"
        f"{'...' if len(unformattable) > 20 else ''}. This is not evidence "
        "that they are formatted; remove the invalid entry or use a "
        "formatter that supports it.\nruff stderr:\n"
        f"{proc.stderr}"
    )
    assert proc.returncode in (0, 1), (
        f"`ruff format --check` failed before the clean-entry inference could be made.\nreturn code: {proc.returncode}\nruff stderr:\n{proc.stderr}"
    )
    already_clean = [entry for entry in entries if entry not in reformatted and entry not in unformattable]
    assert not already_clean, (
        f"{len(already_clean)} exclude entries are already formatted and no "
        f"longer need the exclusion: {already_clean[:20]}"
        f"{'...' if len(already_clean) > 20 else ''}. Remove them from "
        "`[tool.ruff.format].exclude`.\nruff stderr:\n"
        f"{proc.stderr}"
    )


def test_unformattable_exclude_entry_is_not_reported_as_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A formatter error must not be mistaken for a successful clean check."""
    monkeypatch.setattr(sys.modules[__name__], "_load_exclude_list", lambda: ["README.md"])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="",
            stderr=("error: Failed to format README.md: Markdown formatting is experimental, enable preview mode.\n"),
        ),
    )

    with pytest.raises(AssertionError) as caught:
        test_every_exclude_entry_still_genuinely_reformats()

    failure = str(caught.value)
    assert "cannot be checked by `ruff format`" in failure
    assert "README.md" in failure
    assert "already formatted" not in failure


def test_unexpected_ruff_failure_is_not_reported_as_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any other ruff failure is reported as a failed check, not cleanliness."""
    monkeypatch.setattr(sys.modules[__name__], "_load_exclude_list", lambda: ["example.py"])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="",
            stderr="error: Internal ruff failure\n",
        ),
    )

    with pytest.raises(AssertionError, match="failed before the clean-entry inference"):
        test_every_exclude_entry_still_genuinely_reformats()
