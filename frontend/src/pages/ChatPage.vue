<script setup lang="ts">
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import type { Observation, Page } from '../domain/types'
import { price } from '../domain/format'
import Icon from '../components/Icon.vue'
import PageHeader from '../components/PageHeader.vue'
import MerchantAvatar from '../components/MerchantAvatar.vue'
import MessageItem from '../components/MessageItem.vue'
const props = defineProps<{ data: Extract<Observation, { view: 'public' | 'private' }>; draft: string; sending: boolean; error: string }>()
defineEmits<{ navigate: [page: Page, merchantId?: string]; detail: [id: string]; info: []; draft: [text: string]; send: [] }>()
const privateChat = computed(() => props.data.view === 'private')
const network = inject('networkMode', false)
const merchant = computed(() => props.data.merchants.find(m => m.id === props.data.merchantId)!)
const product = computed(() => props.data.products.find(p => p.id === merchant.value.featuredProductId) || props.data.products[0])
const log = ref<HTMLElement>()
async function scrollToLast() { await nextTick(); if (log.value) log.value.scrollTop = log.value.scrollHeight }
watch(() => props.data.messages.at(-1)?.id, scrollToLast)
onMounted(scrollToLast)
function preview(id: string) {
  return props.data.view === 'private' ? props.data.conversations.find(c => c.merchantId === id)?.lastMessage.text : props.data.merchants.find(m => m.id === id)?.description
}
</script>
<template>
  <PageHeader :title="privateChat ? '和商家单独聊聊' : '一起聊聊，了解更多'" :subtitle="privateChat ? '这里的消息仅在你与当前商家的会话中可见。' : '每个商家一个讨论区，问题与回复向本场买家公开。'" @info="$emit('info')" />
  <div class="panel chat-layout">
    <aside class="chat-list"><div class="chat-list-title">{{ privateChat ? '商家会话' : '商家讨论区' }}</div>
      <button v-for="m in data.merchants" :key="m.id" type="button" class="contact" :class="{ selected: m.id === merchant.id }" :aria-label="m.name + (privateChat ? '私聊' : '讨论区')" @click="$emit('navigate', data.view, m.id)"><MerchantAvatar :merchant="m" /><span class="contact-copy"><strong>{{ m.name }}</strong><small>{{ preview(m.id) }}</small></span></button>
    </aside>
    <section class="chat-right">
      <div class="conversation-head"><div><strong>{{ merchant.name }}{{ privateChat ? '' : ' · 讨论区' }}</strong><p>{{ privateChat ? (network ? '私密会话 · 等待 Seller 后续 Wave 回复' : '私密会话 · 商家回复为演示预设') : '公开交流 · 本场参与者可见' }}</p></div><button class="btn small" @click="$emit('navigate', privateChat ? 'public' : 'private', merchant.id)">{{ privateChat ? '去公开交流' : '私聊商家' }}</button></div>
      <div v-if="privateChat && product" class="private-product-strip"><img :src="product.imageUrl" :alt="product.name" /><span>{{ product.name }} <b>¥{{ price(product.priceCents) }}</b></span><button class="text-btn" @click="$emit('detail', product.id)">查看商品</button></div>
      <div v-else class="sales-description"><div class="sales-copy"><div class="tiny"><Icon name="store" /> 商家销售描述</div><p>{{ merchant.pitch }}</p></div><div v-if="product" class="feature-product"><img :src="product.imageUrl" :alt="product.name" /><div><h3>{{ product.name }}</h3><div class="price"><i>¥</i>{{ price(product.priceCents) }}</div><button class="text-btn" @click="$emit('detail', product.id)">查看商品 →</button></div></div></div>
      <div ref="log" class="messages" role="log" :aria-label="privateChat ? '私聊消息' : '公开消息'" aria-live="polite"><MessageItem v-for="message in data.messages" :key="message.id" :message="message" :actor-id="data.actor.id" :merchant="data.merchants.find(m => m.id === message.author.id)" /></div>
      <form class="composer" @submit.prevent="$emit('send')">
        <label for="message-input">{{ privateChat ? `发送给 ${merchant.name} · 仅当前会话可见` : `发送至 ${merchant.name}讨论区 · 公开可见` }}（最多 500 字）</label>
        <div class="composer-row"><textarea id="message-input" :value="draft" maxlength="500" rows="1" :disabled="sending" :placeholder="privateChat ? '想了解什么？直接问问商家…' : '有想问的，和大家一起聊聊…'" :aria-label="privateChat ? '私聊消息内容' : '公开消息内容'" @input="$emit('draft', ($event.target as HTMLTextAreaElement).value)" /><button class="btn primary" type="submit" :disabled="sending || !draft.trim()">{{ sending ? (network ? '处理中…' : '发送中…') : network ? '加入本轮消息' : '发送' }} <Icon name="send" /></button></div>
        <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      </form>
    </section>
  </div>
</template>
