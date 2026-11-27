import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { handleRequest } from "./app/index.ts";

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
