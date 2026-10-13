package org.speckitty.missionstatus.adapter.in.http.stream;

import java.util.List;

/** The contract's shared Problem, for the refusals the contract leaves to its {@code default} response. */
final class StreamRefusalContract {

  private StreamRefusalContract() {}

  static List<String> problem(String body) {
    return ValidatedEvents.contract().validateProblem(body);
  }
}
