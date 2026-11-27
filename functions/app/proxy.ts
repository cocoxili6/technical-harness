// Request validation and forwarding for the Qoder Sites Edge Function.

const API_MARKER = "/api/";
const CHAT_PATH = "/api/chat/stream";
const HEALTH_PATH = "/api/health";
const THREADS_PATH = "/api/threads";
const MEMORIES_PATH = "/api/memories";
const THREAD_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const MEMORY_ID_PATTERN = /^[A-Za-z0-9-]{8,64}$/;
const MAX_BODY_BYTES = 16_384;

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function fail(status: number, code: string, message: string): Response {
  return jsonResponse(status, { error: code, message });
}

export async function handleRequest(
  request: Request,
  configuredBackendUrl: string,
  sharedToken: string,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  const backendUrl = configuredBackendUrl.replace(/\/+$/, "");

  if (!backendUrl || !sharedToken) {
    return fail(503, "service_not_configured", "The harness backend is not configured.");
  }
  if (!/^https?:\/\//.test(backendUrl)) {
    return fail(503, "service_not_configured", "The harness backend URL is invalid.");
  }

  const requestUrl = new URL(request.url);
  const markerIndex = requestUrl.pathname.indexOf(API_MARKER);
  if (markerIndex === -1) {
    return fail(404, "not_found", "Unknown endpoint.");
  }
  const apiPath = requestUrl.pathname.slice(markerIndex);

  const isChat = request.method === "POST" && apiPath === CHAT_PATH;
  const isHealth = request.method === "GET" && apiPath === HEALTH_PATH;
  const isThreads = request.method === "GET" && apiPath === THREADS_PATH;
  const isThread =
    request.method === "GET" &&
    apiPath.startsWith(THREADS_PATH + "/") &&
    THREAD_ID_PATTERN.test(apiPath.slice(THREADS_PATH.length + 1));
  const isMemoryList = request.method === "GET" && apiPath === MEMORIES_PATH;
  const isMemoryAdd = request.method === "POST" && apiPath === MEMORIES_PATH;
  const isMemoryReview =
    request.method === "POST" &&
    apiPath.startsWith(MEMORIES_PATH + "/") &&
    apiPath.endsWith("/review") &&
    MEMORY_ID_PATTERN.test(
      apiPath.slice(MEMORIES_PATH.length + 1, -"/review".length),
    );
  const isMemoryDelete =
    request.method === "DELETE" &&
    apiPath.startsWith(MEMORIES_PATH + "/") &&
    MEMORY_ID_PATTERN.test(apiPath.slice(MEMORIES_PATH.length + 1));

  if (
    !isChat &&
    !isHealth &&
    !isThreads &&
    !isThread &&
    !isMemoryList &&
    !isMemoryAdd &&
    !isMemoryReview &&
    !isMemoryDelete
  ) {
    return fail(404, "not_found", "Unknown endpoint.");
  }

  const upstreamHeaders = new Headers();
  upstreamHeaders.set("accept", request.headers.get("accept") ?? "*/*");
  const userAuthorization = request.headers.get("authorization");
  if (userAuthorization) {
    upstreamHeaders.set("authorization", userAuthorization);
  }
  upstreamHeaders.set("x-harness-gateway-token", sharedToken);

  let body: BodyInit | undefined;

  if (isChat || isMemoryAdd) {
    const contentType = request.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return fail(415, "unsupported_media_type", "Expected an application/json body.");
    }

    const rawBody = await request.text();
    if (rawBody.length > MAX_BODY_BYTES) {
      return fail(413, "payload_too_large", "The request body is too large.");
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawBody);
    } catch {
      return fail(400, "invalid_json", "The request body is not valid JSON.");
    }
    if (!parsed || typeof parsed !== "object") {
      return fail(400, "invalid_body", "The request body is invalid.");
    }

    if (isChat) {
      const message = (parsed as { message?: unknown }).message;
      const threadId = (parsed as { thread_id?: unknown }).thread_id;

      if (
        typeof message !== "string" ||
        message.trim().length === 0 ||
        message.length > 4000
      ) {
        return fail(422, "invalid_message", "message must be between 1 and 4000 characters.");
      }
      if (threadId !== undefined && (typeof threadId !== "string" || !THREAD_ID_PATTERN.test(threadId))) {
        return fail(422, "invalid_thread", "thread_id is invalid.");
      }
    } else {
      const text = (parsed as { text?: unknown }).text;
      if (typeof text !== "string" || text.trim().length === 0 || text.length > 300) {
        return fail(422, "invalid_memory", "text must be between 1 and 300 characters.");
      }
    }

    upstreamHeaders.set("content-type", "application/json");
    body = rawBody;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300_000);
  const abortUpstream = () => controller.abort();
  const cleanup = () => {
    clearTimeout(timeoutId);
    request.signal.removeEventListener("abort", abortUpstream);
  };

  if (request.signal.aborted) {
    controller.abort();
  } else {
    request.signal.addEventListener("abort", abortUpstream, { once: true });
  }

  let upstream: Response;
  try {
    upstream = await fetcher(`${backendUrl}${apiPath}${requestUrl.search}`, {
      method: request.method,
      headers: upstreamHeaders,
      body,
      signal: controller.signal,
      redirect: "error",
    });
  } catch {
    cleanup();
    return fail(502, "service_unavailable", "The harness backend is unavailable.");
  }

  const responseHeaders = new Headers();
  responseHeaders.set(
    "content-type",
    upstream.headers.get("content-type") ?? "application/octet-stream",
  );
  responseHeaders.set("cache-control", "no-store");

  if (!isChat) {
    try {
      return new Response(await upstream.text(), {
        status: upstream.status,
        headers: responseHeaders,
      });
    } finally {
      cleanup();
    }
  }

  responseHeaders.set("x-accel-buffering", "no");
  if (!upstream.body) {
    cleanup();
    return new Response(null, { status: upstream.status, headers: responseHeaders });
  }
  const reader = upstream.body.getReader();
  const stream = new ReadableStream<Uint8Array>({
    async pull(streamController) {
      try {
        const result = await reader.read();
        if (result.done) {
          streamController.close();
          cleanup();
        } else {
          streamController.enqueue(result.value);
        }
      } catch (error) {
        cleanup();
        streamController.error(error);
      }
    },
    async cancel(reason) {
      try {
        await reader.cancel(reason);
      } finally {
        cleanup();
      }
    },
  });
  return new Response(stream, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
