<script setup lang="ts">
import type { Merchant } from '../domain/types'
defineProps<{ merchant: Merchant }>()
</script>
<template><span class="merchant-avatar" :class="merchant.color">{{ merchant.initial }}</span></template>
