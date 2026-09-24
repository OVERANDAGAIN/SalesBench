<script setup lang="ts">
import { inject } from 'vue'
import Icon from './Icon.vue'
defineProps<{ title: string; subtitle: string }>()
defineEmits<{ info: [] }>()
const network = inject('networkMode', false)
</script>
<template>
  <div class="page-head"><div><div class="eyebrow">买方体验 / {{ network ? '当前持久场次' : '演示场次 01' }}</div><h1>{{ title }}</h1><p>{{ subtitle }}</p></div><button type="button" class="quiet-button" @click="$emit('info')"><Icon name="info" />{{ network ? '市场说明' : '演示说明' }}</button></div>
</template>
