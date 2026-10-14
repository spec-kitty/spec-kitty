package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;

/** A reference to one artifact of the Mission: its path relative to the Mission directory and its kind. */
public record ArtifactReference(String path, ArtifactKind kind) {

  public ArtifactReference {
    Objects.requireNonNull(path, "path");
    Objects.requireNonNull(kind, "kind");
  }
}
