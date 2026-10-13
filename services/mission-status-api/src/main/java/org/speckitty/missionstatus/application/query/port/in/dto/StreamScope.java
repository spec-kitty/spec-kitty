package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.MissionId;

/** Which Missions a change stream carries. */
public sealed interface StreamScope {

  /** Every Mission, live only. */
  record All() implements StreamScope {}

  /** One Mission, by its ULID. */
  record OneMission(MissionId missionId) implements StreamScope {

    public OneMission {
      Objects.requireNonNull(missionId, "missionId");
    }
  }

  static StreamScope all() {
    return new All();
  }

  static StreamScope mission(MissionId missionId) {
    return new OneMission(missionId);
  }
}
