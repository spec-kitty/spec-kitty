package org.speckitty.missionstatus.application.query.port.in;

import java.util.List;
import org.speckitty.missionstatus.application.query.port.in.exceptions.ArtifactRefused;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactListing;

/** The inbound seam of the artifact reads ({@code listArtifacts}, {@code getArtifactContent}). Every refusal is an {@link ArtifactRefused}. */
public interface MissionArtifactQuery {

  /** The eligible files of the Mission, in byte order of the path, at most 1000. */
  ArtifactListing listArtifacts(String missionId);

  /**
   * The decoded and redacted text of one artifact. {@code paths} is every value of the {@code path} query parameter after the one
   * decoding the HTTP layer does; anything but exactly one valid path is {@code invalid_artifact_path}.
   */
  ArtifactContent readArtifact(String missionId, List<String> paths);
}
