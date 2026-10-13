package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Landing fold R-7: a served date-time field needs an offset (RFC 3339, the contract's {@code format: date-time}). A value without one is
 * served as null (a Mission date, {@code lastActivityAt}) or drops the stream event ({@code at}), each with a {@code projection_refused}
 * diagnostic, as a value that is no instant at all is (J6, J7). Comparison keeps the lenient reading (an offset-less value is UTC).
 */
@ExtendWith(OutputCaptureExtension.class)
class ServedInstantsTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final ContractValidator CONTRACT = ContractValidator.fromClasspath();
  private static final String MID8 = Rows.ALPHA_ID.substring(0, 8);

  private static FixtureSpec offsetLessMission() {
    String meta = Rows.metaWith(Rows.ALPHA_ID, "alpha", PortFixtures.CREATED, "\"accepted_at\":\"2026-09-02T10:00:00\",\"merged_at\":\"2026-09-03T10:00:00+00:00\",\"discarded_at\":\"2026-09-04T10:00:00\"");
    return FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, Rows.status(Rows.id(1), "2026-09-01T10:00:00", "WP01", "planned", "claimed")));
  }

  @Test
  void anOffsetLessMissionDateAndAnOffsetLessLastActivityAreServedAsNullAndTheBodiesValidate() throws Exception {
    try (StreamRig rig = StreamRig.of(offsetLessMission())) {
      var missions = rig.http.get("/api/v1/missions");
      var project = rig.http.get("/api/v1/project");
      assertThat(missions.status()).isEqualTo(200);
      JsonNode item = JSON.readTree(missions.text()).get("items").get(0);
      assertThat(item.get("acceptedAt").isNull()).as("offset-less accepted_at").isTrue();
      assertThat(item.get("discardedAt").isNull()).as("offset-less discarded_at").isTrue();
      assertThat(item.get("mergedAt").asString()).as("a date with an offset is served as written").isEqualTo("2026-09-03T10:00:00+00:00");
      assertThat(item.get("lastActivityAt").isNull()).as("offset-less last transition").isTrue();
      assertThat(item.get("lifecycleStatus").asString()).as("a nulled discarded_at cannot discard the Mission").isEqualTo("active");
      assertThat(CONTRACT.validateMissions(missions.text())).isEmpty();
      assertThat(project.status()).isEqualTo(200);
      assertThat(JSON.readTree(project.text()).get("lastActivityAt").isNull()).isTrue();
      assertThat(CONTRACT.validateProject(project.text())).isEmpty();
      assertThat(rig.diagnostics(DiagnosticCode.PROJECTION_REFUSED)).isNotEmpty().allSatisfy(d -> assertThat(d.mid8()).isEqualTo(MID8));
    }
  }

  @Test
  void anOffsetLessAtDropsTheStreamEventWithOneDiagnosticAndTheNextEventIsDelivered(CapturedOutput output) throws Exception {
    FixtureSpec spec = FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
    try (StreamRig rig = StreamRig.of(spec);
        SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T11:00:00", "WP01", "claimed", "in_progress"));
      rig.append("alpha", Rows.status(Rows.id(3), "2026-09-01T12:00:00Z", "WP01", "in_progress", "for_review"));
      rig.tick();

      SseClient.Event only = client.nextEvent(StreamRig.BOUND);
      assertThat(only.data()).contains(Rows.id(3));
      assertThat(client.next(StreamRig.QUIET)).isNull();
      assertThat(output.getAll().split("code=projection_refused mid8=" + MID8, -1)).as("one diagnostic for the dropped event").hasSize(2);
    }
  }
}
