import test from "node:test";
import assert from "node:assert/strict";
import { createHmac, webcrypto } from "node:crypto";
import worker, { allowedGalleryKey as allowed } from "../src/index.js";
globalThis.crypto ??= webcrypto;
const prefix = "private/dev/";
const key = prefix + "galleries/1/2/originals/a.jpg";
const env = { B2_ALLOWED_PREFIX: prefix, B2_BUCKET_NAME: "lumispixel-production-media", B2_REGION: "us-east-005", B2_ENDPOINT_URL: "https://s3.us-east-005.backblazeb2.com", B2_ACCESS_KEY_ID: "synthetic", B2_SECRET_ACCESS_KEY: "synthetic", MEDIA_SIGNING_SECRET: "synthetic-test-secret-not-for-production", MEDIA_MAX_SIGNED_URL_TTL: "900" };
function url(k=key, variant="preview", ttl=60) {
  const u = new URL("https://example.test/" + k);
  const expires = String(Math.floor(Date.now()/1000)+ttl);
  u.searchParams.set("expires", expires);
  u.searchParams.set("variant", variant);
  u.searchParams.set("signature", createHmac("sha256", env.MEDIA_SIGNING_SECRET).update(u.pathname+"\n"+expires+"\n"+variant).digest("base64url"));
  return u;
}
test("namespace validation", () => {
  assert.equal(allowed(key,prefix),true);
  for (const bad of [key.replace("/dev/","/prod/"), prefix+"../a.jpg", prefix+"%2e/a.jpg", prefix+"x//a.jpg", prefix+"x\\a.jpg", prefix+"unknown/a.jpg"]) assert.equal(allowed(bad,prefix),false,bad);
  assert.equal(allowed(key,"private/"),false);
});
test("invalid origin and method fail closed", async () => {
  assert.equal((await worker.fetch(new Request(url()), {...env,B2_ENDPOINT_URL:"https://example.test"})).status,500);
  assert.equal((await worker.fetch(new Request(url(),{method:"POST"}),env)).status,405);
  assert.equal((await worker.fetch(new Request(url(key.replace("/dev/","/prod/"))),env)).status,404);
});
test("authorization rejects tampering before cache", async () => {
  for (const mutate of [u=>u.searchParams.delete("variant"),u=>u.searchParams.append("variant","preview"),u=>u.searchParams.set("variant","original"),u=>u.searchParams.delete("signature"),u=>u.searchParams.append("expires","1")]) {
    const u=url(); mutate(u); assert.equal((await worker.fetch(new Request(u),env)).status,403);
  }
  for(const ttl of [-1,901]) assert.equal((await worker.fetch(new Request(url(key,"preview",ttl)),env)).status,403);
});
test("cache hit and miss preserve response policy; origin is mocked", async () => {
  let stored, calls=0;
  const oldFetch=globalThis.fetch, oldCaches=globalThis.caches;
  globalThis.caches={default:{match:async()=>stored?.clone(),put:async(k,r)=>{assert.match(k.url,/delivery=v3/);stored=r.clone();}}};
  globalThis.fetch=async r=>{calls++; assert.match(r.url,/variants\/preview\/a\.webp$/); return new Response("synthetic",{headers:{"content-type":"image/webp"}});};
  try {
    for(const status of ["MISS","HIT"]) {
      const r=await worker.fetch(new Request(url()),env);
      assert.equal(r.status,200);assert.equal(r.headers.get("x-lumispixel-cache"),status);
      assert.equal(r.headers.get("cache-control"),"private, no-store");
    }
    assert.equal(calls,1);
    const u=url();u.searchParams.set("variant","original");assert.equal((await worker.fetch(new Request(u),env)).status,403);
  } finally {globalThis.fetch=oldFetch;globalThis.caches=oldCaches;}
});

test("origin redirects are rejected without following or caching", async () => {
  const oldFetch = globalThis.fetch, oldCaches = globalThis.caches;
  let calls = 0, writes = 0;
  globalThis.caches = {default: {match: async () => undefined, put: async () => { writes++; }}};
  try {
    for (const status of [301, 302, 303, 307, 308]) {
      for (const method of ["GET", "HEAD"]) {
        globalThis.fetch = async request => {
          calls++;
          assert.equal(request.redirect, "manual");
          return new Response(null, {status, headers: {location: "https://untrusted.example/"}});
        };
        const before = calls;
        const response = await worker.fetch(new Request(url(), {method}), env);
        assert.equal(response.status, 502);
        assert.equal(response.headers.get("location"), null);
        assert.equal(response.headers.get("cache-control"), "no-store");
        assert.equal(calls, before + 1);
      }
    }
    assert.equal(writes, 0);
  } finally {
    globalThis.fetch = oldFetch;
    globalThis.caches = oldCaches;
  }
});
