package org.speckitty.missionstatus.testsupport;

import java.util.function.Supplier;

/**
 * The request-scoped route marker a harness installs on the recording seam ({@code RecordingAllowlistAccess#routeSupplier}), so that
 * every access the recorder notes carries the route of the request that caused it. The HTTP server answers on another thread than the
 * test, so the holder is one volatile field and never a {@link ThreadLocal}: the value a test sets is the value the server thread reads.
 * It names no route class; a route is a plain string such as {@code getMission}.
 */
public final class RouteMarker {

  /** What the recorder notes when no route is set. */
  public static final String NO_ROUTE = "-";

  private volatile String route = NO_ROUTE;

  private RouteMarker() {}

  public static RouteMarker create() {
    return new RouteMarker();
  }

  /** Marks every access from now on as made for {@code route}. */
  public void set(String route) {
    this.route = java.util.Objects.requireNonNull(route, "route");
  }

  /** Back to {@link #NO_ROUTE}. */
  public void clear() {
    this.route = NO_ROUTE;
  }

  /** What a harness installs on the recorder; it answers the value current at the moment of each access. */
  public Supplier<String> supplier() {
    return () -> route;
  }
}
