package org.speckitty.missionstatus.adapter.in.http.detail;

import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/missions/{missionId}}: the Mission detail. The controller holds no logic: it turns the path text into a typed
 * identifier (an id that is not a ULID is not found, never a bad request: the adapter does not choose between a 400 and a 404), makes one call
 * to the inbound port and shapes the result. Every refusal leaves as a typed exception that the advice maps to the shared Problem.
 */
@RestController
class MissionDetailController {

  private final MissionDetailQuery query;

  MissionDetailController(MissionDetailQuery query) {
    this.query = query;
  }

  @GetMapping("/missions/{missionId}")
  org.speckitty.missionstatus.adapter.in.http.model.MissionDetail mission(@PathVariable("missionId") String missionId) {
    MissionId id = MissionId.parse(missionId).orElseThrow(DetailRefusal::notFound);
    return MissionDetailMapper.detail(query.mission(id));
  }
}
