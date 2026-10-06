"""Harness-owned adapter for agent-authored doctrine YAML.

This adapter is the production-facing charter synthesis seam after the
Anthropic SDK removal: the LLM harness writes artifact YAML files, and
spec-kitty validates, stages, and promotes them. No network calls occur here.

Input layout
------------
    .kittify/charter/generated/
      directives/<NNN>-<slug>.directive.yaml
      tactics/<slug>.tactic.yaml
      styleguides/<slug>.styleguide.yaml

Each file must already contain the final artifact body for its target. The
adapter verifies that the on-disk ``id`` matches the target's expected
artifact identity before handing it to the schema gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from kernel.clock import from_epoch

from .adapter import AdapterOutput
from .errors import GeneratedArtifactLoadError, GeneratedArtifactMissingError
from .request import SynthesisRequest
from .topic_resolver import _SYNTHESIZABLE_KINDS

__all__ = [
    "GeneratedArtifactAdapter",
]


GENERATED_ADAPTER_VERSION = "1.0.0"


class GeneratedArtifactAdapter:
    """Load agent-authored doctrine YAML from `.kittify/charter/generated/`."""

    id: str = "generated"
    version: str = GENERATED_ADAPTER_VERSION

    def __init__(self, repo_root: Path, input_root: Path | None = None) -> None:
        self._repo_root = repo_root
        self._input_root = input_root or repo_root / ".kittify" / "charter" / "generated"

    def _path_for_target(self, request: SynthesisRequest) -> Path:
        target = request.target
        if target.kind not in _SYNTHESIZABLE_KINDS:
            raise KeyError(target.kind)
        subdir = ArtifactKind(target.kind).plural
        path: Path = self._input_root / subdir / target.filename
        return path

    def _load_body(self, path: Path) -> Mapping[str, Any]:
        yaml = YAML(typ="safe")
        try:
            raw = yaml.load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise GeneratedArtifactLoadError(
                artifact_path=str(path),
                reason=f"invalid YAML: {exc}",
            ) from exc

        if not isinstance(raw, dict):
            raise GeneratedArtifactLoadError(
                artifact_path=str(path),
                reason="top-level YAML document must be a mapping",
            )
        return raw

    def _assert_target_identity(
        self,
        request: SynthesisRequest,
        body: Mapping[str, Any],
        path: Path,
    ) -> None:
        raw_id = body.get("id")
        expected_id = request.target.artifact_id
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise GeneratedArtifactLoadError(
                artifact_path=str(path),
                reason="artifact body must include a non-empty 'id' field",
                expected_id=expected_id,
            )

        actual_id = raw_id.strip()
        if actual_id != expected_id:
            raise GeneratedArtifactLoadError(
                artifact_path=str(path),
                reason="artifact id mismatch",
                expected_id=expected_id,
                actual_id=actual_id,
            )

    def generate(self, request: SynthesisRequest) -> AdapterOutput:
        path = self._path_for_target(request)
        if not path.exists():
            raise GeneratedArtifactMissingError(
                expected_path=str(path),
                kind=request.target.kind,
                slug=request.target.slug,
                expected_id=request.target.artifact_id,
            )

        body = self._load_body(path)
        self._assert_target_identity(request, body, path)

        generated_at = from_epoch(path.stat().st_mtime)
        try:
            rel_path = path.relative_to(self._repo_root)
            note_path = rel_path.as_posix()
        except ValueError:
            note_path = str(path)

        return AdapterOutput(
            body=body,
            generated_at=generated_at,
            notes=f"generated-artifact:{note_path}",
        )

    def generate_batch(
        self, requests: list[SynthesisRequest]
    ) -> list[AdapterOutput]:
        return [self.generate(request) for request in requests]
