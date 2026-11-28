import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { existsSync } from "node:fs";
import worker from "../src/index.js";

const repoRoot = resolve(fileURLToPath(new URL("../../../", import.meta.url)));
const secret = "cross-language-test-only-not-a-production-secret";
const original = "galleries/1/2/originals/c5caea9fb51144cbb03a02d08be0015b.jpg";
const pythonCode = [
  "import json",
  "from django.conf import settings",
  "settings.configure(GALLERY_STORAGE_ENVIRONMENT='dev', MEDIA_SIGNING_SECRET=" + JSON.stringify(secret) + ", MEDIA_DELIVERY_BASE_URL='https://media-dev.lumispixel.com', MEDIA_SIGNED_URL_TTL=300)",
  "from apps.galleries.media_delivery import signed_media_url",
  "print(json.dumps({v:signed_media_url(" + JSON.stringify(original) + ",variant=v,now=1795470000) for v in ('thumbnail','preview','original')}))",
].join("\n");
const env = {
  MEDIA_SIGNING_SECRET: secret,
  MEDIA_MAX_SIGNED_URL_TTL: "3600",
  B2_ACCESS_KEY_ID: "test-key",
  B2_SECRET_ACCESS_KEY: "test-secret",
  B2_BUCKET_NAME: "lumispixel-production-media",
  B2_REGION: "us-east-005",
  B2_ENDPOINT_URL: "https://s3.us-east-005.backblazeb2.com",
  B2_ALLOWED_PREFIX: "private/dev/",
  MEDIA_EDGE_CACHE_TTL: "0",
};
test("Django signatures are accepted by the JavaScript Worker for each variant", async () => {
  const windowsVenv = resolve(repoRoot, "env_lumispixel", "Scripts", "python.exe");
  const unixVenv = resolve(repoRoot, "env_lumispixel", "bin", "python");
  const python = process.env.PYTHON || (existsSync(windowsVenv) ? windowsVenv : existsSync(unixVenv) ? unixVenv : (process.platform === "win32" ? "python" : "python3"));
  const result = spawnSync(python, ["-c", pythonCode], { cwd: repoRoot, encoding: "utf8" });
  assert.equal(result.status, 0, `Python signing failed: ${result.stderr}`);
  const urls = JSON.parse(result.stdout.trim());
  const originalFetch = globalThis.fetch;
  const originalCaches = globalThis.caches;
  const originalDateNow = Date.now;
  try {
    Date.now = () => 1795470000 * 1000;
    globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
    globalThis.fetch = async () => new Response("webp", { status: 200, headers: { "content-type": "image/webp" } });
    for (const variant of ["thumbnail", "preview", "original"]) {
      const response = await worker.fetch(new Request(urls[variant]), env);
      assert.equal(response.status, 200, `${variant}: ${await response.text()}`);
    }
    const tampered = new URL(urls.thumbnail);
    tampered.searchParams.set("variant", "original");
    const response = await worker.fetch(new Request(tampered), env);
    assert.equal(response.status, 403);
  } finally {
    Date.now = originalDateNow;
    globalThis.fetch = originalFetch;
    globalThis.caches = originalCaches;
  }
});
