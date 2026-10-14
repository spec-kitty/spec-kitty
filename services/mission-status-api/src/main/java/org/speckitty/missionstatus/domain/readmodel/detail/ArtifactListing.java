package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.MissionId;

/**
 * The artifacts of a Mission, at most {@value #MAX_ENTRIES}.
 *
 * @param truncated true exactly when more eligible artifacts exist than the entries carry
 */
public record ArtifactListing(MissionId missionId, List<ArtifactEntry> entries, boolean truncated) {

  public static final int MAX_ENTRIES = 1000;

  public ArtifactListing {
    Objects.requireNonNull(missionId, "missionId");
    Objects.requireNonNull(entries, "entries");
    entries = List.copyOf(entries);
    if (entries.size() > MAX_ENTRIES) {
      throw new IllegalArgumentException("too many entries");
    }
  }
}
