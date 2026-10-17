import { test as base, expect } from "@playwright/test";
import { mkdtemp, copyFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { setTimeout } from "node:timers/promises";
import assert from "node:assert/strict";

export { expect };
export const test = base.extend({
  app: async ({}, use) => {
    const root = process.cwd();
    const directory = await mkdtemp(join(tmpdir(), "bytebites-browser-"));
    const filenames = ["restaurants.json", "products.json"];
    const originals = await Promise.all(filenames.map((name) => readFile(join(root, "data", name))));
    for (const name of filenames) await copyFile(join(root, "data", name), join(directory, name));
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
      await use({ url, directory, restart: async () => { await stop(); await start(); } });
    } finally {
      await stop();
      for (const [index, name] of filenames.entries()) {
        assert.deepEqual(await readFile(join(root, "data", name)), originals[index], `Representative ${name} changed`);
      }
      await rm(directory, { recursive: true, force: true });
    }
  },
});
