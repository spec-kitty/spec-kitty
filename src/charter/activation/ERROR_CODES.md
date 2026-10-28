# Charter Activation Error & Warning Codes

This file has three parts:

1. **Charter encoding codes** (below): a hand-maintained mirror of the
   `CharterEncodingDiagnostic` StrEnum.
2. **Activation configuration codes**: codes raised when the active charter
   configuration cannot be read.
3. **Governance resolution diagnostic codes** (at the end): the `code` of each
   `{code, message}` entry in `GovernanceResolution.diagnostics` and in the
   `charter context --json` `diagnostics` list.

# Charter encoding codes

> **Source of truth**: `src/charter/activation/_diagnostics.py` (StrEnum class `CharterEncodingDiagnostic`).
> This part is a hand-maintained mirror. Until #645's code-to-docs flow exists,
> the StrEnum members and this part's `##` section count must match per NFR-008.
> The NFR-008 mirror rule covers this part only, not the activation
> configuration codes or the governance resolution diagnostic codes below.

## CHARTER_ENCODING_AMBIGUOUS

**When it fires**: the charter file's byte sequence cannot be decoded as strict
UTF-8 and no single encoding candidate from `charset-normalizer` achieved a
confidence score of ≥ 0.85; the chokepoint cannot safely normalize the content.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Remediation**:
1. Open the file in a UTF-8-aware editor (e.g. VS Code, Vim `:set fileencoding=utf-8`) and re-save it.
2. Convert with `iconv`: `iconv -f <detected-encoding> -t utf-8 <file> > <file>.utf8 && mv <file>.utf8 <file>`.
3. Re-run with `--unsafe` to accept the highest-confidence candidate; `bypass_used=true` is recorded in `.encoding-provenance.jsonl`.

**Body example**:

```text
ERROR: CHARTER_ENCODING_AMBIGUOUS
  File: kitty-specs/my-mission/charter/charter.yaml
  Detected candidates:
    - cp1252 (confidence 0.62)
    - utf-8 with replacement (confidence 0.48)
  Mixed-content signal: the byte sequence cannot be decoded as strict UTF-8
  and no single encoding achieved >= 85% confidence.

  Remediation options:
    1. Open the file in a UTF-8-aware editor and re-save.
    2. iconv -f <detected-encoding> -t utf-8 <file> > <file>.utf8 && mv <file>.utf8 <file>.
    3. Re-run with --unsafe (logs bypass_used=true to provenance).
```

## CHARTER_ENCODING_NOT_NORMALIZED

**When it fires**: the charter file is successfully decoded but contains
byte-order marks or characters that indicate the content was not originally
saved as plain UTF-8 (e.g. a UTF-8-BOM file); normalization was applied
automatically and the operator may want to re-save the source file as plain
UTF-8.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Remediation**:
1. Re-save the file as UTF-8 without BOM in your editor.
2. Convert with `iconv`: `iconv -f utf-8-sig -t utf-8 <file> > <file>.utf8 && mv <file>.utf8 <file>`.
3. No action required if the content loaded correctly; this is an informational
   warning — the chokepoint normalized the content successfully.

**Body example**:

```text
WARNING: CHARTER_ENCODING_NOT_NORMALIZED
  File: kitty-specs/my-mission/charter/charter.yaml
  Detected encoding: utf-8-sig (confidence 1.00)
  Action: BOM stripped; content normalized to plain UTF-8.
  Recommendation: re-save the file as UTF-8 without BOM to avoid this message.
```

# Activation configuration codes

> **Source of truth**: `src/charter/activation/pack_context.py`
> (`ActiveCharterConfigError`, which carries the code as `exc.code`). Command
> boundaries read `exc.code`; they never spell the code string themselves.

## ACTIVE_CHARTER_CONFIG_INVALID

**When it fires**: the active charter configuration has an invalid shape. The
active charter configuration is `.kittify/config.yaml` or the `charter.yaml`
its `charter:` pointer names. Typical causes: invalid YAML, a root that is not
a mapping, a `charter:` pointer that names a missing file, or an activation
key with the wrong type. Raised by `mission create`, the `charter` commands
and the runtime prompt builders; with `--json` the code is the payload's
error code.

**Replaces**: the code this error carried before #3732 (ADR 2026-10-06-2
section 1; the changelog Before/After names it). No alias is accepted.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier. The payload shape is unchanged from the
code it replaces.

**Remediation**:
1. Fix the YAML shape in `.kittify/config.yaml` or the `charter.yaml` it points to.
2. Run `spec-kitty charter list --json` to confirm the configuration loads.
3. If the configuration cannot be repaired by hand, run `spec-kitty upgrade` to
   restore the default active charter shape.

**Body example**:

```text
Error (ACTIVE_CHARTER_CONFIG_INVALID): .kittify/config.yaml 'charter:' pointer names
/path/to/charter.yaml, which does not exist.
Remediation: fix .kittify/config.yaml (or the charter.yaml it points to) or run
`spec-kitty upgrade` to restore the default active charter shape.
```

# Governance resolution diagnostic codes

> **Source of truth**: `src/charter/activation/_diagnostics.py` (StrEnum class
> `GovernanceDiagnosticCode`, carried by the `GovernanceDiagnostic` value object).
> Every entry of `GovernanceResolution.diagnostics` has a `code` from this closed
> set and a human `message`. `charter context --json` (schema 1.4.0) renders
> each entry as `{"code": "<CODE>", "message": "<text>"}`. Consumers match on
> `code`; `message` is display text and may be reworded without notice. The set
> is closed per schema version: adding a code bumps the minor version of
> `context_schema_version`. These are informational notes, not errors:
> resolution still succeeds. `UNKNOWN_SELECTION_DROPPED` marks a dropped
> selection, and `spec-kitty agent status doctor` warns on it.

## UNKNOWN_SELECTION_DROPPED

**When it fires**: a selection in `charter.yaml` (`selected_directives` or
`selected_paradigms`) names an id that no layer knows (built-in, org packs or
`.kittify/charter-packs/`). The id is dropped and the rest of the resolution
stands. `spec-kitty doctor` warns on this code.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Example message**:

```text
Unknown selected directive 'NOPE_999' dropped: not found in built-in, org packs (charter_packs.org.packs) or .kittify/charter-packs/; see 'spec-kitty charter list'.
```

## CATALOG_DEFAULT_APPLIED

**When it fires**: the activation key for paradigms or directives is absent, so
the built-in catalog default is the base set.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Example message**:

```text
No activated paradigm set configured; using built-in catalog default (14 paradigms).
```

## FALLBACK_APPLIED

**When it fires**: the charter does not select `available_tools` (the runtime
tool registry is used) or a `template_set` (the fallback template set is used).

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Example message**:

```text
Template set not selected in charter; fallback 'software-dev-default' applied.
```

## SELECTION_MERGED

**When it fires**: a selection in `charter.yaml` or a project-local declaration is
unioned onto the base set: tools beyond the runtime registry, selected
directives or paradigms beyond the base (or all already present), and
project-local directives merged onto the resolved set (or all already present).

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Example message**:

```text
Charter selected 1 directive(s) beyond the activation base: QA_003.
```

## UNRESOLVED_REFERENCE

**When it fires**: profile-aware governance resolution
(`resolve_governance_for_profile`) follows a reference that resolves to no
artifact. It is part of the closed set, but `charter context` does not produce
it.

**JSON stability**: this code string is stable across minor releases; consumers
may match it as an opaque identifier.

**Example message**:

```text
Unresolved reference: directive/MISSING_DIRECTIVE
```
