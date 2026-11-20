<script setup lang="ts">
import type { ChatMessage } from "../types";
import MarkdownBody from "./MarkdownBody.vue";
import SourceList from "./SourceList.vue";
import ToolTrace from "./ToolTrace.vue";

defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
}>();
</script>

<template>
  <div class="conversation">
    <template v-for="message in messages" :key="message.id">
      <section v-if="message.role === 'user'" class="question">
        <div class="question-label">研究问题</div>
        <p class="question-text">{{ message.content }}</p>
      </section>

      <article v-else class="note">
        <header class="note-head">
          <span class="note-seal" aria-hidden="true">研</span>
          <span class="note-label">研途 · 研究笔记</span>
          <span
            v-if="message.status === 'streaming'"
            class="note-status streaming"
          >
            <span class="live-dot" aria-hidden="true"></span>生成中
          </span>
          <span v-else-if="message.status === 'stopped'" class="note-status">
            已停止
          </span>
          <span v-else-if="message.status === 'error'" class="note-status danger">
            未完成
          </span>
        </header>

        <ToolTrace v-if="message.trace?.length" :items="message.trace" />

        <div
          v-if="message.status === 'streaming' && !message.content"
          class="waiting"
        >
          <span class="waiting-line" aria-hidden="true"></span>
          正在检索并整理文献…
        </div>

        <MarkdownBody
          v-if="message.content"
          :content="message.content"
          :streaming="message.status === 'streaming'"
        />

        <div
          v-if="message.status === 'error'"
          class="error-note"
          role="alert"
        >
          <strong>本轮没有完成</strong>
          <p>{{ message.error || "生成失败，请重试。" }}</p>
        </div>

        <SourceList v-if="message.sources?.length" :sources="message.sources" />
      </article>
    </template>
  </div>
</template>

<style scoped>
.conversation {
  display: flex;
  flex-direction: column;
  gap: 38px;
  padding-bottom: 18px;
}

.question {
  position: relative;
  padding: 17px 22px 19px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.56);
  animation: rise-in 280ms ease both;
}

.question::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 3px;
  height: 26px;
  background: var(--accent);
}

.question-label {
  margin-bottom: 7px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--accent);
}

.question-text {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.note {
  padding-top: 13px;
  border-top: 1px solid var(--ink);
  animation: rise-in 320ms ease both;
}

.note-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 16px;
}

.note-seal {
  display: grid;
  place-items: center;
  width: 19px;
  height: 19px;
  background: var(--accent);
  color: #fbf8f1;
  font-family: var(--font-serif);
  font-size: 12px;
  line-height: 1;
  transform: rotate(-2deg);
}

.note-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--ink-soft);
}

.note-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.04em;
  color: var(--muted);
}

.note-status.streaming {
  color: var(--accent);
}

.note-status.danger {
  color: var(--danger);
}

.live-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  animation: live-pulse 1.25s ease-in-out infinite;
}

.waiting {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0 8px;
  font-size: 12.5px;
  color: var(--muted);
}

.waiting-line {
  width: 26px;
  height: 1px;
  background: linear-gradient(90deg, var(--accent), transparent);
  animation: waiting-sweep 1.4s ease-in-out infinite;
}

.error-note {
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px solid #d8b3ab;
  background: #f8e9e5;
  color: #7c261c;
  font-size: 13px;
}

.error-note strong {
  display: block;
  margin-bottom: 4px;
  font-size: 12.5px;
  letter-spacing: 0.03em;
}

.error-note p {
  margin: 0;
  line-height: 1.65;
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes live-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@keyframes waiting-sweep {
  0% {
    transform: translateX(0);
    opacity: 0.4;
  }
  50% {
    transform: translateX(6px);
    opacity: 1;
  }
  100% {
    transform: translateX(0);
    opacity: 0.4;
  }
}

@media (max-width: 640px) {
  .conversation {
    gap: 30px;
  }

  .question {
    padding: 15px 16px 17px;
  }

  .question-text {
    font-size: 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .question,
  .note {
    animation: none;
  }

  .live-dot,
  .waiting-line {
    animation: none;
  }
}
</style>
