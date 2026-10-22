"""Fixture builders for org packs that ship pack skills (mission pack-skills-kind, WP03)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML

from charter.activation.activation_ledger import LEDGER_KEYS
from kernel.activation_ledger_store import activation_ledger_path
from tests._factories.activation_ledger import seed_activation_ledger

NAMESPACE = "acme"


def write_skill(pack_root: Path, skill_id: str, *, form: str = "prompt", expands_to: str = "builtin:spec-kitty.consolidate") -> None:
    """Write ``skills/<id>.skill.yaml`` (+ body for prompt form) into an org pack."""
    skills = pack_root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "schema_version": "1.0",
        "id": skill_id,
        "title": f"Skill {skill_id}",
        "description": f"Pack skill {skill_id}.",
        "form": form,
    }
    if form == "prompt":
        record["body_path"] = f"{skill_id}.skill.md"
        (skills / f"{skill_id}.skill.md").write_text(f"Run {skill_id}: $ARGUMENTS\n", encoding="utf-8")
    else:
        record["expands_to"] = {"target": expands_to, "args": "$ARGUMENTS"}
    with (skills / f"{skill_id}.skill.yaml").open("w", encoding="utf-8") as handle:
        YAML(typ="safe").dump(record, handle)


def write_procedure(pack_root: Path, procedure_id: str) -> None:
    """Write a minimal valid org-pack procedure."""
    procedures = pack_root / "procedures"
    procedures.mkdir(parents=True, exist_ok=True)
    (procedures / f"{procedure_id}.procedure.yaml").write_text(
        'schema_version: "1.0"\n'
        f"id: {procedure_id}\n"
        f"name: {procedure_id} fixture procedure\n"
        "purpose: >\n  Substance carried by a procedure.\n"
        "entry_condition: >\n  A skill requires it.\n"
        "exit_condition: >\n  Done.\n"
        "steps:\n  - title: Act\n    description: >\n      Do the thing.\n    actor: agent\n",
        encoding="utf-8",
    )


def write_directive(pack_root: Path, directive_id: str) -> None:
    """Write a minimal org-pack directive."""
    directives = pack_root / "directives"
    directives.mkdir(parents=True, exist_ok=True)
    (directives / f"{directive_id}.directive.yaml").write_text(f"id: {directive_id}\ntype: directive\ntitle: {directive_id}\n", encoding="utf-8")


def write_fragment(pack_root: Path, *, nodes: list[tuple[str, str]], edges: list[tuple[str, str, str]]) -> None:
    """Write a root-level DRG ``fixture.graph.yaml`` fragment (full URN endpoints)."""
    node_lines = "\n".join(f'  - urn: "{urn}"\n    kind: {kind}' for urn, kind in nodes)
    edge_lines = "\n".join(f'  - source: "{src}"\n    target: "{tgt}"\n    relation: {rel}' for src, tgt, rel in edges)
    nodes_section = f"nodes:\n{node_lines}\n" if nodes else "nodes: []\n"
    edges_section = f"edges:\n{edge_lines}\n" if edges else "edges: []\n"
    (pack_root / "fixture.graph.yaml").write_text(
        f'schema_version: "1.0"\ngenerated_at: "2026-10-04T00:00:00Z"\ngenerated_by: "test"\n{nodes_section}{edges_section}',
        encoding="utf-8",
    )


def write_org_charter(pack_root: Path, *, required_skills: list[str] | None = None, namespace: str | None = NAMESPACE) -> None:
    """Write ``org-charter.yaml`` carrying ``required_skills`` / ``skill_namespace``."""
    doc: dict[str, object] = {"org_name": "acme-org"}
    if required_skills is not None:
        doc["required_skills"] = required_skills
    if namespace is not None:
        doc["skill_namespace"] = namespace
    (pack_root / "org-charter.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")


def write_config(
    project_root: Path,
    pack_root: Path | None,
    *,
    extra: str = "",
    project_namespace: str | None = None,
    ledger: Mapping[str, Any] | None = None,
    legacy: bool = False,
) -> Path:
    """Write ``.kittify/config.yaml`` registering *pack_root* as the only org pack, plus its activation.

    The activation (``mission_type_activations: [software-dev]`` plus *ledger*)
    is seeded into the activation ledger, ``.kittify/charter/activation.yaml``,
    the shape ``init`` and the ledger migration produce (ADR 2026-10-19-1). A
    re-call replaces the ledger, so a key left out of *ledger* is absent again.

    ``legacy=True`` writes the same keys onto the pre-ledger ``config.yaml``
    surface instead: an unmigrated project, whose reads use those keys and
    whose deny writes refuse. Use it only for a test whose subject is that
    surface. *extra* carries the non-activation config (``agents:`` ...); an
    activation key in it raises, so a test cannot slip back onto the legacy
    surface unnoticed.
    """
    stray = sorted(set(yaml.safe_load(extra) or {}) & set(LEDGER_KEYS))
    if stray:
        raise ValueError(f"write_config: pass activation keys {stray} through ledger=, not extra=")
    activation: dict[str, Any] = {"mission_type_activations": ["software-dev"], **(ledger or {})}
    lines = [yaml.safe_dump(activation, sort_keys=False).rstrip("\n")] if legacy else []
    if pack_root is not None or project_namespace is not None:
        lines.append("charter_packs:")
    if pack_root is not None:
        lines += ["  org:", "    packs:", "      - name: acme", f"        local_path: {pack_root}"]
    if project_namespace is not None:
        lines += ["  project:", f"    skill_namespace: {project_namespace}"]
    config = project_root / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("".join(f"{line}\n" for line in lines) + extra, encoding="utf-8")
    activation_ledger_path(project_root).unlink(missing_ok=True)  # a re-seed replaces, never merges
    if not legacy:
        seed_activation_ledger(project_root, **activation)
    return config
