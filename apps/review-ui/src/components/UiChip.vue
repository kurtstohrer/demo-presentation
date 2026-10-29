<!-- UiChip — a small status word. The tone tints the chip; the text uses the tone's word colour, which is measured on --surface. -->
<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'neutral' | 'accent' | 'a' | 'b' | 'x' | 'y'; dot?: boolean; pulse?: boolean }>(), { tone: 'neutral', dot: false, pulse: false })
</script>

<template>
  <span class="ui-chip" :data-tone="tone"><span v-if="dot" class="ui-chip__dot" :data-pulse="pulse ? '' : undefined" aria-hidden="true" /><slot /></span>
</template>

<style>
.ui-chip {
  --tone: var(--text-muted);
  display: inline-flex; align-items: center; gap: 6px; padding: 1px 9px; border-radius: 99px;
  font: 500 12px/1.6 var(--font); color: rgb(var(--tone)); white-space: nowrap;
  /* The tint sits on an opaque surface: tone words are measured legible on --surface, never on --bg. */
  background: linear-gradient(rgb(var(--tone) / 0.12), rgb(var(--tone) / 0.12)), rgb(var(--surface));
  border: 1px solid rgb(var(--tone) / 0.32);
}
.ui-chip[data-tone='accent'] { --tone: var(--link); }
.ui-chip[data-tone='a'] { --tone: var(--a); }
.ui-chip[data-tone='b'] { --tone: var(--b); }
.ui-chip[data-tone='x'] { --tone: var(--x); }
.ui-chip[data-tone='y'] { --tone: var(--y); }
.ui-chip__dot { width: 7px; height: 7px; border-radius: 50%; background: rgb(var(--tone)); }
.ui-chip__dot[data-pulse] { animation: ui-pulse 1s ease-in-out infinite; }
@keyframes ui-pulse { 50% { opacity: 0.3; } }
@media (prefers-reduced-motion: reduce) { .ui-chip__dot[data-pulse] { animation: none; } }
</style>
