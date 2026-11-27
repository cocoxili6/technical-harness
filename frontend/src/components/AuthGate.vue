<script setup lang="ts">
import { ref } from "vue";
import {
  isSupabaseConfigured,
  requestPasswordReset,
  signInWithPassword,
  signUpWithPassword,
} from "../lib/supabase";

const email = ref("");
const password = ref("");
const mode = ref<"login" | "signup" | "recovery">("login");
const busy = ref(false);
const error = ref("");
const notice = ref("");

async function submit(): Promise<void> {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    const normalizedEmail = email.value.trim();
    if (mode.value === "login") {
      await signInWithPassword(normalizedEmail, password.value);
    } else if (mode.value === "signup") {
      const result = await signUpWithPassword(normalizedEmail, password.value);
      if (result.confirmationRequired) {
        mode.value = "login";
        notice.value = "请检查邮箱并完成确认，然后使用密码登录。";
      }
    } else {
      await requestPasswordReset(normalizedEmail);
      notice.value = "密码重置邮件已发送，请检查邮箱。";
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "操作失败，请重试。";
  } finally {
    busy.value = false;
  }
}

function setMode(nextMode: "login" | "signup" | "recovery"): void {
  mode.value = nextMode;
  password.value = "";
  error.value = "";
  notice.value = "";
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="auth-mark" aria-hidden="true">研</div>
      <p class="auth-eyebrow">研途 · 研究工作台</p>
      <h1 id="auth-title">{{ mode === "signup" ? "创建账户" : mode === "recovery" ? "重置密码" : "登录你的账户" }}</h1>
      <p class="auth-description">
        {{ mode === "signup" ? "使用邮箱和密码创建你的研究账户。" : mode === "recovery" ? "输入账户邮箱，我们会发送密码重置链接。" : "使用邮箱和密码登录。" }}
      </p>

      <p v-if="!isSupabaseConfigured" class="auth-message error" role="alert">
        登录服务尚未配置，请设置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY。
      </p>

      <form @submit.prevent="submit">
        <label for="auth-email">邮箱地址</label>
        <label for="auth-password">密码</label>
        <input
          id="auth-email"
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="name@example.com"
          required
          :disabled="busy || !isSupabaseConfigured"
        />
        <input
          id="auth-password"
          v-model="password"
          type="password"
          :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'"
          :placeholder="mode === 'recovery' ? '无需填写' : '至少 8 个字符'"
          :minlength="mode === 'recovery' ? undefined : 8"
          :required="mode !== 'recovery'"
          :disabled="busy || !isSupabaseConfigured || mode === 'recovery'"
        />
        <button class="auth-primary" type="submit" :disabled="busy || !isSupabaseConfigured">
          {{ busy ? "请稍候…" : mode === "signup" ? "创建账户" : mode === "recovery" ? "发送重置邮件" : "登录" }}
        </button>
        <div v-if="mode === 'login'" class="auth-actions">
          <button type="button" class="auth-link" data-action="signup" :disabled="busy" @click="setMode('signup')">创建账户</button>
          <button type="button" class="auth-link" data-action="recovery" :disabled="busy" @click="setMode('recovery')">忘记密码</button>
        </div>
        <div v-else class="auth-actions">
          <button type="button" class="auth-link" :disabled="busy" @click="setMode('login')">返回登录</button>
        </div>
      </form>

      <p v-if="notice" class="auth-message" role="status">{{ notice }}</p>
      <p v-if="error" class="auth-message error" role="alert">{{ error }}</p>
      <p class="auth-footnote">登录后，你的会话、论文清单和长期记忆会安全保存在个人账户中。</p>
    </section>
  </main>
</template>

<style scoped>
.auth-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background: var(--paper);
}

.auth-card {
  width: min(100%, 420px);
  padding: 42px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: 0 22px 70px rgba(44, 37, 25, 0.08);
}

.auth-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 12px;
  background: var(--accent);
  color: #fffaf0;
  font-family: var(--font-serif);
  font-size: 21px;
}

.auth-eyebrow {
  margin: 24px 0 8px;
  color: var(--muted);
  font-size: 12px;
  letter-spacing: 0.08em;
}

h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 500;
}

.auth-description {
  margin: 10px 0 28px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

form {
  display: grid;
  gap: 10px;
}

label {
  color: var(--ink-soft);
  font-size: 12px;
}

input {
  width: 100%;
  min-height: 46px;
  padding: 0 13px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: #fffdf8;
  color: var(--ink);
  font: inherit;
}

input:focus {
  border-color: var(--accent);
  outline: 2px solid color-mix(in srgb, var(--accent) 28%, transparent);
}

.auth-primary {
  min-height: 46px;
  margin-top: 8px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  font: inherit;
  cursor: pointer;
}

.auth-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.auth-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 6px;
}

.auth-link {
  padding: 4px 0;
  border: 0;
  background: none;
  color: var(--accent-deep);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.auth-link:disabled {
  color: var(--muted);
  cursor: not-allowed;
}

.auth-message {
  margin: 16px 0 0;
  color: var(--ok);
  font-size: 12px;
  line-height: 1.5;
}

.auth-message.error {
  color: var(--danger);
}

.auth-footnote {
  margin: 28px 0 0;
  padding-top: 18px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

@media (max-width: 480px) {
  .auth-card {
    padding: 30px 24px;
  }
}
</style>
