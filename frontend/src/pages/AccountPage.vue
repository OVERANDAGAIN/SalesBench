<script setup lang="ts">
import { inject } from 'vue'
import type { Account, Actor, Order } from '../domain/types'
import { amount, time } from '../domain/format'
import PageHeader from '../components/PageHeader.vue'
import Icon from '../components/Icon.vue'
defineProps<{ account: Account; actor: Actor; orders: Order[] }>()
defineEmits<{ browse: []; info: [] }>()
const network = inject('networkMode', false)
</script>
<template>
  <PageHeader title="我的购买与余额" subtitle="每一次选择，都可以在这里回看。" @info="$emit('info')" />
  <div class="account-grid"><section class="wallet"><div class="eyebrow">当前可用余额</div><Icon name="wallet" /><div class="balance"><span>¥ </span>{{ amount(actor.balanceCents) }}</div><p>{{ network ? 'PostgreSQL 已提交的实验资金 · 无真实付款' : '初始模拟余额 ¥' + (account.initialBalanceCents === null ? '—' : amount(account.initialBalanceCents)) + ' · 无真实资金' }}</p></section><section class="stat-card"><div class="label">{{ network ? '已成交支出' : '累计模拟支出' }}</div><div class="stat">¥{{ amount(account.spentCents) }}</div><div class="tiny">本次会话已完成的购买</div></section><section class="stat-card"><div class="label">购买记录</div><div class="stat">{{ orders.length }} <span class="stat-unit">笔</span></div><div class="tiny">共 {{ orders.reduce((n, o) => n + o.quantity, 0) }} 件商品</div></section></div>
  <section class="panel history"><div class="history-head"><h2>购买历史</h2><button class="btn small" @click="$emit('browse')">继续浏览 <Icon name="arrow" /></button></div>
    <div v-if="orders.length" class="table-wrap"><table><thead><tr><th>商品 / 商家</th><th>数量</th><th>金额</th><th>状态</th><th>购买时间</th></tr></thead><tbody><tr v-for="order in orders" :key="order.id"><td class="order-product">{{ order.productName }}<small>{{ order.merchantName }} · {{ order.id }}</small></td><td>{{ order.quantity }} 件</td><td><b>¥{{ amount(order.totalCents) }}</b></td><td><span class="order-status">{{ order.status === 'completed' ? '已成交 · TEST 结算' : '模拟购买完成' }}</span></td><td class="muted">{{ time(order.createdAt) }}</td></tr></tbody></table></div>
    <div v-else class="empty-state"><Icon name="bag" /><h3>还没有购买记录</h3><p>可以先浏览、聊聊，等找到需要的再购买。</p><button class="btn primary" @click="$emit('browse')">去看看商品</button></div>
  </section>
  <p class="account-note"><Icon name="info" />{{ network ? '余额和订单来自服务端已提交观察；刷新与服务重启不会重置本场数据。' : '所有购买均为模拟操作；刷新或重新打开页面会重置本次会话。' }}</p>
</template>
