package org.speckitty.missionstatus.application.query.port.in.dto;

/** Why a Mission-scoped stream ends (rows S3 to S5 of the stream table, and the overflow of a slow consumer). */
public enum Closure {
  LEDGER_UNREADABLE,
  LEDGER_UNPARSEABLE,
  MISSION_VANISHED,
  SLOW_CONSUMER;

  /** The stable name, in the style of the diagnostic codes. */
  public String wire() {
    return name().toLowerCase(java.util.Locale.ROOT);
  }
}
