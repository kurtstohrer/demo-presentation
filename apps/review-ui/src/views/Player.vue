<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { UiButton, UiCard, UiChip, UiField, UiThread } from '../components'
import { api, fmt, lexiconOf, runUrl, toast, type Comment, type Lexicon, type Region, type Run } from '../api'
import Transcript from './Transcript.vue'
import PronounceDialog from './PronounceDialog.vue'

const props = defineProps<{ run: Run; saveLibrary: (entries: Lexicon) => Promise<void> }>()
const emit = defineEmits<{ reload: [] }>()
const video = ref<HTMLVideoElement | null>(null)
const t = ref(0)
const paused = ref(true)
const pronounce = ref<{ word: string; context: string } | null>(null)
const pronounceOpen = computed({ get: () => !!pronounce.value, set: v => { if (!v) pronounce.value = null } })
const lexicon = computed(() => lexiconOf(props.run))
const draft = ref<{ t: number; text: string; region: Region | null } | null>(null)
const marking = ref(false)
const drag = ref<{ a: { x: number; y: number }; b: { x: number; y: number } } | null>(null)
const activeId = ref<string | null>(null)
const filter = ref<'open' | 'closed' | 'all'>('open')

const final = computed(() => props.run.final)
const duration = computed(() => final.value?.duration ?? 0)
const beats = computed(() => (final.value?.scenes ?? []).flatMap(s => s.beats.map(b => ({ ...b, scene: s }))))
const beatAt = (time: number) => beats.value.filter(b => b.start <= time).pop()
const comments = computed(() => props.run.review.comments
  .filter(c => filter.value === 'all' || (filter.value === 'open' ? c.status === 'open' : c.status !== 'open'))
  .slice().sort((a, b) => (a.t ?? 1e9) - (b.t ?? 1e9)))
const active = computed(() => props.run.review.comments.find(c => c.id === activeId.value))
const pct = (time: number) => `${(100 * time) / (duration.value || 1)}%`

function seek(time: number) {
  const v = video.value
  if (!v) return
  v.currentTime = Math.max(0, Math.min(duration.value, time))
  t.value = v.currentTime
}
function startComment() {
  video.value?.pause()
  draft.value = { t: video.value?.currentTime ?? t.value, text: '', region: null }
}
function onKey(e: KeyboardEvent) {
  if (pronounce.value || /INPUT|TEXTAREA|SELECT/.test((document.activeElement as HTMLElement | null)?.tagName ?? '')) return
  const v = video.value
  if (!v) return
  const keys: Record<string, () => void> = {
    c: startComment, C: startComment,
    ' ': () => { v.paused ? void v.play() : v.pause() },
    ArrowLeft: () => seek(v.currentTime - (e.shiftKey ? 1 : 5)),
    ArrowRight: () => seek(v.currentTime + (e.shiftKey ? 1 : 5)),
    ',': () => { v.pause(); seek(v.currentTime - 1 / 30) },
    '.': () => { v.pause(); seek(v.currentTime + 1 / 30) },
  }
  const action = keys[e.key]
  if (action) { e.preventDefault(); action() }
}
onMounted(() => addEventListener('keydown', onKey))
onBeforeUnmount(() => { removeEventListener('keydown', onKey); cancelAnimationFrame(raf) })

// timeupdate fires only ~4×/s; follow the playhead every frame so the transcript keeps up with the voice.
let raf = 0
function follow() {
  if (video.value) t.value = video.value.currentTime
  if (!paused.value) raf = requestAnimationFrame(follow)
}
function onPlay() { paused.value = false; cancelAnimationFrame(raf); raf = requestAnimationFrame(follow) }
function onPause() { paused.value = true; cancelAnimationFrame(raf); if (video.value) t.value = video.value.currentTime }

function onTimeline(e: MouseEvent) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  seek(((e.clientX - r.left) / r.width) * duration.value)
}
const rel = (e: PointerEvent) => {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) }
}
const box = (a: { x: number; y: number }, b: { x: number; y: number }): Region => ({ x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) })
function down(e: PointerEvent) { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); const p = rel(e); drag.value = { a: p, b: p } }
function move(e: PointerEvent) { if (drag.value) drag.value = { ...drag.value, b: rel(e) } }
function up() {
  if (drag.value && draft.value) { const r = box(drag.value.a, drag.value.b); if (r.w > 0.01 && r.h > 0.01) draft.value.region = r }
  drag.value = null; marking.value = false
}
const shownRegion = computed<Region | null>(() => (drag.value ? box(drag.value.a, drag.value.b) : draft.value?.region ?? active.value?.region ?? null))

async function submit() {
  if (!draft.value?.text.trim()) return
  try {
    await api('POST', runUrl(props.run.name, '/comments'), { t: draft.value.t, text: draft.value.text, region: draft.value.region })
    draft.value = null
    emit('reload')
  } catch (e) { toast((e as Error).message) }
}
async function patch(c: Comment, body: Record<string, unknown>) {
  try { await api('PATCH', runUrl(props.run.name, `/comments/${c.id}`), body); emit('reload') } catch (e) { toast((e as Error).message) }
}
async function remove(c: Comment) {
  await api('DELETE', runUrl(props.run.name, `/comments/${c.id}`)).catch(e => toast((e as Error).message))
  emit('reload')
}
function focus(c: Comment) { activeId.value = c.id; if (c.t != null) seek(c.t) }
</script>

<template>
  <UiCard v-if="!run.hasFinal || !final" class="empty">
    <p>No video yet.</p>
    <p class="muted">The agent records it once you approve the outline in chat — or use <b>Render video</b> above.</p>
  </UiCard>
  <div v-else class="player">
    <div class="main">
      <div class="video-box">
        <video ref="video" :src="`/files/${run.name}/final.mp4?v=${run.videoVersion}`" controls preload="auto" playsinline
          @timeupdate="t = ($event.target as HTMLVideoElement).currentTime" @seeked="t = ($event.target as HTMLVideoElement).currentTime"
          @play="onPlay" @pause="onPause" @ended="onPause" />
        <div v-if="marking" class="region-layer" @pointerdown="down" @pointermove="move" @pointerup="up" />
        <div v-if="shownRegion" class="region"
          :style="{ left: `${shownRegion.x * 100}%`, top: `${shownRegion.y * 100}%`, width: `${shownRegion.w * 100}%`, height: `${shownRegion.h * 100}%` }" />
      </div>
      <div class="timeline" role="slider" aria-label="Timeline" :aria-valuemin="0" :aria-valuemax="duration" :aria-valuenow="t" @click="onTimeline">
        <div class="segs"><div v-for="s in final.scenes" :key="s.id" class="seg" :data-type="s.type" :style="{ width: pct(s.end - s.start) }" :title="s.title">{{ s.title }}</div></div>
        <div v-for="b in beats" :key="b.key" class="tick" :style="{ left: pct(b.start) }" />
        <button v-for="c in run.review.comments.filter(x => x.t != null)" :key="c.id" class="pin" :data-done="c.status !== 'open' ? '' : undefined"
          :style="{ left: pct(c.t!) }" :title="c.text" :aria-label="`Comment at ${fmt(c.t)}`" @click.stop="focus(c)" />
        <div class="head" :style="{ left: pct(t) }" />
      </div>
      <div class="now row">
        <span class="muted">{{ fmt(t) }} / {{ fmt(duration) }}</span>
        <span class="spacer" />
        <span class="muted keys"><span class="kbd">C</span> comment · <span class="kbd">space</span> play · <span class="kbd">←</span><span class="kbd">→</span> 5s · <span class="kbd">,</span><span class="kbd">.</span> frame</span>
      </div>
      <Transcript :final="final" :t="t" :paused="paused" :lexicon="lexicon" :stale="run.stale.narration"
        @seek="seek" @pronounce="(word, context) => { pronounce = { word, context } }" />
    </div>

    <aside class="side">
      <UiCard v-if="draft" as="form" class="composer" @submit.prevent="submit">
        <div class="row"><b>Comment at {{ fmt(draft.t) }}</b><span class="mono muted">{{ beatAt(draft.t)?.key ?? '' }}</span></div>
        <UiField v-model="draft.text" label="Comment" hide-label multiline :rows="3" placeholder="What should change here?"
          @keydown.ctrl.enter="submit" @keydown.meta.enter="submit" />
        <div class="row">
          <UiButton size="sm" @click="marking = true">{{ draft.region ? 'Re-mark region' : 'Mark region' }}</UiButton>
          <UiButton v-if="draft.region" size="sm" variant="ghost" @click="draft.region = null">Clear region</UiButton>
          <span class="spacer" />
          <UiButton size="sm" variant="ghost" @click="draft = null">Cancel</UiButton>
          <UiButton size="sm" variant="primary" type="submit" :disabled="!draft.text.trim()" reason="Write the comment first">Add</UiButton>
        </div>
        <p v-if="marking" class="muted">Drag on the video to mark the area.</p>
      </UiCard>
      <UiButton v-else variant="primary" @click="startComment">Comment at {{ fmt(t) }}</UiButton>
      <div class="row">
        <UiButton v-for="f in (['open', 'closed', 'all'] as const)" :key="f" size="sm" :variant="filter === f ? 'secondary' : 'ghost'" @click="filter = f">{{ f }}</UiButton>
      </div>
      <p v-if="!comments.length" class="muted">No {{ filter === 'all' ? '' : filter }} comments.</p>
      <UiThread v-for="c in comments" :key="c.id" :text="c.text" :status="c.status" :replies="c.replies" :active="c.id === activeId"
        :removable="c.author !== 'agent'" @focus="focus(c)" @status="s => patch(c, { status: s })" @reply="text => patch(c, { reply: text, author: 'reviewer' })"
        @remove="remove(c)">
        <template #meta>
          <UiChip v-if="c.t != null" tone="accent" class="time" @click="focus(c)">{{ fmt(c.t) }}</UiChip>
          <span class="mono muted">{{ c.key ?? '' }}</span>
          <UiChip v-if="c.region">region</UiChip>
          <UiChip v-if="c.version < run.review.version" :title="`Left on render v${c.version}`">v{{ c.version }}</UiChip>
        </template>
      </UiThread>
    </aside>
    <PronounceDialog v-model:open="pronounceOpen" :run="run" :word="pronounce?.word ?? ''" :context="pronounce?.context ?? ''" :save-library="saveLibrary" />
  </div>
</template>

<style scoped>
.empty { text-align: center; padding: 48px; }
.player { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 18px; align-items: start; }
@media (max-width: 1100px) { .player { grid-template-columns: 1fr; } }
.main { min-width: 0; }
.video-box { position: relative; background: #000; border-radius: var(--radius-lg); overflow: hidden; aspect-ratio: 16 / 9; }
.video-box video { width: 100%; height: 100%; display: block; }
.region-layer { position: absolute; inset: 0; cursor: crosshair; }
.region { position: absolute; border: 2px solid rgb(var(--accent)); background: rgb(var(--accent) / 0.18); border-radius: 4px; pointer-events: none; }
.timeline { position: relative; height: 54px; margin-top: 12px; cursor: pointer; user-select: none; }
.segs { position: absolute; left: 0; right: 0; top: 18px; height: 22px; display: flex; border-radius: var(--radius); overflow: hidden; }
.seg { height: 100%; border-right: 2px solid rgb(var(--bg)); overflow: hidden; font-size: 11px; padding: 3px 6px; color: rgb(var(--text)); white-space: nowrap; text-overflow: ellipsis; background: rgb(var(--surface-3)); }
.seg[data-type='whiteboard'] { background: rgb(var(--x-fill) / 0.35); }
.seg[data-type='terminal'] { background: rgb(var(--y-fill) / 0.35); }
.seg[data-type='code'] { background: rgb(var(--b-fill) / 0.35); }
.seg[data-type='chat'] { background: rgb(var(--b-fill) / 0.2); }
.seg[data-type='ui'] { background: rgb(var(--accent) / 0.35); }
.tick { position: absolute; top: 40px; width: 1px; height: 6px; background: rgb(var(--text-muted)); }
.pin { position: absolute; top: 0; width: 14px; height: 14px; margin-left: -7px; padding: 0; border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
  background: rgb(var(--accent)); border: 2px solid rgb(var(--surface)); cursor: pointer; }
.pin[data-done] { background: rgb(var(--text-muted)); }
.pin:focus-visible { outline: 2px solid rgb(var(--focus)); }
.head { position: absolute; top: 12px; bottom: 6px; width: 2px; margin-left: -1px; background: rgb(var(--text)); pointer-events: none; }
.now { margin-top: 2px; }
.keys { font-size: 12.5px; }
.side { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.composer { display: flex; flex-direction: column; gap: 8px; }
.time { cursor: pointer; }
</style>
