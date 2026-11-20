export interface Health {
  status: string;
  demo_mode: boolean;
  llm_configured: boolean;
  model: string;
  search: string;
  memory: string;
}

export interface ThreadSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Source {
  title: string;
  authors: string;
  year: string;
  url: string;
  category?: string;
  summary: string;
}

export type ToolStatus = "running" | "done" | "error";

export interface TraceItem {
  id: string;
  name: string;
  query: string;
  status: ToolStatus;
  summary?: string;
  count?: number;
}

export type MessageStatus = "streaming" | "done" | "error" | "stopped";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  trace?: TraceItem[];
  status?: MessageStatus;
  error?: string;
}

export interface ThreadDetail {
  id: string;
  title: string;
  created_at: string;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    sources?: Source[];
    trace?: TraceItem[];
  }>;
}

export type BackendState = "connecting" | "online" | "offline";

export type StatusTone = "ok" | "demo" | "offline" | "loading";
