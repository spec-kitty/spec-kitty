package org.speckitty.missionstatus.application.query.port.in;

import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;

/** The inbound port of the Mission detail: the overview, the five phases and a summary of each Work Package. */
public interface MissionDetailQuery {

  /**
   * The detail of one Mission.
   *
   * @throws DetailRefusal {@code NOT_FOUND} when no Mission has the id
   */
  MissionDetail mission(MissionId missionId);
}
