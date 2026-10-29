<!-- UiCard — a raised panel on the frame. `as` lets it be a link or an article. -->
<script setup lang="ts">
withDefaults(defineProps<{ as?: string; padded?: boolean; selected?: boolean; tone?: 'a' | 'b' | 'x' | 'y' }>(), { as: 'div', padded: true, selected: false, tone: undefined })
</script>

<template>
  <component :is="as" class="ui-card" :data-padded="padded ? '' : undefined" :data-selected="selected ? '' : undefined" :data-tone="tone"><slot /></component>
</template>

<style>
.ui-card {
  display: block; min-width: 0; background: rgb(var(--surface)); color: rgb(var(--text));
  border: 1px solid rgb(var(--rule)); border-radius: var(--radius-lg); box-shadow: var(--lift-2);
  text-decoration: none; overflow: hidden;
}
.ui-card[data-padded] { padding: var(--s3) var(--s4); }
.ui-card[data-selected] { border-color: rgb(var(--focus)); }
.ui-card[data-tone='a'] { border-color: rgb(var(--a-fill)); }
.ui-card[data-tone='b'] { border-color: rgb(var(--b-fill)); }
.ui-card[data-tone='x'] { border-color: rgb(var(--x-fill)); }
.ui-card[data-tone='y'] { border-color: rgb(var(--y-fill)); }
a.ui-card:hover, button.ui-card:hover { border-color: rgb(var(--border)); }
.ui-card:focus-visible { outline: 2px solid rgb(var(--focus)); outline-offset: 2px; }
</style>
