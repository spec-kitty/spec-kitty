"""Org-tier ``expected-artifacts.yaml`` override (FR-008, WP05).

``MissionTemplateRepository`` (``doctrine/missions/repository.py``) is a
bespoke, single-root reader with no org-tier or project-tier mechanism of any
kind (C-003 forbids restructuring it into a ``BaseArtifactRepository``
subclass or adding a new method to it). This module is the free-function,
sibling-module seam that gives an org pack a way to override
``<org_root>/missions/<mission_type>/expected-artifacts.yaml`` without
touching that class.

Contract C-4 (``kitty-specs/up-org-doctrine-consumers-01M05YAB/contracts/org-tier-resolution-contract.md``):
Contract C-4's own code sample cites the pre-fix path
(``<org_root>/<mission_type>/expected-artifacts.yaml``) — that frozen
historical document is not kept in sync with this bugfix; see
:func:`resolve_org_expected_artifacts`'s docstring for the current, correct
on-disk path.

* **Precedence within ``org_roots``**: last-EXISTING-match wins (the common
  ``org_dirs``-style later-wins convention, NFR-003) — the opposite of
  FR-002's first-match DRG ``org_root`` resolution. FR-008 is new surface
  with no pre-existing first-match precedent to inherit.
* **Precedence vs. built-in**: whole-file replacement, never a field-merge.
  When an org file resolves, callers must not read the built-in file at all
  for that mission type.
* **No built-in baseline required**: a wholly org-defined custom mission
  type is valid input — this helper never consults the built-in tree itself.

Both callers (``charter.activation.mission_type_profiles._resolve_expected_artifacts_slot``
and ``specify_cli.dossier.manifest.ManifestRegistry.load_manifest``) pass
**raw**, existence-filtered org roots (``resolve_org_roots(repo_root)``
filtered to ``.exists()``) — not ``resolve_org_dirs``-style subdir-joined
output — because ``mission_type`` varies per call and cannot be baked into a
fixed ``subdir`` string the way ``"mission_step_contracts"`` or
``"mission_types"`` can.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.missions.repository import MalformedManifestError

__all__ = ["resolve_org_expected_artifacts"]

_EXPECTED_ARTIFACTS_FILENAME = "expected-artifacts.yaml"


def resolve_org_expected_artifacts(
    org_roots: list[Path], mission_type: str
) -> Mapping[str, Any] | None:
    """Return the parsed org-tier ``expected-artifacts.yaml`` for *mission_type*.

    Checks each *org_roots* entry (already existence-filtered by the caller,
    per this WP's Context section — this helper does not re-check
    ``org_root.exists()`` itself) for
    ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``, in the
    order given. The **last** entry with a parseable matching file wins (NFR-003
    declared-order precedence) — a later ``org_roots`` entry with no
    matching file does not clear an earlier match; only a later *match*
    overrides an earlier one.

    A present org file is a whole-file replacement: it is returned verbatim
    (as a parsed mapping), never merged with the built-in manifest or with
    an earlier org root's file for the same mission type — callers must not
    field-merge the result.

    Returns ``None`` only for genuine absence: no *org_roots* entry has a
    matching file for *mission_type* (Invariant I1). A file that IS present
    for some *org_roots* entry but fails to parse as YAML, is unreadable
    (``OSError``/``UnicodeDecodeError``), or does not parse to a YAML
    mapping raises :class:`~charter.offering.missions.repository.MalformedManifestError`
    (FR-007/FR-012, #3412) instead of being treated as "no matching file"
    — mirroring ``MissionTemplateRepository.get_expected_artifacts``'s
    fail-loud behaviour on the built-in tier (the sibling-error model,
    D2). A malformed *org* file hides a genuine misconfiguration an
    operator authored and expected to take effect, so it is never silently
    substituted with an earlier root's good match or degraded to "not
    overridden" (C-006) — the raise propagates immediately, before any
    later *org_roots* entry is even consulted.
    """
    result: Mapping[str, Any] | None = None
    for org_root in org_roots:
        path = org_root / "missions" / mission_type / _EXPECTED_ARTIFACTS_FILENAME
        parsed = _read_yaml_mapping(path)
        if parsed is not None:
            result = parsed
    return result


def _read_yaml_mapping(path: Path) -> Mapping[str, Any] | None:
    """Read *path* as a YAML mapping.

    Returns ``None`` only for genuine absence (``not path.is_file()``,
    Invariant I1). A PRESENT file that fails to parse as YAML, cannot be
    read/decoded (``OSError``/``UnicodeDecodeError``, FR-012), or does not
    parse to a YAML mapping raises
    :class:`~charter.offering.missions.repository.MalformedManifestError`
    (FR-007, #3412) instead of degrading to "no override" — see
    :func:`resolve_org_expected_artifacts`'s docstring for the rationale
    (an operator authored this file and expects it to take effect).
    """
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        yaml = YAML(typ="safe")
        parsed = yaml.load(content)
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise MalformedManifestError(path, exc) from exc
    if not isinstance(parsed, Mapping):
        raise MalformedManifestError(
            path, TypeError(f"expected a YAML mapping, got {type(parsed).__name__}")
        )
    return parsed
