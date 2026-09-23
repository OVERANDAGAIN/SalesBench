<script setup lang="ts">
import type { Merchant, Page, Product } from '../domain/types'
import { price } from '../domain/format'
import ModalFrame from './ModalFrame.vue'
import Icon from './Icon.vue'
defineProps<{ product: Product; merchant: Merchant }>()
defineEmits<{ close: []; decline: []; checkout: []; navigate: [page: Page, merchantId: string] }>()
</script>
<template>
  <ModalFrame title="商品详情" @close="$emit('close')">
    <div class="modal-body"><div class="detail-top"><img :src="product.imageUrl" :alt="`${product.name}商品示意图`" /><div><div class="merchant-link"><Icon name="store" />{{ merchant.name }}</div><h2>{{ product.name }}</h2><p class="variant">{{ product.variant }}</p><div class="price"><i>¥</i>{{ price(product.priceCents) }}</div><div class="stock">剩余 {{ product.stock }} 件 · 商品图片为示意</div></div></div><div class="specs"><span v-for="spec in product.specs" :key="spec">{{ spec }}</span></div><p class="detail-description">{{ product.description }}</p><div class="detail-secondary"><button class="btn" @click="$emit('navigate', 'public', merchant.id)"><Icon name="public" />公开交流</button><button class="btn" @click="$emit('navigate', 'private', merchant.id)"><Icon name="private" />私聊商家</button></div></div>
    <template #actions><button class="text-btn" @click="$emit('decline')">暂不购买</button><button class="btn" @click="$emit('close')">继续浏览</button><button class="btn primary" :disabled="!product.stock" @click="$emit('checkout')">购买此商品</button></template>
  </ModalFrame>
</template>
