# AI Use and Provenance

## Entry 1

- Student(s): Zihan Tao
- Artifact: `.github/workflows/ci.yml`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Review the Milestone 1 automated-test requirements and improve the
  existing GitHub Actions test workflow.
- Influence: Generated and adapted the CI changes that add strict pytest
  validation, a JUnit test report, report upload after successful or failed test
  runs, an explicit dependency-cache key, and a test-job timeout. Also generated
  this provenance entry from the course-provided template.
- Validation: Ran the CI pytest command locally with Python 3.14.3 and confirmed
  that all 11 tests passed and a JUnit XML report was produced. Parsed the
  workflow as YAML, ran `git diff --check`, and reviewed the workflow against
  the project requirements and official GitHub Actions documentation.
