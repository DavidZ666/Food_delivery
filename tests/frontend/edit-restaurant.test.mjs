import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import { test } from "node:test";

import { restaurantToValues } from "../../frontend/js/restaurant-form.js";

const restaurants = [1, 2].map((id) => ({
  id,
  name: `Restaurant ${id}`,
  cuisine: "Fusion",
  location: { address: `${id} Main St`, city: "Kelowna", province: "BC", postal_code: "V1V 1V1" },
}));

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

// Minimal DOM surface used by the page; requests still go through api.js.
async function mountForm(t, respond) {
  const element = () => ({
    value: "", textContent: "", disabled: false, dataset: {}, attributes: {},
    addEventListener(type, listener) { this[type] = listener; },
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
  });
  const inputs = new Map(Object.keys(restaurantToValues(restaurants[0])).map((name) => [name, element()]));
  const errors = new Map([...inputs.keys()].map((name) => [`error-${name}`, element()]));
  const button = element();
  const status = element();
  const pickerStatus = element();
  const heading = element();
  const picker = Object.assign(element(), {
    options: [],
    append(option) { this.options.push(option); },
    querySelector(selector) {
      return this.options.find((option) => selector === `option[value="${option.value}"]`);
    },
  });
  const form = Object.assign(element(), {
    hidden: true,
    elements: { namedItem: (name) => inputs.get(name) },
    querySelector: () => button,
    querySelectorAll(selector) {
      if (selector === ".field-error") return [...errors.values()];
      if (selector === "[aria-invalid]") return [...inputs.values()].filter((input) => "aria-invalid" in input.attributes);
      if (selector === "input, textarea") return [...inputs.values()];
      throw new Error(`Unexpected selector: ${selector}`);
    },
  });
  const nodes = { "#restaurant-picker": picker, "#picker-status": pickerStatus,
    "#restaurant-form": form, "#editing-heading": heading, "#form-status": status };
  const location = { search: "", pathname: "/app/edit-restaurant.html" };
  const globals = {
    document: { querySelector: (selector) => nodes[selector], createElement: element,
      getElementById: (id) => errors.get(id) },
    location,
    history: { replaceState(_, __, url) { location.search = url.startsWith("?") ? url : ""; } },
    FormData: class {
      *[Symbol.iterator]() {
        for (const [name, input] of inputs) if (!input.disabled) yield [name, input.value];
      }
    },
  };
  for (const [name, value] of Object.entries(globals)) {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
    t.after(() => {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    });
  }
  const calls = [];
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const call = { path, method: options.method, body: options.body && JSON.parse(options.body) };
    calls.push(call);
    if (path === "/restaurants") return Response.json(restaurants);
    return respond(call);
  });
  await import(`../../frontend/js/edit-restaurant.js?test=${encodeURIComponent(t.name)}`);
  await setImmediate();
  return {
    inputs, errors, button, picker, form, status, pickerStatus, heading, location, calls,
    async select(id) {
      if (!picker.disabled) {
        picker.value = String(id);
        picker.change();
      }
      await setImmediate();
    },
    submit() { return form.submit({ preventDefault() {} }); },
  };
}

test("saving locks the selected restaurant and inputs until saved values are displayed", async (t) => {
  const saving = deferred();
  const ui = await mountForm(t, ({ path, method, body }) => {
    if (method === "PATCH" && path === "/restaurants/1") return saving.promise;
    const restaurant = restaurants.find((item) => path === `/restaurants/${item.id}`);
    return Response.json({ ...restaurant, ...body });
  });
  await ui.select(1);
  ui.inputs.get("name").value = "Updated A";
  const submitted = ui.submit();
  assert.equal(ui.picker.disabled, true);
  assert.equal(ui.button.disabled, true);
  assert.ok([...ui.inputs.values()].every((input) => input.disabled));
  await ui.select(2);
  await ui.submit();
  assert.equal(ui.picker.value, "1");
  assert.equal(ui.location.search, "?id=1");
  assert.equal(ui.calls.filter((call) => call.method === "PATCH").length, 1);
  saving.resolve(Response.json({ ...restaurants[0], name: "Updated A" }));
  await submitted;
  assert.equal(ui.inputs.get("name").value, "Updated A");
  assert.equal(ui.heading.textContent, "Editing Updated A (ID 1)");
  assert.equal(ui.status.dataset.kind, "success");
  assert.equal(ui.picker.disabled, false);
  assert.equal(ui.button.disabled, false);
  assert.ok([...ui.inputs.values()].every((input) => !input.disabled));
  await ui.select(2);
  ui.inputs.get("description").value = "B's edit";
  await ui.submit();
  assert.equal(ui.calls.at(-1).path, "/restaurants/2");
  assert.deepEqual(ui.calls.at(-1).body, { description: "B's edit" });
});

for (const status of [200, 404, 500]) {
  test(`clearing the picker ignores a delayed HTTP ${status} load`, async (t) => {
    const loading = deferred();
    const ui = await mountForm(t, () => loading.promise);
    await ui.select(1);
    await ui.select("");
    loading.resolve(Response.json(status === 200 ? restaurants[0] : { detail: "Load failed" }, { status }));
    await setImmediate();
    assert.equal(ui.picker.value, "");
    assert.equal(ui.location.search, "");
    assert.equal(ui.form.hidden, true);
    assert.equal(ui.pickerStatus.textContent, "");
  });
}

for (const failure of [422, 404, 500, "network"]) {
  test(`a rejected save (${failure}) keeps edits and unlocks the form`, async (t) => {
    const ui = await mountForm(t, ({ method }) => {
      if (method === "GET") return Response.json(restaurants[0]);
      if (failure === "network") throw new TypeError("Failed to fetch");
      const detail = failure === 422 ? [{ loc: ["body", "name"], msg: "Rejected name" }] : "Save failed";
      return Response.json({ detail }, { status: failure });
    });
    await ui.select(1);
    ui.inputs.get("name").value = "Keep my edit";
    await ui.submit();
    assert.equal(ui.inputs.get("name").value, "Keep my edit");
    assert.equal(ui.status.dataset.kind, "error");
    assert.equal(ui.picker.disabled, false);
    assert.equal(ui.button.disabled, false);
    assert.ok([...ui.inputs.values()].every((input) => !input.disabled));
    if (failure === 422) assert.equal(ui.errors.get("error-name").textContent, "Rejected name");
  });
}
