import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ApiError, apiRequest } from "../../frontend/js/api.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function respondWith(status, body, contentType = "application/json") {
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return new Response(body, { status, headers: { "Content-Type": contentType } });
  };
  return calls;
}

test("POST sends JSON and returns the API response", async () => {
  const created = { id: 3, name: "Taco Spot" };
  const calls = respondWith(201, JSON.stringify(created));

  const result = await apiRequest("/restaurants", { method: "POST", body: { name: "Taco Spot" } });

  assert.deepEqual(result, created);
  assert.equal(calls[0].path, "/restaurants");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].options.body), { name: "Taco Spot" });
});

test("GET sends no body", async () => {
  const calls = respondWith(200, "[]");
  assert.deepEqual(await apiRequest("/restaurants"), []);
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.body, undefined);
});

test("422 rejects with the validation detail", async () => {
  const detail = [{ loc: ["body", "name"], msg: "Field required" }];
  respondWith(422, JSON.stringify({ detail }));

  await assert.rejects(apiRequest("/restaurants", { method: "POST", body: {} }), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.deepEqual(error.detail, detail);
    assert.equal(error.message, "Some fields are invalid.");
    return true;
  });
});

test("404 rejects with the API's message", async () => {
  respondWith(404, JSON.stringify({ detail: "Restaurant not found" }));
  await assert.rejects(apiRequest("/restaurants/999"), {
    name: "ApiError",
    status: 404,
    message: "Restaurant not found",
  });
});

test("500 with a plain-text body rejects with a generic server message", async () => {
  respondWith(500, "Internal Server Error", "text/plain");
  await assert.rejects(apiRequest("/restaurants", { method: "POST", body: {} }), {
    name: "ApiError",
    status: 500,
    detail: null,
    message: "The server could not complete the request. Try again later.",
  });
});

test("network failure rejects without a status", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(apiRequest("/restaurants"), {
    name: "ApiError",
    status: null,
    message: "Could not reach the server. Check that it is running.",
  });
});

for (const status of [201, 422, 500]) {
  test(`interrupted response body rejects with ApiError and HTTP ${status}`, async () => {
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('{"detail":'));
      },
      pull(controller) {
        controller.error(new TypeError("Connection terminated"));
      },
    });
    globalThis.fetch = async () => new Response(body, { status });

    await assert.rejects(apiRequest("/restaurants", { method: "POST", body: {} }), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, status);
      assert.equal(error.detail, null);
      assert.equal(error.message, "Could not read the server response. The request may have completed.");
      return true;
    });
  });
}

function storeToken(token) {
  globalThis.sessionStorage = { getItem: (key) => (key === "accessToken" ? token : null) };
}

test("a stored session token is sent as a bearer credential", async (t) => {
  t.after(() => delete globalThis.sessionStorage);
  storeToken("abc123");
  const calls = respondWith(200, "{}");
  await apiRequest("/restaurants/1", { method: "PATCH", body: {} });
  assert.equal(calls[0].options.headers.Authorization, "Bearer abc123");
});

test("no Authorization header without a stored token or storage", async (t) => {
  t.after(() => delete globalThis.sessionStorage);
  const calls = respondWith(200, "[]");
  await apiRequest("/restaurants");
  storeToken(null);
  await apiRequest("/restaurants");
  globalThis.sessionStorage = { getItem: () => { throw new Error("blocked"); } };
  await apiRequest("/restaurants");
  for (const call of calls) assert.equal(call.options.headers.Authorization, undefined);
});

function storeSession(token) {
  const items = new Map([["accessToken", token], ["customer", '{"id":1,"name":"Ada","role":"customer"}']]);
  globalThis.sessionStorage = {
    getItem: (key) => items.get(key) ?? null,
    removeItem: (key) => items.delete(key),
  };
  return items;
}

test("401 without a session asks to sign in", async () => {
  respondWith(401, JSON.stringify({ detail: "Invalid credentials" }));
  await assert.rejects(apiRequest("/restaurants", { method: "POST", body: {} }), {
    name: "ApiError", status: 401, detail: "Invalid credentials", message: "Sign in to continue.",
  });
});

test("401 with a session reports that it expired and forgets it", async (t) => {
  t.after(() => delete globalThis.sessionStorage);
  const items = storeSession("stale");
  const calls = respondWith(401, JSON.stringify({ detail: "Invalid credentials" }));
  await assert.rejects(apiRequest("/customers/1"), {
    status: 401, message: "Your session has expired. Sign in again.",
  });
  assert.equal(calls[0].options.headers.Authorization, "Bearer stale");
  assert.equal(items.size, 0);
  await apiRequest("/customers/1").catch(() => {});
  assert.equal(calls[1].options.headers.Authorization, undefined);
});

test("403 says the account is not allowed and keeps the session", async (t) => {
  t.after(() => delete globalThis.sessionStorage);
  const items = storeSession("valid");
  respondWith(403, JSON.stringify({ detail: "Forbidden" }));
  await assert.rejects(apiRequest("/restaurants", { method: "POST", body: {} }), {
    status: 403, detail: "Forbidden", message: "This account is not allowed to do that.",
  });
  assert.equal(items.size, 2);
});

test("other errors keep the session", async (t) => {
  t.after(() => delete globalThis.sessionStorage);
  const items = storeSession("valid");
  for (const status of [404, 422, 500]) {
    respondWith(status, JSON.stringify({ detail: "x" }));
    await assert.rejects(apiRequest("/customers/1"), { status });
  }
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(apiRequest("/customers/1"), { status: null });
  assert.equal(items.size, 2);
});
