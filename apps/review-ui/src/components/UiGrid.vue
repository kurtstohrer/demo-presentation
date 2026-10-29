<!-- UiGrid — cards that fill the row: auto-fill columns no narrower than `min`, one column on a phone. -->
<script setup lang="ts">
withDefaults(defineProps<{ min?: string; gap?: string }>(), { min: '300px', gap: 'var(--s4)' })
</script>

<template>
  <div class="ui-grid" :style="{ '--ui-grid-min': min, '--ui-grid-gap': gap }"><slot /></div>
</template>

<style>
.ui-grid { display: grid; gap: var(--ui-grid-gap); grid-template-columns: repeat(auto-fill, minmax(min(var(--ui-grid-min), 100%), 1fr)); }
</style>
