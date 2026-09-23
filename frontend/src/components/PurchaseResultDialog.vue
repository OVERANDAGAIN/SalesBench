<script setup lang="ts">
import type { ActionResult } from '../domain/types'
import { amount } from '../domain/format'
import ModalFrame from './ModalFrame.vue'
import Icon from './Icon.vue'
defineProps<{ result: Extract<ActionResult, { type: 'purchase' }> }>()
defineEmits<{ close: []; browse: []; history: [] }>()
</script>
<template>
  <ModalFrame title="购买完成" @close="$emit('close')"><div class="success-body"><div class="success-check"><Icon name="check" /></div><h2>已完成模拟购买</h2><p>{{ result.order.merchantName }} · {{ result.order.productName }} × {{ result.order.quantity }}</p><div class="success-amount">¥{{ amount(result.order.totalCents) }}</div><p>当前余额 ¥{{ amount(result.balanceCents) }}<br />本地购买记录已保存至「我的」</p></div><template #actions><button class="btn" @click="$emit('browse')">继续浏览</button><button class="btn primary" @click="$emit('history')">查看购买历史</button></template></ModalFrame>
</template>
