package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.exceptions.ArtifactRefused;
import org.speckitty.missionstatus.application.query.port.out.MissionArtifactSource;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactBytes;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactFile;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactListing;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactRefusalCode;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/** The order of decision of the artifact reads over a scripted source: the faults a real tree run as root cannot produce. */
class ArtifactQueryServiceTest {

  private static final String ID = "01J01000000000000000000001";
  private static final MissionRef MISSION = new MissionRef("alpha");

  /** A scripted source: files by path, plus switches for each fault. */
  private static final class FakeSource implements MissionArtifactSource {
    final Map<String, byte[]> files = new HashMap<>();
    final Set<String> vanishOnStat = new HashSet<>();
    final Set<String> eligibilityFault = new HashSet<>();
    final Set<String> unreadable = new HashSet<>();
    final List<String> extraWalked = new ArrayList<>();
    boolean present = true;
    boolean dirFault;
    boolean walkFault;
    int reads;

    @Override
    public Optional<MissionRef> findMission(String missionId) {
      return ID.equals(missionId) ? Optional.of(MISSION) : Optional.empty();
    }

    @Override
    public boolean missionDirPresent(MissionRef ref) {
      if (dirFault) {
        throw new SourceFault(SourceFault.Kind.DIR_UNREADABLE);
      }
      return present;
    }

    @Override
    public List<String> walk(MissionRef ref) {
      if (walkFault) {
        throw new SourceFault(SourceFault.Kind.DIR_UNREADABLE);
      }
      List<String> walked = new ArrayList<>(files.keySet());
      walked.addAll(extraWalked);
      return walked;
    }

    @Override
    public boolean isRegularFileWithoutLinks(MissionRef ref, String path) {
      if (eligibilityFault.contains(path)) {
        throw new SourceFault(SourceFault.Kind.DIR_UNREADABLE);
      }
      return files.containsKey(path);
    }

    @Override
    public Optional<ArtifactFile> stat(MissionRef ref, String path) {
      return vanishOnStat.contains(path) || !files.containsKey(path) ? Optional.empty() : Optional.of(new ArtifactFile(files.get(path).length, 0));
    }

    @Override
    public ArtifactBytes read(MissionRef ref, String path, int cap) {
      reads++;
      if (unreadable.contains(path)) {
        return new ArtifactBytes.Unreadable();
      }
      byte[] data = files.get(path);
      if (data.length > cap) {
        return new ArtifactBytes.TooLarge(data.length);
      }
      return new ArtifactBytes.Content(data.length, data);
    }
  }

  private final FakeSource source = new FakeSource();
  private final ArtifactQueryService service = new ArtifactQueryService(source, LeakPatternsFile.load());

  private static ArtifactRefusalCode codeOf(Runnable call) {
    try {
      call.run();
    } catch (ArtifactRefused refused) {
      return refused.code();
    }
    throw new AssertionError("no refusal");
  }

  private static byte[] text(String value) {
    return value.getBytes(StandardCharsets.UTF_8);
  }

  @Test
  void aContentReadIsDecidedInTheReferenceOrder() {
    source.files.put("spec.md", text("spec"));
    assertThat(codeOf(() -> service.readArtifact(ID, List.of()))).isEqualTo(ArtifactRefusalCode.INVALID_ARTIFACT_PATH);
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("spec.md", "spec.md")))).isEqualTo(ArtifactRefusalCode.INVALID_ARTIFACT_PATH);
    assertThat(codeOf(() -> service.readArtifact("bogus", List.of("../x")))).isEqualTo(ArtifactRefusalCode.INVALID_ARTIFACT_PATH);
    assertThat(codeOf(() -> service.readArtifact("bogus", List.of("spec.md")))).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
    assertThat(codeOf(() -> service.readArtifact("01J01000000000000000000009", List.of("spec.md")))).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
    ArtifactContent content = service.readArtifact(ID, List.of("spec.md"));
    assertThat(content.content()).isEqualTo("spec");
    assertThat(content.sizeBytes()).isEqualTo(4);
  }

  @Test
  void aMissionDirectoryThatIsGoneIsNotFoundAndOneThatCannotBeStatedIsAServerError() {
    source.files.put("spec.md", text("spec"));
    source.present = false;
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("spec.md")))).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
    assertThat(codeOf(() -> service.listArtifacts(ID))).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
    source.present = true;
    source.dirFault = true;
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("spec.md")))).isEqualTo(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
    assertThat(codeOf(() -> service.listArtifacts(ID))).isEqualTo(ArtifactRefusalCode.ARTIFACT_LISTING_UNREADABLE);
  }

  @Test
  void anEligibilityOrReadFaultIsAServerErrorNeverANotFound() {
    source.files.put("spec.md", text("spec"));
    source.files.put("plan.md", text("plan"));
    source.eligibilityFault.add("spec.md");
    source.unreadable.add("plan.md");
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("spec.md")))).isEqualTo(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("plan.md")))).isEqualTo(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
  }

  @Test
  void statusRecordsAndNamesTheRuleRefusesAreNeverListed() {
    source.files.put("status.json", text("{}"));
    source.files.put("Status.Events.Jsonl", text(""));
    source.files.put("spec.md", text("spec"));
    source.extraWalked.add("a\\b");
    assertThat(service.listArtifacts(ID).entries()).extracting(entry -> entry.path()).containsExactly("spec.md");
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("status.json")))).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
  }

  @Test
  void aListingIsSortedByCodePointCappedAndMarksTruncation() {
    for (int i = 0; i < 1001; i++) {
      source.files.put(String.format("n/%04d.md", i), text("x"));
    }
    source.files.put("😀.md", text("emoji"));
    source.files.put("�.md", text("replacement"));
    ArtifactListing listing = service.listArtifacts(ID);
    assertThat(listing.entries()).hasSize(1000);
    assertThat(listing.truncated()).isTrue();
    assertThat(listing.entries().get(0).path()).isEqualTo("n/0000.md");
    source.files.clear();
    source.files.put("😀.md", text("emoji"));
    source.files.put("�.md", text("replacement"));
    assertThat(service.listArtifacts(ID).entries()).extracting(entry -> entry.path()).containsExactly("�.md", "😀.md");
    assertThat(service.listArtifacts(ID).truncated()).isFalse();
  }

  @Test
  void aFileGoneBeforeItsStatIsOmittedAndAFaultFailsTheListing() {
    source.files.put("spec.md", text("spec"));
    source.files.put("plan.md", text("plan"));
    source.vanishOnStat.add("plan.md");
    assertThat(service.listArtifacts(ID).entries()).extracting(entry -> entry.path()).containsExactly("spec.md");
    source.eligibilityFault.add("spec.md");
    assertThat(codeOf(() -> service.listArtifacts(ID))).isEqualTo(ArtifactRefusalCode.ARTIFACT_LISTING_UNREADABLE);
    source.eligibilityFault.clear();
    source.walkFault = true;
    assertThatThrownBy(() -> service.listArtifacts(ID)).isInstanceOf(ArtifactRefused.class);
  }

  @Test
  void aFileOverTheCapIsDecidedFromItsSizeAndNeverRead() {
    source.files.put("big.txt", new byte[262_145]);
    ArtifactListing listing = service.listArtifacts(ID);
    assertThat(listing.entries().get(0).readable()).isFalse();
    assertThat(source.reads).isZero();
    assertThat(codeOf(() -> service.readArtifact(ID, List.of("big.txt")))).isEqualTo(ArtifactRefusalCode.ARTIFACT_TOO_LARGE);
  }

  @Test
  void aNameOutsideTheArtifactAllowlistIsNeitherListedNorOpened() {
    source.files.put("spec.md", text("spec"));
    for (String name : new String[] {".env", "notes/.env", "credentials.json", "id_rsa", "server.pem"}) {
      source.files.put(name, text("OPENAI_API_KEY=" + "sk-" + "proj-" + "x".repeat(40)));
    }
    assertThat(service.listArtifacts(ID).entries()).extracting(entry -> entry.path()).containsExactly("spec.md");
    assertThat(source.reads).as("only spec.md is read, for its readable flag").isEqualTo(1);
    for (String name : new String[] {".env", "notes/.env", "credentials.json", "id_rsa", "server.pem"}) {
      assertThat(codeOf(() -> service.readArtifact(ID, List.of(name)))).as(name).isEqualTo(ArtifactRefusalCode.NOT_FOUND);
    }
    assertThat(source.reads).as("a refused name is never opened").isEqualTo(1);
  }

  @Test
  void theReadableFlagIsTheContentDecision() {
    source.files.put("ok.md", text("ok"));
    source.files.put("bad.md", new byte[] {(byte) 0xff});
    source.files.put("gone.md", text("x"));
    source.unreadable.add("gone.md");
    Map<String, Boolean> readable = new HashMap<>();
    service.listArtifacts(ID).entries().forEach(entry -> readable.put(entry.path(), entry.readable()));
    assertThat(readable).containsEntry("ok.md", true).containsEntry("bad.md", false).containsEntry("gone.md", false);
  }
}
