package org.speckitty.missionstatus.adapter.in.http;

import java.io.IOException;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/openapi.yaml}: the committed contract document, bundled at build time and served with its bytes unchanged
 * (operator decision E-11: contract first, no springdoc). A classpath read, not a project-root read.
 */
@RestController
class ContractDocumentController {

  static final String RESOURCE = "contract/openapi.yaml";
  private static final MediaType YAML = MediaType.parseMediaType("application/yaml");

  @GetMapping("/openapi.yaml")
  ResponseEntity<byte[]> document() throws IOException {
    return ResponseEntity.ok().contentType(YAML).body(new ClassPathResource(RESOURCE).getContentAsByteArray());
  }
}
