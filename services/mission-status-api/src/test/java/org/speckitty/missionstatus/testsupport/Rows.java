package org.speckitty.missionstatus.testsupport;

/** Text builders for {@code meta.json} and ledger rows, in the shape live spec-kitty writes them. */
public final class Rows {

  public static final String ALPHA_ID = "01J01000000000000000000001";
  public static final String BETA_ID = "01J02000000000000000000002";
  public static final String GAMMA_ID = "01J03000000000000000000003";

  private Rows() {}

  public static String meta(String missionId, String slug, String createdAt) {
    return "{\"created_at\":\"" + createdAt + "\",\"friendly_name\":\"Fixture " + slug + "\",\"mission_id\":\"" + missionId + "\",\"mission_number\":null,"
        + "\"mission_slug\":\"" + slug + "\",\"mission_type\":\"software-dev\",\"slug\":\"" + slug + "\",\"target_branch\":\"main\"}";
  }

  public static String metaWith(String missionId, String slug, String createdAt, String extraMembers) {
    String base = meta(missionId, slug, createdAt);
    return base.substring(0, base.length() - 1) + "," + extraMembers + "}";
  }

  /** One terminated lane-transition row. */
  public static String status(String eventId, String at, String wpId, String from, String to) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"event_id\":\"" + eventId + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,"
        + "\"from_lane\":\"" + from + "\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"" + to + "\",\"wp_id\":\"" + wpId + "\"}\n";
  }

  /** One terminated lifecycle row of the seven forwarded types. */
  public static String lifecycle(String eventId, String type, String at) {
    return "{\"event_id\":\"" + eventId + "\",\"event_type\":\"" + type + "\",\"timestamp\":\"" + at + "\"}\n";
  }

  /** One terminated annotation row for a work package. */
  public static String annotation(String eventId, String at, String wpId) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"delta\":{\"note\":\"hello\"},\"event_id\":\"" + eventId + "\",\"kind\":\"annotation\",\"wp_id\":\"" + wpId + "\"}\n";
  }

  /** A well-formed object that is a decision-point row: an unknown lifecycle type, which every consumer ignores. */
  public static String unknownType(String eventId) {
    return "{\"event_id\":\"" + eventId + "\",\"event_type\":\"DecisionPointOpened\",\"timestamp\":\"2026-09-01T10:00:00Z\"}\n";
  }

  /** The Nth event id (26 characters, ULID alphabet). */
  public static String id(int n) {
    return String.format("%026d", n);
  }
}
