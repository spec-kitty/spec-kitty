package org.speckitty.missionstatus.testsupport;

import java.util.function.Function;

/**
 * The one place that decides which source backs a port-level class. Port-level classes never construct a factory: they ask for a
 * {@link Fixture} over a {@link FixtureSpec}. The default is the in-memory {@link FixtureFactory}; a launcher may install an override
 * (the filesystem leg of a later work package) and must restore it afterwards.
 */
public final class PortSourceSelector {

  private static final Function<FixtureSpec, Fixture> IN_MEMORY = FixtureFactory::build;
  private static volatile Function<FixtureSpec, Fixture> slot = IN_MEMORY;

  private PortSourceSelector() {}

  public static Fixture open(FixtureSpec spec) {
    return slot.apply(spec);
  }

  /** Installs an override; closing the returned handle restores whatever was installed before. */
  public static AutoCloseable override(Function<FixtureSpec, Fixture> factory) {
    Function<FixtureSpec, Fixture> previous = slot;
    slot = factory;
    return () -> slot = previous;
  }

  /** True while the default (in-memory) source is selected. */
  public static boolean isDefault() {
    return slot == IN_MEMORY;
  }
}
