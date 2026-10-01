# AI Use and Provenance

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
  branch `feature/16-restaurant-details`, based on `origin/main`. User requested
  stopping after a signed commit and push, before opening a PR. Peer review,
  merge and feature-branch CI execution are not claimed.
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
