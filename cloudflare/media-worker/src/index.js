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

async function expectedSignature(secret, pathname, expires) {
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
    new TextEncoder().encode(`${pathname}\n${expires}`),
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

  const expected = await expectedSignature(
    env.MEDIA_SIGNING_SECRET,
    requestUrl.pathname,
    expiresRaw,
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

    if (!env.B2_ACCESS_KEY_ID || !env.B2_SECRET_ACCESS_KEY) {
      return textResponse("Media origin credentials are not configured", 500);
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

    const originRequest = await aws.sign(originUrl, {
      method: request.method,
      headers: request.headers.has("range")
        ? { range: request.headers.get("range") }
        : {},
    });

    const originResponse = await fetch(originRequest);

    if (originResponse.status === 404) {
      return textResponse("Not found", 404);
    }

    if (!originResponse.ok && originResponse.status !== 206) {
      console.error("B2 media origin error", {
        status: originResponse.status,
        key: objectKey,
      });
      return textResponse("Media origin error", 502);
    }

    const headers = new Headers(originResponse.headers);
    headers.set("x-content-type-options", "nosniff");
    headers.set("cache-control", "private, no-store");

    return new Response(originResponse.body, {
      status: originResponse.status,
      statusText: originResponse.statusText,
      headers,
    });
  },
};
