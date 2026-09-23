<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Merchant, Product } from '../domain/types'
import { amount } from '../domain/format'
import ModalFrame from './ModalFrame.vue'
const props = defineProps<{ product: Product; merchant: Merchant; balanceCents: number; busy: boolean; error: string }>()
defineEmits<{ close: []; decline: []; detail: []; confirm: [quantity: number] }>()
const quantity = ref<number | string>(1)
const validNumber = computed(() => Number.isInteger(Number(quantity.value)) && Number(quantity.value) >= 1 && Number(quantity.value) <= 99)
const total = computed(() => validNumber.value ? props.product.priceCents * Number(quantity.value) : 0)
const validation = computed(() => !validNumber.value ? '请输入 1–99 的整数数量。' : Number(quantity.value) > props.product.stock ? '剩余库存不足，请调整数量。' : total.value > props.balanceCents ? '模拟余额不足，可以继续浏览其他商品。' : '')
</script>
<template>
  <ModalFrame title="确认模拟购买" :busy="busy" @close="$emit('close')">
    <div class="modal-body"><div class="checkout-product"><img :src="product.imageUrl" :alt="product.name" /><div><h3>{{ product.name }}</h3><p>{{ merchant.name }} · {{ product.variant }}</p></div></div><div class="summary-row"><span>单价</span><strong>¥{{ amount(product.priceCents) }}</strong></div><div class="summary-row"><label for="quantity">购买数量 <span class="tiny">（库存 {{ product.stock }} 件）</span></label><input id="quantity" v-model="quantity" class="quantity-input" type="number" min="1" :max="Math.min(product.stock, 99)" step="1" :disabled="busy" /></div><div class="summary-row total"><span>模拟支付</span><strong>{{ validNumber ? `¥${amount(total)}` : '—' }}</strong></div><div class="summary-row"><span>购买后余额</span><strong>{{ validNumber ? `¥${amount(balanceCents - total)}` : '—' }}</strong></div><div v-if="validation || error" class="field-error" role="alert">{{ validation || error }}</div><p v-if="busy" class="dialog-small-note" role="status">正在提交，请等待回执；尚未确认购买成功。</p><p class="dialog-small-note">本次操作只扣减模拟余额，并更新库存及购买历史，不涉及真实付款。</p></div>
    <template #actions><button class="text-btn" :disabled="busy" @click="$emit('decline')">暂不购买</button><button class="btn" :disabled="busy" @click="$emit('detail')">返回详情</button><button class="btn primary" :disabled="busy || !!validation" @click="$emit('confirm', Number(quantity))">{{ busy ? '提交中…' : '确认购买' }}</button></template>
  </ModalFrame>
</template>
