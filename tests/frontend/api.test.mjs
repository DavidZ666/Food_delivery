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
