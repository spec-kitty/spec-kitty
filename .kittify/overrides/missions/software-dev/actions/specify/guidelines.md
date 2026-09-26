# Specify Action — Governance Guidelines

These guidelines govern the quality and authorship standards for mission specification work in the software-dev mission. They were extracted from the command template and are injected at runtime via the charter context bootstrap.

---

## Core Authorship Focus

- Focus on **WHAT** users need and **WHY**.
- Avoid HOW to implement (no tech stack, APIs, code structure).
- Write for business stakeholders, not developers.
- Do NOT create checklists embedded in the spec itself — that is handled by a separate command.

---

## Section Requirements

- **Mandatory sections**: Must be completed for every feature.
- **Optional sections**: Include only when relevant to the feature.
- When a section doesn't apply, remove it entirely — do not leave it as "N/A".

---

## Requirement Writing Standards

- Do not mix functional, non-functional, and constraint requirements in one list.
- Do not emit requirements without stable IDs (`FR-###`, `NFR-###`, `C-###`).
- Do not leave requirement status fields empty.
- Do not write non-functional requirements without measurable thresholds.
- Do not proceed to planning with unresolved requirement quality checklist failures.

---

## AI Generation Rules

When creating a spec from a user prompt:

1. **Make informed guesses**: Use context, industry standards, and common patterns to fill gaps.
2. **Document assumptions**: Record reasonable defaults in the Assumptions section.
3. **Limit clarifications**: Maximum 3 `[NEEDS CLARIFICATION]` markers — use only for critical decisions that:
   - Significantly impact feature scope or user experience
   - Have multiple reasonable interpretations with different implications
   - Lack any reasonable default
4. **Prioritize clarifications**: scope > security/privacy > user experience > technical details
5. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item.
6. **Common areas needing clarification** (only if no reasonable default exists):
   - Feature scope and boundaries (include/exclude specific use cases)
   - User types and permissions (if multiple conflicting interpretations possible)
   - Security/compliance requirements (when legally/financially significant)

**Examples of reasonable defaults** (do not ask about these):

- Data retention: Industry-standard practices for the domain
- Performance targets: Standard web/mobile app expectations unless specified
- Error handling: User-friendly messages with appropriate fallbacks
- Authentication method: Standard session-based or OAuth2 for web apps
- Integration patterns: RESTful APIs unless specified otherwise

---

## Success Criteria Standards

Success criteria must be:

1. **Measurable**: Include specific metrics (time, percentage, count, rate)
2. **Technology-agnostic**: No mention of frameworks, languages, databases, or tools
3. **User-focused**: Describe outcomes from user/business perspective, not system internals
4. **Verifiable**: Can be tested/validated without knowing implementation details

**Good examples**:

- "Users can complete checkout in under 3 minutes"
- "System supports 10,000 concurrent users"
- "95% of searches return results in under 1 second"
- "Task completion rate improves by 40%"

**Bad examples** (implementation-focused):

- "API response time is under 200ms" — too technical, use "Users see results instantly"
- "Database can handle 1000 TPS" — implementation detail, use user-facing metric
- "React components render efficiently" — framework-specific
- "Redis cache hit rate above 80%" — technology-specific
