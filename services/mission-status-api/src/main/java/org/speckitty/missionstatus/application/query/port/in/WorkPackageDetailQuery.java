package org.speckitty.missionstatus.application.query.port.in;

import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;

/** The inbound port of the extended detail of one Work Package: subtasks, dependencies, review cycles, workspace and owned files. */
public interface WorkPackageDetailQuery {

  /**
   * The detail of one Work Package.
   *
   * @throws DetailRefusal {@code NOT_FOUND} or {@code SOURCE_UNREADABLE}
   */
  WorkPackageDetail workPackageDetail(MissionId missionId, WpId wpId);
}
