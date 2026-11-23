<script setup lang="ts">
import { computed, ref } from "vue";
import type { Source } from "../types";

const props = defineProps<{ sources: Source[]; content?: string }>();
const emit = defineEmits<{ (e: "analyze", source: Source): void }>();

const open = ref(false);

function cited(source: Source): boolean {
  const content = props.content ?? "";
  if (content.includes(source.url)) return true;
  const id = source.url.match(/10\.\d{4,}\/[^\s#?]+/)?.[0];
  if (id && content.includes(id)) return true;
  const arxiv = source.url.match(/arxiv\.org\/(?:abs|pdf)\/([\d.]+)/)?.[1];
  return Boolean(arxiv && content.includes(arxiv));
}

const others = computed(() => props.sources.filter((source) => !cited(source)));
</script>

<template>
  <section v-if="others.length" class="sources" aria-label="其他检索结果">
    <button type="button" class="sources-head" @click="open = !open">
      <h3>其他检索结果</h3>
      <span>{{ others.length }} 条 · 阅读路线未选用</span>
      <span class="toggle">{{ open ? "收起" : "展开" }}</span>
    </button>
    <div v-if="open" class="source-grid">
      <article v-for="source in others" :key="source.url" class="source-card">
        <div class="source-top">
          <span v-if="source.category === 'DEMO'" class="demo-tag">演示</span>
          <a
            class="external-icon"
            :href="source.url"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="查看原文"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M6 3H3.5A1.5 1.5 0 0 0 2 4.5v8A1.5 1.5 0 0 0 3.5 14h8a1.5 1.5 0 0 0 1.5-1.5V10M9 2h5v5M14 2 7.5 8.5"
                stroke="currentColor"
                stroke-width="1.3"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </a>
        </div>
        <h4>{{ source.title }}</h4>
        <p class="source-meta">
          <span v-if="source.authors">{{ source.authors }}</span>
          <span v-if="source.authors && source.year" class="sep">·</span>
          <span v-if="source.year">{{ source.year }}</span>
          <span
            v-if="source.category && source.category !== 'DEMO'"
            class="category"
            >{{ source.category }}</span
          >
        </p>
        <p v-if="source.summary" class="source-summary">{{ source.summary }}</p>
        <button type="button" class="analyze-btn" @click="emit('analyze', source)">
          分析这篇
        </button>
      </article>
    </div>
  </section>
</template>

<style scoped>
.sources {
  margin-top: 30px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}

.sources-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  width: 100%;
  margin-bottom: 14px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.sources-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink);
}

.sources-head span {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.toggle {
  margin-left: auto;
  color: var(--accent) !important;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.source-card {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  padding: 14px 15px 15px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.62);
  color: var(--ink);
}

.source-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.demo-tag {
  padding: 1px 6px;
  border: 1px solid #d9c48e;
  background: #f6edda;
  color: #8a6a22;
  font-size: 10px;
  letter-spacing: 0.08em;
}

.external-icon {
  width: 13px;
  height: 13px;
  margin-left: auto;
  color: var(--muted);
}

.external-icon:hover {
  color: var(--accent);
}

.source-card h4 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 14.5px;
  font-weight: 600;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.source-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin: 0;
  font-size: 11px;
  color: var(--muted);
  line-height: 1.5;
}

.sep {
  opacity: 0.6;
}

.category {
  margin-left: 2px;
  padding: 1px 5px;
  background: var(--paper-deep);
  color: var(--ink-soft);
  font-family: var(--font-mono);
  font-size: 9.5px;
}

.source-summary {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.analyze-btn {
  align-self: flex-start;
  margin-top: auto;
  padding: 1px 9px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-soft);
  font-family: var(--font-sans);
  font-size: 11.5px;
  line-height: 1.8;
  cursor: pointer;
}

.analyze-btn:hover {
  border-color: var(--accent);
  color: var(--accent-deep);
}

@media (max-width: 760px) {
  .source-grid {
    grid-template-columns: 1fr;
  }
}
</style>
