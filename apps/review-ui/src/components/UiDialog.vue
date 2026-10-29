<!-- UiDialog — a modal (reka-ui Dialog: focus trap, Esc, focus return). Title is required: it names the dialog for assistive tech. -->
<script setup lang="ts">
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'

defineProps<{ title: string; description?: string }>()
const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="ui-dialog__scrim" />
      <DialogContent class="ui-dialog">
        <DialogTitle class="ui-dialog__title">{{ title }}</DialogTitle>
        <DialogDescription v-if="description" class="ui-dialog__desc">{{ description }}</DialogDescription>
        <div class="ui-dialog__body"><slot /></div>
        <div v-if="$slots.footer" class="ui-dialog__footer"><slot name="footer" /></div>
        <DialogClose class="ui-dialog__close" aria-label="Close">✕</DialogClose>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

<style>
.ui-dialog__scrim { position: fixed; inset: 0; background: rgb(var(--scrim) / 0.6); z-index: 60; }
.ui-dialog {
  position: fixed; z-index: 61; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: min(520px, calc(100vw - 32px)); max-height: calc(100vh - 64px); overflow: auto;
  background: rgb(var(--surface)); color: rgb(var(--text)); border: 1px solid rgb(var(--border));
  border-radius: var(--radius-lg); box-shadow: var(--lift-2); padding: var(--s5); font: 14px/1.5 var(--font);
}
.ui-dialog__title { margin: 0 0 var(--s2); font-size: 18px; }
.ui-dialog__desc { margin: 0 0 var(--s4); color: rgb(var(--text-2)); }
.ui-dialog__footer { display: flex; justify-content: flex-end; gap: var(--s2); margin-top: var(--s5); }
.ui-dialog__close { position: absolute; top: var(--s3); right: var(--s3); border: 0; background: none; color: rgb(var(--text-muted)); cursor: pointer; font-size: 14px; }
.ui-dialog__close:focus-visible { outline: 2px solid rgb(var(--focus)); }
</style>
