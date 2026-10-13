package org.speckitty.missionstatus.domain.readmodel.paging;

import java.util.Comparator;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;

/** The listing order: {@code createdAt} descending as an instant, ties by {@code missionId} ascending as text. */
public final class MissionOrder {

  public static final Comparator<MissionOverview> COMPARATOR =
      Comparator.comparing((MissionOverview o) -> Instants.parse(o.createdAt()), Comparator.reverseOrder())
          .thenComparing(o -> o.missionId().value(), CodePoints::compare);

  private MissionOrder() {}
}
