package org.speckitty.missionstatus.application.query.port.in.exceptions;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;

/**
 * The read cannot be served (the whole-read rows of the failure table, a projection refusal, and the connect-time rows of a stream).
 * It carries the diagnostic and nothing else: no path, no line text, no operating-system message.
 */
public final class MissionStatusUnavailable extends RuntimeException {

  private static final long serialVersionUID = 1L;

  private final transient Diagnostic diagnostic;

  public MissionStatusUnavailable(Diagnostic diagnostic) {
    super("mission status unavailable: " + Objects.requireNonNull(diagnostic, "diagnostic").code().wire());
    this.diagnostic = diagnostic;
  }

  public DiagnosticCode code() {
    return diagnostic.code();
  }

  public Diagnostic diagnostic() {
    return diagnostic;
  }
}
