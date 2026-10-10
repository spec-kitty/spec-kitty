"""Step contract executor for Phase 6 mission composition.

This executor is intentionally a composer, not a command runner or model
caller. It resolves step contract delegations through the merged DRG and then
routes each step through ``ProfileInvocationExecutor`` so the existing
governance context, trail, and glossary chokepoint behavior remains the single
invocation primitive.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Concrete module, not the ``charter.profiles`` facade: the facade's
    # re-export types as ``Any`` under ``mypy --strict`` (same known pattern
    # as ``load_validated_graph`` below), which would leak into
    # ``_select_role_fallback``'s return type.
    from charter.activation.pack_context import PackContext
    from charter.offering.agent_profiles.profile import AgentProfile

from charter.activation._drg_helpers import load_validated_graph
from charter.drg import (
    ArtifactKind,
    DRGGraph,
    DRGLoadError,
    NodeKind,
    OrgDRGFragment,
    ResolvedContext,
    OrgPackMissingError,
    OrgPackParseError,
    OrgPackSchemaError,
    load_graph_or_dir,
    load_org_pack,
    resolve_context,
    resolve_existing_org_roots,
    resolve_org_dirs,
)
from charter.activation.drg_activation import filter_graph_by_activation, load_org_drg
from kernel.charter_pack_paths import pack_drg_fragment, project_pack_root
from charter.mission_steps import (
    MissionStepContract,
    MissionStepContractRepository,
    MissionStepContractStep,
    MissionStepInput,
)
from specify_cli.invocation.executor import InvocationPayload, ProfileInvocationExecutor
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.mission_step_contracts.profile_defaults import (
    _ACTION_PROFILE_DEFAULTS,
    _DEFAULT_PROFILE_ROLES,
    mission_default_profile_warning,
)


logger = logging.getLogger(__name__)


# Derived from the single :class:`ArtifactKind` authority: each kind maps to
# the identically-named ``NodeKind`` member (``NodeKind(k.value)``), so this
# never drifts from the enums (#5823). ``ANTI_PATTERN`` and ``SKILL`` are
# excluded -- they carry no step-contract delegation node kind here (preserving
# the prior 11-entry contents exactly).
_ARTIFACT_TO_NODE_KIND: dict[ArtifactKind, NodeKind] = {
    kind: NodeKind(kind.value) for kind in ArtifactKind if kind not in {ArtifactKind.ANTI_PATTERN, ArtifactKind.SKILL}
}


class StepContractExecutionError(RuntimeError):
    """Raised when a step contract run cannot be composed."""


@dataclass(frozen=True)
class StepContractExecutionContext:
    """Minimal context needed to execute a mission step contract."""

    repo_root: Path
    mission: str
    action: str
    actor: str = "unknown"
    profile_hint: str | None = None
    request_text: str | None = None
    mode_of_work: ModeOfWork | None = None
    resolution_depth: int = 2


@dataclass(frozen=True)
class ResolvedStepDelegation:
    """A delegation candidate selected through merged DRG resolution."""

    kind: ArtifactKind
    candidate: str
    urn: str
    label: str | None = None


@dataclass(frozen=True)
class StepContractStepResult:
    """Structured result for one composed step invocation."""

    step_id: str
    sequence: int
    description: str
    command: str | None
    command_declared: bool
    guidance: str | None
    inputs: tuple[MissionStepInput, ...] = field(default_factory=tuple)
    resolved_delegations: tuple[ResolvedStepDelegation, ...] = field(default_factory=tuple)
    unresolved_candidates: tuple[str, ...] = field(default_factory=tuple)
    invocation_payload: InvocationPayload | None = None

    @property
    def invocation_id(self) -> str | None:
        """Return the underlying invocation ID when this step was invoked."""
        if self.invocation_payload is None:
            return None
        # InvocationPayload uses ``**kwargs: object`` + ``setattr`` for storage;
        # mypy --strict therefore widens attribute access to Any. The class-level
        # annotation pins it to ``str`` at runtime — narrow back explicitly so the
        # property's declared return type is honored without a blanket ignore.
        invocation_id: str = self.invocation_payload.invocation_id
        return invocation_id


@dataclass(frozen=True)
class StepContractExecutionResult:
    """Structured result for a complete step contract run."""

    contract_id: str
    mission: str
    action: str
    profile_hint: str
    resolution_source: str
    steps: tuple[StepContractStepResult, ...]

    @property
    def invocation_ids(self) -> tuple[str, ...]:
        """Return all invocation IDs emitted by the composed run."""
        ids: list[str] = []
        for step in self.steps:
            invocation_id = step.invocation_id
            if invocation_id is not None:
                ids.append(invocation_id)
        return tuple(ids)


class StepContractExecutor:
    """Execute mission step contracts by composing profile invocations."""

    def __init__(
        self,
        *,
        repo_root: Path,
        contract_repository: MissionStepContractRepository | None = None,
        invocation_executor: ProfileInvocationExecutor | None = None,
        graph: DRGGraph | None = None,
    ) -> None:
        self._repo_root = repo_root
        # #3525 Fold B: `resolve_org_dirs` (repository overlay) and this
        # executor's DRG load (`_load_graph_degrading_malformed_org_pack` ->
        # `load_validated_graph`, below) now share the SAME chain-aware,
        # later-declared-wins resolution over ALL existing org packs — the
        # C-004 first-match-only divergence this comment used to flag is
        # closed. Charter-build-time DRG callers remain intentionally
        # org-inert (see `load_validated_graph`'s docstring); this executor
        # is a runtime caller and always resolves the full chain.
        self._contracts = contract_repository or MissionStepContractRepository(
            project_dir=project_pack_root(repo_root) / "mission_step_contracts",
            org_dirs=resolve_org_dirs(repo_root, "mission_step_contracts"),
        )
        self._invocation_executor = invocation_executor or ProfileInvocationExecutor(repo_root)
        self._graph = graph

    def execute(
        self,
        context: StepContractExecutionContext,
        contract: MissionStepContract | None = None,
    ) -> StepContractExecutionResult:
        """Execute a contract's steps in order through ``ProfileInvocationExecutor``."""
        selected_contract = contract or self._contracts.get_by_action(context.mission, context.action)
        if selected_contract is None:
            raise StepContractExecutionError(
                f"No step contract found for mission/action {context.mission}/{context.action}"
            )

        profile_hint = self._resolve_profile_hint(context, selected_contract)
        # #3525 Fold B: resolve the FULL declaration-ordered org-pack chain
        # (mirrors charter/action_governance_bundle.py:_resolve_action_bundle),
        # not just the first configured pack.
        effective_org_roots = resolve_existing_org_roots(context.repo_root)
        graph = self._graph or self._load_graph_degrading_malformed_org_pack(
            context.repo_root, effective_org_roots
        )
        # FR-031, FR-033 (WP08): apply activation filter before resolving context.
        pack_context = self._resolve_pack_context(context.repo_root)
        if pack_context is not None:
            graph = filter_graph_by_activation(graph, pack_context)
        action_urn = f"action:{selected_contract.mission}/{selected_contract.action}"
        action_context = resolve_context(graph, action_urn, depth=context.resolution_depth)

        step_results: list[StepContractStepResult] = []
        for sequence, step in enumerate(selected_contract.steps, start=1):
            resolved, unresolved = self._resolve_step_delegations(
                graph=graph,
                action_context=action_context,
                step=step,
            )
            payload = self._invocation_executor.invoke(
                self._build_request_text(
                    contract=selected_contract,
                    context=context,
                    step=step,
                    resolved_delegations=resolved,
                    unresolved_candidates=unresolved,
                ),
                profile_hint=profile_hint,
                actor=context.actor,
                mode_of_work=context.mode_of_work,
                action_hint=selected_contract.action,
            )
            try:
                step_results.append(
                    StepContractStepResult(
                        step_id=step.id,
                        sequence=sequence,
                        description=step.description,
                        command=step.command,
                        command_declared=step.command is not None,
                        inputs=tuple(step.inputs),
                        guidance=step.guidance,
                        resolved_delegations=tuple(resolved),
                        unresolved_candidates=tuple(unresolved),
                        invocation_payload=payload,
                    )
                )
            except Exception:
                self._invocation_executor.complete_invocation(
                    payload.invocation_id,
                    outcome="failed",
                    closed_by="agent",
                )
                raise
            else:
                # outcome describes the composition-step trail only; not host-LLM generation status.
                self._invocation_executor.complete_invocation(
                    payload.invocation_id, outcome="done", closed_by="agent"
                )

        return StepContractExecutionResult(
            contract_id=selected_contract.id,
            mission=selected_contract.mission,
            action=selected_contract.action,
            profile_hint=profile_hint,
            resolution_source="merged_drg",
            steps=tuple(step_results),
        )

    def _resolve_profile_hint(
        self,
        context: StepContractExecutionContext,
        contract: MissionStepContract,
    ) -> str:
        if context.profile_hint:
            return context.profile_hint
        default = _ACTION_PROFILE_DEFAULTS.get((contract.mission, contract.action))
        if default is not None:
            return self._resolve_available_default(contract, default)
        raise StepContractExecutionError(
            "profile_hint is required when no action default exists for "
            f"{contract.mission}/{contract.action}"
        )

    def _resolve_available_default(
        self,
        contract: MissionStepContract,
        default: str,
    ) -> str:
        """Return *default* when the invocation catalog can resolve it; an
        available same-role profile when it cannot (#4115); raise otherwise.

        Pre-#4115 this method's body was a bare ``return default``: a project
        that deactivated a shipped profile named in ``_ACTION_PROFILE_DEFAULTS``
        (``charter deactivate agent-profile researcher-robbie`` succeeds and
        ``charter preflight`` passes) blocked every built-in mission at that
        step with a laundered ``ProfileNotFoundError`` crash — the table named
        deactivated profiles unconditionally and offered no project-level
        remap. Resolution order:

        1. Catalog unavailable → return *default* unchanged (legacy
           behavior; the real invocation executor then surfaces
           ``ProfileNotFoundError`` exactly as before). The catalog seam is
           duck-typed because the executor accepts fake invocation executors
           (the established test pattern), which carry no registry.
        2. *default* present in the catalog → return it: byte-identical
           dispatch for every project that never deactivated it.
        3. *default* absent → role-based fallback over the SAME catalog
           ``invoke`` resolves against: the highest-``routing-priority``
           available profile carrying *default*'s role
           (``_DEFAULT_PROFILE_ROLES``), profile_id-ascending as the
           deterministic tie-break, with a WARNING naming both profiles.
           A fallback chosen from this catalog is guaranteed resolvable at
           invoke time — it can never trade the default's
           ``ProfileNotFoundError`` for the fallback's.
        4. No same-role profile → structured ``StepContractExecutionError``
           (the FR-009 composition-failure surface, not the pre-fix
           crash-laundering path) naming the mission/action, the deactivated
           default, its role, and the remedy.
        """
        catalog = self._available_profiles()
        if catalog is None or any(profile.profile_id == default for profile in catalog):
            return default
        role = _DEFAULT_PROFILE_ROLES.get(default)
        if role is not None:
            chosen = self._select_role_fallback(catalog, role)
            if chosen is not None:
                # Typed locals absorb the ``follow_imports=skip`` Any that
                # ``AgentProfile`` carries in a narrow strict check of this
                # module (the established pattern in this file, e.g.
                # ``_load_graph_degrading_malformed_org_pack``'s graph locals).
                fallback_id: str = chosen.profile_id
                fallback_priority: int = chosen.routing_priority
                logger.warning(
                    "Built-in default profile %r is not available for %s/%s; "
                    "dispatching through %r instead (role %r, routing-priority %d).",
                    default,
                    contract.mission,
                    contract.action,
                    fallback_id,
                    role,
                    fallback_priority,
                )
                return fallback_id
        role_note = f" (role '{role}')" if role is not None else ""
        raise StepContractExecutionError(
            f"No available profile for {contract.mission}/{contract.action}: the "
            f"built-in default profile '{default}'{role_note} is deactivated and "
            "no available profile carries that role. Activate an agent profile "
            "with that role, or supply an explicit profile for the step."
        )

    @staticmethod
    def _select_role_fallback(
        catalog: list[AgentProfile], role: str
    ) -> AgentProfile | None:
        """Return the deterministic same-role fallback from *catalog*, or None.

        Highest ``routing_priority`` first (the router's own tie-break
        semantics, ``invocation/router.py``); profile_id ascending breaks
        remaining ties so two same-priority candidates can never dispatch
        nondeterministically.
        """
        same_role = sorted(
            (profile for profile in catalog if role in profile.roles),
            key=lambda profile: (-profile.routing_priority, profile.profile_id),
        )
        return same_role[0] if same_role else None

    def _available_profiles(self) -> list[AgentProfile] | None:
        """Return the invocation catalog (profiles ``invoke`` can resolve).

        ``None`` when the invocation executor does not expose one (the fake
        executors tests inject), which callers treat as "cannot judge
        availability" and keep the legacy resolution — never as "the catalog
        is empty". The catalog is the same ``ProfileRegistry`` the real
        ``ProfileInvocationExecutor`` resolves ``profile_hint`` against.
        """
        list_profiles: Callable[[], list[AgentProfile]] | None = getattr(
            self._invocation_executor, "list_available_profiles", None
        )
        if list_profiles is None:
            return None
        return list_profiles()

    @staticmethod
    def _load_graph_degrading_malformed_org_pack(
        repo_root: Path, org_roots: list[Path]
    ) -> DRGGraph:
        """Load the merged DRG, degrading any malformed root in *org_roots* to
        "no contribution from that pack" instead of letting it crash
        composition.

        Mirrors ``charter.activation.action_governance_bundle._resolve_action_bundle``'s
        established handling of the same ``load_validated_graph(...,
        org_roots=...)`` call: a configured org pack whose on-disk DRG layout
        does not conform to ``load_graph_or_dir`` (no ``graph.yaml``/
        ``*.graph.yaml`` directly at its root -- this repo's own
        ``packs/internal`` is exactly this shape) must not turn every
        composition dispatch in the consuming project into a hard block.
        Before org-tier resolution was wired into this executor, such a
        misconfigured-but-registered pack was simply never exercised on this
        path, so its layout mismatch was inert; degrading here restores that
        "an optional tier being broken doesn't stop dispatch" behaviour
        without silencing the problem (D-005: WARNING, never silent --
        matches ``resolve_org_dirs``'s per-dropped-root warning; this is a
        distinct treatment from ``_resolve_expected_artifacts_slot``'s
        malformed-manifest handling, which now RAISES
        ``MalformedManifestError``/``ManifestSchemaError`` rather than
        warning-and-degrading -- see mission
        ``expected-artifacts-loader-unification-01M1C9VQ`` (#3412): that
        slot's manifest is gate-authoritative (blocks/required artifacts),
        so a corrupt manifest fails loud, whereas this DRG-org-root degrade
        is a best-effort optional-tier fallback where a WARNING is the
        correct, deliberately weaker treatment for the same class of
        problem).

        #3525 Fold B — per-root degrade: each root in *org_roots* is
        independently probed (via ``load_graph_or_dir``, the same loader
        ``load_validated_graph`` uses internally for each root) BEFORE the
        chain-wide merge, so a malformed pack #2 drops ONLY pack #2 (one
        WARNING) while pack #1 -- and every other healthy root -- still
        contributes. This replaces the pre-fix all-or-nothing degrade, which
        collapsed the ENTIRE org tier the moment any single configured root
        failed to load.

        This degrade is deliberately narrow: when *org_roots* is empty (no
        org pack configured, or none exists on disk), any ``DRGLoadError``
        raised by the single ``load_validated_graph(repo_root, org_roots=[])``
        call below is a **built-in or project** layer failure and is left to
        propagate unchanged -- the no-org-pack path stays byte-identical to
        before this mission (no per-root probing runs at all). NFR-006's
        fail-closed posture for doctrine *content* correctness is untouched:
        a broken built-in graph, or a broken project overlay, still fails the
        dispatch outright. Only the optional org tier degrades, and only for
        the specific root(s) that actually failed to load.

        Do NOT drop this pre-probe on the assumption ``load_validated_graph``
        now covers it. As of PR #3534's landing that function skips a
        *graphless* root internally (a root with no root-level ``*.graph.yaml``
        -- it warns and contributes nothing), so for that specific shape this
        probe is redundant. But this probe additionally degrades a *malformed*
        root (a present-but-invalid root-level ``*.graph.yaml``), which
        ``load_validated_graph`` deliberately still lets fail loud. Removing it
        would reopen the malformed-content crash on this dispatch path.
        """
        # #3530: the org ``drg/fragment.yaml`` layer is loaded ONCE here and
        # threaded into every ``load_validated_graph`` branch below, mirroring
        # the four correct dual-callers (``review/gate_bindings.py``,
        # ``cli/commands/charter/{activate,deactivate}.py``). Without it a pack
        # shipping only a ``drg/fragment.yaml`` (this repo's own
        # ``packs/internal`` shape) is dropped on this dispatch path -- the
        # branch-named silent drop this WP closes.
        org_fragments = StepContractExecutor._load_org_fragments_degrading(repo_root)
        # Typed locals absorb the ``charter._drg_helpers`` facade re-export (mypy
        # sees ``load_validated_graph`` as ``Any`` when this module is checked
        # alongside ``charter.drg``); the annotation restores the concrete
        # return type without a suppression (matches the pattern in
        # :meth:`_load_org_fragments_degrading`).
        if not org_roots:
            no_root_graph: DRGGraph = load_validated_graph(
                repo_root, org_roots=[], org_fragments=org_fragments
            )
            return no_root_graph

        healthy_roots: list[Path] = []
        for root in org_roots:
            try:
                load_graph_or_dir(root)
            except DRGLoadError as exc:
                StepContractExecutor._warn_dropped_org_root(root, exc)
                continue
            healthy_roots.append(root)

        merged: DRGGraph = load_validated_graph(
            repo_root, org_roots=healthy_roots, org_fragments=org_fragments
        )
        return merged

    @staticmethod
    def _load_org_fragments_degrading(repo_root: Path) -> list[OrgDRGFragment]:
        """Load the org ``drg/fragment.yaml`` layer, degrading PER-PACK on a bad pack.

        Threads ``load_org_drg(repo_root, strict=False, degrade_malformed=True)``
        so a fragment-shaped org pack reaches this composition-dispatch path.
        ``strict=False`` skips a pack that ships no ``drg/fragment.yaml`` (its
        root ``*.graph.yaml``, if any, is folded by the ``org_roots`` loop
        instead).

        ``degrade_malformed=True`` is the fix for the convergent LOW finding of
        mission ``doctrine-drg-silent-drop-boundary``: a SINGLE malformed
        optional fragment used to propagate out of ``load_org_drg`` and this
        method dropped the ENTIRE fragment layer -- evicting every healthy
        sibling's fragment too, with only a DEBUG note. That was itself a silent
        drop, ironic for the mission that closes them. The degrade now lives
        inside ``load_org_drg``'s per-pack loop, so a bad optional pack drops
        ONLY its own fragment (with an operator-visible WARNING naming the pack)
        while its healthy siblings still fold. Because the per-pack degrade
        handles the parse/schema fault class and the read-fault class (see
        the #4200 note below), this method no longer catches either here.

        The only residual fault ``load_org_drg`` can still raise on this
        non-strict path is a config-level ``NotImplementedError`` (a pack with
        an unsupported ``source:``), which ``load_pack_registry`` raises BEFORE
        the per-pack loop, so it cannot be degraded per-pack. Degrade it to an
        empty fragment layer with a WARNING (never a silent DEBUG) so an
        unsupported org tier does not hard-block every dispatch, but the
        operator is still told. Env-var / subdir-escape config faults are
        deliberately NOT caught -- they fail closed, matching
        :meth:`_resolve_pack_context`.

        #4200 defect 2: the per-pack degrade inside ``load_org_drg`` covers
        the read-fault class (``OSError`` — a permission-denied or otherwise
        unreadable optional ``drg/fragment.yaml``) alongside the parse/schema
        class, so this composition path keeps tolerating exactly the condition
        it tolerated before the loader stopped masking read faults as
        ``OrgPackParseError``; such a pack drops ONLY its own fragment (with
        the operator-visible WARNING above), never the whole layer.
        """
        try:
            # Typed local absorbs the ``charter.drg`` facade re-export (mypy sees
            # the facade symbol as ``Any``); the annotation restores the concrete
            # return type without a suppression.
            fragments: list[OrgDRGFragment] = load_org_drg(
                repo_root, strict=False, degrade_malformed=True
            )
            return fragments
        except NotImplementedError as exc:
            logger.warning(
                "Org pack registry declares an unsupported source (%s); "
                "composing this step without any org-fragment contribution. "
                "Only local_path org packs are supported -- fix or remove the "
                "entry in .kittify/config.yaml.",
                exc,
            )
            return []

    @staticmethod
    def _warn_dropped_org_root(root: Path, exc: DRGLoadError) -> None:
        """Warn (honestly) that *root* was dropped from the root-graph loop.

        #3530 warning honesty: a *fragment-shaped* org pack (a valid
        ``drg/fragment.yaml`` and no root-level ``*.graph.yaml`` -- this repo's
        own ``packs/internal`` is exactly this shape) cannot be read by
        ``load_graph_or_dir`` (root graphs only), but its content DOES arrive via
        the ``org_fragments`` layer. Emitting the "without this org pack's
        contribution" WARNING for it would misattribute a folded pack as a
        dropped one, so degrade to a DEBUG note. A root that fails to load AND
        contributes no valid fragment (a present-but-invalid root graph, or a
        root with neither a graph nor a loadable fragment) is genuinely lost and
        still WARNs.
        """
        if StepContractExecutor._org_root_folds_fragment(root):
            logger.debug(
                "Org pack DRG at %s ships a drg/fragment.yaml and no root "
                "*.graph.yaml; folding it via the org-fragment layer rather "
                "than the root-graph loop.",
                root,
            )
            return
        logger.warning(
            "Org pack DRG at %s failed to load (%s: %s); composing this "
            "step with the remaining doctrine layers, without this "
            "org pack's contribution.",
            root,
            type(exc).__name__,
            exc,
        )

    @staticmethod
    def _org_root_folds_fragment(root: Path) -> bool:
        """True iff *root* ships a ``drg/fragment.yaml`` that loads cleanly.

        Distinguishes a *folded* fragment-shaped pack (whose content reaches the
        merged graph via the org-fragment layer) from a genuinely lost root, so
        the pre-probe's degrade WARNING stays honest. The ``pack_name``/
        ``layer_index`` passed here only affect labelling, not whether the
        fragment parses, so a probe-local name and index are sufficient.

        #4200 defect 2: an unreadable fragment (``OSError`` — e.g. a
        permission-denied ``drg/fragment.yaml``) answers ``False`` (a
        genuinely lost root), never raises — the loader presents read faults
        as the I/O fault they are rather than masking them as
        ``OrgPackParseError``, so this probe tolerates the fault class by
        name.
        """
        if not pack_drg_fragment(root).is_file():
            return False
        try:
            load_org_pack(root.name, root, 1)
        except (
            OrgPackMissingError,
            OrgPackParseError,
            OrgPackSchemaError,
            NotImplementedError,
            OSError,
        ):
            return False
        return True

    def _resolve_pack_context(self, repo_root: Path) -> PackContext | None:
        """Construct a PackContext from project config for activation filtering.

        FR-031, FR-033 (WP08): Obtain pack_context from project config so the
        activation filter can narrow the DRG before context resolution.
        Returns ``None`` on any error so the filter is always optional.
        """
        from charter.drg import (
            OrgPackEnvVarUnsetError,
            OrgPackSubdirEscapeError,
        )

        try:
            from charter.activation.pack_context import PackContext  # noqa: PLC0415

            return PackContext.from_config(repo_root)
        except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError):
            # Fail closed (FR-003): an unset env var or a symlink-escape is
            # operator-actionable, not "activation filter unavailable" —
            # silently degrading here would run the mission-step DRG
            # unfiltered instead of surfacing the real config problem.
            raise
        except Exception:  # noqa: BLE001 — defensive; activation filter is optional
            return None

    def _resolve_step_delegations(
        self,
        *,
        graph: DRGGraph,
        action_context: ResolvedContext,
        step: MissionStepContractStep,
    ) -> tuple[list[ResolvedStepDelegation], list[str]]:
        if step.delegates_to is None:
            return [], []

        kind = step.delegates_to.kind
        resolved: list[ResolvedStepDelegation] = []
        unresolved: list[str] = []
        selected_urns = action_context.artifact_urns

        for candidate in step.delegates_to.candidates:
            urn = self._candidate_urn(graph, kind, candidate)
            if urn is None or urn not in selected_urns:
                unresolved.append(candidate)
                continue
            node = graph.get_node(urn)
            resolved.append(
                ResolvedStepDelegation(
                    kind=kind,
                    candidate=candidate,
                    urn=urn,
                    label=node.label if node is not None else None,
                )
            )
        return resolved, unresolved

    def _candidate_urn(
        self,
        graph: DRGGraph,
        kind: ArtifactKind,
        candidate: str,
    ) -> str | None:
        node_kind = _ARTIFACT_TO_NODE_KIND.get(kind)
        if node_kind is None:
            return None

        direct = f"{kind.value}:{candidate}"
        direct_node = graph.get_node(direct)
        if direct_node is not None and direct_node.kind == node_kind:
            return direct

        directive_urn = self._directive_candidate_urn(candidate) if kind == ArtifactKind.DIRECTIVE else None
        if directive_urn is not None:
            directive_node = graph.get_node(directive_urn)
            if directive_node is not None and directive_node.kind == node_kind:
                return directive_urn

        matches: list[str] = [
            str(node.urn)
            for node in graph.nodes
            if node.kind == node_kind and node.urn.split(":", 1)[1] == candidate
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _directive_candidate_urn(candidate: str) -> str | None:
        numeric = ""
        for char in candidate:
            if not char.isdigit():
                break
            numeric += char
        if not numeric:
            return None
        return f"directive:DIRECTIVE_{numeric.zfill(3)}"

    def _build_request_text(
        self,
        *,
        contract: MissionStepContract,
        context: StepContractExecutionContext,
        step: MissionStepContractStep,
        resolved_delegations: list[ResolvedStepDelegation],
        unresolved_candidates: list[str],
    ) -> str:
        lines = [
            f"Execute mission step contract {contract.id} ({contract.mission}/{contract.action}).",
            f"Step {step.id}: {step.description}",
        ]
        if context.request_text:
            lines.append(f"Run request: {context.request_text}")
        if step.command:
            lines.append(f"Declared command: {self._render_declared_command(step)}")
            lines.append("Command status: declared only; the host/operator owns execution.")
        elif step.inputs:
            joined = " ".join(
                self._format_step_input(input_spec) for input_spec in step.inputs
            )
            lines.append(f"Declared step inputs: {joined}")
        if resolved_delegations:
            joined = ", ".join(delegation.urn for delegation in resolved_delegations)
            lines.append(f"Resolved delegations: {joined}")
        if unresolved_candidates:
            joined = ", ".join(unresolved_candidates)
            lines.append(f"Unresolved delegation candidates: {joined}")
        if step.guidance:
            lines.append(f"Step guidance: {step.guidance}")
        return "\n".join(lines)

    def _render_declared_command(self, step: MissionStepContractStep) -> str:
        if not step.command or not step.inputs:
            return step.command or ""
        joined = " ".join(
            self._format_step_input(input_spec) for input_spec in step.inputs
        )
        return f"{step.command} {joined}"

    @staticmethod
    def _format_step_input(input_spec: MissionStepInput) -> str:
        rendered = f"{input_spec.flag} {{{input_spec.source}}}"
        if input_spec.optional:
            return f"[{rendered}]"
        return rendered


__all__ = [
    "ResolvedStepDelegation",
    "StepContractExecutionContext",
    "StepContractExecutionError",
    "StepContractExecutionResult",
    "StepContractExecutor",
    "StepContractStepResult",
    "mission_default_profile_warning",
]
