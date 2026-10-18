package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.List;
import java.util.Objects;

/** The artifacts of one Mission ({@code ArtifactListing}): at most {@link #MAX_ENTRIES} entries in byte order of the path. */
public record ArtifactListing(String missionId, List<ArtifactEntry> entries, boolean truncated) {

  /** The most entries a listing returns. */
  public static final int MAX_ENTRIES = 1000;

  public ArtifactListing {
    Objects.requireNonNull(missionId, "missionId");
    entries = List.copyOf(entries);
  }
}
