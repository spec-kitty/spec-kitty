package org.speckitty.missionstatus.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.port.in.MissionArtifactQuery;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactListing;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/missions/{missionId}/artifacts} ({@code listArtifacts}) and {@code GET .../artifacts/content?path=}
 * ({@code getArtifactContent}). Hand-written, like the event stream, for two reasons. The generated models type {@code sizeBytes} as a
 * 32-bit integer. And the {@code path} query parameter must be judged as the list of its values: Spring's binding of a {@code String}
 * joins a repeated parameter with a comma, and answers a missing one with a code-less 400. The query string is decoded once, by the
 * container; a malformed percent-encoding leaves through the advice as {@code invalid_artifact_path}.
 */
@RestController
class ArtifactsController {

  static final String PATH_PARAMETER = "path";
  private static final Pattern CONTENT_PATH = Pattern.compile("/api/v1/missions/[^/]+/artifacts/content");

  private final MissionArtifactQuery query;

  ArtifactsController(MissionArtifactQuery query) {
    this.query = query;
  }

  /** Whether a request URI is the content route (for the advice, which sees a query string the container could not parse). */
  static boolean isContentPath(String requestUri) {
    return requestUri != null && CONTENT_PATH.matcher(requestUri).matches();
  }

  @GetMapping("/missions/{missionId}/artifacts")
  ResponseEntity<ArtifactBodies.Listing> listArtifacts(@PathVariable("missionId") String missionId) {
    return ResponseEntity.ok(body(query.listArtifacts(missionId)));
  }

  @GetMapping("/missions/{missionId}/artifacts/content")
  ResponseEntity<ArtifactBodies.Content> getArtifactContent(@PathVariable("missionId") String missionId, HttpServletRequest request) {
    String[] values = request.getParameterValues(PATH_PARAMETER);
    List<String> paths = values == null ? List.of() : Arrays.asList(values);
    return ResponseEntity.ok(body(query.readArtifact(missionId, paths)));
  }

  private static ArtifactBodies.Listing body(ArtifactListing listing) {
    List<ArtifactBodies.Entry> entries =
        listing.entries().stream().map(entry -> new ArtifactBodies.Entry(entry.path(), entry.kind().wire(), entry.sizeBytes(), entry.modifiedAt(), entry.readable())).toList();
    return new ArtifactBodies.Listing(listing.missionId(), entries, listing.truncated());
  }

  private static ArtifactBodies.Content body(ArtifactContent content) {
    return new ArtifactBodies.Content(content.path(), content.kind().wire(), content.mediaType(), ArtifactContent.ENCODING, content.sizeBytes(), content.redacted(), content.content());
  }
}
