import { test as base, expect } from "@playwright/test";
import { mkdtemp, copyFile, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { setTimeout } from "node:timers/promises";
import assert from "node:assert/strict";

export { expect };

// Test-only restaurant owner for management writes (#78).
const MANAGER = {
  id: 1, name: "Manager", email: "manager@example.com", phone: "250-555-0100",
  delivery_address: { address: "1 Main St", city: "Kelowna", province: "BC", postal_code: "V1V 1V1" },
  password_hash: "scrypt$16384$8$1$b8be40fc497f6b11c4da3573b50facbe$4c3b06cc8be295a3765b090a4b49ff0aa81a4aa29f0956d9d2ee1c58d916edb63d566caa7a2eb6e6c0e730b638f14728148e66b03d91c58cc9fc2723a07e8624",
  role: "restaurant_owner", is_active: true,
};

export const test = base.extend({
  app: async ({}, use) => {
    const root = process.cwd();
    const directory = await mkdtemp(join(tmpdir(), "bytebites-browser-"));
    const filenames = ["restaurants.json", "products.json"];
    const originals = await Promise.all(filenames.map((name) => readFile(join(root, "data", name))));
    for (const name of filenames) await copyFile(join(root, "data", name), join(directory, name));
    await writeFile(join(directory, "customers.json"), JSON.stringify([MANAGER]));
    const socket = createServer();
    await new Promise((done) => socket.listen(0, "127.0.0.1", done));
    const port = socket.address().port;
    await new Promise((done) => socket.close(done));
    const url = `http://127.0.0.1:${port}`;
    let server;
    let stopped;
    let output = "";
    async function start() {
      server = spawn(process.env.FOOD_DELIVERY_PYTHON || resolve(".venv/bin/python"),
        ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)],
        { cwd: root, env: { ...process.env, FOOD_DELIVERY_DATA_DIR: directory, PYTHONDONTWRITEBYTECODE: "1" },
          stdio: ["ignore", "pipe", "pipe"] });
      stopped = new Promise((done) => { server.once("exit", done); server.once("error", done); });
      server.stdout.on("data", (chunk) => { output += chunk; });
      server.stderr.on("data", (chunk) => { output += chunk; });
      for (let i = 0; i < 100; i++) {
        if (server.exitCode !== null) throw new Error(`Server failed: ${output}`);
        try { if ((await fetch(`${url}/health`)).ok) return; } catch {}
        await setTimeout(50);
      }
      throw new Error(`Server did not start: ${output}`);
    }
    async function stop() {
      if (!server || server.exitCode !== null) return;
      server.kill("SIGTERM");
      await Promise.race([stopped, setTimeout(3000)]);
      if (server.exitCode === null) { server.kill("SIGKILL"); await stopped; }
    }
    try {
      await start();
      // Sessions are in memory: sign in again after each restart.
      const signIn = async () => {
        const response = await fetch(`${url}/auth/login`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: MANAGER.email, password: "manager-test-password" }),
        });
        assert.equal(response.status, 200);
        return (await response.json()).access_token;
      };
      await use({ url, directory, signIn, restart: async () => { await stop(); await start(); } });
    } finally {
      await stop();
      for (const [index, name] of filenames.entries()) {
        assert.deepEqual(await readFile(join(root, "data", name)), originals[index], `Representative ${name} changed`);
      }
      await rm(directory, { recursive: true, force: true });
    }
  },
});
