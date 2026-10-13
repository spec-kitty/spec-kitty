package org.speckitty.missionstatus.testsupport;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Consumer;
import org.speckitty.missionstatus.domain.model.Diagnostic;

/** The recording diagnostics consumer, the deterministic executor and the clock of one built fixture. */
public final class FixtureHandles {

  private final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  private final DeterministicExecutor executor = new DeterministicExecutor();
  private final MutableClock clock;

  FixtureHandles(MutableClock clock) {
    this.clock = clock;
  }

  public Consumer<Diagnostic> recorder() {
    return diagnostics::add;
  }

  public List<Diagnostic> diagnostics() {
    return List.copyOf(diagnostics);
  }

  public DeterministicExecutor executor() {
    return executor;
  }

  public MutableClock clock() {
    return clock;
  }
}
