"""Org-layer advisory checkers — `OrgOverridesBuiltinChecker` and `OrgCharterDeviationChecker`.

WP07 T036 + T047 of mission ``layered-doctrine-org-layer-01KRNPEE``.

Both checkers emit ``low`` severity findings — the org layer is informational
to the project charter, never a hard gate.  Findings carry the
``org_layer`` category so operators can filter them.

These checkers degrade silently when no org pack is configured or when the
optional ``charter.activation.org_charter`` module (owned by WP09) has not
yet shipped — they simply return an empty finding list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from charter.drg import ArtifactKind
from charter.packs import RETIRED_PACK_FIELD, RetiredPackFieldError
from specify_cli.charter_runtime.lint.findings import LintFinding

KITTIFY_DIR_NAME = ".kittify"

_OVERRIDABLE_ARTIFACT_TYPES: tuple[str, ...] = tuple(kind.plural for kind in ArtifactKind if kind.core)


def _find_repo_root_from_drg(drg: Any) -> Path | None:
    """Best-effort resolution of the repo root from the merged DRG.

    The charter lint engine does not pass ``repo_root`` to checkers; we use
    the current working directory as a fallback because the engine itself
    is rooted there.  Callers that need a different root should invoke the
    checker directly.
    """
    _ = drg  # drg carries no repo-root metadata today
    cwd = Path.cwd()
    if (cwd / KITTIFY_DIR_NAME).exists():
        return cwd
    for parent in cwd.parents:
        if (parent / KITTIFY_DIR_NAME).exists():
            return parent
    return None


class OrgOverridesBuiltinChecker:
    """Advisory: the org layer overrides a built-in artifact.

    Walks every configured org pack and reports any artifact ID whose
    on-disk provenance resolves to ``"org"`` *and* whose ID also exists in
    the built-in doctrine repository.  These overrides are advisory — they
    are a legitimate org-policy lever — but operators should know that the
    built-in version has been shadowed.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root_override = repo_root

    def run(self, drg: Any, feature_scope: str | None = None) -> list[LintFinding]:
        _ = drg, feature_scope
        repo_root = self._repo_root_override or _find_repo_root_from_drg(drg)
        if repo_root is None:
            return []

        services = _resolve_override_scan_services(repo_root)
        if services is None:
            return []
        service, built_in_only = services

        findings: list[LintFinding] = []
        for artifact_type in _OVERRIDABLE_ARTIFACT_TYPES:
            findings.extend(
                _scan_artifact_type_for_overrides(artifact_type, service, built_in_only)
            )
        return findings


class OrgCharterDeviationChecker:
    """Advisory: project charter deviates from an org charter governance policy.

    Reads the merged ``org-charter.yaml`` policies via
    :func:`charter.activation.org_charter.load_org_charter_policies` (owned
    by WP09).  When the module is not yet shipped, the check returns ``[]``.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root_override = repo_root

    def run(self, drg: Any, feature_scope: str | None = None) -> list[LintFinding]:
        _ = drg, feature_scope
        repo_root = self._repo_root_override or _find_repo_root_from_drg(drg)
        if repo_root is None:
            return []

        # Optional dependency on WP09's module.  When absent, advisory is a no-op.
        try:
            from charter.activation.org_charter import (
                load_org_charter_policies,
            )
        except ImportError:
            return []

        # Landing-fold regression fix (defect 3): the previous
        # ``try/except Exception: pass`` silently degraded to an unfiltered
        # (``pack_context=None``) policy load on ANY failure, not just a
        # genuinely-absent-module case -- the byte-identical fail-open shape
        # this same commit removes from ``generate.py``. ``charter`` is
        # first-party and ships in the same wheel, so there is no legitimate
        # "not yet available" case to tolerate here; call it directly and let
        # ``charter.activation.pack_context.ActiveCharterConfigError`` (raised by
        # ``PackContext.from_config`` inside ``ProjectContext.from_repo``)
        # propagate rather than silently falling back to an unfiltered scan.
        from charter.activation.invocation_context import ProjectContext  # noqa: PLC0415

        _pack_ctx = ProjectContext.from_repo(repo_root).require_pack_context()

        try:
            policies = load_org_charter_policies(repo_root, pack_context=_pack_ctx)
        except RetiredPackFieldError as exc:
            # #3732: never drop a pack with a retired field in silence.
            return [_retired_pack_field_finding(exc)]
        except Exception:  # noqa: BLE001
            return []
        governance_policies = list(getattr(policies, "governance_policies", []) or [])
        if not governance_policies:
            return []

        project_values = _load_project_charter_fields(repo_root)
        findings: list[LintFinding] = []
        for policy in governance_policies:
            field = getattr(policy, "field", None)
            expected = getattr(policy, "value", None)
            if not isinstance(field, str):
                continue
            project_val = project_values.get(field)
            if project_val is None:
                continue
            if str(project_val) == str(expected):
                continue
            findings.append(
                LintFinding(
                    category="org_layer",
                    type="org_charter_deviation",
                    id=f"governance:{field}",
                    severity="low",
                    message=(
                        f"project charter field {field!r} = {project_val!r}; "
                        f"org charter recommends {expected!r}"
                    ),
                    remediation_hint=(
                        "Reconcile via charter interview, or document an explicit "
                        "deviation in the project charter."
                    ),
                )
            )
        return findings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _retired_pack_field_finding(exc: RetiredPackFieldError) -> LintFinding:
    """A ``high`` finding for an org pack whose ``org-charter.yaml`` carries a retired field."""
    return LintFinding(
        category="org_layer",
        type="retired_pack_field",
        id=f"{exc.file}:{exc.field}",
        severity="high",
        message=f"{RETIRED_PACK_FIELD}: {exc}",
        remediation_hint=f"Rename '{exc.field}' to '{exc.replacement}' in {exc.file}.",
    )


def _resolve_override_scan_services(repo_root: Path) -> tuple[Any, Any] | None:
    """Build the (org-layered, built-in-only) service pair for override scanning.

    Returns ``None`` when the ``charter.drg`` facade is unavailable, no org
    packs are configured, or either service fails to construct — every case
    degrades to "skip the advisory".
    """
    try:
        from charter.drg import load_pack_registry
    except ImportError:
        return None

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        return None

    # Build a service with org layer applied so provenance is populated.
    service = _build_service_with_org_layer(repo_root, registry)
    if service is None:
        return None

    # Build a built-in-only baseline to detect which IDs exist in built-in.
    built_in_only = _build_built_in_only_service(repo_root)
    if built_in_only is None:
        return None

    return service, built_in_only


def _scan_artifact_type_for_overrides(
    artifact_type: str, service: Any, built_in_only: Any
) -> list[LintFinding]:
    """Return org-overrides-builtin findings for a single artifact type."""
    org_repo = service.raw_repository(artifact_type)
    built_in_repo = built_in_only.raw_repository(artifact_type)
    if org_repo is None or built_in_repo is None:
        return []

    try:
        items = org_repo.list_all()
    except Exception:  # noqa: BLE001, S112 — degrade silently on bad pack
        return []

    findings: list[LintFinding] = []
    for item in items:
        finding = _check_item_overrides_builtin(artifact_type, item, org_repo, built_in_repo)
        if finding is not None:
            findings.append(finding)
    return findings


def _check_item_overrides_builtin(
    artifact_type: str, item: Any, org_repo: Any, built_in_repo: Any
) -> LintFinding | None:
    """Return a finding if *item* is org-provenanced and shadows a built-in artifact."""
    item_id = getattr(item, "id", None)
    if not isinstance(item_id, str):
        return None
    try:
        provenance = org_repo.get_provenance(item_id)
    except Exception:  # noqa: BLE001, S112 — provenance is advisory only
        return None
    if provenance != "org":
        return None
    try:
        builtin_match = built_in_repo.get(item_id)
    except Exception:  # noqa: BLE001
        builtin_match = None
    if builtin_match is None:
        return None
    return LintFinding(
        category="org_layer",
        type="org_overrides_builtin",
        id=f"{artifact_type}:{item_id}",
        severity="low",
        message=f"org layer overrides built-in {artifact_type[:-1]} {item_id!r}",
        remediation_hint=(
            "Verify the override is intentional; remove the org pack "
            "copy if the built-in artifact already meets policy."
        ),
    )


def _build_scan_service(repo_root: Path, *, org_roots: list[Path] | None = None) -> Any:
    """Construct the activation-aware provenance-scan service, unfiltered.

    Returns a :class:`charter.activation.resolver.ActiveCharterService` constructed with
    ``pack_context=None`` — the sanctioned "unfiltered-diagnostic" form
    named in this mission's ``data-model.md``
    (charter-sole-door-bypass-closure-01KZ3WAA WP01, FR-002 Option A,
    cycle-2 review fix for Blocker 1). The wrapper's three-state filter
    treats ``pack_context is None`` as "admit all"; this call site is
    distinguished from every activation-gated caller ONLY by that explicit
    argument, never by a different class or a raw, unwrapped
    ``charter.offering.service.CharterOfferingService`` returned directly (the cycle-1
    violation: this function previously returned the raw inner service
    under a docstring-authorized "exception" that C-002 does not sanction —
    a docstring is not an escalation, and the claimed
    ``_doctrine_collect.py`` precedent was itself an unfixed FR-002
    violation, not a sanctioned pattern).

    :class:`OrgOverridesBuiltinChecker` needs the RAW repository objects
    behind the wrapper's gated ``dict`` properties — ``.list_all()`` /
    ``.get_provenance()``, which a ``dict`` has neither of. It reaches them
    via :meth:`charter.activation.resolver.ActiveCharterService.raw_repository`, the Option
    A accessor this cycle adds (the same "filtered dict can't do repository
    ops" pattern :attr:`~charter.activation.resolver.ActiveCharterService.agent_profile_repository`
    already solves for ``agent_profiles``), instead of this function
    returning an unwrapped service. There is no charter activation
    *decision* being read here at all — only raw on-disk provenance ("which
    layer supplied this artifact"), a structural question the activation
    filter does not answer and the ``raw_repository`` accessor is
    documented as not gating.

    The inner service is built via
    :func:`charter.activation.doctrine_service_builder._build_doctrine_service` — the
    ONE function in this codebase permitted to construct a raw
    ``charter.offering.service.CharterOfferingService`` (NFR-001) — so this scan path
    shares the same ``active_languages``/``project_root`` resolution as
    every other consumer of the unified builder, rather than a bespoke
    shape that could silently drift from it.

    This helper also closes the FR-002 fail-open bug named at this module's
    two call sites: the previous code built the raw service, then
    conditionally attempted to wrap it in ``charter.activation.resolver.ActiveCharterService``
    behind a ``try/except ImportError: pass`` that silently returned the
    unwrapped service on import failure. No caller ever passed the
    ``pack_context`` that gated that attempt (verified: zero call sites), so
    the branch was dead code; per the above it would also have been the
    *wrong* fix had it ever fired. It is removed outright (DIRECTIVE_025 Boy
    Scout Rule) rather than "fixed" into a wrap that provably breaks the
    checker.

    Landing-fold regression fix (defect 3): a SECOND ``except ImportError:
    return None`` survived here, guarding the imports below. Both callers
    (:func:`_build_service_with_org_layer` / :func:`_build_built_in_only_service`)
    treat a ``None`` return as "skip the check" (``OrgOverridesBuiltinChecker.run``'s
    ``if service is None: return []`` / ``if built_in_only is None: return []``).
    ``charter.activation.doctrine_service_builder`` and ``charter.activation.resolver`` are
    first-party modules shipped in the same wheel as this one -- there is no
    legitimate partial-install scenario in which this import fails -- so the
    handler could only ever fire on a genuinely broken install, in which case
    the operator should see an ``ImportError``, not a silently empty
    org-override report. The import is left function-local (matching this
    module's lazy-import convention) but is no longer guarded.
    """
    from charter.activation.doctrine_service_builder import _build_doctrine_service
    from charter.activation.resolver import ActiveCharterService

    inner = _build_doctrine_service(repo_root, org_roots=org_roots)
    return ActiveCharterService(inner, pack_context=None)


def _build_service_with_org_layer(repo_root: Path, registry: Any) -> Any:
    """Construct an unfiltered scan service rooted at built-in + project + configured org packs.

    See :func:`_build_scan_service` for the wrapped, unfiltered-diagnostic
    construction this returns.
    """
    org_roots = [
        pack_root
        for pack in registry.packs
        if (pack_root := pack.effective_root(repo_root)).exists()
    ]
    if not org_roots:
        return None
    return _build_scan_service(repo_root, org_roots=org_roots)


def _build_built_in_only_service(repo_root: Path) -> Any:
    """Construct an unfiltered scan service rooted at built-in + project only (no org).

    The deliberate absence of an org layer is the baseline
    :class:`OrgOverridesBuiltinChecker` diffs against to detect an override;
    see :func:`_build_scan_service` for the wrapped, unfiltered-diagnostic
    construction this returns.
    """
    return _build_scan_service(repo_root)


def _load_project_charter_fields(repo_root: Path) -> dict[str, Any]:
    """Read ``.kittify/charter/interview/answers.yaml`` and return a flat field map.

    Returns an empty dict if the file is absent or unreadable — the calling
    advisory check will then emit no findings.
    """
    answers_path = repo_root / KITTIFY_DIR_NAME / "charter" / "interview" / "answers.yaml"
    if not answers_path.exists():
        return {}
    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        data = yaml.load(answers_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    # Some interview-answer files nest fields under "answers" — surface both shapes.
    nested = data.get("answers")
    flat: dict[str, Any] = {}
    if isinstance(nested, dict):
        flat.update(nested)
    for key, value in data.items():
        if key == "answers":
            continue
        flat.setdefault(key, value)
    return flat
