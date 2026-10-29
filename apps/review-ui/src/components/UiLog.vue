<!--
  UiLog — a live process log: state chip, elapsed time, optional cancel, and an
  auto-scrolling, collapsible output pane. Lines are plain text (escaped by Vue).
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import UiButton from './UiButton.vue'
import UiChip from './UiChip.vue'

const props = withDefaults(defineProps<{
  title: string
  lines: ReadonlyArray<string>
  state: 'running' | 'cancelling' | 'ok' | 'failed' | 'cancelled' | string
  started?: number
  ended?: number | null
  cancellable?: boolean
}>(), { started: undefined, ended: null, cancellable: true })
const emit = defineEmits<{ cancel: [] }>()
const open = defineModel<boolean>('open', { default: false })
const pane = ref<HTMLPreElement | null>(null)
const now = ref(Date.now() / 1000)
const running = computed(() => props.state === 'running' || props.state === 'cancelling')
let timer: ReturnType<typeof setInterval> | undefined
watch(running, r => { clearInterval(timer); if (r) timer = setInterval(() => { now.value = Date.now() / 1000 }, 1000) }, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
const elapsed = computed(() => props.started ? Math.max(0, Math.round((props.ended ?? now.value) - props.started)) : null)
const tone = computed(() => (props.state === 'ok' ? 'y' : props.state === 'failed' || props.state === 'cancelled' ? 'a' : running.value ? 'accent' : 'neutral'))
watch(() => [props.lines.length, open.value], async () => { await nextTick(); if (pane.value) pane.value.scrollTop = pane.value.scrollHeight })
</script>

<template>
  <section class="ui-log">
    <header class="ui-log__head">
      <UiChip :tone="tone" dot :pulse="running">{{ state }}</UiChip>
      <b class="ui-log__title">{{ title }}</b>
      <slot name="meta" />
      <span v-if="elapsed !== null" class="ui-log__time">{{ elapsed }}s</span>
      <span class="ui-log__spacer" />
      <UiButton v-if="cancellable && running" size="sm" variant="danger" @click="emit('cancel')">Cancel</UiButton>
      <UiButton size="sm" variant="ghost" :aria-expanded="open" @click="open = !open">{{ open ? 'Hide log' : 'Show log' }}</UiButton>
    </header>
    <pre v-if="open" ref="pane" class="ui-log__pane" tabindex="0" aria-label="Log output">{{ lines.join('\n') || '…' }}</pre>
  </section>
</template>

<style>
.ui-log { padding: var(--s2) var(--s3); background: rgb(var(--surface)); border: 1px solid rgb(var(--rule)); border-radius: var(--radius-lg); }
.ui-log__head { display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; font: 14px/1.4 var(--font); }
.ui-log__title { color: rgb(var(--text)); }
.ui-log__time { color: rgb(var(--text-muted)); font-variant-numeric: tabular-nums; }
.ui-log__spacer { flex: 1; }
.ui-log__pane {
  margin: var(--s2) 0 0; max-height: 240px; overflow: auto; padding: 10px 12px; border-radius: var(--radius);
  background: rgb(var(--surface-2)); color: rgb(var(--text-2)); font: 12px/1.5 var(--mono); white-space: pre-wrap;
}
.ui-log__pane:focus-visible { outline: 2px solid rgb(var(--focus)); }
</style>
