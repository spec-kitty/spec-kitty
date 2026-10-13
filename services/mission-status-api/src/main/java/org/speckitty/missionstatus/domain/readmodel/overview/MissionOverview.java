package org.speckitty.missionstatus.domain.readmodel.overview;

import java.util.Map;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.Topology;

/**
 * One Mission overview, member names as the contract's {@code MissionOverview}. Human text ({@code friendlyName},
 * {@code nextAction}) is NOT yet projected: redaction is the projection component's job.
 */
public record MissionOverview(
    MissionId missionId,
    String mid8,
    String slug,
    String friendlyName,
    Integer displayNumber,
    String missionType,
    String targetBranch,
    Topology topology,
    String createdAt,
    Map<Lane, Integer> statusLaneCounts,
    int wpTotal,
    int blockedCount,
    Progress progress,
    LifecycleStatus lifecycleStatus,
    String acceptedAt,
    String mergedAt,
    String discardedAt,
    String lastEventId,
    String lastActivityAt,
    int eventCount,
    StreamCursor streamCursor,
    String nextAction) {}
