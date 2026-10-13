package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * The members of a Mission's {@code meta.json} the overview needs. The text members are served as stored; an empty optional date
 * reads as absent, as the oracle's {@code _optional_text} does. {@code topology} is {@code UNKNOWN} when none is stored.
 */
public record MissionMeta(
    MissionId missionId,
    String slug,
    String friendlyName,
    Integer displayNumber,
    String missionType,
    String targetBranch,
    Topology topology,
    String createdAt,
    String acceptedAt,
    String mergedAt,
    String discardedAt,
    boolean hasBaseline) {

  public MissionMeta {
    Objects.requireNonNull(missionId, "missionId");
    Objects.requireNonNull(slug, "slug");
    Objects.requireNonNull(targetBranch, "targetBranch");
    Objects.requireNonNull(topology, "topology");
    Objects.requireNonNull(createdAt, "createdAt");
    acceptedAt = PyText.nullIfEmpty(acceptedAt);
    mergedAt = PyText.nullIfEmpty(mergedAt);
    discardedAt = PyText.nullIfEmpty(discardedAt);
  }
}
