package org.speckitty.missionstatus.domain.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * The members of a current-shape {@code lanes.json} (the {@code mission_slug} form) that a Work Package detail needs: the Mission slug
 * the lane branch names are built from, the Mission id when it is stored, and each lane with its Work Package ids.
 */
public record LanesManifest(String missionSlug, String missionId, List<Lane> lanes) {

  /** One execution lane: its id and the Work Package ids it holds, in the stored order. */
  public record Lane(String laneId, List<String> wpIds) {
    public Lane {
      Objects.requireNonNull(laneId, "laneId");
      wpIds = List.copyOf(wpIds);
    }
  }

  public LanesManifest {
    Objects.requireNonNull(missionSlug, "missionSlug");
    lanes = List.copyOf(lanes);
  }

  /** The first lane that holds the Work Package ({@code LanesManifest.lane_for_wp}). */
  public Optional<Lane> laneFor(String wpId) {
    return lanes.stream().filter(lane -> lane.wpIds().contains(wpId)).findFirst();
  }
}
