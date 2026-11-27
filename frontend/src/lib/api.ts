import type {
  Health,
  LearningProfile,
  MemorySnapshot,
  PaperAnalysis,
  Source,
  ThreadDetail,
  ThreadSummary,
} from "../types";
import { getAccessToken, refreshAccessToken } from "./supabase";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = await getAccessToken();
  if (token) headers.set("authorization", `Bearer ${token}`);

  const response = await fetch(input, { ...init, headers });
  if (response.status !== 401) return response;

  const refreshedToken = await refreshAccessToken();
  if (!refreshedToken) return response;
  headers.set("authorization", `Bearer ${refreshedToken}`);
  return fetch(input, { ...init, headers });
}

async function errorFromResponse(response: Response): Promise<Error> {
  let message = `请求失败（${response.status}）`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail) && typeof body.detail[0]?.msg === "string") {
      message = body.detail[0].msg;
    }
  } catch {
    // keep the status-based message
  }
  return new Error(message);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authenticatedFetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return requestJson<Health>("/api/health");
}

export function listThreads(): Promise<{ threads: ThreadSummary[] }> {
  return requestJson<{ threads: ThreadSummary[] }>("/api/threads");
}

export function getThread(threadId: string): Promise<ThreadDetail> {
  return requestJson<ThreadDetail>(`/api/threads/${encodeURIComponent(threadId)}`);
}

export function analyzePaper(
  source: Source,
): Promise<{ demo: boolean; analysis: PaperAnalysis }> {
  return requestJson<{ demo: boolean; analysis: PaperAnalysis }>(
    "/api/papers/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        title: source.title,
        authors: source.authors,
        year: source.year,
        url: source.url,
        category: source.category ?? "",
        summary: source.summary,
      }),
    },
  );
}

export function listMemories(): Promise<MemorySnapshot> {
  return requestJson<MemorySnapshot>("/api/memories");
}

export function addMemory(text: string): Promise<MemorySnapshot> {
  return requestJson<MemorySnapshot>("/api/memories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export function reviewMemory(memoryId: string): Promise<MemorySnapshot> {
  return requestJson<MemorySnapshot>(
    `/api/memories/${encodeURIComponent(memoryId)}/review`,
    { method: "POST" },
  );
}

export function deleteMemory(memoryId: string): Promise<MemorySnapshot> {
  return requestJson<MemorySnapshot>(
    `/api/memories/${encodeURIComponent(memoryId)}`,
    { method: "DELETE" },
  );
}

export interface StreamHandlers {
  onMeta: (data: { thread_id: string; title: string; demo: boolean }) => void;
  onToken: (data: { text: string }) => void;
  onToolStart: (data: { id: string; name: string; input: { query?: string } }) => void;
  onToolEnd: (data: {
    id: string;
    name: string;
    ok: boolean;
    summary: string;
    count: number;
  }) => void;
  onSources: (data: { items: Source[] }) => void;
  onDone: (data: { thread_id: string }) => void;
}

interface ParsedEvent {
  event: string;
  data: string;
}

function parseEvent(block: string): ParsedEvent | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(":")) continue;
    const separator = rawLine.indexOf(":");
    const field = separator === -1 ? rawLine : rawLine.slice(0, separator);
    let value = separator === -1 ? "" : rawLine.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }

  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

function dispatch(parsed: ParsedEvent, handlers: StreamHandlers): void {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(parsed.data) as Record<string, unknown>;
  } catch {
    return;
  }

  switch (parsed.event) {
    case "meta":
      handlers.onMeta(payload as unknown as { thread_id: string; title: string; demo: boolean });
      break;
    case "token":
      if (typeof payload.text === "string") handlers.onToken({ text: payload.text });
      break;
    case "tool_start":
      handlers.onToolStart(payload as unknown as { id: string; name: string; input: { query?: string } });
      break;
    case "tool_end":
      handlers.onToolEnd(
        payload as unknown as {
          id: string;
          name: string;
          ok: boolean;
          summary: string;
          count: number;
        },
      );
      break;
    case "sources":
      if (Array.isArray(payload.items)) {
        handlers.onSources({ items: payload.items as Source[] });
      }
      break;
    case "done":
      handlers.onDone(payload as unknown as { thread_id: string });
      break;
    case "error": {
      const message =
        typeof payload.message === "string" ? payload.message : "生成失败，请重试。";
      throw new Error(message);
    }
    default:
      break;
  }
}

export async function streamChat(
  input: { message: string; thread_id?: string; profile?: LearningProfile },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(input),
    signal,
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const parsed = parseEvent(block);
        if (parsed) dispatch(parsed, handlers);
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const parsed = parseEvent(buffer);
      if (parsed) dispatch(parsed, handlers);
    }
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    throw error;
  }
}
