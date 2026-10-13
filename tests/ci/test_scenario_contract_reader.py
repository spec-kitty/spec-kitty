"""Unit tests for the Gherkin subset reader, tag rules and step matcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import scenario_contract as sc

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse(text: str):
    return sc.parse_feature_text(text, "x.feature")


def codes(problems):
    return [p.code for p in problems]


# ---- reader ---------------------------------------------------------------


def test_keywords_and_star_inherit_previous_keyword():
    scenarios, problems = parse("Feature: F\n  Scenario: S\n    Given a\n    And b\n    When c\n    But d\n    * e\n    Then f\n    And g\n")
    assert problems == []
    assert [s.keyword for s in scenarios[0].steps] == [
        "Given",
        "Given",
        "When",
        "When",
        "When",
        "Then",
        "Then",
    ]
    assert [s.text for s in scenarios[0].steps] == list("abcdefg")
    assert scenarios[0].steps[0].line == 3


def test_leading_and_step_keyword_without_previous_is_parse_error():
    _, problems = parse("Feature: F\n  Scenario: S\n    And lonely\n")
    assert "PARSE_ERROR" in codes(problems)


def test_tags_inherit_feature_rule_scenario():
    scenarios, _ = parse("@f1\nFeature: F\n  Scenario: Outside\n    Given b\n  @r1\n  Rule: R\n    @s1 @s2\n    Scenario: S\n      Given a\n")
    assert scenarios[0].tags == ("f1",)
    assert scenarios[1].tags == ("f1", "r1", "s1", "s2")


def test_rule_tags_do_not_leak_to_next_rule():
    scenarios, _ = parse("Feature: F\n  @r1\n  Rule: A\n    Scenario: S1\n      Given a\n  Rule: B\n    Scenario: S2\n      Given b\n")
    assert scenarios[0].tags == ("r1",)
    assert scenarios[1].tags == ()


def test_comments_blank_lines_and_trailing_tag_comments():
    scenarios, problems = parse("# c\n\n@a # trailing\nFeature: F # c\n\n  # c\n  Scenario: S\n    Given a # not stripped from steps\n")
    assert problems == []
    assert scenarios[0].tags == ("a",)


def test_description_lines_are_allowed_before_first_step_only():
    scenarios, problems = parse("Feature: F\n  desc\n  more desc\n  Scenario: S\n    some description\n    Given a\n")
    assert problems == []
    assert len(scenarios[0].steps) == 1
    _, problems = parse("Feature: F\n  Scenario: S\n    Given a\n    stray\n")
    assert codes(problems) == ["PARSE_ERROR"]


def test_content_before_feature_is_parse_error():
    _, problems = parse("Scenario: S\n  Given a\n")
    assert set(codes(problems)) == {"PARSE_ERROR"}


def test_missing_feature_line_in_empty_file():
    _, problems = parse("# only a comment\n")
    assert codes(problems) == ["PARSE_ERROR"]


def test_doc_strings_and_tables_are_not_steps():
    scenarios, problems = parse(
        'Feature: F\n  Scenario: S\n    Given a\n      """\n      Given not a step\n      """\n'
        "      ```\n      When nor this\n      ```\n    Then b\n      | x | y |\n      | 1 | 2 |\n"
    )
    assert problems == []
    assert [s.text for s in scenarios[0].steps] == ["a", "b"]


def test_unterminated_doc_string_is_parse_error():
    _, problems = parse('Feature: F\n  Scenario: S\n    Given a\n      """\n      text\n')
    assert codes(problems) == ["PARSE_ERROR"]


def test_table_before_any_step_is_parse_error():
    _, problems = parse("Feature: F\n  Scenario: S\n    | x |\n")
    assert codes(problems) == ["PARSE_ERROR", "NO_STEPS"]


def test_background_steps_are_prepended():
    scenarios, _ = parse("Feature: F\n  Background:\n    Given bg\n  Scenario: S\n    When a\n")
    assert [s.text for s in scenarios[0].steps] == ["bg", "a"]


def test_background_is_scoped_to_its_rule():
    scenarios, _ = parse("Feature: F\n  Scenario: Before\n    Given a\n  Rule: R\n    Background:\n      Given rbg\n    Scenario: In\n      When b\n")
    assert [s.text for s in scenarios[0].steps] == ["a"]
    assert [s.text for s in scenarios[1].steps] == ["rbg", "b"]


def test_background_alone_does_not_count_as_scenario_steps():
    scenarios, problems = parse("Feature: F\n  Background:\n    Given bg\n  Scenario: S\n")
    assert codes(problems) == ["NO_STEPS"]
    assert scenarios[0].steps  # background step is carried


def test_outline_expands_per_row_and_block():
    scenarios, problems = parse(
        "Feature: F\n  Scenario Outline: O\n    Given <a> and <b>\n"
        "    Examples: one\n      | a | b |\n      | 1 | x |\n      | 2 | y |\n"
        "    Examples:\n      | a | b |\n      | 3 | z |\n"
    )
    assert problems == []
    assert [[s.text for s in sc.steps] for sc in scenarios] == [
        ["1 and x"],
        ["2 and y"],
        ["3 and z"],
    ]
    assert all(sc.keyword == "Scenario Outline" for sc in scenarios)


def test_outline_without_rows_reports_no_examples():
    scenarios, problems = parse("Feature: F\n  Scenario Outline: O\n    Given <a>\n    Examples:\n      | a |\n")
    assert codes(problems) == ["NO_EXAMPLES"]
    assert scenarios[0].steps[0].text == "<a>"
    _, problems = parse("Feature: F\n  Scenario Outline: O\n    Given <a>\n")
    assert codes(problems) == ["NO_EXAMPLES"]


def test_examples_without_header_is_parse_error():
    _, problems = parse("Feature: F\n  Scenario Outline: O\n    Given a\n    Examples:\n    stray\n")
    # "stray" is description text; the headerless Examples is still the error
    assert codes(problems) == ["PARSE_ERROR", "NO_EXAMPLES"]


def test_outline_row_with_wrong_cell_count_is_parse_error():
    _, problems = parse("Feature: F\n  Scenario Outline: O\n    Given <a>\n    Examples:\n      | a |\n      | 1 | 2 |\n")
    assert "PARSE_ERROR" in codes(problems)


def test_outline_unknown_placeholder_is_left_as_is():
    scenarios, _ = parse("Feature: F\n  Scenario Outline: O\n    Given <a> <zz>\n    Examples:\n      | a |\n      | 1 |\n")
    assert scenarios[0].steps[0].text == "1 <zz>"


def test_examples_outside_outline_is_parse_error():
    _, problems = parse("Feature: F\n  Scenario: S\n    Given a\n    Examples:\n      | a |\n")
    assert "PARSE_ERROR" in codes(problems)


def test_rule_and_background_are_rejected_before_feature():
    assert "PARSE_ERROR" in codes(parse("Rule: R\n")[1])
    assert "PARSE_ERROR" in codes(parse("Background:\n")[1])


def test_malformed_tag_and_step_outside_a_block():
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  @ok bad\n  Scenario: S\n    Given a\n")[1])
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  Examples:\n  Given a\n")[1])


def test_tags_before_background_and_dangling_tags_at_end_of_file():
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  @t\n  Background:\n    Given a\n")[1])
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  Scenario: S\n    Given a\n  @t\n")[1])


def test_tags_before_free_text_and_before_examples():
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  @t\n  text\n")[1])
    scenarios, problems = parse("Feature: F\n  Scenario Outline: O\n    Given <a>\n  @ex\n    Examples:\n      | a |\n      | 1 |\n")
    assert problems == [] and len(scenarios) == 1


def test_examples_table_without_rows_and_headerless_examples():
    _, problems = parse("Feature: F\n  Scenario Outline: O\n    Given a\n    Examples:\n")
    assert "NO_EXAMPLES" in codes(problems) and "PARSE_ERROR" in codes(problems)


def test_step_keyword_without_text_is_description_or_error():
    assert parse("Feature: F\n  Scenario: S\n    Given\n    Given a\n")[1] == []
    assert "PARSE_ERROR" in codes(parse("Feature: F\n  Scenario: S\n    Given a\n    Given\n")[1])


def test_doc_string_in_examples_is_parse_error():
    _, problems = parse('Feature: F\n  Scenario Outline: O\n    Given a\n    Examples:\n      """\n      x\n      """\n')
    assert "PARSE_ERROR" in codes(problems)


def test_second_rule_background_is_independent():
    scenarios, _ = parse(
        "Feature: F\n  Background:\n    Given fb\n  Rule: A\n    Background:\n      Given ab\n"
        "    Scenario: S1\n      When x\n  Rule: B\n    Scenario: S2\n      When y\n"
    )
    assert [s.text for s in scenarios[0].steps] == ["fb", "ab", "x"]
    assert [s.text for s in scenarios[1].steps] == ["fb", "y"]


def test_outline_row_with_escaped_pipe():
    scenarios, _ = parse("Feature: F\n  Scenario Outline: O\n    Given <a>\n    Examples:\n      | a |\n      | x\\|y |\n")
    assert scenarios[0].steps[0].text == "x|y"


def test_scenario_without_steps():
    _, problems = parse("Feature: F\n  Scenario: S\n")
    assert codes(problems) == ["NO_STEPS"]
    assert problems[0].line == 2


def test_example_keyword_alias_and_scenario_aliases():
    scenarios, problems = parse("Feature: F\n  Example: S\n    Given a\n")
    assert problems == []
    assert scenarios[0].keyword == "Scenario"


def test_tags_not_followed_by_scenario_are_dropped_with_error():
    _, problems = parse("Feature: F\n  @a\n  Given a\n")
    assert "PARSE_ERROR" in codes(problems)


def test_second_feature_line_is_parse_error():
    _, problems = parse("Feature: F\nFeature: G\n")
    assert "PARSE_ERROR" in codes(problems)


def test_parse_feature_reads_file_and_reports_unreadable(tmp_path):
    f = tmp_path / "a.feature"
    f.write_text("Feature: F\n  Scenario: S\n    Given a\n", encoding="utf-8")
    scenarios, problems = sc.parse_feature(f)
    assert problems == [] and scenarios[0].file == str(f)
    _, problems = sc.parse_feature(tmp_path / "missing.feature")
    assert codes(problems) == ["PARSE_ERROR"]
    f.write_bytes(b"\xff\xfe\x00bad")
    _, problems = sc.parse_feature(f)
    assert codes(problems) == ["PARSE_ERROR"]


# ---- tags -----------------------------------------------------------------


def scen(*tags: str):
    return sc.Scenario("x.feature", 1, "S", "Scenario", tuple(tags), (sc.Step("Given", "a", 2),))


@pytest.mark.parametrize(
    "tags,expected",
    [
        ((), []),
        (("promise:PR-1.a_b",), []),
        (("promise:PR-1.a",), []),
        (("promise:",), ["BAD_PROMISE_ID"]),
        (("promise:-x",), ["BAD_PROMISE_ID"]),
        (("promise:A", "promise:A"), ["DUPLICATE_PROMISE"]),
        (("promise:A", "promise:B"), []),
        (("wip", "wip-owner:pedro", "wip-since:2026-10-13"), []),
        (("wip",), ["WIP_MISSING_OWNER", "WIP_MISSING_SINCE"]),
        (("wip", "wip-owner:p"), ["WIP_MISSING_SINCE"]),
        (("wip", "wip-since:2026-10-13"), ["WIP_MISSING_OWNER"]),
        (("wip", "wip-owner:p", "wip-since:2026-13-01"), ["BAD_WIP_SINCE"]),
        (("wip", "wip-owner:p", "wip-since:26-1-1"), ["BAD_WIP_SINCE"]),
        (("wip", "wip-owner:.p", "wip-since:2026-10-13"), ["BAD_WIP_OWNER"]),
        (("wip-owner:p",), []),
        (("manual",), []),
        (("defect:42",), []),
        (("defect:0",), ["BAD_DEFECT"]),
        (("defect:-1",), ["BAD_DEFECT"]),
        (("defect:",), ["BAD_DEFECT"]),
        (("qa:abc-1.x_y",), []),
        (("qa:a/b",), ["BAD_QA_REF"]),
        (("smoke", "Slow_1-x"), []),
        (("-bad",), ["BAD_BARE_TAG"]),
        (("foo:bar",), ["UNKNOWN_PREFIXED_TAG"]),
        (("wip:x",), ["UNKNOWN_PREFIXED_TAG"]),
        (("manual:x",), ["UNKNOWN_PREFIXED_TAG"]),
    ],
)
def test_tag_rules(tags, expected):
    assert codes(sc.validate_tags(scen(*tags))) == expected


def test_is_gating():
    assert sc.is_gating(scen())
    assert not sc.is_gating(scen("wip"))
    assert not sc.is_gating(scen("manual"))


# ---- expressions ----------------------------------------------------------


@pytest.mark.parametrize(
    "expr,text,ok",
    [
        ("I run {string}", 'I run "x y"', True),
        ("I run {string}", "I run 'x y'", True),
        ("I run {string}", "I run x", False),
        ("count {int}", "count -12", True),
        ("count {int}", "count 1.5", False),
        ("word {word}", "word abc", True),
        ("word {word}", "word a b", False),
        (r"a \(b\) c.", "a (b) c.", True),
        (r"a \(b\) c.", "a (b) cx", False),
        (r"a \{b\} d\/e", "a {b} d/e", True),
        ("exact", "exact plus", False),
        ("exact", "xexact", False),
    ],
)
def test_expression_regex(expr, text, ok):
    assert bool(sc.expression_to_regex(expr).fullmatch(text)) is ok


@pytest.mark.parametrize("expr", ["a{s}", "{float}", "{}", "{int", "cuke(s)", "(optional) text", "a/b", "{int}/{int}"])
def test_unsupported_expressions_raise(expr):
    with pytest.raises(sc.UnsupportedExpression, match="not supported"):
        sc.expression_to_regex(expr)


def test_trailing_backslash_is_a_literal_backslash():
    assert sc.expression_to_regex("a\\").fullmatch("a\\")


def test_decode_java_string():
    raw = "a" + chr(92) + '"b' + chr(92) * 2 + "c" + chr(92) + "nd" + chr(92) + "te" + chr(92) + "u0041" + chr(92) + "'"
    assert sc.decode_java_string(raw) == 'a"b' + chr(92) + "c\nd\teA'"
    assert sc.decode_java_string(r"x\qy") == r"x\qy"


# ---- step definitions -----------------------------------------------------


def write_java(tmp_path, body: str, name="S.java"):
    steps = tmp_path / "steps"
    steps.mkdir(parents=True, exist_ok=True)
    (steps / name).write_text(body, encoding="utf-8")
    return tmp_path


def test_load_step_definitions_from_nested_steps_dirs(tmp_path):
    nested = tmp_path / "a" / "steps"
    nested.mkdir(parents=True)
    (nested / "X.java").write_text(
        'class X {\n  @Given("one {string}")\n  void a() {}\n  @When("two \\"q\\"")\n  void b() {}\n  @Then("three")\n  void c() {}\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "a" / "Other.java").write_text('@Given("ignored")', encoding="utf-8")
    defs, problems = sc.load_step_definitions(tmp_path)
    assert problems == []
    assert [(d.keyword, d.expression) for d in defs] == [
        ("Given", "one {string}"),
        ("When", 'two "q"'),
        ("Then", "three"),
    ]
    assert defs[0].source.endswith("X.java:2")


def test_load_step_definitions_reports_unsupported_and_keeps_the_rest(tmp_path):
    write_java(tmp_path, '@Given("ok")\n@Given("bad{x}")\n')
    defs, problems = sc.load_step_definitions(tmp_path)
    assert [d.expression for d in defs] == ["ok"]
    assert codes(problems) == ["UNSUPPORTED_EXPRESSION"]
    assert problems[0].line == 2


def test_load_step_definitions_with_no_java_reports_problem(tmp_path):
    defs, problems = sc.load_step_definitions(tmp_path)
    assert defs == [] and codes(problems) == ["NO_STEP_DEFINITIONS"]


def test_load_step_definitions_unreadable_file(tmp_path):
    steps = write_java(tmp_path, "")
    (steps / "steps" / "Bin.java").write_bytes(b"\xff\xfe\x00")
    _, problems = sc.load_step_definitions(tmp_path)
    assert codes(problems) == ["STEP_FILE_UNREADABLE", "NO_STEP_DEFINITIONS"]


# ---- matching and checking ------------------------------------------------


def defs_for(*exprs: str):
    return [sc.StepDefinition("Given", e, f"S.java:{i}", sc.expression_to_regex(e)) for i, e in enumerate(exprs, 1)]


def test_match_steps_ignores_keyword_and_reports_unbound_and_ambiguous():
    s = sc.Scenario(
        "x.feature",
        1,
        "S",
        "Scenario",
        (),
        (sc.Step("When", "a thing", 2), sc.Step("Then", "nope", 3), sc.Step("Given", "a thing", 4)),
    )
    problems = sc.match_steps(s, defs_for("a thing", "a {word}"))
    assert [(p.code, p.line) for p in problems] == [
        ("AMBIGUOUS_STEP", 2),
        ("UNBOUND_STEP", 3),
        ("AMBIGUOUS_STEP", 4),
    ]


def test_single_match_is_clean_whatever_the_keyword():
    s = sc.Scenario("x.feature", 1, "S", "Scenario", (), (sc.Step("Then", "a thing", 2),))
    assert sc.match_steps(s, defs_for("a thing")) == []


def test_ambiguous_message_names_both_sources():
    s = sc.Scenario("x.feature", 1, "S", "Scenario", (), (sc.Step("Given", "a thing", 2),))
    problems = sc.match_steps(s, defs_for("a thing", "a {word}"))
    assert codes(problems) == ["AMBIGUOUS_STEP"]
    assert "S.java:1" in problems[0].message and "S.java:2" in problems[0].message


def test_unbound_in_non_gating_scenario_is_info():
    s = sc.Scenario("x.feature", 1, "S", "Scenario", ("wip",), (sc.Step("Given", "zzz", 2),))
    problems = sc.match_steps(s, defs_for("a thing"))
    assert [(p.code, p.severity) for p in problems] == [("UNBOUND_STEP", "info")]


def test_ambiguous_in_non_gating_scenario_is_info():
    s = sc.Scenario("x.feature", 1, "S", "Scenario", ("manual",), (sc.Step("Given", "a thing", 2),))
    problems = sc.match_steps(s, defs_for("a thing", "a {word}"))
    assert [(p.code, p.severity) for p in problems] == [("AMBIGUOUS_STEP", "info")]


# ---- tree and CLI ---------------------------------------------------------


def make_tree(tmp_path, feature: str | None, java: str = '@Given("a")\n'):
    features = tmp_path / "features"
    features.mkdir()
    if feature is not None:
        (features / "a.feature").write_text(feature, encoding="utf-8")
    write_java(tmp_path / "j", java)
    return features, tmp_path / "j"


def test_check_tree_clean(tmp_path):
    features, steps = make_tree(tmp_path, "Feature: F\n  Scenario: S\n    Given a\n")
    assert sc.check_tree(features, steps) == []


def test_check_tree_requires_features_and_a_gating_scenario(tmp_path):
    features, steps = make_tree(tmp_path, None)
    assert codes(sc.check_tree(features, steps)) == ["NO_FEATURES"]
    (tmp_path / "features" / "a.feature").write_text(
        "@wip @wip-owner:p @wip-since:2026-10-13\nFeature: F\n  Scenario: S\n    Given a\n",
        encoding="utf-8",
    )
    assert codes(sc.check_tree(features, steps)) == ["NO_GATING_SCENARIOS"]


def test_check_tree_missing_directories(tmp_path):
    problems = sc.check_tree(tmp_path / "nope", tmp_path / "also-nope")
    assert "NO_FEATURES" in codes(problems)
    assert "NO_STEP_DEFINITIONS" in codes(problems)


def test_main_prints_problems_and_exit_codes(tmp_path, capsys):
    features, steps = make_tree(tmp_path, "Feature: F\n  Scenario: S\n    Given zzz\n")
    assert sc.main(["--features", str(features), "--steps", str(steps)]) == 1
    out = capsys.readouterr().out
    assert "UNBOUND_STEP" in out and "a.feature:3" in out
    (features / "a.feature").write_text("Feature: F\n  Scenario: S\n    Given a\n", encoding="utf-8")
    assert sc.main(["--features", str(features), "--steps", str(steps)]) == 0
    assert "ok" in capsys.readouterr().out.lower()


def test_main_prints_info_without_failing(tmp_path, capsys):
    features, steps = make_tree(
        tmp_path,
        "Feature: F\n  Scenario: S\n    Given a\n  @wip @wip-owner:p @wip-since:2026-10-13\n  Scenario: W\n    Given zzz\n",
    )
    assert sc.main(["--features", str(features), "--steps", str(steps)]) == 0
    assert "info" in capsys.readouterr().out.lower()


def test_main_defaults_resolve_to_repo_tree(capsys):
    assert sc.main([]) == 0


def test_format_problems_is_stable():
    p = sc.Problem("X_CODE", "error", "f.feature", 3, "msg")
    assert sc.format_problems([p]) == "f.feature:3: error X_CODE: msg"


def test_star_step_may_open_a_scenario():
    scenarios, problems = parse("Feature: F\n  Scenario: S\n    * a\n    * b\n    Then c\n")
    assert problems == []
    assert [s.keyword for s in scenarios[0].steps] == ["*", "*", "Then"]
    assert [s.text for s in scenarios[0].steps] == ["a", "b", "c"]


def test_and_after_star_opener_is_accepted():
    scenarios, problems = parse("Feature: F\n  Scenario: S\n    * a\n    And b\n")
    assert problems == []
    assert [s.keyword for s in scenarios[0].steps] == ["*", "*"]


def test_description_under_examples_before_the_table_is_accepted():
    text = "Feature: F\n  Scenario Outline: O\n    Given <x>\n    Examples:\n      some words about the data\n      | x |\n      | 1 |\n"
    scenarios, problems = parse(text)
    assert problems == []
    assert len(scenarios) == 1


def test_text_under_examples_after_rows_is_still_an_error():
    text = "Feature: F\n  Scenario Outline: O\n    Given <x>\n    Examples:\n      | x |\n      | 1 |\n      stray\n"
    assert codes(parse(text)[1]) == ["PARSE_ERROR"]


def test_description_under_rule_is_accepted():
    scenarios, problems = parse("Feature: F\n  Rule: R\n    about the rule\n    Scenario: S\n      Given a\n")
    assert problems == []
    assert len(scenarios) == 1


@pytest.mark.parametrize("header", ["Feature: F\n", "Feature: F\n  Rule: R\n"])
def test_step_keyword_description_under_feature_or_rule_is_accepted(header):
    text = header + "    Given a free sentence\n    When something is described\n    And more\n  Scenario: S\n    Given a\n"
    scenarios, problems = parse(text)
    assert problems == []
    assert [s.text for s in scenarios[0].steps] == ["a"]


def test_step_keyword_line_before_feature_is_still_an_error():
    assert "PARSE_ERROR" in codes(parse("Given a\nFeature: F\n  Scenario: S\n    Given a\n")[1])


def test_step_keyword_line_under_scenario_is_a_step_not_description():
    scenarios, problems = parse("Feature: F\n  Scenario: S\n    Given a\n    When b\n")
    assert problems == []
    assert len(scenarios[0].steps) == 2


@pytest.mark.parametrize("expr", ["^a step$", "^a step", "a step$"])
def test_regex_anchored_expressions_are_unsupported(expr):
    with pytest.raises(sc.UnsupportedExpression, match="regular expression"):
        sc.expression_to_regex(expr)


def test_escaped_trailing_dollar_is_a_literal():
    assert sc.expression_to_regex("costs 5\\$").fullmatch("costs 5$")


# ---- comments in step-definition sources -----------------------------------

COMMENTED_JAVA = (
    "class S {\n"
    '  // @Given("line commented")\n'
    '  /* @When("block commented") */\n'
    "  /*\n"
    '   * @Then("multi line commented")\n'
    "   */\n"
    '  @Given("real")\n'
    '  @When("keeps \\\\/\\\\/ and \\\\/* inside")\n'
    '  char c = \'"\'; // @Then("after a char literal")\n'
    '  String t = """\n'
    "      /* inside a text block this opens no comment\n"
    '      """;\n'
    '  @Then("last")\n'
    "}\n"
)


def test_commented_out_step_definitions_are_not_read(tmp_path):
    defs, problems = sc.load_step_definitions(write_java(tmp_path, COMMENTED_JAVA))
    assert problems == []
    assert [d.expression for d in defs] == ["real", "keeps \\/\\/ and \\/* inside", "last"]
    assert [d.source for d in defs] == ["S.java:7", "S.java:8", "S.java:13"]


def test_step_bound_only_by_a_commented_annotation_is_unbound(tmp_path):
    features, steps = make_tree(tmp_path, "Feature: F\n  Scenario: S\n    Given real\n    When block commented\n", java=COMMENTED_JAVA)
    problems = sc.check_tree(features, steps)
    assert [(p.code, p.line) for p in problems] == [("UNBOUND_STEP", 4)]


@pytest.mark.parametrize(
    "source,expected",
    [
        ('a // c "x"', "a         "),
        ("a /* c\nd */ b", "a     \n     b"),
        ("a /* never closed\nx", "a                \n "),
        ('s = "q\\" // still in string"; // c', 's = "q\\" // still in string";     '),
        ('s = "open\n// c', 's = "open\n    '),
        ("c = '/'; // c", "c = '/';     "),
        ('t = """\n/* x\n""" // c', 't = """\n/* x\n"""     '),
        ('t = """ never closed /* x', 't = """ never closed /* x'),
    ],
)
def test_strip_java_comments(source, expected):
    stripped = sc.strip_java_comments(source)
    assert stripped == expected
    assert stripped.count("\n") == source.count("\n")


def test_feature_without_scenarios_is_an_error():
    scenarios, problems = parse("Feature: F\n  Scenaro: typo\n    Given a\n")
    assert scenarios == []
    assert [(p.code, p.line) for p in problems] == [("NO_SCENARIOS", 1)]
    _, problems = parse("@t\n# c\nFeature: F\n  Background:\n    Given a\n")
    assert [(p.code, p.line) for p in problems] == [("NO_SCENARIOS", 3)]


def test_file_without_feature_line_reports_only_the_parse_error():
    assert set(codes(parse("Scenaro: typo\n")[1])) == {"PARSE_ERROR"}


# ---- tags on Examples blocks ------------------------------------------------

TAGGED_EXAMPLES = (
    "@f\nFeature: F\n  @o\n  Scenario Outline: O\n    Given <x>\n"
    "    Examples: ratified\n      | x |\n      | a |\n"
    "    @wip @wip-owner:pedro @wip-since:2026-10-13\n    Examples: drafted\n      | x |\n      | zzz |\n"
)


def test_examples_tags_are_merged_into_each_row():
    scenarios, problems = parse(TAGGED_EXAMPLES)
    assert problems == []
    assert [s.tags for s in scenarios] == [
        ("f", "o"),
        ("f", "o", "wip", "wip-owner:pedro", "wip-since:2026-10-13"),
    ]


def test_wip_examples_rows_are_not_gating(tmp_path):
    features, steps = make_tree(tmp_path, TAGGED_EXAMPLES)
    problems = sc.check_tree(features, steps)
    assert [(p.code, p.severity, p.line) for p in problems] == [("UNBOUND_STEP", "info", 5)]


def test_examples_tags_are_validated(tmp_path):
    text = "Feature: F\n  Scenario Outline: O\n    Given <x>\n    @foo:bar @wip\n    Examples:\n      | x |\n      | a |\n"
    features, steps = make_tree(tmp_path, text)
    assert codes(sc.check_tree(features, steps)) == ["UNKNOWN_PREFIXED_TAG", "WIP_MISSING_OWNER", "WIP_MISSING_SINCE", "NO_GATING_SCENARIOS"]


# ---- landing-review strengthening ------------------------------------------


def test_step_must_match_the_whole_expression():
    s = sc.Scenario("x.feature", 1, "S", "Scenario", (), (sc.Step("Given", "a thing and more", 2), sc.Step("Given", "the a thing", 3)))
    assert [(p.code, p.line) for p in sc.match_steps(s, defs_for("a thing"))] == [("UNBOUND_STEP", 2), ("UNBOUND_STEP", 3)]


def test_crlf_line_endings_are_read_like_lf():
    text = "@t\r\nFeature: F\r\n  Background:\r\n    Given bg\r\n  Scenario: S\r\n    Given a\r\n      | x |\r\n    Then b\r\n"
    scenarios, problems = parse(text)
    assert problems == []
    assert scenarios[0].tags == ("t",)
    assert [(s.text, s.line) for s in scenarios[0].steps] == [("bg", 4), ("a", 6), ("b", 8)]


def test_unbound_background_step_of_a_gating_scenario_is_an_error(tmp_path):
    features, steps = make_tree(tmp_path, "Feature: F\n  Background:\n    Given zzz\n  Scenario: S\n    Given a\n")
    problems = sc.check_tree(features, steps)
    assert [(p.code, p.severity, p.line) for p in problems] == [("UNBOUND_STEP", "error", 3)]


def test_outline_placeholder_inside_a_quoted_string_and_unbound_rows(tmp_path):
    feature = (
        'Feature: F\n  Scenario Outline: O\n    Given a named "<name>"\n    When I count <n> things\n'
        "    Examples:\n      | name      | n    |\n      | bob       | 1    |\n      | two words | many |\n"
        "      | carol     | lots |\n      | dave      | lots |\n"
    )
    java = '@Given("a named {string}")\n@When("I count {int} things")\n'
    features, steps = make_tree(tmp_path, feature, java=java)
    problems = sc.check_tree(features, steps)
    assert [(p.code, p.line, p.message) for p in problems] == [
        ("UNBOUND_STEP", 4, "no step definition matches 'I count many things'"),
        ("UNBOUND_STEP", 4, "no step definition matches 'I count lots things'"),
    ]
