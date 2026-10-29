<script setup lang="ts">
import { ref } from 'vue'
import { UiButton, UiChip, UiField } from '../components'
import type { Decision } from '../api'

const props = defineProps<{ scope: 'run' | 'scene' | 'beat'; k: string; open?: Decision; approved: boolean }>()
const emit = defineEmits<{ decide: [body: Record<string, unknown>] }>()
const asking = ref(false)
const note = ref('')
function send() { emit('decide', { scope: props.scope, key: props.k, decision: 'changes', note: note.value }); asking.value = false; note.value = '' }
</script>

<template>
  <form v-if="asking" class="ask" @submit.prevent="send">
    <UiField v-model="note" label="What should change?" hide-label placeholder="What should change?" />
    <UiButton size="sm" variant="primary" type="submit">Send</UiButton>
    <UiButton size="sm" variant="ghost" @click="asking = false">Cancel</UiButton>
  </form>
  <div v-else class="row">
    <UiChip v-if="approved && !open" tone="y">approved</UiChip>
    <UiButton v-else size="sm" @click="emit('decide', { scope, key: k, decision: 'approve' })">Approve</UiButton>
    <UiButton size="sm" variant="ghost" @click="asking = true">{{ open ? 'Update request' : 'Request change' }}</UiButton>
  </div>
</template>

<style scoped>
.ask { display: flex; gap: 6px; align-items: center; flex: 1; min-width: 0; }
.ask :deep(.ui-field) { flex: 1; }
</style>
