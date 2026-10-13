package org.speckitty.missionstatus.adapter.in.http.rest;

import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;

/** A small fixture for suites that only need a running server. */
public final class ContractRoutes {

  private ContractRoutes() {}

  public static FilesystemFixtureFactory.Built anyFixture() {
    return RouteSupport.pair(RouteSupport.moves(1, 2));
  }
}
