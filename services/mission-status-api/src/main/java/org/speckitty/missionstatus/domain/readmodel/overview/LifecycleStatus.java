package org.speckitty.missionstatus.domain.readmodel.overview;

import java.util.Locale;

/** The five lifecycle values of the contract. */
public enum LifecycleStatus {
  ACTIVE,
  PLANNED,
  DONE,
  DRAFT,
  DISCARDED;

  public String wire() {
    return name().toLowerCase(Locale.ROOT);
  }
}
