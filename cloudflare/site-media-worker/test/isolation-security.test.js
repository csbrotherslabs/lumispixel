import test from "node:test";
import assert from "node:assert/strict";
import { createHmac, webcrypto } from "node:crypto";
import worker, { allowedSiteKey as allowed } from "../src/index.js";
globalThis.crypto ??= webcrypto;
const prefix = "site/dev/";
const key = prefix + "photographer_websites/a.jpg";
const env = { B2_ALLOWED_PREFIX: prefix, B2_BUCKET_NAME: "lumispixel-dev-site-media", B2_REGION: "us-east-005", B2_ENDPOINT_URL: "https://s3.us-east-005.backblazeb2.com", B2_ACCESS_KEY_ID: "synthetic", B2_SECRET_ACCESS_KEY: "synthetic", MEDIA_SIGNING_SECRET: "synthetic-test-secret-not-for-production", MEDIA_MAX_SIGNED_URL_TTL: "900" };
function url(k=key, variant="preview", ttl=60) {
  const u = new URL("https://example.test/" + k);
  
  return u;
}
test("namespace validation", () => {
  assert.equal(allowed(key,prefix),true);
  for (const bad of [key.replace("/dev/","/prod/"), prefix+"../a.jpg", prefix+"%2e/a.jpg", prefix+"x//a.jpg", prefix+"x\\a.jpg", prefix+"unknown/a.jpg"]) assert.equal(allowed(bad,prefix),false,bad);
  assert.equal(allowed(key,"site/"),false);
});
test("invalid origin and method fail closed", async () => {
  assert.equal((await worker.fetch(new Request(url()), {...env,B2_ENDPOINT_URL:"https://example.test"})).status,500);
  assert.equal((await worker.fetch(new Request(url(),{method:"POST"}),env)).status,405);
  assert.equal((await worker.fetch(new Request(url(key.replace("/dev/","/prod/"))),env)).status,404);
});

test("cache hit and miss preserve response policy; origin is mocked", async () => {
  let stored, calls=0;
  const oldFetch=globalThis.fetch, oldCaches=globalThis.caches;
  globalThis.caches={default:{match:async()=>stored?.clone(),put:async(k,r)=>{assert.match(k.url,/delivery=v3/);stored=r.clone();}}};
  globalThis.fetch=async r=>{calls++;  return new Response("synthetic",{headers:{"content-type":"image/jpeg"}});};
  try {
    for(const status of ["MISS","HIT"]) {
      const r=await worker.fetch(new Request(url()),env);
      assert.equal(r.status,200);assert.equal(r.headers.get("x-lumispixel-cache"),status);
      assert.equal(r.headers.get("cache-control"),"public, max-age=3600");
    }
    assert.equal(calls,1);
    
  } finally {globalThis.fetch=oldFetch;globalThis.caches=oldCaches;}
});
