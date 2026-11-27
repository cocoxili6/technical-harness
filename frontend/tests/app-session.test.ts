import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { authReady, authSession } from "../src/lib/supabase";

const { getHealth, getThread, listMemories, listThreads } = vi.hoisted(() => ({
  getHealth: vi.fn(),
  getThread: vi.fn(),
  listMemories: vi.fn(),
  listThreads: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  getHealth,
  getThread,
  listMemories,
  listThreads,
  streamChat: vi.fn(),
}));

import App from "../src/App.vue";

describe("account session boundary", () => {
  beforeEach(() => {
    const values = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    });
    authReady.value = true;
    authSession.value = {
      access_token: "token",
      refresh_token: "refresh",
      token_type: "bearer",
      expires_in: 3600,
      expires_at: Date.now() / 1000 + 3600,
      user: { id: "user-a", email: "reader@example.com" },
    } as never;
    getHealth.mockResolvedValue({
      status: "ok",
      demo_mode: false,
      llm_configured: true,
      model: "test",
      search: "arXiv",
      memory: "Supabase",
    });
    listThreads.mockResolvedValue({
      threads: [{ id: "thread-a", title: "我的会话", created_at: "now", updated_at: "now", message_count: 1 }],
    });
    getThread.mockResolvedValue({
      id: "thread-a",
      title: "我的会话",
      created_at: "now",
      messages: [{ role: "user", content: "private text" }],
    });
    listMemories.mockResolvedValue({
      items: [],
      stats: { active: 0, forgotten: 0, avg_retention: 0 },
    });
  });

  it("clears account-bound workspace state and local thread on sign-out", async () => {
    localStorage.setItem("yantu.activeThread", "thread-a");
    const wrapper = mount(App, { global: { stubs: true } });
    await flushPromises();

    expect(wrapper.text()).toContain("我的会话");
    expect(localStorage.getItem("yantu.activeThread")).toBe("thread-a");

    const healthCalls = getHealth.mock.calls.length;
    authSession.value = { ...authSession.value!, access_token: "rotated-token" };
    await flushPromises();
    expect(getHealth).toHaveBeenCalledTimes(healthCalls);

    await wrapper.get(".sign-out-button").trigger("click");
    await flushPromises();

    expect(authSession.value).toBeNull();
    expect(localStorage.getItem("yantu.activeThread")).toBeNull();
    expect(wrapper.text()).toContain("登录你的账户");
    wrapper.unmount();
  });
});
