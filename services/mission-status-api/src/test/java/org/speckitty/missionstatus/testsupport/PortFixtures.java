package org.speckitty.missionstatus.testsupport;

import static org.speckitty.missionstatus.testsupport.Rows.id;

import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.MissionId;

/**
 * Hand-built, source-neutral fixtures of the port-level subset, and the helpers that open them through {@link PortSourceSelector}.
 * Nothing here names a source: {@link FixtureSpec} is realised by whichever factory the selector currently holds.
 *
 * <p>The two interleaved Missions carry the expected values of the Python oracle (each was reduced there with
 * {@code materialize_snapshot} and {@code compute_weighted_progress}, and the ledger bytes were checked by the offset and the SHA-256
 * of the last line of {@code poll_once}); those numbers are written into the tests that use these fixtures.
 */
public final class PortFixtures {

  public static final MissionId ALPHA = new MissionId(Rows.ALPHA_ID);
  public static final MissionId BETA = new MissionId(Rows.BETA_ID);
  public static final String CREATED = "2026-09-02T10:00:00+00:00";

  private PortFixtures() {}

  /** A Mission as a test knows it: the slug, the id and the {@code created_at} text it wrote into the fixture. */
  public record Planted(String slug, String missionId, String createdAt) {}

  /** The Mission id of the Nth generated Mission (26 characters of the ULID alphabet). */
  public static String missionId(int n) {
    return String.format("01J0%022d", n);
  }

  public static FixtureSpec.Mission mission(String slug, String missionId, String createdAt, String ledger) {
    return FixtureSpec.Mission.of(slug, Rows.meta(missionId, slug, createdAt), ledger);
  }

  /**
   * "interleaved-alpha": equal {@code at} with different event ids, file order that differs from {@code (at, event_id)} order, a duplicated
   * event id whose second row says something else, an offset {@code at} whose text order differs from its instant order, and two
   * fractional-second lengths whose text order differs from their instant order.
   */
  public static String alphaLedger() {
    return Rows.status(id(8), "2026-09-01T10:00:00Z", "WP01", "planned", "blocked")
        + Rows.status(id(7), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")
        + Rows.status(id(9), "2026-09-01T12:00:00+02:00", "WP02", "planned", "claimed")
        + Rows.status(id(10), "2026-09-01T10:30:00Z", "WP03", "planned", "claimed")
        + Rows.status(id(12), "2026-09-01T11:00:00.12345Z", "WP05", "planned", "claimed")
        + Rows.status(id(11), "2026-09-01T11:00:00.123456Z", "WP04", "planned", "claimed")
        + Rows.status(id(12), "2026-09-01T11:00:00.12345Z", "WP05", "claimed", "in_progress");
  }

  /** "interleaved-beta": rows whose {@code at} order is not their event-id order, so {@code at} decides before the id does. */
  public static String betaLedger() {
    return Rows.status(id(21), "2026-09-01T09:00:00Z", "WP01", "planned", "claimed")
        + Rows.status(id(23), "2026-09-01T09:10:00Z", "WP01", "claimed", "in_progress")
        + Rows.status(id(22), "2026-09-01T09:20:00Z", "WP01", "in_progress", "for_review")
        + Rows.status(id(24), "2026-09-01T09:30:00Z", "WP02", "planned", "claimed")
        + Rows.status(id(26), "2026-09-01T09:40:00Z", "WP02", "claimed", "in_progress")
        + Rows.status(id(25), "2026-09-01T09:05:00Z", "WP02", "planned", "claimed");
  }

  public static FixtureSpec interleavedPair() {
    return FixtureSpec.of(
        mission("interleaved-alpha", Rows.ALPHA_ID, CREATED, alphaLedger()),
        mission("interleaved-beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", betaLedger()));
  }

  /** The inbound port over {@code spec}, from whichever source the selector currently holds. */
  public static MissionStatusQuery open(FixtureSpec spec) {
    return PortSourceSelector.open(spec).query();
  }
}
