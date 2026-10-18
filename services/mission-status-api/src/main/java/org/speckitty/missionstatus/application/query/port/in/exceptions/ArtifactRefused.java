package org.speckitty.missionstatus.application.query.port.in.exceptions;

import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactRefusalCode;

/** An artifact read refused with one of the contract's seven codes. It carries the code only: never a path, a directory or content. */
public final class ArtifactRefused extends RuntimeException {

  private static final long serialVersionUID = 1L;

  private final ArtifactRefusalCode code;

  public ArtifactRefused(ArtifactRefusalCode code) {
    super(Objects.requireNonNull(code, "code").wire(), null, false, false);
    this.code = code;
  }

  public ArtifactRefusalCode code() {
    return code;
  }
}
