package org.speckitty.missionstatus.adapter.in.http;

import org.speckitty.missionstatus.adapter.in.http.api.ProjectApi;
import org.speckitty.missionstatus.adapter.in.http.model.Project;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

/** {@code GET /api/v1/project}: the generated interface over the inbound port, and nothing else. */
@RestController
class ProjectController implements ProjectApi {

  private final MissionStatusQuery query;

  ProjectController(MissionStatusQuery query) {
    this.query = query;
  }

  @Override
  public ResponseEntity<Project> getProject() {
    return ResponseEntity.ok(ContractMapper.project(query.project()));
  }
}
