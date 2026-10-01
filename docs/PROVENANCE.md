# AI Use and Provenance

## Restaurant name search — Issue #19

- Student(s): Requesting contributor, GitHub `freesialuo` (Git author
  `CosmoDz`; student name to be confirmed by the contributor).
- Artifact: `app/routes/restaurants.py`; `app/services/restaurant_service.py`;
  `tests/test_restaurant_search.py`; `README.md`; `docs/PROVENANCE.md`;
  existing restaurant-name-search Project Draft converted to Issue #19.
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose: Implement the name-search commitment of Epic #11 (local X1),
  independently of unmerged PRs #15 and #17.
- Influence: Refined the Draft contract and generated optional query handling,
  service matching, isolated tests, API documentation and README guidance.
- Design: Reuse the merged list repository. Keep literal substring matching
  in the service, applying `strip()` and Unicode `casefold()` to the query
  and `casefold()` to stored names. Preserve order and fields; blank queries
  preserve existing list behavior. Avoid regex interpretation and storage writes.
  Storage failures propagate instead of becoming misleading empty results.
  Cuisine filtering remains separate (#13); proposed future composition is AND.
- Validation: All 30 tests passed on Python 3.14.3, including the 11 main
  regression tests and search API/service/OpenAPI tests. Tests use temporary
  storage and verify unchanged bytes. README specifies 3.14.7, which was not
  available locally. `git diff --check` passed.
- Workflow: [Issue #19](https://github.com/DavidZ666/Food_delivery/issues/19),
  branch `feature/19-restaurant-name-search`, based directly on `origin/main`
  at `dd4cbea853e34bf408b8ac51f30afaf1c2edfbf6`. Stop after signed commit,
  before opening a PR; peer review, CI execution and merge are pending.
- Sources: Local `references/Project Overview`, `references/Milestone 1 – First
  Vertical Slice`, `references/M0_TO_M1_DEVELOPMENT_FLOW.md` and
  `references/Generative AI Use and Provenance Guide`.
- Implementation guidance retrieved through Context7 on 2026-10-01:
  - [FastAPI query validation](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/):
    declare an optional string query with `Query(default=None)`.
  - [FastAPI parameter reference](https://fastapi.tiangolo.com/reference/parameters/):
    use query descriptions in generated OpenAPI.
  - [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/):
    retain a typed list response for serialization and validation.
