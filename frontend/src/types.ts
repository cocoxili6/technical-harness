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

export interface LearningProfile {
  background?: "none" | "course" | "research";
  goal?: "overview" | "project" | "research";
  weekly_hours?: number;
  preference?: "survey" | "classic" | "recent";
}

export interface PaperAnalysis {
  research_problem: string;
  method: string;
  contributions: string[];
  limitations: string[];
  prerequisites: string[];
  difficulty: "入门" | "中等" | "较难";
  difficulty_reason: string;
  reading_time: string;
  paper_type: "综述" | "方法" | "实证" | "理论" | "系统" | "其他";
}

export type ToolStatus = "running" | "done" | "error";

export interface MemoryItem {
  id: string;
  text: string;
  kind: "interest" | "background" | "goal" | "preference" | "progress" | "fact" | string;
  importance: number;
  stability_days: number;
  retention: number;
  recall_count: number;
  created_at: string;
  last_recalled_at: string;
  forgotten: boolean;
  source: "auto" | "manual" | string;
}

export interface MemoryStats {
  active: number;
  forgotten: number;
  avg_retention: number;
}

export interface MemorySnapshot {
  items: MemoryItem[];
  stats: MemoryStats;
}

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
  profile?: LearningProfile;
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
    profile?: LearningProfile;
    sources?: Source[];
    trace?: TraceItem[];
  }>;
}

export type BackendState = "connecting" | "online" | "offline";

export type StatusTone = "ok" | "demo" | "offline" | "loading";
