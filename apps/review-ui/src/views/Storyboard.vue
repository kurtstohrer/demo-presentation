<script setup lang="ts">
import { computed } from 'vue'
import { UiButton, UiChip, UiGrid } from '../components'
import { estimate, fmt, toast, type Beat, type Run, type Script } from '../api'
import BeatCard from './Beat.vue'
import DecisionButtons from './DecisionButtons.vue'

const props = defineProps<{ run: Run; saveScript: (script: Script) => Promise<void> }>()
const emit = defineEmits<{ decide: [body: Record<string, unknown>] }>()
const frames = computed(() => new Set(props.run.frames))
const openDecision = (scope: string, key: string) => props.run.review.decisions.find(d => d.state === 'open' && d.scope === scope && d.key === key)
const approved = (scope: string, key: string) => props.run.review.decisions.some(d => d.scope === scope && d.key === key && d.decision === 'approve' && d.version === props.run.review.version && d.state === 'done')
const commentsFor = (key: string) => props.run.review.comments.filter(c => c.key === key && c.status === 'open').length
const total = computed(() => props.run.script.scenes.reduce((n, s) => n + s.beats.reduce((m, b, i) => m + (props.run.audio[`${s.id}.${i}`]?.duration ?? estimate(b.say)) + 0.35, 1.3), 0))
async function saveBeat(si: number, bi: number, patch: Partial<Beat>) {
  const next = structuredClone(JSON.parse(JSON.stringify(props.run.script))) as Script
  Object.assign(next.scenes[si].beats[bi], patch)
  await props.saveScript(next)
  toast('Saved — re-render to see it')
}
const toVideo = () => { location.hash = `#/run/${encodeURIComponent(props.run.name)}/video` }
</script>

<template>
  <div>
    <div class="row intro">
      <p class="muted">{{ run.script.scenes.length }} scenes · ~{{ fmt(total) }} · voice <code>{{ run.script.voice ?? 'af_heart' }}</code> · {{ run.script.theme ?? 'dark' }}</p>
      <span class="spacer" />
      <UiButton v-if="run.review.status === 'draft' || run.review.status === 'storyboard-review'" size="sm" @click="emit('decide', { scope: 'run', decision: 'approve' })">Approve storyboard</UiButton>
    </div>
    <p v-if="!run.frames.length" class="muted">Edit narration and actions here. <b>Storyboard</b> above renders one frame per beat without recording.</p>
    <section v-for="(s, si) in run.script.scenes" :key="s.id" class="scene">
      <header class="head">
        <span class="num">{{ si + 1 }}</span>
        <h2>{{ s.title ?? s.id }}</h2>
        <UiChip>{{ s.type }}</UiChip>
        <UiChip v-if="run.stale.record.includes(s.id) && run.hasFinal" tone="b">changed since recording</UiChip>
        <span class="spacer" />
        <DecisionButtons scope="scene" :k="s.id" :open="openDecision('scene', s.id)" :approved="approved('scene', s.id)" @decide="b => emit('decide', b)" />
      </header>
      <p v-if="openDecision('scene', s.id)" class="note">Change requested: {{ openDecision('scene', s.id)?.note || '(no note)' }}</p>
      <UiGrid min="330px">
        <BeatCard v-for="(b, bi) in s.beats" :key="`${s.id}.${bi}`" :k="`${s.id}.${bi}`" :beat="b"
          :frame="frames.has(`${s.id}.${bi}.png`) ? `/files/${run.name}/storyboard/${s.id}.${bi}.png?v=${run.fingerprint}` : null"
          :dur="run.audio[`${s.id}.${bi}`]?.duration" :narration-stale="run.stale.narration.includes(`${s.id}.${bi}`)"
          :decision="openDecision('beat', `${s.id}.${bi}`)" :approved="approved('beat', `${s.id}.${bi}`)" :comments="commentsFor(`${s.id}.${bi}`)"
          :save-beat="p => saveBeat(si, bi, p)" @decide="d => emit('decide', d)" @comments="toVideo" />
      </UiGrid>
    </section>
  </div>
</template>

<style scoped>
.intro p { margin: 0; }
.intro { margin-bottom: 12px; }
.scene { margin-bottom: 28px; }
.head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
h2 { margin: 0; font-size: 17px; }
.num { background: rgb(var(--accent)); color: rgb(var(--on-accent)); border-radius: 6px; padding: 0 8px; font-weight: 600; }
.note { font-size: 12.5px; padding: 6px 9px; border-radius: var(--radius); background: rgb(var(--b-fill) / 0.14); }
</style>
