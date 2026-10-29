<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { UiCard, UiField } from '../components'
import { actionSummary, api, runUrl, toast, type Beat, type Run, type Script } from '../api'

const props = defineProps<{ run: Run }>()
const versions = computed(() => props.run.versions.map(v => v.version))
const base = ref(versions.value.length ? String(versions.value[versions.value.length - 1]) : '')
const old = ref<Script | null>(null)
watch(base, async v => {
  if (!v) return
  try { old.value = (await api<{ script: Script }>('GET', runUrl(props.run.name, `/versions/${v}`))).script } catch (e) { toast((e as Error).message) }
}, { immediate: true })
const beatsOf = (s: Script | null) => new Map((s?.scenes ?? []).flatMap(sc => sc.beats.map((b, i) => [`${sc.id}.${i}`, b] as [string, Beat])))
const kinds = (b?: Beat) => (b?.do ?? []).map(a => actionSummary(a)[0]).join(', ')
const rows = computed(() => {
  const a = beatsOf(old.value), b = beatsOf(props.run.script)
  return [...new Set([...a.keys(), ...b.keys()])].map(k => {
    const x = a.get(k), y = b.get(k)
    const sayChanged = (x?.say ?? '') !== (y?.say ?? '')
    const doChanged = JSON.stringify(x?.do ?? []) !== JSON.stringify(y?.do ?? [])
    return { k, x, y, changed: !x || !y || sayChanged || doChanged, sayChanged, doChanged }
  }).filter(r => r.changed)
})
const options = computed(() => versions.value.map(v => ({ value: String(v), label: `v${v}` })))
</script>

<template>
  <p v-if="!versions.length" class="muted">Nothing rendered yet — versions appear after each stitch. Only the latest video is kept; older versions keep their script.</p>
  <div v-else class="stack">
    <div class="row">
      <span>Current script compared with</span>
      <UiField v-model="base" label="Compare with version" hide-label :options="options" class="pick" />
      <span class="muted">{{ rows.length }} beat{{ rows.length === 1 ? '' : 's' }} differ</span>
    </div>
    <p v-if="old && !rows.length" class="muted">No differences.</p>
    <UiCard v-for="r in rows" :key="r.k" class="diff">
      <div class="mono">{{ r.k }}<br><span class="muted">{{ !r.x ? 'added' : !r.y ? 'removed' : [r.sayChanged && 'narration', r.doChanged && 'actions'].filter(Boolean).join(' + ') }}</span></div>
      <div><del v-if="r.x">{{ r.x.say ?? '' }}</del><span v-else class="muted">—</span><div v-if="r.doChanged && r.x" class="muted mono">{{ kinds(r.x) }}</div></div>
      <div><ins v-if="r.y">{{ r.y.say ?? '' }}</ins><span v-else class="muted">—</span><div v-if="r.doChanged && r.y" class="muted mono">{{ kinds(r.y) }}</div></div>
    </UiCard>
  </div>
</template>

<style scoped>
.pick { width: 120px; }
.diff { display: grid; grid-template-columns: 110px 1fr 1fr; gap: 12px; }
@media (max-width: 760px) { .diff { grid-template-columns: 1fr; } }
del { background: rgb(var(--a-fill) / 0.18); text-decoration: none; }
ins { background: rgb(var(--y-fill) / 0.18); text-decoration: none; }
</style>
