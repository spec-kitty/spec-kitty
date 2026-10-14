package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of rule 16 clause a: a port type imports Spring. */
public interface R16Spring {
  org.springframework.http.HttpStatus status();
}
