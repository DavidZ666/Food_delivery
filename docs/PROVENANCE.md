# AI Use and Provenance

## Restaurant creation and persistent writes (#24, #25)

- Student(s): GitHub `freesialuo`
- Artifact: `app/{routes,services,repositories,schemas}/`,
  `tests/test_restaurant_creation.py`, `tests/test_json_writes.py`, `README.md`,
  `docs/decisions/json-writes.md`, `docs/PROVENANCE.md`
- Label: AI-GENERATED
- AI tool: OpenAI Codex
- Purpose and influence: Implement validated restaurant creation, serialized
  atomic JSON transactions, isolated tests and API/design documentation.
- Validation: Full pytest suite on Python 3.14.7, including fresh-process
  persistence, concurrent creation and write-failure cases; `git diff --check`.
- References: [FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/),
  [response status codes](https://fastapi.tiangolo.com/tutorial/response-status-code/),
  [Python temporary files](https://docs.python.org/3/library/tempfile.html),
  [os.replace](https://docs.python.org/3/library/os.html#os.replace).
