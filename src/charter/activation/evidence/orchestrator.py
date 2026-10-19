"""Evidence orchestration for charter synthesis."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import ruamel.yaml

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.evidence.corpus_loader import CorpusLoader
from charter.activation.synthesizer.evidence import CodeSignals, CorpusSnapshot, EvidenceBundle
from kernel.clock import now_utc_iso

__all__ = [
    "ConfigShapeError",
    "EvidenceOrchestrator",
    "load_url_list_from_config",
]


class ConfigShapeError(RuntimeError):
    """Raised when ``.kittify/config.yaml``'s top-level YAML content is not a mapping.

    A YAML document need not be a mapping — ``just-a-string``, ``- a\\n- b``, and
    ``42`` all parse without error but are not a ``dict``. Before this guard, a
    corrupted or hand-edited config.yaml in this shape made ``config.get(...)``
    raise a bare ``AttributeError`` that propagated, unhandled, all the way through
    ``charter status --json`` (and ``synthesize``/``resynthesize``), leaking raw
    Python exception text through the structured ``--json`` error envelope
    (ledger SK-16). Raising this typed, message-carrying exception here keeps the
    fail-closed outcome the ledger's SK-16 entry says is correct (exit 1,
    ``success: false``) while replacing the leaked exception text with a
    controlled diagnostic that names the file and the real problem.
    """


@dataclass
class EvidenceResult:
    """Result of evidence collection — always has a bundle (may be empty)."""

    bundle: EvidenceBundle
    warnings: list[str] = field(default_factory=list)


class EvidenceOrchestrator:
    """Coordinates evidence collection from all configured sources."""

    def __init__(
        self,
        repo_root: Path,
        url_list: tuple[str, ...] = (),
        skip_code: bool = False,
        skip_corpus: bool = False,
        corpus_root: Path | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._url_list = url_list
        self._skip_code = skip_code
        self._skip_corpus = skip_corpus
        self._corpus_root = corpus_root

    def collect(self) -> EvidenceResult:
        """Run all enabled collectors with exception isolation."""
        warnings: list[str] = []
        code_signals: CodeSignals | None = None
        corpus_snapshot: CorpusSnapshot | None = None

        if not self._skip_code:
            try:
                collector = CodeReadingCollector(self._repo_root)
                code_signals = collector.collect()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Code-reading evidence collection failed: {exc}")

        if not self._skip_corpus:
            # The corpus is chosen by the primary language only (stack_id is built from it);
            # the other observed languages in ``code_signals.languages`` do not select one (D-06).
            profile_key = code_signals.stack_id if code_signals else "generic"
            try:
                loader = CorpusLoader(corpus_root=self._corpus_root)
                corpus_snapshot = loader.load(profile_key)
                if corpus_snapshot is None:
                    warnings.append(
                        f"No corpus found for profile '{profile_key}' or 'generic'; "
                        "synthesis proceeds without corpus evidence."
                    )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Corpus loading failed: {exc}")

        bundle = EvidenceBundle(
            code_signals=code_signals,
            url_list=self._url_list,
            corpus_snapshot=corpus_snapshot,
            collected_at=now_utc_iso(),
        )
        return EvidenceResult(bundle=bundle, warnings=warnings)


def load_url_list_from_config(repo_root: Path) -> tuple[str, ...]:
    """Read charter.synthesis_inputs.url_list from .kittify/config.yaml.

    Post-#2773, the `charter` key holds a path string pointing at
    `.kittify/charter/charter.yaml` rather than an inline mapping, so
    `synthesis_inputs.url_list` has no live config home there anymore.
    Returns an empty tuple whenever the key is absent, the file does not
    exist, or `charter` is not a mapping (e.g. the path-string shape) --
    all of those are *valid, understood* config shapes.

    A non-mapping *top-level* document is different: it is not a valid
    config.yaml shape at all (corruption or a hand-editing mistake), so this
    raises :class:`ConfigShapeError` rather than silently returning ``()``.
    Silently returning empty here would make ``charter status --json`` exit 0
    with a full success envelope on a corrupted config file -- exactly the
    "silent success" failure mode this repository's own ledger (SK-16) and
    charter treat as a defect class, not a style choice.

    Raises:
        ConfigShapeError: ``config.yaml``'s top-level YAML content parses but
            is not a mapping (e.g. a bare scalar or a list).
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return ()
    yaml = ruamel.yaml.YAML()
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            config = yaml.load(fh) or {}
    except Exception:  # noqa: BLE001
        return ()
    if not isinstance(config, dict):
        raise ConfigShapeError(
            f"{config_path} must be a YAML mapping at the top level; found "
            f"{type(config).__name__} instead. Repair the file (it should look "
            "like `charter: ...`) or restore it from version control."
        )
    charter_cfg = config.get("charter") or {}
    if not isinstance(charter_cfg, dict):
        charter_cfg = {}
    synthesis_inputs = charter_cfg.get("synthesis_inputs") or {}
    raw = synthesis_inputs.get("url_list") or []
    return tuple(u for u in raw if u and isinstance(u, str))
