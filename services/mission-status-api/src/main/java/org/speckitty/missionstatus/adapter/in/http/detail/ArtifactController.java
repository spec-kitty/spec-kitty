package org.speckitty.missionstatus.adapter.in.http.detail;

import jakarta.servlet.http.HttpServletRequest;
import org.speckitty.missionstatus.adapter.in.http.ProblemBody;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactContent;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactListing;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /missions/{missionId}/artifacts} (listArtifacts) and {@code GET /missions/{missionId}/artifacts/content?path=}
 * (getArtifactContent), under the {@code /api/v1} prefix. Hand-written: the generated interface set has neither. It holds a typed
 * identifier, the raw {@code path} values and one call on {@link ArtifactQuery}.
 *
 * <p>An ill-formed {@code missionId} is {@code not_found}, never a 400, and it is judged first, so it wins over a malformed {@code path}
 * (rulings E-5 and OO-2). The raw query string is read as it came (a framework parameter would join a repeated {@code path} and replace
 * invalid UTF-8): {@link RawQuery} decodes each value once, strictly, and the port decides what zero, several or malformed values are.
 * The refusal of the port is answered here with the artifact Problem of the contract; the shared advice keeps every other route.
 */
@RestController
class ArtifactController {

  private final ArtifactQuery query;

  ArtifactController(ArtifactQuery query) {
    this.query = query;
  }

  @GetMapping("/missions/{missionId}/artifacts")
  ArtifactListing listArtifacts(@PathVariable("missionId") String missionId) {
    return ArtifactMapper.listing(query.list(missionId(missionId)));
  }

  @GetMapping("/missions/{missionId}/artifacts/content")
  ArtifactContent getArtifactContent(@PathVariable("missionId") String missionId, HttpServletRequest request) {
    MissionId id = missionId(missionId);
    return ArtifactMapper.content(query.content(id, RawQuery.path(request.getQueryString())));
  }

  @ExceptionHandler(DetailRefusal.class)
  ResponseEntity<ProblemBody> refused(DetailRefusal refusal) {
    return ProblemMapper.artifact(refusal);
  }

  private static MissionId missionId(String raw) {
    return MissionId.parse(raw).orElseThrow(DetailRefusal::notFound);
  }
}
