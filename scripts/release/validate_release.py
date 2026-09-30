#!/usr/bin/env python3
"""Release readiness validator for Spec Kitty automation.

The script validates three core conditions before allowing a release or
testing cut:

1. The version declared in pyproject.toml is well-formed.
2. CHANGELOG.md contains a populated section for the target version.
3. Version progression is monotonic relative to existing git tags and, in tag
   mode, matches the release tag that triggered the workflow.

Both validation modes accept stable versions (``X.Y.Z`` or ``X.Y.Z.N``) and
prerelease versions such as ``3.2.7rc1`` or ``3.2.6.1rc1``. Tagged prereleases
publish through the same release workflow, but GitHub marks them as prereleases
and installers must opt into them explicitly.

It is intentionally dependency-light so it can run both locally and in CI
without additional bootstrapping beyond Python 3.11.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Sequence

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore


RELEASE_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:\.(?P<hotfix>\d+))?"
    r"(?:(?P<stage>a|b|rc|alpha|beta)(?P<stage_num>\d*))?$",
    re.IGNORECASE,
)
_CHANGELOG_VERSION_SUB = r"\d+\.\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+|(?:alpha|beta)\d*)?"
# A changelog heading may carry a version, an ``Unreleased`` marker, or both, in
# any of these shapes (with or without the surrounding ``[ ]``):
#   ## [3.2.3]                  -> finalized section for 3.2.3
#   ## [3.2.3] - 2026-06-24     -> finalized section with a date suffix
#   ## [Unreleased] - 3.2.3     -> pending pre-release section declaring 3.2.3
#   ## [3.2.3] - Unreleased     -> pending pre-release section declaring 3.2.3
#   ## 3.2.3 - Unreleased       -> pending pre-release section declaring 3.2.3
#   ## Unreleased - 3.2.3       -> pending pre-release section declaring 3.2.3
#   ## [Unreleased - 3.2.3]     -> pending pre-release section declaring 3.2.3
#   ## [Unreleased]             -> version-less placeholder (no declared version)
# The ``unreleased*`` capture groups let callers distinguish a *pending* section
# (rejected on actual tag/publish runs) from a *finalized* one.
CHANGELOG_HEADING_RE = re.compile(
    r"^##\s*"
    r"(?:\[\s*)?"
    r"(?:"
    r"(?P<unreleased_a>Unreleased)\s*\]?\s*(?:-\s*)?(?P<version_a>" + _CHANGELOG_VERSION_SUB + r")"
    r"|"
    r"(?P<version_b>" + _CHANGELOG_VERSION_SUB + r")\s*\]?\s*(?:-\s*(?P<unreleased_b>Unreleased))?"
    r"|"
    r"(?P<unreleased_c>Unreleased)\s*\]?"
    r")"
    r"\s*\]?"
    r"(?:\s*-.*)?$",
    re.IGNORECASE,
)


@dataclass
class ChangelogHeading:
    """A parsed CHANGELOG ``## ...`` heading.

    ``version`` is ``None`` for a version-less ``## [Unreleased]`` placeholder.
    ``unreleased`` is ``True`` when the heading carries an ``Unreleased`` marker,
    i.e. the section is *pending* and not yet finalized for a publish run.
    """

    version: str | None
    unreleased: bool


def parse_changelog_heading(line: str) -> ChangelogHeading | None:
    """Parse a single changelog line into a :class:`ChangelogHeading`.

    Returns ``None`` when *line* is not a recognised release heading.
    """
    match = CHANGELOG_HEADING_RE.match(line)
    if not match:
        return None
    version = match.group("version_a") or match.group("version_b")
    unreleased = bool(match.group("unreleased_a") or match.group("unreleased_b") or match.group("unreleased_c"))
    return ChangelogHeading(version=version, unreleased=unreleased)


@dataclass(frozen=True)
class UnreleasedSection:
    """The body of a changelog's ``## [Unreleased]`` section.

    ``start_line`` is the 1-based line of the heading in the source text. ``lines`` are the
    body lines, excluding the heading and the release heading that terminates the section.
    """

    start_line: int
    lines: tuple[str, ...]


_FENCE_MARKERS: tuple[str, ...] = ("```", "~~~")


def _fence_marker(line: str) -> str | None:
    """Return the fence marker (triple backtick or triple tilde) *line* opens or closes, else None."""
    stripped = line.lstrip()
    return next((marker for marker in _FENCE_MARKERS if stripped.startswith(marker)), None)


def unreleased_section(text: str) -> UnreleasedSection | None:
    """Locate the ``## [Unreleased]`` section of a changelog.

    Built on :func:`parse_changelog_heading`, so it accepts every heading shape the release
    validator accepts (including ``##[Unreleased]`` without a space). A release-looking heading
    inside a fenced block never ends the section; a fence closes only with the marker that opened it.
    Returns ``None`` when the changelog has no Unreleased heading.
    """
    start_line: int | None = None
    body: list[str] = []
    open_fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = _fence_marker(line)
        if marker is not None and open_fence in (None, marker):
            open_fence = None if open_fence else marker
        elif open_fence is None and line.startswith("##"):
            heading = parse_changelog_heading(line)
            if heading is not None and start_line is None and heading.unreleased:
                start_line = number
                continue
            if heading is not None and start_line is not None:
                break
        if start_line is not None:
            body.append(line)
    if start_line is None:
        return None
    return UnreleasedSection(start_line=start_line, lines=tuple(body))


@dataclass
class ValidationIssue:
    message: str
    hint: str | None = None

    def format(self) -> str:
        if self.hint:
            return f"{self.message} (Hint: {self.hint})"
        return self.message


@dataclass
class ValidationResult:
    ok: bool
    mode: str
    pyproject_path: Path
    changelog_path: Path
    lockfile_path: Path
    version: str
    tag: str | None
    issues: list[ValidationIssue] = field(default_factory=list)

    def report(self) -> None:
        header = "Release Validator Summary"
        print(header)
        print("-" * len(header))
        print(f"Mode: {self.mode}")
        print(f"pyproject.toml: {self.pyproject_path}")
        print(f"CHANGELOG.md: {self.changelog_path}")
        print(f"uv.lock: {self.lockfile_path}")
        print(f"Version: {self.version or 'N/A'}")
        print(f"Tag: {self.tag or 'N/A'}")
        if not self.ok:
            print("\nIssues detected:")
            for idx, issue in enumerate(self.issues, start=1):
                print(f"  {idx}. {issue.format()}")
        else:
            print("\nAll required checks passed.")


class ReleaseValidatorError(Exception):
    """Base exception for validator failures."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate release readiness for Spec Kitty release automation")
    parser.add_argument(
        "--mode",
        choices=("branch", "tag"),
        default="branch",
        help="Validation mode. 'branch' expects a version bump without a tag. "
        "'tag' enforces tag-version parity and monotonic progression for stable "
        "or prerelease publish tags.",
    )
    parser.add_argument(
        "--tag",
        help="Explicit tag (e.g., v1.2.3 or v1.3.0a0). Defaults to the detected GITHUB_REF or GITHUB_REF_NAME in tag mode.",
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: %(default)s)",
    )
    parser.add_argument(
        "--changelog",
        default=None,
        help="Path to changelog file (default: CHANGELOG.md under the target repository root)",
    )
    parser.add_argument(
        "--lockfile",
        default=None,
        help="Path to uv.lock (default: uv.lock under the target repository root)",
    )
    parser.add_argument(
        "--consistency-only",
        action="store_true",
        help=("In branch mode, validate release-version source consistency without requiring the project version to advance beyond the latest tag."),
    )
    parser.add_argument(
        "--tag-pattern",
        default="v*.*.*",
        help="Git tag glob pattern used for version progression checks (default: %(default)s).",
    )
    parser.add_argument(
        "--fail-on-missing-tag",
        action="store_true",
        help="Treat missing tag detection as a hard failure (defaults to failure in tag mode).",
    )
    args = parser.parse_args(argv)
    if args.mode == "tag" and args.consistency_only:
        parser.error("--consistency-only can only be used with --mode branch")
    return args


def _normalize_stage(stage: str | None) -> str | None:
    if stage is None:
        return None
    lowered = stage.lower()
    if lowered == "alpha":
        return "a"
    if lowered == "beta":
        return "b"
    return lowered


def is_prerelease_version(value: str) -> bool:
    match = RELEASE_VERSION_RE.match(value)
    return bool(match and _normalize_stage(match.group("stage")) is not None)


def load_pyproject_version(path: Path) -> str:
    if not path.exists():
        raise ReleaseValidatorError(f"pyproject.toml not found at {path} – ensure you run from repository root.")
    with path.open("rb") as fp:
        data = tomllib.load(fp)
    try:
        version = data["project"]["version"]
    except KeyError as exc:  # pragma: no cover - defensive; unlikely if file well-formed
        raise ReleaseValidatorError("Unable to locate [project].version in pyproject.toml.") from exc
    if not isinstance(version, str):
        raise ReleaseValidatorError("pyproject version must be a string.")
    if not RELEASE_VERSION_RE.match(version):
        raise ReleaseValidatorError(
            f"Version '{version}' is not a supported release version (expected X.Y.Z or X.Y.Z.N, optionally followed by a/b/rc/alpha/beta and a number)."
        )
    return version


def load_metadata_yaml_version(repo_root: Path) -> str:
    """Load spec_kitty.version from .kittify/metadata.yaml."""
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - pyyaml required
        raise ReleaseValidatorError("PyYAML is required to load .kittify/metadata.yaml. Run: pip install pyyaml") from exc
    metadata_path = repo_root / ".kittify" / "metadata.yaml"
    if not metadata_path.exists():
        raise ReleaseValidatorError(f".kittify/metadata.yaml not found at {metadata_path}")
    data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    version = data.get("spec_kitty", {}).get("version")
    if not version:
        raise ReleaseValidatorError(".kittify/metadata.yaml missing spec_kitty.version")
    return str(version)


def validate_metadata_yaml_version_sync(
    pyproject_version: str,
    repo_root: Path,
) -> ValidationIssue | None:
    """Assert .kittify/metadata.yaml version matches pyproject.toml. See FR-601, FR-602.

    Returns a ValidationIssue if there is a mismatch, otherwise None.
    """
    try:
        metadata_version = load_metadata_yaml_version(repo_root)
    except ReleaseValidatorError as exc:
        return ValidationIssue(message=str(exc))
    if pyproject_version != metadata_version:
        return ValidationIssue(
            message=(f"Version mismatch detected: pyproject.toml={pyproject_version!r} vs .kittify/metadata.yaml={metadata_version!r}"),
            hint=(f"Update .kittify/metadata.yaml spec_kitty.version to {pyproject_version!r} so both files agree before cutting the release."),
        )
    return None


def load_uv_lock_project_version(
    path: Path,
    package_name: str = "spec-kitty-cli",
) -> str:
    """Load the root package version recorded in uv.lock."""
    if not path.exists():
        raise ReleaseValidatorError(f"uv.lock not found at {path}")
    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ReleaseValidatorError(f"Unable to parse uv.lock at {path}: {exc}") from exc

    packages = data.get("package")
    if not isinstance(packages, list):
        raise ReleaseValidatorError("uv.lock does not contain a package list.")

    for package in packages:
        if not isinstance(package, dict) or package.get("name") != package_name:
            continue
        version = package.get("version")
        if not isinstance(version, str):
            raise ReleaseValidatorError(f"uv.lock package {package_name!r} is missing a string version.")
        if not RELEASE_VERSION_RE.match(version):
            raise ReleaseValidatorError(f"uv.lock package {package_name!r} version {version!r} is not a supported release version.")
        return version

    raise ReleaseValidatorError(f"uv.lock does not contain package {package_name!r}.")


def validate_uv_lock_version_sync(
    pyproject_version: str,
    lockfile_path: Path,
) -> ValidationIssue | None:
    """Assert uv.lock's root package version matches pyproject.toml."""
    try:
        lockfile_version = load_uv_lock_project_version(lockfile_path)
    except ReleaseValidatorError as exc:
        return ValidationIssue(message=str(exc))

    if canonical_release_version(pyproject_version) != canonical_release_version(lockfile_version):
        return ValidationIssue(
            message=(f"Version mismatch detected: pyproject.toml={pyproject_version!r} vs uv.lock spec-kitty-cli={lockfile_version!r}"),
            hint=(f"Run `uv lock` after updating pyproject.toml so uv.lock records spec-kitty-cli {pyproject_version!r}."),
        )
    return None


def read_changelog(path: Path) -> str:
    if not path.exists():
        raise ReleaseValidatorError(f"CHANGELOG not found at {path}.")
    return path.read_text(encoding="utf-8-sig")


def changelog_has_entry(changelog: str, version: str) -> bool:
    lines = changelog.splitlines()
    capture = False
    content: list[str] = []
    for line in lines:
        heading = parse_changelog_heading(line)
        if heading:
            if capture:
                break
            capture = heading.version == version
            continue
        if capture:
            content.append(line.strip())
    if not capture:
        return False
    return any(fragment for fragment in content if fragment)


def changelog_section_is_finalized(changelog: str, version: str) -> bool:
    """Return ``True`` when *version* has a populated, non-``Unreleased`` section.

    A heading carrying an ``Unreleased`` marker is *pending* — populated but not
    finalized — so it does not satisfy a publish/tag run.
    """
    lines = changelog.splitlines()
    capture = False
    capture_unreleased = False
    content: list[str] = []
    for line in lines:
        heading = parse_changelog_heading(line)
        if heading:
            if capture:
                break
            capture = heading.version == version
            capture_unreleased = heading.unreleased
            continue
        if capture:
            content.append(line.strip())
    if not capture or capture_unreleased:
        return False
    return any(fragment for fragment in content if fragment)


def first_populated_changelog_entry_version(changelog: str) -> str | None:
    """Return the first populated release heading version in changelog order."""
    current_version: str | None = None
    content: list[str] = []

    def populated() -> bool:
        return current_version is not None and any(fragment for fragment in content)

    for line in changelog.splitlines():
        heading = parse_changelog_heading(line)
        if heading:
            if populated():
                return current_version
            current_version = heading.version
            content = []
            continue
        if current_version is not None:
            content.append(line.strip())

    if populated():
        return current_version
    return None


def validate_changelog_latest_version_sync(
    pyproject_version: str,
    changelog: str,
) -> ValidationIssue | None:
    """Assert the top populated changelog release entry matches pyproject.toml."""
    changelog_version = first_populated_changelog_entry_version(changelog)
    if changelog_version is None:
        return None

    if canonical_release_version(changelog_version) != canonical_release_version(pyproject_version):
        return ValidationIssue(
            message=(f"CHANGELOG.md latest release entry is {changelog_version!r}, but pyproject.toml declares {pyproject_version!r}."),
            hint=("Move or update the current release notes so the first populated CHANGELOG.md release section matches [project].version."),
        )
    return None


def validate_version_source_consistency(
    version: str,
    repo_root: Path,
    lockfile_path: Path,
    changelog_text: str,
) -> list[ValidationIssue]:
    """Collect cross-file release-version consistency issues."""
    checks = [
        validate_metadata_yaml_version_sync(version, repo_root),
        validate_uv_lock_version_sync(version, lockfile_path),
        validate_release_covers_migration_targets(version, repo_root),
        validate_changelog_latest_version_sync(version, changelog_text),
    ]
    return [issue for issue in checks if issue is not None]


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReleaseValidatorError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def find_repo_root(start: Path) -> Path:
    try:
        output = git("rev-parse", "--show-toplevel", cwd=start)
    except ReleaseValidatorError as exc:
        raise ReleaseValidatorError("Unable to locate git repository root. Ensure git is installed and run this script inside the Spec Kitty repository.") from exc
    return Path(output)


def discover_release_tags(repo_root: Path, tag_pattern: str, exclude: str | None = None) -> list[str]:
    output = git("tag", "--list", tag_pattern, cwd=repo_root)
    tags = [line.strip() for line in output.splitlines() if line.strip()]
    filtered = [tag for tag in tags if tag != exclude and tag.startswith("v") and RELEASE_VERSION_RE.match(tag.lstrip("v"))]
    filtered.sort(key=lambda tag: parse_release_version(tag.lstrip("v")), reverse=True)
    return filtered


def parse_release_version(value: str) -> tuple[int, int, int, int, int, int]:
    match = RELEASE_VERSION_RE.match(value)
    if not match:
        raise ReleaseValidatorError(
            f"Value '{value}' is not a valid release version (expected X.Y.Z or X.Y.Z.N, optionally followed by a/b/rc/alpha/beta and a number)."
        )

    stage = _normalize_stage(match.group("stage"))
    stage_number = int(match.group("stage_num") or "0")
    stage_rank = {
        "a": 0,
        "b": 1,
        "rc": 2,
        None: 3,
    }[stage]
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        int(match.group("hotfix") or "0"),
        stage_rank,
        stage_number,
    )


def canonical_release_version(value: str) -> str:
    """Return the canonical spelling for an accepted release version."""
    match = RELEASE_VERSION_RE.match(value)
    if not match:
        raise ReleaseValidatorError(
            f"Value '{value}' is not a valid release version (expected X.Y.Z or X.Y.Z.N, optionally followed by a/b/rc/alpha/beta and a number)."
        )

    version = f"{int(match.group('major'))}.{int(match.group('minor'))}.{int(match.group('patch'))}"
    if match.group("hotfix") is not None:
        version += f".{int(match.group('hotfix'))}"
    stage = _normalize_stage(match.group("stage"))
    if stage is None:
        return version
    return f"{version}{stage}{int(match.group('stage_num') or '0')}"


def detect_tag_from_env() -> str | None:
    ref_name = os.getenv("GITHUB_REF_NAME")
    if ref_name and ref_name.startswith("v") and RELEASE_VERSION_RE.match(ref_name[1:]):
        return ref_name
    ref = os.getenv("GITHUB_REF")
    if ref and ref.startswith("refs/tags/"):
        candidate = ref.rsplit("/", maxsplit=1)[-1]
        if candidate.startswith("v") and RELEASE_VERSION_RE.match(candidate[1:]):
            return candidate
    return None


def validate_version_progression(current_version: str, existing_tags: Sequence[str]) -> ValidationIssue | None:
    if not existing_tags:
        return None
    current_tuple = parse_release_version(current_version)
    latest_tuple = parse_release_version(existing_tags[0].lstrip("v"))
    if current_tuple <= latest_tuple:
        return ValidationIssue(
            message=f"Version {current_version} does not advance beyond latest tag {existing_tags[0]}.",
            hint="Select a stable or prerelease version greater than previously published releases.",
        )
    return None


def _literal_string_assignments(path: Path) -> dict[str, str]:
    """Return module/class string assignments from *path*.

    This intentionally supports the simple migration-module patterns used in
    ``src/specify_cli/upgrade/migrations``:
    ``TARGET_VERSION = "X.Y.Z"`` and ``target_version = TARGET_VERSION``.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}

    values: dict[str, str] = {}

    def visit_body(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                value: str | None = None
                if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                    value = stmt.value.value
                elif isinstance(stmt.value, ast.Name):
                    value = values.get(stmt.value.id)
                if value is None:
                    continue
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = value
            elif isinstance(stmt, ast.ClassDef):
                visit_body(stmt.body)

    visit_body(tree.body)
    return values


def load_migration_target_versions(repo_root: Path) -> list[str]:
    """Read registered migration target versions from source files.

    Missing source trees return an empty list so external package-level tests can
    reuse the release validator without vendoring Spec Kitty's repository layout.
    """
    migrations_dir = repo_root / "src" / "specify_cli" / "upgrade" / "migrations"
    if not migrations_dir.is_dir():
        return []

    targets: list[str] = []
    for migration_file in sorted(migrations_dir.glob("m_*.py")):
        values = _literal_string_assignments(migration_file)
        target = values.get("target_version")
        if target and RELEASE_VERSION_RE.match(target):
            targets.append(target)
    return targets


def validate_release_covers_migration_targets(
    release_version: str,
    repo_root: Path,
) -> ValidationIssue | None:
    """Block releases that sit behind migration targets.

    Users upgrading to a package version only run migrations whose
    ``target_version`` is <= that package version. A migration target above the
    package version, including above an RC, is therefore skipped by the real
    upgrade path.
    """
    release_tuple = parse_release_version(release_version)
    ahead: list[str] = []

    for target in load_migration_target_versions(repo_root):
        target_tuple = parse_release_version(target)
        if target_tuple > release_tuple:
            ahead.append(target)

    if not ahead:
        return None

    unique_ahead = sorted(set(ahead), key=parse_release_version)
    latest = unique_ahead[-1]
    return ValidationIssue(
        message=(f"Release {release_version} is behind migration target(s): {', '.join(unique_ahead)}."),
        hint=(
            f"A user upgrading to {release_version} will not run migrations "
            f"targeted after {release_version}. Retarget those migrations to "
            f"{release_version}, or bump the package version to at least {latest} "
            "before tagging."
        ),
    )


def ensure_tag_matches_version(version: str, tag: str | None) -> ValidationIssue | None:
    expected = f"v{version}"
    if not tag:
        return ValidationIssue(
            message="No release tag detected.",
            hint="Pass --tag, set GITHUB_REF_NAME, or run in branch mode.",
        )
    if tag != expected:
        return ValidationIssue(
            message=f"Tag {tag} does not match project version {version}.",
            hint=f"Retag the commit as {expected} or bump the version in pyproject.toml.",
        )
    return None


def run_validation(args: argparse.Namespace) -> ValidationResult:
    pyproject_path = Path(args.pyproject).resolve()
    changelog_path = Path(args.changelog).resolve() if args.changelog else pyproject_path.parent / "CHANGELOG.md"
    lockfile_path = Path(args.lockfile).resolve() if args.lockfile else pyproject_path.parent / "uv.lock"
    version = ""
    tag: str | None = None
    issues: list[ValidationIssue] = []

    try:
        version = load_pyproject_version(pyproject_path)
    except ReleaseValidatorError as exc:
        issues.append(ValidationIssue(str(exc)))
        return ValidationResult(
            ok=False,
            mode=args.mode,
            pyproject_path=pyproject_path,
            changelog_path=changelog_path,
            lockfile_path=lockfile_path,
            version=version,
            tag=tag,
            issues=issues,
        )

    repo_root = find_repo_root(pyproject_path.parent)
    if not args.changelog:
        changelog_path = repo_root / "CHANGELOG.md"
    if not args.lockfile:
        lockfile_path = repo_root / "uv.lock"

    try:
        changelog_text = read_changelog(changelog_path)
    except ReleaseValidatorError as exc:
        issues.append(ValidationIssue(str(exc)))
        return ValidationResult(
            ok=False,
            mode=args.mode,
            pyproject_path=pyproject_path,
            changelog_path=changelog_path,
            lockfile_path=lockfile_path,
            version=version,
            tag=tag,
            issues=issues,
        )

    issues.extend(
        validate_version_source_consistency(
            version,
            repo_root,
            lockfile_path,
            changelog_text,
        )
    )

    if not changelog_has_entry(changelog_text, version):
        issues.append(
            ValidationIssue(
                message=f"CHANGELOG.md lacks a populated section for {version}.",
                hint="Add release notes under a '## {version}' heading.",
            )
        )
    elif args.mode == "tag" and not changelog_section_is_finalized(changelog_text, version):
        # Branch mode tolerates a pending ``## [Unreleased] - X.Y.Z`` heading, but
        # an actual publish run must point at a finalized ``## [X.Y.Z]`` section.
        issues.append(
            ValidationIssue(
                message=(f"CHANGELOG.md lacks a finalized section for {version}: the section is still marked 'Unreleased'."),
                hint=(f"Finalize the release notes by retitling the heading to '## [{version}]' (with the release date) before tagging."),
            )
        )

    if args.mode == "tag":
        tag = args.tag or detect_tag_from_env()
        if not tag:
            issues.append(
                ValidationIssue(
                    message="No tag supplied and none detected from environment.",
                    hint="Use --tag vX.Y.Z or vX.Y.ZaN, or set GITHUB_REF_NAME when running in CI.",
                )
            )
        else:
            mismatch = ensure_tag_matches_version(version, tag)
            if mismatch:
                issues.append(mismatch)

        existing_tags = discover_release_tags(
            repo_root,
            tag_pattern=args.tag_pattern,
            exclude=tag,
        )
        progression_issue = validate_version_progression(version, existing_tags)
        if progression_issue:
            issues.append(progression_issue)
    elif not args.consistency_only:
        existing_tags = discover_release_tags(repo_root, tag_pattern=args.tag_pattern)
        progression_issue = validate_version_progression(version, existing_tags)
        if progression_issue:
            issues.append(progression_issue)

    ok = len(issues) == 0
    return ValidationResult(
        ok=ok,
        mode=args.mode,
        pyproject_path=pyproject_path,
        changelog_path=changelog_path,
        lockfile_path=lockfile_path,
        version=version,
        tag=tag,
        issues=issues,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_validation(args)
    result.report()
    if result.ok:
        return 0
    for issue in result.issues:
        print(f"ERROR: {issue.format()}", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
