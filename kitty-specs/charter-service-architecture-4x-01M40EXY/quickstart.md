# Review Quickstart

1. Read the new charter redesign ADR first.
2. Confirm that its staged ownership table says:
   - Python writes initially;
   - Java reads after conformance;
   - Java writes migrate later.
3. Open the linked living C4 views and verify their names and relationships
   match the ADR.
4. Open the 4.x roadmap and verify:
   - read service → #645 / 4.x Work;
   - write migration → #2519 / CLI 4.x stable;
   - neither → milestone 11.
5. Check that architecture vision and domain planning pages link to the ADR
   without repeating the decision.
6. Confirm that round-trip parity includes a confined-mutation witness.
7. Search the changed canonical pages for unqualified performance, token, or
   adoption claims; there should be none.
