"""Helpers for assembling the ``org_charter`` JSON block surfaced by ``charter context --json``.

Materialises the data structure that
:func:`charter.activation.context.build_charter_context_json` embeds under the
``org_charter`` key. Org charter composition lives in
:mod:`charter.activation.org_charter` (mission ``charter-pack-cutover-01M491G6``,
FR-010 / OD-9); this module reads policies through it and returns plain data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from charter.activation.org_charter import load_org_charter_policy
from kernel.charter_pack_paths import pack_org_charter

_EMPTY_BLOCK: dict[str, Any] = {"present": False, "packs": []}


def load_org_charter_json_block(org_roots: list[Path] | None) -> dict[str, Any]:
    """Return the ``org_charter`` JSON block for the configured org snapshots.

    Walks every supplied org snapshot path looking for an ``org-charter.yaml``
    file and merges the resulting policy summaries into a single block.
    The block shape is::

        {
            "present": bool,
            "packs": [
                {
                    "pack_name": str,
                    "governance_policies": [{..., "source": "org"}, ...],
                    "required_directives": [str, ...]
                },
                ...
            ]
        }

    Returns the empty block (``present=False``, ``packs=[]``) when:

    * ``org_roots`` is empty or ``None``;
    * none of the configured packs ship an ``org-charter.yaml``.
    """
    if not org_roots:
        return dict(_EMPTY_BLOCK)

    pack_entries: list[dict[str, Any]] = []
    for org_root in org_roots:
        if not org_root.exists():
            continue
        charter_path = pack_org_charter(org_root)
        if not charter_path.exists():
            continue
        try:
            policy = load_org_charter_policy(org_root)
        except Exception:  # noqa: BLE001, S112 — best-effort summary; continue with next pack
            continue
        if policy is None:
            continue

        governance_policies: list[dict[str, Any]] = []
        for gp in getattr(policy, "governance_policies", []) or []:
            try:
                entry = gp.model_dump() if hasattr(gp, "model_dump") else dict(gp)
            except Exception:  # noqa: BLE001, S112 — best-effort summary; skip malformed entry
                continue
            entry["source"] = "org"
            governance_policies.append(entry)

        pack_entries.append(
            {
                "pack_name": getattr(policy, "org_name", None) or org_root.name,
                "governance_policies": governance_policies,
                "required_directives": list(getattr(policy, "required_directives", []) or []),
            }
        )

    return {"present": bool(pack_entries), "packs": pack_entries}


__all__ = ["load_org_charter_json_block"]
