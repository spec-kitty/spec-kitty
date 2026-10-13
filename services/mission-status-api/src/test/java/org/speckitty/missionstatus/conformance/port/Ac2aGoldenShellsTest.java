package org.speckitty.missionstatus.conformance.port;

import org.speckitty.missionstatus.testsupport.Ac2aGoldenHook;
import org.speckitty.missionstatus.testsupport.PortLevelTest;
import org.speckitty.missionstatus.testsupport.PortSourceSelector;

/**
 * AC-2a for the five fixture classes whose outcome path resolution, {@code config.yaml}, {@code HEAD} and symbolic links do not
 * decide. Each method is a shell: it holds no assertion logic and delegates to {@link Ac2aGoldenHook} with its fixture class and the
 * selector's way of obtaining a query. Until the goldens exist the hook skips the test; the later work package implements the hook and
 * runs these shells against both sources, so nothing here changes.
 */
public class Ac2aGoldenShellsTest {

  @PortLevelTest("AC-2a/interleaved")
  public void interleaved() {
    Ac2aGoldenHook.check("interleaved", spec -> PortSourceSelector.open(spec).query());
  }

  @PortLevelTest("AC-2a/lifecycle-only")
  public void lifecycleOnly() {
    Ac2aGoldenHook.check("lifecycle-only", spec -> PortSourceSelector.open(spec).query());
  }

  @PortLevelTest("AC-2a/no-ledger")
  public void noLedger() {
    Ac2aGoldenHook.check("no-ledger", spec -> PortSourceSelector.open(spec).query());
  }

  @PortLevelTest("AC-2a/log-truncated")
  public void logTruncated() {
    Ac2aGoldenHook.check("log-truncated", spec -> PortSourceSelector.open(spec).query());
  }

  @PortLevelTest("AC-2a/crlf-and-listing")
  public void crlfAndListing() {
    Ac2aGoldenHook.check("crlf-and-listing", spec -> PortSourceSelector.open(spec).query());
  }
}
