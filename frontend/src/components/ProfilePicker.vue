<script setup lang="ts">
import type { LearningProfile } from "../types";
import {
  BACKGROUND_OPTIONS,
  GOAL_OPTIONS,
  HOUR_OPTIONS,
  PREFERENCE_OPTIONS,
} from "../lib/profile";

defineProps<{
  disabled: boolean;
}>();

const profile = defineModel<LearningProfile>({ required: true });

type OptionValue = string | number;

function toggle<K extends keyof LearningProfile>(
  key: K,
  value: LearningProfile[K],
): void {
  profile.value = {
    ...profile.value,
    [key]: profile.value[key] === value ? undefined : value,
  };
}

function isActive(key: keyof LearningProfile, value: OptionValue): boolean {
  return profile.value[key] === value;
}
</script>

<template>
  <fieldset class="profile" :disabled="disabled">
    <legend class="sr-only">学习画像</legend>

    <div class="profile-row">
      <span class="profile-label">基础</span>
      <button
        v-for="option in BACKGROUND_OPTIONS"
        :key="option.value"
        type="button"
        class="profile-chip"
        :class="{ active: isActive('background', option.value) }"
        :aria-pressed="isActive('background', option.value)"
        @click="toggle('background', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="profile-row">
      <span class="profile-label">目标</span>
      <button
        v-for="option in GOAL_OPTIONS"
        :key="option.value"
        type="button"
        class="profile-chip"
        :class="{ active: isActive('goal', option.value) }"
        :aria-pressed="isActive('goal', option.value)"
        @click="toggle('goal', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="profile-row">
      <span class="profile-label">每周</span>
      <button
        v-for="hours in HOUR_OPTIONS"
        :key="hours"
        type="button"
        class="profile-chip"
        :class="{ active: isActive('weekly_hours', hours) }"
        :aria-pressed="isActive('weekly_hours', hours)"
        @click="toggle('weekly_hours', hours)"
      >
        {{ hours }} 小时
      </button>
      <span class="profile-label spaced">偏好</span>
      <button
        v-for="option in PREFERENCE_OPTIONS"
        :key="option.value"
        type="button"
        class="profile-chip"
        :class="{ active: isActive('preference', option.value) }"
        :aria-pressed="isActive('preference', option.value)"
        @click="toggle('preference', option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </fieldset>
</template>

<style scoped>
.profile {
  margin: 0 0 10px;
  padding: 0;
  border: 0;
}

.profile-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.profile-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--muted);
  margin-right: 2px;
}

.profile-label.spaced {
  margin-left: 14px;
}

.profile-chip {
  padding: 2px 9px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-soft);
  font-family: var(--font-sans);
  font-size: 12px;
  line-height: 1.7;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    background-color 140ms ease,
    color 140ms ease;
}

.profile-chip:hover:not(:disabled) {
  border-color: var(--line-strong);
}

.profile-chip.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-deep);
}

.profile-chip:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 640px) {
  .profile-label.spaced {
    margin-left: 0;
    width: 100%;
  }
}
</style>
