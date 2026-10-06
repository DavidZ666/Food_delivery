# AI Use and Provenance

## Restaurant menu browsing

- Student(s): GitHub `freesialuo`
- Artifact: `app/main.py`; `app/routes/menu.py`; `app/services/menu_service.py`;
  `app/repositories/product_repo.py`; `app/schemas/menu.py`;
  `tests/test_menu.py`; `README.md`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Implement restaurant menu and menu-item reads for #20.
- Influence: Generated the API contract, layered implementation, isolated tests
  and documentation; reused stored product fields and restaurant relationships.
- Validation: 37 tests passed on Python 3.14.7, including resource errors,
  ownership, storage failures, unchanged files and OpenAPI. Whitespace checks
  passed.
- References: [FastAPI additional responses](https://fastapi.tiangolo.com/advanced/additional-responses/),
  [response models](https://fastapi.tiangolo.com/tutorial/response-model/),
  [path operations](https://fastapi.tiangolo.com/reference/fastapi/).

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
