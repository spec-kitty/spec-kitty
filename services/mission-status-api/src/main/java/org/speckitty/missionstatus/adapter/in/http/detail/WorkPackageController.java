package org.speckitty.missionstatus.adapter.in.http.detail;

import jakarta.servlet.http.HttpServletRequest;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.adapter.in.http.dto.WorkPackage;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.springframework.aot.hint.annotation.RegisterReflectionForBinding;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /api/v1/missions/{missionId}/work-packages/{wpId}}: one Work Package, with {@code promptMarkdown} when {@code includePrompt=true}.
 * The controller holds no logic: it turns both path values into typed identifiers (an id that does not parse is not found, never a bad
 * request: the adapter does not choose between a 400 and a 404, rows C2 and W1), turns the parameter into a boolean through
 * {@link IncludePrompt} (a refused value is the {@code invalid_parameter} Problem before the port is called, so no file is read), makes one
 * call to the inbound port and shapes the result. The identifiers are judged before the parameter (S-27). The values come from the servlet's
 * parameter map, not from a framework conversion, because a conversion would turn an empty value into "no value" and join a repeated one.
 * Every refusal of the port leaves as a typed exception that the advice maps to the shared Problem; a malformed percent-encoding anywhere in
 * the query is raised by the container when the parameters are first read, which is before anything else here.
 *
 * <p>The method returns {@code ResponseEntity<?>} (the body is the {@code WorkPackage} record or the {@code invalid_parameter} Problem), so
 * the AOT processing cannot read the body type from its signature. A native image built without the binding hint below lacks the record's
 * components and answers {@code internal_error}; the hint registers the record, the generated model classes it holds and its serializer.
 * It sits here and not on the wiring because rule 9 keeps the contract DTO packages inside {@code adapter.in.http}.
 */
@RegisterReflectionForBinding(WorkPackage.class)
@RestController
class WorkPackageController {

  private static final String INCLUDE_PROMPT = "includePrompt";

  private final WorkPackageQuery query;

  WorkPackageController(WorkPackageQuery query) {
    this.query = query;
  }

  @GetMapping("/missions/{missionId}/work-packages/{wpId}")
  ResponseEntity<?> workPackage(@PathVariable("missionId") String missionId, @PathVariable("wpId") String wpId, HttpServletRequest request) {
    String[] values = request.getParameterValues(INCLUDE_PROMPT);
    MissionId mission = MissionId.parse(missionId).orElseThrow(DetailRefusal::notFound);
    WpId workPackage = WpId.parse(wpId).orElseThrow(DetailRefusal::notFound);
    Optional<Boolean> includePrompt = IncludePrompt.parse(values == null ? List.of() : Arrays.asList(values));
    if (includePrompt.isEmpty()) {
      return ProblemMapper.invalidParameter();
    }
    return ResponseEntity.ok(WorkPackageMapper.workPackage(query.workPackage(mission, workPackage, includePrompt.get())));
  }
}
