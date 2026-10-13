package org.speckitty.missionstatus.testsupport;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

/** A clock that stays where it is until a test moves it. */
public final class MutableClock extends Clock {

  private Instant now;

  public MutableClock(Instant start) {
    this.now = start;
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
    return now;
  }
}
