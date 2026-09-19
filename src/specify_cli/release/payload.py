"""Release-prep payload assembler for spec-kitty.

Reads pyproject.toml (current version), git tags (previous tag), and
kitty-specs/ artifacts (missions included in this release window).
Zero network calls (FR-014, C-002).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded

from .changelog import build_changelog_block
from .version import ReleaseChannel, propose_version

# Kept as Literal for JSON serialization compatibility
_ChannelLiteral = Literal["alpha", "beta", "stable"]


@dataclass(frozen=True)
class ReleasePrepPayload:
    """Full release-prep payload produced by ``build_release_prep_payload``.

    Fields:
        channel: The release channel used to compute the version bump.
        current_version: Version string from ``pyproject.toml``.
        proposed_version: Next version string computed from channel rules.
        changelog_block: Multi-line markdown ready to paste into CHANGELOG.md.
        proposed_changelog_block: Alias for ``changelog_block``. Included for
            downstream tooling that looks for this key in JSON output (FR-603).
        mission_slug_list: Slugs of missions included in this release window.
        target_branch: Branch being released into (always ``"main"`` for
            spec-kitty core).
        structured_inputs: Name->value pairs for the release tag/PR workflow.
            Keys: version, tag_name, release_title, release_notes_body,
            mission_slug_list (comma-separated).

    Automated by ``spec-kitty agent release prep``:
        - Changelog draft (via ``build_changelog_block``)
        - Version bump proposal (via ``propose_version``)
        - Structured release-prep payload (``structured_inputs``)
        - JSON output mode for downstream automation

    Still manual (FR-023 scope cut):
        - PR creation: ``gh pr create --title "..." --body "<changelog_block>"``
        - Tag push: ``git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z``
        - Release workflow monitoring: ``gh run watch``
    """

    channel: _ChannelLiteral
    current_version: str
    proposed_version: str
    changelog_block: str
    proposed_changelog_block: str
    mission_slug_list: list[str]
    target_branch: str
    structured_inputs: dict[str, str]


class ReleasePyprojectError(GuardedReadError):
    """``pyproject.toml`` cannot be read as a valid ``[project].version`` source.

    Raised by :func:`_read_current_version` via
    :func:`kernel.guarded_read.read_guarded` (mission cli-error-surface-seam,
    WP04/#4637) for any of three collapsed failure modes: the file is
    missing, ``[project]``/``version`` is absent, or the TOML is malformed.
    The global CLI error-presentation hook (WP01) renders this uniformly at
    exit 1 -- see ``contracts/error-envelope.md``.
    """


def _parse_current_version(content: bytes | str) -> str:
    """Extract ``[project].version`` from already-read TOML *content*.

    Accepts ``bytes | str`` to match :func:`read_guarded`'s generic ``parse``
    contract; ``read_guarded`` is called with ``mode="text"`` below, so
    *content* is always ``str`` at runtime, but the narrower annotation would
    not satisfy the primitive's declared callable type.
    """
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    data = tomllib.loads(text)
    version = data["project"]["version"]
    if not isinstance(version, str):
        raise TypeError(f"Expected version to be a string, got {type(version)!r}")
    return version


def _read_current_version(repo_root: Path) -> str:
    """Read ``version`` from ``pyproject.toml`` using stdlib ``tomllib``.

    Raises:
        ReleasePyprojectError: if ``pyproject.toml`` is missing, the TOML is
            malformed, or the ``[project]`` table / ``version`` key is
            absent. The global CLI error-presentation hook renders this
            uniformly (never a raw traceback).
    """
    pyproject_path = repo_root / "pyproject.toml"
    return read_guarded(
        pyproject_path,
        _parse_current_version,
        errors=(tomllib.TOMLDecodeError, KeyError, TypeError),
        error_cls=ReleasePyprojectError,
    )


def build_release_prep_payload(
    channel: ReleaseChannel,
    repo_root: Path,
) -> ReleasePrepPayload:
    """Assemble the full release-prep payload from local artifacts.

    Reads:
      - ``pyproject.toml`` for the current version string.
      - ``kitty-specs/`` for missions accepted since the previous git tag.
      - Local git for the previous ``v*`` tag (no network access).

    Returns:
        A fully-populated :class:`ReleasePrepPayload` ready to render or
        serialize.

    Performance:
        <= 5 seconds wall-clock on a mission with up to 16 WPs (NFR-004).
        The implementation makes at most one ``git`` subprocess call for tag
        resolution, then reads filesystem only.

    No network calls are made (FR-014, C-002). Raises :class:`ValueError` if
    the current version cannot be parsed for the requested channel.
    """
    current_version = _read_current_version(repo_root)
    proposed_version = propose_version(current_version, channel)

    changelog_block, mission_slug_list = build_changelog_block(repo_root)

    release_title = f"Release v{proposed_version}"
    tag_name = f"v{proposed_version}"
    mission_slug_csv = ", ".join(mission_slug_list)

    structured_inputs: dict[str, str] = {
        "version": proposed_version,
        "tag_name": tag_name,
        "release_title": release_title,
        "release_notes_body": changelog_block,
        "mission_slug_list": mission_slug_csv,
    }

    return ReleasePrepPayload(
        channel=channel,
        current_version=current_version,
        proposed_version=proposed_version,
        changelog_block=changelog_block,
        proposed_changelog_block=changelog_block,  # FR-603: alias for downstream tooling
        mission_slug_list=mission_slug_list,
        target_branch="main",
        structured_inputs=structured_inputs,
    )
