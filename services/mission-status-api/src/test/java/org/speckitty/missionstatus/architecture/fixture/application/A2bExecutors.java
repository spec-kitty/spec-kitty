package org.speckitty.missionstatus.architecture.fixture.application;

/**
 * Architecture-rule fixture: planted violation of rule 2 (second control: ways to run work on a thread the application does not own).
 * Each member alone turns rule 2 red; they are listed so a reader sees every spelling the thread rule has to catch.
 */
public final class A2bExecutors {
  public Object pool() {
    return java.util.concurrent.Executors.newFixedThreadPool(2);
  }

  public Object common() {
    return java.util.concurrent.ForkJoinPool.commonPool();
  }

  public Object async() {
    return java.util.concurrent.CompletableFuture.runAsync(() -> {});
  }

  public Object parallel(java.util.List<String> values) {
    return values.parallelStream().count() + values.stream().parallel().count();
  }

  public Object timer() {
    return new java.util.Timer();
  }
}
