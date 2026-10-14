package org.speckitty.missionstatus.conformance.golden;

import java.util.Set;

/**
 * What a detail route phase registers with the golden harness: the {@code (fixture, golden file)} pairs it serves, and the raw response
 * body it answers for each request key of a pair. The shape is complete: no route work package edits this file.
 *
 * <p>A golden file of the detail classes is a canonical-JSON object keyed by <em>request key</em>, and one fixture holds up to four
 * golden files, so a route serves a pair and answers one request per key of that golden. The request conventions, fixed here for the
 * four route work packages:
 *
 * <ul>
 *   <li>key {@code "-"}: the Mission-level request ({@code GET /api/v1/missions/{missionId}}, and {@code listArtifacts});
 *   <li>a Work Package id key: {@code GET .../work-packages/{wpId}} ({@code get-work-package.json}, with no {@code includePrompt}
 *       parameter; {@code get-work-package-prompt.json}, the same URL with {@code includePrompt=true}) or
 *       {@code .../work-packages/{wpId}/detail} ({@code get-work-package-detail.json});
 *   <li>for {@code get-artifact-content.json} the key is the artifact path, requested as {@code .../artifacts/content?path=<key>} with
 *       the path percent-encoded once.
 * </ul>
 *
 * The Mission id of a request is the synthetic ULID of the fixture's {@code meta.json}. The body is the raw response body whatever the
 * status: an oracle refusal such as {@code legacy-lanes-json} compares the Problem body.
 */
public interface ServedRoute {

  /** One served pair: {@code fixtureKey} is {@code ConformanceTree.TreeFixture#key()}; {@code goldenFile} one of the six golden file names. */
  record Entry(String fixtureKey, String goldenFile) {}

  /** The golden file names this provider owns (the partition of {@link ServedRoutes#OWNER}). */
  Set<String> goldenFiles();

  /** Every pair this provider serves. */
  Set<Entry> served();

  /** The raw response body answered for one request key of one served pair. */
  byte[] body(Entry entry, String requestKey);
}
