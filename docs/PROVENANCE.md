# AI Use and Provenance

## Restaurant edit request handling (#51, PR #57)

- Student(s): Zihan Tao (GitHub `freesialuo`)
- Artifact: `frontend/js/edit-restaurant.js`;
  `tests/frontend/edit-restaurant.test.mjs`; `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose and influence: Lock selection and inputs during saves, ignore loads
  after clearing the selection, and add page-level regression tests.
- Validation: 232 pytest and 30 Node.js tests passed; regression tests cover
  delayed loads, save locking, and rejected edits; `git diff --check` passed.
- Reference: [Node.js test mocks](https://nodejs.org/docs/latest-v22.x/api/test.html#mocking).

## Restaurant update form (#51)

- Student(s): Spencer Stephen (GitHub `SpencerS04`)
- Artifact: `frontend/edit-restaurant.html`, `frontend/js/edit-restaurant.js`,
  `frontend/js/form-ui.js`, `frontend/js/restaurant-form.js`, small changes to
  the create page and home page, `tests/test_frontend.py`, `tests/frontend/`,
  `README.md`
- Label: AI-GENERATED
- AI tool: Claude Code (Claude Opus 5.5)
- Purpose: Edit form for existing restaurants (#51, part of #32).
- Influence: Wrote the edit page and the logic that only sends changed fields
  in the PATCH (cleared optional fields get sent as null). Moved the status and
  error display code into `form-ui.js` so both forms use it. Also wrote the
  tests and README section.
- Validation: 232 pytest and 22 node tests passed locally. Tried it in the
  browser on a copy of the data: edited a restaurant, checked only the changed
  fields were sent, restarted the server and the changes were still there.
  Also tried no changes, a blank name, unknown/invalid IDs and a fake 422, and
  made sure the create form still worked.

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
- Artifact: `app/main.py`, `frontend/`, `tests/test_frontend.py`,
  `tests/frontend/`, `.github/workflows/ci.yml`, `README.md`
- Label: AI-GENERATED
- AI tool: Claude Code (Claude Opus 5.5)
- Purpose: Get a basic frontend going and build the create restaurant form
  (#50, part of #32).
- Influence: Wrote the StaticFiles setup in `main.py`, the API helper, the
  create form, the python and node tests, and the CI step for the node tests.
  We serve the frontend from FastAPI so there's no second server and no CORS
  setup.
- Validation: 201 pytest and 13 node tests passed locally. Tried the form in
  the browser on a copy of the data: created a restaurant, restarted and it
  was still there, and checked blank fields, a fake 422 and a network error
  all showed messages.
- References: [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/),
  [Node.js test runner](https://nodejs.org/api/test.html)

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
