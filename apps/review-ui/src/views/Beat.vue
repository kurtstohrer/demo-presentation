<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { UiButton, UiCard, UiChip, UiField } from '../components'
import { actionSummary, estimate, type Beat, type Decision } from '../api'
import DecisionButtons from './DecisionButtons.vue'

const props = defineProps<{ k: string; beat: Beat; frame: string | null; dur?: number; narrationStale: boolean; decision?: Decision; approved: boolean; comments: number; saveBeat: (patch: Partial<Beat>) => Promise<void> }>()
const emit = defineEmits<{ decide: [body: Record<string, unknown>]; comments: [] }>()

const say = ref(props.beat.say ?? '')
watch(() => props.beat.say, v => { say.value = v ?? '' })
const dirty = computed(() => say.value !== (props.beat.say ?? ''))
const editing = ref(false)
const json = ref('')
const err = ref('')
async function save(patch: Partial<Beat>) {
  try { err.value = ''; await props.saveBeat(patch); editing.value = false } catch (e) { err.value = (e as Error).message }
}
function saveActions() {
  try { save({ do: JSON.parse(json.value) }) } catch (e) { err.value = `Invalid JSON: ${(e as Error).message}` }
}
const actions = computed(() => (props.beat.do ?? []).map(a => ({ a, s: actionSummary(a) })))
</script>

<template>
  <UiCard :padded="false" class="beat" :tone="decision ? 'b' : undefined" :selected="approved && !decision">
    <div class="frame">
      <img v-if="frame" :src="frame" :alt="`Storyboard frame ${k}`" loading="lazy">
      <div v-else class="none">no frame yet</div>
      <div class="badges">
        <UiChip class="mono">{{ k }}</UiChip>
        <UiChip>{{ dur != null ? `${dur.toFixed(1)}s` : `~${estimate(say).toFixed(1)}s` }}</UiChip>
        <UiChip v-if="narrationStale" tone="b">narration pending</UiChip>
      </div>
    </div>
    <div class="body">
      <UiField v-model="say" :label="`Narration for ${k}`" hide-label multiline :rows="3" />
      <div v-if="dirty" class="row">
        <UiButton size="sm" variant="primary" @click="save({ say })">Save narration</UiButton>
        <UiButton size="sm" variant="ghost" @click="say = beat.say ?? ''">Revert</UiButton>
      </div>
      <template v-if="editing">
        <UiField v-model="json" :label="`Actions JSON for ${k}`" hide-label multiline mono :rows="8" />
        <div class="row">
          <UiButton size="sm" variant="primary" @click="saveActions">Save actions</UiButton>
          <UiButton size="sm" variant="ghost" @click="editing = false; err = ''">Cancel</UiButton>
        </div>
      </template>
      <ul v-else class="actions">
        <li v-for="(x, i) in actions" :key="i" :title="JSON.stringify(x.a)"><code>{{ x.s[0] }}</code> {{ x.s[1] }}</li>
        <li v-if="!actions.length">no actions</li>
      </ul>
      <p v-if="err" class="err">{{ err }}</p>
      <p v-if="decision" class="note">Change requested: {{ decision.note || '(no note)' }}</p>
      <UiButton v-if="comments" size="sm" variant="ghost" @click="emit('comments')">{{ comments }} open comment{{ comments > 1 ? 's' : '' }} →</UiButton>
      <div class="row foot">
        <DecisionButtons scope="beat" :k="k" :open="decision" :approved="approved" @decide="b => emit('decide', b)" />
        <span class="spacer" />
        <UiButton v-if="!editing" size="sm" variant="ghost" @click="json = JSON.stringify(beat.do ?? [], null, 2); editing = true">Edit actions</UiButton>
      </div>
    </div>
  </UiCard>
</template>

<style scoped>
.beat { display: flex; flex-direction: column; }
.frame { aspect-ratio: 16 / 9; background: #000; position: relative; }
.frame img { width: 100%; height: 100%; object-fit: cover; display: block; }
.none { position: absolute; inset: 0; display: grid; place-items: center; color: #8d95a6; font-size: 13px; }
.badges { position: absolute; top: 8px; left: 8px; display: flex; gap: 4px; flex-wrap: wrap; }
.badges :deep(.ui-chip) { background: rgb(0 0 0 / 0.72); color: #fff; border-color: transparent; }
.body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
.actions { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 3px; }
.actions li { font-size: 12.5px; color: rgb(var(--text-muted)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actions code { background: rgb(var(--accent) / 0.16); color: rgb(var(--text)); padding: 0 5px; border-radius: 4px; font-size: 11.5px; }
.note { margin: 0; font-size: 12.5px; padding: 6px 9px; border-radius: var(--radius); background: rgb(var(--b-fill) / 0.14); color: rgb(var(--text)); }
.foot { margin-top: auto; }
</style>
