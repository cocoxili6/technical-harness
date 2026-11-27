<script setup lang="ts">
import type { MemoryStats, StatusTone, ThreadSummary } from "../types";
import { relativeTime } from "../lib/format";

defineProps<{
  threads: ThreadSummary[];
  activeThreadId: string | null;
  open: boolean;
  turnCount: number;
  statusText: string;
  statusTone: StatusTone;
  memoryStats: MemoryStats | null;
}>();

defineEmits<{
  (e: "new"): void;
  (e: "select", id: string): void;
  (e: "close"): void;
  (e: "retry"): void;
  (e: "memories"): void;
}>();
</script>

<template>
  <div
    class="sidebar-backdrop"
    :class="{ open }"
    aria-hidden="true"
    @click="$emit('close')"
  ></div>

  <aside class="sidebar" :class="{ open }" aria-label="会话导航">
    <div class="brand">
      <div class="brand-seal" aria-hidden="true">研</div>
      <div class="brand-text">
        <span class="brand-name">研途</span>
        <span class="brand-sub">RESEARCH HARNESS</span>
      </div>
      <button
        class="sidebar-close"
        type="button"
        aria-label="关闭会话列表"
        @click="$emit('close')"
      >
        <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="m4 4 8 8M12 4l-8 8"
            stroke="currentColor"
            stroke-width="1.3"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>

    <button class="new-thread" type="button" @click="$emit('new')">
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M8 3v10M3 8h10"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
        />
      </svg>
      新的调研
    </button>

    <div class="threads-head">
      <span>会话</span>
      <span>{{ threads.length }}</span>
    </div>

    <nav class="thread-list" aria-label="历史会话">
      <p v-if="threads.length === 0" class="thread-empty">
        还没有会话。提出第一个研究问题后，它会出现在这里。
      </p>
      <button
        v-for="thread in threads"
        :key="thread.id"
        type="button"
        class="thread-item"
        :class="{ active: thread.id === activeThreadId }"
        @click="$emit('select', thread.id)"
      >
        <span class="thread-title">{{ thread.title }}</span>
        <span class="thread-meta">
          {{ relativeTime(thread.updated_at) }} · {{ thread.message_count }} 条
        </span>
      </button>
    </nav>

    <div class="sidebar-foot">
      <div class="memory-card">
        <div class="memory-head">
          <span>短期记忆</span>
          <span class="memory-pip" :class="{ active: activeThreadId }"></span>
        </div>
        <div class="memory-value">
          {{ activeThreadId ? `本会话已记忆 ${turnCount} 轮` : "尚未开始会话" }}
        </div>
        <p>会话与上下文按账户保存在 Supabase，刷新后可继续。</p>
      </div>

      <button type="button" class="memory-card long-term" @click="$emit('memories')">
        <div class="memory-head">
          <span>长期记忆</span>
          <span class="memory-link">查看 →</span>
        </div>
        <div class="memory-value">
          {{ memoryStats ? `${memoryStats.active} 条活跃` : "尚未积累" }}
        </div>
        <p>
          {{
            memoryStats && memoryStats.forgotten
              ? `另有 ${memoryStats.forgotten} 条已淡忘 · 按遗忘曲线衰减`
              : "按遗忘曲线衰减，跨会话生效。"
          }}
        </p>
      </button>

      <div class="status-line">
        <span class="status-dot" :class="statusTone" aria-hidden="true"></span>
        <span>{{ statusText }}</span>
        <button
          v-if="statusTone === 'offline'"
          class="retry-link"
          type="button"
          @click="$emit('retry')"
        >
          重试
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-backdrop {
  display: none;
}

.sidebar {
  position: relative;
  z-index: 20;
  display: flex;
  flex: 0 0 268px;
  flex-direction: column;
  width: 268px;
  height: 100%;
  padding: 24px 18px 18px;
  border-right: 1px solid var(--line);
  background: rgba(247, 242, 232, 0.74);
  backdrop-filter: blur(10px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 4px 20px;
}

.brand-seal {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 38px;
  height: 38px;
  background: var(--accent);
  color: #fbf8f1;
  font-family: var(--font-serif);
  font-size: 20px;
  line-height: 1;
  transform: rotate(-3deg);
  box-shadow:
    inset 0 0 0 2px rgba(251, 248, 241, 0.28),
    0 6px 16px -11px rgba(130, 42, 31, 0.9);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-family: var(--font-serif);
  font-size: 19px;
  letter-spacing: 0.09em;
  line-height: 1.2;
}

.brand-sub {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.17em;
  color: var(--muted);
}

.sidebar-close {
  display: none;
  place-items: center;
  width: 28px;
  height: 28px;
  margin-left: auto;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
}

.sidebar-close svg {
  width: 14px;
  height: 14px;
}

.new-thread {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border: 1px solid var(--line-strong);
  background: transparent;
  color: var(--ink-soft);
  font-size: 12.5px;
  text-align: left;
  transition:
    border-color 160ms ease,
    color 160ms ease,
    background-color 160ms ease;
}

.new-thread svg {
  width: 14px;
  height: 14px;
}

.new-thread:hover {
  border-color: var(--accent);
  background: rgba(166, 58, 43, 0.035);
  color: var(--accent);
}

.threads-head {
  display: flex;
  justify-content: space-between;
  margin: 24px 4px 8px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: var(--muted);
  text-transform: uppercase;
}

.thread-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
  margin: 0 -4px;
  padding: 0 4px 12px;
  overflow-y: auto;
}

.thread-empty {
  margin: 6px;
  font-size: 11.5px;
  line-height: 1.75;
  color: var(--muted);
}

.thread-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 9px 10px 9px 12px;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  text-align: left;
  transition:
    background-color 140ms ease,
    border-color 140ms ease;
}

.thread-item:hover {
  background: rgba(251, 248, 241, 0.55);
}

.thread-item.active {
  border-left-color: var(--accent);
  background: rgba(251, 248, 241, 0.9);
}

.thread-title {
  display: -webkit-box;
  overflow: hidden;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-soft);
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.thread-item.active .thread-title {
  color: var(--ink);
}

.thread-meta {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--muted);
}

.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

.memory-card {
  padding: 12px 12px 13px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.5);
}

.memory-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.memory-pip {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--line-strong);
}

.memory-pip.active {
  background: var(--accent);
}

.memory-value {
  margin-top: 7px;
  font-family: var(--font-serif);
  font-size: 14px;
  color: var(--ink);
}

.memory-card p {
  margin: 5px 0 0;
  font-size: 10px;
  line-height: 1.65;
  color: var(--muted);
}

.memory-card.long-term {
  display: block;
  width: 100%;
  font-family: inherit;
  text-align: left;
  color: inherit;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    background-color 140ms ease;
}

.memory-card.long-term:hover {
  border-color: var(--accent);
  background: rgba(251, 248, 241, 0.86);
}

.memory-link {
  color: var(--accent);
}

.status-line {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 3px;
  font-size: 10.5px;
  color: var(--ink-soft);
}

.status-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ok);
}

.status-dot.demo {
  background: #b4842b;
}

.status-dot.offline {
  background: var(--danger);
}

.status-dot.loading {
  background: var(--muted);
  animation: status-blink 1.2s ease-in-out infinite;
}

.retry-link {
  margin-left: auto;
  padding: 0;
  border: 0;
  background: none;
  color: var(--accent);
  font-size: 10.5px;
  text-decoration: underline;
  text-underline-offset: 2px;
}

@keyframes status-blink {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 60;
    width: min(288px, 86vw);
    flex-basis: auto;
    background: #f7f2e8;
    box-shadow: 22px 0 60px -40px rgba(32, 30, 26, 0.7);
    transform: translateX(-102%);
    transition: transform 240ms ease;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .sidebar-close {
    display: grid;
  }

  .sidebar-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: block;
    background: rgba(32, 30, 26, 0.34);
    opacity: 0;
    pointer-events: none;
    transition: opacity 240ms ease;
  }

  .sidebar-backdrop.open {
    opacity: 1;
    pointer-events: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar,
  .sidebar-backdrop {
    transition: none;
  }

  .status-dot.loading {
    animation: none;
  }
}
</style>
