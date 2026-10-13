package org.speckitty.missionstatus.adapter.in.http;

import org.speckitty.missionstatus.adapter.in.http.api.MissionsApi;
import org.speckitty.missionstatus.adapter.in.http.model.MissionOverviewPage;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/missions}: the generated interface over the inbound port. The page size is clamped by the application (the
 * generated constraint annotations are not enforced: no validator is on the classpath), and a refused page cursor is mapped to the
 * Problem by the advice.
 */
@RestController
class MissionsController implements MissionsApi {

  private final MissionStatusQuery query;

  MissionsController(MissionStatusQuery query) {
    this.query = query;
  }

  @Override
  public ResponseEntity<MissionOverviewPage> listMissions(Integer pageSize, String pageCursor) {
    return ResponseEntity.ok(ContractMapper.page(query.missions(new PageRequest(pageSize, pageCursor))));
  }
}
