# AI Use and Provenance

## Restaurant name search

- Student(s): GitHub `freesialuo`
- Artifact: `app/routes/restaurants.py`; `app/services/restaurant_service.py`;
  `tests/test_restaurant_search.py`; `README.md`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Implement restaurant name search for #19.
- Influence: Generated optional query handling, case-insensitive substring
  matching, isolated tests, OpenAPI descriptions and documentation.
- Validation: 30 tests passed on Python 3.14.7, covering search behavior,
  unchanged storage, storage errors and OpenAPI. The diff passed whitespace
  checks.
- Commit: `6e08e718bf63324d5e0781143eee4531883e214f`
- References: [FastAPI query parameters](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/),
  [parameter reference](https://fastapi.tiangolo.com/reference/parameters/),
  [response models](https://fastapi.tiangolo.com/tutorial/response-model/).

## CI test reports

- Student(s): Zihan Tao
- Artifact: `.github/workflows/ci.yml`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Improve automated test reporting.
- Influence: Generated pytest validation, JUnit report upload, dependency caching,
  a job timeout and provenance documentation.
- Validation: 11 tests passed on Python 3.14.3; verified JUnit output, workflow
  YAML and the diff.
- PR: #15

## Test result summaries

- Student(s): Zihan Tao
- Artifact: `scripts/summarize_tests.py`; `tests/test_test_summary.py`;
  `.github/workflows/ci.yml`; `README.md`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Publish readable test results for #14.
- Influence: Generated the JUnit summary renderer, workflow integration, tests,
  usage documentation and provenance documentation.
- Validation: 18 tests passed on Python 3.14.3. A separate run verified pass,
  failure, skip and setup-error counts; tests cover missing reports and escaping.
- Revalidation: The current CI branch suite passed all 18 tests on Python 3.14.7.
- PR: #15
- References: [pytest JUnit reports](https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files),
  [GitHub job summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary).

## Restaurant details

- Student(s): GitHub `freesialuo`
- Artifact: `app/routes/restaurants.py`; `app/services/restaurant_service.py`;
  `app/repositories/restaurant_repo.py`; `app/schemas/error.py`;
  `tests/test_restaurant_details.py`; `README.md`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Implement restaurant details for #16.
- Influence: Generated the layered lookup, missing-resource handling, OpenAPI
  descriptions, isolated tests and documentation.
- Validation: 30 tests passed on Python 3.14.7 after CI integration, covering
  valid and invalid IDs, missing restaurants, storage errors, response fields,
  OpenAPI and test-report summaries. The diff passed whitespace checks.
- PR: #17
- References: [FastAPI errors](https://fastapi.tiangolo.com/tutorial/handling-errors/),
  [path parameters](https://fastapi.tiangolo.com/tutorial/path-params/),
  [additional responses](https://fastapi.tiangolo.com/advanced/additional-responses/).
