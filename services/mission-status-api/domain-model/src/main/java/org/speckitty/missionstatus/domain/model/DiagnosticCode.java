package org.speckitty.missionstatus.domain.model;

import java.util.Locale;

/** The closed set of diagnostic codes. */
public enum DiagnosticCode {
  LEDGER_UNREADABLE,
  LEDGER_UNPARSEABLE,
  LEDGER_TORN_TAIL,
  META_UNPARSEABLE,
  MISSION_VANISHED,
  PATH_REFUSED,
  MISSION_DIR_UNREADABLE,
  PROJECTION_REFUSED,
  MISSION_ID_DUPLICATE;

  public String wire() {
    return name().toLowerCase(Locale.ROOT);
  }
}
