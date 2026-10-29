<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { UiButton, UiCard, UiChip, UiField } from '../components'
import { lexiconOf, speak, toast, wordKey, type Lexicon, type Run } from '../api'

const props = defineProps<{ run: Run; saveLibrary: (entries: Lexicon) => Promise<void> }>()

type Row = { word: string; say: string }
const toRows = (lex: Lexicon): Row[] => Object.entries(lex).map(([word, say]) => ({ word, say }))
const rows = ref<Row[]>(toRows(props.run.library))
watch(() => props.run.library, lib => { if (!dirty.value) rows.value = toRows(lib) })
const asLexicon = (list: Row[]): Lexicon => Object.fromEntries(list.filter(r => r.word.trim() && r.say.trim()).map(r => [r.word.trim(), r.say.trim()]))
const dirty = computed(() => JSON.stringify(asLexicon(rows.value)) !== JSON.stringify(props.run.library) || rows.value.some(r => !r.word.trim() || !r.say.trim()))
const err = ref('')
const playing = ref<string | null>(null)

// Words spoken in this run, for usage counts and suggestions.
const spoken = computed(() => {
  const n = new Map<string, number>()
  for (const s of props.run.script.scenes) for (const b of s.beats) for (const w of (b.say ?? '').split(/\s+/)) {
    const k = wordKey(w)
    if (k) n.set(k, (n.get(k) ?? 0) + 1)
  }
  return n
})
const scriptOnly = computed(() => Object.entries((props.run.script.lexicon as Lexicon | undefined) ?? {}).filter(([w]) => !(w in props.run.library)))
// Acronyms, camelCase, and dotted/dashed identifiers are what TTS most often gets wrong.
const suggestions = computed(() => {
  const known = lexiconOf(props.run)
  return [...spoken.value.keys()].filter(w => !(w in known) && /^[A-Z]{2,}s?$|[a-z][A-Z]|\w[._/-]\w/.test(w)).sort()
})

function add(word = '', say = '') { rows.value = [...rows.value, { word, say }] }
async function listen(r: Row) {
  playing.value = r.word
  try { await speak(r.word, props.run.script.voice, { ...lexiconOf(props.run), ...asLexicon([r]) }) } catch (e) { toast((e as Error).message) }
  finally { playing.value = null }
}
async function save() {
  const words = rows.value.map(r => r.word.trim())
  if (rows.value.some(r => !r.word.trim() || !r.say.trim())) { err.value = 'Every entry needs a word and how to say it (or remove the row).'; return }
  if (words.some(w => /\s/.test(w))) { err.value = 'One word per entry.'; return }
  if (new Set(words).size !== words.length) { err.value = 'Each word can appear only once.'; return }
  try { err.value = ''; await props.saveLibrary(asLexicon(rows.value)); toast('Library saved — re-render to hear the changes') }
  catch (e) { err.value = (e as Error).message }
}
</script>

<template>
  <div class="stack">
    <p class="muted intro">How narration says words, for every demo in this project. Write a sound-alike spelling
      (<code>C L I</code>, <code>git hub</code>) or IPA between slashes (<code>/kˈOkəɹO/</code>). Entries here win over a script's own lexicon.</p>

    <UiCard class="table">
      <div class="head"><span>Word</span><span>Say it as</span><span class="n">In this demo</span><span /></div>
      <p v-if="!rows.length" class="muted">The library is empty. Add a word, or pause the video and edit a word in the transcript.</p>
      <div v-for="(r, i) in rows" :key="i" class="line">
        <UiField v-model="r.word" :label="`Word ${i + 1}`" hide-label />
        <UiField v-model="r.say" :label="`Pronunciation of ${r.word || `word ${i + 1}`}`" hide-label mono />
        <span class="n muted">{{ spoken.get(r.word.trim()) ?? 0 }}×</span>
        <div class="row">
          <UiButton size="sm" :disabled="!r.word.trim() || !!playing" reason="Enter a word" @click="listen(r)">{{ playing === r.word ? '…' : 'Listen' }}</UiButton>
          <UiButton size="sm" variant="ghost" :aria-label="`Remove ${r.word}`" @click="rows = rows.filter((_, j) => j !== i)">Remove</UiButton>
        </div>
      </div>
      <p v-if="err" class="err">{{ err }}</p>
      <div class="row foot">
        <UiButton size="sm" @click="add()">Add word</UiButton>
        <span class="spacer" />
        <template v-if="dirty">
          <UiButton size="sm" variant="ghost" @click="rows = toRows(run.library); err = ''">Revert</UiButton>
          <UiButton size="sm" variant="primary" @click="save">Save library</UiButton>
        </template>
      </div>
    </UiCard>

    <UiCard v-if="scriptOnly.length" class="stack">
      <b>From this script's lexicon</b>
      <p class="muted">The agent set these in <code>script.json</code>. Add one to the library to reuse it and edit it here.</p>
      <div class="row">
        <UiButton v-for="[w, s] in scriptOnly" :key="w" size="sm" variant="ghost" @click="add(w, s)">{{ w }} → <span class="mono">{{ s }}</span> +</UiButton>
      </div>
    </UiCard>

    <UiCard v-if="suggestions.length" class="stack">
      <b>Worth checking</b>
      <p class="muted">Acronyms and identifiers in this narration without an entry.</p>
      <div class="row">
        <UiChip v-for="w in suggestions" :key="w" class="pick" role="button" tabindex="0" @click="add(w)" @keydown.enter="add(w)">{{ w }} +</UiChip>
      </div>
    </UiCard>
  </div>
</template>

<style scoped>
.intro { margin: 0; max-width: 760px; }
.table { display: flex; flex-direction: column; gap: 8px; }
.head, .line { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(160px, 2fr) 90px auto; gap: 10px; align-items: center; }
.head { font-size: 12.5px; color: rgb(var(--text-muted)); }
.n { text-align: right; }
.foot { margin-top: 4px; }
.pick { cursor: pointer; }
@media (max-width: 640px) {
  .head { display: none; }
  .line { grid-template-columns: 1fr 1fr; padding-bottom: 8px; border-bottom: 1px solid rgb(var(--rule)); }
  .n { text-align: left; }
}
</style>
