import { AwsClient } from "aws4fetch";

function textResponse(message, status) {
  return new Response(message, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function normalizePrefix(prefix) {
  return /^(?:site)\/(?:dev|prod)\/$/.test(prefix) ? prefix : "";
}

function safeKey(key) {
  return typeof key === "string" && !/[\\%?#\x00-\x1f\x7f]/.test(key) &&
    key.split("/").every(p => p && p !== "." && p !== "..");
}

function validOrigin(env) {
  const prefix = normalizePrefix(env.B2_ALLOWED_PREFIX);
  if (!prefix) return false;
  const environment = prefix.split("/")[1];
  const bucket = `lumispixel-${environment}-site-media`;
  return env.B2_BUCKET_NAME === bucket &&
    /^[a-z0-9-]+$/.test(env.B2_REGION) &&
    env.B2_ENDPOINT_URL === `https://s3.${env.B2_REGION}.backblazeb2.com`;
}


const SITE_PREFIXES = ["client-profiles/", "photographer_profiles/photos/", "photographer_profiles/logos/", "photographer-covers/", "photographer_websites/"];
export function allowedSiteKey(key, prefix) {
  const normalized = normalizePrefix(prefix);
  const relative = key.slice(normalized.length);
  return !!normalized && safeKey(key) && key.startsWith(normalized) &&
    !key.split("/").some(part => part === ".." || part === ".") &&
    SITE_PREFIXES.some(part => relative.startsWith(part)) &&
    /\.(jpe?g|png|webp|gif|avif)$/i.test(relative);
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return textResponse("Method not allowed", 405);
    }

    if (
      !env.B2_ACCESS_KEY_ID ||
      !env.B2_SECRET_ACCESS_KEY ||
      !env.B2_BUCKET_NAME ||
      !env.B2_REGION ||
      !env.B2_ENDPOINT_URL ||
      !env.B2_ALLOWED_PREFIX
    ) {
      return textResponse("Media origin is not configured", 500);
    }

    if (!validOrigin(env)) {
      return textResponse("Media origin configuration is invalid", 500);
    }

    const requestUrl = new URL(request.url);

    let objectKey;

    try {
      objectKey = decodeURIComponent(requestUrl.pathname.slice(1));
    } catch {
      return textResponse("Invalid object path", 400);
    }

    const allowedPrefix = normalizePrefix(env.B2_ALLOWED_PREFIX);

    if (!objectKey || !allowedSiteKey(objectKey, allowedPrefix)) {
      return textResponse("Not found", 404);
    }

    const cache = caches.default;
    const cacheUrl = new URL(requestUrl.origin + requestUrl.pathname);
    cacheUrl.searchParams.set("delivery", "v3");
    const cacheKey = new Request(cacheUrl.toString(), { method: "GET" });
    const isRangeRequest = request.headers.has("range");

    // Only allowlisted site-image paths from this dedicated private bucket are public.
    if (request.method === "GET" && !isRangeRequest) {
      const cachedResponse = await cache.match(cacheKey);
      if (cachedResponse) {
        const headers = new Headers(cachedResponse.headers);
        headers.set("x-lumispixel-cache", "HIT");
        headers.set("cache-control", "public, max-age=3600");
        return new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers,
        });
      }
    }

    const endpoint = String(env.B2_ENDPOINT_URL || "").replace(/\/+$/, "");
    const bucket = encodeURIComponent(env.B2_BUCKET_NAME);
    const encodedKey = objectKey
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    const originUrl = `${endpoint}/${bucket}/${encodedKey}`;

    const aws = new AwsClient({
      accessKeyId: env.B2_ACCESS_KEY_ID,
      secretAccessKey: env.B2_SECRET_ACCESS_KEY,
      service: "s3",
      region: env.B2_REGION,
    });

    let originResponse;
    try {
    const originRequest = await aws.sign(originUrl, {
      redirect: "manual",
      method: request.method,
      headers: request.headers.has("range")
        ? { range: request.headers.get("range") }
        : {},
    });

      originResponse = await fetch(originRequest);
    } catch (error) {
      console.warn("Media origin failure");
      return textResponse("Media origin unavailable", 502);
    }

    if (originResponse.status >= 300 && originResponse.status < 400) {
      console.warn("Media origin redirect rejected");
      return textResponse("Media origin error", 502);
    }

    if (originResponse.status === 404) {
      return textResponse("Not found", 404);
    }

    if (!originResponse.ok && originResponse.status !== 206) {
      console.warn("Media origin failure");
      return textResponse("Media origin error", 502);
    }

    const mime = (originResponse.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!["image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"].includes(mime)) {
      return textResponse("Invalid media content type", 502);
    }
    const headers = new Headers(originResponse.headers);
    headers.set("x-content-type-options", "nosniff");
    headers.set("cache-control", "public, max-age=3600");
    headers.set("x-lumispixel-cache", isRangeRequest ? "BYPASS" : "MISS");

    const response = new Response(originResponse.body, {
      status: originResponse.status,
      statusText: originResponse.statusText,
      headers,
    });

    // Cache only complete successful GET responses. Range/HEAD responses bypass
    // cache to avoid serving partial objects as complete media.
    if (request.method === "GET" && !isRangeRequest && originResponse.status === 200) {
      const cacheTtl = Number(env.MEDIA_EDGE_CACHE_TTL || 86400);
      if (Number.isFinite(cacheTtl) && cacheTtl > 0) {
        const cacheResponse = new Response(response.clone().body, response);
        cacheResponse.headers.set("cache-control", `public, max-age=${Math.floor(cacheTtl)}`);
        try { await cache.put(cacheKey, cacheResponse); } catch { console.warn("Media cache write failed"); }
      }
    }

    return response;
  },
};
