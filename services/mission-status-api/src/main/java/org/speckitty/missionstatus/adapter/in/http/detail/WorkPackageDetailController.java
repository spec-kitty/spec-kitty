package org.speckitty.missionstatus.adapter.in.http.detail;

import org.speckitty.missionstatus.adapter.in.http.ProblemBody;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/missions/{missionId}/work-packages/{wpId}/detail}: the extended detail of one Work Package. The controller holds no
 * logic: it turns the two path texts into typed identifiers (an identifier that is not well formed is not found, never a bad request: the
 * adapter does not choose between a 400 and a 404), makes one call to the inbound port and shapes the result.
 *
 * <p>This route has two refusals in its contract, {@code not_found} and {@code source_unreadable}, so both kinds of refusal that the port
 * throws are answered here with the route's own Problem: every {@link MissionStatusUnavailable} (whatever diagnostic the service wrote) is
 * the one 500 {@code source_unreadable}. The shared advice keeps every other route.
 */
@RestController
class WorkPackageDetailController {

  private final WorkPackageDetailQuery query;

  WorkPackageDetailController(WorkPackageDetailQuery query) {
    this.query = query;
  }

  @GetMapping("/missions/{missionId}/work-packages/{wpId}/detail")
  org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetail detail(@PathVariable("missionId") String missionId, @PathVariable("wpId") String wpId) {
    MissionId mission = MissionId.parse(missionId).orElseThrow(DetailRefusal::notFound);
    WpId workPackage = WpId.parse(wpId).orElseThrow(DetailRefusal::notFound);
    return WorkPackageDetailMapper.detail(query.workPackageDetail(mission, workPackage));
  }

  @ExceptionHandler(DetailRefusal.class)
  ResponseEntity<ProblemBody> refused(DetailRefusal refusal) {
    return ProblemMapper.workPackageDetail(refusal);
  }

  @ExceptionHandler(MissionStatusUnavailable.class)
  ResponseEntity<ProblemBody> unreadable(MissionStatusUnavailable unavailable) {
    return ProblemMapper.workPackageDetail(DetailRefusal.sourceUnreadable());
  }
}
