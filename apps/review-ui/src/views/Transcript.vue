<!--
  Transcript — the narration under the video, word by word, one line at a time like a
  caption: the line holding the spoken word is shown and follows the voice. The spoken
  word is highlighted as the video plays; clicking a word seeks to it. While paused, the
  word under the playhead (or the clicked one) can have its pronunciation edited.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { UiButton, UiChip } from '../components'
import { fmt, wordKey, type Final, type Lexicon, type Word } from '../api'

const props = defineProps<{ final: Final; t: number; paused: boolean; lexicon: Lexicon; stale: string[] }>()
const emit = defineEmits<{ seek: [time: number]; pronounce: [word: string, context: string] }>()

type W = Word & { i: number; key: string }
// Old renders have no word timings in final.json: spread the words over the beat's audio.
const fallback = (say: string, start: number, dur: number): Word[] => {
  const ws = say.split(/\s+/).filter(Boolean)
  const total = ws.reduce((n, w) => n + w.length + 1, 0) || 1
  let t = start
  return ws.map(w => { const d = (dur * (w.length + 1)) / total; const o = { w, s: t, e: t + d }; t += d; return o })
}
const scenes = computed(() => {
  let i = 0
  return props.final.scenes.map(s => ({
    ...s,
    beats: s.beats.filter(b => b.say).map(b => ({
      ...b,
      words: (b.words?.length ? b.words : fallback(b.say, b.start, b.audio || b.end - b.start)).map(w => ({ ...w, i: i++, key: b.key }) as W),
    })),
  }))
})
const words = computed(() => scenes.value.flatMap(s => s.beats.flatMap(b => b.words)))
const timed = computed(() => !!props.final.scenes.some(s => s.beats.some(b => b.words?.length)))

/** Index of the last word that has started at time t (-1 before the first). */
const lastAt = (t: number) => {
  const ws = words.value
  let lo = 0, hi = ws.length - 1, out = -1
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (ws[mid].s <= t + 0.02) { out = mid; lo = mid + 1 } else hi = mid - 1 }
  return out
}
const last = computed(() => lastAt(props.t))
const current = computed(() => (last.value >= 0 && props.t <= words.value[last.value].e + 0.2 ? last.value : -1))
const currentBeat = computed(() => (last.value >= 0 ? words.value[last.value].key : ''))

const picked = ref<number | null>(null)
watch(() => props.paused, p => { if (!p) picked.value = null })
const editing = computed(() => (props.paused ? words.value[picked.value ?? last.value] : undefined))
const editKey = computed(() => (editing.value ? wordKey(editing.value.w) : ''))
const beatSay = (key: string) => scenes.value.flatMap(s => s.beats).find(b => b.key === key)?.say ?? ''

function pick(w: W) {
  picked.value = w.i
  emit('seek', w.s + 0.01)
}

// The box is one line tall: scroll it so the line holding the spoken word (or, while
// paused, the picked one) is the line shown. Between words it stays on the last line said.
const box = ref<HTMLElement | null>(null)
const shown = computed(() => editing.value?.i ?? Math.max(last.value, 0))
const currentScene = computed(() => scenes.value.find(s => s.beats.some(b => b.words.some(w => w.i === shown.value))))
const still = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
async function showLine(i: number, smooth = true) {
  await nextTick()
  const view = box.value, el = view?.querySelector<HTMLElement>(`[data-i="${i}"]`)
  if (!view || !el) return
  // .box is the offsetParent; an inline word sits centred in its line box, so step back by the half-leading.
  const line = parseFloat(getComputedStyle(el.parentElement!).lineHeight)
  const top = Math.max(0, el.offsetTop - (line - el.offsetHeight) / 2 - parseFloat(getComputedStyle(view).paddingTop))
  if (Math.abs(view.scrollTop - top) > 1) view.scrollTo({ top, behavior: smooth && !still ? 'smooth' : 'auto' })
}
watch(shown, i => showLine(i))
onMounted(() => showLine(shown.value, false))
// The line breaks move when the width changes; keep the same word on the shown line.
let resize: ResizeObserver | undefined
onMounted(() => { if (box.value && typeof ResizeObserver === 'function') { resize = new ResizeObserver(() => showLine(shown.value, false)); resize.observe(box.value) } })
onBeforeUnmount(() => resize?.disconnect())
</script>

<template>
  <section class="transcript" aria-label="Transcript">
    <div class="bar row">
      <b>Transcript</b>
      <button v-if="currentScene" class="scene-title" @click="emit('seek', currentScene.start)"><span class="mono">{{ fmt(currentScene.start) }}</span> {{ currentScene.title }}</button>
      <span v-if="!timed" class="muted small">approximate timing — re-narrate for word timing</span>
      <span class="spacer" />
      <template v-if="editing && editKey">
        <span class="muted small">Paused on</span>
        <UiChip tone="accent">{{ editKey }}</UiChip>
        <span v-if="lexicon[editKey]" class="mono small">→ {{ lexicon[editKey] }}</span>
        <UiButton size="sm" variant="primary" @click="emit('pronounce', editKey, beatSay(editing.key))">Edit pronunciation</UiButton>
      </template>
      <span v-else class="muted small">Pause, or click a word, to fix how it is said</span>
    </div>
    <div ref="box" class="box">
      <div v-for="s in scenes" :key="s.id" class="scene">
        <p v-for="b in s.beats" :key="b.key" class="beat" :data-current="b.key === currentBeat ? '' : undefined">
          <UiChip v-if="stale.includes(b.key)" tone="b" class="pending" title="Narration changed since this was recorded">re-narrate</UiChip>
          <template v-for="w in b.words" :key="w.i"><span
            class="w" :data-i="w.i"
            :data-now="w.i === current ? '' : undefined"
            :data-edit="editing && w.i === editing.i ? '' : undefined"
            :data-lex="lexicon[wordKey(w.w)] ? '' : undefined"
            :title="lexicon[wordKey(w.w)] ? `says: ${lexicon[wordKey(w.w)]}` : fmt(w.s)"
            @click="pick(w)">{{ w.w }}</span>{{ ' ' }}</template>
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.transcript { margin-top: 10px; border: 1px solid rgb(var(--rule)); border-radius: var(--radius-lg); background: rgb(var(--surface)); box-shadow: var(--lift-2); overflow: hidden; }
.bar { padding: 8px 12px; border-bottom: 1px solid rgb(var(--rule)); min-height: 46px; }
.small { font-size: 12.5px; }
/* One line of narration: exactly one line box tall, scrolled by showLine(), never by the reader.
   No vertical padding — scrolled content shows through padding, so the spacing is a margin. */
.box { --line: calc(15px * 1.75); height: var(--line); overflow: hidden; padding: 0 14px; margin: 8px 0; position: relative; }
.scene, .beat { margin: 0; }
.scene-title { border: 0; background: none; padding: 2px 0; color: rgb(var(--text-muted)); font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.scene-title:hover { color: rgb(var(--text)); }
.beat { line-height: 1.75; font-size: 15px; color: rgb(var(--text-2)); }
.beat[data-current] { color: rgb(var(--text)); }
.pending { margin-right: 6px; }
.w { cursor: pointer; border-radius: 4px; padding: 1px 2px; margin: 0 -2px; transition: background-color 80ms linear; }
.w:hover { background: rgb(var(--surface-3)); }
.w[data-lex] { text-decoration: underline dotted rgb(var(--accent)); text-underline-offset: 4px; }
.w[data-now] { background: rgb(var(--accent) / 0.32); color: rgb(var(--text)); }
.w[data-edit] { outline: 2px solid rgb(var(--focus)); }
@media (prefers-reduced-motion: reduce) { .w { transition: none; } }
</style>
