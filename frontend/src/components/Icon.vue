<script setup lang="ts">
withDefaults(defineProps<{ name?: string }>(), { name: 'info' })
const paths: Record<string, string> = {
  rank: 'M4 20v-7h4v7M10 20V5h4v15M16 20V9h4v11',
  products: 'M4.5 3h4A1.5 1.5 0 0 1 10 4.5v4A1.5 1.5 0 0 1 8.5 10h-4A1.5 1.5 0 0 1 3 8.5v-4A1.5 1.5 0 0 1 4.5 3ZM15.5 3h4A1.5 1.5 0 0 1 21 4.5v4a1.5 1.5 0 0 1-1.5 1.5h-4A1.5 1.5 0 0 1 14 8.5v-4A1.5 1.5 0 0 1 15.5 3ZM4.5 14h4a1.5 1.5 0 0 1 1.5 1.5v4A1.5 1.5 0 0 1 8.5 21h-4A1.5 1.5 0 0 1 3 19.5v-4A1.5 1.5 0 0 1 4.5 14ZM15.5 14h4a1.5 1.5 0 0 1 1.5 1.5v4a1.5 1.5 0 0 1-1.5 1.5h-4a1.5 1.5 0 0 1-1.5-1.5v-4a1.5 1.5 0 0 1 1.5-1.5Z',
  public: 'M20 11.5a8 8 0 0 1-8 7.5H7l-4 3 1-5A8 8 0 1 1 20 11.5ZM8 10h8M8 14h5',
  private: 'M6 5h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3Zm-2 2 8 6 8-6',
  me: 'M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2',
  wallet: 'M20 8H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h13v5M3 6v13a2 2 0 0 0 2 2h15V8M16 12h5v5h-5a2.5 2.5 0 0 1 0-5Z',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 11v6M12 7v1',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  store: 'm3 8 2-5h14l2 5v3H3V8Zm2 3v10h14V11M9 21v-6h6v6M7 3l-1 5m6-5v5m5-5 1 5',
  close: 'm6 6 12 12M6 18 18 6',
  check: 'm5 12 4 4L19 6',
  bag: 'M5 7h14l1 14H4L5 7ZM9 9V6a3 3 0 0 1 6 0v3',
  shield: 'm12 3 8 3v5c0 5-4 8-8 10-4-2-8-5-8-10V6l8-3Zm-4 9 3 3 5-6',
  send: 'm3 3 18 9-18 9 3-9-3-9Zm3 9h15',
}
</script>
<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true" stroke-linecap="round" stroke-linejoin="round"><path :d="paths[name] || paths.info" /></svg>
</template>
