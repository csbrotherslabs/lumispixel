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
  return String(prefix || "").replace(/^\/+/, "").replace(/\/+$/, "") + "/";
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
  if (!env.MEDIA_SIGNING_SECRET) {
    return { ok: false, response: textResponse("Media signing is not configured", 500) };
  }

  const expiresRaw = requestUrl.searchParams.get("expires");
  const signature = requestUrl.searchParams.get("signature");

  if (!expiresRaw || !signature || !/^\d+$/.test(expiresRaw)) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const expires = Number(expiresRaw);
  const now = Math.floor(Date.now() / 1000);

  if (!Number.isSafeInteger(expires) || expires <= now) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const maxTtl = Number(env.MEDIA_MAX_SIGNED_URL_TTL || 3600);
  if (!Number.isFinite(maxTtl) || maxTtl <= 0 || expires - now > maxTtl) {
    return { ok: false, response: textResponse("Forbidden", 403) };
  }

  const variant = requestUrl.searchParams.get("variant") || "original";
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

    if (!String(env.B2_ENDPOINT_URL).startsWith("https://")) {
      return textResponse("Media origin configuration is invalid", 500);
    }

    const requestUrl = new URL(request.url);
    const authorization = await authorize(requestUrl, env);
    if (!authorization.ok) return authorization.response;

    let objectKey;

    try {
      objectKey = decodeURIComponent(requestUrl.pathname.replace(/^\/+/, ""));
    } catch {
      return textResponse("Invalid object path", 400);
    }

    const allowedPrefix = normalizePrefix(env.B2_ALLOWED_PREFIX);

    if (!objectKey || !objectKey.startsWith(allowedPrefix)) {
      return textResponse("Not found", 404);
    }

    // The requested variant is bound to the HMAC; changing it invalidates the URL.
    const variant = requestUrl.searchParams.get("variant") || "original";
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
    cacheUrl.searchParams.set("delivery", "v2");
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

    const endpoint = String(env.B2_ENDPOINT_URL || "").replace(/\\/+$/, "");
    const bucket = encodeURIComponent(env.B2_BUCKET_NAME);
    const encodedKey = fetchKey.split("/").map(encodeURIComponent).join("/");
    const originUrl = `${endpoint}/${bucket}/${encodedKey}`;

    const aws = new AwsClient({
      accessKeyId: env.B2_ACCESS_KEY_ID,
      secretAccessKey: env.B2_SECRET_ACCESS_KEY,
      service: "s3",
      region: env.B2_REGION,
    });

    const originRequest = await aws.sign(originUrl, {
      method: request.method,
      headers: isRangeRequest
        ? { range: request.headers.get("range") }
        : {},
    });

    let originResponse;
    try {
      originResponse = await fetch(originRequest);
    } catch (error) {
      console.error("B2 transport failure", { key: fetchKey, error: String(error) });
      return textResponse("Media origin unavailable", 502);
    }

    if (originResponse.status === 404) {
      console.warn("B2 object missing", { key: fetchKey, variant });
      return textResponse("Media variant not ready", 404);
    }
    if (!originResponse.ok && originResponse.status !== 206) {
      console.error("B2 origin rejected request", {
        status: originResponse.status, key: fetchKey,
        requestId: originResponse.headers.get("x-amz-request-id"),
      });
      return textResponse("Media origin error", 502);
    }
    if (variant !== "original" && request.method === "GET") {
      const contentType = (originResponse.headers.get("content-type") || "").toLowerCase();
      if (!contentType.startsWith("image/webp")) {
        console.error("Invalid derivative content type", { key: fetchKey, contentType });
        return textResponse("Invalid media variant", 502);
      }
    }

    const headers = new Headers(originResponse.headers);
    headers.set("x-content-type-options", "nosniff");
    headers.set("cache-control", "private, max-age=0, no-cache");
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
        await cache.put(cacheKey, cacheResponse);
      }
    }

    return response;
  },
};
