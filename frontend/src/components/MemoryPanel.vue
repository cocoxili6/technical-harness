<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { addMemory, deleteMemory, listMemories, reviewMemory } from "../lib/api";
import { relativeTime } from "../lib/format";
import type { MemoryItem, MemoryStats } from "../types";

const emit = defineEmits<{
  (e: "close"): void;
  (e: "changed", stats: MemoryStats): void;
}>();

const items = ref<MemoryItem[]>([]);
const stats = ref<MemoryStats | null>(null);
const loading = ref(true);
const error = ref("");
const draft = ref("");
const busyId = ref("");
const adding = ref(false);

const KIND_LABELS: Record<string, string> = {
  interest: "兴趣",
  background: "背景",
  goal: "目标",
  preference: "偏好",
  progress: "进展",
  fact: "事实",
};

const activeItems = computed(() => items.value.filter((item) => !item.forgotten));
const forgottenItems = computed(() => items.value.filter((item) => item.forgotten));

function percent(item: MemoryItem): number {
  return Math.max(0, Math.min(100, Math.round(item.retention * 100)));
}

function tone(item: MemoryItem): string {
  const value = percent(item);
  if (value >= 60) return "strong";
  if (value >= 30) return "medium";
  return "weak";
}

function apply(snapshot: { items: MemoryItem[]; stats: MemoryStats }): void {
  items.value = snapshot.items;
  stats.value = snapshot.stats;
  emit("changed", snapshot.stats);
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    apply(await listMemories());
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "记忆加载失败，请重试。";
  } finally {
    loading.value = false;
  }
}

async function submitAdd(): Promise<void> {
  const text = draft.value.trim();
  if (!text || adding.value) return;
  adding.value = true;
  error.value = "";
  try {
    apply(await addMemory(text));
    draft.value = "";
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "保存失败，请重试。";
  } finally {
    adding.value = false;
  }
}

async function review(id: string): Promise<void> {
  busyId.value = id;
  error.value = "";
  try {
    apply(await reviewMemory(id));
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "复习失败，请重试。";
  } finally {
    busyId.value = "";
  }
}

async function remove(id: string): Promise<void> {
  busyId.value = id;
  error.value = "";
  try {
    apply(await deleteMemory(id));
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "删除失败，请重试。";
  } finally {
    busyId.value = "";
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}

onMounted(load);
</script>

<template>
  <div class="panel-mask" @click.self="emit('close')" @keydown="onKeydown">
    <aside class="panel" role="dialog" aria-modal="true" aria-labelledby="memory-title">
      <header class="panel-head">
        <div>
          <h2 id="memory-title">长期记忆</h2>
          <p class="panel-sub">跨会话记住你，并按遗忘曲线自动衰减。</p>
        </div>
        <button type="button" class="close-btn" aria-label="关闭" @click="emit('close')">
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M4 4l8 8M12 4 4 12"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </header>

      <div v-if="stats" class="stats">
        <span>活跃 <strong>{{ stats.active }}</strong></span>
        <span>已淡忘 <strong>{{ stats.forgotten }}</strong></span>
        <span>平均强度 <strong>{{ Math.round(stats.avg_retention * 100) }}%</strong></span>
      </div>

      <p class="curve-note">
        强度 R = e<sup>−t/S</sup>：每条记忆有稳定度 S（天），t 天没被用到就衰减。对话命中或点「复习」都会让 S
        增长；R 低于 10% 记为淡忘，不再参与回答。注入分两层：背景/学习偏好常驻，兴趣/目标/进展/事实按会话方向与当前问题检索。
      </p>

      <form class="add-form" @submit.prevent="submitAdd">
        <input
          v-model="draft"
          type="text"
          maxlength="300"
          placeholder="手动记一条，例如：我在做多智能体强化学习"
          aria-label="新增记忆"
        />
        <button type="submit" :disabled="!draft.trim() || adding">
          {{ adding ? "保存中" : "记住" }}
        </button>
      </form>

      <p v-if="loading" class="panel-status">正在读取记忆…</p>
      <p v-else-if="error" class="panel-status error">
        {{ error }}
        <button type="button" class="retry" @click="load">重试</button>
      </p>

      <template v-else>
        <section class="group">
          <h3>活跃记忆 <span>{{ activeItems.length }}</span></h3>
          <p v-if="!activeItems.length" class="empty">
            还没有长期记忆。对话几轮后，关于你的兴趣、背景和进展会记录在这里；也可以在上方手动添加。
          </p>
          <article v-for="item in activeItems" :key="item.id" class="memory-item">
            <div class="item-top">
              <span class="kind">{{ KIND_LABELS[item.kind] ?? item.kind }}</span>
              <span class="score" :class="tone(item)">{{ percent(item) }}%</span>
            </div>
            <p class="item-text">{{ item.text }}</p>
            <div class="bar"><span class="fill" :class="tone(item)" :style="{ width: `${percent(item)}%` }"></span></div>
            <p class="item-meta">
              重要度 {{ item.importance }}/5 · 稳定度 {{ item.stability_days }} 天 · 回想
              {{ item.recall_count }} 次 · 上次 {{ relativeTime(item.last_recalled_at) }}
            </p>
            <div class="item-actions">
              <button type="button" :disabled="busyId === item.id" @click="review(item.id)">
                复习
              </button>
              <button
                type="button"
                class="danger"
                :disabled="busyId === item.id"
                @click="remove(item.id)"
              >
                删除
              </button>
            </div>
          </article>
        </section>

        <section v-if="forgottenItems.length" class="group">
          <h3>已淡忘 <span>{{ forgottenItems.length }}</span></h3>
          <article
            v-for="item in forgottenItems"
            :key="item.id"
            class="memory-item forgotten"
          >
            <div class="item-top">
              <span class="kind">{{ KIND_LABELS[item.kind] ?? item.kind }}</span>
              <span class="score weak">{{ percent(item) }}%</span>
            </div>
            <p class="item-text">{{ item.text }}</p>
            <div class="bar"><span class="fill weak" :style="{ width: `${percent(item)}%` }"></span></div>
            <p class="item-meta">稳定度 {{ item.stability_days }} 天 · 回想 {{ item.recall_count }} 次</p>
            <div class="item-actions">
              <button type="button" :disabled="busyId === item.id" @click="review(item.id)">
                恢复并复习
              </button>
              <button
                type="button"
                class="danger"
                :disabled="busyId === item.id"
                @click="remove(item.id)"
              >
                删除
              </button>
            </div>
          </article>
          <p class="forgotten-note">淡忘的记忆不参与回答；恢复后强度回到 100%。</p>
        </section>
      </template>

      <p class="panel-foot">
        记忆保存在本机 <code>backend/data/memories.json</code>。自动抽取需要配置 DeepSeek Key；未配置时可手动添加。
      </p>
    </aside>
  </div>
</template>

<style scoped>
.panel-mask {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  justify-content: flex-end;
  background: rgba(32, 30, 26, 0.28);
}

.panel {
  width: min(480px, 100%);
  height: 100%;
  overflow-y: auto;
  padding: 22px 26px 40px;
  background: var(--surface);
  border-left: 1px solid var(--line);
  box-shadow: -8px 0 24px rgba(32, 30, 26, 0.08);
  animation: slide-in 220ms ease both;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
}

.panel-sub {
  margin: 5px 0 0;
  font-size: 11.5px;
  color: var(--muted);
}

.close-btn {
  flex: none;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-soft);
  cursor: pointer;
}

.close-btn svg {
  width: 14px;
  height: 14px;
}

.close-btn:hover {
  border-color: var(--line-strong);
  color: var(--ink);
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  margin-top: 16px;
  padding: 9px 12px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.6);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.stats strong {
  margin-left: 3px;
  font-weight: 600;
  color: var(--ink);
}

.curve-note {
  margin: 12px 0 0;
  font-size: 11px;
  line-height: 1.75;
  color: var(--muted);
}

.add-form {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.add-form input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.6);
  color: var(--ink);
  font-size: 12.5px;
}

.add-form input:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 1px;
}

.add-form button {
  flex: none;
  padding: 0 14px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fbf8f1;
  font-size: 12.5px;
  cursor: pointer;
}

.add-form button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.panel-status {
  margin: 28px 0 0;
  font-size: 13px;
  color: var(--muted);
}

.panel-status.error {
  color: var(--danger);
}

.retry {
  margin-left: 8px;
  padding: 1px 8px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
}

.group {
  margin-top: 26px;
}

.group h3 {
  margin: 0 0 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--accent);
}

.group h3 span {
  color: var(--muted);
}

.empty {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--muted);
}

.memory-item {
  padding: 12px 13px 13px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.55);
}

.memory-item + .memory-item {
  margin-top: 8px;
}

.memory-item.forgotten {
  opacity: 0.72;
}

.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kind {
  padding: 0 7px;
  border: 1px solid var(--line);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.8;
  color: var(--ink-soft);
}

.score {
  font-family: var(--font-mono);
  font-size: 11px;
}

.score.strong {
  color: var(--ok);
}

.score.medium {
  color: #b4842b;
}

.score.weak {
  color: var(--danger);
}

.item-text {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink);
}

.bar {
  height: 3px;
  margin-top: 9px;
  background: var(--paper-deep);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  transition: width 240ms ease;
}

.fill.strong {
  background: var(--ok);
}

.fill.medium {
  background: #b4842b;
}

.fill.weak {
  background: var(--danger);
}

.item-meta {
  margin: 8px 0 0;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.7;
  color: var(--muted);
}

.item-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.item-actions button {
  padding: 2px 10px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-soft);
  font-size: 11.5px;
  cursor: pointer;
}

.item-actions button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-deep);
}

.item-actions button.danger:hover:not(:disabled) {
  border-color: var(--danger);
  color: var(--danger);
}

.item-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.forgotten-note {
  margin: 8px 0 0;
  font-size: 10.5px;
  color: var(--muted);
}

.panel-foot {
  margin: 26px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 11px;
  line-height: 1.7;
  color: var(--muted);
}

.panel-foot code {
  padding: 1px 4px;
  background: var(--paper-deep);
  font-family: var(--font-mono);
  font-size: 10px;
}

@keyframes slide-in {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
}

@media (max-width: 640px) {
  .panel {
    padding: 18px 18px 36px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .panel {
    animation: none;
  }

  .fill {
    transition: none;
  }
}
</style>