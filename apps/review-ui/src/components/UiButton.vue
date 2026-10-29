<!--
  UiButton — the themed pressable. `disabled`
  never sets the native attribute (that would make the control unfocusable and
  hide why it is inert); it is announced with aria-disabled, explained by
  `reason` (also the tooltip), and activation is suppressed at the source.
-->
<script setup lang="ts">
const props = withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  disabled?: boolean
  reason?: string
  type?: 'button' | 'submit' | 'reset'
}>(), { variant: 'secondary', size: 'md', disabled: false, reason: undefined, type: 'button' })

function suppress(event: Event) {
  if (!props.disabled) return
  event.preventDefault()
  event.stopImmediatePropagation()
}
</script>

<template>
  <button
    class="ui-button"
    :type="props.type"
    :data-variant="props.variant"
    :data-size="props.size"
    :aria-disabled="props.disabled ? 'true' : undefined"
    :data-disabled="props.disabled ? '' : undefined"
    :title="props.disabled && props.reason ? props.reason : undefined"
    @click.capture="suppress"
  >
    <slot />
  </button>
</template>

<style>
.ui-button {
  display: inline-flex; align-items: center; justify-content: center; gap: var(--s2);
  height: 32px; padding: 0 var(--s3); border-radius: var(--radius);
  border: 1px solid rgb(var(--border)); background: rgb(var(--surface-2)); color: rgb(var(--text));
  font: 500 14px/1 var(--font); white-space: nowrap; cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.ui-button[data-size='sm'] { height: 26px; padding: 0 var(--s2); font-size: 12.5px; }
.ui-button:hover:not([data-disabled]) { background: rgb(var(--surface-3)); }
.ui-button[data-variant='primary'] { background: rgb(var(--accent)); border-color: transparent; color: rgb(var(--on-accent)); font-weight: 600; }
.ui-button[data-variant='primary']:hover:not([data-disabled]) { background: rgb(var(--accent-hover)); }
.ui-button[data-variant='danger'] { background: rgb(var(--a-fill)); border-color: transparent; color: rgb(var(--a-on-fill)); }
.ui-button[data-variant='ghost'] { background: transparent; border-color: transparent; }
.ui-button[data-variant='ghost']:hover:not([data-disabled]) { background: rgb(var(--surface-2)); }
.ui-button[data-disabled] { opacity: 0.5; cursor: not-allowed; }
.ui-button:focus-visible { outline: 2px solid rgb(var(--focus)); outline-offset: 2px; }
</style>
