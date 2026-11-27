import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { signUpWithPassword, signInWithPassword, requestPasswordReset } = vi.hoisted(() => ({
  signUpWithPassword: vi.fn(),
  signInWithPassword: vi.fn(),
  requestPasswordReset: vi.fn(),
}));

vi.mock("../src/lib/supabase", () => ({
  isSupabaseConfigured: true,
  signUpWithPassword,
  signInWithPassword,
  requestPasswordReset,
}));

import AuthGate from "../src/components/AuthGate.vue";

describe("AuthGate email and password", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("signs in with the submitted email and password", async () => {
    signInWithPassword.mockResolvedValue(undefined);
    const wrapper = mount(AuthGate);

    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    await wrapper.get('input[type="password"]').setValue("correct-horse-123");
    await wrapper.get("form").trigger("submit");

    expect(signInWithPassword).toHaveBeenCalledWith("reader@example.com", "correct-horse-123");
  });

  it("creates an account with email and password", async () => {
    signUpWithPassword.mockResolvedValue({ confirmationRequired: true });
    const wrapper = mount(AuthGate);
    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    await wrapper.get('button[data-action="signup"]').trigger("click");
    await wrapper.get('input[type="password"]').setValue("correct-horse-123");
    await wrapper.get("form").trigger("submit");

    expect(signUpWithPassword).toHaveBeenCalledWith("reader@example.com", "correct-horse-123");
    expect(wrapper.text()).toContain("请检查邮箱并完成确认");
  });

  it("sends a password recovery email", async () => {
    requestPasswordReset.mockResolvedValue(undefined);
    const wrapper = mount(AuthGate);
    await wrapper.get('input[type="email"]').setValue("reader@example.com");
    await wrapper.get('button[data-action="signup"]').trigger("click");
    await wrapper.vm.$nextTick();
    await wrapper.get("button.auth-link").trigger("click");
    await wrapper.vm.$nextTick();
    await wrapper.get('button[data-action="recovery"]').trigger("click");
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("重置密码");
    await wrapper.get("form").trigger("submit");
    await wrapper.vm.$nextTick();

    expect(requestPasswordReset).toHaveBeenCalledWith("reader@example.com");
    expect(wrapper.text()).toContain("密码重置邮件已发送");
  });
});
