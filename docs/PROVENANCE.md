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

## Entry 2

- Student(s): Zihan Tao
- Artifact: `scripts/summarize_tests.py`; `tests/test_test_summary.py`;
  `.github/workflows/ci.yml`; `README.md`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Complete Task #14 by publishing readable automated test results.
- Influence: Added a standard-library JUnit summary renderer, an always-run
  summary step, report documentation, and tests for result counts, failure
  names, unavailable reports, and HTML escaping. Retained read-only workflow
  permissions and the existing 7-day artifact retention.
- Validation: All 18 project tests passed on Python 3.14.3. A separate pytest
  run with one pass, failure, skip, and setup error returned exit code 1;
  the renderer reported the matching counts and failure names. Checked the
  complete workflow diff and ran `git diff --check`.
- References (retrieved with Exa):
  - https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
