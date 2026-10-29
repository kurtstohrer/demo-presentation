<!--
  UiThread — one comment with its replies, a status and a reply box. The parent
  owns the data: `reply`, `status` and `remove` are emitted, nothing is stored here.
-->
<script setup lang="ts">
import { ref } from 'vue'
import UiButton from './UiButton.vue'
import UiField from './UiField.vue'

export interface ThreadReply { author: string; text: string; at?: string }

const props = withDefaults(defineProps<{
  text: string
  author?: string
  replies?: ReadonlyArray<ThreadReply>
  status?: string
  statuses?: ReadonlyArray<string>
  active?: boolean
  removable?: boolean
}>(), { author: undefined, replies: () => [], status: undefined, statuses: () => ['open', 'addressed', 'resolved', 'wontfix'], active: false, removable: false })
const emit = defineEmits<{ reply: [text: string]; status: [status: string]; remove: []; focus: [] }>()
const draft = ref('')
function send() { const t = draft.value.trim(); if (!t) return; emit('reply', t); draft.value = '' }
</script>

<template>
  <article class="ui-thread" :data-active="props.active ? '' : undefined" :data-closed="props.status && props.status !== 'open' ? '' : undefined">
    <header class="ui-thread__head">
      <slot name="meta" />
      <span class="ui-thread__spacer" />
      <select v-if="props.status" class="ui-thread__status" :value="props.status" aria-label="Status" @change="emit('status', ($event.target as HTMLSelectElement).value)">
        <option v-for="s in props.statuses" :key="s" :value="s">{{ s }}</option>
      </select>
    </header>
    <p class="ui-thread__text" @click="emit('focus')">{{ props.text }}</p>
    <ul v-if="props.replies.length" class="ui-thread__replies">
      <li v-for="(r, i) in props.replies" :key="i"><b>{{ r.author }}</b> {{ r.text }}</li>
    </ul>
    <form class="ui-thread__reply" @submit.prevent="send">
      <UiField v-model="draft" label="Reply" hide-label placeholder="Reply…" />
      <UiButton size="sm" type="submit" :disabled="!draft.trim()" reason="Write a reply first">Send</UiButton>
      <UiButton v-if="props.removable" size="sm" variant="ghost" aria-label="Delete comment" @click="emit('remove')">✕</UiButton>
    </form>
  </article>
</template>

<style>
.ui-thread { display: flex; flex-direction: column; gap: var(--s2); padding: var(--s3); background: rgb(var(--surface)); border: 1px solid rgb(var(--rule)); border-radius: var(--radius-lg); }
.ui-thread[data-active] { border-color: rgb(var(--focus)); }
.ui-thread[data-closed] { opacity: 0.7; }
.ui-thread__head { display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; }
.ui-thread__spacer { flex: 1; }
.ui-thread__status { padding: 3px 6px; border-radius: var(--radius); border: 1px solid rgb(var(--border)); background: rgb(var(--surface-2)); color: rgb(var(--text)); font: 12.5px var(--font); }
.ui-thread__text { margin: 0; white-space: pre-wrap; color: rgb(var(--text)); font: 14px/1.5 var(--font); cursor: default; }
.ui-thread__replies { list-style: none; margin: 0; padding: 0 0 0 10px; border-left: 2px solid rgb(var(--rule)); display: flex; flex-direction: column; gap: 4px; font: 13px/1.45 var(--font); color: rgb(var(--text-2)); }
.ui-thread__replies b { color: rgb(var(--text)); font-weight: 600; }
.ui-thread__reply { display: flex; gap: var(--s2); align-items: center; }
.ui-thread__reply .ui-field { flex: 1; }
</style>
