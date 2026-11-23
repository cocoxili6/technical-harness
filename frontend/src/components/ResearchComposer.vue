<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import ProfilePicker from "./ProfilePicker.vue";
import type { LearningProfile } from "../types";

const props = defineProps<{
  variant: "hero" | "docked";
  streaming: boolean;
  disabled: boolean;
  submitLabel: string;
}>();

const emit = defineEmits<{
  (e: "submit", text: string): void;
  (e: "stop"): void;
}>();

const profile = defineModel<LearningProfile>("profile", { required: true });

const draft = defineModel<string>({ default: "" });
const textarea = ref<HTMLTextAreaElement | null>(null);

const placeholder = computed(() =>
  props.variant === "hero"
    ? "例如：我想入门多智能体强化学习中的信用分配问题，应该从哪里开始？"
    : "继续追问，或换一个角度……",
);

function resize(): void {
  const element = textarea.value;
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight, 168)}px`;
}

watch(draft, () => {
  void nextTick(resize);
});

onMounted(() => {
  void nextTick(resize);
});

function submit(): void {
  const text = draft.value.trim();
  if (!text || props.streaming || props.disabled) return;
  emit("submit", text);
  draft.value = "";
  void nextTick(resize);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  submit();
}

function focus(): void {
  textarea.value?.focus({ preventScroll: true });
}

defineExpose({ focus });
</script>

<template>
  <form class="composer" :class="variant" @submit.prevent="submit">
    <ProfilePicker
      v-if="variant === 'hero'"
      v-model="profile"
      :disabled="disabled || streaming"
    />
    <label class="sr-only" for="research-input">研究问题</label>
    <textarea
      id="research-input"
      ref="textarea"
      v-model="draft"
      rows="2"
      :placeholder="placeholder"
      @input="resize"
      @keydown="onKeydown"
    ></textarea>
    <div class="composer-bottom">
      <span class="composer-hint">Enter 发送 · Shift + Enter 换行</span>
      <div class="composer-actions">
        <button
          v-if="streaming"
          type="button"
          class="stop-btn"
          @click="$emit('stop')"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <rect
              x="4"
              y="4"
              width="8"
              height="8"
              stroke="currentColor"
              stroke-width="1.4"
            />
          </svg>
          停止生成
        </button>
        <button
          v-else
          type="submit"
          class="send-btn"
          :disabled="disabled || !draft.trim()"
        >
          {{ submitLabel }}
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M8 13V3M8 3 3.5 7.5M8 3l4.5 4.5"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  </form>
</template>

<style scoped>
.composer {
  border: 1px solid var(--line-strong);
  background: var(--surface);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.composer:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(166, 58, 43, 0.07);
}

.composer.hero {
  padding: 18px 18px 13px;
  box-shadow: 0 24px 50px -42px rgba(32, 30, 26, 0.6);
}

.composer.docked {
  padding: 9px 12px 7px;
  border-color: var(--line);
  background: rgba(251, 248, 241, 0.94);
  box-shadow: 0 16px 36px -34px rgba(32, 30, 26, 0.65);
}

textarea {
  display: block;
  width: 100%;
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  color: var(--ink);
  overflow-y: auto;
}

.hero textarea {
  min-height: 82px;
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.8;
}

.docked textarea {
  min-height: 44px;
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.7;
}

textarea::placeholder {
  color: var(--muted);
  opacity: 0.85;
}

.composer-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 6px;
}

.composer-hint {
  font-size: 10.5px;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.send-btn,
.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 15px;
  border: 1px solid var(--ink);
  font-size: 12.5px;
  line-height: 1;
  letter-spacing: 0.02em;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    color 160ms ease;
}

.send-btn {
  background: var(--ink);
  color: var(--surface);
}

.send-btn:hover:not(:disabled) {
  background: var(--accent);
  border-color: var(--accent);
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.send-btn svg,
.stop-btn svg {
  width: 14px;
  height: 14px;
}

.stop-btn {
  background: transparent;
  border-color: var(--line-strong);
  color: var(--ink-soft);
}

.stop-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.docked .send-btn,
.docked .stop-btn {
  padding: 8px 13px;
}

@media (max-width: 640px) {
  .composer-hint {
    display: none;
  }

  .composer.hero {
    padding: 14px 14px 11px;
  }

  .hero textarea {
    min-height: 76px;
    font-size: 15px;
  }

  .composer-bottom {
    justify-content: flex-end;
  }
}
</style>
