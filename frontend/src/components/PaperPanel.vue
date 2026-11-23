<script setup lang="ts">
import { ref, watch } from "vue";
import { analyzePaper } from "../lib/api";
import type { PaperAnalysis, Source } from "../types";

const props = defineProps<{ source: Source }>();
const emit = defineEmits<{ (e: "close"): void }>();

const analysis = ref<PaperAnalysis | null>(null);
const loading = ref(false);
const error = ref("");
const demo = ref(false);

const difficultyClass: Record<PaperAnalysis["difficulty"], string> = {
  入门: "easy",
  中等: "medium",
  较难: "hard",
};

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const result = await analyzePaper(props.source);
    analysis.value = result.analysis;
    demo.value = result.demo;
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "分析失败，请重试。";
  } finally {
    loading.value = false;
  }
}

watch(() => props.source.url, load, { immediate: true });

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}
</script>

<template>
  <div class="panel-mask" @click.self="emit('close')" @keydown="onKeydown">
    <aside class="panel" role="dialog" aria-modal="true" aria-labelledby="paper-title">
      <header class="panel-head">
        <div class="panel-badges">
          <template v-if="analysis">
            <span class="badge" :class="difficultyClass[analysis.difficulty]">
              {{ analysis.difficulty }}
            </span>
            <span class="badge">{{ analysis.paper_type }}</span>
            <span v-if="analysis.reading_time" class="badge">
              {{ analysis.reading_time }}
            </span>
          </template>
          <span v-if="demo" class="badge demo">演示</span>
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

      <h2 id="paper-title">{{ source.title }}</h2>
      <p class="panel-meta">
        <span v-if="source.authors">{{ source.authors }}</span>
        <span v-if="source.authors && source.year" class="sep">·</span>
        <span v-if="source.year">{{ source.year }}</span>
        <span v-if="source.category" class="category">{{ source.category }}</span>
      </p>
      <a class="paper-link" :href="source.url" target="_blank" rel="noopener noreferrer">
        查看原文
      </a>

      <p v-if="loading" class="panel-status">正在根据摘要生成分析…</p>
      <p v-else-if="error" class="panel-status error">
        {{ error }}
        <button type="button" class="retry" @click="load">重试</button>
      </p>

      <template v-else-if="analysis">
        <section>
          <h3>研究问题</h3>
          <p>{{ analysis.research_problem }}</p>
        </section>
        <section>
          <h3>方法</h3>
          <p>{{ analysis.method }}</p>
        </section>
        <section>
          <h3>主要贡献</h3>
          <ul>
            <li v-for="item in analysis.contributions" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section>
          <h3>局限</h3>
          <ul>
            <li v-for="item in analysis.limitations" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section>
          <h3>前置知识</h3>
          <p class="chips">
            <span v-for="item in analysis.prerequisites" :key="item" class="chip">
              {{ item }}
            </span>
          </p>
        </section>
        <p v-if="analysis.difficulty_reason" class="difficulty-note">
          难度依据：{{ analysis.difficulty_reason }}
        </p>
        <p class="panel-foot">分析只依据标题与摘要，未读全文，供判断要不要读这篇。</p>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.panel-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  justify-content: flex-end;
  background: rgba(32, 30, 26, 0.28);
}

.panel {
  width: min(460px, 100%);
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
  margin-bottom: 16px;
}

.panel-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge {
  padding: 1px 8px;
  border: 1px solid var(--line);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.8;
  color: var(--ink-soft);
}

.badge.easy {
  border-color: var(--ok);
  color: var(--ok);
}

.badge.hard {
  border-color: var(--danger);
  color: var(--danger);
}

.badge.demo {
  border-color: #d9c48e;
  background: #f6edda;
  color: #8a6a22;
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

.panel h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.6;
}

.panel-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted);
}

.sep {
  opacity: 0.6;
}

.category {
  padding: 1px 5px;
  background: var(--paper-deep);
  color: var(--ink-soft);
  font-family: var(--font-mono);
  font-size: 10px;
}

.paper-link {
  display: inline-block;
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--accent-deep);
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

.panel section {
  margin-top: 22px;
}

.panel h3 {
  margin: 0 0 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--accent);
}

.panel section p,
.panel li {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink-soft);
}

.panel ul {
  margin: 0;
  padding-left: 18px;
}

.panel li + li {
  margin-top: 4px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 1px 8px;
  border: 1px solid var(--line);
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-soft);
}

.difficulty-note {
  margin: 18px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--muted);
}

.panel-foot {
  margin: 22px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--muted);
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
</style>
