<!-- UiThemePicker — Match system, Dark or Light, for the app's theme controller. -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { ThemeChoice, ThemeController } from '../theme'
import UiField from './UiField.vue'

const props = defineProps<{ controller: ThemeController; label?: string; hideLabel?: boolean }>()
const choice = ref(props.controller.choice)
const off = props.controller.onChange(c => { choice.value = c })
onBeforeUnmount(off)
const options = [
  { value: 'system', label: 'Match system' },
  { value: 'dark', label: 'Dark' },
  { value: 'light', label: 'Light' },
]
const model = computed({ get: () => choice.value, set: v => props.controller.set(v as ThemeChoice) })
</script>

<template>
  <UiField v-model="model" class="ui-theme-picker" :label="label ?? 'Theme'" :hide-label="hideLabel" :options="options" />
</template>
