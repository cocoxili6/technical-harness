<script setup lang="ts">
import type { Source } from "../types";

defineProps<{ sources: Source[] }>();
</script>

<template>
  <section class="sources" aria-label="文献来源">
    <div class="sources-head">
      <h3>文献来源</h3>
      <span>{{ sources.length }} 条</span>
    </div>
    <div class="source-grid">
      <a
        v-for="(source, index) in sources"
        :key="source.url"
        :href="source.url"
        class="source-card"
        target="_blank"
        rel="noopener noreferrer"
      >
        <div class="source-top">
          <span class="source-index">{{ String(index + 1).padStart(2, "0") }}</span>
          <span v-if="source.category === 'DEMO'" class="demo-tag">演示</span>
          <svg
            class="external-icon"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M6 3H3.5A1.5 1.5 0 0 0 2 4.5v8A1.5 1.5 0 0 0 3.5 14h8a1.5 1.5 0 0 0 1.5-1.5V10M9 2h5v5M14 2 7.5 8.5"
              stroke="currentColor"
              stroke-width="1.3"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
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
      </a>
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
  justify-content: space-between;
  margin-bottom: 14px;
}

.sources-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.sources-head span {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
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
  text-decoration: none;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    transform 160ms ease;
}

.source-card:hover {
  border-color: var(--accent);
  background: var(--surface);
  transform: translateY(-1px);
}

.source-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-index {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--accent);
  letter-spacing: 0.08em;
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
  transition: color 160ms ease;
}

.source-card:hover .external-icon {
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

@media (max-width: 760px) {
  .source-grid {
    grid-template-columns: 1fr;
  }
}
</style>
