"""Canonical skill registry — discovers skills from the doctrine layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.skills.paths import SkillPathObservation, observe_skill_path, recheck_skill_paths, skill_path_observations


@dataclass(frozen=True)
class CanonicalSkill:
    """A single canonical skill discovered from the doctrine skills directory."""

    name: str
    skill_dir: Path
    skill_md: Path
    references: list[Path] = field(default_factory=list)
    scripts: list[Path] = field(default_factory=list)
    assets: list[Path] = field(default_factory=list)
    #: ``builtin`` for the shipped doctrine skills, ``pack`` for a charter-pack
    #: skill rendered into the staged root (ADR 2026-09-27-1). Pack skills are
    #: project-root only: they never feed a user-global asset batch.
    origin: str = "builtin"
    #: Pack source path and prepared-input hash; empty for built-in skills.
    source_ref: str = ""
    source_hash: str = ""

    @property
    def all_files(self) -> list[Path]:
        """All installable files (SKILL.md + references + scripts + assets)."""
        return [self.skill_md] + self.references + self.scripts + self.assets


def _collect_files(directory: Path) -> list[Path]:
    """Return sorted list of files in *directory*, excluding dotfiles like .gitkeep."""
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")
    )


class SkillRegistry:
    """Discovers canonical skills from a skills root directory."""

    def __init__(self, skills_root: Path) -> None:
        self._skills_root = skills_root

    def snapshot_catalog(self) -> tuple[tuple[CanonicalSkill, ...], tuple[SkillPathObservation, ...]]:
        """Read the existing inventory policy and retain membership/source inputs."""
        root = observe_skill_path(self._skills_root, members=True)
        if root.state.kind != "directory":
            raise ValueError("Required canonical skill catalog is missing or not a directory")
        observations = [root]
        skills = tuple(self.discover_skills())
        for skill in skills:
            for path in (skill.skill_dir, *(skill.skill_dir / name for name in ("references", "scripts", "assets"))):
                ancestry = skill_path_observations(self._skills_root, path)
                observations.extend(ancestry)
                if ancestry[-1].state.kind not in {"directory", "absent"}:
                    raise ValueError(f"Canonical skill directory is unsafe: {path}")
                observations.append(observe_skill_path(path, members=True))
            for path in skill.all_files:
                inputs = skill_path_observations(self._skills_root, path)
                if inputs[-1].state.kind != "file":
                    raise ValueError(f"Canonical skill source is not a regular file: {path}")
                observations.extend(inputs)
        retained = tuple(observations)
        recheck_skill_paths(retained)
        return skills, retained

    @classmethod
    def from_local_repo(cls, repo_root: Path) -> SkillRegistry:
        """Create registry from local dev checkout."""
        return cls(repo_root / "src" / "charter" / "offering" / "skills")

    @classmethod
    def from_package(cls) -> SkillRegistry:
        """Create registry from installed package.

        The doctrine skills tree now lives under the ``charter.offering``
        package (``site-packages/charter/offering/skills``), so we resolve it
        via ``importlib.resources`` directly. A development-mode fallback
        walks up from ``specify_cli`` to ``src/charter/offering/skills``.
        """
        import importlib.resources

        # Installed package: charter.offering carries the doctrine skills tree
        try:
            offering_root = importlib.resources.files("charter.offering")
            skills_path = Path(str(offering_root / "skills"))
            if skills_path.is_dir():
                return cls(skills_path)
        except (ModuleNotFoundError, TypeError):
            pass

        # Development fallback: src/charter/offering/skills relative to specify_cli
        dev_path = Path(__file__).resolve().parent.parent.parent / "charter" / "offering" / "skills"
        return cls(dev_path)

    def discover_skills(self) -> list[CanonicalSkill]:
        """Discover all valid skills in the skills root.

        Scans subdirectories for those containing a ``SKILL.md`` file and
        returns a sorted list of :class:`CanonicalSkill` objects.

        Returns an empty list when *skills_root* does not exist.
        """
        if not self._skills_root.is_dir():
            return []

        skills: list[CanonicalSkill] = []
        for child in sorted(self._skills_root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            skills.append(
                CanonicalSkill(
                    name=child.name,
                    skill_dir=child,
                    skill_md=skill_md,
                    references=_collect_files(child / "references"),
                    scripts=_collect_files(child / "scripts"),
                    assets=_collect_files(child / "assets"),
                )
            )
        return skills

    def get_skill(self, name: str) -> CanonicalSkill | None:
        """Get a specific skill by name, or ``None`` if not found."""
        for skill in self.discover_skills():
            if skill.name == name:
                return skill
        return None
