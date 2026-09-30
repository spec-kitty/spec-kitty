"""Gap analysis for documentation missions.

This module provides functionality to audit existing documentation, classify
docs into Divio types, build coverage matrices, and identify gaps.

The multi-strategy approach:
1. Detect documentation framework from file structure
2. Parse frontmatter for explicit type classification
3. Apply content heuristics if no explicit type
4. Build coverage matrix showing what exists vs what's needed
5. Prioritize gaps by user impact
"""

from __future__ import annotations

from dataclasses import dataclass, field
from kernel.clock import datetime, now_utc
from enum import Enum
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

#: Canonical concern subdirectories under ``docs/development/``, established by the
#: ``common-docs-convergence`` mission (WP10) when the flat contributor tree was
#: subdivided by concern. Pinned here so documentation gap analysis surfaces each
#: contributor-doc concern as a distinct project area rather than lumping every
#: development page under a single ``development`` bucket. Kept in lock-step with
#: the on-disk structure by
#: ``tests/agent/test_gap_analysis.py::test_development_concern_subdirs_pinned``
#: (FR-018 subdir-name pin) — renaming or adding a ``docs/development/`` concern
#: directory without updating this tuple turns that guard red.
DEVELOPMENT_CONCERN_SUBDIRS: tuple[str, ...] = (
    "getting-started",
    "how-to",
    "reference",
    "reporting",
    "testing",
)

#: The top-level docs directory whose concern subdirectories are pinned above.
_DEVELOPMENT_SECTION = "development"


class DocFramework(Enum):
    """Supported documentation frameworks."""

    SPHINX = "sphinx"
    MKDOCS = "mkdocs"
    DOCUSAURUS = "docusaurus"
    JEKYLL = "jekyll"
    HUGO = "hugo"
    PLAIN_MARKDOWN = "plain-markdown"
    UNKNOWN = "unknown"


def detect_doc_framework(docs_dir: Path) -> DocFramework:
    """Detect documentation framework from file structure.

    Args:
        docs_dir: Directory containing documentation

    Returns:
        Detected framework or UNKNOWN if cannot determine
    """
    # Sphinx: conf.py is definitive indicator
    if (docs_dir / "conf.py").exists():
        return DocFramework.SPHINX

    # MkDocs: mkdocs.yml is definitive
    if (docs_dir / "mkdocs.yml").exists():
        return DocFramework.MKDOCS

    # Docusaurus: docusaurus.config.js
    if (docs_dir / "docusaurus.config.js").exists():
        return DocFramework.DOCUSAURUS

    # Jekyll: _config.yml
    if (docs_dir / "_config.yml").exists():
        return DocFramework.JEKYLL

    # Hugo: config.toml or config.yaml
    if (docs_dir / "config.toml").exists() or (docs_dir / "config.yaml").exists():
        return DocFramework.HUGO

    # Check for markdown files without framework
    if list(docs_dir.rglob("*.md")):
        return DocFramework.PLAIN_MARKDOWN

    return DocFramework.UNKNOWN


class DivioType(Enum):
    """Divio documentation types."""

    TUTORIAL = "tutorial"
    HOWTO = "how-to"
    REFERENCE = "reference"
    EXPLANATION = "explanation"
    UNCLASSIFIED = "unclassified"


def parse_frontmatter(content: str) -> dict[str, Any] | None:
    """Parse YAML frontmatter from markdown file.

    Args:
        content: File content

    Returns:
        Frontmatter dict if present, None otherwise
    """
    if not content.startswith("---"):
        return None

    # Find closing ---
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    # Parse YAML frontmatter
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        frontmatter_text = "\n".join(lines[1:end_idx])
        parsed = yaml.load(frontmatter_text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def classify_by_content_heuristics(content: str) -> DivioType:
    """Classify document by analyzing content patterns.

    Args:
        content: Document content (without frontmatter)

    Returns:
        Best-guess Divio type based on content analysis
    """
    content_lower = content.lower()

    # Tutorial markers
    tutorial_markers = [
        "step 1",
        "step 2",
        "first,",
        "next,",
        "now,",
        "you should see",
        "let's",
        "you'll learn",
        "by the end",
        "what you'll build",
    ]
    tutorial_score = sum(1 for marker in tutorial_markers if marker in content_lower)

    # How-to markers
    howto_markers = [
        "how to",
        "to do",
        "follow these steps",
        "problem:",
        "solution:",
        "before you begin",
        "prerequisites:",
        "verification:",
    ]
    howto_score = sum(1 for marker in howto_markers if marker in content_lower)

    # Reference markers
    reference_markers = [
        "parameters:",
        "returns:",
        "arguments:",
        "options:",
        "methods:",
        "properties:",
        "attributes:",
        "class:",
        "function:",
        "api",
    ]
    reference_score = sum(1 for marker in reference_markers if marker in content_lower)

    # Explanation markers
    explanation_markers = [
        "why",
        "background",
        "concepts",
        "architecture",
        "design decision",
        "alternatives",
        "trade-offs",
        "how it works",
        "understanding",
    ]
    explanation_score = sum(1 for marker in explanation_markers if marker in content_lower)

    # Determine type by highest score
    scores = {
        DivioType.TUTORIAL: tutorial_score,
        DivioType.HOWTO: howto_score,
        DivioType.REFERENCE: reference_score,
        DivioType.EXPLANATION: explanation_score,
    }

    max_score = max(scores.values())
    if max_score == 0:
        return DivioType.UNCLASSIFIED

    # Return type with highest score
    for divio_type, score in scores.items():
        if score == max_score:
            return divio_type

    return DivioType.UNCLASSIFIED


def classify_divio_type(content: str) -> tuple[DivioType, float]:
    """Classify document into Divio type.

    Uses multi-strategy approach:
    1. Check frontmatter for explicit 'type' field (confidence: 1.0)
    2. Apply content heuristics (confidence: 0.7)

    Args:
        content: Full document content including frontmatter

    Returns:
        Tuple of (DivioType, confidence_score)
    """
    # Strategy 1: Frontmatter (explicit classification)
    frontmatter = parse_frontmatter(content)
    if frontmatter and "type" in frontmatter:
        type_str = frontmatter["type"].lower()
        type_map = {
            "tutorial": DivioType.TUTORIAL,
            "how-to": DivioType.HOWTO,
            "howto": DivioType.HOWTO,
            "reference": DivioType.REFERENCE,
            "explanation": DivioType.EXPLANATION,
        }
        if type_str in type_map:
            return (type_map[type_str], 1.0)  # High confidence

    # Strategy 2: Content heuristics
    divio_type = classify_by_content_heuristics(content)
    confidence = 0.7 if divio_type != DivioType.UNCLASSIFIED else 0.0

    return (divio_type, confidence)


@dataclass
class CoverageMatrix:
    """Documentation coverage matrix showing Divio type coverage by project area.

    The matrix shows which project areas (features, modules, components) have
    documentation for each Divio type (tutorial, how-to, reference, explanation).
    """

    project_areas: list[str] = field(default_factory=list)  # e.g., ["auth", "api", "cli"]
    divio_types: list[str] = field(default_factory=lambda: ["tutorial", "how-to", "reference", "explanation"])

    # Maps (area, type) to doc file path (None if missing)
    cells: dict[tuple[str, str], Path | None] = field(default_factory=dict)

    def get_gaps(self) -> list[tuple[str, str]]:
        """Return list of (area, type) tuples with missing documentation.

        Returns:
            List of (area, divio_type) tuples where documentation is missing
        """
        gaps = []
        for area in self.project_areas:
            for dtype in self.divio_types:
                if self.cells.get((area, dtype)) is None:
                    gaps.append((area, dtype))
        return gaps

    def get_coverage_percentage(self) -> float:
        """Calculate percentage of cells with documentation.

        Returns:
            Coverage percentage (0.0 to 1.0)
        """
        total_cells = len(self.project_areas) * len(self.divio_types)
        if total_cells == 0:
            return 0.0

        filled_cells = sum(1 for path in self.cells.values() if path is not None)

        return filled_cells / total_cells

    def to_markdown_table(self) -> str:
        """Generate Markdown table representation of coverage.

        Returns:
            Markdown table showing coverage matrix
        """
        if not self.project_areas:
            return "No project areas identified."

        # Build table header
        header = "| Area | " + " | ".join(self.divio_types) + " |"
        separator = "|" + "|".join(["---"] * (len(self.divio_types) + 1)) + "|"

        # Build table rows
        rows = []
        for area in self.project_areas:
            cells = []
            for dtype in self.divio_types:
                doc_path = self.cells.get((area, dtype))
                if doc_path:
                    cells.append("✓")
                else:
                    cells.append("✗")
            row = f"| {area} | " + " | ".join(cells) + " |"
            rows.append(row)

        # Combine
        table_lines = [header, separator] + rows

        # Add coverage percentage
        coverage_pct = self.get_coverage_percentage() * 100
        summary = f"\n**Coverage**: {len([c for c in self.cells.values() if c])}/{len(self.cells)} cells = {coverage_pct:.1f}%"  # noqa: E501

        return "\n".join(table_lines) + summary


class GapPriority(Enum):
    """Priority levels for documentation gaps."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DocumentationGap:
    """Represents a missing piece of documentation.

    Attributes:
        area: Project area missing documentation
        divio_type: Which Divio type is missing
        priority: How important this gap is (high/medium/low)
        reason: Why this gap matters
    """

    area: str
    divio_type: str
    priority: GapPriority
    reason: str

    def __repr__(self) -> str:
        return f"[{self.priority.value.upper()}] {self.area} → {self.divio_type}: {self.reason}"


def prioritize_gaps(
    gaps: list[tuple[str, str]],
    project_areas: list[str],
    existing_docs: dict[Path, DivioType],  # noqa: ARG001
) -> list[DocumentationGap]:
    """Assign priorities to documentation gaps based on user impact.

    Prioritization rules (from research):
    - HIGH: Missing tutorials (blocks new users)
    - HIGH: Missing reference for core features (users can't find APIs)
    - MEDIUM: Missing how-tos for common tasks (users struggle with problems)
    - MEDIUM: Missing tutorials for advanced features
    - LOW: Missing explanations (nice-to-have, not blocking)

    Args:
        gaps: List of (area, divio_type) tuples with missing docs
        project_areas: All project areas
        existing_docs: Map of doc paths to classified types (for context)

    Returns:
        List of DocumentationGap objects with priorities assigned
    """
    prioritized = []

    for area, divio_type in gaps:
        # Determine if this is a core area (heuristic: alphabetically first areas are core)
        is_core_area = project_areas.index(area) < len(project_areas) // 2

        # Prioritization logic
        if divio_type == "tutorial":
            if is_core_area:
                priority = GapPriority.HIGH
                reason = "New users need tutorials to get started with core functionality"
            else:
                priority = GapPriority.MEDIUM
                reason = "Users need tutorials for advanced features"

        elif divio_type == "reference":
            if is_core_area:
                priority = GapPriority.HIGH
                reason = "Users need API reference to use core features"
            else:
                priority = GapPriority.MEDIUM
                reason = "API reference helps users discover all capabilities"

        elif divio_type == "how-to":
            priority = GapPriority.MEDIUM
            reason = "Users need how-tos to solve common problems and tasks"

        elif divio_type == "explanation":
            priority = GapPriority.LOW
            reason = "Explanations aid understanding but are not blocking"

        else:
            priority = GapPriority.LOW
            reason = "Unknown Divio type"

        prioritized.append(DocumentationGap(area=area, divio_type=divio_type, priority=priority, reason=reason))

    # Sort by priority (high first)
    priority_order = {GapPriority.HIGH: 0, GapPriority.MEDIUM: 1, GapPriority.LOW: 2}
    prioritized.sort(key=lambda gap: priority_order[gap.priority])

    return prioritized


@dataclass
class GapAnalysis:
    """Complete gap analysis results.

    Attributes:
        project_name: Project being analyzed
        analysis_date: When analysis was performed
        framework: Detected documentation framework
        coverage_matrix: Coverage matrix showing existing docs
        gaps: Prioritized list of documentation gaps
        outdated: List of outdated documentation files
        existing: Map of existing doc files to their classified types
    """

    project_name: str
    analysis_date: datetime
    framework: DocFramework
    coverage_matrix: CoverageMatrix
    gaps: list[DocumentationGap]
    outdated: list[tuple[Path, str]] = field(default_factory=list)  # (file, reason)
    existing: dict[Path, tuple[DivioType, float]] = field(default_factory=dict)  # (type, confidence)

    def to_markdown(self) -> str:  # noqa: C901
        """Generate Markdown report of gap analysis.

        Returns:
            Full gap analysis report as Markdown
        """
        lines = [
            f"# Gap Analysis: {self.project_name}",
            "",
            f"**Analysis Date**: {self.analysis_date.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Documentation Framework**: {self.framework.value}",
            f"**Coverage**: {self.coverage_matrix.get_coverage_percentage() * 100:.1f}%",
            "",
            "## Coverage Matrix",
            "",
            self.coverage_matrix.to_markdown_table(),
            "",
            "## Identified Gaps",
            "",
        ]

        if not self.gaps:
            lines.append("No gaps identified - documentation coverage is complete!")
        else:
            lines.append(f"Found {len(self.gaps)} documentation gaps:")
            lines.append("")

            # Group by priority
            high_gaps = [g for g in self.gaps if g.priority == GapPriority.HIGH]
            medium_gaps = [g for g in self.gaps if g.priority == GapPriority.MEDIUM]
            low_gaps = [g for g in self.gaps if g.priority == GapPriority.LOW]

            if high_gaps:
                lines.append("### High Priority")
                lines.append("")
                for gap in high_gaps:
                    lines.append(f"- **{gap.area} → {gap.divio_type}**: {gap.reason}")
                lines.append("")

            if medium_gaps:
                lines.append("### Medium Priority")
                lines.append("")
                for gap in medium_gaps:
                    lines.append(f"- **{gap.area} → {gap.divio_type}**: {gap.reason}")
                lines.append("")

            if low_gaps:
                lines.append("### Low Priority")
                lines.append("")
                for gap in low_gaps:
                    lines.append(f"- **{gap.area} → {gap.divio_type}**: {gap.reason}")
                lines.append("")

        # Existing documentation inventory
        lines.extend(
            [
                "## Existing Documentation",
                "",
            ]
        )

        if not self.existing:
            lines.append("No existing documentation found.")
        else:
            lines.append(f"Found {len(self.existing)} documentation files:")
            lines.append("")

            # Group by Divio type
            by_type: dict[DivioType, list[tuple[Path, float]]] = {}
            for path, (dtype, confidence) in self.existing.items():
                if dtype not in by_type:
                    by_type[dtype] = []
                by_type[dtype].append((path, confidence))

            for dtype in DivioType:
                if dtype in by_type and dtype != DivioType.UNCLASSIFIED:
                    lines.append(f"### {dtype.value.title()}")
                    lines.append("")
                    for path, confidence in by_type[dtype]:
                        conf_str = f"({confidence * 100:.0f}% confidence)" if confidence < 1.0 else ""
                        lines.append(f"- {path} {conf_str}")
                    lines.append("")

            # Unclassified docs
            if DivioType.UNCLASSIFIED in by_type:
                lines.append("### Unclassified")
                lines.append("")
                for path, _ in by_type[DivioType.UNCLASSIFIED]:
                    lines.append(f"- {path}")
                lines.append("")

        # Outdated documentation
        if self.outdated:
            lines.extend(
                [
                    "## Outdated Documentation",
                    "",
                    f"Found {len(self.outdated)} outdated documentation files:",
                    "",
                ]
            )
            for path, reason in self.outdated:
                lines.append(f"- **{path}**: {reason}")
            lines.append("")

        # Recommendations
        lines.extend(
            [
                "## Recommendations",
                "",
            ]
        )

        if high_gaps:
            lines.append("**Immediate action needed**:")
            for gap in high_gaps[:3]:  # Top 3 high-priority gaps
                lines.append(f"1. Create {gap.divio_type} for {gap.area} - {gap.reason}")
            lines.append("")

        if medium_gaps:
            lines.append("**Should address soon**:")
            for gap in medium_gaps[:3]:  # Top 3 medium-priority gaps
                lines.append(f"- Add {gap.divio_type} for {gap.area}")
            lines.append("")

        if low_gaps:
            lines.append(f"**Nice to have**: {len(low_gaps)} low-priority gaps (see above)")
            lines.append("")

        return "\n".join(lines)


def detect_project_areas(docs_dir: Path, project_root: Path) -> list[str]:
    """Detect project areas from directory structure.

    Heuristics:
    - Check docs/ subdirectories (e.g., docs/guides/auth/ → "auth" area)
    - Check source code directories (e.g., src/api/ → "api" area)
    - Fallback: Single area named after project

    Args:
        docs_dir: Documentation directory
        project_root: Project root directory

    Returns:
        List of project area names
    """
    areas = set()

    # Check docs subdirectories
    for item in docs_dir.iterdir():
        if item.is_dir() and item.name not in ["_build", "_static", "_templates"]:
            areas.add(item.name)

    # Surface the pinned docs/development/ concern subdirectories as distinct
    # areas so contributor docs classify by concern (getting-started / how-to /
    # reference / testing) instead of collapsing under one "development" bucket.
    dev_dir = docs_dir / _DEVELOPMENT_SECTION
    if dev_dir.is_dir():
        for concern in DEVELOPMENT_CONCERN_SUBDIRS:
            if (dev_dir / concern).is_dir():
                areas.add(f"{_DEVELOPMENT_SECTION}/{concern}")

    # Check source code directories
    src_dir = project_root / "src"
    if src_dir.exists():
        for item in src_dir.iterdir():
            if item.is_dir():
                areas.add(item.name)

    # Fallback: project name as single area
    if not areas:
        areas.add(project_root.name)

    return sorted(areas)


def infer_area_from_path(doc_path: Path, project_areas: list[str]) -> str | None:
    """Infer which project area a doc file belongs to.

    Args:
        doc_path: Path to documentation file
        project_areas: Known project areas

    Returns:
        Area name if match found, None otherwise
    """
    # Match the most specific (longest) area name that appears in the path, so a
    # page under docs/development/how-to/ classifies to "development/how-to"
    # rather than the shorter "development" bucket it also matches.
    path_str = str(doc_path).lower()
    matches = [area for area in project_areas if area.lower() in path_str]
    if matches:
        return max(matches, key=len)

    # Fallback: use first area (generic)
    return project_areas[0] if project_areas else None


def build_coverage_matrix(classified: dict[Path, tuple[DivioType, float]], project_areas: list[str]) -> CoverageMatrix:
    """Build coverage matrix from classified documents.

    Args:
        classified: Map of doc paths to (DivioType, confidence)
        project_areas: List of project area names

    Returns:
        CoverageMatrix showing coverage by area and type
    """
    matrix = CoverageMatrix(project_areas=project_areas)

    # Map each classified doc to (area, type) cell
    for doc_path, (divio_type, _) in classified.items():
        if divio_type == DivioType.UNCLASSIFIED:
            continue

        # Infer area from path (heuristic: directory name or filename prefix)
        area = infer_area_from_path(doc_path, project_areas)
        if area:
            matrix.cells[(area, divio_type.value)] = doc_path

    return matrix


def analyze_documentation_gaps(docs_dir: Path, project_root: Path | None = None) -> GapAnalysis:
    """Analyze documentation directory and identify gaps.

    Args:
        docs_dir: Directory containing documentation
        project_root: Project root (for code analysis), defaults to docs_dir.parent

    Returns:
        GapAnalysis object with coverage matrix, gaps, and recommendations
    """
    if project_root is None:
        project_root = docs_dir.parent

    project_name = project_root.name

    # Detect framework
    framework = detect_doc_framework(docs_dir)

    # Discover all markdown files
    doc_files = list(docs_dir.rglob("*.md"))

    # Classify each file
    classified = {}
    for doc_file in doc_files:
        try:
            content = doc_file.read_text(encoding="utf-8")
            divio_type, confidence = classify_divio_type(content)
            classified[doc_file] = (divio_type, confidence)
        except Exception:
            # Skip files that can't be read/classified
            classified[doc_file] = (DivioType.UNCLASSIFIED, 0.0)

    # Detect project areas from directory structure or code
    project_areas = detect_project_areas(docs_dir, project_root)

    # Build coverage matrix
    coverage_matrix = build_coverage_matrix(classified, project_areas)

    # Identify gaps
    gap_tuples = coverage_matrix.get_gaps()

    # Prioritize gaps
    classified_by_type = {
        path: divio_type for path, (divio_type, _confidence) in classified.items()
    }
    prioritized_gaps = prioritize_gaps(gap_tuples, project_areas, classified_by_type)

    # Detect version mismatches (Python only for now)
    outdated: list[Any] = []
    # TODO: Implement version mismatch detection (T038)

    return GapAnalysis(
        project_name=project_name,
        analysis_date=now_utc(),
        framework=framework,
        coverage_matrix=coverage_matrix,
        gaps=prioritized_gaps,
        outdated=outdated,
        existing=classified,
    )


def generate_gap_analysis_report(docs_dir: Path, output_file: Path, project_root: Path | None = None) -> GapAnalysis:
    """Analyze documentation and generate gap analysis report.

    This is the main entry point for gap analysis. It:
    1. Detects documentation framework
    2. Classifies existing docs into Divio types
    3. Builds coverage matrix
    4. Identifies gaps
    5. Prioritizes gaps by impact
    6. Detects outdated documentation
    7. Generates comprehensive report

    Args:
        docs_dir: Directory containing documentation to analyze
        output_file: Path where gap-analysis.md should be written
        project_root: Project root directory (for code analysis)

    Returns:
        GapAnalysis object with full results

    Raises:
        FileNotFoundError: If docs_dir doesn't exist
    """
    if not docs_dir.exists():
        raise FileNotFoundError(f"Documentation directory not found: {docs_dir}")

    # Run analysis
    analysis = analyze_documentation_gaps(docs_dir, project_root)

    # Generate report
    report_content = analysis.to_markdown()

    # Write to file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(report_content, encoding="utf-8")

    return analysis
