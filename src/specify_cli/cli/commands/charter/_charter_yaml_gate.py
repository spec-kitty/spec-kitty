"""Fail-closed soundness gate for ``charter.yaml`` before a synthesis run writes (#6415).

``charter synthesize`` keys its fresh-project seed on ``charter.yaml`` merely
*existing*, and the establishment probe behind it reads an unparseable file as
"never activated". A broken ``charter.yaml`` therefore used to take the
destructive minimal-seed path and exit 0. This gate runs before the first
write a synthesis command can make and refuses instead.

Soundness has ONE authority: :func:`charter.activation.api.load_charter_yaml_mapping`,
the activation reader's own rule (it follows the ``charter:`` pointer in
``.kittify/config.yaml``, refuses unparseable and non-mapping content, and
raises :class:`~charter.activation.api.ActiveCharterConfigError`,
``ACTIVE_CHARTER_CONFIG_INVALID``), so every charter command refuses a broken
charter identically. The only check local to this gate is for content: an
empty, whitespace-only or comment-only file and an explicit ``{}`` all load as an
empty mapping. The activation reader accepts that, since an empty activation
store is valid to read and extend. Synthesis cannot proceed from it: the fresh
seed is keyed on the file existing, so an empty mapping would take the
destructive seed path. This check is the only guard for every empty case.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.api import ActiveCharterConfigError, load_charter_yaml_mapping

__all__ = ["assert_charter_yaml_sound"]

_REMEDIATION = "Remediation: fix the YAML in the charter file named above, or re-run `spec-kitty charter generate --from-interview` to regenerate it."


def assert_charter_yaml_sound(repo_root: Path) -> None:
    """Raise :class:`ActiveCharterConfigError` when the active ``charter.yaml`` exists but is unsound.

    An absent default ``charter.yaml`` passes: the callers own that case (the
    fresh gate falls through to the adapter pipeline, which fails loud on its
    own). The error names the file (relative to *repo_root*), the parser or
    shape problem and the remedy.
    """
    loaded = load_charter_yaml_mapping(repo_root, remediation=_REMEDIATION)
    if loaded is None:
        return
    path, document = loaded
    if not document:
        display = path.relative_to(repo_root).as_posix() if path.is_relative_to(repo_root) else str(path)
        raise ActiveCharterConfigError(f"{display} is not a sound charter: it has no content (an empty mapping).\nNothing was written.\n{_REMEDIATION}")
