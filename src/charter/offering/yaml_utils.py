"""Shared YAML utilities for the charter offering.

Provides ``canonical_yaml`` — a deterministic, sorted-key YAML serializer
that returns bytes — and ``parse_shipped_yaml``, which parses each shipped
(built-in pack) file at most once per change.  Extracted here so it can be used by both
``charter.offering.versioning`` (migration hash computation) and
``charter.activation.synthesizer.synthesize_pipeline`` (artifact-content hashing)
without creating a circular dependency.

Dependency direction: doctrine is a leaf package. It must NOT import from
charter.*.  Any code in charter that needs canonical YAML should import from
``charter.activation.synthesizer.synthesize_pipeline.canonical_yaml`` (which delegates
here) or call this module directly.
"""

from __future__ import annotations

import copy
import io
from collections.abc import Callable, Hashable, Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def canonical_yaml(body: Mapping[str, Any]) -> bytes:
    """Serialize ``body`` to YAML bytes in a deterministic canonical form.

    Rules:
    - Keys are sorted alphabetically at every level.
    - Default flow style is False (block style).
    - No YAML aliases (pure data, no anchors/references).
    - UTF-8 encoding.

    Returns:
        UTF-8-encoded YAML bytes.  Never calls ``.encode()`` on the result;
        the bytes are produced directly by ruamel.yaml's BytesIO dump.
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.explicit_start = False

    def _sort_keys(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _sort_keys(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [_sort_keys(v) for v in obj]
        return obj

    sorted_body = _sort_keys(dict(body))
    buf = io.BytesIO()
    yaml.dump(sorted_body, buf)
    return buf.getvalue()


__all__ = ["canonical_yaml"]


#: Parsed shipped YAML documents, keyed on each file's resolved path, size and
#: modification time plus the caller's parse variant. Shipped (built-in pack)
#: files are read-only package data that a single command used to re-parse
#: dozens or thousands of times (#5526); any edit to a file changes its key, so
#: an edited file is always re-parsed. Read and parse errors propagate and are
#: never cached.
_SHIPPED_DOCUMENT_MEMO: dict[tuple[str, int, int, Hashable], Any] = {}


def parse_shipped_yaml(path: Path, parse: Callable[[Path], Any], *, variant: Hashable) -> Any:
    """Return ``parse(path)`` for a shipped doctrine file, parsing it at most once per change.

    Only call this for built-in pack files, which nothing writes at runtime.
    *variant* names how *parse* reads the file (for example ``"safe"``), so two
    callers that parse the same file differently never share an entry. Every
    call returns a deep copy, so a caller that mutates its document never
    affects another caller.
    """
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, variant)
    if key not in _SHIPPED_DOCUMENT_MEMO:
        _SHIPPED_DOCUMENT_MEMO[key] = parse(path)
    return copy.deepcopy(_SHIPPED_DOCUMENT_MEMO[key])
