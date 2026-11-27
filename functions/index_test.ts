import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { handleRequest } from "./app/proxy.ts";

Deno.test("forwards user bearer separately from gateway credential", async () => {
  let receivedHeaders: Headers | undefined;
  const userToken = "Bearer supabase-user-token";
  const response = await handleRequest(
    new Request("https://site.test/api/threads", {
      headers: { authorization: userToken },
    }),
    "https://backend.test",
    "edge-secret",
    async (_input, init) => {
      receivedHeaders = new Headers(init?.headers);
      return new Response(JSON.stringify({ threads: [] }), {
        headers: { "content-type": "application/json" },
      });
    },
  );

  assertEquals(response.status, 200);
  assertEquals(receivedHeaders?.get("authorization"), userToken);
  assertEquals(receivedHeaders?.get("x-harness-gateway-token"), "edge-secret");
});

Deno.test("does not substitute gateway credential for missing user token", async () => {
  let receivedHeaders: Headers | undefined;
  await handleRequest(
    new Request("https://site.test/api/threads"),
    "https://backend.test",
    "edge-secret",
    async (_input, init) => {
      receivedHeaders = new Headers(init?.headers);
      return new Response("{}", { headers: { "content-type": "application/json" } });
    },
  );

  assertEquals(receivedHeaders?.has("authorization"), false);
  assertEquals(receivedHeaders?.get("x-harness-gateway-token"), "edge-secret");
});

Deno.test("accepts canonical UUID thread identifiers", async () => {
  let upstreamUrl = "";
  const threadId = "123e4567-e89b-42d3-a456-426614174000";
  const response = await handleRequest(
    new Request(`https://site.test/api/threads/${threadId}`),
    "https://backend.test",
    "edge-secret",
    async (input) => {
      upstreamUrl = String(input);
      return new Response(JSON.stringify({ id: threadId }), {
        headers: { "content-type": "application/json" },
      });
    },
  );

  assertEquals(response.status, 200);
  assertEquals(upstreamUrl, `https://backend.test/api/threads/${threadId}`);
});

Deno.test("preserves streamed SSE response body", async () => {
  const payload = "event: token\ndata: {\"text\":\"hi\"}\n\n";
  const response = await handleRequest(
    new Request("https://site.test/api/chat/stream", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: "hello" }),
    }),
    "https://backend.test",
    "edge-secret",
    async () =>
      new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(payload));
          controller.close();
        },
      }), {
        headers: { "content-type": "text/event-stream" },
      }),
  );

  assertEquals(response.headers.get("content-type"), "text/event-stream");
  assertEquals(response.headers.get("x-accel-buffering"), "no");
  assertEquals(await response.text(), payload);
});
