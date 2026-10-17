# AI Use and Provenance

## Response body failure handling (#55)

- Student(s): Zihan Tao GitHub `freesialuo`
- Artifact: `frontend/js/api.js`; `tests/frontend/api.test.mjs`;
  `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose and influence: Convert interrupted response-body reads into
  `ApiError` so forms show failure feedback; add regression tests.
- Validation: 201 pytest and 16 Node.js tests passed, including interrupted
  bodies for HTTP 201, 422 and 500; `git diff --check` passed.
- Reference: [Fetch response handling](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#handling_the_response).

## Frontend skeleton and restaurant creation form (#50)

- Student(s): Spencer Stephen (GitHub `SpencerS04`)
- Artifact: `app/main.py`; `frontend/`; `tests/test_frontend.py`;
  `tests/frontend/`; `.github/workflows/ci.yml`; `README.md`;
  `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: Claude Code (Claude Opus 5.5)
- Purpose: Serve a basic frontend from FastAPI and build the restaurant
  creation form for #50 (part of #32).
- Influence: Generated the StaticFiles mount, the shared API request helper,
  the form logic and page, Python and Node.js tests, the CI step and the
  documentation. Serving the frontend from the API's origin was chosen to avoid
  a separate server and CORS configuration.
- Validation: 201 pytest tests and 13 Node.js tests passed locally (Python
  3.14.2, Node.js 22.15). The form was checked in a browser against a temporary
  data directory: a created restaurant was shown with its new ID and was read
  back after a restart; blank required fields were flagged; simulated 422 and
  network-failure responses showed field and request errors.
- References: [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/),
  [Node.js test runner](https://nodejs.org/api/test.html),
  [MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData).

## Restaurant creation and persistent writes (#24, #25)

- Student(s): Zihan Tao GitHub `freesialuo`
- Artifact: `app/{routes,services,repositories,schemas}/`,
  `tests/test_restaurant_creation.py`, `tests/test_json_writes.py`, `README.md`,
  `docs/decisions/json-writes.md`, `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose and influence: Implement validated restaurant creation, serialized
  atomic JSON transactions, isolated tests and API/design documentation.
- Validation: Full pytest suite on Python 3.14.7, including fresh-process
  persistence, concurrent creation and write-failure cases; `git diff --check`.
- Integration with name search (#22): OpenAI Codex resolved the service,
  README and provenance conflicts while retaining both features and records.
  Added a create-then-search regression test; 121 tests passed on Python 3.14.7
  and `git diff --check` passed.
- References: [FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/),
  [response status codes](https://fastapi.tiangolo.com/tutorial/response-status-code/),
  [Python temporary files](https://docs.python.org/3/library/tempfile.html),
  [os.replace](https://docs.python.org/3/library/os.html#os.replace).

## Restaurant name search

- Student(s): Zihan Tao GitHub `freesialuo`
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

## Restaurant menu browsing

- Student(s): Zihan Tao GitHub `freesialuo`
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

- Student(s): Zihan Tao GitHub `freesialuo`
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

- Student(s): Zihan Tao GitHub `freesialuo`
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

- Student(s): Zihan Tao GitHub `freesialuo`
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
