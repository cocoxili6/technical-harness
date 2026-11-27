import { beforeEach, describe, expect, it, vi } from "vitest";

const { authMethods } = vi.hoisted(() => ({
  authMethods: {
    signInWithOtp: vi.fn(),
    verifyOtp: vi.fn(),
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

  it("requests an OTP and stores the verified session", async () => {
    const session = {
      access_token: "verified-access-token",
      user: { id: "user-1", email: "reader@example.com" },
    };
    authMethods.signInWithOtp.mockResolvedValue({ error: null });
    authMethods.verifyOtp.mockResolvedValue({ data: { session }, error: null });
    const auth = await import("../src/lib/supabase");

    await auth.requestEmailCode("reader@example.com");
    const verified = await auth.verifyEmailCode("reader@example.com", "321654");

    expect(authMethods.signInWithOtp).toHaveBeenCalledWith({
      email: "reader@example.com",
      options: { shouldCreateUser: true },
    });
    expect(authMethods.verifyOtp).toHaveBeenCalledWith({
      email: "reader@example.com",
      token: "321654",
      type: "email",
    });
    expect(verified).toBe(session);
    expect(auth.authSession.value).toEqual(session);
  });
});
