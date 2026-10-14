package org.speckitty.missionstatus.adapter.in.http.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.adapter.in.http.model.Actor;
import org.speckitty.missionstatus.adapter.in.http.model.Assignment;
import org.speckitty.missionstatus.adapter.in.http.model.Authored;
import org.speckitty.missionstatus.adapter.in.http.model.Cancellation;
import org.speckitty.missionstatus.adapter.in.http.model.HistoryEntry;
import org.speckitty.missionstatus.adapter.in.http.model.Readiness;
import org.speckitty.missionstatus.adapter.in.http.model.Review;
import org.speckitty.missionstatus.adapter.in.http.model.Staleness;
import org.speckitty.missionstatus.adapter.in.http.model.SubtaskProgress;
import org.speckitty.missionstatus.domain.model.CodePoints;
import tools.jackson.core.JsonGenerator;
import tools.jackson.databind.SerializationContext;
import tools.jackson.databind.ValueSerializer;
import tools.jackson.databind.annotation.JsonSerialize;

/**
 * The hand record of the contract schema {@code WorkPackage} (D-79 check c, D-111; research.md decision table). The generated model of
 * the same schema writes {@code "promptMarkdown":null} when the prompt was not requested; the contract says the member is then absent,
 * so {@code promptMarkdown} alone carries {@code NON_NULL}. Every other member is written, including an explicit {@code null}.
 *
 * <p>The open {@code subtasks} map is written through a code-point-ordered serializer: the mapper's {@code ORDER_MAP_ENTRIES_BY_KEYS}
 * sorts by UTF-16 unit, the golden by code point (S-15). The generated twin of this schema stays in the models list as the compile-time
 * drift sensor ({@code ContractDriftProbe}); it is never written to a response.
 */
public record WorkPackage(
    String wpId,
    String title,
    String phaseLabel,
    Authored authored,
    List<String> ownedFiles,
    List<String> dependencies,
    List<String> requirementRefs,
    String executionMode,
    String taskType,
    String priority,
    String mergeTargetBranch,
    List<String> trackerRefs,
    String statusLane,
    Assignment assignment,
    @JsonSerialize(using = CodePointOrderedMap.class) Map<String, String> subtasks,
    SubtaskProgress subtaskProgress,
    String implementerOfRecord,
    String lastTransitionAt,
    int forceCount,
    String lastEventId,
    Actor actor,
    Cancellation cancellation,
    Readiness readiness,
    boolean readyToStart,
    Review review,
    List<HistoryEntry> history,
    Staleness staleness,
    @JsonInclude(JsonInclude.Include.NON_NULL) String promptMarkdown) {

  /** Writes a {@code String} map with its keys in Unicode code point order, as Python's {@code sort_keys} does. */
  static final class CodePointOrderedMap extends ValueSerializer<Map<String, String>> {
    @Override
    public void serialize(Map<String, String> value, JsonGenerator generator, SerializationContext context) {
      List<Map.Entry<String, String>> entries = new ArrayList<>(value.entrySet());
      entries.sort((left, right) -> CodePoints.compare(left.getKey(), right.getKey()));
      generator.writeStartObject();
      for (Map.Entry<String, String> entry : entries) {
        generator.writeStringProperty(entry.getKey(), entry.getValue());
      }
      generator.writeEndObject();
    }
  }
}
