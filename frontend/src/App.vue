<script setup lang="ts">
import type { BuyerService, Page } from './domain/types'
import { amount } from './domain/format'
import { useBuyerApp } from './state/useBuyerApp'
import Icon from './components/Icon.vue'
import RankingPage from './pages/RankingPage.vue'
import ProductsPage from './pages/ProductsPage.vue'
import ChatPage from './pages/ChatPage.vue'
import AccountPage from './pages/AccountPage.vue'
import DetailDialog from './components/DetailDialog.vue'
import CheckoutDialog from './components/CheckoutDialog.vue'
import PurchaseResultDialog from './components/PurchaseResultDialog.vue'
import DemoInfoDialog from './components/DemoInfoDialog.vue'
import ModalFrame from './components/ModalFrame.vue'

const props = defineProps<{ service: BuyerService; demoMode: boolean }>()
const { state, draft, refresh, navigate, openProduct, close, confirmPurchase, decline, setDraft, send } = useBuyerApp(props.service)
const pages: { id: Page; title: string; icon: string }[] = [
  { id: 'leaderboard', title: '排行榜', icon: 'rank' }, { id: 'products', title: '商品推荐', icon: 'products' },
  { id: 'public', title: '公共交流', icon: 'public' }, { id: 'private', title: '私聊', icon: 'private' }, { id: 'me', title: '我的', icon: 'me' },
]
function info() { state.dialog = 'config' }
</script>
<template>
  <aside class="sidebar">
    <div class="brand"><span class="brand-icon"><Icon name="rank" /></span><span class="brand-name">SalesBench</span></div><div class="brand-sub">买 方 体 验</div>
    <nav class="nav" aria-label="主导航"><button v-for="page in pages" :key="page.id" type="button" :class="{ active: page.id === state.page }" :aria-current="page.id === state.page ? 'page' : undefined" @click="navigate(page.id)"><Icon :name="page.icon" /><span>{{ page.title }}</span></button></nav>
    <div class="side-foot"><span class="demo-badge">{{ demoMode ? '本地演示 · Vue' : '真实接口未接入' }}</span><p>模拟商品与商家<br />自由浏览，自主选择</p></div>
  </aside>
  <div class="main">
    <header class="topbar"><div class="breadcrumb">买方空间 <span>/</span> <strong>{{ pages.find(p => p.id === state.page)?.title }}</strong></div><div class="mobile-brand"><Icon name="rank" />SalesBench</div><div class="userbar"><span class="balance-pill"><Icon name="wallet" /> 模拟余额 <b>{{ state.actor ? `¥ ${amount(state.actor.balanceCents)}` : '—' }}</b></span><span class="user-chip"><span class="user-avatar">我</span><span>{{ state.actor?.name || '体验买家' }} <span class="muted tiny">#001</span></span></span></div></header>
    <main class="content" :aria-busy="state.loading">
      <div v-if="state.loading" class="loading-status" role="status">{{ state.snapshot ? '正在更新…' : '正在读取演示数据…' }}</div>
      <div v-if="state.error" class="load-error panel" role="alert"><h2>暂时无法读取</h2><p>{{ state.error }}</p><button class="btn" :disabled="state.loading" @click="refresh">重新读取</button></div>
      <template v-if="!state.error && state.snapshot && state.snapshot.view === state.page">
        <RankingPage v-if="state.snapshot.view === 'leaderboard'" :rows="state.snapshot.leaderboard" @navigate="navigate" @info="info" />
        <ProductsPage v-else-if="state.snapshot.view === 'products'" :products="state.snapshot.products" :merchants="state.snapshot.merchants" :filter="state.filterMerchantId" @filter="navigate('products', $event)" @detail="openProduct($event)" @checkout="openProduct($event, 'checkout')" @discuss="navigate('public', $event)" @info="info" />
        <ChatPage v-else-if="state.snapshot.view === 'public' || state.snapshot.view === 'private'" :data="state.snapshot" :draft="draft" :sending="state.sending || state.loading" :error="state.messageError" @navigate="navigate" @detail="openProduct($event)" @draft="setDraft" @send="send" @info="info" />
        <AccountPage v-else-if="state.snapshot.view === 'me'" :actor="state.snapshot.actor" :account="state.snapshot.account" :orders="state.snapshot.orders" @browse="navigate('products')" @info="info" />
      </template>
    </main>
  </div>
  <DetailDialog v-if="state.dialog === 'detail' && state.product && state.merchant" :product="state.product" :merchant="state.merchant" @close="close" @decline="decline" @checkout="openProduct(state.product.id, 'checkout')" @navigate="navigate" />
  <CheckoutDialog v-else-if="state.dialog === 'checkout' && state.product && state.merchant" :product="state.product" :merchant="state.merchant" :balance-cents="state.checkoutBalanceCents" :busy="state.purchasing" :error="state.purchaseError" @close="close" @decline="decline" @detail="openProduct(state.product.id)" @confirm="confirmPurchase" />
  <PurchaseResultDialog v-else-if="state.dialog === 'result' && state.result" :result="state.result" @close="close" @browse="navigate('products')" @history="navigate('me')" />
  <DemoInfoDialog v-else-if="state.dialog === 'config'" @close="close" />
  <ModalFrame v-else-if="state.dialog === 'loading'" title="读取商品" @close="close"><div class="modal-body"><p v-if="state.dialogError" class="field-error" role="alert">{{ state.dialogError }}</p><p v-else role="status">正在读取商品信息…</p></div></ModalFrame>
  <div id="toast" :class="{ show: !!state.toast }" role="status" aria-live="polite">{{ state.toast }}</div>
</template>
