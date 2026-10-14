package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;

/** The HTTP status of a stream refusal is the adapter's: each kind maps to the one the contract fixes. */
class ProblemMapperTest {

  private static final Map<StreamRefused.Kind, Integer> CONTRACT_STATUS =
      Map.of(
          StreamRefused.Kind.NEGATIVE, 400,
          StreamRefused.Kind.MISALIGNED, 400,
          StreamRefused.Kind.CURSOR_WITHOUT_MISSION, 400,
          StreamRefused.Kind.OUT_OF_RANGE, 409,
          StreamRefused.Kind.CONTENT_MISMATCH, 409,
          StreamRefused.Kind.UNKNOWN_MISSION, 404);

  @Test
  void theStatusOfEachRefusalIsTheOneTheContractFixes() {
    assertThat(CONTRACT_STATUS).as("every kind is covered").containsOnlyKeys(StreamRefused.Kind.values());
    CONTRACT_STATUS.forEach(
        (kind, status) -> assertThat(ProblemMapper.stream(new StreamRefused(kind)).getStatusCode().value()).as(kind.wire()).isEqualTo(status));
  }
}
