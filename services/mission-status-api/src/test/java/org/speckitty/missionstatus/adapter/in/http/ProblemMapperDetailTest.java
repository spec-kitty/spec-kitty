package org.speckitty.missionstatus.adapter.in.http;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

/** The one table from a {@link DetailRefusal} kind to a status and a Problem (the contract's artifact and detail refusal codes), and the {@code invalid_parameter} Problem. */
class ProblemMapperDetailTest {

  /** Text that would show a location, a file, an exception or an enum name. */
  private static final List<String> CANARIES = List.of("/", "\\", "kitty-specs", ".md", ".yaml", "WP0", "Exception", "NOT_FOUND", "ARTIFACT_", "java.");

  private static int expectedStatus(DetailRefusal.Kind kind) {
    return switch (kind) {
      case NOT_FOUND -> 404;
      case INVALID_ARTIFACT_PATH -> 400;
      case ARTIFACT_TOO_LARGE -> 413;
      case ARTIFACT_NOT_TEXT -> 415;
      case ARTIFACT_SECRET -> 422;
      case ARTIFACT_UNREADABLE, ARTIFACT_LISTING_UNREADABLE, SOURCE_UNREADABLE -> 500;
    };
  }

  @ParameterizedTest
  @EnumSource(DetailRefusal.Kind.class)
  void everyKindHasItsStatusAndItsContractCode(DetailRefusal.Kind kind) {
    ResponseEntity<ProblemBody> response = ProblemMapper.detail(new DetailRefusal(kind));

    assertThat(response.getStatusCode().value()).isEqualTo(expectedStatus(kind));
    assertThat(response.getHeaders().getContentType()).isEqualTo(MediaType.APPLICATION_PROBLEM_JSON);
    ProblemBody body = response.getBody();
    assertThat(body.code()).isEqualTo(kind.wire());
    assertThat(body.status()).isEqualTo(expectedStatus(kind));
    assertThat(body.title()).isNotBlank();
    assertThat(body.detail()).isNotBlank();
  }

  @Test
  void theKindsCoverEveryCodeOfTheContract() {
    assertThat(Arrays.stream(DetailRefusal.Kind.values()).map(DetailRefusal.Kind::wire))
        .containsExactly(
            "not_found", "invalid_artifact_path", "artifact_too_large", "artifact_not_text", "artifact_secret", "artifact_unreadable",
            "artifact_listing_unreadable", "source_unreadable");
  }

  @ParameterizedTest
  @EnumSource(DetailRefusal.Kind.class)
  void aBodyNamesNoPathNoHomeNoFileNoEnumAndNoExceptionText(DetailRefusal.Kind kind) {
    ProblemBody body = ProblemMapper.detail(new DetailRefusal(kind)).getBody();
    String all = body.code() + "|" + body.title() + "|" + body.detail();

    assertThat(all).doesNotContain(System.getProperty("user.home"), System.getProperty("java.io.tmpdir"), System.getProperty("user.name"));
    for (String canary : CANARIES) {
      assertThat(all).as("canary %s", canary).doesNotContain(canary);
    }
  }

  @Test
  void invalidParameterIs400WithItsCodeAndNoRequestValue() {
    ResponseEntity<ProblemBody> response = ProblemMapper.invalidParameter();

    assertThat(response.getStatusCode().value()).isEqualTo(400);
    assertThat(response.getHeaders().getContentType()).isEqualTo(MediaType.APPLICATION_PROBLEM_JSON);
    assertThat(response.getBody().code()).isEqualTo("invalid_parameter");
    assertThat(response.getBody().status()).isEqualTo(400);
    assertThat(response.getBody().title()).isNotBlank();
  }

  @ParameterizedTest
  @EnumSource(DetailRefusal.Kind.class)
  void theAdviceHandlerAnswersEveryKindWithTheMapperOutput(DetailRefusal.Kind kind) {
    ResponseEntity<ProblemBody> viaAdvice = new ProblemAdvice().detail(new DetailRefusal(kind));

    assertThat(viaAdvice.getStatusCode().value()).isEqualTo(expectedStatus(kind));
    assertThat(viaAdvice.getBody()).isEqualTo(ProblemMapper.detail(new DetailRefusal(kind)).getBody());
  }

  @Test
  void theAdviceHasExactlyOneHandlerForDetailRefusal() {
    long handlers =
        Arrays.stream(ProblemAdvice.class.getDeclaredMethods())
            .filter(m -> m.isAnnotationPresent(org.springframework.web.bind.annotation.ExceptionHandler.class))
            .filter(m -> Arrays.asList(m.getAnnotation(org.springframework.web.bind.annotation.ExceptionHandler.class).value()).contains(DetailRefusal.class))
            .count();

    assertThat(handlers).isEqualTo(1);
  }
}
