package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture, planted violation of rule 2c only: a thread started through Thread.ofVirtual, not through Executors. */
public final class A2cVirtualThread {
  public Thread start(Runnable task) {
    return Thread.ofVirtual().unstarted(task);
  }
}
