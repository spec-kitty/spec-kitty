# Research: Issue-matrix reference over-matching

## R1 - Where the leading zero enters

- Decision: reject a leading zero in the canonical detector and route the other two number
  patterns through it.
- Rationale: the hand-off on #7808 found that three patterns accept a leading zero: the hash arm
  of the detector, the source-description lead and the closing keyword. Converging them removes
  two of the three copies, so the rule is written once.
- Alternatives considered: one leading-zero check per pattern (three copies of one rule;
  rejected as a second authority).

## R2 - Colour exclusion form

- Decision: CSS declaration form only (a colour-bearing property name or `--custom-prop`, then a
  colon, then the value).
- Rationale: a keyword-anywhere filter would silently drop a real 4-digit reference on a line that
  also says "colour", and a 4-digit `#RGBA` value is indistinguishable from an issue. The
  leading-zero rule alone misses all-digit colours without a leading zero (six repeated digit
  pairs, for example).
- Alternatives considered: a six-digit cap (would drop real references in large repositories);
  a keyword filter (fail-open).

## R3 - Commit citation window

- Decision: a backticked 7-40 hex token with at least one letter `a-f`, within 16 characters of
  the citation on either side.
- Rationale: the reported shape is a parenthesised, backticked short SHA, then a comma and the
  citation. Requiring a letter keeps an all-digit backticked number gating (fail-safe), at the
  cost of missing a rare all-digit SHA.
- Alternatives considered: line-scoped SHA detection (would demote unrelated targets on the same
  line, the #7011 failure class).

## R4 - Scope rule representation

- Decision: a defaulted `in_gating_scope` flag on `Occurrence`, set by discovery and read only by
  `classify_occurrence`.
- Rationale: basenames alone cannot tell `tasks/` from `contracts/`. Discovery already knows the
  path, and the classifier stays the one authority. A trailing default keeps positional
  construction unchanged.
- Alternatives considered: a new `GatingClass.CITED` value (changes the persisted vocabulary and
  scaffold verdicts; rejected by C-001); deciding scope in discovery without the classifier (a
  second gating authority).
