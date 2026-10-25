package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/** One diagnostic occurrence. It never carries a path, line text or an OS message. {@code line} may be null. */
public record Diagnostic(DiagnosticCode code, String mid8, Integer line) {

  /** The mid8 of a diagnostic that is not about one Mission. */
  public static final String NONE = "none";

  public Diagnostic {
    Objects.requireNonNull(code, "code");
    Objects.requireNonNull(mid8, "mid8");
  }
}
