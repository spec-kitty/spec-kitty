"""Byte-parity gate for `.kittify/overrides/missions/software-dev/`.

Every file under this repository's
`.kittify/overrides/missions/software-dev/` override tier must be
byte-identical to its `packs/built-in/missions/software-dev/` counterpart
(command-templates resolve through the real
`MissionTemplateRepository.get_command_template` production seam, which
looks up `packs/built-in/missions/mission-steps/software-dev/<cmd>/prompt.md`
internally). This test pins that outcome so a future doctrine edit that
only touches the built-in copy -- and silently leaves this repository's
override stale again -- fails loudly instead of drifting unnoticed.

Positive controls: the enumerated counterpart set must be non-empty and
must contain specific known members, so a resolver/mapping bug that makes
the walk enumerate zero files -- or silently drop a whole subdirectory --
cannot pass this test vacuously. The three orphan command-templates
(`README.md`, `constitution.md`, `dashboard.md`) have no built-in
counterpart and must be reported as such, proving the mapping actually
discriminates rather than treating every override path as "has a
counterpart" or "has none."
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from charter.offering.missions.repository import MissionTemplateRepository

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OVERRIDE_ROOT = _REPO_ROOT / ".kittify" / "overrides" / "missions" / "software-dev"
_BUILT_IN_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "software-dev"
_MISSION_REPO = MissionTemplateRepository.default()

# Overrides with no built-in counterpart at all (orphans, left untouched).
_EXPECTED_NO_COUNTERPART = frozenset(
    {
        "command-templates/README.md",
        "command-templates/constitution.md",
        "command-templates/dashboard.md",
    }
)

# expected-artifacts.yaml override was deleted outright by operator decision
# rather than resynced -- it must be absent.
_EXPECTED_ARTIFACTS_RELATIVE_PATH = "expected-artifacts.yaml"


@dataclass(frozen=True)
class _Mapping:
    """One override file's resolved (or absent) built-in counterpart bytes."""

    relative_path: str
    counterpart_bytes: bytes | None


def _resolve_counterpart_bytes(relative_path: str) -> bytes | None:
    """Map an override-relative path to its built-in counterpart's bytes, or None.

    Command-templates resolve through the real production seam
    (``MissionTemplateRepository.get_command_template``) rather than a
    hand-maintained id-to-path mapping, so this test cannot drift from how
    the resolver actually locates a command template.
    """
    if relative_path.startswith("command-templates/") and relative_path.endswith(".md"):
        cmd = relative_path[len("command-templates/") : -len(".md")]
        result = _MISSION_REPO.get_command_template("software-dev", cmd)
        return result.content.encode("utf-8") if result is not None else None

    candidate = _BUILT_IN_ROOT / relative_path
    return candidate.read_bytes() if candidate.is_file() else None


def _all_override_files() -> list[str]:
    """Every file under the software-dev override dir, as posix-relative paths."""
    return sorted(str(path.relative_to(_OVERRIDE_ROOT).as_posix()) for path in _OVERRIDE_ROOT.rglob("*") if path.is_file())


def _all_mappings() -> list[_Mapping]:
    return [_Mapping(relative_path=rel, counterpart_bytes=_resolve_counterpart_bytes(rel)) for rel in _all_override_files()]


class TestOverrideParityMappingDiscriminates:
    """Positive controls: the walk enumerates real files and the mapping
    actually distinguishes counterpart-bearing files from orphans."""

    def test_override_root_exists(self) -> None:
        assert _OVERRIDE_ROOT.is_dir(), f"expected override dir at {_OVERRIDE_ROOT}"

    def test_enumerated_override_set_is_non_empty(self) -> None:
        files = _all_override_files()
        assert files, "override file walk returned zero files -- an empty walk must not silently pass the counterpart-parity checks below"

    def test_counterpart_set_is_non_empty_and_contains_known_members(self) -> None:
        mappings = _all_mappings()
        with_counterpart = {m.relative_path for m in mappings if m.counterpart_bytes is not None}
        assert with_counterpart, "no override file resolved to a built-in counterpart -- this would let the byte-equality test below pass vacuously"
        for expected in (
            "templates/spec-template.md",
            "command-templates/review.md",
            "actions/review/index.yaml",
        ):
            assert expected in with_counterpart, (
                f"expected {expected!r} to resolve to a built-in counterpart (positive control); resolved set was {sorted(with_counterpart)}"
            )

    def test_known_orphans_report_no_counterpart(self) -> None:
        mappings = {m.relative_path: m.counterpart_bytes for m in _all_mappings()}
        for orphan in _EXPECTED_NO_COUNTERPART:
            assert orphan in mappings, f"expected orphan {orphan!r} to still exist"
            assert mappings[orphan] is None, (
                f"{orphan!r} is a documented no-counterpart override "
                "(command-templates/{README,constitution,dashboard}.md) but the "
                "mapping resolved a counterpart for it -- the mapping must "
                "discriminate, not treat every path as having one"
            )

    def test_no_counterpart_set_matches_exactly(self) -> None:
        """Every no-counterpart file is a documented orphan, and every
        documented orphan is actually reported as having none -- the two
        sets are identical, not merely overlapping."""
        mappings = _all_mappings()
        actual_no_counterpart = {m.relative_path for m in mappings if m.counterpart_bytes is None}
        assert actual_no_counterpart == _EXPECTED_NO_COUNTERPART, (
            f"no-counterpart set drifted: actual={sorted(actual_no_counterpart)} expected={sorted(_EXPECTED_NO_COUNTERPART)}"
        )


class TestExpectedArtifactsDeleted:
    """The inert `expected-artifacts.yaml` override was deleted outright."""

    def test_expected_artifacts_absent(self) -> None:
        path = _OVERRIDE_ROOT / _EXPECTED_ARTIFACTS_RELATIVE_PATH
        assert not path.exists(), (
            f"{path} must be deleted, not resynced -- it was intentionally "
            "deprecated and inert, and is removed outright rather than kept "
            "in parity with a dead quirk"
        )


class TestOverrideByteParity:
    """Every override file with a built-in counterpart is byte-identical to it."""

    @pytest.mark.parametrize(
        "mapping",
        [m for m in _all_mappings() if m.counterpart_bytes is not None],
        ids=[m.relative_path for m in _all_mappings() if m.counterpart_bytes is not None],
    )
    def test_override_matches_built_in_counterpart(self, mapping: _Mapping) -> None:
        assert mapping.counterpart_bytes is not None  # narrows type for mypy
        override_path = _OVERRIDE_ROOT / mapping.relative_path
        override_bytes = override_path.read_bytes()
        assert override_bytes == mapping.counterpart_bytes, (
            f"{override_path} has drifted from its built-in counterpart -- resync "
            "it (or file an upstream gap if the built-in copy itself needs a fix "
            "first, per CLAUDE.md's canonical-sources rule)"
        )
