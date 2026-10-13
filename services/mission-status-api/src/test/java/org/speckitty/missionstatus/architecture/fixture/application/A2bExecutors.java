package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture: planted violation of rule 2 (second control: Executors in application). */
public final class A2bExecutors {
  public Object pool() {
    return java.util.concurrent.Executors.newFixedThreadPool(2);
  }
}
