<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import AuthGate from "./components/AuthGate.vue";
import ConversationView from "./components/ConversationView.vue";
import MemoryPanel from "./components/MemoryPanel.vue";
import ResearchComposer from "./components/ResearchComposer.vue";
import Sidebar from "./components/Sidebar.vue";
import { getHealth, getThread, listMemories, listThreads, streamChat } from "./lib/api";
import { createId } from "./lib/format";
import { isEmptyProfile } from "./lib/profile";
import { authReady, authSession, signOut } from "./lib/supabase";
import type {
  BackendState,
  ChatMessage,
  Health,
  LearningProfile,
  MemoryStats,
  StatusTone,
  ThreadSummary,
} from "./types";

const ACTIVE_KEY = "yantu.activeThread";

const starters = [
  "我学过机器学习基础，想入门联邦学习隐私保护，每周能读 6 小时论文，帮我排一条阅读路线。",
  "扩散策略在机器人操作中的研究现状如何？",
  "如何为一篇 RL 论文设计可信的消融实验？",
];

const health = ref<Health | null>(null);
const backendState = ref<BackendState>("connecting");
const threads = ref<ThreadSummary[]>([]);
const activeThreadId = ref<string | null>(null);
const activeTitle = ref("");
const messages = ref<ChatMessage[]>([]);
const streaming = ref(false);
const draft = ref("");
const profile = ref<LearningProfile>({});
const memoryStats = ref<MemoryStats | null>(null);
const memoriesOpen = ref(false);
const mobileSidebarOpen = ref(false);
const loadError = ref("");
const scrollEl = ref<HTMLElement | null>(null);
const composerRef = ref<InstanceType<typeof ResearchComposer> | null>(null);
const userEmail = computed(() => authSession.value?.user.email ?? "");

let controller: AbortController | null = null;
let generation = 0;

const isDemo = computed(() => health.value?.demo_mode === true);
const backendReady = computed(() => backendState.value === "online");
const hasConversation = computed(() => messages.value.length > 0);
const turnCount = computed(
  () => messages.value.filter((message) => message.role === "user").length,
);

const statusTone = computed<StatusTone>(() => {
  if (backendState.value === "offline") return "offline";
  if (backendState.value === "connecting") return "loading";
  if (isDemo.value) return "demo";
  return "ok";
});

const statusText = computed(() => {
  switch (statusTone.value) {
    case "offline":
      return "后端未连接";
    case "loading":
      return "连接中";
    case "demo":
      return "演示模式";
    default:
      return health.value ? `DeepSeek · ${health.value.model}` : "已连接";
  }
});

const emptyFoot = computed(() => {
  if (backendState.value === "offline") {
    return "后端未连接。启动 FastAPI 服务后，在上方提示条点击重试。";
  }
  if (backendState.value === "connecting") {
    return "正在连接后端…";
  }
  if (isDemo.value) {
    return "当前为演示模式，回答是界面示例。配置 DeepSeek API Key 后会使用真实文献生成。";
  }
  return "回答会流式生成 · 会话内上下文 + 跨会话长期记忆";
});

function scrollToBottom(force = false): void {
  requestAnimationFrame(() => {
    const element = scrollEl.value;
    if (!element) return;
    if (!force) {
      const distance =
        element.scrollHeight - element.scrollTop - element.clientHeight;
      if (distance > 220) return;
    }
    element.scrollTop = element.scrollHeight;
  });
}

async function refreshHealth(): Promise<void> {
  backendState.value = "connecting";
  try {
    health.value = await getHealth();
    backendState.value = "online";
  } catch {
    health.value = null;
    backendState.value = "offline";
  }
}

async function refreshThreads(): Promise<void> {
  if (!backendReady.value) return;
  try {
    const data = await listThreads();
    threads.value = data.threads;
  } catch {
    // the next explicit action surfaces the failure
  }
}

async function refreshMemoryStats(): Promise<void> {
  if (!backendReady.value) return;
  try {
    const data = await listMemories();
    memoryStats.value = data.stats;
  } catch {
    // memory panel surfaces load errors when opened
  }
}

function closeSidebar(): void {
  mobileSidebarOpen.value = false;
}

function openMemories(): void {
  memoriesOpen.value = true;
  closeSidebar();
}

function stopStream(): void {
  const active = controller;
  if (!active) return;
  generation += 1;
  controller = null;
  streaming.value = false;
  active.abort();

  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const message = messages.value[index];
    if (message.role === "assistant" && message.status === "streaming") {
      message.status = "stopped";
      if (!message.content) message.content = "_已停止生成。_";
      break;
    }
  }
}

async function openThread(threadId: string, silent = false): Promise<void> {
  if (streaming.value) stopStream();
  loadError.value = "";
  try {
    const detail = await getThread(threadId);
    activeThreadId.value = detail.id;
    activeTitle.value = detail.title;
    messages.value = detail.messages.map((message) => ({
      id: createId(),
      role: message.role,
      content: message.content,
      profile: message.profile,
      sources: message.sources ?? [],
      trace: message.trace ?? [],
      status: "done" as const,
    }));
    localStorage.setItem(ACTIVE_KEY, detail.id);
    closeSidebar();
    await nextTick();
    scrollToBottom(true);
  } catch (error) {
    if (!silent) {
      loadError.value =
        error instanceof Error ? error.message : "会话加载失败，请重试。";
    }
    localStorage.removeItem(ACTIVE_KEY);
  }
}

async function restoreThread(): Promise<void> {
  const saved = localStorage.getItem(ACTIVE_KEY);
  if (!saved) return;
  if (!threads.value.some((thread) => thread.id === saved)) {
    localStorage.removeItem(ACTIVE_KEY);
    return;
  }
  await openThread(saved, true);
}

function newThread(): void {
  if (streaming.value) stopStream();
  activeThreadId.value = null;
  activeTitle.value = "";
  messages.value = [];
  loadError.value = "";
  localStorage.removeItem(ACTIVE_KEY);
  closeSidebar();
  void nextTick(() => composerRef.value?.focus());
}

function useStarter(text: string): void {
  draft.value = text;
  void nextTick(() => composerRef.value?.focus());
}

async function reconnect(): Promise<void> {
  await refreshHealth();
  if (!backendReady.value) return;

  await refreshThreads();

  if (activeThreadId.value) {
    const stillExists = threads.value.some(
      (thread) => thread.id === activeThreadId.value,
    );
    if (!stillExists) {
      activeThreadId.value = null;
      localStorage.removeItem(ACTIVE_KEY);
      loadError.value =
        "后端已重启，之前的会话记忆已清除。继续提问会开启新的会话。";
    }
  } else if (messages.value.length === 0) {
    await restoreThread();
  }
}

async function loadWorkspace(): Promise<void> {
  await refreshHealth();
  if (!backendReady.value) return;
  await refreshThreads();
  await restoreThread();
  void refreshMemoryStats();
}

async function handleSignOut(): Promise<void> {
  try {
    await signOut();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : "退出登录失败，请重试。";
  }
}

function clearUserWorkspace(): void {
  stopStream();
  threads.value = [];
  activeThreadId.value = null;
  activeTitle.value = "";
  messages.value = [];
  draft.value = "";
  profile.value = {};
  memoryStats.value = null;
  memoriesOpen.value = false;
  mobileSidebarOpen.value = false;
  loadError.value = "";
  health.value = null;
  backendState.value = "connecting";
  localStorage.removeItem(ACTIVE_KEY);
}

watch(
  () => authSession.value?.user.id,
  (userId, previousUserId) => {
    if (userId) void loadWorkspace();
    else if (previousUserId) clearUserWorkspace();
  },
);

async function send(text: string): Promise<void> {
  if (streaming.value || !backendReady.value) return;

  loadError.value = "";
  streaming.value = true;
  const run = ++generation;
  const isCurrent = () => run === generation;

  const sentProfile = isEmptyProfile(profile.value)
    ? undefined
    : { ...profile.value };
  messages.value.push({
    id: createId(),
    role: "user",
    content: text,
    profile: sentProfile,
    status: "done",
  });
  messages.value.push({
    id: createId(),
    role: "assistant",
    content: "",
    sources: [],
    trace: [],
    status: "streaming",
  });
  const assistant = messages.value[
    messages.value.length - 1
  ] as ChatMessage;

  const activeController = new AbortController();
  controller = activeController;

  await nextTick();
  scrollToBottom(true);

  try {
    await streamChat(
      {
        message: text,
        thread_id: activeThreadId.value ?? undefined,
        profile: sentProfile,
      },
      {
        onMeta: (meta) => {
          if (!isCurrent()) return;
          activeThreadId.value = meta.thread_id;
          activeTitle.value = meta.title;
          localStorage.setItem(ACTIVE_KEY, meta.thread_id);
          void refreshThreads();
        },
        onToken: ({ text: token }) => {
          if (!isCurrent()) return;
          assistant.content += token;
          scrollToBottom();
        },
        onToolStart: (data) => {
          if (!isCurrent()) return;
          assistant.trace = assistant.trace ?? [];
          assistant.trace.push({
            id: data.id || createId(),
            name: data.name,
            query: data.input?.query ?? "",
            status: "running",
          });
          scrollToBottom();
        },
        onToolEnd: (data) => {
          if (!isCurrent()) return;
          const trace = assistant.trace ?? [];
          const item =
            trace.find((entry) => entry.id === data.id) ??
            [...trace]
              .reverse()
              .find(
                (entry) =>
                  entry.name === data.name && entry.status === "running",
              );
          if (item) {
            item.status = data.ok ? "done" : "error";
            item.summary = data.summary;
            item.count = data.count;
          }
          scrollToBottom();
        },
        onSources: (data) => {
          if (!isCurrent()) return;
          assistant.sources = assistant.sources ?? [];
          const seen = new Set(assistant.sources.map((source) => source.url));
          for (const source of data.items) {
            if (!seen.has(source.url)) {
              seen.add(source.url);
              assistant.sources.push(source);
            }
          }
          scrollToBottom();
        },
        onDone: () => {
          if (!isCurrent()) return;
          assistant.status = "done";
        },
      },
      activeController.signal,
    );

    if (isCurrent() && assistant.status === "streaming") {
      assistant.status = "done";
    }
  } catch (error) {
    if (!isCurrent()) return;
    const aborted =
      activeController.signal.aborted ||
      (error instanceof DOMException && error.name === "AbortError");

    if (aborted) {
      assistant.status = "stopped";
      if (!assistant.content) assistant.content = "_已停止生成。_";
    } else {
      assistant.status = "error";
      assistant.error =
        error instanceof Error ? error.message : "生成失败，请重试。";
    }
  } finally {
    if (isCurrent()) {
      controller = null;
      streaming.value = false;
    }
    if (backendReady.value) {
      void refreshThreads();
      // 记忆抽取是后台任务，延迟一点再刷新侧栏统计
      window.setTimeout(() => void refreshMemoryStats(), 2500);
    }
    await nextTick();
    scrollToBottom();
  }
}

onMounted(() => {
  if (authSession.value) void loadWorkspace();
});

onBeforeUnmount(() => {
  controller?.abort();
});
</script>

<template>
  <AuthGate v-if="!authReady || !authSession" />
  <template v-else>
    <a class="skip-link" href="#main-scroll">跳到主要内容</a>

  <div class="app-shell">
    <Sidebar
      :threads="threads"
      :active-thread-id="activeThreadId"
      :open="mobileSidebarOpen"
      :turn-count="turnCount"
      :status-text="statusText"
      :status-tone="statusTone"
      :memory-stats="memoryStats"
      @new="newThread"
      @select="openThread"
      @close="closeSidebar"
      @retry="reconnect"
      @memories="openMemories"
    />

    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button
            class="menu-btn"
            type="button"
            aria-label="打开会话列表"
            @click="mobileSidebarOpen = true"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M2 4h12M2 8h12M2 12h12"
                stroke="currentColor"
                stroke-width="1.3"
                stroke-linecap="round"
              />
            </svg>
          </button>
          <span class="crumb-root">研究台</span>
          <template v-if="activeTitle">
            <span class="crumb-sep" aria-hidden="true">/</span>
            <span class="crumb-current">{{ activeTitle }}</span>
          </template>
        </div>

        <div class="topbar-right">
          <span class="search-chip">
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <circle
                cx="7"
                cy="7"
                r="4.2"
                stroke="currentColor"
                stroke-width="1.2"
              />
              <path
                d="m10.2 10.2 3 3"
                stroke="currentColor"
                stroke-width="1.2"
                stroke-linecap="round"
              />
            </svg>
            {{ health ? `${health.search} 检索` : "arXiv 检索" }}
          </span>
          <span class="mode-chip" :class="statusTone">
            <span class="mode-dot" aria-hidden="true"></span>
            {{ statusText }}
          </span>
          <span class="account-email">{{ userEmail }}</span>
          <button class="sign-out-button" type="button" @click="handleSignOut">退出</button>
        </div>
      </header>

      <div
        v-if="backendState === 'offline' || isDemo || loadError"
        class="banners"
      >
        <div
          v-if="backendState === 'offline'"
          class="banner error"
          role="status"
        >
          <span>后端未连接，暂时无法发起调研。</span>
          <button type="button" @click="reconnect">重试连接</button>
        </div>
        <div v-else-if="isDemo" class="banner demo" role="status">
          <span>演示模式 · 当前回答为界面示例。</span>
          <span class="banner-detail">
            在 <code>backend/.env</code> 配置 <code>DEEPSEEK_API_KEY</code>
            并重启服务后，切换为真实检索与生成。
          </span>
        </div>
        <div v-if="loadError" class="banner error" role="status">
          <span>{{ loadError }}</span>
          <button type="button" @click="loadError = ''">关闭</button>
        </div>
      </div>

      <div id="main-scroll" ref="scrollEl" class="main-scroll">
        <div class="page" :class="{ 'empty-page': !hasConversation }">
          <div v-if="!hasConversation" class="empty">
            <div class="empty-kicker">
              <span class="kicker-rule" aria-hidden="true"></span>
              研究台 · RESEARCH DESK
            </div>
            <h1 class="hero-title">
              把一个模糊的兴趣，<br />
              变成一条<span class="mark">阅读路线</span>。
            </h1>
            <p class="hero-sub">
              输入研究方向，也可以说说你的基础、目标和每周能投入的时间。智能体会检索
              arXiv 与 OpenAlex 的真实文献，按入门、基础、进阶、前沿四个阶段排好阅读顺序。
            </p>

            <ResearchComposer
              ref="composerRef"
              v-model="draft"
              v-model:profile="profile"
              variant="hero"
              :streaming="streaming"
              :disabled="!backendReady"
              submit-label="开始调研"
              @submit="send"
              @stop="stopStream"
            />

            <section class="starters" aria-label="示例问题">
              <div class="starters-label">可以这样开始</div>
              <button
                v-for="(starter, index) in starters"
                :key="starter"
                type="button"
                class="starter"
                @click="useStarter(starter)"
              >
                <span class="starter-index">0{{ index + 1 }}</span>
                <span class="starter-text">{{ starter }}</span>
                <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M3 8h9M8.5 4.5 12 8l-3.5 3.5"
                    stroke="currentColor"
                    stroke-width="1.2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
            </section>

            <p class="empty-foot">{{ emptyFoot }}</p>
          </div>

          <ConversationView v-else :messages="messages" :streaming="streaming" />
        </div>
      </div>

      <footer v-if="hasConversation" class="composer-dock">
        <div class="composer-inner">
          <ResearchComposer
            ref="composerRef"
            v-model="draft"
            v-model:profile="profile"
            variant="docked"
            :streaming="streaming"
            :disabled="!backendReady"
            submit-label="发送追问"
            @submit="send"
            @stop="stopStream"
          />
        </div>
      </footer>
    </main>
  </div>

  <MemoryPanel
    v-if="memoriesOpen"
    @close="memoriesOpen = false"
    @changed="memoryStats = $event"
  />
  </template>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  height: 100%;
}

.topbar {
  display: flex;
  flex: 0 0 57px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 28px;
  border-bottom: 1px solid var(--line);
  background: rgba(243, 238, 227, 0.82);
  backdrop-filter: blur(10px);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.menu-btn {
  display: none;
  flex: 0 0 auto;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-soft);
}

.menu-btn svg {
  width: 15px;
  height: 15px;
}

.crumb-root {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.16em;
  color: var(--muted);
  text-transform: uppercase;
}

.crumb-sep {
  color: var(--line-strong);
}

.crumb-current {
  max-width: 340px;
  overflow: hidden;
  font-size: 12px;
  color: var(--ink-soft);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.account-email {
  max-width: 180px;
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sign-out-button {
  border: 0;
  padding: 6px 8px;
  background: transparent;
  color: var(--accent-deep);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.search-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border: 1px solid var(--line);
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.06em;
  color: var(--muted);
  white-space: nowrap;
}

.search-chip svg {
  width: 11px;
  height: 11px;
}

.mode-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 235px;
  overflow: hidden;
  padding: 4px 9px;
  border: 1px solid var(--line);
  background: rgba(251, 248, 241, 0.4);
  color: var(--ink-soft);
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-dot {
  flex: 0 0 auto;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ok);
}

.mode-chip.demo .mode-dot {
  background: #b4842b;
}

.mode-chip.offline .mode-dot {
  background: var(--danger);
}

.mode-chip.loading .mode-dot {
  background: var(--muted);
  animation: mode-blink 1.2s ease-in-out infinite;
}

.banners {
  flex: 0 0 auto;
}

.banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 4px 10px;
  padding: 8px 24px;
  border-bottom: 1px solid var(--line);
  font-size: 11.5px;
  line-height: 1.6;
}

.banner.demo {
  border-bottom-color: #e4d3ae;
  background: #f6ecd8;
  color: #6f541a;
}

.banner.error {
  border-bottom-color: #e3bfb7;
  background: #f7e6e1;
  color: #7c261c;
}

.banner button {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font-size: 11.5px;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.banner code {
  padding: 1px 4px;
  background: rgba(255, 255, 255, 0.42);
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.banner-detail {
  opacity: 0.78;
}

.main-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.page {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 32px 36px;
}

.page.empty-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 100%;
  padding-top: clamp(26px, 5vh, 64px);
  padding-bottom: clamp(26px, 5vh, 56px);
}

.empty {
  width: 100%;
}

.empty-kicker {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--muted);
}

.kicker-rule {
  width: 26px;
  height: 1px;
  background: var(--accent);
}

.hero-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.4vw, 46px);
  font-weight: 600;
  line-height: 1.32;
  letter-spacing: 0.01em;
  color: var(--ink);
}

.mark {
  background: linear-gradient(
    transparent 64%,
    rgba(166, 58, 43, 0.17) 64%
  );
}

.hero-sub {
  max-width: 560px;
  margin: 18px 0 30px;
  font-size: 14px;
  line-height: 1.9;
  color: var(--muted);
}

.starters {
  margin-top: 28px;
}

.starters-label {
  margin-bottom: 6px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: var(--muted);
}

.starter {
  display: grid;
  grid-template-columns: 30px 1fr 16px;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 13px 4px;
  border: 0;
  border-top: 1px solid var(--line);
  background: none;
  color: var(--ink-soft);
  text-align: left;
  transition:
    padding-left 150ms ease,
    color 150ms ease;
}

.starter:last-of-type {
  border-bottom: 1px solid var(--line);
}

.starter:hover {
  padding-left: 8px;
  color: var(--accent);
}

.starter-index {
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.starter-text {
  font-family: var(--font-serif);
  font-size: 13.5px;
  line-height: 1.6;
}

.starter svg {
  width: 13px;
  height: 13px;
  color: var(--line-strong);
}

.starter:hover svg {
  color: var(--accent);
}

.empty-foot {
  margin: 24px 0 0;
  font-size: 10.5px;
  line-height: 1.7;
  color: var(--muted);
}

.composer-dock {
  flex: 0 0 auto;
  padding: 12px 0 18px;
  border-top: 1px solid var(--line);
  background: linear-gradient(
    180deg,
    rgba(243, 238, 227, 0.55),
    rgba(243, 238, 227, 0.97)
  );
}

.composer-inner {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 0 32px;
}

@keyframes mode-blink {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .menu-btn {
    display: grid;
  }

  .topbar {
    padding: 0 16px;
  }

  .crumb-current {
    max-width: 180px;
  }

  .page {
    padding: 28px 18px 30px;
  }

  .composer-inner {
    padding: 0 14px;
  }

  .composer-dock {
    padding-bottom: 12px;
  }

  .banner {
    justify-content: flex-start;
    padding: 8px 16px;
  }
}

@media (max-width: 640px) {
  .search-chip {
    display: none;
  }

  .mode-chip {
    max-width: 150px;
  }

  .crumb-current {
    max-width: 120px;
  }

  .hero-title {
    font-size: 30px;
  }

  .hero-sub {
    margin-bottom: 24px;
    font-size: 13px;
  }

  .starter {
    grid-template-columns: 26px 1fr 14px;
    gap: 10px;
  }

  .starter-text {
    font-size: 13px;
  }

  .banner-detail {
    flex-basis: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .mode-chip.loading .mode-dot {
    animation: none;
  }

  .starter {
    transition: none;
  }
}
</style>
