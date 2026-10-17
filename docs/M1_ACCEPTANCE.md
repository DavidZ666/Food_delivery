# M1 acceptance evidence (#29, #33, #41, #42)

Snapshot date: 2026-10-17 (Asia/Shanghai). Base: `bec8603` (includes PR #57).
This is local implementation evidence, not a declaration that all GitHub issues can close.

## Reproduce

Use Python 3.14 with project requirements installed. From the repository root:

```bash
python -m pytest tests --verbose --strict-config --strict-markers --junitxml=pytest-results.xml
node --test "tests/frontend/*.test.mjs"
npm ci
npx playwright install chromium
npm run test:e2e
```

Browser fixtures default to `.venv/bin/python`. Set `FOOD_DELIVERY_PYTHON=python`
if your activated Python is elsewhere (also supported on Windows).
Each test starts its own real Uvicorn process on an unused local port, copies
both representative JSON files to a temporary directory, and checks that the
original bytes remain unchanged at teardown. It never uses a running port-8000
server or production data. Browser failures retain traces and a JUnit report
under `test-results/`. Existing CI (#8/#14) now also runs these browser checks.

For local use with an installed Chrome instead of downloading Chromium:
```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run test:e2e
```

## Local results

- Python 3.14: **253 passed**, including all existing M0 regressions.
- Node frontend suite: **30 passed**.
- Actual headless Chrome with FastAPI: **9 passed**.
- Representative JSON file byte checks passed in every browser fixture.
- These results are from the implementation prepared on 2026-10-17;
  remote CI for the new changes is reported separately in the PR.

## Acceptance mapping

| Requirement | Evidence |
|---|---|
| #41: actual restaurant list, name and cuisine filters | Browser test: real API list/search/combined filter; no restaurant data hard-coded in pages |
| #41: loading, no results, empty store, failures, navigation | Browser loading/network, empty store, real storage failure and detail navigation tests |
| #42: selected restaurant → menu → selected item | Real API browsing test verifies URL IDs, names, prices, return links |
| #42: empty menus, missing resources, ownership, request errors | Empty-menu, unknown/wrong-owner/invalid-ID, failure and retry browser tests |
| #29: complete customer browser flow | All browser success paths use actual FastAPI endpoints and temporary JSON |
| #33: API create/update and restart persistence | `test_management_api_and_readback_in_a_fresh_process`; browser item test kills/restarts Uvicorn |
| #33: UI restaurant management and persistence | Browser creates restaurant, edits name/city, restarts server, reloads form and reads details |
| #33: invalid input and storage failures | Existing regressions plus explicit-null update rejection and failed-write preservation tests |
| #33: isolated tests and M0 regressions | Full pytest and Node suites; browser fixture checks representative-data bytes |
| #33: OpenAPI matches behavior | Contract tests; documented menu create/update semantics and 500 storage errors; nulls rejected before writes |
| #33: peer review, merge, CI evidence | Historical PR table below; this change still requires PR CI and independent review/merge |

The only simulated HTTP results in browser tests exercise network/HTTP failures,
loading delays and out-of-order responses. Normal browsing and management use
real API integration. Empty/malformed storage tests modify only temporary copies.

## Historical PR audit

Checked via GitHub PR metadata, submitted reviews and PR-head workflow runs:

| PR | Merge | Submitted approval | CI on PR head |
|---|---|---|---|
| [#17](https://github.com/DavidZ666/Food_delivery/pull/17) | Merged | SpencerS04 | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/36930506181) |
| [#21](https://github.com/DavidZ666/Food_delivery/pull/21) | Merged | SpencerS04 | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/37354137795) |
| [#22](https://github.com/DavidZ666/Food_delivery/pull/22) | Merged | No submitted approval returned | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/37534893898) |
| [#26](https://github.com/DavidZ666/Food_delivery/pull/26) | Merged | No submitted approval returned | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/38835346294) |
| [#53](https://github.com/DavidZ666/Food_delivery/pull/53) | Merged | freesialuo | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/38943293134) |
| [#54](https://github.com/DavidZ666/Food_delivery/pull/54) | Merged | No submitted approval returned | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/38984562897) |
| [#55](https://github.com/DavidZ666/Food_delivery/pull/55) | Merged | freesialuo | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/38995232474) |
| [#56](https://github.com/DavidZ666/Food_delivery/pull/56) | Merged | No submitted approval returned | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/38997581007) |
| [#57](https://github.com/DavidZ666/Food_delivery/pull/57) | Merged | freesialuo | [success](https://github.com/DavidZ666/Food_delivery/actions/runs/39000387541) |

A merge or green CI does not establish a peer review. No submitted approvals
were returned for #22, #26, #54 or #56; obtain existing review evidence or have
teammates review these changes before claiming that part of #33 is satisfied.
No messages or review requests have been sent to teammates by this change.

## Limits and closure conditions

- Current implementation must pass its own remote CI, receive independent peer
  review and merge. Do not close #33 merely because local tests pass.
- The JSON store supports one application worker on a local filesystem.
  Menu service mutations currently read/modify before atomic file replacement;
  simultaneous menu writes can lose updates. Do not use this as a multi-user
  production ordering service. Concurrency redesign is outside these browsing
  acceptance criteria and remains recorded here.
- Menu image URLs are optional external resources. Failed or unsafe-protocol
  images are hidden; item text remains usable.
- Existing menu contract ignores unknown fields/client-supplied IDs and permits
  empty PATCH as a no-op. This change preserves that behavior; it rejects
  explicit null updates and nonfinite prices to avoid corrupting required fields.
- No authentication, checkout or delivery flow is claimed by these issues.

