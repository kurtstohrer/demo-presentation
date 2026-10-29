<script setup lang="ts">
import { computed } from 'vue'
import { UiButton, UiCard, UiChip, UiMenu } from '../components'
import type { Run } from '../api'

const props = defineProps<{ run: Run; busy: boolean }>()
const emit = defineEmits<{ start: [kind: string, scenes?: string[]] }>()
const all = computed(() => props.run.script.scenes.map(s => s.id))
const st = computed(() => props.run.stale)
const needsRender = computed(() => !!(st.value.record.length || st.value.stitch || st.value.narration.length))
function renderChanged() {
  const partial = st.value.record.length && st.value.record.length < all.value.length && props.run.hasFinal
  if (!st.value.record.length && st.value.stitch) return emit('start', 'stitch')
  emit('start', 'build', partial ? st.value.record : [])
}
function storyboard() {
  const f = props.run.frames.length, s = st.value.storyboard
  emit('start', 'storyboard', f && s.length < all.value.length ? s : [])
}
const more = [
  { id: 'tts', label: 'Narrate only' },
  { id: 'record', label: 'Record all scenes' },
  { id: 'stitch', label: 'Stitch only' },
  { id: 'build', label: 'Full rebuild', hint: 'all steps' },
]
const busyReason = 'A render job is running'
</script>

<template>
  <UiCard class="needs">
    <div class="row chips">
      <UiChip v-if="!run.frames.length">no storyboard</UiChip>
      <UiChip v-else-if="st.storyboard.length" tone="b">storyboard outdated: {{ st.storyboard.join(', ') }}</UiChip>
      <UiChip v-if="st.narration.length" tone="b">narration: {{ st.narration.length }} beat{{ st.narration.length > 1 ? 's' : '' }}</UiChip>
      <UiChip v-if="st.record.length && st.record.length < all.length" tone="b">re-record: {{ st.record.join(', ') }}</UiChip>
      <UiChip v-else-if="st.record.length">not recorded</UiChip>
      <UiChip v-if="st.stitch && !st.record.length" tone="b">needs stitch</UiChip>
      <UiChip v-if="!needsRender && run.hasFinal && !st.storyboard.length" tone="y">video up to date</UiChip>
    </div>
    <span class="spacer" />
    <div class="row">
      <UiButton :disabled="busy" :reason="busyReason" @click="storyboard">{{ run.frames.length && st.storyboard.length ? 'Refresh storyboard' : 'Storyboard' }}</UiButton>
      <UiButton :variant="needsRender ? 'primary' : 'secondary'" :disabled="busy || !needsRender" :reason="busy ? busyReason : 'Nothing changed since the last render'" @click="renderChanged">
        {{ run.hasFinal ? 'Re-render changes' : 'Render video' }}
      </UiButton>
      <UiMenu label="More" :items="more" :disabled="busy" @select="kind => emit('start', kind)" />
    </div>
  </UiCard>
</template>

<style scoped>
.needs { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
.chips { flex: 1 1 auto; }
</style>
