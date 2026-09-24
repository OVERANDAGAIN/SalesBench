<script setup lang="ts">
import { provide } from 'vue'
import type { BuyerService, Page } from './domain/types'
import type { NetworkBuyerService } from './platform/buyer'
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

const props = defineProps<{ service: BuyerService | NetworkBuyerService; demoMode: boolean }>()
provide('networkMode', !props.demoMode)
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
    <div class="side-foot"><span class="demo-badge">{{ demoMode ? '本地演示 · Vue' : '真实共享市场 · 已持久化' }}</span><p>实验商品与商家<br />自由浏览，自主选择</p></div>
  </aside>
  <div class="main">
    <header class="topbar"><div class="breadcrumb">买方空间 <span>/</span> <strong>{{ pages.find(p => p.id === state.page)?.title }}</strong></div><div class="mobile-brand"><Icon name="rank" />SalesBench</div><div class="userbar"><span class="balance-pill"><Icon name="wallet" /> {{ demoMode ? '模拟余额' : '已提交余额' }} <b>{{ state.actor ? `¥ ${amount(state.actor.balanceCents)}` : '—' }}</b></span><span class="user-chip"><span class="user-avatar">我</span><span>{{ state.actor?.name || '买家' }}</span></span></div></header>
    <main class="content" :aria-busy="state.loading">
      <slot name="market" />
      <div v-if="state.loading" class="loading-status" role="status">{{ state.snapshot ? '正在更新…' : demoMode ? '正在读取演示数据…' : '正在读取市场数据…' }}</div>
      <div v-if="state.error" class="load-error panel" role="alert"><h2>暂时无法读取</h2><p>{{ state.error }}</p><button class="btn" :disabled="state.loading" @click="refresh">重新读取</button></div>
      <template v-if="!state.error && state.snapshot && state.snapshot.view === state.page">
        <RankingPage v-if="state.snapshot.view === 'leaderboard'" :rows="state.snapshot.leaderboard" :snapshot="state.snapshot.leaderboardSnapshot" @navigate="navigate" @info="info" />
        <ProductsPage v-else-if="state.snapshot.view === 'products'" :products="state.snapshot.products" :merchants="state.snapshot.merchants" :filter="state.filterMerchantId" @filter="navigate('products', $event)" @detail="openProduct($event)" @checkout="openProduct($event, 'checkout')" @discuss="navigate('public', $event)" @info="info" />
        <ChatPage v-else-if="state.snapshot.view === 'public' || state.snapshot.view === 'private'" :data="state.snapshot" :draft="draft" :sending="state.sending || state.loading" :error="state.messageError" @navigate="navigate" @detail="openProduct($event)" @draft="setDraft" @send="send" @info="info" />
        <AccountPage v-else-if="state.snapshot.view === 'me'" :actor="state.snapshot.actor" :account="state.snapshot.account" :orders="state.snapshot.orders" @browse="navigate('products')" @info="info" />
      </template>
    </main>
  </div>
  <DetailDialog v-if="state.dialog === 'detail' && state.product && state.merchant" :product="state.product" :merchant="state.merchant" @close="close" @decline="decline" @checkout="openProduct(state.product.id, 'checkout')" @navigate="navigate" />
  <CheckoutDialog v-else-if="state.dialog === 'checkout' && state.product && state.merchant" :product="state.product" :merchant="state.merchant" :balance-cents="state.checkoutBalanceCents" :busy="state.purchasing" :error="state.purchaseError" @close="close" @decline="decline" @detail="openProduct(state.product.id)" @confirm="confirmPurchase" />
  <PurchaseResultDialog v-else-if="state.dialog === 'result' && state.result" :result="state.result" @close="close" @browse="navigate('products')" @history="navigate('me')" />
  <DemoInfoDialog v-else-if="state.dialog === 'config' && demoMode" @close="close" />
  <ModalFrame v-else-if="state.dialog === 'config'" title="市场与实验说明" @close="close"><div class="modal-body"><p>当前五页读取真实授权 observation。消息和购买先加入本轮草稿，统一提交；同 Wave 收齐后由 Runner / Engine 裁决，PostgreSQL 提交成功才更新余额与订单。</p><p>资金、供给、即时成交仍是 TEST economic rules，无真实付款；排行榜与推荐算法尚未发布。Seller 回复来自操作者，不自动生成。</p><p>公共消息向本场公开，私聊只对双方可见；刷新和服务重启不重置持久 session。关闭弹窗不自动提交，未提交不等于 Wait。</p></div></ModalFrame>
  <ModalFrame v-else-if="state.dialog === 'loading'" title="读取商品" @close="close"><div class="modal-body"><p v-if="state.dialogError" class="field-error" role="alert">{{ state.dialogError }}</p><p v-else role="status">正在读取商品信息…</p></div></ModalFrame>
  <div id="toast" :class="{ show: !!state.toast }" role="status" aria-live="polite">{{ state.toast }}</div>
</template>
