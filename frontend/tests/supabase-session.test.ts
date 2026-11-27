import { beforeEach, describe, expect, it, vi } from "vitest";

const { authMethods } = vi.hoisted(() => ({
  authMethods: {
    signUp: vi.fn(),
    signInWithPassword: vi.fn(),
    resetPasswordForEmail: vi.fn(),
    updateUser: vi.fn(),
    getSession: vi.fn(),
    refreshSession: vi.fn(),
    signOut: vi.fn(),
    onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
  },
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => ({ auth: authMethods })),
}));

describe("Supabase email session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("VITE_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "publishable-test-key");
    vi.resetModules();
  });

  it("signs up and signs in with email and password", async () => {
    const session = {
      access_token: "verified-access-token",
      user: { id: "user-1", email: "reader@example.com" },
    };
    authMethods.signUp.mockResolvedValue({ data: { session: null, user: session.user }, error: null });
    authMethods.signInWithPassword.mockResolvedValue({ data: { session }, error: null });
    const auth = await import("../src/lib/supabase");

    const signup = await auth.signUpWithPassword("reader@example.com", "password-123");
    const verified = await auth.signInWithPassword("reader@example.com", "password-123");

    expect(authMethods.signUp).toHaveBeenCalledWith({
      email: "reader@example.com",
      password: "password-123",
    });
    expect(signup.confirmationRequired).toBe(true);
    expect(authMethods.signInWithPassword).toHaveBeenCalledWith({
      email: "reader@example.com",
      password: "password-123",
    });
    expect(verified).toBe(session);
    expect(auth.authSession.value).toEqual(session);
  });

  it("requests password reset and updates the password from a recovery session", async () => {
    authMethods.resetPasswordForEmail.mockResolvedValue({ error: null });
    authMethods.updateUser.mockResolvedValue({ error: null });
    const auth = await import("../src/lib/supabase");

    await auth.requestPasswordReset("reader@example.com");
    auth.passwordRecoveryPending.value = true;
    await auth.updatePassword("new-password-123");

    expect(authMethods.resetPasswordForEmail).toHaveBeenCalledWith(
      "reader@example.com",
      { redirectTo: window.location.origin },
    );
    expect(authMethods.updateUser).toHaveBeenCalledWith({ password: "new-password-123" });
    expect(auth.passwordRecoveryPending.value).toBe(false);
  });
});
