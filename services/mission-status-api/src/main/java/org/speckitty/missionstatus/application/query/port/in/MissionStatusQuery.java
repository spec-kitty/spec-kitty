package org.speckitty.missionstatus.application.query.port.in;

import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamCapacityReached;
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

  /** The projected events after a cursor (none for a stream without one), and the cursor to resume from. */
  StreamBatch changesSince(StreamScope scope, Optional<StreamCursor> cursor);

  /**
   * A live stream of projected events. Every connect-time outcome is decided before it exists: it throws {@link StreamCapacityReached}
   * (the one cap every adapter shares, checked first), {@link StreamRefused} or {@link MissionStatusUnavailable}.
   */
  Subscription subscribe(StreamScope scope, Optional<StreamCursor> cursor);

  /**
   * Ends every open subscription. Idempotent. This is the composition root's shutdown hook, not an adapter operation: a container's
   * graceful shutdown must not wait on streams that never finish. It has no default body so that an implementer cannot forget it.
   */
  void endStreams();
}
