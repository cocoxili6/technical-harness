<script setup lang="ts">
import { computed } from "vue";
import DOMPurify from "dompurify";
import { marked } from "marked";

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
}>();

const html = computed(() => {
  const rendered = marked.parse(props.content, { async: false }) as string;
  return DOMPurify.sanitize(rendered, { USE_PROFILES: { html: true } });
});
</script>

<template>
  <div class="markdown" :class="{ 'is-streaming': streaming }" v-html="html"></div>
</template>
