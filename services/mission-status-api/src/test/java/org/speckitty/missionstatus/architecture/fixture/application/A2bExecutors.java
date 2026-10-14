package org.speckitty.missionstatus.architecture.fixture.application;

/**
 * Architecture-rule fixture: planted violation of rule 2 (second control: an executor the application does not own).
 * The other thread spellings each have their own single-member control (A2c to A2g), so each one is proven on its own.
 */
public final class A2bExecutors {
  public Object pool() {
    return java.util.concurrent.Executors.newFixedThreadPool(2);
  }
}
