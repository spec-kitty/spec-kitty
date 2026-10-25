package org.speckitty.missionstatus.domain.model;

/** The unterminated tail of a ledger: none, whitespace only, or non-whitespace (which refuses the read). */
public enum TailClassification {
  NONE,
  WHITESPACE,
  NON_WHITESPACE
}
