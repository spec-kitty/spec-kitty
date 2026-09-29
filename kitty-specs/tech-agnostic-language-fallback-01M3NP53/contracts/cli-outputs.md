# CLI output contracts — tech-agnostic-language-fallback-01M3NP53

## spec-kitty review — dead-code not applicable
Console (shape, wording finalised in implementation; tests assert the stable parts in **bold**):
```
  ⚠  Dead-code scan: **not applicable** (**MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE**)
       reason: changed source set contains no files the dead-code scan supports (unsupported: **.go, .zig**)
       remediation: <tech-agnostic: extend your local charter with tech-specific review guidance and your own analyzer/test command>
```
- Must NOT contain `.py` as unsupported, `src/`, `pytest`, or "create a Python file".
- Report: gate `dead_code` result `skip`; finding type `dead_code_not_applicable`; verdict `pass_with_notes`; rc 0; never "0 unreferenced".

## spec-kitty review — missing pytest
```
  ⚠  MISSION_REVIEW_TEST_EXTRA_MISSING: <installation note + remediation>   (review continues)
```

## charter generate — unregistered tool
```
available_tools: 'zig' is not a registered tool id; ignored (tool ids are validated separately from project languages)
```

## charter context — unknown language
- compact: `  - Languages: unknown` followed by the single advisory line.
- bootstrap: the single advisory line; no Languages line requirement.
- Advisory (single constant): states no specialist guidance exists for the project's language and to add tech-specific guidelines to the local charter, naming the how-to "Extend your charter for an unsupported language".
