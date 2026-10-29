<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { ThemeController } from '../theme'
import { UiButton, UiChip, UiLog, UiThemePicker } from '../components'
import { STATUS, api, runUrl, toast, type Job, type Lexicon, type Run, type Script } from '../api'
import Needs from './Needs.vue'
import Storyboard from './Storyboard.vue'
import Player from './Player.vue'
import Pronunciations from './Pronunciations.vue'
import Requests from './Requests.vue'
import Changes from './Changes.vue'

const props = defineProps<{ name: string; tab?: string; theme: ThemeController }>()
const run = ref<Run | null>(null)
const error = ref('')
const job = ref<Job | null>(null)
const log = ref<string[]>([])
const showLog = ref(false)

async function load() {
  try {
    const r = await api<Run>('GET', runUrl(props.name))
    run.value = r
    if (r.job && !job.value) job.value = r.job
    error.value = ''
  } catch (e) { error.value = (e as Error).message }
}
load()

const events = new EventSource(runUrl(props.name, '/events'))
events.addEventListener('changed', () => load())
events.addEventListener('job', e => {
  const j = JSON.parse((e as MessageEvent).data) as Job
  job.value = j
  log.value = [...log.value, ...j.lines].slice(-800)
  if (j.state === 'failed') { showLog.value = true; toast(`${j.kind} failed — see the log`) }
  if (j.state === 'ok') toast(`${j.kind} finished`)
})
onBeforeUnmount(() => events.close())

const busy = computed(() => !!job.value && (job.value.state === 'running' || job.value.state === 'cancelling'))
async function startJob(kind: string, scenes: string[] = []) {
  try {
    log.value = []; showLog.value = true
    job.value = await api<Job>('POST', runUrl(props.name, '/jobs'), { kind, scenes })
  } catch (e) { toast((e as Error).message) }
}
async function cancelJob() { await api('POST', runUrl(props.name, '/jobs/cancel')).catch(() => {}) }
async function decide(body: Record<string, unknown>) {
  try { await api('POST', runUrl(props.name, '/decisions'), body); await load() } catch (e) { toast((e as Error).message) }
}
async function saveScript(script: Script) {
  await api('PUT', runUrl(props.name, '/script'), script)
  await load()
}
async function saveLibrary(entries: Lexicon) {
  await api('PUT', '/api/pronunciations', entries)
  await load()
}
async function copyBrief() {
  const prompt = `Address the review on demo run "${props.name}": run the demo-presentation skill's \`demo review ${props.name}\`, make the requested changes to script.json, re-render what changed, and reply to each item with \`demo review ${props.name} --reply <id> "..."\` / \`--done <id>\`.`
  try { await navigator.clipboard.writeText(prompt); toast('Agent prompt copied') } catch { toast('Copy failed — select the prompt in the review CLI instead') }
}

const openComments = computed(() => run.value?.review.comments.filter(c => c.status === 'open').length ?? 0)
const openDecisions = computed(() => run.value?.review.decisions.filter(d => d.state === 'open').length ?? 0)
// The video review is the main screen; everything else is a tool in the sidebar.
const active = computed(() => props.tab ?? 'video')
const href = (tool: string) => `#/run/${encodeURIComponent(props.name)}/${tool}`
const tools = computed(() => [
  { id: 'video', label: 'Video review', count: openComments.value },
  { id: 'storyboard', label: 'Script & storyboard' },
  { id: 'pronunciation', label: 'Pronunciation' },
  { id: 'review', label: 'Change requests', count: openDecisions.value },
  { id: 'changes', label: 'Changes' },
])
const jobTitle = computed(() => job.value ? `${job.value.kind}${job.value.scenes?.length ? ` · ${job.value.scenes.join(', ')}` : ''}` : '')
</script>

<template>
  <header class="topnav"><div class="inner">
    <a class="project" href="#/" title="All demos in this project">{{ run?.project ?? 'Demos' }}</a>
    <span class="sep" aria-hidden="true">/</span>
    <span class="title">{{ run?.script.title ?? name }}</span>
    <template v-if="run">
      <UiChip :tone="STATUS[run.review.status]?.[1] ?? 'neutral'">{{ STATUS[run.review.status]?.[0] ?? run.review.status }}</UiChip>
      <UiChip v-if="run.review.version">v{{ run.review.version }}</UiChip>
    </template>
    <span class="spacer" />
    <template v-if="run">
      <UiButton v-if="openComments + openDecisions > 0" size="sm" @click="copyBrief">Copy agent prompt</UiButton>
      <UiButton v-if="run.review.status === 'video-review'" size="sm" variant="primary" @click="decide({ scope: 'run', decision: 'approve' })">Approve video</UiButton>
    </template>
    <UiThemePicker :controller="theme" label="Theme" hide-label class="theme" />
    <nav class="tools" aria-label="Tools">
      <a v-for="x in tools" :key="x.id" class="tool" :href="href(x.id)" :aria-current="active === x.id ? 'page' : undefined">
        {{ x.label }}<span v-if="x.count" class="count">{{ x.count }}</span>
      </a>
    </nav>
  </div></header>

  <main class="wrap">
    <p v-if="error && !run" class="err">{{ error }}</p>
    <p v-else-if="!run" class="muted">Loading…</p>
    <template v-else>
      <Needs :run="run" :busy="busy" @start="startJob" />
      <UiLog v-if="job" v-model:open="showLog" class="job" :title="jobTitle" :state="job.state" :lines="log.length ? log : job.lines"
        :started="job.started" :ended="job.ended" @cancel="cancelJob" />

      <Player v-if="active === 'video'" :run="run" :save-library="saveLibrary" @reload="load" />
      <Storyboard v-else-if="active === 'storyboard'" :run="run" :save-script="saveScript" @decide="decide" />
      <Pronunciations v-else-if="active === 'pronunciation'" :run="run" :save-library="saveLibrary" />
      <Requests v-else-if="active === 'review'" :run="run" @decide="decide" />
      <Changes v-else-if="active === 'changes'" :run="run" />
    </template>
  </main>
</template>

<style scoped>
.topnav { position: sticky; top: 0; z-index: 20; background: rgb(var(--surface)); border-bottom: 1px solid rgb(var(--rule)); }
.inner { max-width: 1480px; margin: 0 auto; padding: 10px 24px 0; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.project { color: rgb(var(--text-muted)); text-decoration: none; font-weight: 600; }
.project:hover { color: rgb(var(--text)); }
.sep { color: rgb(var(--text-muted)); }
.title { font: 600 17px/1.2 var(--display); color: rgb(var(--text)); max-width: 32ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tools { flex-basis: 100%; display: flex; gap: 4px; overflow-x: auto; margin: 2px -10px 0; }
.tool { display: flex; align-items: center; gap: 6px; padding: 8px 10px 9px; border-bottom: 2px solid transparent; color: rgb(var(--text-2)); text-decoration: none; font-size: 14px; white-space: nowrap; }
.tool:hover { color: rgb(var(--text)); }
.tool[aria-current] { border-bottom-color: rgb(var(--accent)); color: rgb(var(--text)); font-weight: 600; }
.tool:focus-visible { outline: 2px solid rgb(var(--focus)); }
.count { font-size: 11.5px; padding: 0 7px; border-radius: 10px; background: rgb(var(--b-fill) / 0.25); color: rgb(var(--text)); }
.theme { width: 170px; }
.job { margin-bottom: 14px; }
@media (max-width: 820px) {
  .inner { padding: 8px 16px 0; }
  .theme { display: none; }
}
</style>
