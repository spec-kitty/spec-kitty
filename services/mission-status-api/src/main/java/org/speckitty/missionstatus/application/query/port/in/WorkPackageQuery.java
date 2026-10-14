package org.speckitty.missionstatus.application.query.port.in;

import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;

/** The inbound port of one Work Package of a Mission, optionally with its prompt. */
public interface WorkPackageQuery {

  /**
   * One Work Package.
   *
   * @param includePrompt whether the prompt text is read and carried in {@code promptMarkdown}
   * @throws DetailRefusal {@code NOT_FOUND} when the Mission or the Work Package does not exist
   */
  WorkPackageView workPackage(MissionId missionId, WpId wpId, boolean includePrompt);
}
