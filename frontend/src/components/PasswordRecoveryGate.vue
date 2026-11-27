<script setup lang="ts">
import { ref } from "vue";
import { updatePassword } from "../lib/supabase";

const password = ref("");
const busy = ref(false);
const error = ref("");

async function submit(): Promise<void> {
  error.value = "";
  busy.value = true;
  try {
    await updatePassword(password.value);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "密码更新失败，请重试。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="recovery-page">
    <section class="recovery-panel">
      <p class="recovery-brand">研途 · 研究工作台</p>
      <h1>设置新密码</h1>
      <p>为你的账户设置一个新密码，然后继续使用研究工作台。</p>
      <form @submit.prevent="submit">
        <label for="new-password">新密码</label>
        <input
          id="new-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          required
          :disabled="busy"
        />
        <button type="submit" :disabled="busy">{{ busy ? "正在更新…" : "更新密码" }}</button>
      </form>
      <p v-if="error" class="recovery-error" role="alert">{{ error }}</p>
    </section>
  </main>
</template>

<style scoped>
.recovery-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background: var(--paper);
}

.recovery-panel {
  width: min(100%, 420px);
  padding: 40px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
}

.recovery-brand { color: var(--muted); font-size: 12px; }
h1 { margin: 22px 0 8px; font-family: var(--font-serif); font-size: 26px; font-weight: 500; }
p { color: var(--muted); font-size: 13px; line-height: 1.6; }
form { display: grid; gap: 10px; margin-top: 24px; }
label { color: var(--ink-soft); font-size: 12px; }
input { min-height: 46px; padding: 0 12px; border: 1px solid var(--line-strong); border-radius: 8px; background: #fffdf8; font: inherit; }
button { min-height: 46px; margin-top: 8px; border: 0; border-radius: 8px; background: var(--accent); color: white; font: inherit; cursor: pointer; }
button:disabled { opacity: .6; cursor: not-allowed; }
.recovery-error { color: var(--danger); }
</style>
