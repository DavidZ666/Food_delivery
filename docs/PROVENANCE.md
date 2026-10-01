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
- Validation: 30 tests passed on Python 3.14.3, covering search behavior,
  unchanged storage, storage errors and OpenAPI. The diff passed whitespace
  checks; Python 3.14.7 was not tested.
- Commit: `6e08e718bf63324d5e0781143eee4531883e214f`
- References: [FastAPI query parameters](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/),
  [parameter reference](https://fastapi.tiangolo.com/reference/parameters/),
  [response models](https://fastapi.tiangolo.com/tutorial/response-model/).
