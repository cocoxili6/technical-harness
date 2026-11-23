<script setup lang="ts">
import type { TraceItem } from "../types";

defineProps<{ items: TraceItem[] }>();

function toolLabel(name: string): string {
  if (name === "search_arxiv") return "arXiv 检索";
  if (name === "search_scholar") return "Google Scholar 检索";
  if (name === "search_openalex") return "OpenAlex 检索";
  return name;
}
</script>

<template>
  <section class="trace" aria-label="检索轨迹">
    <div class="trace-head">
      <span>检索轨迹</span>
      <span class="trace-count">{{ items.length }} 次调用</span>
    </div>
    <div
      v-for="item in items"
      :key="item.id"
      class="trace-item"
      :class="item.status"
    >
      <span class="trace-dot" aria-hidden="true"></span>
      <span class="trace-name">{{ toolLabel(item.name) }}</span>
      <span v-if="item.query" class="trace-query">“{{ item.query }}”</span>
      <span class="trace-state">
        <template v-if="item.status === 'running'">检索中</template>
        <template v-else-if="item.status === 'error'">失败</template>
        <template v-else>{{ item.summary || "完成" }}</template>
      </span>
    </div>
  </section>
</template>

<style scoped>
.trace {
  margin: 4px 0 22px;
  border: 1px solid var(--line);
  background: rgba(248, 243, 233, 0.72);
  font-family: var(--font-mono);
  font-size: 12px;
}

.trace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 10.5px;
}

.trace-count {
  letter-spacing: 0.02em;
  color: var(--muted);
}

.trace-item {
  display: flex;
  align-items: baseline;
  gap: 9px;
  padding: 9px 14px;
  line-height: 1.6;
  color: var(--ink-soft);
}

.trace-item + .trace-item {
  border-top: 1px dashed var(--line);
}

.trace-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--line-strong);
  transform: translateY(-1px);
}

.trace-item.running .trace-dot {
  background: var(--accent);
  animation: trace-pulse 1.2s ease-in-out infinite;
}

.trace-item.done .trace-dot {
  background: var(--ok);
}

.trace-item.error .trace-dot {
  background: var(--danger);
}

.trace-name {
  flex: 0 0 auto;
  color: var(--ink);
  font-weight: 600;
}

.trace-query {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
}

.trace-state {
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 11px;
}

.trace-item.error .trace-state {
  color: var(--danger);
}

@keyframes trace-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@media (max-width: 640px) {
  .trace-item {
    flex-wrap: wrap;
  }

  .trace-query {
    order: 4;
    flex-basis: 100%;
    padding-left: 15px;
    white-space: normal;
  }

  .trace-state {
    margin-left: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .trace-item.running .trace-dot {
    animation: none;
  }
}
</style>
