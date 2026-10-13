package org.speckitty.missionstatus.domain.readmodel.overview;

/** Whether the project's schema is one the serving build supports. */
public enum Health {
  HEALTHY("healthy"),
  SCHEMA_DRIFT("schema_drift");

  private final String wire;

  Health(String wire) {
    this.wire = wire;
  }

  public String wire() {
    return wire;
  }
}
