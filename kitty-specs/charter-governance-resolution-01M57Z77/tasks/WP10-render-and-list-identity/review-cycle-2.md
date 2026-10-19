---
affected_files: []
cycle_number: 2
mission_slug: charter-governance-resolution-01M57Z77
reproduction_command:
reviewed_at: '2026-10-19T02:23:41Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review feedback (reviewer-renata), cycle 2

Cycle-1 items 2 (suppressions) and 3 (timing) are addressed. The suppressions are gone: the payloads are typed as `dict[str, Any]` and the import is in the module's import block. The timing test passes 3 of 3 serial runs. ruff, format (`--force-exclude`), `mypy --strict`, C901 and the targeted tests (130 passed) are all clean. Item 1 (changelog) moves to closeout, per the orchestrator.

One blocking issue remains: the new fast path in `identity_index.py`.

## 1. `_declared_id_of` does not equal the full parse (required)

The docstring says the result "always equals `kind_vocabulary._read_id`'s". It does not. The fast path is also load-bearing. Swapping `_declared_id_of` for `_full_parse` in a probe of the same timing harness gives preset/list ratios of 1.54x and 1.65x, which breaks the 1.5x budget. With the fast path the ratios are 1.02x and 1.05x. So the fast path is warranted, but it has to be correct.

These divergences were probed with `kind_vocabulary._parse_id` against `_declared_id_of` (full, then fast):

| value | full | fast |
|---|---|---|
| `id: 001` | `'1'` | `'001'` |
| `id: true` | `'True'` | `'true'` |
| `id: null` / `id: Null` | `'None'` | `'null'` / `'Null'` |
| `id: 1.50` | `'1.5'` | `'1.50'` |
| `id: 1e3` | `'1000.0'` | `'1e3'` |
| `id: 0o17` / `id: 0x1F` | `'15'` / `'31'` | the literal |
| a multi-document file (`---`) | `None` | the id |
| a duplicate `id:` key | `None` | the id |
| broken YAML later in the file | `None` | the id |
| a top-level sequence after the line | `None` | the id |

This matters for two reasons:
- The fast-path value is written into the shared `ResolutionPass.ids`, the pass that `_Roots` and `kind_vocabulary._read_id` read. A later resolver read in the same pass gets the fast value, not the parse result.
- An artifact with `id: 001` gets one identity in the index and another everywhere else. That is the split identity this mission exists to remove. A malformed file the resolver treats as unreadable gets indexed as activatable.

The ten parametrised cases in `test_declared_id_fast_path_equals_full_parse` miss every one of these. `id: 0` agrees only by coincidence.

Required fixes:
1. Take the fast path only when YAML's implicit resolver would type the value as a string. For example, `yaml.resolver.resolve(ScalarNode, value, (True, False)) == "tag:yaml.org,2002:str"` (ruamel's own resolver, so it stays exact and cheap). Anything else falls back to the full parse.
2. Malformed and multi-document files: either fall back when the text has a document marker (`^---` / `^\.\.\.`) or more than one top-level `<id_field>:` line, or deliberately accept the residual "malformed YAML later in the file" case. If you accept it, state it in the docstring, which must not claim "always equals". Whichever you choose, the docstring must state the true contract.
3. Commit an equivalence test that asserts `_declared_id_of == _parse_id` for every `*.yaml` under `packs/built-in` and each relevant id field (`id`, and the profile field from `_id_field_for`). The ad-hoc run over 650 files and 1950 pairs found 0 diffs today; the test locks that in. Add the table above as parametrised cases.
4. Re-run `test_preset_cli_timing.py` serially (`-n0`) after the change and confirm it still passes.
