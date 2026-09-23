<script setup lang="ts">
import Icon from './Icon.vue'
defineProps<{ title: string; subtitle: string }>()
defineEmits<{ info: [] }>()
</script>
<template>
  <div class="page-head"><div><div class="eyebrow">买方体验 / 演示场次 01</div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div><button type="button" class="quiet-button" @click="$emit('info')"><Icon name="info" />演示说明</button></div>
</template>
