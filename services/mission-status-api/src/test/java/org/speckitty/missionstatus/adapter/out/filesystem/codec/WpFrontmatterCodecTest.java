package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.WpFrontmatterCodec.Yaml12;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.FrontmatterResult.RejectionClass;
import org.speckitty.missionstatus.domain.model.WpMetadata;

/**
 * FR-006 items 3 and 4, at the codec: the file framing (BOM, newlines, delimiters), the YAML 1.2 resolution of plain scalars that
 * ruamel applies and snakeyaml does not, and the {@code WPMetadata} validation. The corpus {@code wpm-01..28} is read by
 * {@link WpFrontmatterCodecCorpusTest}.
 */
class WpFrontmatterCodecTest {

  private static final String ID = "work_package_id: WP01\n";

  private static FrontmatterResult decode(String text) {
    return WpFrontmatterCodec.decode(text.getBytes(StandardCharsets.UTF_8));
  }

  private static FrontmatterResult file(String yaml) {
    return decode("---\n" + yaml + "---\n\nbody\n");
  }

  private static WpMetadata parsed(String yaml) {
    FrontmatterResult result = file(yaml);
    assertThat(result).as(yaml).isInstanceOf(FrontmatterResult.Parsed.class);
    return ((FrontmatterResult.Parsed) result).metadata();
  }

  private static void assertRejected(String yaml, RejectionClass kind) {
    assertThat(file(yaml)).as(yaml).isEqualTo(new FrontmatterResult.Rejected(kind));
  }

  // ---- framing ----------------------------------------------------------------------------------------------------------------

  @Test
  void theBodyIsEveryLineAfterTheClosingDelimiterJoinedByALineFeed() {
    FrontmatterResult.Parsed result = (FrontmatterResult.Parsed) decode("---\n" + ID + "---\n\n# Body\nline\n");
    assertThat(result.body()).isEqualTo("\n# Body\nline\n");
  }

  @Test
  void aLeadingByteOrderMarkIsDroppedOnceAndOnlyOnce() {
    byte[] bom = {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF};
    byte[] once = concat(bom, ("---\n" + ID + "---\n").getBytes(StandardCharsets.UTF_8));
    assertThat(WpFrontmatterCodec.decode(once)).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(WpFrontmatterCodec.decode(concat(bom, once))).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_FRONTMATTER));
  }

  @Test
  void crLfAndALoneCrAreTranslatedToLineFeedsBeforeSplitting() {
    FrontmatterResult.Parsed crlf = (FrontmatterResult.Parsed) decode("---\r\n" + ID.trim() + "\r\n---\r\nbody\r\nmore\r\n");
    assertThat(crlf.body()).isEqualTo("body\nmore\n");
    FrontmatterResult.Parsed cr = (FrontmatterResult.Parsed) decode("---\r" + ID.trim() + "\r---\rbody\r");
    assertThat(cr.body()).isEqualTo("body\n");
    assertThat(cr.metadata().workPackageId()).isEqualTo("WP01");
  }

  @Test
  void theClosingDelimiterIsTheFirstLaterLineThatStripsToTripleDashAndMayCarryWhitespace() {
    assertThat(decode("---\n" + ID + "---   \nbody")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(decode("---\n" + ID + " \u00a0---\u3000\nbody")).as("Python strip removes Unicode spaces").isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(decode("---\n" + ID + "--- x\nbody")).as("not a bare delimiter").isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_CLOSING_DELIMITER));
  }

  @Test
  void anOpeningLineMayCarryTextAfterTheDashesBecauseOnlyTheStartIsTested() {
    assertThat(decode("---abc\n" + ID + "---\n")).isInstanceOf(FrontmatterResult.Parsed.class);
  }

  @Test
  void aFileWithoutTheOpeningOrClosingDelimiterIsRejected() {
    assertThat(decode("# just a body\n")).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_FRONTMATTER));
    assertThat(decode("")).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_FRONTMATTER));
    assertThat(decode("---\n" + ID)).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_CLOSING_DELIMITER));
    assertThat(decode("---")).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NO_CLOSING_DELIMITER));
  }

  @Test
  void bytesThatAreNotStrictUtf8AreRejectedAndNeverRepaired() {
    byte[] valid = ("---\n" + ID + "title: ok\n---\n").getBytes(StandardCharsets.UTF_8);
    byte[] broken = concat(valid, new byte[] {(byte) 0xC3});
    assertThat(WpFrontmatterCodec.decode(broken)).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NOT_UTF8));
    assertThat(WpFrontmatterCodec.decode(concat(valid, new byte[] {(byte) 0xC0, (byte) 0xAF}))).isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NOT_UTF8));
    assertThat(WpFrontmatterCodec.decode(concat(valid, new byte[] {(byte) 0xED, (byte) 0xA0, (byte) 0x80})))
        .isEqualTo(new FrontmatterResult.Rejected(RejectionClass.NOT_UTF8));
    assertThat(WpFrontmatterCodec.decode(valid)).as("control: the same bytes without the break parse").isInstanceOf(FrontmatterResult.Parsed.class);
  }

  // ---- the YAML document ------------------------------------------------------------------------------------------------------

  @Test
  void anEmptyDocumentAndAnExplicitNullAreEmptyMappingsThatFailValidationForWantingAnId() {
    assertRejected("", RejectionClass.VALIDATION);
    assertRejected("~\n", RejectionClass.VALIDATION);
    assertRejected("# only a comment\n", RejectionClass.VALIDATION);
  }

  @Test
  void aSyntaxErrorADuplicateKeyAndANonMappingAreEachTheirOwnRejection() {
    assertRejected("work_package_id: [WP01\n", RejectionClass.YAML_SYNTAX);
    assertRejected("work_package_id: WP01\nwork_package_id: WP02\n", RejectionClass.DUPLICATE_KEY);
    assertRejected("- WP01\n- WP02\n", RejectionClass.NOT_A_MAPPING);
    assertRejected("just text\n", RejectionClass.NOT_A_MAPPING);
    assertRejected("a: 1\n--- b\n", RejectionClass.YAML_SYNTAX);
  }

  @Test
  void aDuplicateKeyInANestedMappingIsRejectedToo() {
    assertRejected(ID + "agent:\n  tool: a\n  tool: b\n", RejectionClass.DUPLICATE_KEY);
  }

  @Test
  void aQuotedAndAPlainSpellingOfOneKeyAreDuplicates() {
    assertRejected("work_package_id: WP01\n\"work_package_id\": WP02\n", RejectionClass.DUPLICATE_KEY);
  }

  @ParameterizedTest
  @ValueSource(strings = {"base: &a 1\n", "base: *a\n", "base: !!str 1\n", "base: !custom 1\n", "<<: {a: 1}\n", "? [a]\n: 1\n", "base: {<<: x}\n"})
  void whatTheDecoderCannotReadIdenticallyIsRefusedNotGuessed(String yaml) {
    FrontmatterResult result = file(ID + yaml);
    assertThat(result).as(yaml).isInstanceOf(FrontmatterResult.Rejected.class);
    assertThat(((FrontmatterResult.Rejected) result).kind()).isIn(RejectionClass.UNSUPPORTED_YAML, RejectionClass.YAML_SYNTAX);
  }

  @Test
  void anAnchorAnAliasAnExplicitTagAndAMergeKeyAreReportedAsUnsupportedYaml() {
    assertRejected(ID + "agent: &a {tool: x}\n", RejectionClass.UNSUPPORTED_YAML);
    assertRejected(ID + "agent: !!map {tool: x}\n", RejectionClass.UNSUPPORTED_YAML);
    assertRejected(ID + "agent: &s [x]\n", RejectionClass.UNSUPPORTED_YAML);
    assertRejected(ID + "<<: {a: 1}\n", RejectionClass.UNSUPPORTED_YAML);
    assertRejected(ID + "agent: [<<]\n".replace("[<<]", "{<<: 1}"), RejectionClass.UNSUPPORTED_YAML);
    assertRejected(ID + "agent: {[a]: 1}\n", RejectionClass.UNSUPPORTED_YAML);
  }

  // ---- YAML 1.2 resolution (the oracle) against YAML 1.1 (snakeyaml) -----------------------------------------------------------

  @ParameterizedTest
  @ValueSource(strings = {"yes", "Yes", "YES", "no", "on", "On", "ON", "off", "y", "Y", "n", "N", "1:30", "0o", "_", "tRUE", "nUll", "1_000x", "0b2", "1.2.3"})
  void aPlainScalarThatYaml11ReadsAsABooleanOrANumberIsAStringInYaml12(String text) {
    assertThat(Yaml12.resolve(text).type()).as(text).isEqualTo(Yaml12.Type.STR);
  }

  @ParameterizedTest
  @CsvSource({
    "true,BOOL", "True,BOOL", "TRUE,BOOL", "false,BOOL", "False,BOOL", "FALSE,BOOL",
    "~,NULL", "null,NULL", "Null,NULL", "NULL,NULL",
    "10,INT", "-10,INT", "+7,INT", "010,INT", "0o17,INT", "0x1F,INT", "0b101,INT", "1_000,INT", "0777,INT",
    "1.5,FLOAT", ".5,FLOAT", "1e3,FLOAT", "-1.5e+3,FLOAT", ".inf,FLOAT", "-.inf,FLOAT", ".nan,FLOAT", "1.,FLOAT", "1_0.5,FLOAT",
    "2026-09-01,TIMESTAMP", "2026-09-01T10:00:00Z,TIMESTAMP", "2026-09-01 10:00:00,TIMESTAMP", "2026-9-1 1:02:03 +5,TIMESTAMP",
    "2026-09-01T10:00:00.123456+05:30,TIMESTAMP",
    "<<,UNSUPPORTED", "=,UNSUPPORTED"
  })
  void theYaml12ImplicitResolversOfRuamelGiveEachPlainScalarItsType(String text, Yaml12.Type expected) {
    assertThat(Yaml12.resolve(text).type()).as(text).isEqualTo(expected);
  }

  @Test
  void theEmptyPlainScalarIsNull() {
    assertThat(Yaml12.resolve("").type()).isEqualTo(Yaml12.Type.NULL);
  }

  @Test
  void integersAreConstructedTheWayRuamelConstructsThem() {
    assertThat(Yaml12.resolve("0o17").value()).isEqualTo(BigInteger.valueOf(15));
    assertThat(Yaml12.resolve("0x1F").value()).isEqualTo(BigInteger.valueOf(31));
    assertThat(Yaml12.resolve("0b101").value()).isEqualTo(BigInteger.valueOf(5));
    assertThat(Yaml12.resolve("010").value()).as("YAML 1.2 has no leading-zero octal").isEqualTo(BigInteger.TEN);
    assertThat(Yaml12.resolve("0777").value()).isEqualTo(BigInteger.valueOf(777));
    assertThat(Yaml12.resolve("-1_000").value()).isEqualTo(BigInteger.valueOf(-1000));
    assertThat(Yaml12.resolve("+5").value()).isEqualTo(BigInteger.valueOf(5));
  }

  @Test
  void aValueRuamelsConstructorCannotBuildIsRefusedNotServed() {
    for (String text : new String[] {"-_", "0b_", "0x_", "0o_", "2026-13-01", "2026-02-30", "0000-01-01", "2026-09-01T25:00:00Z", "2026-09-01T10:61:00Z", "2026-09-01T10:00:61Z", "2026-09-01T10:00:00+24:00"}) {
      FrontmatterResult result = file(ID + "agent: " + text + "\n");
      assertThat(result).as(text).isInstanceOf(FrontmatterResult.Rejected.class);
    }
  }

  @Test
  void floatsAreConstructedWithInfinityAndNotANumber() {
    assertThat((Double) Yaml12.resolve("1_0.5").value()).isEqualTo(10.5);
    assertThat((Double) Yaml12.resolve("-.inf").value()).isEqualTo(Double.NEGATIVE_INFINITY);
    assertThat((Double) Yaml12.resolve(".INF").value()).isEqualTo(Double.POSITIVE_INFINITY);
    assertThat((Double) Yaml12.resolve(".NaN").value()).isNaN();
  }

  @Test
  void aQuotedOrBlockScalarIsAlwaysAString() {
    assertThat(parsed(ID + "priority: '010'\n").priority()).isEqualTo("010");
    assertThat(parsed(ID + "priority: \"yes\"\n").priority()).isEqualTo("yes");
    assertThat(parsed(ID + "priority: |\n  true\n").priority()).as("the YAML text has no trailing line feed").isEqualTo("true");
    assertThat(parsed(ID + "priority: >\n  a\n  b\n").priority()).isEqualTo("a b");
    assertThat(parsed(ID + "created_at: '2026-09-01'\n").workPackageId()).isEqualTo("WP01");
  }

  @Test
  void yesOnAndOctalLookingIntegersAreStringsWhereTheOracleServesStrings() {
    assertThat(parsed(ID + "task_type: on\n").taskType()).isEqualTo("on");
    assertThat(parsed(ID + "priority: yes\n").priority()).isEqualTo("yes");
    assertRejected(ID + "priority: 010\n", RejectionClass.VALIDATION);
    assertRejected(ID + "created_at: 2026-09-01\n", RejectionClass.VALIDATION);
    assertRejected(ID + "priority: true\n", RejectionClass.VALIDATION);
    assertRejected(ID + "priority: 1.5\n", RejectionClass.VALIDATION);
  }

  @Test
  void theThreeLineBreakCharactersThatYaml11FoldsAreRefusedBecauseYaml12KeepsThem() {
    for (String character : new String[] {"\u0085", "\u2028", "\u2029"}) {
      assertRejected(ID + "title: a" + character + "b\n", RejectionClass.UNSUPPORTED_YAML);
    }
    assertThat(decode("---\n" + ID + "---\nbody with \u2028 is not frontmatter\n")).as("only the YAML text is checked").isInstanceOf(FrontmatterResult.Parsed.class);
  }

  // ---- WPMetadata validation ---------------------------------------------------------------------------------------------------

  @Test
  void theKnownFieldsTheRoutesNeedAreKept() {
    WpMetadata metadata =
        parsed(
            ID
                + "title: A title\nphase: 2\ntask_type: code\npriority: high\nexecution_mode: code_change\nmerge_target_branch: main\n"
                + "planning_base_branch: plan\nrole: implementer\nagent_profile: java-jenny\nmodel: sonnet\n"
                + "dependencies: [WP02]\nrequirement_refs: [FR-001]\ntracker_refs: ['#5']\nowned_files: [a, b]\nsubtasks: [T001, T002]\n");
    assertThat(metadata.workPackageId()).isEqualTo("WP01");
    assertThat(metadata.title()).isEqualTo("A title");
    assertThat(metadata.phase()).as("coerce_phase: str(2)").isEqualTo("2");
    assertThat(metadata.taskType()).isEqualTo("code");
    assertThat(metadata.priority()).isEqualTo("high");
    assertThat(metadata.executionMode()).isEqualTo("code_change");
    assertThat(metadata.mergeTargetBranch()).isEqualTo("main");
    assertThat(metadata.planningBaseBranch()).isEqualTo("plan");
    assertThat(metadata.role()).isEqualTo("implementer");
    assertThat(metadata.agentProfile()).isEqualTo("java-jenny");
    assertThat(metadata.model()).isEqualTo("sonnet");
    assertThat(metadata.dependencies()).containsExactly("WP02");
    assertThat(metadata.requirementRefs()).containsExactly("FR-001");
    assertThat(metadata.trackerRefs()).containsExactly("#5");
    assertThat(metadata.ownedFiles()).containsExactly("a", "b");
    assertThat(metadata.subtasks()).containsExactly("T001", "T002");
    assertThat(metadata.subtasksRefused()).isFalse();
  }

  @Test
  void anAbsentMemberIsNullOrAnEmptyList() {
    WpMetadata metadata = parsed(ID);
    assertThat(metadata.title()).isNull();
    assertThat(metadata.phase()).isNull();
    assertThat(metadata.dependencies()).isEmpty();
    assertThat(metadata.requirementRefs()).isEmpty();
    assertThat(metadata.subtasks()).isEmpty();
  }

  @Test
  void anUnknownKeyIsRejectedAndSoIsAKeyThatIsNotAString() {
    assertRejected(ID + "mystery_key: 1\n", RejectionClass.VALIDATION);
    assertRejected(ID + "Title: x\n", RejectionClass.VALIDATION);
    assertRejected(ID + "1: x\n", RejectionClass.VALIDATION);
    assertRejected(ID + "true: x\n", RejectionClass.VALIDATION);
  }

  @Test
  void everyKnownKeyOfTheModelIsAccepted() {
    String all =
        ID
            + "title: t\ndependencies: []\nbase_branch: b\nbase_commit: abcdef1\ncreated_at: c\nplanning_base_branch: p\nmerge_target_branch: m\n"
            + "branch_strategy: s\nrequirement_refs: []\ntracker_refs: []\npriority: p\nexecution_mode: e\nowned_files: []\ncreate_intent: []\n"
            + "authoritative_surface: a\nscope: s\ntask_type: t\nsubtasks: []\nphase: p\nphases: ps\nassignee: a\nagent: claude\nmodel: m\n"
            + "agent_profile: a\nrole: r\nshell_pid: 12\nshell_pid_created_at: x\nhistory: []\nlane: planned\nfeature_slug: f\nactivity_log: a\n"
            + "review_status: r\nreviewed_by: r\napproved_by: a\nreviewer: x\nreviewer_agent: r\nreviewer_shell_pid: '1'\nreview_feedback: f\n"
            + "review_feedback_file: f\nsubtitle: s\ndescription: d\nestimated_duration: e\ntags: [a]\nmission_id: m\nmission_number: '1'\n"
            + "mission_slug: s\nstatus: s\nwp_code: w\nwork_package_title: wt\n";
    assertThat(file(all)).isInstanceOf(FrontmatterResult.Parsed.class);
  }

  @Test
  void aStringFieldRefusesAnythingThatIsNotAStringOrNull() {
    assertRejected(ID + "title: [a]\n", RejectionClass.VALIDATION);
    assertRejected(ID + "role: {a: b}\n", RejectionClass.VALIDATION);
    assertRejected(ID + "model: 5\n", RejectionClass.VALIDATION);
    assertRejected(ID + "phases: 5\n", RejectionClass.VALIDATION);
    assertThat(parsed(ID + "role:\n").role()).as("a null is allowed").isNull();
  }

  @Test
  void aTitleThatIsBlankIsRefusedAndTheLegacyTitleKeyFillsAnAbsentOne() {
    assertRejected(ID + "title: '   '\n", RejectionClass.VALIDATION);
    assertRejected(ID + "title: ''\n", RejectionClass.VALIDATION);
    assertThat(parsed(ID + "work_package_title: Old\n").title()).isEqualTo("Old");
    assertThat(parsed(ID + "title: New\nwork_package_title: Old\n").title()).isEqualTo("New");
    assertRejected(ID + "work_package_title: '  '\n", RejectionClass.VALIDATION);
  }

  @Test
  void theIdMustMatchWpAndTwoOrMoreDigitsAsPydanticReadsIt() {
    assertRejected("title: x\n", RejectionClass.VALIDATION);
    assertRejected("work_package_id: wp1\n", RejectionClass.VALIDATION);
    assertRejected("work_package_id: WP1\n", RejectionClass.VALIDATION);
    assertRejected("work_package_id: ''\n", RejectionClass.VALIDATION);
    assertRejected("work_package_id: 1\n", RejectionClass.VALIDATION);
    assertRejected("work_package_id:\n", RejectionClass.VALIDATION);
    assertThat(parsed("work_package_id: WP123\n").workPackageId()).isEqualTo("WP123");
    assertThat(parsed("work_package_id: \"WP01\\n\"\n").workPackageId()).as("the oracle's $ allows a trailing line feed").isEqualTo("WP01\n");
    assertThat(parsed("work_package_id: WP\u0661\u0662\n").workPackageId()).as("\\d is a Unicode digit").isEqualTo("WP\u0661\u0662");
  }

  @Test
  void aBaseCommitIsAHexShaOrUnknownOrNull() {
    assertThat(file(ID + "base_commit: abcdef1\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "base_commit: unknown\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "base_commit:\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertRejected(ID + "base_commit: abc\n", RejectionClass.VALIDATION);
    assertRejected(ID + "base_commit: ABCDEF1\n", RejectionClass.VALIDATION);
    assertRejected(ID + "base_commit: 1234567\n", RejectionClass.VALIDATION);
    assertRejected(ID + "base_commit: '1234567890123456789012345678901234567890a'\n", RejectionClass.VALIDATION);
  }

  /** J-S3a: CPython 3.11+ raises ValueError for a decimal int of more than 4300 digits (sys.int_info.default_max_str_digits); ruamel and int() both. */
  @Test
  void aDecimalIntOfMoreThan4300DigitsIsRefusedLikeTheOracleAndOneOf4300IsKept() {
    assertThat(file(ID + "shell_pid: " + "1".repeat(4300) + "\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertRejected(ID + "shell_pid: " + "1".repeat(4301) + "\n", RejectionClass.UNSUPPORTED_YAML);
    assertThat(file(ID + "shell_pid: 0x" + "1".repeat(5000) + "\n")).as("a power-of-two base has no limit").isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "shell_pid: '" + "1".repeat(4300) + "'\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertRejected(ID + "shell_pid: '" + "1".repeat(4301) + "'\n", RejectionClass.VALIDATION);
  }

  /** J-S3a: the digit-run pattern recursed once per underscore group; 20000 groups overflowed the stack. */
  @Test
  void aLongUnderscoreRunInAShellPidIsRefusedNotAStackOverflow() {
    assertRejected(ID + "shell_pid: '1" + "_1".repeat(20000) + "'\n", RejectionClass.VALIDATION);
    assertThat(Yaml12.pyInt("1" + "_1".repeat(20000))).isNull();
    assertThat(Yaml12.pyInt("1_1")).isEqualTo(BigInteger.valueOf(11));
    assertThat(Yaml12.pyInt("\ud835\udfd2\ud835\udfd3")).as("supplementary decimal digits").isEqualTo(BigInteger.valueOf(45));
  }

  @Test
  void aShellPidGoesThroughPythonInt() {
    for (String ok : new String[] {"12345", "'12345'", "' 12 '", "'1_000'", "'+5'", "''", "true", "1.5", "0x10", "'\u0661\u0662'", "~"}) {
      assertThat(file(ID + "shell_pid: " + ok + "\n")).as(ok).isInstanceOf(FrontmatterResult.Parsed.class);
    }
    for (String bad : new String[] {"abc", "'abc'", "'1__0'", "'_1'", "'0x10'", "'1.5'", ".nan", ".inf", "[1]", "{a: 1}", "2026-09-01"}) {
      assertRejected(ID + "shell_pid: " + bad + "\n", RejectionClass.VALIDATION);
    }
  }

  @Test
  void aLaneIsADisplayLaneOrTheDoingAliasOrEmpty() {
    for (String ok : new String[] {"planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done", "blocked", "canceled", "doing", "''", "~"}) {
      assertThat(file(ID + "lane: " + ok + "\n")).as(ok).isInstanceOf(FrontmatterResult.Parsed.class);
    }
    for (String bad : new String[] {"genesis", "uninitialized", "nonsense", "5", "true", "[planned]", "Planned"}) {
      assertRejected(ID + "lane: " + bad + "\n", RejectionClass.VALIDATION);
    }
  }

  @Test
  void theFreeShapeFieldsAcceptAMappingAScalarAndAListButTheirContentMustBeReadable() {
    assertThat(file(ID + "agent:\n  tool: claude\n  model: sonnet\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "agent: claude:sonnet:p:r\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "reviewer:\n  name: someone\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(file(ID + "history:\n- {a: 1}\n- [x, 2.5]\n- 2026-09-01\n")).isInstanceOf(FrontmatterResult.Parsed.class);
    assertRejected(ID + "history: nope\n", RejectionClass.VALIDATION);
    assertRejected(ID + "history:\n", RejectionClass.VALIDATION);
    assertRejected(ID + "subtasks: nope\n", RejectionClass.VALIDATION);
    assertRejected(ID + "subtasks: ~\n", RejectionClass.VALIDATION);
  }

  @Test
  void aListOfStringsRefusesAnItemThatIsNotAStringAndAScalarThatIsNotCoerced() {
    assertRejected(ID + "owned_files: [1]\n", RejectionClass.VALIDATION);
    assertRejected(ID + "owned_files: ['a', ~]\n", RejectionClass.VALIDATION);
    assertRejected(ID + "owned_files: a.txt\n", RejectionClass.VALIDATION);
    assertRejected(ID + "owned_files: {a: b}\n", RejectionClass.VALIDATION);
    assertRejected(ID + "tags: 5\n", RejectionClass.VALIDATION);
    assertRejected(ID + "create_intent:\n", RejectionClass.VALIDATION);
    assertRejected(ID + "dependencies:\n", RejectionClass.VALIDATION);
    assertRejected(ID + "dependencies: [WP01, 2]\n", RejectionClass.VALIDATION);
    assertRejected(ID + "dependencies: 2\n", RejectionClass.VALIDATION);
    assertThat(parsed(ID + "owned_files: []\n").ownedFiles()).isEmpty();
  }

  @Test
  void dependenciesWrittenAsAStringAreCoercedTheWayTheOracleCoercesThem() {
    assertThat(parsed(ID + "dependencies: '[]'\n").dependencies()).isEmpty();
    assertThat(parsed(ID + "dependencies: ' [] '\n").dependencies()).isEmpty();
    assertThat(parsed(ID + "dependencies: 'WP01, WP02'\n").dependencies()).containsExactly("WP01", "WP02");
    assertThat(parsed(ID + "dependencies: 'WP01'\n").dependencies()).containsExactly("WP01");
    assertThat(parsed(ID + "dependencies: ' WP01 ,, WP03 ,'\n").dependencies()).containsExactly("WP01", "WP03");
    assertThat(parsed(ID + "dependencies: ''\n").dependencies()).isEmpty();
  }

  @Test
  void requirementRefsWrittenAsAStringAreTokenisedOnCommasAndWhitespace() {
    assertThat(parsed(ID + "requirement_refs: 'FR-001, FR-002'\n").requirementRefs()).containsExactly("FR-001", "FR-002");
    assertThat(parsed(ID + "requirement_refs: 'FR-001 FR-002\tNFR-1\u00a0C-3'\n").requirementRefs())
        .as("the oracle's RE2 \\s is ASCII only: a no-break space does not split")
        .containsExactly("FR-001", "FR-002", "NFR-1\u00a0C-3");
    assertThat(parsed(ID + "requirement_refs: ' ,, '\n").requirementRefs()).isEmpty();
    assertThat(parsed(ID + "requirement_refs: 'FR-001'\n").requirementRefs()).containsExactly("FR-001");
    assertThat(parsed(ID + "requirement_refs: ['FR-001 FR-002']\n").requirementRefs()).as("a list keeps its items verbatim").containsExactly("FR-001 FR-002");
  }

  @Test
  void trackerRefsWrittenAsAStringAreSplitOnCommasOnly() {
    assertThat(parsed(ID + "tracker_refs: '#1298, JIRA-123'\n").trackerRefs()).containsExactly("#1298", "JIRA-123");
    assertThat(parsed(ID + "tracker_refs: '#1 #2'\n").trackerRefs()).containsExactly("#1 #2");
    assertThat(parsed(ID + "tracker_refs: ''\n").trackerRefs()).isEmpty();
  }

  @Test
  void aPhaseIsStringifiedAndOnlyWhereThatStringIsReproduced() {
    assertThat(parsed(ID + "phase: 3\n").phase()).isEqualTo("3");
    assertThat(parsed(ID + "phase: true\n").phase()).isEqualTo("True");
    assertThat(parsed(ID + "phase: Foundations\n").phase()).isEqualTo("Foundations");
    assertThat(parsed(ID + "phase:\n").phase()).isNull();
    assertThat(parsed(ID + "phase: 0o10\n").phase()).isEqualTo("8");
    assertThat(parsed(ID + "phase: 1.5\n").phase()).isEqualTo("1.5");
    assertThat(parsed(ID + "phase: 1e3\n").phase()).isEqualTo("1000.0");
    assertThat(parsed(ID + "phase: .nan\n").phase()).isEqualTo("nan");
    assertThat(parsed(ID + "phase: -.inf\n").phase()).isEqualTo("-inf");
    assertThat(parsed(ID + "phase: 2026-09-01\n").phase()).isEqualTo("2026-09-01");
    assertThat(parsed(ID + "phase: <<\n").phase()).isEqualTo("<<");
    assertRejected(ID + "phase: 1e20\n", RejectionClass.VALIDATION);
    assertRejected(ID + "phase: 0.00001\n", RejectionClass.VALIDATION);
    assertRejected(ID + "phase: 2026-09-01T10:00:00Z\n", RejectionClass.VALIDATION);
    assertRejected(ID + "phase: [1]\n", RejectionClass.VALIDATION);
    assertRejected(ID + "phase: {a: 1}\n", RejectionClass.VALIDATION);
  }

  @Test
  void subtasksAreStringifiedLikePythonAndAMappingOrListRefusesTheRoster() {
    WpMetadata scalars = parsed(ID + "subtasks: [T001, 7, true, ~, 'q']\n");
    assertThat(scalars.subtasks()).containsExactly("T001", "7", "True", "None", "q");
    assertThat(scalars.subtasksRefused()).isFalse();
    WpMetadata maps = parsed(ID + "subtasks:\n- id: T001\n- T002\n- [a]\n- 1.5\n- 2026-09-01T10:00:00Z\n");
    assertThat(maps.subtasks()).as("only what could be stringified").containsExactly("T002", "1.5");
    assertThat(maps.subtasksRefused()).isTrue();
    assertThat(parsed(ID + "subtasks: []\n").subtasksRefused()).isFalse();
  }

  // ---- helpers kept public for the other tests of the codec package -------------------------------------------------------------

  @Test
  void splitHelpersMatchPythonOnTheirEdges() {
    assertThat(WpFrontmatterCodec.splitTrackerRefs("")).isEmpty();
    assertThat(WpFrontmatterCodec.splitTrackerRefs(",")).isEmpty();
    assertThat(WpFrontmatterCodec.splitTrackerRefs("a,")).containsExactly("a");
    assertThat(WpFrontmatterCodec.splitRefs("")).isEmpty();
    assertThat(WpFrontmatterCodec.splitRefs("a\u2028b")).as("U+2028 is not an RE2 space").containsExactly("a\u2028b");
    assertThat(WpFrontmatterCodec.splitRefs("a\u000bb")).as("nor is a vertical tab").containsExactly("a\u000bb");
    assertThat(WpFrontmatterCodec.splitRefs("a\fb\r\nc")).containsExactly("a", "b", "c");
    assertThat(WpFrontmatterCodec.splitRefs("\u00a0 \u00a0,a")).as("a piece that is only Python whitespace is dropped").containsExactly("a");
    assertThat(WpFrontmatterCodec.splitRefs("a\ud83d\ude00b")).as("a supplementary character is not a separator").containsExactly("a\ud83d\ude00b");
    assertThat(WpFrontmatterCodec.legacyDependencies("[]")).isEmpty();
    assertThat(WpFrontmatterCodec.dropBom("")).isEmpty();
    assertThat(WpFrontmatterCodec.translateNewlines("a\r\nb\rc")).isEqualTo("a\nb\nc");
    assertThat(Yaml12.pyInt("12")).isEqualTo(BigInteger.valueOf(12));
    assertThat(Yaml12.pyInt("x")).isNull();
    assertThat(List.of(Yaml12.Type.values())).hasSize(7);
  }

  private static byte[] concat(byte[] first, byte[] second) {
    byte[] out = new byte[first.length + second.length];
    System.arraycopy(first, 0, out, 0, first.length);
    System.arraycopy(second, 0, out, first.length, second.length);
    return out;
  }
}
