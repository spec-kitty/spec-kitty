"""CharterScope abstraction (Slice F WP09, FR-008..FR-011).

Resolves "which charter applies to this filesystem path" given an optional
monorepo layout declared in ``.kittify/config.yaml::charter_scopes:``.

Single-project repositories (no ``charter_scopes:`` configured) use
:meth:`CharterScope.default`, which is byte-identical to today's
repo-root-only resolution. The 23 ``test_wp_prompt_governance_contract.py``
fixtures pass unchanged (NFR-001 binding).

Public surface
--------------

``CharterScope``
    Frozen dataclass with two constructors:

    - ``CharterScope.default(repo_root)`` — single-project constructor.
    - ``CharterScope.resolve(repo_root, feature_dir)`` — monorepo-aware
      resolver: walks the configured ``charter_scopes`` list and returns
      the nearest enclosing match, or :class:`CharterScopeNotFound` /
      :class:`CharterScopeConflict` when the configuration is malformed.

``CharterScopeConfig``
    Pydantic model that validates the operator-facing
    ``.kittify/config.yaml::charter_scopes:`` payload. This is the
    FR-140 round-trip target for
    ``contracts/charter-scope-resolution.md``.

``CharterScopeConflict`` / ``CharterScopeNotFound``
    Exception surface for the two malformed-config paths called out in
    the contract.

See ADR-8 (``docs/adr/3.x/2026-05-18-1-monorepo-charter-scope.md``)
for the design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from yaml import YAMLError

from charter.activation.pack_context import CharterPackConfigError

__all__ = [
    "CharterScope",
    "CharterScopeConfig",
    "CharterScopeConflict",
    "CharterScopeNotFound",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CharterScopeConflict(Exception):
    """Raised when two configured charter scopes have incompatible nesting.

    Triggered when one scope's ``root`` is an ancestor of another's, so a
    ``feature_dir`` deep enough is claimed ambiguously. The message names
    both offending paths so the operator can resolve the configuration.
    """


class CharterScopeNotFound(Exception):
    """Raised when ``feature_dir`` is not under any configured scope's root.

    The message includes the list of configured scope roots so the operator
    can either run from inside a configured scope or extend the
    ``charter_scopes:`` configuration.
    """


# ---------------------------------------------------------------------------
# Pydantic configuration model — FR-140 round-trip target
# ---------------------------------------------------------------------------


class _CharterScopeEntry(BaseModel):
    """A single entry in ``charter_scopes:``.

    ``root`` is a repo-root-relative path (forward-slash separated) that
    must be non-empty. ``name`` is an optional operator-facing label
    surfaced in prompts, diagnostics, and catalog-miss events.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str = Field(..., description="Repo-root-relative path to the scope.")
    name: str | None = Field(
        default=None,
        description="Optional operator-facing label for the scope.",
    )

    @field_validator("root")
    @classmethod
    def _root_must_be_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError(
                "charter_scopes[].root must be a non-empty repo-relative path"
            )
        return value

    @field_validator("root")
    @classmethod
    def _root_must_be_relative_safe(cls, value: str) -> str:
        """Reject absolute paths and ``..`` segments (P2 fix 2026-05).

        An absolute ``root`` or one containing ``..`` would allow the scope
        resolver to walk outside the repository root and read (or write)
        arbitrary filesystem paths.
        """
        p = Path(value)
        if p.is_absolute():
            raise ValueError(
                f"charter_scopes[].root must be a relative path, "
                f"got absolute: {value!r}"
            )
        if ".." in p.parts:
            raise ValueError(
                f"charter_scopes[].root must not contain '..' segments: {value!r}"
            )
        return value


class CharterScopeConfig(BaseModel):
    """Operator-facing ``.kittify/config.yaml::charter_scopes:`` payload.

    Validated at config load time. Empty entries are rejected; ``name`` is
    optional. The valid/invalid round-trip examples in
    ``contracts/charter-scope-resolution.md`` are the binding shape.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    charter_scopes: list[_CharterScopeEntry] = Field(
        default_factory=list,
        description="List of per-package charter scopes for monorepos.",
    )


# ---------------------------------------------------------------------------
# Runtime resolver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharterScope:
    """Resolved charter scope for a given filesystem path.

    Attributes
    ----------
    root:
        Absolute path to the charter root. For single-project repos this
        equals ``repo_root``. For monorepos this is ``repo_root / entry.root``
        (resolved).
    name:
        Operator-facing label, or ``None`` for the single-project default.
    config_source:
        ``"repo_root_default"`` when no ``charter_scopes:`` configuration is
        present; ``"monorepo_config"`` when the scope came from the
        configured list.
    """

    root: Path
    name: str | None
    config_source: Literal["repo_root_default", "monorepo_config"]

    # -- constructors ---------------------------------------------------

    @classmethod
    def default(cls, repo_root: Path) -> CharterScope:
        """Single-project default. Byte-identical to today (NFR-001)."""
        return cls(root=repo_root, name=None, config_source="repo_root_default")

    @classmethod
    def resolve(cls, repo_root: Path, feature_dir: Path) -> CharterScope:
        """Resolve the charter scope for *feature_dir*.

        Algorithm (per ``charter-scope-resolution.md``):

        1. If ``repo_root/.kittify/config.yaml`` is absent OR its
           ``charter_scopes:`` key is empty/missing, return the default
           single-project scope.
        2. Validate the configured scopes do not have incompatible nesting
           (ancestor-of relationships) — raise :class:`CharterScopeConflict`
           if they do.
        3. Walk the configured scopes; pick the nearest enclosing ancestor
           of ``feature_dir`` (deepest path wins).
        4. If no scope encloses ``feature_dir``, raise
           :class:`CharterScopeNotFound`.
        """
        config_payload = _load_charter_scope_config(repo_root)
        if config_payload is None or not config_payload.charter_scopes:
            return cls.default(repo_root)

        # Compute absolute paths for the configured scope roots.
        # Defence-in-depth: even after Pydantic validation, assert that the
        # resolved path stays inside repo_root (P2 fix 2026-05).
        repo_root_abs = repo_root.resolve()
        scope_roots: list[tuple[Path, str | None, str]] = []
        for entry in config_payload.charter_scopes:
            resolved = (repo_root / entry.root).resolve()
            if not resolved.is_relative_to(repo_root_abs):
                raise CharterScopeConflict(
                    f"charter_scopes[].root {entry.root!r} resolves outside "
                    f"repo_root {repo_root} — refusing traversal."
                )
            scope_roots.append((resolved, entry.name, entry.root))

        # Normalise feature_dir to an absolute path.
        feature_dir_abs = (
            feature_dir if feature_dir.is_absolute() else (repo_root / feature_dir)
        ).resolve()

        # Detect incompatible nesting that would render feature_dir ambiguous.
        _validate_no_incompatible_nesting(scope_roots, feature_dir_abs)

        # Collect candidate scopes that enclose feature_dir.
        candidates = [
            (scope_root, name)
            for scope_root, name, _raw in scope_roots
            if scope_root == feature_dir_abs or scope_root in feature_dir_abs.parents
        ]
        if not candidates:
            available = [raw for _abs, _name, raw in scope_roots]
            raise CharterScopeNotFound(
                f"No charter scope encloses {feature_dir}. "
                f"Configured scopes: {available}. Either run from inside one "
                f"of the configured scopes or add an entry to "
                f".kittify/config.yaml::charter_scopes."
            )

        # Nearest enclosing = deepest path (most path parts).
        candidates.sort(key=lambda match: len(match[0].parts), reverse=True)
        winning_root, winning_name = candidates[0]
        return cls(
            root=winning_root, name=winning_name, config_source="monorepo_config"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_charter_scope_config(repo_root: Path) -> CharterScopeConfig | None:
    """Read ``.kittify/config.yaml`` and validate it into a CharterScopeConfig.

    Returns ``None`` when the file is absent — the caller defaults to a
    single-project scope.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        parsed: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise CharterPackConfigError(f"Cannot read configuration {config_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        return CharterScopeConfig()
    # CharterScopeConfig ignores unrelated keys via ConfigDict(extra="ignore").
    return CharterScopeConfig.model_validate(parsed)


def _validate_no_incompatible_nesting(
    scope_roots: list[tuple[Path, str | None, str]],
    feature_dir_abs: Path,
) -> None:
    """Raise :class:`CharterScopeConflict` if two scopes both claim
    *feature_dir_abs* via an ancestor-of relationship.

    Sibling scopes (e.g. ``packages/auth`` and ``packages/web``) are normal
    monorepo layouts and pass through; only ancestor pairs where the deeper
    scope also encloses ``feature_dir_abs`` are flagged.
    """
    for outer_path, _outer_name, outer_raw in scope_roots:
        for inner_path, _inner_name, inner_raw in scope_roots:
            if outer_path == inner_path:
                continue
            # outer is an ancestor of inner AND feature_dir is under inner
            # (or at inner): both scopes legitimately claim the path.
            if outer_path in inner_path.parents and (
                inner_path == feature_dir_abs
                or inner_path in feature_dir_abs.parents
            ):
                raise CharterScopeConflict(
                    f"Charter scope configuration is malformed: "
                    f"{outer_raw} and {inner_raw} both claim {feature_dir_abs}. "
                    f"Reorganise the configuration so each path belongs to "
                    f"exactly one scope."
                )
