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

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return textResponse("Method not allowed", 405);
    }

    if (!env.B2_ACCESS_KEY_ID || !env.B2_SECRET_ACCESS_KEY) {
      return textResponse("Media origin credentials are not configured", 500);
    }

    const requestUrl = new URL(request.url);
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
