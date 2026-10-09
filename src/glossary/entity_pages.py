"""Glossary entity page renderer.

Reverse-walks ``vocabulary`` edges in the merged DRG and produces a
regenerable Markdown entity page per glossary term at::

    .kittify/charter/compiled/glossary/<term-urn-slug>.md

Pages are build artifacts — gitignored, never committed, idempotent on
re-run. Writes are atomic: write to ``.md.tmp``, then ``rename`` to
``.md``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from glossary.semantic_events import iter_semantic_conflicts
from kernel.charter_pack_paths import project_pack_root

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class BacklinkEntry:
    """A single inbound reference from a DRG artifact to a glossary term."""

    source_id: str  # DRG node URN of the referencing artifact
    source_type: str  # "wp" | "adr" | "mission_step" | "retro_finding" | "charter_section" | "other"
    label: str  # human-readable label (e.g., "WP03 — Entity Page Renderer")
    artifact_path: str | None = None  # relative path to the artifact file, if resolvable


@dataclass
class _TermRecord:
    """Internal: a glossary term node plus its backlinks."""

    urn: str
    label: str | None
    definition: str
    provenance: str | None
    backlinks: list[BacklinkEntry] = field(default_factory=list)


class TermNotFoundError(Exception):
    """Raised by ``generate_one()`` when the term URN is not in the DRG."""


# ---------------------------------------------------------------------------
# DRG loader
# ---------------------------------------------------------------------------


def _load_merged_drg(repo_root: Path) -> Any | None:
    """Load the merged DRG from ``graph.yaml``.

    Returns a ``DRGGraph`` instance, or ``None`` if:
    - the ``doctrine`` package is not importable, or
    - the graph file does not exist, or
    - any other error occurs.
    """
    try:
        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        drg_dir = project_pack_root(repo_root)
        candidates = ["graph.yaml", "merged_drg.json", "drg.json", "compiled_drg.json"]
        for name in candidates:
            p = drg_dir / name
            if p.exists():
                text = p.read_text(encoding="utf-8")
                if name.endswith(".yaml") or name.endswith(".yml"):
                    yaml = YAML()
                    raw = yaml.load(text)
                else:
                    raw = json.loads(text)
                return DRGGraph.model_validate(raw)
        return None
    except Exception:  # noqa: BLE001
        logger.debug("entity_pages: DRG not available", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class GlossaryEntityPageRenderer:
    """Render per-term Markdown entity pages from the merged DRG."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._output_dir = repo_root / ".kittify" / "charter" / "compiled" / "glossary"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_all(self) -> list[Path]:
        """Generate entity pages for all glossary terms in the merged DRG.

        Returns a list of written paths.  Returns ``[]`` silently when the
        DRG is not available (WP5.1 external dependency may be absent).
        """
        drg = _load_merged_drg(self._repo_root)
        if drg is None:
            logger.warning("entity_pages: merged DRG not found — skipping generation")
            return []

        records = self._extract_term_records(drg)
        written: list[Path] = []
        for rec in records:
            content = self._render_page(rec)
            path = self._write_page(rec.urn, content)
            written.append(path)
        return written

    def generate_one(self, term_id: str) -> Path:
        """Generate the entity page for a single term URN.

        Raises ``TermNotFoundError`` if the DRG is unavailable or the term
        is not found.
        """
        drg = _load_merged_drg(self._repo_root)
        if drg is None:
            raise TermNotFoundError(f"DRG not available (term: {term_id})")

        records = self._extract_term_records(drg)
        matching = [r for r in records if r.urn == term_id]
        if not matching:
            raise TermNotFoundError(f"Term not found in DRG: {term_id}")

        rec = matching[0]
        content = self._render_page(rec)
        return self._write_page(rec.urn, content)

    # ------------------------------------------------------------------
    # DRG traversal
    # ------------------------------------------------------------------

    def _extract_term_records(self, drg: Any) -> list[_TermRecord]:
        """Build ``_TermRecord`` objects for every ``glossary:*`` node."""
        backlink_index = self._build_backlink_index(drg)
        records: list[_TermRecord] = []

        for node in drg.nodes:
            urn = getattr(node, "urn", None) or ""
            if not urn.startswith("glossary:"):
                continue
            node_label = getattr(node, "label", None)
            # Definition lives in metadata when present; fall back to label or placeholder
            definition = (
                getattr(node, "definition", None)
                or node_label
                or "_No definition recorded._"
            )
            provenance = getattr(node, "provenance", None)
            records.append(
                _TermRecord(
                    urn=urn,
                    label=node_label,
                    definition=definition,
                    provenance=provenance,
                    backlinks=backlink_index.get(urn, []),
                )
            )
        return records

    def _build_backlink_index(self, drg: Any) -> dict[str, list[BacklinkEntry]]:
        """Return ``{ glossary_urn -> [BacklinkEntry, ...] }`` for vocabulary edges."""
        index: dict[str, list[BacklinkEntry]] = {}
        for edge in drg.edges:
            # DRGEdge uses ``relation`` (a Relation enum / str) not ``type``
            relation = getattr(edge, "relation", None)
            relation_val = getattr(relation, "value", str(relation) if relation else "")
            if relation_val != "vocabulary":
                continue
            target = getattr(edge, "target", "")
            if not target.startswith("glossary:"):
                continue
            source_urn = getattr(edge, "source", "")
            source_node = drg.get_node(source_urn)
            source_type = self._classify_node_type(source_node, source_urn)
            entry = BacklinkEntry(
                source_id=source_urn,
                source_type=source_type,
                label=self._node_label(source_node, source_urn),
                artifact_path=self._node_artifact_path(source_node),
            )
            index.setdefault(target, []).append(entry)
        return index

    def _classify_node_type(self, node: Any | None, urn: str) -> str:
        """Map a DRG node to a BacklinkEntry source_type string."""
        if node is not None:
            urn = getattr(node, "urn", urn)
            kind = getattr(node, "kind", None)
            kind_val = getattr(kind, "value", str(kind) if kind else "")
            if kind_val in ("agent_profile", "action"):
                prefix_map = {
                    "agent_profile": "other",
                    "action": "mission_step",
                }
                return prefix_map.get(kind_val, "other")

        # Fall back to URN prefix matching
        prefix = urn.split(":")[0] if ":" in urn else ""
        mapping = {
            "wp": "wp",
            "adr": "adr",
            "step": "mission_step",
            "action": "mission_step",
            "retro": "retro_finding",
            "charter": "charter_section",
        }
        return mapping.get(prefix, "other")

    @staticmethod
    def _node_label(node: Any | None, urn: str) -> str:
        """Return a human-readable label for a DRG node."""
        if node is None:
            return urn
        label = getattr(node, "label", None)
        if label:
            return str(label)
        return str(getattr(node, "urn", urn))

    @staticmethod
    def _node_artifact_path(node: Any | None) -> str | None:
        """Return the artifact file path for a DRG node, if available."""
        if node is None:
            return None
        raw_path = getattr(node, "artifact_path", None) or getattr(node, "path", None)
        return str(raw_path) if raw_path else None

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def _render_page(self, rec: _TermRecord) -> str:
        """Render the full Markdown entity page for one term."""
        display_name = rec.label or rec.urn.split(":", 1)[-1]
        lines: list[str] = []

        # Header
        lines.append(f"# {display_name}")
        lines.append("")
        lines.append(f"**ID**: `{rec.urn}`")
        lines.append("")

        # Definition
        lines.append("## Definition")
        lines.append("")
        lines.append(rec.definition)
        lines.append("")

        # Provenance
        if rec.provenance:
            lines.append("## Provenance")
            lines.append("")
            lines.append(f"First introduced: {rec.provenance}")
            lines.append("")

        # Inbound references, grouped by source_type
        if rec.backlinks:
            lines.append("## References")
            lines.append("")
            groups: dict[str, list[BacklinkEntry]] = {}
            for bl in rec.backlinks:
                groups.setdefault(bl.source_type, []).append(bl)
            type_labels = {
                "wp": "Work Packages",
                "adr": "ADRs",
                "mission_step": "Mission Steps",
                "retro_finding": "Retrospective Findings",
                "charter_section": "Charter Sections",
                "other": "Other",
            }
            for stype, entries in groups.items():
                lines.append(f"### {type_labels.get(stype, stype)}")
                lines.append("")
                for e in entries:
                    if e.artifact_path:
                        lines.append(f"- [{e.label}]({e.artifact_path})")
                    else:
                        lines.append(f"- {e.label} (`{e.source_id}`)")
                lines.append("")

        # Conflict history
        conflict_events = self._load_conflict_history(rec.urn)
        if conflict_events:
            lines.append("## Conflict History")
            lines.append("")
            lines.append("| Timestamp | Severity | Type | Resolution |")
            lines.append("|-----------|----------|------|------------|")
            for ev in conflict_events:
                ts = ev.get("checked_at", "")
                sev = ev.get("severity", "")
                ctype = ev.get("conflict_type", "")
                res = ev.get("resolution", "unresolved")
                lines.append(f"| {ts} | {sev} | {ctype} | {res} |")
            lines.append("")

        lines.append("---")
        lines.append("*Regenerated automatically. Do not edit manually.*")

        return "\n".join(lines)

    def _load_conflict_history(self, term_urn: str) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for conflict in iter_semantic_conflicts(self._repo_root):
            if conflict.term_id != term_urn:
                continue
            result.append(
                {
                    "checked_at": conflict.timestamp or "",
                    "severity": conflict.severity,
                    "conflict_type": conflict.conflict_type,
                    "resolution": conflict.resolution or "unresolved",
                }
            )
        return result

    # ------------------------------------------------------------------
    # Atomic write
    # ------------------------------------------------------------------

    def _write_page(self, term_urn: str, content: str) -> Path:
        """Write page content atomically (tmp then rename)."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        slug = term_urn.replace(":", "-").replace("/", "-")
        final_path = self._output_dir / f"{slug}.md"
        tmp_path = final_path.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(final_path)
        return final_path
