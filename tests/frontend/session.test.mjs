import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { clearSession, getCustomer, getToken, saveCustomer, saveSession } from "../../frontend/js/session.js";

afterEach(() => delete globalThis.sessionStorage);

function fakeStorage() {
  const items = new Map();
  globalThis.sessionStorage = {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
  };
  return items;
}

const LOGIN = {
  access_token: "abc123", token_type: "bearer",
  customer: { id: 7, name: "Ada", email: "ada@example.com", phone: "250-555-0101", role: "customer", is_active: true },
};

test("a saved session returns its token and only the id, name and role", () => {
  const items = fakeStorage();
  assert.equal(saveSession(LOGIN), true);
  assert.equal(getToken(), "abc123");
  assert.deepEqual(getCustomer(), { id: 7, name: "Ada", role: "customer" });
  assert.deepEqual([...items.keys()], ["accessToken", "customer"]);
  assert.equal(saveCustomer({ ...LOGIN.customer, name: "Ada King" }), true);
  assert.equal(getCustomer().name, "Ada King");
});

test("clearing the session removes the token and the customer", () => {
  const items = fakeStorage();
  saveSession(LOGIN);
  clearSession();
  assert.equal(getToken(), null);
  assert.equal(getCustomer(), null);
  assert.equal(items.size, 0);
});

test("missing or blocked storage reads as signed out and never throws", () => {
  assert.equal(getToken(), null);
  assert.equal(getCustomer(), null);
  assert.equal(saveSession(LOGIN), false);
  clearSession();
  const blocked = () => { throw new Error("blocked"); };
  globalThis.sessionStorage = { getItem: blocked, setItem: blocked, removeItem: blocked };
  assert.equal(getToken(), null);
  assert.equal(getCustomer(), null);
  assert.equal(saveSession(LOGIN), false);
  assert.equal(saveCustomer(LOGIN.customer), false);
  clearSession();
});

for (const stored of ["{broken", "null", '"text"', '{"name":"Ada"}', '{"id":"7"}']) {
  test(`a malformed stored customer ${stored} reads as none`, () => {
    fakeStorage().set("customer", stored);
    assert.equal(getCustomer(), null);
  });
}
