package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * FR-011 / AC-11a, the stream leg (SC-003): the data of every event received over the real socket validates against the schema of its
 * event name in {@code paths/events.yaml}. The floor: at least one event of each of the three names was validated (zero validated fails,
 * so a suite that stopped calling the validator cannot pass). The control: one added unknown property fails the same validation.
 */
class EventDataContractTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  @Test
  void everyEventNameIsReceivedOverTheSocketAndItsDataValidatesAgainstItsSchema() {
    ValidatedEvents.reset();
    String history = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
    try (StreamRig rig = StreamRig.of(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, history)));
        SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress") + Rows.lifecycle(Rows.id(3), "TasksCompleted", "2026-09-01T10:02:00Z"));
      rig.tick();
      List<SseClient.Event> events = client.events(2, BOUND);
      events.forEach(ValidatedEvents::valid);

      rig.replace("alpha", history);
      rig.tick();
      ValidatedEvents.valid(client.nextEvent(BOUND));
    }

    assertThat(ValidatedEvents.count("status-transition")).as("status-transition events validated").isPositive();
    assertThat(ValidatedEvents.count("mission-lifecycle")).as("mission-lifecycle events validated").isPositive();
    assertThat(ValidatedEvents.count("log-truncated")).as("log-truncated events validated").isPositive();
  }

  @Test
  void controlAnEventWithOneAddedUnknownPropertyFailsTheValidation() {
    String history = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
    try (StreamRig rig = StreamRig.of(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, history)));
        SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress") + Rows.lifecycle(Rows.id(3), "TasksCompleted", "2026-09-01T10:02:00Z"));
      rig.tick();
      rig.replace("alpha", history);
      rig.tick();
      List<SseClient.Event> events = client.events(3, BOUND);
      assertThat(events).extracting(SseClient.Event::name).containsExactly("status-transition", "mission-lifecycle", "log-truncated");

      for (SseClient.Event event : events) {
        assertThat(ValidatedEvents.contract().validateEventData(event.name(), event.data())).as(event.name() + " as received").isEmpty();
        ObjectNode withExtra = (ObjectNode) JSON.readTree(event.data());
        withExtra.put("unexpected", true);
        assertThat(ValidatedEvents.contract().validateEventData(event.name(), JSON.writeValueAsString(withExtra))).as(event.name() + " with one more property").isNotEmpty();
      }
    }
  }

  @Test
  void controlAnEventNameOutsideTheThreeIsNotValidated() {
    assertThat(org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator.EVENT_NAMES).containsExactly("status-transition", "mission-lifecycle", "log-truncated");
  }
}
