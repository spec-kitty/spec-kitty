package org.speckitty.missionstatus.application.query.artifact;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.artifact.ArtifactReader.Probe;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.CapRaceInjector;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/** The order of decision of the content read (FR-005) status by status, each next to a served control, and the classifier of AC-5.8. */
class ArtifactReaderTest {

  private static final MissionRef MISSION = new MissionRef("alpha-mission");
  private static final String MID8 = "00000000";
  private static final TextScreen SCREEN = new TextScreen(LeakPatternsFile.load());

  private final List<Diagnostic> diagnostics = new ArrayList<>();

  private static FileRef ref(String path) {
    return new FileRef.MissionFile(MISSION, RelativePath.of(path));
  }

  private static byte[] utf8(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  private ArtifactReader reader(InMemoryTextSource source) {
    return new ArtifactReader(source, SCREEN, diagnostics::add);
  }

  private DetailRefusal.Kind refusal(ArtifactReader reader, String path) {
    return org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, () -> reader.read(MISSION, MID8, path)).kind();
  }

  // ---- 200 -------------------------------------------------------------------------------------------------------------------

  @Test
  void aTextFileIsServedWithItsByteSizeItsClassAndItsMediaType() {
    InMemoryTextSource source = new InMemoryTextSource().file(ref("café.md"), utf8("café\n"));

    ArtifactContent content = reader(source).read(MISSION, MID8, "café.md");

    assertThat(content.content()).isEqualTo("café\n");
    assertThat(content.sizeBytes()).as("bytes, not characters").isEqualTo(6).isGreaterThan(content.content().length());
    assertThat(content.redacted()).isFalse();
    assertThat(content.kind()).isEqualTo(ArtifactKind.OTHER);
    assertThat(content.mediaType()).isEqualTo("text/markdown");
    assertThat(diagnostics).isEmpty();
    assertThat(source.readScopes()).as("read under the artifact scope, asserted explicitly").containsOnly(ReadScope.ARTIFACT);
  }

  @Test
  void anEmptyFileIs200WithEmptyContentAndSizeZero() {
    ArtifactContent content = reader(new InMemoryTextSource().file(ref("empty.txt"), new byte[0])).read(MISSION, MID8, "empty.txt");

    assertThat(content.content()).isEmpty();
    assertThat(content.sizeBytes()).isZero();
  }

  @Test
  void aByteOrderMarkIsKept() {
    byte[] bom = {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, 'x'};

    assertThat(reader(new InMemoryTextSource().file(ref("bom.md"), bom)).read(MISSION, MID8, "bom.md").content()).isEqualTo("﻿x");
  }

  @Test
  void aFileOfExactlyTheCapIsServedAndOneByteMoreIsTooLarge() {
    InMemoryTextSource source =
        new InMemoryTextSource().file(ref("cap.txt"), "a".repeat(ArtifactLimits.CONTENT_CAP_BYTES).getBytes(StandardCharsets.US_ASCII)).file(ref("over.txt"), "a".repeat(ArtifactLimits.READ_REQUEST_BYTES).getBytes(StandardCharsets.US_ASCII));
    ArtifactReader reader = reader(source);

    assertThat(reader.read(MISSION, MID8, "cap.txt").sizeBytes()).isEqualTo(262_144);
    assertThat(refusal(reader, "over.txt")).isEqualTo(DetailRefusal.Kind.ARTIFACT_TOO_LARGE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_TOO_LARGE, MID8, null));
  }

  // ---- 404: nothing eligible -------------------------------------------------------------------------------------------------

  @Test
  void aMissingFileADirectoryALinkAPathThroughALinkAndARootStatusRecordAreNotFoundWithNoDiagnostic() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("ok.md"), utf8("ok\n"))
            .file(ref("dir/inner.md"), utf8("inner\n"))
            .link(ref("link.md"))
            .link(ref("linkdir"))
            .file(ref("linkdir/x.md"), utf8("never read\n"))
            .file(ref("status.json"), utf8("{}"))
            .file(ref("STATUS.events.JSONL"), utf8("{}"))
            .file(ref("notes/status.json"), utf8("{}"));
    ArtifactReader reader = reader(source);

    assertThat(reader.read(MISSION, MID8, "ok.md").content()).isEqualTo("ok\n");
    for (String path : List.of("missing.md", "dir", "link.md", "linkdir/x.md", "status.json", "STATUS.events.JSONL", "ok.md/below")) {
      assertThat(refusal(reader, path)).as(path).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    }
    assertThat(reader.read(MISSION, MID8, "notes/status.json").content()).as("root only").isEqualTo("{}");
    assertThat(diagnostics).isEmpty();
    assertThat(source.readRefs()).as("the root records were never asked of the port").doesNotContain(ref("status.json"), ref("STATUS.events.JSONL"));
  }

  @Test
  void aVanishedMissionDirectoryOrFileIsNotFound() {
    InMemoryTextSource source = new InMemoryTextSource().fault(ref("gone.md"), TextFault.Kind.VANISHED);

    assertThat(refusal(reader(source), "gone.md")).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(diagnostics).isEmpty();
  }

  // ---- 415 -------------------------------------------------------------------------------------------------------------------

  @Test
  void aNulByteAndEveryFormOfInvalidUtf8AreNotText() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("nul.dat"), new byte[] {'a', 0, 'b'})
            .file(ref("lone.txt"), new byte[] {(byte) 0xC3})
            .file(ref("overlong.txt"), new byte[] {(byte) 0xC0, (byte) 0xAF})
            .file(ref("surrogate.txt"), new byte[] {(byte) 0xED, (byte) 0xA0, (byte) 0x80})
            .file(ref("latin1.txt"), new byte[] {'c', 'a', 'f', (byte) 0xE9})
            .file(ref("fine.txt"), utf8("fine"));
    ArtifactReader reader = reader(source);

    assertThat(reader.read(MISSION, MID8, "fine.txt").content()).isEqualTo("fine");
    for (String path : List.of("nul.dat", "lone.txt", "overlong.txt", "surrogate.txt", "latin1.txt")) {
      assertThat(refusal(reader, path)).as(path).isEqualTo(DetailRefusal.Kind.ARTIFACT_NOT_TEXT);
    }
    assertThat(diagnostics).hasSize(5).allMatch(diagnostic -> diagnostic.code() == DiagnosticCode.ARTIFACT_NOT_TEXT && diagnostic.mid8().equals(MID8));
  }

  // ---- 422 -------------------------------------------------------------------------------------------------------------------

  /** Credential-shaped inputs are assembled at run time from a prefix and a body; none is committed (D-48). */
  private static String token(String prefix, int bodyLength) {
    return prefix + "A".repeat(bodyLength);
  }

  @Test
  void aCredentialIs422WithNoContentAndANearMissOneCharacterShortIsServed() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("secret.txt"), utf8("key " + token("gh" + "p_", 36) + "\n"))
            .file(ref("near.txt"), utf8("key " + token("gh" + "p_", 35) + "\n"))
            .file(ref("pat.txt"), utf8(token("github" + "_pat_", 40)))
            .file(ref("pat-near.txt"), utf8(token("github" + "_pat_", 39)))
            .file(ref("aws.txt"), utf8(token("AK" + "IA", 16)))
            .file(ref("aws-near.txt"), utf8(token("AK" + "IA", 15)))
            .file(ref("bare.txt"), utf8("gh" + "p_"));
    ArtifactReader reader = reader(source);

    assertThat(refusal(reader, "secret.txt")).isEqualTo(DetailRefusal.Kind.ARTIFACT_SECRET);
    assertThat(refusal(reader, "pat.txt")).isEqualTo(DetailRefusal.Kind.ARTIFACT_SECRET);
    assertThat(refusal(reader, "aws.txt")).isEqualTo(DetailRefusal.Kind.ARTIFACT_SECRET);
    for (String path : List.of("near.txt", "pat-near.txt", "aws-near.txt", "bare.txt")) {
      assertThat(reader.read(MISSION, MID8, path).path()).as(path).isEqualTo(path);
    }
    assertThat(diagnostics).hasSize(3).allMatch(diagnostic -> diagnostic.code() == DiagnosticCode.ARTIFACT_SECRET);
  }

  @Test
  void noRefusalCarriesAByteOfTheFileOrAPath() {
    InMemoryTextSource source = new InMemoryTextSource().file(ref("secret.txt"), utf8("only-secret " + token("gh" + "p_", 36)));

    DetailRefusal refusal = org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, () -> reader(source).read(MISSION, MID8, "secret.txt"));

    assertThat(refusal.getMessage()).doesNotContain("only-secret", "secret.txt", "ghp");
    assertThat(diagnostics.toString()).doesNotContain("only-secret", "secret.txt", "ghp");
  }

  // ---- 200 with redaction ------------------------------------------------------------------------------------------------------

  @Test
  void aHostPathBecomesPathWithTheCharactersThatFollowItAndAnAddressBecomesEmail() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("paths.md"), utf8("Path: /ho" + "me/jane/x/y.md and mail jane" + "@" + "example.org in text.\nTrailing: /t" + "mp/a/b,c\n"))
            .file(ref("relative.md"), utf8("see docs/guide/readme.md and src/app/main.py\n"));

    ArtifactContent redacted = reader(source).read(MISSION, MID8, "paths.md");
    ArtifactContent untouched = reader(source).read(MISSION, MID8, "relative.md");

    assertThat(redacted.content()).isEqualTo("Path: [path] and mail [email] in text.\nTrailing: [path]\n");
    assertThat(redacted.redacted()).isTrue();
    assertThat(untouched.redacted()).isFalse();
    assertThat(untouched.content()).isEqualTo("see docs/guide/readme.md and src/app/main.py\n");
  }

  // ---- the classifier of AC-5.8 -------------------------------------------------------------------------------------------------

  @Test
  void theKindAndTheMediaTypeComeFromThePathAlone() {
    record Row(String path, ArtifactKind kind, String mediaType) {}
    List<Row> rows =
        List.of(
            new Row("tasks/WP01-x/review-cycle-1.md", ArtifactKind.REVIEW_CYCLE, "text/markdown"),
            new Row("tasks/WP01-x/review-cycle-01.md", ArtifactKind.OTHER, "text/markdown"),
            new Row("tasks/WP1-x.md", ArtifactKind.OTHER, "text/markdown"),
            new Row("tasks/WP01-x.md", ArtifactKind.WORK_PACKAGE_PROMPT, "text/markdown"),
            new Row("research.md", ArtifactKind.RESEARCH, "text/markdown"),
            new Row("research/a.md", ArtifactKind.RESEARCH, "text/markdown"),
            new Row("contracts/api.yaml", ArtifactKind.CONTRACT, "application/yaml"),
            new Row("checklists/r.md", ArtifactKind.CHECKLIST, "text/markdown"),
            new Row("meta.json", ArtifactKind.OTHER, "application/json"),
            new Row("events.jsonl", ArtifactKind.OTHER, "application/x-ndjson"),
            new Row("data.csv", ArtifactKind.OTHER, "text/csv"),
            new Row("A.MD", ArtifactKind.OTHER, "text/plain"),
            new Row("spec.md", ArtifactKind.SPEC, "text/markdown"));
    InMemoryTextSource source = new InMemoryTextSource();
    rows.forEach(row -> source.file(ref(row.path()), utf8("x")));

    for (Row row : rows) {
      ArtifactContent content = reader(source).read(MISSION, MID8, row.path());
      assertThat(content.kind()).as(row.path()).isEqualTo(row.kind());
      assertThat(content.mediaType()).as(row.path()).isEqualTo(row.mediaType());
    }
  }

  // ---- 500 ---------------------------------------------------------------------------------------------------------------------

  @Test
  void aFileOrDirectoryThatCannotBeReadIs500AndWritesOneUnreadableDiagnostic() {
    InMemoryTextSource source = new InMemoryTextSource().fault(ref("bad.md"), TextFault.Kind.FILE_UNREADABLE).fault(ref("baddir/x.md"), TextFault.Kind.DIR_UNREADABLE);

    assertThat(refusal(reader(source), "bad.md")).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    assertThat(refusal(reader(source), "baddir/x.md")).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, MID8, null), new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, MID8, null));
  }

  @Test
  void aNonAsciiPathOnAHostThatCannotDecodeNamesIs500UnreadableButAnAsciiPathIsServed() {
    InMemoryTextSource untrusted = new InMemoryTextSource().trustworthy(false).file(ref("café.md"), utf8("x")).file(ref("plain.md"), utf8("x"));
    InMemoryTextSource trusted = new InMemoryTextSource().file(ref("café.md"), utf8("x"));

    assertThat(refusal(reader(untrusted), "café.md")).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, MID8, null));
    assertThat(reader(untrusted).read(MISSION, MID8, "plain.md").content()).isEqualTo("x");
    assertThat(reader(trusted).read(MISSION, MID8, "café.md").content()).isEqualTo("x");
  }

  @Test
  void aFaultWhileAskingWhetherNamesCanBeTrustedLeavesTheDecisionToTheRead() {
    InMemoryTextSource source = new InMemoryTextSource().fault(new FileRef.MissionFile(MISSION, RelativePath.ROOT), TextFault.Kind.DIR_UNREADABLE);

    assertThat(refusal(reader(source), "caf\u00e9.md")).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(diagnostics).isEmpty();
  }

  // ---- the cap is applied twice (open handle, then bytes read) on a real file --------------------------------------------------

  private static Path mission(Path root) throws java.io.IOException {
    Path dir = Files.createDirectories(root.resolve("kitty-specs").resolve("alpha-mission"));
    Files.writeString(dir.resolve("meta.json"), "{}");
    return dir;
  }

  @Test
  void aFileOf262145BytesIsRefusedByTheOpenHandleWithoutReadingAByte(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    Files.write(dir.resolve("big.md"), new byte[ArtifactLimits.READ_REQUEST_BYTES]);
    CapRaceInjector injector = new CapRaceInjector(AllowlistAccess.passThrough(), path -> path.getFileName().toString().equals("big.md"), ArtifactLimits.READ_REQUEST_BYTES, new byte[ArtifactLimits.READ_REQUEST_BYTES]);
    ArtifactReader reader = new ArtifactReader(new FilesystemTextSource(root, injector, NameEncoding.fixed(true)), SCREEN, diagnostics::add);

    assertThat(refusal(reader, "big.md")).isEqualTo(DetailRefusal.Kind.ARTIFACT_TOO_LARGE);
    assertThat(injector.bytesRead()).as("the instrumented port records no byte read").isZero();
  }

  @Test
  void aFileThatIs100BytesAtStatAnd300000AtReadIsTooLargeByBytesReadAfterAtMost262145(@TempDir Path root) throws Exception {
    Path dir = mission(root);
    Files.write(dir.resolve("grows.md"), new byte[100]);
    CapRaceInjector injector = new CapRaceInjector(AllowlistAccess.passThrough(), path -> path.getFileName().toString().equals("grows.md"), 100, new byte[300_000]);
    ArtifactReader reader = new ArtifactReader(new FilesystemTextSource(root, injector, NameEncoding.fixed(true)), SCREEN, diagnostics::add);

    assertThat(refusal(reader, "grows.md")).isEqualTo(DetailRefusal.Kind.ARTIFACT_TOO_LARGE);
    assertThat(injector.bytesRead()).isPositive().isLessThanOrEqualTo(ArtifactLimits.READ_REQUEST_BYTES);
  }

  // ---- the probe: the one decision, without side effects --------------------------------------------------------------------

  @Test
  void theProbeSaysWhatARefusalWouldBeAndWritesNothing() {
    InMemoryTextSource source =
        new InMemoryTextSource()
            .file(ref("ok.md"), utf8("ok"))
            .file(ref("nul.dat"), new byte[] {0})
            .file(ref("secret.txt"), utf8(token("gh" + "p_", 36)))
            .file(ref("over.txt"), new byte[ArtifactLimits.READ_REQUEST_BYTES])
            .fault(ref("bad.md"), TextFault.Kind.FILE_UNREADABLE);
    ArtifactReader reader = reader(source);

    assertThat(reader.probe(MISSION, "ok.md")).isInstanceOf(Probe.Readable.class);
    assertThat(reader.probe(MISSION, "nul.dat")).isEqualTo(new Probe.Refused(DetailRefusal.Kind.ARTIFACT_NOT_TEXT));
    assertThat(reader.probe(MISSION, "secret.txt")).isEqualTo(new Probe.Refused(DetailRefusal.Kind.ARTIFACT_SECRET));
    assertThat(reader.probe(MISSION, "over.txt")).isEqualTo(new Probe.Refused(DetailRefusal.Kind.ARTIFACT_TOO_LARGE));
    assertThat(reader.probe(MISSION, "bad.md")).isEqualTo(new Probe.Refused(DetailRefusal.Kind.ARTIFACT_UNREADABLE));
    assertThat(reader.probe(MISSION, "missing.md")).isInstanceOf(Probe.Gone.class);
    assertThat(diagnostics).as("the probe writes nothing").isEmpty();
  }
}
