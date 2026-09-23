<script setup lang="ts">
import type { Merchant, Product } from '../domain/types'
import { price } from '../domain/format'
import Icon from './Icon.vue'
defineProps<{ product: Product; merchant: Merchant }>()
defineEmits<{ detail: [id: string]; checkout: [id: string]; discuss: [merchantId: string] }>()
</script>
<template>
  <article class="panel product-card">
    <button class="product-picture" type="button" :aria-label="`查看${product.name}详情`" @click="$emit('detail', product.id)"><img :src="product.imageUrl" :alt="`${product.name}商品示意图`" /><span class="photo-tag">商品示意</span></button>
    <div class="product-info">
      <button type="button" class="merchant-link" @click="$emit('discuss', merchant.id)"><Icon name="store" />{{ merchant.name }}</button>
      <h3>{{ product.name }}</h3><div class="variant">{{ product.variant }}</div>
      <div class="product-buy"><div><div class="price"><i>¥</i>{{ price(product.priceCents) }}</div><div class="stock">剩余 {{ product.stock }} 件</div></div><button class="btn soft" type="button" :disabled="!product.stock" @click="$emit('checkout', product.id)">{{ product.stock ? '直接购买' : '已售罄' }}</button></div>
    </div>
  </article>
</template>
