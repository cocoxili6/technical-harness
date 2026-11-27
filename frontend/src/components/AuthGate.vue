<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { isSupabaseConfigured, requestEmailCode, verifyEmailCode } from "../lib/supabase";

const email = ref("");
const code = ref("");
const stage = ref<"email" | "code">("email");
const busy = ref(false);
const error = ref("");
const notice = ref("");
const resendSeconds = ref(0);
let resendTimer: number | undefined;

function startResendCooldown(): void {
  resendSeconds.value = 30;
  window.clearInterval(resendTimer);
  resendTimer = window.setInterval(() => {
    resendSeconds.value -= 1;
    if (resendSeconds.value <= 0) {
      resendSeconds.value = 0;
      window.clearInterval(resendTimer);
    }
  }, 1000);
}

async function submitEmail(): Promise<void> {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    await requestEmailCode(email.value.trim());
    stage.value = "code";
    notice.value = "验证码已发送，请检查邮箱。";
    startResendCooldown();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "验证码发送失败，请重试。";
  } finally {
    busy.value = false;
  }
}

async function submitCode(): Promise<void> {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    await verifyEmailCode(email.value.trim(), code.value.trim());
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "验证码无效，请重试。";
  } finally {
    busy.value = false;
  }
}

async function resendCode(): Promise<void> {
  if (resendSeconds.value > 0 || busy.value) return;
  await submitEmail();
}

function editEmail(): void {
  stage.value = "email";
  code.value = "";
  error.value = "";
  notice.value = "";
}

onBeforeUnmount(() => window.clearInterval(resendTimer));
</script>

<template>
  <main class="auth-page">
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="auth-mark" aria-hidden="true">研</div>
      <p class="auth-eyebrow">研途 · 研究工作台</p>
      <h1 id="auth-title">{{ stage === "email" ? "登录你的账户" : "输入邮箱验证码" }}</h1>
      <p class="auth-description">
        {{ stage === "email" ? "输入邮箱，我们会发送一次性验证码。" : `验证码已发送至 ${email}` }}
      </p>

      <p v-if="!isSupabaseConfigured" class="auth-message error" role="alert">
        登录服务尚未配置，请设置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY。
      </p>

      <form v-if="stage === 'email'" @submit.prevent="submitEmail">
        <label for="auth-email">邮箱地址</label>
        <input
          id="auth-email"
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="name@example.com"
          required
          :disabled="busy || !isSupabaseConfigured"
        />
        <button class="auth-primary" type="submit" :disabled="busy || !isSupabaseConfigured">
          {{ busy ? "正在发送…" : "发送一次性验证码" }}
        </button>
      </form>

      <form v-else @submit.prevent="submitCode">
        <label for="auth-code">一次性验证码</label>
        <input
          id="auth-code"
          v-model="code"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          placeholder="输入邮箱中的验证码"
          minlength="6"
          maxlength="8"
          required
          :disabled="busy"
        />
        <button class="auth-primary" type="submit" :disabled="busy">
          {{ busy ? "正在验证…" : "验证并登录" }}
        </button>
        <div class="auth-actions">
          <button type="button" class="auth-link" @click="editEmail">更换邮箱</button>
          <button
            type="button"
            class="auth-link"
            :disabled="busy || resendSeconds > 0"
            @click="resendCode"
          >
            {{ resendSeconds > 0 ? `${resendSeconds} 秒后重新发送` : "重新发送验证码" }}
          </button>
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
