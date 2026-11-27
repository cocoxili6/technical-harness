import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { requestEmailCode, verifyEmailCode } = vi.hoisted(() => ({
  requestEmailCode: vi.fn(),
  verifyEmailCode: vi.fn(),
}));

vi.mock("../src/lib/supabase", () => ({
  isSupabaseConfigured: true,
  requestEmailCode,
  verifyEmailCode,
}));

import AuthGate from "../src/components/AuthGate.vue";

describe("AuthGate email OTP", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("requests an email code and opens code-entry state", async () => {
    requestEmailCode.mockResolvedValue(undefined);
    const wrapper = mount(AuthGate);

    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    await wrapper.get("form").trigger("submit");

    expect(requestEmailCode).toHaveBeenCalledWith("reader@example.com");
    expect(wrapper.get('input[autocomplete="one-time-code"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("验证码已发送");
  });

  it("shows invalid-code errors and verifies a valid code", async () => {
    verifyEmailCode.mockRejectedValueOnce(new Error("验证码无效"));
    const wrapper = mount(AuthGate);
    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    requestEmailCode.mockResolvedValue(undefined);
    await wrapper.get("form").trigger("submit");
    await wrapper.get('input[autocomplete="one-time-code"]').setValue("123456");
    await wrapper.get("form").trigger("submit");

    expect(verifyEmailCode).toHaveBeenCalledWith("reader@example.com", "123456");
    expect(wrapper.text()).toContain("验证码无效");
  });

  it("disables resend during the cooldown", async () => {
    vi.useFakeTimers();
    requestEmailCode.mockResolvedValue(undefined);
    const wrapper = mount(AuthGate);
    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    await wrapper.get("form").trigger("submit");
    await wrapper.vm.$nextTick();

    const resend = wrapper.get("button.auth-link:last-child");
    expect(resend.attributes("disabled")).toBeDefined();
    expect(resend.text()).toContain("30 秒后重新发送");
    wrapper.unmount();
    vi.useRealTimers();
  });
});
