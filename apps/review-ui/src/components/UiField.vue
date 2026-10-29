<!--
  UiField — a labelled input, textarea or select. `multiline` makes a textarea;
  `options` makes a select. The label is always rendered (use `hideLabel` to keep
  it for assistive tech only); `hint` and `error` are linked with aria-describedby.
-->
<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  hideLabel?: boolean
  hint?: string
  error?: string
  multiline?: boolean
  rows?: number
  options?: ReadonlyArray<{ value: string; label: string; group?: string }>
  placeholder?: string
  mono?: boolean
  type?: string
}>(), { hideLabel: false, hint: undefined, error: undefined, multiline: false, rows: 3, options: undefined, placeholder: undefined, mono: false, type: 'text' })
const model = defineModel<string>({ default: '' })
const id = useId()
const described = computed(() => [props.hint && `${id}-hint`, props.error && `${id}-error`].filter(Boolean).join(' ') || undefined)
const groups = computed(() => {
  const out = new Map<string, Array<{ value: string; label: string }>>()
  for (const o of props.options ?? []) { const g = o.group ?? ''; if (!out.has(g)) out.set(g, []); out.get(g)!.push(o) }
  return [...out]
})
</script>

<template>
  <div class="ui-field" :data-invalid="error ? '' : undefined">
    <label :for="id" class="ui-field__label" :class="{ 'ui-sr-only': hideLabel }">{{ label }}</label>
    <select v-if="options" :id="id" v-model="model" class="ui-field__control" :aria-describedby="described" :aria-invalid="error ? 'true' : undefined">
      <template v-for="[group, items] in groups" :key="group">
        <optgroup v-if="group" :label="group"><option v-for="o in items" :key="o.value" :value="o.value">{{ o.label }}</option></optgroup>
        <template v-else><option v-for="o in items" :key="o.value" :value="o.value">{{ o.label }}</option></template>
      </template>
    </select>
    <textarea v-else-if="multiline" :id="id" v-model="model" class="ui-field__control" :rows="rows" :placeholder="placeholder"
      :data-mono="mono ? '' : undefined" :aria-describedby="described" :aria-invalid="error ? 'true' : undefined" />
    <input v-else :id="id" v-model="model" class="ui-field__control" :type="type" :placeholder="placeholder"
      :data-mono="mono ? '' : undefined" :aria-describedby="described" :aria-invalid="error ? 'true' : undefined">
    <p v-if="hint" :id="`${id}-hint`" class="ui-field__hint">{{ hint }}</p>
    <p v-if="error" :id="`${id}-error`" class="ui-field__error">{{ error }}</p>
  </div>
</template>

<style>
.ui-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.ui-field__label { font: 600 12px/1.4 var(--font); color: rgb(var(--text-2)); }
.ui-field__control {
  box-sizing: border-box; width: 100%; min-width: 0; padding: 7px 10px; border-radius: var(--radius); border: 1px solid rgb(var(--border));
  background: rgb(var(--surface-2)); color: rgb(var(--text)); font: 14px/1.45 var(--font); resize: vertical;
}
.ui-field__control[data-mono] { font-family: var(--mono); font-size: 12.5px; }
.ui-field__control:focus-visible { outline: 2px solid rgb(var(--focus)); outline-offset: 1px; }
.ui-field[data-invalid] .ui-field__control { border-color: rgb(var(--a-fill)); }
.ui-field__hint { margin: 0; font: 12px/1.4 var(--font); color: rgb(var(--text-muted)); }
.ui-field__error { margin: 0; font: 12px/1.4 var(--font); color: rgb(var(--a)); white-space: pre-wrap; }
.ui-sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
</style>
