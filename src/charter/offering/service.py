"""Charter offering service: lazy access to every artifact repository of the offering."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from charter.offering.shared.scoping import normalize_languages
from charter.offering.agent_profiles import AgentProfileRepository
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from charter.offering.assets import AssetRepository
from charter.offering.directives import DirectiveRepository
from charter.offering.glossary_packs import GlossaryPackRepository
from charter.offering.missions.step_contracts import MissionStepContractRepository
from charter.offering.pack_skills import PackSkillRepository
from charter.offering.paradigms import ParadigmRepository
from charter.offering.procedures import ProcedureRepository
from charter.offering.styleguides import StyleguideRepository
from charter.offering.tactics import TacticRepository
from charter.offering.toolguides import ToolguideRepository
from kernel.charter_pack_paths import KITTIFY_DIRNAME, PROJECT_PACK_DIRNAME


def _is_project_pack_root(root: Path) -> bool:
    """Return whether *root* is a project pack root (``.kittify/charter-packs``)."""
    return root.name == PROJECT_PACK_DIRNAME and root.parent.name == KITTIFY_DIRNAME


class CharterOfferingService:
    """Lazy, unfiltered aggregation over the charter offering's artifact repositories.

    Raw by design: it applies no activation filter. Activation-aware callers
    wrap it in the activation-aware service of :mod:`charter.activation.resolver`.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        org_roots: list[Path] | None = None,
        active_languages: list[str] | tuple[str, ...] | None = None,
        agent_profile_overlay_dir: Path | None = None,
    ) -> None:
        self._project_root = project_root
        self._org_roots = org_roots or []
        self._active_languages = None if active_languages is None else normalize_languages(active_languages)
        # #3176 (WP02): optional override for the agent-profile project overlay
        # directory. When set, the ``agent_profiles`` property points its
        # project layer at this path (e.g. ``.kittify/agent_profiles``) instead
        # of the project-root ``agent_profiles`` dir ``_project_dir`` derives.
        # Only ``agent_profiles`` consults it; every other repository is
        # unaffected. Default ``None`` ⇒ byte-identical behaviour (NFR-002).
        self._agent_profile_overlay_dir = agent_profile_overlay_dir
        self._cache: dict[str, object] = {}

    def _project_dir(self, artifact: str) -> Path | None:
        if self._project_root is None:
            return None
        if _is_project_pack_root(self._project_root):
            # Consume the single hoisted authority (WP03/WP04, contract A-5) so
            # scaffolder and resolver cannot disagree. Fail-closed: an unknown
            # plural raises rather than falling through a silent default.
            kind = ArtifactKind.from_plural(artifact)
            return self._project_root / PROJECT_KIND_DIRS[kind]
        return self._project_root / artifact

    def _org_dirs(self, artifact: str) -> list[Path]:
        """Return per-pack org-layer directories for *artifact* in declaration order.

        Each configured org root contributes one directory: ``<org_root>/<artifact>``.
        Repositories iterate this list in order, so later packs override earlier ones
        for the same artifact ID (FR-006, C-004). Non-existent directories are
        retained in the returned list; existence checks happen at load time.
        """
        return [root / artifact for root in self._org_roots]

    @property
    def directives(self) -> DirectiveRepository:
        if "directives" not in self._cache:
            self._cache["directives"] = DirectiveRepository(
                org_dirs=self._org_dirs("directives"),
                project_dir=self._project_dir("directives"),
            )
        return cast(DirectiveRepository, self._cache["directives"])

    @property
    def tactics(self) -> TacticRepository:
        if "tactics" not in self._cache:
            self._cache["tactics"] = TacticRepository(
                org_dirs=self._org_dirs("tactics"),
                project_dir=self._project_dir("tactics"),
                active_languages=self._active_languages,
            )
        return cast(TacticRepository, self._cache["tactics"])

    @property
    def styleguides(self) -> StyleguideRepository:
        if "styleguides" not in self._cache:
            self._cache["styleguides"] = StyleguideRepository(
                org_dirs=self._org_dirs("styleguides"),
                project_dir=self._project_dir("styleguides"),
                active_languages=self._active_languages,
            )
        return cast(StyleguideRepository, self._cache["styleguides"])

    @property
    def toolguides(self) -> ToolguideRepository:
        if "toolguides" not in self._cache:
            self._cache["toolguides"] = ToolguideRepository(
                org_dirs=self._org_dirs("toolguides"),
                project_dir=self._project_dir("toolguides"),
                active_languages=self._active_languages,
            )
        return cast(ToolguideRepository, self._cache["toolguides"])

    @property
    def paradigms(self) -> ParadigmRepository:
        if "paradigms" not in self._cache:
            self._cache["paradigms"] = ParadigmRepository(
                org_dirs=self._org_dirs("paradigms"),
                project_dir=self._project_dir("paradigms"),
            )
        return cast(ParadigmRepository, self._cache["paradigms"])

    @property
    def procedures(self) -> ProcedureRepository:
        if "procedures" not in self._cache:
            self._cache["procedures"] = ProcedureRepository(
                org_dirs=self._org_dirs("procedures"),
                project_dir=self._project_dir("procedures"),
                active_languages=self._active_languages,
            )
        return cast(ProcedureRepository, self._cache["procedures"])

    @property
    def mission_step_contracts(self) -> MissionStepContractRepository:
        if "mission_step_contracts" not in self._cache:
            self._cache["mission_step_contracts"] = MissionStepContractRepository(
                org_dirs=self._org_dirs("mission_step_contracts"),
                project_dir=self._project_dir("mission_step_contracts"),
            )
        return cast(MissionStepContractRepository, self._cache["mission_step_contracts"])

    @property
    def glossary_packs(self) -> GlossaryPackRepository:
        if "glossary_packs" not in self._cache:
            self._cache["glossary_packs"] = GlossaryPackRepository(
                org_dirs=self._org_dirs("glossary_packs"),
                project_dir=self._project_dir("glossary_packs"),
            )
        return cast(GlossaryPackRepository, self._cache["glossary_packs"])

    @property
    def skills(self) -> PackSkillRepository:
        if "skills" not in self._cache:
            self._cache["skills"] = PackSkillRepository(
                org_dirs=self._org_dirs("skills"),
                project_dir=self._project_dir("skills"),
            )
        return cast(PackSkillRepository, self._cache["skills"])

    @property
    def assets(self) -> AssetRepository:
        if "assets" not in self._cache:
            self._cache["assets"] = AssetRepository(
                org_dirs=self._org_dirs("assets"),
                project_dir=self._project_dir("assets"),
            )
        return cast(AssetRepository, self._cache["assets"])

    @property
    def agent_profiles(self) -> AgentProfileRepository:
        if "agent_profiles" not in self._cache:
            project_dir = self._agent_profile_overlay_dir if self._agent_profile_overlay_dir is not None else self._project_dir("agent_profiles")
            self._cache["agent_profiles"] = AgentProfileRepository(
                org_dirs=self._org_dirs("agent_profiles"),
                project_dir=project_dir,
                active_languages=self._active_languages,
            )
        return cast(AgentProfileRepository, self._cache["agent_profiles"])
