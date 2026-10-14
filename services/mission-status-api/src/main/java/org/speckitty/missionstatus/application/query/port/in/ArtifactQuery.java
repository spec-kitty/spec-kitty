package org.speckitty.missionstatus.application.query.port.in;

import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;

/** The inbound port of the artifacts of a Mission: the listing and the text of one artifact. */
public interface ArtifactQuery {

  /**
   * The artifact listing of a Mission.
   *
   * @throws DetailRefusal {@code NOT_FOUND} or {@code ARTIFACT_LISTING_UNREADABLE}
   */
  ArtifactListing list(MissionId missionId);

  /**
   * The text of one artifact.
   *
   * @param path the decoded {@code path} values of the request, or the fact that they could not be decoded
   * @throws DetailRefusal one of the artifact kinds of refusal
   */
  ArtifactContent content(MissionId missionId, ArtifactPathInput path);
}
