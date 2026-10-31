# Research — charter packs refusal code convergence (issue #6772)

Recorded during the mission's discovery step, from grounding on `main@512567eee7`
(2026-10-30). Extends, never replaces, this file.

## Reproduction (evidence)

Reproduced on current `main` with the shared fixtures of
`tests/specify_cli/cli/commands/charter/test_activation_text_golden.py`
(`build_activation_project`) and `.kittify/config.yaml` rewritten to
`charter_packs: [1, 2]`:

| Invocation | Exit | Code |
| --- | --- | --- |
| `charter activate directive 001-...` (text) | 1 | `ACTIVATION_FAILED` |
| `charter activate directive 001-... --json` | 1 | `ACTIVATION_FAILED` |
| `charter deactivate directive 001-...` (text) | 1 | `ACTIVE_CHARTER_CONFIG_INVALID` |
| `charter deactivate directive 001-... --json` | 1 | `ACTIVE_CHARTER_CONFIG_INVALID` |

Within each verb, text and `--json` agree on the code; the divergence is between
the verbs. All four write nothing under `.kittify/`. The asymmetry is pinned by
`test_activation_json_6525.py::test_a_malformed_charter_packs_config_is_refused`
and documented as known in `docs/api/charter-commands.md` (follow-up #6772 — this
issue), so it is not superseded.

## Cause chain (verified in source)

- **deactivate** refuses during the direct write: `ActiveCharterManager.deactivate`
  → `load_denied` (strict required floor, `charter.activation.pack_context`) →
  `read_org_required_tokens(strict=True)` →
  `org_pack_discovery._declared_org_packs(strict=True)` → `_strict_error(...)`
  which raises `ActiveCharterConfigError` (code `ACTIVE_CHARTER_CONFIG_INVALID`).
  The CLI maps `ActiveCharterConfigError` → `config_refusal` (its own code).
- **activate** refuses earlier, in `_apply_direct_activation`
  (`specify_cli/cli/commands/charter/activate.py`):
  `resolve_pack_chain(repo_root, strict=True)` →
  `charter.offering.drg.org_pack_config.require_declared_org_roots` →
  `load_pack_registry(strict=True)` raises a plain `ValueError`, which
  `require_declared_org_roots` re-raises as
  `ValueError("the org pack registry cannot be read: ...")`. The CLI maps generic
  `ValueError` → `ACTIVATION_FAILED`.

## Decision: the fix lands at the shared seam, as a typed error

**Decision D1.** `require_declared_org_roots` (the one fail-closed registry read
behind `resolve_pack_chain(strict=True)`) raises a **dedicated typed error** for
the unreadable/malformed registry instead of a plain `ValueError`. The typed error
carries `ACTIVE_CHARTER_CONFIG_INVALID` (it subclasses
`charter.activation.activation_ledger.ActiveCharterConfigError`, the issue's
first suggested option) **and remains a `ValueError`**, so every existing strict
reader that catches `ValueError` keeps its documented behaviour:

- `charter.activation.effective_set._declared_org_roots` (`except ValueError` →
  `_UnresolvableError`);
- `charter.activation.preset_application._org_roots_or_refuse`
  (`except ValueError` → `PresetIdUnresolvedError`);
- `charter.activation.manifest_loader` (documents "Raises ValueError: a declared
  org pack is missing on disk" — same handler covers the registry failure);
- the CLI's `except (ValueError, DRGLoadError)` mappings.

On the activate path the typed error is caught by the pre-existing
`except ActiveCharterConfigError → config_refusal` arm *before* the
`ValueError` arm, so `activate` converges on `ACTIVE_CHARTER_CONFIG_INVALID`
with no CLI-layer change and no message-text branching (NFR-002). On deactivate
nothing changes.

**Rationale.** The alternative — plain `ActiveCharterConfigError` without the
`ValueError` base — would silently change three unrelated strict readers'
behaviour for the malformed-registry case (their `except ValueError` arms would
stop firing), violating FR-004 and the locality doctrine. The alternative of
mapping codes in the CLI by matching message text is exactly the fragility the
issue names.

**Decision D2.** The "declared pack not fetched" refusal (a declared pack whose
root is not a directory) keeps raising a plain `ValueError` from
`require_declared_org_roots`, so `activate` keeps reporting `ACTIVATION_FAILED`
with the `spec-kitty charter fetch` remedy (#4984, #5779/#6006 fail-closed
posture). No convergence of that case.

**Decision D3.** Import direction: `charter.offering.drg.org_pack_config` must
not import `charter.activation` at module load (the activation layer imports
the offering layer). The typed error crosses the seam lazily inside the raising
helper, exactly as `charter.activation.org_pack_discovery._strict_error` already
does in the other direction ("keeps the import graph acyclic").

## Where the typed error lives

`ActiveCharterConfigError` is defined in
`src/charter/activation/activation_ledger.py`. The new subclass
(`OrgPackRegistryUnreadableError`) is defined next to
`require_declared_org_roots` in `src/charter/offering/drg/org_pack_config.py`
(the module that owns the registry read and the refusal), constructed through a
lazily-importing `_registry_error` helper mirroring `_strict_error`'s shape
(D3). It keeps `require_declared_org_roots`' message lead
("the org pack registry cannot be read: ...") so the re-pinned CLI test's
`"org pack registry"` assertion holds for both verbs.

## Open questions resolved at planning

- None blocking. Message bodies of the two verbs differ slightly (deactivate's
  carries the "org required floor" remediation line from `_strict_error`);
  the mission converges the **code**, not the message prose — the issue asks
  only for code convergence and the messages already name the same cause.
