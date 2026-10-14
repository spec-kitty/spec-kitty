package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.Objects;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
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

  /**
   * The scope a request names: no Mission id is every Mission, a ULID is that Mission, and anything else is an unknown Mission (the
   * refusal the contract fixes for a Mission id that cannot be a Mission).
   */
  static StreamScope parse(String missionIdOrNull) {
    if (missionIdOrNull == null) {
      return all();
    }
    try {
      return mission(new MissionId(missionIdOrNull));
    } catch (IllegalArgumentException notAUlid) {
      throw new StreamRefused(StreamRefused.Kind.UNKNOWN_MISSION);
    }
  }
}
