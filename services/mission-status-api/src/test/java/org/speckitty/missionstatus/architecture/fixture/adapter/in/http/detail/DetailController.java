package org.speckitty.missionstatus.architecture.fixture.adapter.in.http.detail;

/** Architecture-rule fixture, conforming: calls only the skeleton port and returns its record. */
public final class DetailController {
  public org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue get(org.speckitty.missionstatus.architecture.fixture.application.query.port.in.MissionDetailQuery query, org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue id) {
    return query.mission(id);
  }
}
