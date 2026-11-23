import type { LearningProfile } from "../types";

export const BACKGROUND_OPTIONS = [
  { value: "none", label: "零基础" },
  { value: "course", label: "学过基础课" },
  { value: "research", label: "有研究经验" },
] as const;

export const GOAL_OPTIONS = [
  { value: "overview", label: "了解领域全景" },
  { value: "project", label: "准备毕设/课题" },
  { value: "research", label: "找研究问题" },
] as const;

export const PREFERENCE_OPTIONS = [
  { value: "survey", label: "综述优先" },
  { value: "classic", label: "经典优先" },
  { value: "recent", label: "最新优先" },
] as const;

export const HOUR_OPTIONS = [3, 6, 10, 20] as const;

function labelOf(
  options: ReadonlyArray<{ value: string; label: string }>,
  value?: string,
): string | null {
  return options.find((option) => option.value === value)?.label ?? null;
}

export function profileTags(profile?: LearningProfile): string[] {
  if (!profile) return [];
  return [
    labelOf(BACKGROUND_OPTIONS, profile.background),
    labelOf(GOAL_OPTIONS, profile.goal),
    profile.weekly_hours ? `每周 ${profile.weekly_hours} 小时` : null,
    labelOf(PREFERENCE_OPTIONS, profile.preference),
  ].filter((tag): tag is string => Boolean(tag));
}

export function isEmptyProfile(profile: LearningProfile): boolean {
  return profileTags(profile).length === 0;
}
