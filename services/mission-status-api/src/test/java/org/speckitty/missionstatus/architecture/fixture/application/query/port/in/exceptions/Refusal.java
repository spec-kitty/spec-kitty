package org.speckitty.missionstatus.architecture.fixture.application.query.port.in.exceptions;

/** Architecture-rule fixture, conforming: an exception holding a nested enum, judged by its outermost class. */
public final class Refusal extends RuntimeException {
  public enum Kind {
    ONE,
    TWO
  }

  private final Kind kind;

  public Refusal(Kind kind) {
    this.kind = kind;
  }

  public Kind kind() {
    return kind;
  }
}
