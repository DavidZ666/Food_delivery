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

## Restaurant details — Issue #16

- Student(s): Requesting contributor, GitHub `freesialuo` (Git author
  `CosmoDz`; student name to be confirmed by the contributor).
- Artifact: `app/routes/restaurants.py`; `app/services/restaurant_service.py`;
  `app/repositories/restaurant_repo.py`; `app/schemas/error.py`;
  `tests/test_restaurant_details.py`; `README.md`; `docs/PROVENANCE.md`;
  restaurant-details Project Draft converted to repository issue #16.
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Implement A3, the small restaurant-details read flow described in
  local `references/M0_TO_M1_DEVELOPMENT_FLOW.md` and the M1 course requirements.
- Influence: Updated the existing Draft with the read-only API contract and
  acceptance criteria, then generated the layered lookup, domain-level missing
  resource error, HTTP 404 mapping, OpenAPI response documentation, isolated
  tests and README changes. Reused the existing `RestaurantRead` model and JSON
  reader. No persistent writes or frontend were introduced.
- Design: Repository lookup returns `None` for an absent ID; the service raises
  `RestaurantNotFoundError`; the route maps that error to HTTP 404. This keeps
  HTTP details in the route and storage details in the repository. Storage or
  invalid-data failures are not converted to a misleading resource-not-found
  response. The small JSON collection uses a linear lookup instead of adding
  an index or cache that could become stale.
- Validation: All 23 tests passed using the existing Python 3.14.3 environment
  (README specifies 3.14.7). Tests exercise stored IDs, optional fields,
  unchanged storage, absent IDs, empty collections, invalid IDs, invalid stored
  records, service behavior, storage-failure propagation and generated OpenAPI
  schemas, alongside the 11 existing regression tests. `git diff --check`
  passed. OpenAPI testing caught that explicitly overriding the 422 response
  description suppressed FastAPI's validation schema; the endpoint now retains
  FastAPI's generated 422 response and describes its behavior in the operation.
- Workflow: [Issue #16](https://github.com/DavidZ666/Food_delivery/issues/16),
  branch `feature/16-restaurant-details`, originally based on `origin/main`.
  The PR now depends on `feature/automated-tests-ci` (PR #15). The CI branch
  was merged into this branch, preserving both CI entries and this entry.
  Merge PR #15 first, then retarget this PR to `main` before merging.
  Peer review and merge are not claimed.
- Sources: Local `references/Project Overview`, `references/Milestone 1 – First
  Vertical Slice`, `references/M0_TO_M1_DEVELOPMENT_FLOW.md` and
  `references/Generative AI Use and Provenance Guide`.
- Implementation guidance retrieved with Exa on 2026-09-30:
  - [FastAPI handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/):
    raise `HTTPException` in the HTTP layer for the documented 404 response.
  - [FastAPI path parameters](https://fastapi.tiangolo.com/tutorial/path-params/):
    typed integer parameters provide parsing, validation and API documentation.
  - [FastAPI additional responses](https://fastapi.tiangolo.com/advanced/additional-responses/):
    document the 404 error model alongside the existing success response model.
