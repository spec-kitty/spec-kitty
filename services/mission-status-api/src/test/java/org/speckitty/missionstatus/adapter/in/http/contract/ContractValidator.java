package org.speckitty.missionstatus.adapter.in.http.contract;

import com.networknt.schema.Error;
import com.networknt.schema.InputFormat;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaLocation;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;
import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.yaml.snakeyaml.Yaml;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Validates response documents against the schemas of the bundled contract ({@code contract/openapi.yaml} on the classpath), with the
 * networknt validator (JSON Schema 2020-12: {@code unevaluatedProperties}, {@code type: [string, 'null']}, format assertions on).
 * Reusable: WP20 validates the data of every SSE event through {@link #validateEventData}.
 */
public final class ContractValidator {

  public static final List<String> EVENT_NAMES = List.of("status-transition", "mission-lifecycle", "log-truncated");

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final SchemaRegistry REGISTRY =
      SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12, builder -> builder.schemaRegistryConfig(com.networknt.schema.SchemaRegistryConfig.builder().formatAssertionsEnabled(true).build()));

  private final JsonNode document;
  private int sequence;

  private ContractValidator(JsonNode document) {
    this.document = document;
  }

  /** The validator over the bundle served by the application itself. */
  public static ContractValidator fromClasspath() {
    try (InputStream in = ContractValidator.class.getResourceAsStream("/contract/openapi.yaml")) {
      if (in == null) {
        throw new IllegalStateException("contract/openapi.yaml is not on the classpath");
      }
      return fromYaml(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
    } catch (IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    }
  }

  public static ContractValidator fromYaml(String yaml) {
    Object loaded = new Yaml().load(yaml);
    return new ContractValidator(JSON.valueToTree(loaded));
  }

  /** The schema node of {@code path} {@code GET} for a status key and a media type; fails when the contract has none. */
  public JsonNode responseSchema(String path, String status, String mediaType) {
    JsonNode node = document.path("paths").path(path).path("get").path("responses").path(status).path("content").path(mediaType).path("schema");
    if (node.isMissingNode()) {
      throw new IllegalArgumentException("the contract has no " + status + " " + mediaType + " schema for GET " + path);
    }
    return node;
  }

  public List<String> validate(JsonNode schema, String jsonText) {
    Schema compiled = REGISTRY.getSchema(SchemaLocation.of("urn:wp10:schema-" + (sequence++)), schema);
    return compiled.validate(jsonText, InputFormat.JSON).stream().map(Error::toString).toList();
  }

  public List<String> validateProject(String json) {
    return validate(responseSchema("/project", "200", "application/json"), json);
  }

  public List<String> validateMissions(String json) {
    return validate(responseSchema("/missions", "200", "application/json"), json);
  }

  /** The shared Problem (the {@code default} response). */
  public List<String> validateProblem(String json) {
    return validate(responseSchema("/project", "default", "application/problem+json"), json);
  }

  public List<String> validatePageCursorRefusal(String json) {
    return validate(responseSchema("/missions", "400", "application/problem+json"), json);
  }

  /** The problem body of a refused event stream request, by its status. */
  public List<String> validateStreamRefusal(int status, String json) {
    return validate(responseSchema("/events", Integer.toString(status), "application/problem+json"), json);
  }

  /** The data of one SSE event (WP20 reuses this): the schema is picked by the event name from the three the contract defines. */
  public List<String> validateEventData(String eventName, String jsonText) {
    String title =
        switch (eventName) {
          case "status-transition" -> "StatusTransitionEvent";
          case "mission-lifecycle" -> "MissionLifecycleEvent";
          case "log-truncated" -> "LogTruncatedEvent";
          default -> throw new IllegalArgumentException("not an event name of the contract: " + eventName);
        };
    return validate(eventSchema(title), jsonText);
  }

  /** The data schema of one event by its title. */
  public JsonNode eventSchema(String title) {
    for (JsonNode candidate : responseSchema("/events", "200", "text/event-stream").path("oneOf")) {
      if (title.equals(candidate.path("title").asString())) {
        return candidate;
      }
    }
    throw new IllegalArgumentException("the contract has no event schema titled " + title);
  }

  /** The {@code examples} of a schema, as JSON text. */
  public List<String> examples(JsonNode schema) {
    List<String> out = new java.util.ArrayList<>();
    for (JsonNode example : schema.path("examples")) {
      out.add(example.toString());
    }
    return out;
  }

  /** The schema node by the member path inside the document, for tests. */
  public Map<String, JsonNode> eventSchemas() {
    Map<String, JsonNode> out = new LinkedHashMap<>();
    for (String name : EVENT_NAMES) {
      out.put(name, eventSchema(switch (name) {
        case "status-transition" -> "StatusTransitionEvent";
        case "mission-lifecycle" -> "MissionLifecycleEvent";
        default -> "LogTruncatedEvent";
      }));
    }
    return out;
  }
}
