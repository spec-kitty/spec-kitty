package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture: rule 2, one spelling of running work on a thread the application does not own. */
public final class A2hAsyncOnOwnExecutor {
  public Object run(java.util.List<String> values) {
    return java.util.concurrent.CompletableFuture.runAsync(() -> {}, Runnable::run);
  }
}
