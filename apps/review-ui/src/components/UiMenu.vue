<!-- UiMenu — a button that opens a list of actions (reka-ui DropdownMenu: keyboard, typeahead, focus return). -->
<script setup lang="ts">
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'
import UiButton from './UiButton.vue'

defineProps<{
  label: string
  items: ReadonlyArray<{ id: string; label: string; hint?: string; disabled?: boolean; danger?: boolean }>
  disabled?: boolean
  size?: 'sm' | 'md'
}>()
const emit = defineEmits<{ select: [id: string] }>()
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child :disabled="disabled">
      <UiButton :size="size" :disabled="disabled">{{ label }} <span aria-hidden="true">▾</span></UiButton>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent class="ui-menu" :side-offset="4" align="end">
        <DropdownMenuItem v-for="item in items" :key="item.id" class="ui-menu__item" :disabled="item.disabled"
          :data-danger="item.danger ? '' : undefined" @select="emit('select', item.id)">
          <span>{{ item.label }}</span><span v-if="item.hint" class="ui-menu__hint">{{ item.hint }}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>

<style>
.ui-menu {
  min-width: 200px; padding: 4px; z-index: 50; background: rgb(var(--surface)); color: rgb(var(--text));
  border: 1px solid rgb(var(--border)); border-radius: var(--radius-lg); box-shadow: var(--lift-2); font: 14px/1.4 var(--font);
}
.ui-menu__item { display: flex; justify-content: space-between; gap: var(--s3); padding: 7px 10px; border-radius: var(--radius); cursor: pointer; outline: none; }
.ui-menu__item[data-highlighted] { background: rgb(var(--surface-2)); }
.ui-menu__item[data-disabled] { color: rgb(var(--text-disabled)); cursor: not-allowed; }
.ui-menu__item[data-danger] { color: rgb(var(--a)); }
.ui-menu__hint { color: rgb(var(--text-muted)); font-size: 12px; }
</style>
