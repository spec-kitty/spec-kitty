package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.testsupport.http.SseClient;

/**
 * FR-011 / AC-11a, the stream leg: the data of every event the suites receive over the real socket is validated against the schema of
 * its event name in the contract (the one {@link ContractValidator}, not a second one). The count per name is the floor the floor test
 * reads: an event that was never validated is not counted.
 */
final class ValidatedEvents {

  private static final ContractValidator CONTRACT = ContractValidator.fromClasspath();
  private static final Map<String, AtomicInteger> VALIDATED = new ConcurrentHashMap<>();

  private ValidatedEvents() {}

  /** Validates the event's data against the schema of its name and returns the event. */
  static SseClient.Event valid(SseClient.Event event) {
    assertThat(event).as("an event arrived").isNotNull();
    assertThat(ContractValidator.EVENT_NAMES).as("a contract event name").contains(event.name());
    List<String> errors = check(event);
    assertThat(errors).as("the data of " + event.name() + " validates against the contract").isEmpty();
    return event;
  }

  /** The validation call itself; an event is counted only by passing through it. */
  private static List<String> check(SseClient.Event event) {
    VALIDATED.computeIfAbsent(event.name(), key -> new AtomicInteger()).incrementAndGet();
    return CONTRACT.validateEventData(event.name(), event.data());
  }

  static int count(String eventName) {
    AtomicInteger count = VALIDATED.get(eventName);
    return count == null ? 0 : count.get();
  }

  static void reset() {
    VALIDATED.clear();
  }

  static ContractValidator contract() {
    return CONTRACT;
  }
}
