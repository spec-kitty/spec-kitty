package org.speckitty.missionstatus.domain.model;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The status lanes. The nine display lanes are the contract's {@code StatusLane} values, in the contract's order. {@code genesis}
 * and {@code uninitialized} are the runtime's two non-display values: live logs carry {@code from_lane: genesis} and the Python
 * parser accepts both, so they are known here but are never counted (decision DD-78).
 */
public enum Lane {
  GENESIS("genesis", false),
  UNINITIALIZED("uninitialized", false),
  PLANNED("planned", true),
  CLAIMED("claimed", true),
  IN_PROGRESS("in_progress", true),
  FOR_REVIEW("for_review", true),
  IN_REVIEW("in_review", true),
  APPROVED("approved", true),
  DONE("done", true),
  BLOCKED("blocked", true),
  CANCELED("canceled", true);

  private static final Map<String, Lane> BY_WIRE = new HashMap<>();
  private static final List<Lane> DISPLAY;

  static {
    for (Lane lane : values()) {
      BY_WIRE.put(lane.wire, lane);
    }
    DISPLAY = List.of(values()).stream().filter(Lane::isDisplay).toList();
  }

  private final String wire;
  private final boolean display;

  Lane(String wire, boolean display) {
    this.wire = wire;
    this.display = display;
  }

  public String wire() {
    return wire;
  }

  public boolean isDisplay() {
    return display;
  }

  /** The nine display lanes in the contract's order. */
  public static List<Lane> displayLanes() {
    return DISPLAY;
  }

  /** An unknown lane (or null) is malformed input, never a default. */
  public static Lane fromWire(String value) {
    Lane lane = BY_WIRE.get(value);
    if (lane == null) {
      throw new IllegalArgumentException("unknown lane");
    }
    return lane;
  }
}
