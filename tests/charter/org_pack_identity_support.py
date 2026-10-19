"""Shared fixture builder: an org pack whose file stems differ from declared ids.

Reused by the identity tests across the charter-governance-resolution Mission
(#6406 / #6407). The pack declares one artifact per kind whose filename stem is
NOT its declared id, so any surface that compares the two spellings raw fails.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from ruamel.yaml import YAML

from charter.activation.pack_context import PackContext

ORG_PACK_NAME = "identity-org"

#: (kind plural, filename stem, declared id) for every artifact in the fixture pack.
IDENTITY_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    ("directives", "qa-003-no-fake-green", "QA_003"),
    ("tactics", "qa-tactic-seven", "qa-seven"),
    ("paradigms", "qa-paradigm-nine", "qa-nine"),
    ("styleguides", "qa-style-guide", "qa-style"),
    ("toolguides", "qa-tool-guide", "qa-tool"),
    ("procedures", "qa-procedure-file", "qa-proc"),
    ("glossary_packs", "qa-glossary-file", "qa-glossary"),
    ("mission_step_contracts", "qa-contract-file", "qa-contract"),
)

_KIND_SUFFIX = {
    "directives": "directive",
    "tactics": "tactic",
    "paradigms": "paradigm",
    "styleguides": "styleguide",
    "toolguides": "toolguide",
    "procedures": "procedure",
    "glossary_packs": "glossary-pack",
    "mission_step_contracts": "step-contract",
}


def write_identity_org_pack(repo_root: Path, **config_keys: object) -> Path:
    """Write the identity org pack under *repo_root* and register it in ``config.yaml``.

    Returns the pack directory. ``config.yaml`` keeps any keys already present;
    *config_keys* (for example ``activated_directives=[...]``) are merged on top.
    """
    pack = repo_root / ORG_PACK_NAME
    for plural, stem, declared in IDENTITY_ARTIFACTS:
        directory = pack / plural
        directory.mkdir(parents=True, exist_ok=True)
        suffix = _KIND_SUFFIX[plural]
        (directory / f"{stem}.{suffix}.yaml").write_text(
            f'schema_version: "1.0"\nid: {declared}\ntitle: {declared} title\nname: {declared} name\nsummary: {declared} summary\n',
            encoding="utf-8",
        )
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_path = kittify / "config.yaml"
    yaml = YAML()
    config = yaml.load(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    config = config or {}
    config.setdefault("mission_type_activations", ["software-dev"])
    config.update(config_keys)
    config["charter_packs"] = {"org": {"packs": [{"name": ORG_PACK_NAME, "local_path": str(pack)}]}}
    with config_path.open("w", encoding="utf-8") as stream:
        yaml.dump(config, stream)
    return pack


def real_pack_context(repo_root: Path, **fields: object) -> PackContext:
    """A real ``PackContext`` rooted at *repo_root* with the given per-kind activation fields."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_path = kittify / "config.yaml"
    if not config_path.exists():
        config_path.write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    return dataclasses.replace(PackContext.from_config(repo_root), **fields)
