package org.speckitty.missionstatus.testsupport;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Consumer;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.domain.model.Diagnostic;

/** The recording diagnostics consumer, the deterministic executor, the clock and (filesystem source) the allowlist recorder of one built fixture. */
public final class FixtureHandles {

  private final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  private final DeterministicExecutor executor = new DeterministicExecutor();
  private final MutableClock clock;
  private final RecordingAllowlistAccess allowlistRecorder;

  FixtureHandles(MutableClock clock) {
    this(clock, null);
  }

  FixtureHandles(MutableClock clock, RecordingAllowlistAccess allowlistRecorder) {
    this.clock = clock;
    this.allowlistRecorder = allowlistRecorder;
  }

  /** The recorder behind the filesystem adapter's file seam, when the factory was given one; null for the in-memory source. */
  public RecordingAllowlistAccess allowlistRecorder() {
    return allowlistRecorder;
  }

  public Consumer<Diagnostic> recorder() {
    return diagnostics::add;
  }

  /** The allowlist violations the recorder saw, as text (empty without a recorder); the conformance trees must not name adapter types. */
  public List<String> allowlistViolations() {
    return allowlistRecorder == null ? List.of() : allowlistRecorder.violations().stream().map(Object::toString).toList();
  }

  /** The number of file accesses the recorder saw (zero without a recorder). */
  public int allowlistAccessCount() {
    return allowlistRecorder == null ? 0 : allowlistRecorder.accesses().size();
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
