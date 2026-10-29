<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { UiButton, UiChip, UiDialog, UiField } from '../components'
import { lexiconOf, speak, toast, type Lexicon, type Run } from '../api'

const props = defineProps<{ run: Run; word: string; context: string; saveLibrary: (entries: Lexicon) => Promise<void> }>()
const open = defineModel<boolean>('open', { default: false })

const key = ref('')
const say = ref('')
const err = ref('')
const busy = ref<'' | 'word' | 'context' | 'save'>('')
const scriptSay = computed(() => (props.run.script.lexicon as Lexicon | undefined)?.[key.value.trim()])
const librarySay = computed(() => props.run.library[key.value.trim()])
watch(open, v => {
  if (!v) return
  key.value = props.word
  say.value = props.run.library[props.word] ?? (props.run.script.lexicon as Lexicon | undefined)?.[props.word] ?? ''
  err.value = ''
}, { immediate: true })

const draft = (): Lexicon => {
  const lex = lexiconOf(props.run)
  const k = key.value.trim()
  if (k && say.value.trim()) lex[k] = say.value.trim()
  else delete lex[k]
  return lex
}
async function listen(which: 'word' | 'context') {
  busy.value = which
  try { await speak(which === 'word' ? key.value.trim() : props.context, props.run.script.voice, draft(), props.run.script.speed as number | undefined) }
  catch (e) { toast((e as Error).message) }
  finally { busy.value = '' }
}
async function save(remove = false) {
  const k = key.value.trim()
  if (!k || /\s/.test(k)) { err.value = 'One word per entry.'; return }
  if (!remove && !say.value.trim()) { err.value = 'Write how it should sound, or remove the entry.'; return }
  const next = { ...props.run.library }
  if (remove) delete next[k]
  else next[k] = say.value.trim()
  busy.value = 'save'
  try { await props.saveLibrary(next); open.value = false; toast(remove ? `Removed “${k}”` : `Saved “${k}” — re-render to hear it in the video`) }
  catch (e) { err.value = (e as Error).message }
  finally { busy.value = '' }
}
</script>

<template>
  <UiDialog v-model:open="open" title="Edit pronunciation" description="Saved to the project's pronunciation library, used by every demo.">
    <form class="stack" @submit.prevent="save()">
      <UiField v-model="key" label="Word" hint="Matched as a whole word, case-sensitive." />
      <UiField v-model="say" label="Say it as" placeholder="e.g. C L I   or   /kˈOkəɹO/"
        hint="A sound-alike spelling, or IPA between slashes." :error="err || undefined" />
      <div class="row">
        <UiButton size="sm" :disabled="!!busy || !key.trim()" reason="Enter a word" @click="listen('word')">{{ busy === 'word' ? 'Speaking…' : 'Listen' }}</UiButton>
        <UiButton v-if="context" size="sm" variant="ghost" :disabled="!!busy" reason="Busy" @click="listen('context')">{{ busy === 'context' ? 'Speaking…' : 'Listen in sentence' }}</UiButton>
        <span class="spacer" />
        <UiChip v-if="librarySay">in library</UiChip>
        <UiChip v-else-if="scriptSay" tone="x" :title="`This script's lexicon says “${scriptSay}”; a library entry overrides it`">from script</UiChip>
      </div>
      <p v-if="context" class="muted ctx">“{{ context }}”</p>
    </form>
    <template #footer>
      <UiButton v-if="librarySay" variant="danger" :disabled="!!busy" reason="Busy" @click="save(true)">Remove</UiButton>
      <span class="spacer" />
      <UiButton variant="ghost" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :disabled="!!busy" reason="Busy" @click="save()">{{ busy === 'save' ? 'Saving…' : 'Save' }}</UiButton>
    </template>
  </UiDialog>
</template>

<style scoped>
.ctx { margin: 0; font-size: 13px; }
</style>
