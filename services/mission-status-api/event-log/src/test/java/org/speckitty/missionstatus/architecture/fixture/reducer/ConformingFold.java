package org.speckitty.missionstatus.architecture.fixture.reducer;

import java.util.Comparator;
import java.util.List;

/** Positive control: a fold that uses only the rule 1b JDK packages. */
public final class ConformingFold {

  private ConformingFold() {}

  public static List<String> ordered(List<String> events) {
    return events.stream().sorted(Comparator.naturalOrder()).toList();
  }
}
