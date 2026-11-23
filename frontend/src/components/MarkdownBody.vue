<script setup lang="ts">
import { computed } from "vue";
import DOMPurify from "dompurify";
import { marked } from "marked";
import type { Source } from "../types";

marked.setOptions({ gfm: true, breaks: true });

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node instanceof Element && node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});

const props = defineProps<{
  content: string;
  streaming?: boolean;
  sources?: Source[];
}>();

const emit = defineEmits<{
  (e: "analyze", source: Source): void;
}>();

function sourceFor(href: string): Source | undefined {
  const sources = props.sources ?? [];
  const exact = sources.find((source) => source.url === href);
  if (exact) return exact;
  const id = href.match(/10\.\d{4,}\/[^\s#?]+/)?.[0];
  if (id) {
    const byDoi = sources.find((source) => source.url.includes(id));
    if (byDoi) return byDoi;
  }
  const arxiv = href.match(/arxiv\.org\/(?:abs|pdf)\/([\d.]+)/)?.[1];
  return arxiv ? sources.find((source) => source.url.includes(arxiv)) : undefined;
}

const html = computed(() => {
  const renderer = new marked.Renderer();
  renderer.link = ({ href, title, text }) => {
    const extra = sourceFor(href)
      ? ' data-analyze="1" title="查看这篇论文的分析"'
      : "";
    const titleAttr = title ? ` title="${title}"` : "";
    return `<a href="${href}"${titleAttr}${extra}>${text}</a>`;
  };
  const rendered = marked.parse(props.content, {
    async: false,
    renderer,
  }) as string;
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["data-analyze"],
  });
});

function onClick(event: MouseEvent): void {
  const link = (event.target as Element).closest("a");
  if (!link?.hasAttribute("data-analyze")) return;
  const source = sourceFor(link.getAttribute("href") ?? "");
  if (!source) return;
  event.preventDefault();
  emit("analyze", source);
}
</script>

<template>
  <div
    class="markdown"
    :class="{ 'is-streaming': streaming }"
    v-html="html"
    @click="onClick"
  ></div>
</template>
