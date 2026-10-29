<script setup lang="ts">
import { computed, ref } from 'vue'
import { UiButton, UiCard, UiChip, UiField } from '../components'
import type { Run } from '../api'

const props = defineProps<{ run: Run }>()
const emit = defineEmits<{ decide: [body: Record<string, unknown>] }>()
const note = ref('')
const say = (key: string | null) => {
  if (!key) return ''
  const i = key.lastIndexOf('.')
  return props.run.script.scenes.find(s => s.id === key.slice(0, i))?.beats[Number(key.slice(i + 1))]?.say ?? ''
}
const list = computed(() => [...props.run.review.decisions].reverse())
function send() { if (!note.value.trim()) return; emit('decide', { scope: 'run', decision: 'changes', note: note.value }); note.value = '' }
</script>

<template>
  <div class="stack">
    <UiCard as="form" class="composer" @submit.prevent="send">
      <b>Request a change to the whole demo</b>
      <UiField v-model="note" label="Change request" hide-label multiline :rows="3" placeholder="e.g. Make it shorter, open with the CLI instead of the whiteboard" />
      <div class="row"><span class="spacer" /><UiButton size="sm" variant="primary" type="submit" :disabled="!note.trim()" reason="Describe the change first">Request changes</UiButton></div>
    </UiCard>
    <p v-if="!list.length" class="muted">No approvals or change requests yet. Use the buttons on scenes and beats in the storyboard.</p>
    <UiCard v-for="d in list" :key="d.id" class="item" :data-closed="d.state !== 'open' ? '' : undefined">
      <div class="row">
        <UiChip :tone="d.decision === 'approve' ? 'y' : 'b'">{{ d.decision === 'approve' ? 'approved' : 'change' }}</UiChip>
        <span class="mono">{{ d.scope }}{{ d.key ? ` ${d.key}` : '' }}</span>
        <span class="muted">v{{ d.version }} · {{ d.state }}</span>
      </div>
      <p v-if="d.scope === 'beat'" class="muted">“{{ say(d.key) }}”</p>
      <p v-if="d.note">{{ d.note }}</p>
      <p v-if="d.reply" class="reply"><b>agent</b> {{ d.reply }}</p>
    </UiCard>
  </div>
</template>

<style scoped>
.composer, .item { display: flex; flex-direction: column; gap: 8px; }
.item[data-closed] { opacity: 0.7; }
.item p { margin: 0; }
.reply { padding-left: 10px; border-left: 2px solid rgb(var(--rule)); }
</style>
