import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { ref } from "vue";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
    })
  : null;

export const authSession = ref<Session | null>(null);
export const authReady = ref(false);

let initialized = false;

export async function initializeSupabaseAuth(): Promise<void> {
  if (initialized) return;
  initialized = true;
  if (!supabase) {
    authReady.value = true;
    return;
  }

  supabase.auth.onAuthStateChange((_event, session) => {
    authSession.value = session;
    authReady.value = true;
  });
  try {
    const { data, error } = await supabase.auth.getSession();
    authSession.value = error ? null : data.session;
  } catch {
    authSession.value = null;
  } finally {
    authReady.value = true;
  }
}

export async function requestEmailCode(email: string): Promise<void> {
  if (!supabase) throw new Error("登录服务尚未配置，请设置 Supabase 前端环境变量。");
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { shouldCreateUser: true },
  });
  if (error) throw error;
}

export async function verifyEmailCode(email: string, code: string): Promise<Session> {
  if (!supabase) throw new Error("登录服务尚未配置，请设置 Supabase 前端环境变量。");
  const { data, error } = await supabase.auth.verifyOtp({
    email,
    token: code,
    type: "email",
  });
  if (error) throw error;
  if (!data.session) throw new Error("验证完成，但未能建立登录会话，请重试。");
  authSession.value = data.session;
  authReady.value = true;
  return data.session;
}

export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.auth.getSession();
  if (error) return null;
  return data.session?.access_token ?? null;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.auth.refreshSession();
  if (error) return null;
  authSession.value = data.session;
  return data.session?.access_token ?? null;
}

export async function signOut(): Promise<void> {
  if (!supabase) {
    authSession.value = null;
    return;
  }
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
  authSession.value = null;
}
