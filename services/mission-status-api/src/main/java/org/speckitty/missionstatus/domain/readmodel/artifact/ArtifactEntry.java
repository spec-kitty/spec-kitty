package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Objects;

/** One artifact of a listing ({@code ArtifactEntry}). */
public record ArtifactEntry(String path, ArtifactKind kind, long sizeBytes, String modifiedAt, boolean readable) {

  public ArtifactEntry {
    Objects.requireNonNull(path, "path");
    Objects.requireNonNull(kind, "kind");
    Objects.requireNonNull(modifiedAt, "modifiedAt");
  }
}
