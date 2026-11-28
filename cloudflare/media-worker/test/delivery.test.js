import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import worker from "../src/index.js";

const original = "/private/dev/galleries/1/2/originals/c5caea9fb51144cbb03a02d08be0015b.jpg";
const secret = "test-only-media-signing-secret-not-for-production";
const expires = String(Math.floor(Date.now() / 1000) + 300);
const env = {
  MEDIA_SIGNING_SECRET: secret,
  MEDIA_MAX_SIGNED_URL_TTL: "3600",
  B2_ACCESS_KEY_ID: "fake-key",
  B2_SECRET_ACCESS_KEY: "fake-secret",
  B2_BUCKET_NAME: "lumispixel-production-media",
  B2_REGION: "us-east-005",
  B2_ENDPOINT_URL: "https://s3.us-east-005.backblazeb2.com",
  B2_ALLOWED_PREFIX: "private/dev/",
  MEDIA_EDGE_CACHE_TTL: "0",
};
function url(variant, signVariant = variant) {
  const signature = createHmac("sha256", secret)
    .update(`${original}\n${expires}\n${signVariant}`)
    .digest("base64url");
  return `https://media-dev.lumispixel.com${original}?expires=${expires}&signature=${signature}&variant=${variant}`;
}
const previousFetch = globalThis.fetch;
const previousCaches = globalThis.caches;
function mockOrigin(handler) {
  globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
  globalThis.fetch = async (request) => handler(new URL(request.url));
}
test.afterEach(() => {
  globalThis.fetch = previousFetch;
  globalThis.caches = previousCaches;
});
test("Photo 7 thumbnail uses exact B2 derivative key without transformation", async () => {
  let requested;
  mockOrigin((u) => {
    requested = decodeURIComponent(u.pathname);
    return new Response("webp-data", { status: 200, headers: { "content-type": "image/webp" } });
  });
  const response = await worker.fetch(new Request(url("thumbnail")), env);
  assert.equal(response.status, 200);
  assert.equal(requested, "/lumispixel-production-media/private/dev/galleries/1/2/variants/thumbnail/c5caea9fb51144cbb03a02d08be0015b.webp");
});
test("Photo 7 preview uses exact B2 derivative key", async () => {
  let requested;
  mockOrigin((u) => {
    requested = decodeURIComponent(u.pathname);
    return new Response("webp-data", { status: 200, headers: { "content-type": "image/webp" } });
  });
  assert.equal((await worker.fetch(new Request(url("preview")), env)).status, 200);
  assert.equal(requested, "/lumispixel-production-media/private/dev/galleries/1/2/variants/preview/c5caea9fb51144cbb03a02d08be0015b.webp");
});
test("missing derivative never falls back to oversized original", async () => {
  let count = 0;
  mockOrigin(() => { count++; return new Response("missing", { status: 404 }); });
  const response = await worker.fetch(new Request(url("thumbnail")), env);
  assert.equal(response.status, 404);
  assert.equal(count, 1);
});
test("changing thumbnail URL to original is forbidden", async () => {
  mockOrigin(() => { throw Error("should not reach B2"); });
  assert.equal((await worker.fetch(new Request(url("original", "thumbnail")), env)).status, 403);
});
