import { beforeEach, describe, expect, it, vi } from "vitest";

const { getAccessToken, refreshAccessToken } = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock("../src/lib/supabase", () => ({ getAccessToken, refreshAccessToken }));

import { listThreads, streamChat } from "../src/lib/api";

describe("API authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("attaches the current bearer token to JSON requests", async () => {
    getAccessToken.mockResolvedValue("access-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ threads: [] }), {
        headers: { "content-type": "application/json" },
      }),
    ));

    await listThreads();

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer access-token");
  });

  it("attaches a refreshed token once after an unauthorized response", async () => {
    getAccessToken.mockResolvedValue("expired-token");
    refreshAccessToken.mockResolvedValue("refreshed-token");
    const observedHeaders: Headers[] = [];
    const fetchMock = vi.fn((_input, init) => {
      observedHeaders.push(new Headers(init?.headers));
      if (observedHeaders.length === 1) {
        return Promise.resolve(new Response("unauthorized", { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ threads: [] }), {
        headers: { "content-type": "application/json" },
      }));
    });
    vi.stubGlobal("fetch", fetchMock);

    await listThreads();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(observedHeaders[0].get("authorization")).toBe("Bearer expired-token");
    expect(observedHeaders[1].get("authorization")).toBe("Bearer refreshed-token");
  });

  it("attaches the current token to SSE requests", async () => {
    getAccessToken.mockResolvedValue("stream-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(new ReadableStream({
        start(controller) {
          controller.close();
        },
      }), { headers: { "content-type": "text/event-stream" } }),
    ));
    const handlers = {
      onMeta: vi.fn(),
      onToken: vi.fn(),
      onToolStart: vi.fn(),
      onToolEnd: vi.fn(),
      onSources: vi.fn(),
      onDone: vi.fn(),
    };

    await streamChat({ message: "question" }, handlers);

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer stream-token");
  });
});
