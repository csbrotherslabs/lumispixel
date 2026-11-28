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
  return /^(?:private)\/(?:dev|prod)\/$/.test(prefix) ? prefix : "";
}

function safeKey(key) {
  return typeof key === "string" && !/[\\%?#\x00-\x1f\x7f]/.test(key) &&
    key.split("/").every(p => p && p !== "." && p !== "..");
}

function validOrigin(env) {
  const prefix = normalizePrefix(env.B2_ALLOWED_PREFIX);
  if (!prefix) return false;
  const environment = prefix.split("/")[1];
  const bucket = "lumispixel-production-media";
  return env.B2_BUCKET_NAME === bucket &&
    /^[a-z0-9-]+$/.test(env.B2_REGION) &&
    env.B2_ENDPOINT_URL === `https://s3.${env.B2_REGION}.backblazeb2.com`;
}

export function allowedGalleryKey(key, prefix) {
  if (!normalizePrefix(prefix) || !safeKey(key) || !key.startsWith(prefix)) return false;
  const p = key.slice(prefix.length).split("/");
  if (p[0] !== "galleries" || !/^[0-9]+$/.test(p[2] || "") ||
      !(p[1] === "covers-v2" || /^[0-9]+$/.test(p[1] || ""))) return false;
  return (p.length === 5 && p[3] === "originals") ||
    (p.length === 6 && p[3] === "variants" && ["thumbnail", "preview"].includes(p[4]) && p[5].endsWith(".webp")) ||
    (p.length === 4 && p[1] !== "covers-v2" && !["originals", "variants"].includes(p[3]));
}


function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function constantTimeEqual(left, right) {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let i = 0; i < left.length; i += 1) {
    mismatch |= left.charCodeAt(i) ^ right.charCodeAt(i);
  }
  return mismatch === 0;
}

async function expectedSignature(secret, pathname, expires, variant) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${pathname}\n${expires}\n${variant}`),
  );
  return base64Url(new Uint8Array(signed));
}

async function authorize(requestUrl, env) {
  if (!env.MEDIA_SIGNING_SECRET || env.MEDIA_SIGNING_SECRET.length < 32) {
    return { ok: false, response: textResponse("Media signing is not configured", 500) };
  }

  if (["expires", "signature", "variant"].some(k => requestUrl.searchParams.getAll(k).length !== 1)) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }
  const expiresRaw = requestUrl.searchParams.get("expires");
  const signature = requestUrl.searchParams.get("signature");

  if (!expiresRaw || !signature || !/^[1-9][0-9]*$/.test(expiresRaw) || !/^[A-Za-z0-9_-]{43}$/.test(signature)) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const expires = Number(expiresRaw);
  const now = Math.floor(Date.now() / 1000);

  if (!Number.isSafeInteger(expires) || expires <= now) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const maxTtl = Number(env.MEDIA_MAX_SIGNED_URL_TTL || 3600);
  if (!Number.isSafeInteger(maxTtl) || maxTtl > 3600 || maxTtl <= 0 || expires - now > maxTtl) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const variant = requestUrl.searchParams.get("variant");
  if (!["thumbnail", "preview", "original"].includes(variant)) {
    return { ok: false, response: textResponse("Invalid media variant", 400) };
  }
  const expected = await expectedSignature(
    env.MEDIA_SIGNING_SECRET,
    requestUrl.pathname,
    expiresRaw,
    variant,
  );

  if (!constantTimeEqual(expected, signature)) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  return { ok: true };
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
    const authorization = await authorize(requestUrl, env);
    if (!authorization.ok) return authorization.response;

    let objectKey;

    try {
      objectKey = decodeURIComponent(requestUrl.pathname.slice(1));
    } catch {
      return textResponse("Invalid object path", 400);
    }

    const allowedPrefix = normalizePrefix(env.B2_ALLOWED_PREFIX);

    if (!allowedGalleryKey(objectKey, allowedPrefix)) {
      return textResponse("Not found", 404);
    }

    // The requested variant is bound to the HMAC; changing it invalidates the URL.
    const variant = requestUrl.searchParams.get("variant");
    const imageOptions = {
      thumbnail: { width: 640, fit: "scale-down", quality: 82, format: "webp" },
      preview: { width: 2560, fit: "scale-down", quality: 85, format: "webp" },
    };
    if (!["thumbnail", "preview", "original"].includes(variant)) {
      return textResponse("Invalid media variant", 400);
    }

    const cache = caches.default;
    // Versioned key prevents existing path-only original caches from being
    // mistaken for resized previews after deployment.
    const cacheUrl = new URL(requestUrl.origin + requestUrl.pathname);
    cacheUrl.searchParams.set("delivery", "v3");
    cacheUrl.searchParams.set("variant", variant);
    const cacheKey = new Request(cacheUrl.toString(), { method: "GET" });
    const isRangeRequest = request.headers.has("range");
    if (isRangeRequest && variant !== "original") {
      return textResponse("Range requests require original variant", 400);
    }

    // Authorization always runs before cache access. Query-string credentials are
    // deliberately excluded from the cache key so authorized viewers share one
    // cached object without making the cache itself a public authorization bypass.
    if (request.method === "GET" && !isRangeRequest) {
      const cachedResponse = await cache.match(cacheKey);
      if (cachedResponse) {
        const headers = new Headers(cachedResponse.headers);
        headers.set("x-lumispixel-cache", "HIT");
        headers.set("cache-control", "private, no-store");
        return new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers,
        });
      }
    }

    // Display media is served exclusively from pre-generated B2 objects.
    // Never transform large originals during a request or silently serve originals.
    let fetchKey = objectKey;
    if (variant !== "original") {
      const parts = objectKey.split("/");
      const index = parts.lastIndexOf("originals");
      if (index < 0 || index !== parts.length - 2) {
        return textResponse("Invalid original media path", 400);
      }
      const basename = parts[parts.length - 1];
      const dot = basename.lastIndexOf(".");
      if (dot <= 0) return textResponse("Invalid original media filename", 400);
      const stem = basename.slice(0, dot);
      parts[index] = "variants";
      fetchKey = [...parts.slice(0, -1), variant, stem + ".webp"].join("/");
    }

    if (!allowedGalleryKey(fetchKey, allowedPrefix)) return textResponse("Invalid media path", 400);
    const endpoint = String(env.B2_ENDPOINT_URL || "").replace(/\/+$/, "");
    const bucket = encodeURIComponent(env.B2_BUCKET_NAME);
    const encodedKey = fetchKey.split("/").map(encodeURIComponent).join("/");
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
      headers: isRangeRequest
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
      console.warn("Media origin failure");
      return textResponse("Media variant not ready", 404);
    }
    if (!originResponse.ok && originResponse.status !== 206) {
      console.warn("Media origin failure");
      return textResponse("Media origin error", 502);
    }
    if (variant !== "original") {
      const contentType = (originResponse.headers.get("content-type") || "").toLowerCase();
      if (contentType.split(";")[0].trim() !== "image/webp") {
        console.warn("Media origin failure");
        return textResponse("Invalid media variant", 502);
      }
    }

    const headers = new Headers(originResponse.headers);
    headers.set("x-content-type-options", "nosniff");
    headers.set("cache-control", "private, no-store");
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
