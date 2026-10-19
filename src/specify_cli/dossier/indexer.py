"""Artifact indexing and missing detection for mission dossiers.

This module implements the Indexer class which recursively scans feature
directories, classifies artifacts into 6 classes, detects missing required
artifacts, and builds complete MissionDossier inventories.

Key concepts:
- Indexer.index_feature() performs recursive directory scan yielding artifacts
- Deterministic classification (6 classes: input, workflow, output, evidence, policy, runtime)
- Missing artifact detection comparing filesystem against manifest requirements
- Graceful error handling: permission errors, UTF-8 decode failures, deleted files
- MissionDossier builder: aggregates all artifacts (present + missing + unreadable)

See: kitty-specs/042-local-mission-dossier-authority-parity-export/tasks/WP03-indexing.md
"""

import fnmatch
import itertools
import logging
import re
import uuid
from pathlib import Path
from collections.abc import Iterator

from kernel.clock import now_utc
from charter.missions import ExpectedArtifactManifest, ExpectedArtifactSpec
from specify_cli.dossier.hasher import hash_file_with_validation, hash_wp_static_projection
from specify_cli.dossier.manifest import ManifestRegistry
from specify_cli.dossier.models import ArtifactRef, MissionDossier

logger = logging.getLogger(__name__)

# A WP artifact is a ``WP##``-prefixed markdown file (e.g. ``tasks/WP01-foo.md``).
# Its content hash is computed from the normalized WPMetadata static projection
# rather than raw bytes (FR-002, C-004) so runtime-mutable frontmatter churn
# (lane, agent, shell_pid, history, review_* …) does not move the dossier hash.
_WP_FILENAME_RE = re.compile(r"^WP\d{2,}", re.IGNORECASE)


def _is_wp_artifact(file_path: Path) -> bool:
    """True if *file_path* is a ``WP##`` markdown work-package file."""
    return file_path.suffix.lower() == ".md" and bool(_WP_FILENAME_RE.match(file_path.stem))


def _hash_wp_projection(file_path: Path) -> tuple[str | None, str | None]:
    """Hash a WP file's normalized static projection: ``(hash, error_reason)``.

    Two failure modes, deliberately treated differently (#2883 items 3/4):

    * **Present-but-schema-invalid frontmatter** (``ValidationError``): the
      frontmatter parsed to a mapping but failed the ``WPMetadata`` schema, so it
      carries runtime-mutable fields (lane / agent / history). Raw-byte hashing it
      would fold those into the recorded hash, so a routine lane transition would
      move the hash and manufacture a false DIVERGENCE (breaking AS-4). **Fail
      closed** — return ``(None, reason)`` so the caller marks it non-present.
    * **No parseable frontmatter** (``FrontmatterError`` / ``ValueError``: a stub
      ``WP##.md``, malformed YAML, or a non-mapping list/scalar doc): there is no
      runtime-field mapping to churn, so a raw-byte hash is stable — keep the
      artifact present via the raw-byte fallback. Crucially this no longer aborts
      the whole scan: a list/scalar doc now surfaces as ``FrontmatterError`` from
      ``read`` rather than a ``TypeError`` (#2883 item 4).
    """
    from pydantic import ValidationError

    from specify_cli.frontmatter import FrontmatterError
    from specify_cli.status import read_wp_frontmatter

    try:
        meta, _ = read_wp_frontmatter(file_path)
    except ValidationError as exc:
        logger.warning("WP %s frontmatter fails schema (%s); marking non-present (fail-closed)", file_path, exc)
        return None, f"wp frontmatter invalid: {exc}"
    except (FrontmatterError, ValueError) as exc:
        logger.debug("WP projection unavailable for %s (%s); using stable raw-byte hash", file_path, exc)
        return hash_file_with_validation(file_path)
    return hash_wp_static_projection(meta), None


def _manifest_specs(manifest: ExpectedArtifactManifest) -> Iterator[ExpectedArtifactSpec]:
    """Every spec of *manifest* in match-priority order.

    Required-always first, then each step's required specs in step order, then
    optional-always: the first matching spec wins in the classifiers below.
    """
    return itertools.chain(manifest.required_always, *manifest.required_by_step.values(), manifest.optional_always)


class Indexer:
    """Recursively indexes feature directory artifacts and builds MissionDossier.

    Scans feature directory, classifies artifacts using manifest definitions,
    detects missing required artifacts, and aggregates into complete MissionDossier.

    Attributes:
        manifest_registry: Registry for loading artifact manifests
        artifacts: List of indexed artifacts
        errors: List of errors encountered during scanning
    """

    def __init__(self, manifest_registry: ManifestRegistry, repo_root: Path | None = None):
        """Initialize Indexer with manifest registry.

        Args:
            manifest_registry: ManifestRegistry instance for loading manifests
            repo_root: Project root, threaded through every
                ``manifest_registry.load_manifest(mission_type, repo_root=...)``
                call so a configured org-pack ``expected-artifacts.yaml``
                override (#3525 Fold C) is honored by the dossier
                completeness index, not just the governance gate. Optional
                and defaults to ``None`` -- the pre-fold behavior (no org
                lookup, built-in manifest tree only) for every caller that
                does not supply it.
        """
        self.manifest_registry = manifest_registry
        self._repo_root = repo_root
        self.artifacts: list[ArtifactRef] = []
        self.errors: list[dict] = []

    def index_feature(self, feature_dir: Path, mission_type: str, step_id: str | None = None) -> MissionDossier:
        """Scan feature directory and build MissionDossier.

        Recursively scans feature_dir, indexes all artifacts, loads manifest,
        detects missing artifacts, and builds complete MissionDossier.

        Args:
            feature_dir: Path to feature directory
            mission_type: e.g., 'software-dev'
            step_id: Current mission step (e.g., 'plan'), for completeness check

        Returns:
            MissionDossier with all indexed artifacts (present + missing + unreadable)
        """
        self.artifacts = []
        self.errors = []

        # Recursively scan feature directory
        for file_path in self._scan_directory(feature_dir):
            artifact = self._index_file(file_path, feature_dir, mission_type)
            if artifact:
                self.artifacts.append(artifact)

        # Load manifest
        manifest = self.manifest_registry.load_manifest(mission_type, repo_root=self._repo_root)

        # Build MissionDossier
        dossier = MissionDossier(
            mission_type=mission_type,
            mission_run_id=str(uuid.uuid4()),
            mission_slug=self._extract_mission_slug(feature_dir),
            feature_dir=str(feature_dir),
            artifacts=self.artifacts,
            manifest=manifest.model_dump() if manifest else None,
        )

        # Detect missing artifacts
        missing = self._detect_missing_artifacts(dossier, step_id)
        dossier.artifacts.extend(missing)

        # Update timestamp
        dossier.dossier_updated_at = now_utc()

        return dossier

    def _scan_directory(self, directory: Path) -> Iterator[Path]:
        """Recursively yield all files in directory (skip hidden/git).

        Args:
            directory: Root directory to scan

        Yields:
            Path objects for each file found (non-hidden, non-.git/.kittify)
        """
        for item in directory.rglob("*"):
            # Skip hidden files/directories (names starting with .)
            if any(part.startswith(".") for part in item.relative_to(directory).parts):
                continue
            if item.is_file():
                yield item

    def _index_file(self, file_path: Path, feature_dir: Path, mission_type: str) -> ArtifactRef | None:
        """Index single file, return ArtifactRef or None if unindexable.

        Handles errors gracefully: permission errors, UTF-8 validation failures,
        file deletion during scan. Records error_reason for all issues.

        Args:
            file_path: Path to file to index
            feature_dir: Path to feature directory (for relative_path)
            mission_type: Mission type for manifest lookup

        Returns:
            ArtifactRef with all metadata, or None if unindexable
        """
        relative_path = str(file_path.relative_to(feature_dir))
        artifact_key = self._derive_artifact_key(file_path, mission_type)
        manifest = self.manifest_registry.load_manifest(mission_type, repo_root=self._repo_root)

        # Try to classify (with fallback for unreadable files)
        try:
            artifact_class = self._classify_artifact(file_path, manifest, feature_dir=feature_dir)
        except ValueError:
            # If classification fails, use a generic fallback
            artifact_class = "output"

        try:
            # Try to read and hash. WP artifacts hash their normalized static
            # projection (FR-002, C-004); everything else hashes raw bytes.
            if _is_wp_artifact(file_path):
                file_hash, error_reason = _hash_wp_projection(file_path)
            else:
                file_hash, error_reason = hash_file_with_validation(file_path)

            if error_reason:
                # UTF-8 validation failed or I/O error
                try:
                    size_bytes = file_path.stat().st_size
                except OSError:
                    size_bytes = 0

                logger.warning(f"Artifact unreadable {relative_path}: {error_reason}")
                return ArtifactRef(
                    artifact_key=artifact_key,
                    artifact_class=artifact_class,
                    relative_path=relative_path,
                    content_hash_sha256="",
                    size_bytes=size_bytes,
                    required_status=self._get_required_status(artifact_key, manifest),
                    is_present=False,
                    error_reason=error_reason,
                )

            # Successfully hashed
            return ArtifactRef(
                artifact_key=artifact_key,
                artifact_class=artifact_class,
                relative_path=relative_path,
                content_hash_sha256=file_hash,
                size_bytes=file_path.stat().st_size,
                required_status=self._get_required_status(artifact_key, manifest),
                is_present=True,
                error_reason=None,
            )

        except PermissionError as e:
            logger.error(f"Permission denied reading {relative_path}: {e}")
            return ArtifactRef(
                artifact_key=artifact_key,
                artifact_class=artifact_class,
                relative_path=relative_path,
                content_hash_sha256="",
                size_bytes=0,
                required_status=self._get_required_status(artifact_key, manifest),
                is_present=False,
                error_reason="unreadable",
            )
        except OSError as e:
            logger.error(f"I/O error reading {relative_path}: {e}")
            return ArtifactRef(
                artifact_key=artifact_key,
                artifact_class=artifact_class,
                relative_path=relative_path,
                content_hash_sha256="",
                size_bytes=0,
                required_status=self._get_required_status(artifact_key, manifest),
                is_present=False,
                error_reason="unreadable",
            )

    def _classify_artifact(  # noqa: C901
        self,
        file_path: Path,
        manifest: ExpectedArtifactManifest | None,
        feature_dir: Path | None = None,
    ) -> str:
        """Deterministically classify artifact into one of 6 classes.

        Classes: input, workflow, output, evidence, policy, runtime

        Strategy 1: Check manifest definitions (if manifest exists)
        Strategy 2: Filename-based patterns (fallback)
        Strategy 3: Fail explicitly if can't classify (no "other" or unknown)

        Args:
            file_path: Path to file to classify
            manifest: Optional manifest for classification hints
            feature_dir: Optional feature directory for relative path matching

        Returns:
            One of the 6 classes: input, workflow, output, evidence, policy, runtime

        Raises:
            ValueError: If artifact cannot be classified
        """
        # Strategy 1: Check manifest definitions (if manifest exists)
        if manifest:
            for specs in _manifest_specs(manifest):
                if self._matches_pattern(file_path, specs.path_pattern, feature_dir=feature_dir):
                    return specs.artifact_class.value

        # Strategy 2: Filename-based patterns (fallback)
        name = file_path.name.lower()

        # Input artifacts
        if name in ["spec.md", "specification.md"]:
            return "input"

        # Workflow artifacts (check before input, as "requirements" overlaps with policy)
        if name in ["plan.md"]:
            return "workflow"
        if name in ["tasks.md"] or (name.startswith("wp") and name.endswith(".md")):
            return "workflow"

        # Evidence artifacts (check before policy/input, as names may overlap)
        if name in ["research.md"]:
            return "evidence"
        if name == "analysis-report.md":
            return "evidence"
        if "test" in name or name.startswith("test_"):
            return "evidence"
        if "gap-analysis" in name:
            return "evidence"
        if "log" in name or name.endswith(".log"):
            return "evidence"

        # Policy artifacts
        if "requirements" in name or "constraints" in name:
            return "policy"
        if "architecture-decision" in name or "adr" in name:
            return "policy"

        # Output artifacts
        if "implementation" in name or "code" in name:
            return "output"
        if "findings" in name or "report" in name:
            return "output"

        # Runtime artifacts
        if "generated" in name or "cache" in name:
            return "runtime"

        # Strategy 3: Fail explicitly if can't classify
        raise ValueError(f"Cannot classify artifact: {file_path} (not in manifest, no pattern match)")

    def _matches_pattern(self, file_path: Path, pattern: str, feature_dir: Path | None = None) -> bool:
        """Check if file_path matches feature-relative glob pattern.

        Args:
            file_path: Path to file to check
            pattern: Glob pattern relative to feature directory
            feature_dir: Feature directory for relative path computation

        Returns:
            True if file_path matches pattern, False otherwise
        """
        relative = str(file_path.relative_to(feature_dir)) if feature_dir else file_path.name
        return fnmatch.fnmatch(relative, pattern)

    def _detect_missing_artifacts(self, dossier: MissionDossier, step_id: str | None = None) -> list[ArtifactRef]:
        """Detect required artifacts that are not present.

        Compares indexed artifacts against manifest requirements. Creates
        "ghost" ArtifactRef objects for each missing required artifact.

        Args:
            dossier: MissionDossier with indexed artifacts
            step_id: Optional step to filter required artifacts

        Returns:
            List of "ghost" ArtifactRef objects (is_present=False) for missing artifacts
        """
        if not dossier.manifest:
            return []  # No manifest, can't detect missing

        # Load manifest to access ExpectedArtifactSpec objects
        manifest = self.manifest_registry.load_manifest(dossier.mission_type, repo_root=self._repo_root)
        if not manifest:
            return []

        # Get required artifacts for current step
        required_specs = list(manifest.required_always)
        if step_id:
            required_specs.extend(manifest.required_by_step.get(step_id, []))

        # Check each required spec
        missing = []
        for spec in required_specs:
            # Check if any indexed artifact matches this spec
            matched = False
            for artifact in dossier.artifacts:
                if artifact.artifact_key == spec.artifact_key:
                    matched = True
                    break

            if not matched:
                # Create "ghost" artifact ref (missing)
                # Use manifest blocking field to determine if this is truly required
                required_status = "required" if spec.blocking else "optional"
                ghost = ArtifactRef(
                    artifact_key=spec.artifact_key,
                    artifact_class=spec.artifact_class.value,
                    relative_path=spec.path_pattern,
                    content_hash_sha256="",
                    size_bytes=0,
                    required_status=required_status,
                    is_present=False,
                    error_reason="not_found",
                    indexed_at=now_utc(),
                )
                missing.append(ghost)

        return missing

    def _derive_artifact_key(self, file_path: Path, mission_type: str) -> str:
        """Derive stable artifact key from file path and mission type.

        Deterministic: same file always produces same key.
        Format: {artifact_class}.{stem}[.{number}] for duplicates

        Args:
            file_path: Path to file
            mission_type: Mission type

        Returns:
            Stable artifact key (e.g., 'input.spec.main')
        """
        # Load manifest to check if file matches any known spec
        manifest = self.manifest_registry.load_manifest(mission_type, repo_root=self._repo_root)

        if manifest:
            for specs in _manifest_specs(manifest):
                if self._matches_pattern(file_path, specs.path_pattern):
                    return specs.artifact_key

        # Fallback: derive from filename
        name_lower = file_path.stem.lower()
        # Remove common prefixes/suffixes
        key = name_lower.replace("_", "-").replace(" ", "-")
        return f"artifact.{key}"

    def _get_required_status(self, artifact_key: str, manifest: ExpectedArtifactManifest | None) -> str:
        """Determine if artifact is required or optional.

        Args:
            artifact_key: Artifact key to check
            manifest: Optional manifest to check

        Returns:
            'required' or 'optional'
        """
        if not manifest:
            return "optional"

        # Check required_always
        for spec in manifest.required_always:
            if spec.artifact_key == artifact_key:
                return "required"

        # Check required_by_step
        for specs_list in manifest.required_by_step.values():
            for spec in specs_list:
                if spec.artifact_key == artifact_key:
                    return "required"

        # Default to optional
        return "optional"

    def _extract_mission_slug(self, feature_dir: Path) -> str:
        """Extract feature slug from feature directory path.

        Assumes directory name follows pattern: {number}-{name} (e.g., 042-dossier)

        Args:
            feature_dir: Path to feature directory

        Returns:
            Feature slug extracted from directory name
        """
        return feature_dir.name
