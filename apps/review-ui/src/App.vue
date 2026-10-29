<script setup lang="ts">
import { computed } from 'vue'
import type { ThemeController } from './theme'
import { hash, toastText } from './api'
import Runs from './views/Runs.vue'
import RunView from './views/RunView.vue'

defineProps<{ theme: ThemeController }>()
const route = computed(() => {
  const m = hash.value.match(/^#\/run\/([^/]+)(?:\/(\w+))?/)
  return m ? { name: decodeURIComponent(m[1]), tab: m[2] } : null
})
</script>

<template>
  <RunView v-if="route" :key="route.name" :name="route.name" :tab="route.tab" :theme="theme" />
  <Runs v-else :theme="theme" />
  <div v-if="toastText" class="toast" role="status">{{ toastText }}</div>
</template>
