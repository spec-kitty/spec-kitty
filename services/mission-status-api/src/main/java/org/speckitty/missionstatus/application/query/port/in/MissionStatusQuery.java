package org.speckitty.missionstatus.application.query.port.in;

import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;

/**
 * The inbound seam, and the only one the HTTP adapter depends on. The first three operations mirror the read port of the Python
 * side; {@link #subscribe} is the continuous form of {@link #changesSince}.
 */
public interface MissionStatusQuery {

  /** The project header. */
  ProjectHeader project();

  /** A page of Mission overviews in contract order. */
  MissionPage missions(PageRequest request);

  /** The forwarded rows after a cursor (none for a stream without one), and the cursor to resume from. */
  ChangeBatch changesSince(StreamScope scope, Optional<StreamCursor> cursor);

  /** A live stream. Every connect-time outcome is decided before it exists: it throws {@link StreamRefused} or {@link MissionStatusUnavailable}. */
  Subscription subscribe(StreamScope scope, Optional<StreamCursor> cursor);
}
