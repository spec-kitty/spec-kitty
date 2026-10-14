package org.speckitty.missionstatus.architecture.fixture.application.query;

import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.OverviewDeriver;

/**
 * Architecture-rule fixture: a planted bypass of the head projection. A class of {@code application.query} other than the reader and the
 * projection derives a Mission head itself. Never executed; only its call sites are read.
 */
public final class HeadBypass {
  public MissionOverview deriveItself() {
    return OverviewDeriver.derive(null, null, null);
  }
}
