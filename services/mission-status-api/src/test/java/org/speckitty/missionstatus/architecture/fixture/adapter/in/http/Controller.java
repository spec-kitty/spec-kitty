package org.speckitty.missionstatus.architecture.fixture.adapter.in.http;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class Controller {
  public org.speckitty.missionstatus.architecture.fixture.adapter.in.http.model.Dto get(org.speckitty.missionstatus.architecture.fixture.application.query.port.in.Query query) {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.in.http.model.Dto(query.value().text());
  }
}
