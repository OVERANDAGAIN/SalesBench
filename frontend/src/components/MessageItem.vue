<script setup lang="ts">
import type { Merchant, Message } from '../domain/types'
import { time } from '../domain/format'
import MerchantAvatar from './MerchantAvatar.vue'
defineProps<{ message: Message; actorId: string; merchant?: Merchant }>()
</script>
<template>
  <div class="message" :class="{ self: message.author.id === actorId, 'merchant-message': message.author.role === 'merchant' }">
    <MerchantAvatar v-if="merchant && message.author.role === 'merchant'" :merchant="merchant" /><span v-else class="message-avatar">{{ message.author.id === actorId ? '我' : message.author.name.slice(0, 1) }}</span>
    <div><div class="message-meta"><span>{{ message.author.name }}</span><span v-if="message.author.role === 'merchant'" class="preset-tag">{{ message.isPreset ? '商家 · 预设回复' : '商家' }}</span><span v-else-if="message.isPreset" class="preset-tag">演示买家</span><time :datetime="message.createdAt.startsWith('step:') ? undefined : message.createdAt">{{ time(message.createdAt) }}</time></div><div class="message-bubble">{{ message.text }}</div></div>
  </div>
</template>
