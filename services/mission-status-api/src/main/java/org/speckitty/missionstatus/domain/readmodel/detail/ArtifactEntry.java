package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;

/**
 * One entry of the artifact listing.
 *
 * @param modifiedAt UTC with a {@code Z} suffix and whole seconds, as served
 * @param readable whether a content read would be served
 */
public record ArtifactEntry(String path, ArtifactKind kind, long sizeBytes, String modifiedAt, boolean readable) {

  public ArtifactEntry {
    Objects.requireNonNull(path, "path");
    Objects.requireNonNull(kind, "kind");
    Objects.requireNonNull(modifiedAt, "modifiedAt");
    if (sizeBytes < 0) {
      throw new IllegalArgumentException("size is not negative");
    }
  }
}
