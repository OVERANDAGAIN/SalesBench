<script setup lang="ts">
import { inject } from 'vue'
import type { Merchant, Product } from '../domain/types'
import PageHeader from '../components/PageHeader.vue'
import Notice from '../components/Notice.vue'
import ProductCard from '../components/ProductCard.vue'
defineProps<{ products: Product[]; merchants: Merchant[]; filter?: string }>()
defineEmits<{ filter: [merchantId?: string]; detail: [id: string]; checkout: [id: string]; discuss: [merchantId: string]; info: [] }>()
const network = inject('networkMode', false)
</script>
<template>
  <PageHeader title="发现适合你的好物" subtitle="先看看商品，再选择交流或直接购买。" @info="$emit('info')" />
  <Notice>{{ network ? '真实公开 Listings · 当前按服务器观察顺序展示，未启用推荐算法。价格和库存以本 Wave 裁决为准。' : '演示推荐 · 以下为固定展示顺序，未启用个性化推荐。' }}</Notice>
  <p v-if="!products.length" class="panel empty-market">当前暂无已发布的在售商品。等待 Seller 完成本 Wave 后将自动刷新。</p>
  <div class="filters" aria-label="按商家浏览"><button class="chip" :class="{ active: !filter }" @click="$emit('filter')">全部商家</button><button v-for="m in merchants" :key="m.id" class="chip" :class="{ active: filter === m.id }" @click="$emit('filter', m.id)">{{ m.name }}</button></div>
  <div class="product-grid"><template v-for="product in products" :key="product.id"><ProductCard v-if="merchants.find(m => m.id === product.merchantId)" :product="product" :merchant="merchants.find(m => m.id === product.merchantId)!" @detail="$emit('detail', $event)" @checkout="$emit('checkout', $event)" @discuss="$emit('discuss', $event)" /></template></div>
</template>
