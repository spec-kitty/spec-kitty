"""Review cycle artifact model for spec-kitty.

Defines ReviewCycleArtifact and AffectedFile dataclasses for persisting
review feedback as versioned, committed artifacts in kitty-specs/.

Artifacts are stored at:
  kitty-specs/<mission>/tasks/<WP-slug>/review-cycle-{N}.md

and referenced via:
  review-cycle://<mission_slug>/<wp_slug>/review-cycle-{N}.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded
from kernel.yaml_io import serialize_mapping

TERMINAL_REVIEW_LANES = frozenset({"approved", "done"})


class ReviewArtifactReadError(GuardedReadError, ValueError):
    """Raised when a ``review-cycle-*.md`` artifact exists but cannot be parsed.

    Mission cli-error-surface-seam WP07/#4746: subclasses ``ValueError`` (in
    addition to :class:`kernel.errors.GuardedReadError`) so existing
    ``except ValueError`` call sites keep matching (D3). Every structural
    failure :meth:`ReviewCycleArtifact.from_file` used to raise directly
    (missing/malformed frontmatter delimiters, invalid YAML, a non-mapping
    payload, or a missing/invalid field) now collapses into this type via
    :func:`kernel.guarded_read.read_guarded`, carrying the SAME message text
    each of those direct raises produced.
    """


_REVIEW_CYCLE_NUMBER_RE = re.compile(r"review-cycle-(\d+)\.md$")

# Campsite (S1192): the ``review-cycle-*.md`` glob and the ``review-cycle-
# {n}.md`` filename shape were duplicated as literals throughout this module
# (~16 occurrences pre-hoist). Both are now sourced from here so every glob
# and every filename build go through a single spelling.
_REVIEW_CYCLE_GLOB = "review-cycle-*.md"


def _review_cycle_filename(cycle_number: int) -> str:
    """Build the on-disk filename for *cycle_number* (``review-cycle-{n}.md``)."""
    return f"review-cycle-{cycle_number}.md"


def _parse_review_cycle_candidates(sub_artifact_dir: Path) -> tuple[list[int], list[str]]:
    """Parse ``review-cycle-*.md`` siblings into cycle numbers, for T032/T033.

    Returns a tuple of (parsed cycle numbers, unparseable filenames). A
    filename is "unparseable" when it matches the ``review-cycle-*.md`` glob
    but not the strict ``review-cycle-(\\d+)\\.md$`` numbering regex (e.g.
    ``review-cycle-final.md``). Used only by :meth:`ReviewCycleArtifact.
    next_cycle_number` — deliberately NOT shared with :func:`_cycle_number_or_zero`
    (WP13/T058's consolidation of the two former ``latest()``/
    ``latest_review_artifact_verdict`` closures), which answers a different
    question ("highest currently readable artifact", where an unparseable
    sibling correctly sorts as `0`) under different, already-shipped refusal
    semantics — this function's REFUSAL on an unparseable sibling must not
    leak into that helper's tolerant sort.
    """
    parsed_numbers: list[int] = []
    unparseable_names: list[str] = []
    for candidate in sub_artifact_dir.glob(_REVIEW_CYCLE_GLOB):
        match = _REVIEW_CYCLE_NUMBER_RE.search(candidate.name)
        if match is None:
            unparseable_names.append(candidate.name)
        else:
            parsed_numbers.append(int(match.group(1)))
    return parsed_numbers, unparseable_names


def _cycle_number_or_zero(path: Path) -> int:
    """Sort key answering "what cycle number does *path* look like it is",
    where an unparseable ``review-cycle-*.md`` sibling sorts as ``0`` (i.e.
    lowest, never masking a genuinely higher-numbered readable artifact).

    WP13 (T058) consolidation: this was two byte-identical inline closures,
    one each inside :meth:`ReviewCycleArtifact.latest` and
    :func:`latest_review_artifact_verdict`. Both answer the SAME question
    ("highest currently-*readable* artifact") and are consolidated here.
    Deliberately NOT merged with :func:`_parse_review_cycle_candidates`
    (used only by :meth:`ReviewCycleArtifact.next_cycle_number`), which
    answers a DIFFERENT question ("is it safe to allocate the next cycle
    number") under different, already-shipped refusal semantics (WP09) — an
    unparseable sibling REFUSES there, it does not sort as `0`. Leaking that
    refusal semantic into this helper would change `latest()`'s answer for
    already-passing callers; this helper's behaviour is unchanged from the
    two closures it replaces.
    """
    match = _REVIEW_CYCLE_NUMBER_RE.search(path.name)
    return int(match.group(1)) if match else 0


def _make_yaml() -> YAML:
    """Create a configured ruamel.yaml instance for frontmatter serialization."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 4096  # prevent line wrapping
    return yaml


@dataclass(frozen=True)
class AffectedFile:
    """A file affected by a review cycle."""

    path: str  # relative to repo root
    line_range: str | None = None  # "start-end" or None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict with sorted keys."""
        d: dict[str, Any] = {"path": self.path}
        if self.line_range is not None:
            d["line_range"] = self.line_range
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AffectedFile:
        """Deserialize from dict."""
        if not isinstance(data, dict):
            raise ValueError(
                "affected_files entries must be mappings with a 'path' key"
            )
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError(
                "affected_files entries must include a non-empty string 'path'"
            )
        line_range = data.get("line_range")
        if line_range is not None and not isinstance(line_range, str):
            raise ValueError(
                "affected_files entry 'line_range' must be a string when present"
            )
        return cls(
            path=path,
            line_range=line_range,
        )


@dataclass(frozen=True)
class ReviewCycleArtifact:
    """A persisted review cycle artifact.

    Written to disk as a markdown file with YAML frontmatter at:
      kitty-specs/<mission>/tasks/<WP-slug>/review-cycle-{N}.md
    """

    cycle_number: int
    wp_id: str
    mission_slug: str
    reviewer_agent: str
    reviewed_at: str  # ISO 8601 UTC
    affected_files: list[AffectedFile] = field(default_factory=list)
    reproduction_command: str | None = None
    body: str = ""  # markdown body (not in frontmatter)
    # Operator/arbiter override stamped onto a rejected artifact by the approval
    # gate (``agent tasks move-task --to approved`` over a rejected latest). When
    # present and complete, the override IS the approval record — terminal-lane
    # consistency gates must honor it just as the approval gate does (see #1924).
    override_actor: str | None = None
    override_reason: str | None = None

    @property
    def has_complete_override(self) -> bool:
        """True iff a complete approval override (actor + reason) is stamped on."""
        return bool(
            self.override_actor
            and self.override_actor.strip()
            and self.override_reason
            and self.override_reason.strip()
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize frontmatter fields to dict with sorted keys."""
        d: dict[str, Any] = {
            "affected_files": [af.to_dict() for af in self.affected_files],
            "cycle_number": self.cycle_number,
            "mission_slug": self.mission_slug,
            "reproduction_command": self.reproduction_command,
            "reviewed_at": self.reviewed_at,
            "reviewer_agent": self.reviewer_agent,
            "wp_id": self.wp_id,
        }
        # Round-trip the approval-override block when present so a
        # ``from_file``→``write`` cycle does not silently drop the override that
        # the approval gate stamped onto a rejected artifact (#1924). Keys are
        # emitted only when set, leaving non-overridden artifacts byte-identical.
        if self.override_actor is not None:
            d["review_artifact_override_actor"] = self.override_actor
        if self.override_reason is not None:
            d["review_artifact_override_reason"] = self.override_reason
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any], body: str = "") -> ReviewCycleArtifact:
        """Deserialize from frontmatter dict and optional body string."""
        cycle_number = data.get("cycle_number")
        if cycle_number is None or isinstance(cycle_number, bool):
            raise ValueError("cycle_number must be a positive integer")
        try:
            parsed_cycle_number = int(cycle_number)
        except (TypeError, ValueError) as exc:
            raise ValueError("cycle_number must be a positive integer") from exc
        if parsed_cycle_number < 1:
            raise ValueError("cycle_number must be a positive integer")

        wp_id = data.get("wp_id")
        if not isinstance(wp_id, str) or not wp_id:
            raise ValueError("wp_id must be a non-empty string")
        mission_slug = data.get("mission_slug")
        if not isinstance(mission_slug, str) or not mission_slug:
            raise ValueError("mission_slug must be a non-empty string")
        reviewer_agent = data.get("reviewer_agent")
        if not isinstance(reviewer_agent, str) or not reviewer_agent:
            raise ValueError("reviewer_agent must be a non-empty string")
        # FR-003/SC-007 (WP06): the frontmatter no longer carries `verdict` as an
        # authoritative field -- every verdict reader resolves the event
        # authority instead (WP05's reader collapse). A stray legacy `verdict`
        # key on an old, pre-schema-change `.md` file is silently ignored here
        # (not stored on the dataclass, not validated) -- this deserializer
        # deliberately no longer requires OR accepts it as authoritative.
        reviewed_at = data.get("reviewed_at")
        if not isinstance(reviewed_at, str) or not reviewed_at:
            raise ValueError("reviewed_at must be a non-empty string")
        affected_files_data = data.get("affected_files", [])
        if not isinstance(affected_files_data, list):
            raise ValueError("affected_files must be a list")
        reproduction_command = data.get("reproduction_command")
        if reproduction_command is not None and not isinstance(reproduction_command, str):
            raise ValueError("reproduction_command must be a string when present")

        affected_files = [
            AffectedFile.from_dict(af)
            for af in affected_files_data
        ]
        # Optional approval-override block (written by the approval gate onto a
        # rejected artifact when move-task --to approved applies an arbiter/operator
        # override). Tolerant parse: non-string values are treated as absent.
        override_actor = data.get("review_artifact_override_actor")
        override_reason = data.get("review_artifact_override_reason")
        return cls(
            cycle_number=parsed_cycle_number,
            wp_id=wp_id,
            mission_slug=mission_slug,
            reviewer_agent=reviewer_agent,
            reviewed_at=reviewed_at,
            affected_files=affected_files,
            reproduction_command=reproduction_command,
            body=body,
            override_actor=override_actor if isinstance(override_actor, str) else None,
            override_reason=override_reason if isinstance(override_reason, str) else None,
        )

    def write(self, path: Path) -> None:
        """Write this artifact to disk as a markdown file with YAML frontmatter.

        The parent directory is created if it does not exist.

        Serialization is delegated to :func:`kernel.yaml_io.serialize_mapping`
        (#3058 follow-up): its rt/preserve_quotes/default_flow_style/width=4096
        configuration is byte-for-byte identical to :func:`_make_yaml`'s for
        every frontmatter scalar within the 4096 wrap width (verified by
        ``tests/review/test_artifacts_yaml_seam.py``) — the payloads this
        artifact produces. The sole divergence is a scalar long enough to wrap
        past 4096 columns, where ``serialize_mapping`` additionally strips the
        non-semantic trailing whitespace the old path left (a strict
        improvement, semantically identical). So this migration is a pure
        internal seam consolidation with no observable output change for real
        review-cycle payloads.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter_text = serialize_mapping(self.to_dict()).decode("utf-8")

        content = f"---\n{frontmatter_text}---\n"
        if self.body:
            content += f"\n{self.body}"

        # Write bytes so the canonical LF representation is identical on every
        # platform.  Text-mode writes with ``newline=None`` translate ``\n`` to
        # CRLF on Windows, while Git's clean conversion can store LF in the
        # governed-ref blob; exact durability read-back must compare the same
        # bytes on both sides rather than normalize that mismatch away.
        path.write_bytes(content.encode("utf-8"))

    @classmethod
    def from_file(cls, path: Path) -> ReviewCycleArtifact:
        """Parse a review-cycle artifact from a markdown file with YAML frontmatter.

        Raises:
            ReviewArtifactReadError: If the file cannot be read or parsed
                (unreadable/non-UTF-8, missing delimiters, bad YAML, a
                non-mapping payload, or a missing/invalid field) -- a
                :class:`kernel.errors.GuardedReadError` subclass that is
                also a ``ValueError`` (D3), so existing
                ``except ValueError`` call sites keep matching.
        """

        def _parse(content: bytes | str) -> ReviewCycleArtifact:
            text = content.decode("utf-8") if isinstance(content, bytes) else content

            # Split on --- delimiters.  The file must start with "---\n".
            if not text.startswith("---"):
                raise ValueError(
                    f"Review artifact file has no YAML frontmatter: {path}"
                )

            # Find the closing --- delimiter
            # text[3:] skips the opening ---
            rest = text[3:]
            # Skip optional newline after opening ---
            if rest.startswith("\n"):
                rest = rest[1:]
            closing = rest.find("\n---")
            if closing == -1:
                raise ValueError(
                    f"Review artifact file has no closing '---' delimiter: {path}"
                )

            frontmatter_str = rest[:closing]
            body_raw = rest[closing + 4:]  # skip \n---
            # Strip leading newline from body
            body = body_raw.lstrip("\n")

            yaml = _make_yaml()
            try:
                data = yaml.load(frontmatter_str)
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse YAML frontmatter in {path}: {exc}"
                ) from exc

            if not isinstance(data, dict):
                raise ValueError(
                    f"YAML frontmatter in {path} is not a mapping"
                )

            try:
                return cls.from_dict(data, body=body)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Missing or invalid field in review artifact {path}: {exc}"
                ) from exc

        return read_guarded(
            path,
            _parse,
            errors=(ValueError,),
            error_cls=ReviewArtifactReadError,
        )

    @staticmethod
    def latest(sub_artifact_dir: Path) -> ReviewCycleArtifact | None:
        """Return the highest-numbered review cycle artifact in *sub_artifact_dir*.

        Returns None if no review-cycle-*.md files exist.
        """
        candidates = list(sub_artifact_dir.glob(_REVIEW_CYCLE_GLOB))
        if not candidates:
            return None

        candidates.sort(key=_cycle_number_or_zero)
        return ReviewCycleArtifact.from_file(candidates[-1])

    @staticmethod
    def latest_cycle_number(sub_artifact_dir: Path) -> int:
        """Return the highest review-cycle number present, by FILENAME only.

        Unlike :meth:`latest`, this never parses a candidate's body/
        frontmatter — it reuses the same tolerant :func:`_cycle_number_or_zero`
        sort key :meth:`latest` sorts with, so an unparseable or otherwise
        damaged sibling (e.g. a merge-conflict-marked file with no valid YAML
        frontmatter at all -- #3244) sorts as ``0`` rather than raising.
        Callers that only need the NUMBER (not the parsed artifact) -- e.g.
        :func:`specify_cli.review.arbiter.persist_arbiter_decision` -- should
        prefer this over ``latest(...).cycle_number`` so a damaged artifact
        cannot crash resolution.

        Returns 0 if no review-cycle-*.md files exist.
        """
        candidates = list(sub_artifact_dir.glob(_REVIEW_CYCLE_GLOB))
        return max((_cycle_number_or_zero(p) for p in candidates), default=0)

    @staticmethod
    def next_cycle_number(sub_artifact_dir: Path) -> int:
        """Return the next cycle number for a new artifact in *sub_artifact_dir*.

        Derives the result as ``max(parsed cycle numbers) + 1`` — never a count
        of files present (FR-006 / I-2) — so a numbering gap (e.g. cycles 1 and
        3 present, 2 missing) cannot produce a number that collides with an
        existing artifact. Returns 1 if no review-cycle-*.md files exist.

        Raises:
            ValueError: if any sibling filename matches the
                ``review-cycle-*.md`` glob but cannot be parsed for its cycle
                number under the strict ``review-cycle-(\\d+)\\.md$`` regex —
                the true next number cannot be established with confidence
                while such a file is present, so this refuses rather than
                silently excluding it from the derivation (which would
                reproduce the identical defect one level down). Also raised
                (defensively) if the derived next number already names a file
                that exists on disk.
        """
        parsed_numbers, unparseable_names = _parse_review_cycle_candidates(
            sub_artifact_dir
        )
        if unparseable_names:
            raise ValueError(
                f"Cannot determine next cycle number in {sub_artifact_dir}: "
                "unparseable review-cycle filename(s): "
                f"{', '.join(sorted(unparseable_names))}"
            )
        if not parsed_numbers:
            return 1
        next_number = max(parsed_numbers) + 1
        collision_path = sub_artifact_dir / _review_cycle_filename(next_number)
        if collision_path.exists():
            raise ValueError(
                f"Cannot allocate cycle number {next_number} in "
                f"{sub_artifact_dir}: {collision_path.name} already exists"
            )
        return next_number


# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-003) retired
# ``latest_review_artifact_verdict`` and ``rejected_review_artifact_for_
# terminal_lane`` here -- the two genuine verdict-parser functions this
# module carried (squad #1's scope correction: NOT ``ReviewCycleArtifact.
# latest``/``.from_file``, which are content/cycle-number loaders, kept
# above). Every consumer now resolves the event authority
# (``status.event_sourced_review_result``) instead; WP08's reconciliation task
# records the retired reader set.
