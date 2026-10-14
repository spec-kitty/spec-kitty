package org.speckitty.missionstatus.domain.model;

/**
 * The resolved assignment of a Work Package (contract {@code Assignment}): seven nullable handles read from the status snapshot. The
 * resolver sentinels ({@code __resolved_model_absent__} and its profile, profile-version and provider siblings) read as null, never as their
 * text (AC-20.1), and so does any value that does not fit the contract's handle shape. Both rules are {@link Actor}'s (the single
 * authority for the handle shape and the sentinel set): an {@code Assignment} holds the value of the slot as {@code Actor.ofText} shows it.
 */
public record Assignment(String agent, String assignee, String role, String agentProfile, String agentProfileVersion, String model, String provider) {

  /** A Work Package with no events: every handle null. */
  public static final Assignment EMPTY = new Assignment(null, null, null, null, null, null, null);

  public Assignment {
    agent = handle(agent);
    assignee = handle(assignee);
    role = handle(role);
    agentProfile = handle(agentProfile);
    agentProfileVersion = handle(agentProfileVersion);
    model = handle(model);
    provider = handle(provider);
  }

  private static String handle(String value) {
    return value == null ? null : Actor.ofText(value).tool();
  }
}
