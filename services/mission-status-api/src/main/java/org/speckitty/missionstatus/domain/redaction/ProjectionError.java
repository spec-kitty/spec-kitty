package org.speckitty.missionstatus.domain.redaction;

import java.util.Objects;

/**
 * A real value cannot be projected into the contract. It carries the field name and a fixed reason only, never the value, a path or
 * any text of the ledger.
 */
public final class ProjectionError extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** Why the value was refused; the detail text is fixed and holds no data. */
  public enum Reason {
    MISSING("a required strict field is missing"),
    NOT_REPRESENTABLE("a strict field holds a value that is not representable"),
    LEAK_REMAINS("redaction left a leak in a human text field");

    private final String detail;

    Reason(String detail) {
      this.detail = detail;
    }

    public String detail() {
      return detail;
    }
  }

  private final String fieldName;
  private final Reason reason;

  public ProjectionError(String fieldName, Reason reason) {
    super(Objects.requireNonNull(fieldName, "fieldName") + ": " + Objects.requireNonNull(reason, "reason").detail());
    this.fieldName = fieldName;
    this.reason = reason;
  }

  public String fieldName() {
    return fieldName;
  }

  public Reason reason() {
    return reason;
  }
}
