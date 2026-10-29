<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import type { ThemeController } from '../theme'
import { UiCard, UiChip, UiGrid, UiThemePicker } from '../components'
import { STATUS, ago, api, fmt, type RunSummary } from '../api'

defineProps<{ theme: ThemeController }>()
const runs = ref<RunSummary[] | null>(null)
const error = ref('')
const project = ref('')
api<{ name: string }>('GET', '/api/project').then(p => { project.value = p.name }).catch(() => {})
const load = () => api<RunSummary[]>('GET', '/api/runs').then(r => { runs.value = r; error.value = '' }).catch(e => { error.value = (e as Error).message })
load()
const timer = setInterval(load, 4000)
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="wrap">
    <div class="topbar">
      <h1>{{ project ? `${project} demos` : 'Demos' }}</h1>
      <span class="spacer" />
      <UiThemePicker :controller="theme" label="Theme" hide-label class="theme" />
    </div>
    <p v-if="error" class="err">{{ error }}</p>
    <UiCard v-if="runs && !runs.length" class="empty">
      <p>No runs yet.</p>
      <p class="muted">Ask the agent for a demo, or run <code>demo new &lt;name&gt;</code>.</p>
    </UiCard>
    <UiGrid min="300px">
      <UiCard v-for="r in runs ?? []" :key="r.name" as="a" :href="`#/run/${encodeURIComponent(r.name)}`" :padded="false" class="run">
        <div class="thumb">
          <img v-if="r.thumb" :src="`/files/${r.name}/${r.thumb}?v=${r.updated}`" alt="" loading="lazy">
          <span v-else class="muted">no storyboard yet</span>
        </div>
        <div class="body">
          <h3>{{ r.title }}</h3>
          <div class="row">
            <UiChip :tone="STATUS[r.status]?.[1] ?? 'neutral'">{{ STATUS[r.status]?.[0] ?? r.status }}</UiChip>
            <UiChip v-if="r.job?.state === 'running'" tone="accent" dot pulse>{{ r.job.kind }}</UiChip>
            <UiChip v-if="r.openDecisions" tone="b">{{ r.openDecisions }} change request{{ r.openDecisions > 1 ? 's' : '' }}</UiChip>
            <UiChip v-if="r.openComments" tone="b">{{ r.openComments }} open comment{{ r.openComments > 1 ? 's' : '' }}</UiChip>
          </div>
          <div class="muted">{{ r.scenes }} scene{{ r.scenes === 1 ? '' : 's' }}<template v-if="r.duration"> · {{ fmt(r.duration) }}</template><template v-if="r.version"> · v{{ r.version }}</template> · {{ ago(r.updated) }}</div>
        </div>
      </UiCard>
    </UiGrid>
  </div>
</template>

<style scoped>
.theme { width: 220px; }
.empty { text-align: center; padding: 48px; }
.run { transition: transform 120ms ease; }
.run:hover { transform: translateY(-2px); }
.thumb { aspect-ratio: 16 / 9; background: rgb(var(--surface-2)); display: grid; place-items: center; }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.body { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 8px; }
h3 { margin: 0; font-size: 15px; }
</style>
