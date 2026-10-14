package org.speckitty.missionstatus.architecture.fixture.domain;

/** Architecture-rule fixture: planted violation of rule 1 (third control: a thread in the domain, which java.lang alone would allow). */
public final class D1cThread {
  public Thread start() {
    return Thread.ofVirtual().start(() -> {});
  }
}
