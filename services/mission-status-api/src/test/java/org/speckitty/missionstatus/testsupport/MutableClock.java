package org.speckitty.missionstatus.testsupport;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

/** A clock that stays where it is until a test moves it. */
public final class MutableClock extends Clock {

  private Instant now;
  private RuntimeException nextFailure;

  public MutableClock(Instant start) {
    this.now = start;
  }

  /** The next read of the clock throws {@code failure} once: a fault nobody anticipated, inside a periodic task. */
  public void failNextRead(RuntimeException failure) {
    this.nextFailure = failure;
  }

  public void advance(Duration by) {
    now = now.plus(by);
  }

  @Override
  public ZoneId getZone() {
    return ZoneOffset.UTC;
  }

  @Override
  public Clock withZone(ZoneId zone) {
    return this;
  }

  @Override
  public Instant instant() {
    if (nextFailure != null) {
      RuntimeException failure = nextFailure;
      nextFailure = null;
      throw failure;
    }
    return now;
  }
}
